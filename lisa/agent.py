"""
Chimeras v2.0 — Lisa Agent

Active scanning bot. Port scanning, service enum, OS detection.
Scope: nmap, masscan, naabu, whatweb, gobuster, ffuf, wpscan, sslscan, testssl, enum4linux-ng

v2 Phase 3: Lateral scan context.
  - When target_context is "lateral", Lisa scans internal targets
  - Tracks internal_targets discovered during scanning
  - Honors aggressiveness level (cautious = slower scans)
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class Lisa(BaseBot):
    """Lisa — Network Scanning Specialist"""

    bot_name = "lisa"
    role_description = "network scanning and enumeration specialist — port scanning, service detection, OS fingerprinting, internal network scanning"
    scope_description = "Active scanning ONLY. Port scanning, service enumeration, OS detection. NO exploitation, NO exfiltration."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    def _build_system_prompt(self) -> str:
        """Override to add lateral scan context when in lateral mode."""
        base_prompt = super()._build_system_prompt()

        target_context = self.state.get("target_context", "external")
        aggressiveness = self.state.get("aggressiveness", "cautious")

        addendum = ""

        if target_context == "lateral":
            addendum += """

## LATERAL SCAN MODE
You are scanning newly-discovered INTERNAL targets. These are hosts found
during lateral movement after gaining initial access to the external target.

Scan objectives:
- Identify open ports and services on internal hosts
- Look for high-value services: SQL Server (1433), SMB (445), RDP (3389),
  LDAP (389/636), WinRM (5985/5986), SSH (22)
- Detect Domain Controllers (port 88 Kerberos, 389 LDAP, 464 Kerberos pwd)
- Find file shares and database servers
- Flag any service that could yield credentials or further access

All targets are within the approved lateral scope. The lateral_approval
gate has been passed. Commands are scope-enforced at the code level.
"""

        # Aggressiveness affects scan behavior
        if aggressiveness == "passive_only":
            addendum += "\n\n## AGGRESSIVENESS: PASSIVE ONLY\nTarget is hardened or WAF detected. Use slow scan timing (-T2 or -T1). Avoid aggressive service detection. Use nmap -sS -T2 --max-retries 1.\n"
        elif aggressiveness == "cautious":
            addendum += "\n\n## AGGRESSIVENESS: CAUTIOUS\nUse normal scan timing (-T3). If target shows WAF/IPS signs (many 403s, connection resets), slow down to -T2.\n"

        if addendum:
            return base_prompt + addendum
        return base_prompt

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with scan findings.

        v2 Phase 3: Tracks internal_targets during lateral scanning.
        """
        try:
            self.state["scan_report"] = analysis.get("structured_data", {})
            self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision

            # Track discovered hosts from scan results
            structured = analysis.get("structured_data", {})
            if not isinstance(structured, dict):
                structured = {}

            new_hosts = []
            for key in ("hosts", "open_hosts", "scanned_hosts", "targets"):
                found = structured.get(key, [])
                if isinstance(found, list):
                    for h in found:
                        if isinstance(h, str) and h:
                            new_hosts.append(h)
                        elif isinstance(h, dict):
                            for field in ("host", "ip", "hostname", "target", "address"):
                                val = h.get(field)
                                if val and isinstance(val, str):
                                    new_hosts.append(val)
                                    break

            # Update discovered_targets
            discovered = self.state.get("discovered_targets", [])
            if not isinstance(discovered, list):
                discovered = []
            for h in new_hosts:
                if h not in discovered:
                    discovered.append(h)
            self.state["discovered_targets"] = discovered

            # Update internal_targets if in lateral context
            target_context = self.state.get("target_context", "external")
            if target_context == "lateral":
                internal = self.state.get("internal_targets", [])
                if not isinstance(internal, list):
                    internal = []
                for h in new_hosts:
                    if h not in internal:
                        internal.append(h)
                self.state["internal_targets"] = internal

        except Exception as e:
            print(f"[LISA] _update_state error: {e}")
            try:
                self.state["scan_report"] = analysis.get("structured_data", {})
                self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision
            except Exception:
                pass