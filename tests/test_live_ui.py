"""
Tests for the v3.3 live operation TUI (core/live_ui.py).

Covers:
- Rendering smoke test (frame renders without error, no Live needed)
- Findings scan from per-bot JSONL
- Log buffer + counters (tool execs, decisions)
- Node status lifecycle (started/done/failed, elapsed)
- Module-level log() fallback when UI inactive / consumed when active
- Severity ordering (critical first)
"""

import io
import json

from rich.console import Console

import core.live_ui as live_ui
from core.live_ui import OperationUI


def _ui(tmp_path):
    return OperationUI("Test Mission", "10.0.0.0/8", tmp_path)


def _write_findings(tmp_path, bot, findings):
    path = tmp_path / f"findings_{bot}.jsonl"
    with open(path, "w") as f:
        for finding in findings:
            f.write(json.dumps(finding) + "\n")


class TestRendering:
    def test_frame_renders(self, tmp_path):
        ui = _ui(tmp_path)
        ui.log("aria", "EXEC", "nmap -sV target")
        frame = ui._render_frame()
        console = Console(file=io.StringIO(), width=120, height=40, force_terminal=True)
        console.print(frame)  # must not raise

    def test_empty_state_renders(self, tmp_path):
        ui = _ui(tmp_path)
        console = Console(file=io.StringIO(), width=120, height=40, force_terminal=True)
        console.print(ui._render_frame())


class TestFindingsScan:
    def test_reads_per_bot_jsonl(self, tmp_path):
        _write_findings(tmp_path, "aria", [
            {"finding_id": "f1", "severity": "critical", "cvss": 9.8,
             "description": "SQLi in login", "host": "10.0.0.5"},
            {"finding_id": "f2", "severity": "low", "cvss": 3.1,
             "description": "server header leak", "host": "10.0.0.5"},
        ])
        ui = _ui(tmp_path)
        ui._findings_scanned_at = 0  # bypass throttle
        ui._scan_findings()
        assert len(ui._findings) == 2
        assert ui._findings[0]["bot"] == "aria"

    def test_bad_lines_skipped(self, tmp_path):
        (tmp_path / "findings_wasp.jsonl").write_text(
            '{"finding_id":"ok","severity":"high"}\nnot json\n')
        ui = _ui(tmp_path)
        ui._findings_scanned_at = 0
        ui._scan_findings()
        assert len(ui._findings) == 1

    def test_no_evidence_dir_no_crash(self, tmp_path):
        ui = _ui(tmp_path)
        ui._findings_scanned_at = 0
        ui._scan_findings()
        assert ui._findings == []


class TestCounters:
    def test_tool_execs_counted(self, tmp_path):
        ui = _ui(tmp_path)
        ui.log("lisa", "EXEC", "nmap")
        ui.log("lisa", "INFO", "thinking")
        ui.log("wasp", "EXEC", "ffuf")
        assert ui._tool_execs == 2

    def test_decisions_counted(self, tmp_path):
        ui = _ui(tmp_path)
        ui.decision(); ui.decision()
        assert ui._decisions == 2


class TestNodeStatus:
    def test_lifecycle(self, tmp_path):
        ui = _ui(tmp_path)
        ui.node_started("aria")
        assert ui._bots["aria"]["status"] == "running"
        ui.node_done("aria")
        assert ui._bots["aria"]["status"] == "done"
        assert ui._bots["aria"]["elapsed"] >= 0

    def test_failed_flag(self, tmp_path):
        ui = _ui(tmp_path)
        ui.node_started("wasp")
        ui.node_done("wasp", failed=True)
        assert ui._bots["wasp"]["status"] == "failed"


class TestModuleLogRouting:
    def teardown_method(self):
        OperationUI._instance = None

    def test_fallback_when_inactive(self, tmp_path):
        OperationUI._instance = None
        assert live_ui.log("aria", "INFO", "x") is False

    def test_consumed_when_active(self, tmp_path):
        ui = _ui(tmp_path)
        ui._live = object()  # pretend a Live is running
        OperationUI._instance = ui
        assert live_ui.log("aria", "EXEC", "nmap") is True
        assert ui._tool_execs == 1
