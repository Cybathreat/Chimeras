"""
Chimeras v2.0 — Bloodhound Agent

Vulnerability hunter. Identifies CVEs, misconfigs, scores them.
Scope: nmap scripts, nuclei, searchsploit, netexec, ssh-audit, sslscan, testssl

v2 Phase 4: WAF/IPS detection and aggressiveness calibration.
  - Detects WAF signs (403 rates, rate limiting, connection resets)
  - Can downgrade aggressiveness in state if target is hardened
  - Tracks failed detection attempts in failed_vectors
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class Bloodhound(BaseBot):
    """Bloodhound — Vulnerability Detection and Scoring Specialist"""

    bot_name = "bloodhound"
    role_description = "vulnerability detection and scoring specialist — CVE mapping, misconfig detection, risk scoring, WAF detection"
    scope_description = "Vulnerability identification ONLY. Scanning for known vulns, CVE mapping, scoring. NO exploitation."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    def _build_system_prompt(self) -> str:
        """Override to add WAF detection guidance and aggressiveness context."""
        base_prompt = super()._build_system_prompt()

        aggressiveness = self.state.get("aggressiveness", "cautious")

        addendum = """

## WAF/IPS Detection
While scanning for vulnerabilities, watch for signs of WAF/IPS:
- High rate of HTTP 403 Forbidden responses
- Connection resets or timeouts on specific payloads
- Rate limiting (429 Too Many Requests)
- WAF fingerprint headers (e.g., Cloudflare, Akamai, ModSecurity)
- Honeypot behavior (consistent fake responses)

If you detect WAF/IPS, include this in your structured_data:
{
  "waf_detected": true,
  "waf_type": "Cloudflare/ModSecurity/unknown",
  "evidence": "403 rate: 80%, connection resets on SQLi payloads"
}

This triggers WarChief to downgrade aggressiveness on the next cycle.
"""

        if aggressiveness == "passive_only":
            addendum += "\n## AGGRESSIVENESS: PASSIVE ONLY\nWAF detected on previous cycle. Use only passive checks (nuclei with -passive, searchsploit offline). Avoid active exploitation-style vuln checks.\n"
        elif aggressiveness == "cautious":
            addendum += "\n## AGGRESSIVENESS: CAUTIOUS\nUse standard vuln checks. If WAF signs appear, note them for WarChief to adjust.\n"

        return base_prompt + addendum

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with vuln findings.

        v2 Phase 4: WAF detection triggers aggressiveness downgrade.
        Failed detection attempts tracked in failed_vectors.
        """
        try:
            structured = analysis.get("structured_data", {})
            if not isinstance(structured, dict):
                structured = {}

            vulns = structured.get("vulnerabilities", [])
            # If structured_data.vulnerabilities is empty, try findings list
            if not vulns:
                findings = analysis.get("findings", [])
                vulns = []
                for f in findings:
                    if isinstance(f, dict):
                        vulns.append(f)
                    elif isinstance(f, str) and ("CVE" in f or "vuln" in f.lower() or "CVSS" in f):
                        vulns.append({"description": f, "cve": "N/A", "cvss": "N/A"})

            self.state["vuln_report"] = vulns
            self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision

            # ─── WAF detection → aggressiveness downgrade ───
            if structured.get("waf_detected", False):
                current_agg = self.state.get("aggressiveness", "cautious")
                waf_type = structured.get("waf_type", "unknown")
                evidence = structured.get("evidence", "")

                if current_agg == "cautious":
                    self.state["aggressiveness"] = "passive_only"
                    print(f"[BLOODHOUND] WAF detected ({waf_type}) — downgrading to passive_only")
                    self._append_log(f"WAF DETECTED: {waf_type}. Evidence: {evidence}. Aggressiveness downgraded to passive_only.")
                elif current_agg == "normal":
                    self.state["aggressiveness"] = "cautious"
                    print(f"[BLOODHOUND] WAF detected ({waf_type}) — downgrading to cautious")
                    self._append_log(f"WAF DETECTED: {waf_type}. Evidence: {evidence}. Aggressiveness downgraded to cautious.")

            # ─── Track failed detection attempts ───
            failed = self.state.get("failed_vectors", [])
            if not isinstance(failed, list):
                failed = []

            # Extract failed checks from analysis
            for key in ("failed_checks", "errors", "blocked_scans"):
                found = structured.get(key, [])
                if isinstance(found, list):
                    for item in found:
                        if isinstance(item, dict):
                            failed.append({
                                "target": item.get("target", item.get("host", "unknown")),
                                "tool": item.get("tool", self.bot_name),
                                "error": item.get("error", item.get("reason", "unknown")),
                                "timestamp": item.get("timestamp", ""),
                            })

            # Also check tool_results for failures
            for result in tool_results:
                if isinstance(result, dict) and not result.get("success", True):
                    failed.append({
                        "target": self.state.get("mission", {}).get("target", "unknown"),
                        "tool": result.get("command", "").split()[0] if result.get("command") else self.bot_name,
                        "error": result.get("stderr", "command failed")[:200],
                        "timestamp": "",
                    })

            self.state["failed_vectors"] = failed

        except Exception as e:
            print(f"[BLOODHOUND] _update_state error: {e}")
            try:
                self.state["vuln_report"] = []
                self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision
            except Exception:
                pass