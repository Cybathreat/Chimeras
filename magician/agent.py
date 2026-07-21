"""
Chimeras v2.0 — Magician Agent
Privilege escalation and lateral movement.
Scope: linpeas, find, cat, ls, ssh, smbclient, python3, bash
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class Magician(BaseBot):
    """Magician — Privilege Escalation and Lateral Movement"""

    bot_name = "magician"
    role_description = "privilege escalation and lateral movement specialist — local privesc, AD movement, credential dumping"
    scope_description = "Privilege escalation and lateral movement ONLY. NO exfiltration, NO initial exploitation."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with movement findings."""
        self.state["movement_report"] = analysis.get("structured_data", {})
        self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision