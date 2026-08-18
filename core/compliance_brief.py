"""
Chimeras v2.3 — Structured Compliance Brief

Replaces raw context dumps for WarChief with a fixed-schema intake.
200 tokens instead of 2000. The LLM answers specific compliance questions
instead of free-form "review the engagement."

The compliance brief is a structured summary built from engagement state:
- scope_changes: targets added/removed since last checkpoint
- new_targets: newly discovered hosts
- roe_flags: RoE violations or concerns
- findings_summary: high-level summary of findings
- phase_result: what the last bot did and found

This is NOT a deterministic filter. The LLM still makes all compliance
decisions. This just gives it pre-digested data instead of raw markdown.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional


class ComplianceBrief:
    """Build a structured compliance brief for WarChief."""

    def __init__(self, state: Dict[str, Any]):
        self.state = state

    def build(self, last_bot: str = "") -> str:
        """Build the compliance brief as a structured prompt section.

        Args:
            last_bot: Name of the bot that just completed (for phase_result).

        Returns:
            Structured brief string for injection into WarChief's prompt.
        """
        brief = {
            "engagement_phase": self.state.get("mission_state", "init"),
            "target_context": self.state.get("target_context", "external"),
            "scope": self._scope_info(),
            "scope_changes": self._scope_changes(),
            "new_targets": self._new_targets(),
            "roe_flags": self._roe_flags(),
            "findings_summary": self._findings_summary(),
            "phase_result": self._phase_result(last_bot),
            "critical_findings": self._critical_findings(),
            "decision_history": self._decision_history(),
            "loop_count": self.state.get("loop_count", {}),
            "aggressiveness": self.state.get("aggressiveness", "cautious"),
            "failed_vectors": self._failed_vectors(),
        }

        lines = ["## Structured Compliance Brief", ""]
        for key, value in brief.items():
            if value is None or value == "" or value == [] or value == {}:
                continue
            if isinstance(value, (list, dict)):
                lines.append(f"**{key}**:")
                lines.append(f"```json\n{json.dumps(value, indent=2, default=str)}\n```")
            else:
                lines.append(f"**{key}**: {value}")
            lines.append("")

        return "\n".join(lines)

    def _scope_info(self) -> Dict[str, Any]:
        mission = self.state.get("mission", {})
        approved = self.state.get("approved_extra_targets", [])
        return {
            "mission_scope": mission.get("scope", "N/A"),
            "approved_extra_targets": approved,
            "internal_scope": self.state.get("internal_scope", ""),
            "roe": mission.get("roe", "N/A"),
        }

    def _scope_changes(self) -> List[Dict[str, Any]]:
        """Targets added/removed since last checkpoint."""
        candidates = self.state.get("scope_expansion_candidates", [])
        if not candidates:
            return []
        return [
            {"target": c.get("target"), "found_by": c.get("found_by"),
             "reason": c.get("reason", "")[:100]}
            for c in candidates[-5:]  # last 5 only
        ]

    def _new_targets(self) -> List[str]:
        """Newly discovered hosts beyond initial scope."""
        discovered = self.state.get("discovered_targets", [])
        external = self.state.get("external_targets", [])
        if not discovered:
            return []
        new = [t for t in discovered if t not in (external or [])]
        return new[-10:]  # last 10

    def _roe_flags(self) -> List[str]:
        """RoE violations or concerns from this engagement."""
        flags = []
        # Check for destructive command attempts
        mission_roe = self.state.get("mission", {}).get("roe", "").lower()
        if "no dos" in mission_roe or "no dos" in mission_roe:
            # Check if any bots hit DoS blocks
            failed = self.state.get("failed_vectors", [])
            for f in failed[-3:]:
                if "dos" in str(f.get("error", "")).lower():
                    flags.append(f"DoS attempt blocked on {f.get('target','?')}")
        return flags

    def _findings_summary(self) -> Optional[str]:
        """High-level findings summary — last 500 chars only."""
        # Try to read findings from state, not file (avoids re-reading)
        reasoning = self.state.get("reasoning_reports", {})
        summaries = []
        for bot, report in reasoning.items():
            if isinstance(report, dict):
                summary = report.get("summary", "") or report.get("assessment", "")
                if summary:
                    summaries.append(f"[{bot}] {summary[:150]}")
        return "\n".join(summaries[-5:]) if summaries else None

    def _phase_result(self, last_bot: str) -> Optional[Dict[str, Any]]:
        """What the last bot did and found."""
        if not last_bot:
            return None
        report = self.state.get("reasoning_reports", {}).get(last_bot, {})
        if not report or not isinstance(report, dict):
            return None
        return {
            "bot": last_bot,
            "strategy": report.get("strategy", "N/A"),
            "confidence": report.get("confidence", 0.5),
            "reasoning": (report.get("reasoning", "") or "")[:200],
            "executed": report.get("executed", False),
        }

    def _critical_findings(self) -> List[str]:
        """Critical findings from state (CVSS >= 7.0)."""
        # This reads from the critical_findings.json buffer if available
        # But for the brief, we check state for vuln_report entries
        vulns = self.state.get("vuln_report", [])
        if not vulns:
            return []
        critical = []
        for v in vulns:
            if isinstance(v, dict):
                cvss = v.get("cvss", 0)
                try:
                    cvss = float(cvss)
                except (ValueError, TypeError):
                    cvss = 0
                if cvss >= 7.0:
                    critical.append(
                        f"CVSS {cvss} on {v.get('target','?')}: {v.get('title', v.get('description',''))[:100]}"
                    )
        return critical

    def _decision_history(self) -> List[Dict[str, Any]]:
        """Last 3 decisions for trend awareness."""
        history = self.state.get("decision_history", [])
        if not history:
            return []
        return [
            {"decision": h.get("decision"), "phase": h.get("phase"),
             "confidence": h.get("confidence")}
            for h in history[-3:]
        ]

    def _failed_vectors(self) -> List[str]:
        """Recent failed attack vectors."""
        failed = self.state.get("failed_vectors", [])
        if not failed:
            return []
        return [
            f"{f.get('target','?')}: {f.get('tool','?')} — {str(f.get('error',''))[:80]}"
            for f in failed[-3:]
        ]