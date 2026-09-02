"""
Chimeras v3.0.2 — Tool Request Registry.

The arsenal is finite; engagement needs are not. When a bot needs a tool
outside its arsenal, it files a request instead of silently degrading.

Two sinks:
  1. Per-engagement CSV:  <engagement>/tool_requests.csv
     — the engagement's own record, consumed by Bookkeeper's report.
  2. Global registry:     <repo>/tool_requests_registry.csv
     — accumulates across ALL engagements. This is the improvement loop
       data: mine it after each engagement to decide tier image and
       TOOL_CATEGORIES updates.

CSV columns:
  date, agent, tool, description, use_case, arguments, source

source = "llm_request" (bot asked proactively)
       | "auto_not_found" (bot tried to run it, environment lacked it)
"""

import csv
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

HEADER = ["date", "agent", "tool", "description", "use_case", "arguments", "source"]

# Global registry lives at repo root (Chimeras/), next to the missions
_REPO_ROOT = Path(__file__).parent.parent
_GLOBAL_REGISTRY = _REPO_ROOT / "tool_requests_registry.csv"


def _append_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    """Thread-safe-ish CSV append with header bootstrap."""
    if not rows:
        return
    needs_header = not path.exists() or path.stat().st_size == 0
    try:
        with open(path, "a", newline="", encoding="utf-8") as f:
            # fcntl lock for cross-process safety (defense in depth with GIL)
            try:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            except (ImportError, OSError):
                pass  # non-Linux — single-process is fine

            writer = csv.DictWriter(f, fieldnames=HEADER)
            if needs_header:
                writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in HEADER})
    except Exception as e:
        logger.error(f"Tool request write failed ({path}): {e}")


def log_tool_requests(
    bot_name: str,
    requests: List[Dict[str, str]],
    engagement_dir: Optional[str] = None,
    source: str = "llm_request",
) -> int:
    """File tool requests for a bot.

    Args:
        bot_name: requesting bot (e.g. 'marksman')
        requests: list of dicts with keys: tool (required),
                  description, use_case, arguments (all optional)
        engagement_dir: engagement folder — writes
                  <engagement>/tool_requests.csv. None skips per-engagement.
        source: 'llm_request' or 'auto_not_found'

    Returns:
        number of requests actually written.
    """
    if not requests:
        return 0

    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for r in requests:
        if not isinstance(r, dict):
            continue
        tool = str(r.get("tool", "")).strip()
        if not tool:
            continue  # a request without a tool name is noise
        rows.append({
            "date": now,
            "agent": bot_name,
            "tool": tool,
            "description": str(r.get("description", ""))[:500],
            "use_case": str(r.get("use_case", ""))[:500],
            "arguments": str(r.get("arguments", ""))[:300],
            "source": source,
        })

    if not rows:
        return 0

    if engagement_dir:
        eng = Path(engagement_dir)
        try:
            eng.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Cannot create engagement dir {eng}: {e}")
        _append_csv(eng / "tool_requests.csv", rows)

    # Global registry always written (cross-engagement improvement loop)
    _append_csv(_GLOBAL_REGISTRY, rows)

    logger.info(f"[{bot_name}] {len(rows)} tool request(s) filed: "
                f"{[r['tool'] for r in rows]}")
    return len(rows)


def detect_not_found(tool_results: List[Dict[str, any]]) -> List[Dict[str, str]]:
    """Extract implicit tool requests from failed executions.

    A 'command not found' failure is a tool request the bot already made
    with its feet — record it with full context so the improvement loop
    can see WHAT the bot was trying to do when the wall was hit.
    """
    implicit = []
    for tr in tool_results or []:
        if not isinstance(tr, dict):
            continue
        if tr.get("success") is True or tr.get("exit_code") in (0, None):
            continue
        # Check both stderr and stdout — different shells report differently
        err = f"{tr.get('stderr', '')} {tr.get('stdout', '')}".lower()
        cmd = str(tr.get("command", ""))
        if "command not found" in err or "not found" in err and "/" not in cmd.split()[0]:
            # Extract the tool name: first token of the command
            tokens = cmd.split()
            tool = tokens[0] if tokens else ""
            if tool and not tool.startswith(("-", "/", "./")):
                implicit.append({
                    "tool": tool,
                    "description": f"auto-detected: '{tool}' missing from execution environment",
                    "use_case": cmd[:300],
                    "arguments": " ".join(tokens[1:6])[:300],
                })
    return implicit


def summarize_registry(path: Optional[Path] = None) -> Dict[str, Dict[str, int]]:
    """Aggregate the registry: tool → {count, last_seen}.

    The improvement loop's query function. Sorted by frequency, this tells
    you exactly which tools to add to which tier images next.
    """
    path = path or _GLOBAL_REGISTRY
    if not path.exists():
        return {}
    agg: Dict[str, Dict[str, int]] = {}
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                tool = (row.get("tool") or "").strip()
                agent = (row.get("agent") or "").strip()
                if not tool:
                    continue
                key = tool
                if key not in agg:
                    agg[key] = {"count": 0, "by_agent": {}}
                agg[key]["count"] += 1
                agg[key]["by_agent"][agent] = agg[key]["by_agent"].get(agent, 0) + 1
                if "last_date" not in agg[key] or row.get("date", "") > agg[key].get("last_date", ""):
                    agg[key]["last_date"] = row.get("date", "")
    except Exception as e:
        logger.error(f"Registry summarize failed: {e}")
    return agg