"""
Chimeras v1.0 — Surgeon Agent

Exploitation specialist. Executes exploits against human-approved targets.
HUMAN-IN-LOOP GATE: only runs if human_approval=True
Scope: msfconsole, msfvenom, sqlmap, nc, python3
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class Surgeon(BaseBot):
    """Surgeon — Exploitation Specialist. Human gate enforced."""

    bot_name = "surgeon"
    role_description = "exploitation and initial access specialist — executes exploits, establishes sessions"
    scope_description = "Exploitation ONLY. Executes approved exploits. NO privilege escalation, NO exfiltration."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    async def run(self) -> Dict[str, Any]:
        """Override to check human approval gate before doing anything."""
        if not self.state.get("human_approval", False):
            self._banner()
            self._log("HUMAN APPROVAL NOT GRANTED — exploitation blocked", "GATE")
            self._append_log("BLOCKED: Human approval not granted. Exploitation skipped.")
            self._write_bot_file(f"# SURGEON — BLOCKED\n\nHuman approval not granted. Exploitation phase skipped.\n")
            decision = {"needed": True, "strategy": "await_approval", "confidence": 1.0,
                        "reasoning": "Human approval gate not passed."}
            self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision
            return {"reasoning": decision, "executed": False, "awaiting_approval": True}

        return await super().run()

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with active sessions."""
        sessions = analysis.get("structured_data", {}).get("sessions", [])
        self.state["active_sessions"] = sessions
        self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision