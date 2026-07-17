"""
Chimeras v1.0 — Lisa Agent

Active scanning bot. Port scanning, service enum, OS detection.
Scope: nmap, masscan, nikto, whatweb, gobuster, wpscan
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class Lisa(BaseBot):
    """Lisa — Network Scanning Specialist"""

    bot_name = "lisa"
    role_description = "network scanning and enumeration specialist — port scanning, service detection, OS fingerprinting"
    scope_description = "Active scanning ONLY. Port scanning, service enumeration, OS detection. NO exploitation, NO exfiltration."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with scan findings."""
        self.state["scan_report"] = analysis.get("structured_data", {})
        self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision