"""
SwarmBots v2.0 — WarChief Agent

Supervisor/orchestrator bot. Coordinates all other bots,
reads reasoning reports, and routes the graph flow.
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class WarChief(BaseBot):
    """
    WarChief - Supervisor/Orchestrator
    
    Role: Reads all reasoning reports, decides next node,
    manages human approval gate, and triggers final report.
    """
    
    bot_name = "warchief"
    role_description = "the swarm supervisor and orchestrator"
    
    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)
        self._prompt = self._build_supervisor_prompt()
    
    def _build_supervisor_prompt(self) -> str:
        """Build WarChief's system prompt."""
        return f"""You are WarChief, the supervisor and orchestrator of the SwarmBots multi-agent system.

Your responsibilities:
1. Review all bot reasoning reports in the shared state
2. Determine which bot should execute next based on mission phase
3. Manage the human-in-loop approval gate for exploitation
4. Coordinate parallel execution when appropriate (Magician + Thief)
5. Trigger Bookkeeper for final report generation
6. Monitor abort_flag and kill all bots if emergency stop requested

Current State:
{self.state}

Think strategically. The mission success depends on your coordination."""
    
    async def reason(self) -> Dict[str, Any]:
        """
        WarChief reasoning: assess state, determine next action.
        """
        self._log("Assessing swarm state...", "REASON")
        
        reasoning_reports = self.state.get("reasoning_reports", {})
        human_approval = self.state.get("human_approval", False)
        abort_flag = self.state.get("abort_flag", False)
        
        # Check for emergency stop
        if abort_flag:
            self._log("ABORT FLAG DETECTED - Killing all bots", "CRITICAL")
            return {
                "needed": True,
                "strategy": "abort",
                "confidence": 1.0,
                "reasoning": "Emergency stop requested. Terminating all operations.",
                "recommended_actions": ["terminate_all"],
                "next_node": "END"
            }
        
        # Determine mission phase and next node
        if not reasoning_reports.get("aria"):
            next_node = "aria"
            strategy = "initiate_recon"
        elif not reasoning_reports.get("lisa"):
            next_node = "lisa"
            strategy = "initiate_scan"
        elif not reasoning_reports.get("bloodhound"):
            next_node = "bloodhound"
            strategy = "initiate_vuln_hunt"
        elif not human_approval:
            next_node = "human_approval"
            strategy = "await_exploitation_approval"
        elif not reasoning_reports.get("surgeon"):
            next_node = "surgeon"
            strategy = "initiate_exploitation"
        elif not reasoning_reports.get("magician") or not reasoning_reports.get("thief"):
            next_node = "magician_thief_parallel"
            strategy = "parallel_privesc_exfil"
        else:
            next_node = "bookkeeper_final"
            strategy = "generate_final_report"
        
        self._log(f"Next phase: {next_node}", "DECIDE")
        
        return {
            "needed": True,
            "strategy": strategy,
            "confidence": 0.95,
            "reasoning": f"Mission phase assessment complete. Next node: {next_node}",
            "recommended_actions": [strategy],
            "next_node": next_node
        }
    
    async def execute(self) -> Dict[str, Any]:
        """
        WarChief execution: route to next node, manage state.
        """
        self._log("Executing coordination...", "EXECUTE")
        
        reasoning_reports = self.state.get("reasoning_reports", {})
        next_node = reasoning_reports.get(self.bot_name, {}).get("next_node", "aria")
        
        self._append_ledger("coordination", {"next_node": next_node})
        
        return {
            "next_node": next_node,
            "bots_deployed": list(reasoning_reports.keys()),
            "mission_phase": self._determine_phase()
        }
    
    def _determine_phase(self) -> str:
        """Determine current mission phase."""
        reports = self.state.get("reasoning_reports", {})
        if "thief" in reports and "magician" in reports:
            return "exfil_complete"
        if "surgeon" in reports:
            return "exploitation"
        if "bloodhound" in reports:
            return "vuln_detection"
        if "lisa" in reports:
            return "scanning"
        if "aria" in reports:
            return "recon"
        return "init"
