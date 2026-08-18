"""
Chimeras v2.3 — Critical Findings Buffer

Critical findings (CVSS >= 7.0) are never truncated by the rolling digest.
This file is append-only and read first by Bookkeeper and WarChief.

A compliance officer that drops a critical finding is a failed compliance officer.
This buffer guarantees that never happens.

Usage:
    from core.critical_buffer import CriticalFindingsBuffer

    buf = CriticalFindingsBuffer(engagement_dir)
    buf.add(finding_text="SQL injection in /api/login (CVSS 9.8)",
            bot_name="wasp", cvss=9.8, target="example.com")
    critical = buf.read_all()  # never truncated
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict


class CriticalFindingsBuffer:
    """Append-only buffer for high-severity findings. Never truncated."""

    MIN_CVSS = 7.0

    def __init__(self, engagement_dir: Optional[Path] = None):
        self.engagement_dir = Path(engagement_dir) if engagement_dir else Path("mission/engagement")
        self._path = self.engagement_dir / "critical_findings.json"

    def add(self, finding_text: str, bot_name: str, cvss: float,
            target: str = "", tool: str = "", extra: Optional[dict] = None):
        """Add a critical finding. Only if CVSS >= MIN_CVSS."""
        try:
            if float(cvss) < self.MIN_CVSS:
                return  # not critical enough
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "bot": bot_name,
                "cvss": float(cvss),
                "target": target,
                "tool": tool,
                "finding": finding_text,
            }
            if extra:
                entry.update(extra)

            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"[CRITICAL_BUFFER] Failed to write: {e}")

    def read_all(self) -> List[Dict]:
        """Read all critical findings. Never truncated. Returns [] if none."""
        try:
            if not self._path.exists():
                return []
            entries = []
            with open(self._path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
            return entries
        except Exception as e:
            print(f"[CRITICAL_BUFFER] Failed to read: {e}")
            return []

    def format_for_context(self) -> str:
        """Format critical findings for injection into WarChief/Bookkeeper context."""
        entries = self.read_all()
        if not entries:
            return ""
        lines = ["## ⚠ CRITICAL FINDINGS (CVSS >= 7.0 — never truncated)"]
        for e in entries:
            lines.append(
                f"- [{e.get('bot','?').upper()}] CVSS {e.get('cvss','?')} "
                f"on {e.get('target','?')}: {e.get('finding','?')}"
            )
        return "\n".join(lines)