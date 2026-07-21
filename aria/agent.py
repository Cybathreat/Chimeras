"""
Chimeras v2.0 — ARIA Agent
Passive reconnaissance bot. OSINT only. NO active scanning.
Scope: dig, host, whois, curl, whatweb
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class ARIA(BaseBot):
    """ARIA — Passive Reconnaissance Specialist"""

    bot_name = "aria"
    role_description = "passive reconnaissance specialist — OSINT, DNS, subdomains, tech stack"
    scope_description = "Passive reconnaissance ONLY. No active scanning, no exploitation. DNS lookups, WHOIS, certificate transparency, web fingerprinting."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with recon findings."""
        self.state["recon_report"] = analysis.get("structured_data", {})
        self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision