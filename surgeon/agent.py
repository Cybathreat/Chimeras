"""
SwarmBots v2.0 — Surgeon Agent

Exploitation specialist. Executes exploits against approved targets,
establishes initial foothold, and creates active sessions.
"""

from typing import Dict, Any, Optional, List
from core.base_bot import BaseBot
from core.state import SwarmState


class Surgeon(BaseBot):
    """
    Surgeon - Exploitation Specialist
    
    Role: Executes exploits against human-approved targets,
    establishes shells, creates active sessions.
    
    HUMAN-IN-LOOP GATE: This bot ONLY executes if human_approval=True
    """
    
    bot_name = "surgeon"
    role_description = "exploitation and initial access specialist"
    
    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)
        self._prompt = self._build_exploit_prompt()
    
    def _build_exploit_prompt(self) -> str:
        """Build Surgeon's system prompt."""
        return f"""You are Surgeon, the exploitation specialist for SwarmBots.

Your mission:
1. Review Bloodhound's vulnerability report
2. Select highest-priority, exploitable targets
3. Choose appropriate exploit for each target
4. Execute exploit ONLY after human approval
5. Establish initial shell/access
6. Report active session details

Current Mission:
{self.state.get('mission', {})}

Vulnerability Report:
{self.state.get('vuln_report', [])}

Human Approval Status: {self.state.get('human_approval', False)}

CRITICAL: You DO NOT exploit without human_approval=True.
This is a hard gate. No bypass. No exceptions."""
    
    async def reason(self) -> Dict[str, Any]:
        """
        Surgeon reasoning: assess vulns, select exploits, check approval.
        """
        self._log("Analyzing exploitation opportunities...", "REASON")
        
        vuln_report = self.state.get("vuln_report", [])
        human_approval = self.state.get("human_approval", False)
        
        if not vuln_report:
            self._log("No vulnerabilities - exploitation not possible", "DECIDE")
            return {
                "needed": False,
                "strategy": "skip",
                "confidence": 1.0,
                "reasoning": "No vulnerabilities identified by Bloodhound. Exploitation cannot proceed.",
                "recommended_actions": []
            }
        
        if not human_approval:
            self._log("Human approval NOT granted - exploitation BLOCKED", "CRITICAL")
            return {
                "needed": True,
                "strategy": "await_approval",
                "confidence": 1.0,
                "reasoning": "Exploitation targets identified but human approval gate is NOT passed. Waiting.",
                "recommended_actions": ["wait_for_human_approval"],
                "blocked": True
            }
        
        # Select best exploit targets
        high_priority = [v for v in vuln_report if v.get("cvss", 0) >= 7.0]
        strategy = "surgical_exploitation"
        
        self._log(f"Exploit strategy: {strategy} - {len(high_priority)} high-priority targets", "DECIDE")
        
        return {
            "needed": True,
            "strategy": strategy,
            "confidence": 0.85,
            "reasoning": f"Human approval granted. {len(high_priority)} high-priority targets selected for exploitation.",
            "recommended_actions": [
                "exploit_selection",
                "payload_delivery",
                "session_establishment",
                "privilege_check"
            ],
            "targets": high_priority
        }
    
    async def execute(self) -> Dict[str, Any]:
        """
        Surgeon execution: run exploits, establish sessions.
        """
        self._log("Executing exploitation...", "EXECUTE")
        
        vuln_report = self.state.get("vuln_report", [])
        high_priority = [v for v in vuln_report if v.get("cvss", 0) >= 7.0]
        
        # Simulated exploitation results (in production, these would call real tools)
        active_sessions: List[Dict[str, Any]] = []
        
        for vuln in high_priority:
            session = {
                "session_id": f"sess_{vuln.get('host')}_{vuln.get('port')}",
                "target": vuln.get("host"),
                "port": vuln.get("port"),
                "exploit_used": "mock_exploit",
                "shell_type": "reverse_tcp",
                "user": "www-data",
                "timestamp": "2026-03-23T09:00:00Z",
                "success": True
            }
            active_sessions.append(session)
        
        # In production, integrate with:
        # - Metasploit Framework (exploit/multi/handler, exploit/*)
        # - manual exploits (Python, Bash)
        # - payload listeners (nc, pwncat)
        # - session management (meterpreter, shells)
        
        self._append_ledger("exploitation_complete", {"sessions": len(active_sessions)})
        
        # Update state
        self.state["active_sessions"] = active_sessions
        
        return {
            "sessions_established": active_sessions,
            "total_exploits": len(active_sessions),
            "success_rate": 1.0
        }
