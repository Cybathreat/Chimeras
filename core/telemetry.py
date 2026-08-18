"""
Chimeras v2.3 — Telemetry Logger

JSONL telemetry for every LLM call and tool execution.
Logs: timestamp, bot_name, phase, action, duration_sec, token_count,
       llm_calls, success, error.

Output: engagement/telemetry.jsonl

Usage:
    from core.telemetry import Telemetry

    tel = Telemetry(engagement_dir)
    with tel.track("warchief", "compliance_check", "init"):
        result = warchief.run()
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


class Telemetry:
    """Minimal JSONL telemetry logger. One line per event."""

    def __init__(self, engagement_dir: Optional[Path] = None):
        self.engagement_dir = Path(engagement_dir) if engagement_dir else Path("mission/engagement")
        self.enabled = True

    def _log_path(self) -> Path:
        return self.engagement_dir / "telemetry.jsonl"

    def record(self, bot_name: str, action: str, phase: str,
               duration_sec: float, success: bool = True,
               token_count: int = 0, error: str = "",
               extra: Optional[dict] = None):
        """Write a single telemetry event."""
        if not self.enabled:
            return
        try:
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "bot": bot_name,
                "action": action,
                "phase": phase,
                "duration_sec": round(duration_sec, 3),
                "success": success,
                "token_count": token_count,
            }
            if error:
                entry["error"] = error[:300]
            if extra:
                entry.update(extra)

            self._log_path().parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path(), "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            # Telemetry must never crash the engagement
            print(f"[TELEMETRY] Failed to write: {e}")

    def track(self, bot_name: str, action: str, phase: str):
        """Context manager for timing a block of work."""
        return _TelemetryTracker(self, bot_name, action, phase)


class _TelemetryTracker:
    def __init__(self, telemetry: Telemetry, bot_name: str, action: str, phase: str):
        self.telemetry = telemetry
        self.bot_name = bot_name
        self.action = action
        self.phase = phase
        self.start = 0.0
        self.token_count = 0

    def __enter__(self):
        self.start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.monotonic() - self.start
        success = exc_type is None
        error = str(exc_val) if exc_val else ""
        self.telemetry.record(
            self.bot_name, self.action, self.phase,
            duration, success=success, token_count=self.token_count,
            error=error,
        )
        return False  # don't suppress exceptions