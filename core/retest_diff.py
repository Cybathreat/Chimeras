"""
Chimeras v3.2 — Retest Diff Engine

Compares findings from engagement N against engagement N-1 to identify
regressions (NEW) and fixes (FIXED). Extends RetestVerifier with
cross-engagement diffing.

Usage:
    from core.retest_diff import RetestDiffer

    differ = RetestDiffer()
    report = differ.diff(prev_findings, curr_findings)
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

STATUS_NEW = "NEW"           # Finding exists in current but not previous (regression)
STATUS_FIXED = "FIXED"       # Finding existed in previous but not current (remediated)
STATUS_PERSISTENT = "PERSISTENT"  # Finding in both (still open)
STATUS_CHANGED = "CHANGED"   # Finding in both but severity/status changed


class RetestDiffer:
    """Diff two sets of findings across engagements.

    Matches findings by title (normalized) and target host.
    Reports NEW (regressions), FIXED (wins), PERSISTENT (still open),
    and CHANGED (severity/status modified).
    """

    def _fingerprint(self, finding: Dict[str, Any]) -> str:
        """Create a fingerprint for matching findings across engagements."""
        title = (finding.get("title") or finding.get("finding_id") or "").strip().lower()
        host = (finding.get("host") or finding.get("target") or "").strip().lower()
        return f"{title}|{host}"

    def diff(
        self,
        previous: List[Dict[str, Any]],
        current: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Diff two finding sets.

        Args:
            previous: Findings from engagement N-1.
            current: Findings from engagement N.

        Returns:
            Dict with categorized findings and summary stats.
        """
        prev_map = {}
        for f in previous:
            fp = self._fingerprint(f)
            prev_map[fp] = f

        curr_map = {}
        for f in current:
            fp = self._fingerprint(f)
            curr_map[fp] = f

        new_findings: List[Dict[str, Any]] = []
        fixed_findings: List[Dict[str, Any]] = []
        persistent: List[Dict[str, Any]] = []
        changed: List[Dict[str, Any]] = []

        # Find NEW and CHANGED
        for fp, curr_f in curr_map.items():
            if fp not in prev_map:
                curr_f_copy = dict(curr_f)
                curr_f_copy["diff_status"] = STATUS_NEW
                new_findings.append(curr_f_copy)
            else:
                prev_f = prev_map[fp]
                prev_sev = (prev_f.get("severity") or "").lower()
                curr_sev = (curr_f.get("severity") or "").lower()
                prev_status = (prev_f.get("status") or "").lower()
                curr_status = (curr_f.get("status") or "").lower()

                if prev_sev != curr_sev or prev_status != curr_status:
                    curr_f_copy = dict(curr_f)
                    curr_f_copy["diff_status"] = STATUS_CHANGED
                    curr_f_copy["previous_severity"] = prev_sev
                    curr_f_copy["previous_status"] = prev_status
                    changed.append(curr_f_copy)
                else:
                    curr_f_copy = dict(curr_f)
                    curr_f_copy["diff_status"] = STATUS_PERSISTENT
                    persistent.append(curr_f_copy)

        # Find FIXED
        for fp, prev_f in prev_map.items():
            if fp not in curr_map:
                prev_f_copy = dict(prev_f)
                prev_f_copy["diff_status"] = STATUS_FIXED
                fixed_findings.append(prev_f_copy)

        total_prev = len(previous)
        total_curr = len(current)
        fixed_count = len(fixed_findings)
        new_count = len(new_findings)

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "previous_count": total_prev,
            "current_count": total_curr,
            "new_findings": new_findings,
            "fixed_findings": fixed_findings,
            "persistent_findings": persistent,
            "changed_findings": changed,
            "summary": {
                "new": new_count,
                "fixed": fixed_count,
                "persistent": len(persistent),
                "changed": len(changed),
                "remediation_rate": round(fixed_count / total_prev * 100, 1) if total_prev > 0 else 0,
                "regression_count": new_count,
            },
        }

    def format_diff_report(self, diff_result: Dict[str, Any]) -> str:
        """Format diff results as markdown report."""
        s = diff_result["summary"]
        lines = [
            "# Retest Diff Report",
            "",
            f"**Generated:** {diff_result['generated_at']}",
            f"**Previous findings:** {diff_result['previous_count']}",
            f"**Current findings:** {diff_result['current_count']}",
            "",
            "---",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| New findings (regressions) | {s['new']} |",
            f"| Fixed findings (remediated) | {s['fixed']} |",
            f"| Persistent findings | {s['persistent']} |",
            f"| Changed findings | {s['changed']} |",
            f"| Remediation rate | {s['remediation_rate']}% |",
            "",
        ]

        if diff_result["new_findings"]:
            lines.append("## 🔴 New Findings (Regressions)")
            lines.append("")
            for f in diff_result["new_findings"]:
                fid = f.get("id") or f.get("finding_id", "NEW")
                lines.append(f"### {fid}: {f.get('title', 'Untitled')}")
                lines.append(f"**Severity:** {f.get('severity', 'N/A')} | **CVSS:** {f.get('cvss', 'N/A')}")
                lines.append(f"**Description:** {f.get('description', 'N/A')}")
                lines.append("")

        if diff_result["fixed_findings"]:
            lines.append("## ✅ Fixed Findings (Remediated)")
            lines.append("")
            for f in diff_result["fixed_findings"]:
                fid = f.get("id") or f.get("finding_id", "FIXED")
                lines.append(f"- ~~{fid}: {f.get('title', 'Untitled')}~~ — {f.get('severity', 'N/A')}")
            lines.append("")

        if diff_result["persistent_findings"]:
            lines.append("## ⚠ Persistent Findings (Still Open)")
            lines.append("")
            for f in diff_result["persistent_findings"]:
                fid = f.get("id") or f.get("finding_id", "PERSIST")
                lines.append(f"- **{fid}**: {f.get('title', 'Untitled')} ({f.get('severity', 'N/A')})")
            lines.append("")

        if diff_result["changed_findings"]:
            lines.append("## 🔄 Changed Findings")
            lines.append("")
            for f in diff_result["changed_findings"]:
                fid = f.get("id") or f.get("finding_id", "CHANGED")
                lines.append(f"### {fid}: {f.get('title', 'Untitled')}")
                lines.append(f"**Previous:** {f.get('previous_severity', 'N/A')} / {f.get('previous_status', 'N/A')}")
                lines.append(f"**Current:** {f.get('severity', 'N/A')} / {f.get('status', 'N/A')}")
                lines.append("")

        lines.append("---")
        lines.append("*Retest diff report generated by Chimeras v3.2 — Cyberian Defenses*")

        return "\n".join(lines)