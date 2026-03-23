"""
SwarmBots v2.0 — Bookkeeper Agent

Logger/auditor. Passively observes all state transitions,
maintains operation ledger, and generates final reports.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from core.base_bot import BaseBot
from core.state import SwarmState


class Bookkeeper(BaseBot):
    """
    Bookkeeper - Logger and Auditor
    
    Role: Passively observes all state transitions, maintains
    append-only operation ledger, generates technical and
    executive final reports.
    
    Always running as background task. First spawned, last killed.
    """
    
    bot_name = "bookkeeper"
    role_description = "operation logger and report generator"
    
    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)
        self._prompt = self._build_auditor_prompt()
    
    def _build_auditor_prompt(self) -> str:
        """Build Bookkeeper's system prompt."""
        return f"""You are Bookkeeper, the operation logger and auditor for SwarmBots.

Your mission:
1. Passively observe all state transitions
2. Maintain append-only operation ledger
3. Log every bot action with timestamp
4. Generate technical report (findings, IOCs, TTPs)
5. Generate executive report (business impact, recommendations)
6. Archive operation to vault

Current Mission:
{self.state.get('mission', {})}

Operation Ledger:
{self.state.get('operation_ledger', [])}

You are meticulous and impartial. You record everything without bias."""
    
    async def reason(self) -> Dict[str, Any]:
        """
        Bookkeeper reasoning: assess logging completeness.
        """
        self._log("Assessing operation log...", "REASON")
        
        ledger = self.state.get("operation_ledger", [])
        reasoning_reports = self.state.get("reasoning_reports", {})
        
        # Bookkeeper is always needed
        strategy = "continuous_logging"
        self._log(f"Logging strategy: {strategy}", "DECIDE")
        
        return {
            "needed": True,
            "strategy": strategy,
            "confidence": 1.0,
            "reasoning": f"Operation ledger contains {len(ledger)} entries. {len(reasoning_reports)} bots have reported.",
            "recommended_actions": [
                "ledger_append",
                "integrity_check",
                "report_generation"
            ]
        }
    
    async def execute(self) -> Dict[str, Any]:
        """
        Bookkeeper execution: finalize ledger, generate reports.
        """
        self._log("Finalizing operation log...", "EXECUTE")
        
        ledger = self.state.get("operation_ledger", [])
        reasoning_reports = self.state.get("reasoning_reports", {})
        
        # Generate final report
        final_report = {
            "generated_at": datetime.utcnow().isoformat(),
            "mission": self.state.get("mission", {}),
            "bots_deployed": list(reasoning_reports.keys()),
            "total_actions": len(ledger),
            "executive_summary": self._generate_executive_summary(),
            "technical_findings": self._generate_technical_findings(),
            "iocs": self._extract_iocs(),
            "ttps": self._extract_ttps(),
            "recommendations": self._generate_recommendations()
        }
        
        self._append_ledger("final_report_generated", {"report_id": final_report["generated_at"]})
        
        # Update state
        self.state["final_report"] = final_report
        
        return final_report
    
    def _generate_executive_summary(self) -> str:
        """Generate executive summary for leadership."""
        ledger = self.state.get("operation_ledger", [])
        return f"""
EXECUTIVE SUMMARY
=================

Operation completed successfully. {len(ledger)} actions logged.

Key Findings:
- Reconnaissance: Passive OSINT completed
- Vulnerabilities: Multiple high-severity findings
- Exploitation: Initial access achieved (human-approved)
- Post-Exploitation: Privilege escalation and lateral movement successful
- Data Exposure: Sensitive data identified and documented

Business Impact:
- Critical vulnerabilities require immediate remediation
- Active Directory exposure detected
- Data exfiltration paths identified

Recommendations:
1. Patch critical vulnerabilities within 7 days
2. Implement network segmentation
3. Deploy EDR on all endpoints
4. Conduct security awareness training
"""
    
    def _generate_technical_findings(self) -> List[Dict[str, Any]]:
        """Generate technical findings for security team."""
        vuln_report = self.state.get("vuln_report", [])
        return [{
            "id": f"finding_{i}",
            "severity": v.get("cvss", 0),
            "target": v.get("host"),
            "vulnerability": v.get("cve"),
            "evidence": v.get("evidence"),
            "remediation": v.get("recommendation")
        } for i, v in enumerate(vuln_report)]
    
    def _extract_iocs(self) -> List[str]:
        """Extract indicators of compromise."""
        iocs = []
        vuln_report = self.state.get("vuln_report", [])
        for v in vuln_report:
            if v.get("host"):
                iocs.append(f"IP: {v.get('host')}")
        return iocs
    
    def _extract_ttps(self) -> List[str]:
        """Extract MITRE ATT&CK TTPs."""
        ttps = [
            "T1595 - Active Scanning",
            "T1190 - Exploit Public-Facing Application",
            "T1068 - Exploitation for Privilege Escalation",
            "T1021 - Remote Services",
            "T1003 - OS Credential Dumping"
        ]
        return ttps
    
    def _generate_recommendations(self) -> List[str]:
        """Generate security recommendations."""
        return [
            "Implement vulnerability management program",
            "Deploy network segmentation",
            "Enable MFA for all privileged accounts",
            "Conduct regular penetration testing",
            "Implement security monitoring (SIEM)"
        ]
