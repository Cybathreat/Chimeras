"""
Chimeras v2.0 — Surgeon Agent

Exploitation specialist. Executes exploits against human-approved targets.
HUMAN-IN-LOOP GATE: only runs if human_approval=True
Scope: msfconsole, msfvenom, sqlmap, nc, python3

v2 Phase 3: Tracks exploited hosts and artifacts left on target.
  - Updates exploited_hosts in state when shell is obtained
  - Tracks target_artifacts (dropped payloads, scheduled tasks, users)
  - Lateral context: exploitation of internal targets post-pivot
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class Surgeon(BaseBot):
    """Surgeon — Exploitation Specialist. Human gate enforced."""

    bot_name = "surgeon"
    role_description = "exploitation and initial access specialist — executes exploits, establishes sessions, lateral exploitation"
    scope_description = "Exploitation ONLY. Executes approved exploits. NO privilege escalation, NO exfiltration."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    async def run(self) -> Dict[str, Any]:
        """Override to check human approval gate before doing anything."""
        if not self.state.get("human_approval", False):
            self._banner()
            self._log("HUMAN APPROVAL NOT GRANTED — exploitation blocked", "GATE")
            self._append_log("BLOCKED: Human approval not granted. Exploitation skipped.")
            self._write_bot_file("# SURGEON — BLOCKED\n\nHuman approval not granted. Exploitation phase skipped.\n")
            decision = {"needed": True, "strategy": "await_approval", "confidence": 1.0,
                        "reasoning": "Human approval gate not passed."}
            self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision
            return {"reasoning": decision, "executed": False, "awaiting_approval": True}

        return await super().run()

    def _build_system_prompt(self) -> str:
        """Override to add lateral exploitation context."""
        base_prompt = super()._build_system_prompt()

        target_context = self.state.get("target_context", "external")
        if target_context == "lateral":
            lateral_addendum = """

## LATERAL EXPLOITATION MODE
You are exploiting INTERNAL targets discovered during lateral movement.

Considerations:
- Use credentials harvested by Magician or ARIA for lateral access
- SMB exec, WinRM, RDP, PsExec-style attacks for Windows lateral movement
- SQL injection on internal database servers
- SSH key reuse or credential replay on internal Linux hosts
- Track every artifact you leave on the target (dropped payloads,
  scheduled tasks, created users, modified configs)

Internal targets have different characteristics than external:
- May be domain-joined (use AD credentials)
- May have less hardening than perimeter systems
- Higher value (database servers, Domain Controllers)

All targets are within approved lateral scope. The lateral_approval
gate has been passed.
"""
            return base_prompt + lateral_addendum

        return base_prompt

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with active sessions and track exploited hosts.

        v2 Phase 3: Populates exploited_hosts and target_artifacts.
        """
        try:
            structured = analysis.get("structured_data", {})
            if not isinstance(structured, dict):
                structured = {}

            sessions = structured.get("sessions", [])
            self.state["active_sessions"] = sessions
            self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision

            # ─── Track exploited hosts ───
            exploited = self.state.get("exploited_hosts", [])
            if not isinstance(exploited, list):
                exploited = []

            # Extract host from sessions
            for session in sessions:
                if isinstance(session, dict):
                    host = session.get("host") or session.get("target") or session.get("ip")
                    if host and isinstance(host, str) and host not in exploited:
                        exploited.append(host)
                elif isinstance(session, str) and session not in exploited:
                    exploited.append(session)

            # Also check structured data for exploited hosts
            for key in ("exploited_hosts", "shells", "access"):
                found = structured.get(key, [])
                if isinstance(found, list):
                    for h in found:
                        if isinstance(h, str) and h not in exploited:
                            exploited.append(h)
                        elif isinstance(h, dict):
                            host = h.get("host") or h.get("ip") or h.get("target")
                            if host and isinstance(host, str) and host not in exploited:
                                exploited.append(host)

            self.state["exploited_hosts"] = exploited

            # ─── Track artifacts left on target ───
            artifacts = self.state.get("target_artifacts", [])
            if not isinstance(artifacts, list):
                artifacts = []

            # Extract artifacts from analysis
            for key in ("artifacts", "dropped_files", "payloads_dropped", "modifications"):
                found = structured.get(key, [])
                if isinstance(found, list):
                    for a in found:
                        if isinstance(a, dict):
                            artifact = {
                                "host": a.get("host") or a.get("target", "unknown"),
                                "artifact_type": a.get("type", key),
                                "path": a.get("path", a.get("location", "unknown")),
                                "description": a.get("description", ""),
                                "cleaned": False,
                            }
                            artifacts.append(artifact)

            self.state["target_artifacts"] = artifacts

        except Exception as e:
            print(f"[SURGEON] _update_state error: {e}")
            try:
                self.state["active_sessions"] = analysis.get("structured_data", {}).get("sessions", [])
                self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision
            except Exception:
                pass