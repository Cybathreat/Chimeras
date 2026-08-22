"""
Chimeras v2.4 — Telemetry Logger

JSONL telemetry for every LLM call and tool execution.
Logs: timestamp, bot_name, phase, action, duration_sec, token_count,
       llm_calls, success, error, provider, model, cache_hits.

v2.4 expansion: per-provider LLM latency, tool execution time,
cache hit rate, parse failure rate. Three critical metrics:
1. LLM call latency per provider
2. Tool execution time
3. Digest loss rate (findings truncated vs total)

Output: engagement/telemetry.jsonl

Usage:
    from core.telemetry import Telemetry

    tel = Telemetry(engagement_dir)
    with tel.track("warchief", "compliance_check", "init"):
        result = warchief.run()

    # v2.4: Direct LLM call recording
    tel.record_llm_call(bot_name="bloodhound", provider="ollama-cloud",
                        model="deepseek-v4-pro", duration_sec=12.5,
                        tokens_in=1500, tokens_out=800, parse_ok=True)
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from collections import defaultdict


class Telemetry:
    """JSONL telemetry logger. One line per event. v2.4: expanded metrics."""

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

    def record_llm_call(self, bot_name: str, provider: str, model: str,
                        duration_sec: float, tokens_in: int = 0,
                        tokens_out: int = 0, parse_ok: bool = True,
                        cache_hit: bool = False, error: str = ""):
        """v2.4: Record an LLM call with provider/model-specific metrics."""
        if not self.enabled:
            return
        try:
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "bot": bot_name,
                "action": "llm_call",
                "phase": "",
                "duration_sec": round(duration_sec, 3),
                "success": parse_ok,
                "provider": provider,
                "model": model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "parse_ok": parse_ok,
                "cache_hit": cache_hit,
            }
            if error:
                entry["error"] = error[:300]

            self._log_path().parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path(), "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"[TELEMETRY] Failed to write LLM call: {e}")

    def record_tool_exec(self, bot_name: str, tool_name: str, target: str,
                         duration_sec: float, exit_code: int = 0,
                         cached: bool = False, scope_blocked: bool = False):
        """v2.4: Record a tool execution with structured metrics."""
        if not self.enabled:
            return
        try:
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "bot": bot_name,
                "action": "tool_exec",
                "phase": "",
                "duration_sec": round(duration_sec, 3),
                "success": exit_code == 0 and not scope_blocked,
                "tool": tool_name,
                "target": target,
                "exit_code": exit_code,
                "cached": cached,
                "scope_blocked": scope_blocked,
            }

            self._log_path().parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path(), "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"[TELEMETRY] Failed to write tool exec: {e}")

    def summary(self) -> Dict[str, Any]:
        """v2.4: Generate a summary of all telemetry events.
        Used for baseline comparison and efficiency measurement.
        """
        events = self.read_all()
        if not events:
            return {"total_events": 0}

        llm_calls = [e for e in events if e.get("action") == "llm_call"]
        tool_execs = [e for e in events if e.get("action") == "tool_exec"]

        # Per-provider latency
        provider_latencies = defaultdict(list)
        for e in llm_calls:
            provider = e.get("provider", "unknown")
            if e.get("duration_sec"):
                provider_latencies[provider].append(e["duration_sec"])

        provider_stats = {}
        for provider, latencies in provider_latencies.items():
            provider_stats[provider] = {
                "calls": len(latencies),
                "avg_latency": round(sum(latencies) / len(latencies), 3) if latencies else 0,
                "max_latency": round(max(latencies), 3) if latencies else 0,
            }

        # Cache hit rate
        tool_count = len(tool_execs)
        cache_hits = sum(1 for e in tool_execs if e.get("cached", False))
        cache_hit_rate = round(cache_hits / tool_count, 3) if tool_count > 0 else 0

        # Parse failure rate
        llm_count = len(llm_calls)
        parse_failures = sum(1 for e in llm_calls if not e.get("parse_ok", True))
        parse_failure_rate = round(parse_failures / llm_count, 3) if llm_count > 0 else 0

        return {
            "total_events": len(events),
            "llm_calls": llm_count,
            "tool_executions": tool_count,
            "cache_hits": cache_hits,
            "cache_hit_rate": cache_hit_rate,
            "parse_failures": parse_failures,
            "parse_failure_rate": parse_failure_rate,
            "provider_stats": provider_stats,
            "total_tokens_in": sum(e.get("tokens_in", 0) for e in llm_calls),
            "total_tokens_out": sum(e.get("tokens_out", 0) for e in llm_calls),
        }

    def read_all(self) -> List[Dict[str, Any]]:
        """Read all telemetry events."""
        path = self._log_path()
        if not path.exists():
            return []
        events = []
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except Exception:
            pass
        return events

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