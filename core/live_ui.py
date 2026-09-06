"""
Chimeras v3.3 — Live Operation TUI

Flicker-free full-screen rendering for a running operation (Rich Live).

Layout:
  Header   — mission name, scope, elapsed time, mission state
  Left     — Progress: per-bot status table + rolling activity log
  Right    — Findings: live table from the per-bot JSONL findings store
  Footer   — counters (findings by severity, tool executions, decisions, phase)

Design notes:
  - Rich Live with screen=True (alternate buffer) — zero scroll, zero flicker.
  - All mutations are locked; bots log from graph-node threads.
  - JSONL findings are re-scanned at most once per second (files are small).
  - Gates call pause() so input() prompts work in normal terminal mode.
  - Falls back to legacy print() output when stdout is not a TTY or when
    the UI was never started (headless/--approve/CI runs).

Integration:
  BaseBot._log() → ui.log()        (activity feed)
  graph._with_checkpoint → ui.node_started/node_done
  gate nodes → with ui.pause(): input()
  main.run_operation → ui.start() ... ui.stop()
"""

import json
import sys
import threading
import time
from collections import deque
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

_SEVERITY_STYLE = {
    "critical": "bold white on dark_red",
    "high": "bold red",
    "medium": "yellow",
    "low": "blue",
    "info": "dim",
}

_BOT_ORDER = ["warchief", "aria", "lisa", "bloodhound", "wasp",
              "marksman", "magician", "thief", "bookkeeper"]

_BOT_ICON = {
    "warchief": "👑", "aria": "🔍", "lisa": "📡", "bloodhound": "🩺",
    "wasp": "🐝", "marksman": "🎯", "magician": "🎩", "thief": "📦",
    "bookkeeper": "📝",
}

_STATUS_STYLE = {
    "running": "bold green", "done": "green", "waiting": "dim",
    "failed": "bold red", "skipped": "dim yellow",
}


class OperationAbort(Exception):
    """Raised inside a graph node wrapper when the operator pauses and
    chooses to quit. The checkpoint from the last completed node stays
    on disk — `python main.py run --resume` continues from there."""


class _Frame:
    """Re-renderable wrapper — Live calls __rich__ on every refresh so the
    Layout is rebuilt from current state each frame (flicker-free redraw)."""

    def __init__(self, ui: "OperationUI"):
        self.ui = ui

    def __rich__(self):
        return self.ui._render_frame()


class OperationUI:
    """Singleton live dashboard for the running operation."""

    _instance: Optional["OperationUI"] = None

    def __init__(self, mission_name: str, scope: str, engagement_dir: Path):
        self.mission_name = mission_name
        self.scope = scope
        self.engagement_dir = Path(engagement_dir)

        self._lock = threading.Lock()
        self._started_at = time.time()
        self._log_lines: deque = deque(maxlen=500)
        self._bots: Dict[str, Dict[str, Any]] = {
            b: {"status": "waiting", "started": None, "elapsed": 0.0}
            for b in _BOT_ORDER
        }
        self._mission_state = "init"
        self._tool_execs = 0
        self._decisions = 0
        self._findings: List[Dict[str, Any]] = []
        self._findings_scanned_at = 0.0

        self.console = Console()
        self._live: Optional[Live] = None

        # Keyboard control: background thread reads single keys in cbreak
        # mode while the Live screen owns the terminal; graph nodes pop them
        # at node boundaries. p = pause, q = pause-and-quit.
        self._key_queue: deque = deque(maxlen=16)
        self._kb_thread: Optional[threading.Thread] = None
        self._kb_stop = threading.Event()
        self._kb_fd: Optional[int] = None
        self._kb_termios = None

    # ── lifecycle ────────────────────────────────────────────────────

    @classmethod
    def create(cls, mission_name: str, scope: str,
               engagement_dir: Path, enabled: bool = True) -> "OperationUI":
        ui = cls(mission_name, scope, engagement_dir)
        if enabled:
            cls._instance = ui
            ui.start()
        else:
            cls._instance = None
        return ui

    @classmethod
    def current(cls) -> Optional["OperationUI"]:
        return cls._instance

    def start(self):
        self._live = Live(_Frame(self), console=self.console,
                          screen=True, refresh_per_second=4, transient=False)
        self._live.start()
        self._start_keyboard()

    def stop(self):
        self._stop_keyboard()
        if self._live is not None:
            try:
                self._live.update(self._render_frame(), refresh=True)
                self._live.stop()
            finally:
                self._live = None
                OperationUI._instance = None

    def is_active(self) -> bool:
        return self._live is not None

    # ── keyboard listener (pause/quit control) ───────────────────────

    def _start_keyboard(self):
        if not sys.stdin.isatty():
            return
        import termios
        self._kb_fd = sys.stdin.fileno()
        self._kb_termios = termios.tcgetattr(self._kb_fd)
        self._kb_stop.clear()
        self._kb_thread = threading.Thread(
            target=self._kb_loop, name="tui-keys", daemon=True)
        self._kb_thread.start()

    def _kb_loop(self):
        import select
        import termios
        import tty
        fd = self._kb_fd
        try:
            tty.setcbreak(fd)
            while not self._kb_stop.is_set():
                r, _, _ = select.select([fd], [], [], 0.2)
                if not r:
                    continue
                try:
                    ch = sys.stdin.read(1)
                except OSError:
                    break
                if ch:
                    with self._lock:
                        self._key_queue.append(ch)
        except (OSError, termios.error):
            pass
        finally:
            if self._kb_termios is not None:
                try:
                    termios.tcsetattr(fd, termios.TCSADRAIN, self._kb_termios)
                except termios.error:
                    pass

    def _stop_keyboard(self):
        self._kb_stop.set()
        t = self._kb_thread
        if t and t.is_alive():
            t.join(timeout=1.0)
        self._kb_thread = None

    def pop_key(self) -> Optional[str]:
        """Return the oldest queued keypress, or None."""
        with self._lock:
            if self._key_queue:
                return self._key_queue.popleft()
        return None

    @contextmanager
    def pause(self):
        """Suspend the live display and the keyboard listener so
        input()/Prompts work normally."""
        live, self._live = self._live, None
        was_started = live is not None
        if was_started:
            self._stop_keyboard()
            live.stop()
        try:
            yield
        finally:
            if was_started:
                live.start()
                self._start_keyboard()
                self._live = live

    # ── event API (called from bots / graph nodes) ───────────────────

    def log(self, bot: str, level: str, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self._log_lines.append((ts, bot.upper(), level, message))
            if level == "EXEC":
                self._tool_execs += 1

    def decision(self):
        with self._lock:
            self._decisions += 1

    def set_mission_state(self, state: str):
        with self._lock:
            self._mission_state = state

    def node_started(self, name: str):
        with self._lock:
            info = self._bots.setdefault(name, {"started": None, "elapsed": 0.0})
            info["status"] = "running"
            info["started"] = time.time()

    def node_done(self, name: str, failed: bool = False):
        with self._lock:
            info = self._bots.setdefault(name, {"started": None, "elapsed": 0.0})
            if info["started"]:
                info["elapsed"] += time.time() - info["started"]
                info["started"] = None
            info["status"] = "failed" if failed else "done"

    # ── findings polling ─────────────────────────────────────────────

    def _scan_findings(self):
        now = time.time()
        if now - self._findings_scanned_at < 1.0:
            return
        self._findings_scanned_at = now
        findings: List[Dict[str, Any]] = []
        try:
            for path in sorted(self.engagement_dir.glob("findings_*.jsonl")):
                bot = path.stem.replace("findings_", "")
                with open(path) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            finding = json.loads(line)
                            if isinstance(finding, dict):
                                finding.setdefault("bot", bot)
                                findings.append(finding)
                        except json.JSONDecodeError:
                            continue
        except OSError:
            return
        with self._lock:
            self._findings = findings

    # ── rendering ────────────────────────────────────────────────────

    def _render_frame(self) -> Layout:
        self._scan_findings()
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        layout["body"].split_row(
            Layout(name="progress", ratio=1),
            Layout(name="findings", ratio=1),
        )
        layout["header"].update(self._header())
        layout["findings"].update(self._findings_panel())
        layout["progress"].update(self._progress_panel())
        layout["footer"].update(self._footer())
        return layout

    def _header(self) -> Panel:
        with self._lock:
            elapsed = time.time() - self._started_at
            state = self._mission_state
        mm, ss = divmod(int(elapsed), 60)
        text = Text.assemble(
            (" CHIMERAS ", "bold white on red"),
            (f"  {self.mission_name}", "bold"),
            (f"   scope: {self.scope or 'N/A'}", "dim"),
            (f"   state: {state}", "cyan"),
            (f"   {mm:02d}:{ss:02d}", "dim"),
        )
        return Panel(text, style="red", padding=(0, 1))

    def _findings_panel(self) -> Panel:
        with self._lock:
            findings = list(self._findings)
        table = Table(box=None, expand=True, show_header=True,
                      header_style="bold", pad_edge=False)
        table.add_column("Sev", width=8)
        table.add_column("CVSS", width=5, justify="right")
        table.add_column("Finding", overflow="fold", ratio=3)
        table.add_column("Host", overflow="fold", ratio=2)

        # Low/info findings are counted but not displayed — noise reduction
        severities = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        displayable = [f for f in findings
                       if str(f.get("severity", "info")).lower() in
                       ("critical", "high", "medium")]
        hidden = len(findings) - len(displayable)
        ordered = sorted(
            displayable,
            key=lambda f: severities.get(str(f.get("severity", "info")).lower(), 5),
        )
        # most severe on top; cap to last-frame capacity
        shown = ordered[:22]
        for f in shown:
            sev = str(f.get("severity", "info")).lower()
            style = _SEVERITY_STYLE.get(sev, "dim")
            title = f.get("title") or f.get("vuln_type") or \
                (f.get("description") or "")[:60] or "finding"
            cvss = f.get("cvss")
            cvss_str = f"{cvss:.1f}" if isinstance(cvss, (int, float)) else "-"
            host = str(f.get("host") or f.get("port") or "")[:22]
            table.add_row(Text(sev.upper(), style=style), cvss_str,
                          Text(str(title)[:44]), host)

        counts: Dict[str, int] = {}
        for f in findings:
            sev = str(f.get("severity", "info")).lower()
            counts[sev] = counts.get(sev, 0) + 1
        subtitle = "  ".join(
            f"{s}:{counts[s]}" for s in ("critical", "high", "medium")
            if counts.get(s)
        )
        if hidden:
            subtitle = (subtitle + "  " if subtitle else "") + \
                f"low/info hidden: {hidden}"
        if not subtitle:
            subtitle = "none yet"
        return Panel(table, title=f"Findings ({len(findings)})",
                     subtitle=subtitle, border_style="red")

    def _progress_panel(self) -> Panel:
        with self._lock:
            bots = {b: dict(i) for b, i in self._bots.items()}
            lines = list(self._log_lines)

        status = Table(box=None, expand=False, show_header=False, pad_edge=False)
        status.add_column("bot", width=14)
        status.add_column("state", width=9)
        status.add_column("time", width=7, justify="right")
        for bot in _BOT_ORDER:
            info = bots.get(bot, {"status": "waiting", "started": None, "elapsed": 0.0})
            running_for = (time.time() - info["started"]) if info["started"] else 0.0
            elapsed = info["elapsed"] + running_for
            st = info["status"]
            status.add_row(
                Text(f"{_BOT_ICON.get(bot, '•')} {bot}", style="bold"),
                Text(st, style=_STATUS_STYLE.get(st, "dim")),
                f"{int(elapsed)}s" if elapsed > 0 else "",
            )

        log_text = Text()
        for ts, bot, level, msg in lines[-14:]:
            m = msg
            log_text.append(f"{ts} ", style="dim")
            log_text.append(f"{bot:<11}", style="cyan")
            log_text.append(f" {m}\n")

        group = Group(
            Panel(status, title="Bots", border_style="blue", padding=(0, 1)),
            Panel(log_text, title="Activity", border_style="blue", padding=(0, 1)),
        )
        return Panel(group, title="Progress", border_style="blue")

    def _footer(self) -> Panel:
        with self._lock:
            n_findings = len(self._findings)
            tools = self._tool_execs
            decisions = self._decisions
        with self._lock:
            pending = [k for k in self._key_queue if k in ("p", "P", "q", "Q")]
        pause_note = ""
        if pending:
            pause_note = "⏸ pause requested — takes effect after current bot"
        text = Text.assemble(
            (f" findings: {n_findings}", "bold"),
            (f"   tool execs: {tools}", "bold"),
            (f"   decisions: {decisions}", "bold"),
            ("   [p] pause · [q] quit · Ctrl+C abort", "dim"),
            (f"   {pause_note}" if pause_note else "", "bold yellow"),
        )
        return Panel(text, style="dim", padding=(0, 1))


# ── module-level convenience (used by base_bot / graph) ──────────────

def log(bot: str, level: str, message: str) -> bool:
    """Route a log line to the live UI. Returns True if consumed."""
    ui = OperationUI.current()
    if ui is not None and ui.is_active():
        ui.log(bot, level, message)
        return True
    return False
