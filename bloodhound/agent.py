"""
Chimeras v2.0 — Bloodhound Agent
Vulnerability hunter. Identifies CVEs, misconfigs, scores them.
Scope: nmap scripts, nuclei, searchsploit, nikto
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class Bloodhound(BaseBot):
    """Bloodhound — Vulnerability Detection and Scoring Specialist"""

    bot_name = "bloodhound"
    role_description = "vulnerability detection and scoring specialist — CVE mapping, misconfig detection, risk scoring"
    scope_description = "Vulnerability identification ONLY. Scanning for known vulns, CVE mapping, scoring. NO exploitation."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with vuln findings."""
        vulns = analysis.get("structured_data", {}).get("vulnerabilities", [])
        # If structured_data.vulnerabilities is empty, try findings list
        if not vulns:
            findings = analysis.get("findings", [])
            # Convert string findings to vuln dicts for the gate
            vulns = []
            for f in findings:
                if isinstance(f, dict):
                    vulns.append(f)
                elif isinstance(f, str) and ("CVE" in f or "vuln" in f.lower() or "CVSS" in f):
                    vulns.append({"description": f, "cve": "N/A", "cvss": "N/A"})
        self.state["vuln_report"] = vulns
        self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision