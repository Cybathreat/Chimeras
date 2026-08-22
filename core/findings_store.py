"""
Chimeras v2.4 — Lossless Findings Store

Findings are NEVER truncated. Truncate logs, not evidence.

Per-bot JSONL files: engagement/findings_{bot_name}.jsonl
Merged by Bookkeeper at report time.

Replaces the old markdown findings.md approach where findings
were truncated by the rolling digest and lost between cycles.

Usage:
    from core.findings_store import FindingsStore

    store = FindingsStore(engagement_dir)
    store.add("bloodhound", {
        "finding_id": "BH-001",
        "title": "OpenSSH 9.2 — CVE-2024-6387",
        "severity": "Critical",
        "cvss": 9.8,
        ...
    })
    all = store.get_all()  # all findings from all bots
    bot_findings = store.get_bot_findings("bloodhound")
"""

import json
import fcntl
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


class FindingsStore:
    """Per-bot JSONL findings store. Lossless. File-locked writes.

    Each bot writes to findings_{bot_name}.jsonl — no shared writes.
    Bookkeeper merges all files at report time.
    """

    def __init__(self, engagement_dir: Optional[Path] = None):
        self.engagement_dir = Path(engagement_dir) if engagement_dir else Path("mission/engagement")
        self.engagement_dir.mkdir(parents=True, exist_ok=True)

    def _bot_path(self, bot_name: str) -> Path:
        """Get the JSONL file path for a specific bot."""
        return self.engagement_dir / f"findings_{bot_name}.jsonl"

    def _merged_path(self) -> Path:
        """Path for the merged findings file (written by Bookkeeper)."""
        return self.engagement_dir / "findings.jsonl"

    def add(self, bot_name: str, finding: Dict[str, Any]) -> str:
        """Add a finding to the bot's JSONL file. Returns finding_id.

        The finding dict should follow the Finding schema from core.schemas.
        If finding_id is missing, one is generated.
        """
        # Ensure finding_id exists
        if "finding_id" not in finding or not finding["finding_id"]:
            # Generate based on bot name and count
            existing = self.get_bot_findings(bot_name)
            count = len(existing) + 1
            finding["finding_id"] = f"{bot_name.upper()[:3]}-{count:03d}"

        # Add metadata
        finding["source_bot"] = bot_name
        finding["timestamp"] = finding.get("timestamp", datetime.utcnow().isoformat())

        # File-locked append
        path = self._bot_path(bot_name)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, "a") as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                except (OSError, ImportError):
                    pass  # fcntl not available on all platforms
                f.write(json.dumps(finding) + "\n")
        except Exception as e:
            print(f"[FINDINGS_STORE] Failed to write finding for {bot_name}: {e}")

        return finding["finding_id"]

    def get_bot_findings(self, bot_name: str) -> List[Dict[str, Any]]:
        """Read all findings from a specific bot's JSONL file."""
        path = self._bot_path(bot_name)
        if not path.exists():
            return []
        findings = []
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            findings.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass  # skip malformed entries
        except Exception as e:
            print(f"[FINDINGS_STORE] Failed to read {bot_name} findings: {e}")
        return findings

    def get_all(self) -> List[Dict[str, Any]]:
        """Read all findings from all bots. Merges all JSONL files."""
        all_findings = []
        for path in self.engagement_dir.glob("findings_*.jsonl"):
            if path.name == "findings.jsonl":
                continue  # skip merged file
            bot_name = path.stem.replace("findings_", "")
            findings = self.get_bot_findings(bot_name)
            all_findings.extend(findings)
        return all_findings

    def get_critical(self, min_cvss: float = 7.0) -> List[Dict[str, Any]]:
        """Get all findings with CVSS >= min_cvss."""
        all_findings = self.get_all()
        return [f for f in all_findings if self._get_cvss(f) >= min_cvss]

    def _get_cvss(self, finding: Dict[str, Any]) -> float:
        """Extract CVSS score from finding, handling missing/invalid values."""
        cvss = finding.get("cvss")
        if cvss is None:
            return 0.0
        try:
            return float(cvss)
        except (ValueError, TypeError):
            return 0.0

    def merge_all(self) -> Path:
        """Merge all per-bot findings into a single findings.jsonl file.
        Called by Bookkeeper at report time.

        Returns path to merged file.
        """
        all_findings = self.get_all()
        merged_path = self._merged_path()

        try:
            with open(merged_path, "w") as f:
                for finding in all_findings:
                    f.write(json.dumps(finding) + "\n")
        except Exception as e:
            print(f"[FINDINGS_STORE] Failed to merge findings: {e}")

        return merged_path

    def format_for_report(self) -> List[Dict[str, Any]]:
        """Format all findings for the report template.
        Ensures each finding has all required fields populated.
        """
        all_findings = self.get_all()
        formatted = []
        for f in all_findings:
            entry = {
                "id": f.get("finding_id", "UNKNOWN"),
                "title": f.get("title", "Untitled Finding"),
                "severity": f.get("severity", "Info"),
                "cvss": f.get("cvss", "N/A"),
                "status": f.get("status", "Confirmed"),
                "description": f.get("description", "N/A"),
                "risks": f.get("risks", "N/A"),
                "attack_vectors": f.get("attack_vectors", "N/A"),
                "poc": f.get("poc", "N/A"),
                "proof_of_existence": f.get("proof_of_existence", "N/A"),
                "remediation": f.get("remediation", "N/A"),
            }
            formatted.append(entry)
        return formatted

    def format_critical_for_report(self) -> List[Dict[str, Any]]:
        """Format critical findings (CVSS >= 7.0) for the report template."""
        critical = self.get_critical()
        formatted = []
        for f in critical:
            formatted.append({
                "bot": f.get("source_bot", "?"),
                "cvss": f.get("cvss", "N/A"),
                "target": f.get("host", "N/A"),
                "finding": f.get("title", "N/A"),
            })
        return formatted

    def deduplicate(self) -> int:
        """Remove duplicate findings (same finding_id). Returns count removed."""
        all_findings = self.get_all()
        seen_ids = set()
        unique = []
        duplicates = 0
        for f in all_findings:
            fid = f.get("finding_id", "")
            if fid and fid in seen_ids:
                duplicates += 1
            else:
                seen_ids.add(fid)
                unique.append(f)

        if duplicates > 0:
            # Rewrite all per-bot files with deduplicated data
            by_bot = {}
            for f in unique:
                bot = f.get("source_bot", "unknown")
                if bot not in by_bot:
                    by_bot[bot] = []
                by_bot[bot].append(f)

            for bot, findings in by_bot.items():
                path = self._bot_path(bot)
                try:
                    with open(path, "w") as fp:
                        for finding in findings:
                            fp.write(json.dumps(finding) + "\n")
                except Exception as e:
                    print(f"[FINDINGS_STORE] Failed to rewrite {bot} findings: {e}")

        return duplicates