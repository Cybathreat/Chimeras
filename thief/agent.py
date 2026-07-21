"""
Chimeras v2.0 — Thief Agent
Data exfiltration specialist. Extracts data from compromised systems.
Scope: curl, wget, nc, python3, tar, gzip, scp
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class Thief(BaseBot):
    """Thief — Data Exfiltration Specialist"""

    bot_name = "thief"
    role_description = "data exfiltration and covert transfer specialist — identifies valuable data, stages and transfers covertly"
    scope_description = "Data exfiltration ONLY. Identifies and extracts valuable data. NO exploitation, NO privilege escalation."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with exfil findings."""
        self.state["exfil_report"] = analysis.get("structured_data", {})
        self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision