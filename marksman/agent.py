"""
Chimeras v2.5 — Marksman Agent

Exploit researcher AND exploitation operator. Merges Pathologist (research/development)
and Surgeon (execution/delivery) into a single bot.

- Researches, develops, adapts, and fires exploits
- Searches exploit-db, GitHub, PacketStorm for PoCs
- Writes custom exploits from scratch when needed
- Fires exploits against human-approved targets
- Catches shells, manages sessions, tracks artifacts
- Hands off to Magician for privilege escalation

HUMAN-IN-LOOP GATE: only runs if human_approval=True

Tool category: marksman (combines payload_fab + exploitation tools)
SHELL_CAPABLE — can use shell metacharacters for crafting and executing payloads.
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class Marksman(BaseBot):
    """Marksman — Exploit Researcher & Operator.

    Does both research (was Pathologist) and execution (was Surgeon).
    Human gate enforced — blocks immediately if not approved.
    """

    bot_name = "marksman"
    role_description = (
        "exploit researcher and operator — researches, develops, adapts, and fires "
        "exploits against approved targets, establishes sessions, tracks artifacts"
    )
    scope_description = (
        "Exploit research AND execution. Searches for PoCs, writes custom exploits, "
        "fires them against approved targets, catches shells, manages sessions. "
        "NO privilege escalation, NO exfiltration."
    )

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    async def run(self) -> Dict[str, Any]:
        """Override to check human approval gate before doing anything."""
        if not self.state.get("human_approval", False):
            self._banner()
            self._log("HUMAN APPROVAL NOT GRANTED — exploitation blocked", "GATE")
            self._append_log("BLOCKED: Human approval not granted. Exploitation phase skipped.")
            self._write_bot_file("# MARKSMAN — BLOCKED\n\nHuman approval not granted. Exploitation phase skipped.\n")
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
        """Update state with exploit research output, active sessions, and track artifacts.

        Merges Pathologist's payload manifest tracking and Surgeon's session/artifact tracking.
        """
        try:
            structured = analysis.get("structured_data", {})
            if not isinstance(structured, dict):
                structured = {}

            self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision

            # ─── Track payloads/exploits (was Pathologist) ───
            payloads = structured.get("payloads", [])
            if payloads:
                self.state["payloads"] = payloads

            # ─── Track active sessions (was Surgeon) ───
            sessions = structured.get("sessions", [])
            self.state["active_sessions"] = sessions

            # ─── Track exploited hosts ───
            exploited = self.state.get("exploited_hosts", [])
            if not isinstance(exploited, list):
                exploited = []

            for session in sessions:
                if isinstance(session, dict):
                    host = session.get("host") or session.get("target") or session.get("ip")
                    if host and isinstance(host, str) and host not in exploited:
                        exploited.append(host)
                elif isinstance(session, str) and session not in exploited:
                    exploited.append(session)

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

            # ─── Track failed exploitation attempts ───
            failed = self.state.get("failed_vectors", [])
            if not isinstance(failed, list):
                failed = []

            for key in ("failed_exploits", "failed_checks", "errors", "blocked_attempts"):
                found = structured.get(key, [])
                if isinstance(found, list):
                    for item in found:
                        if isinstance(item, dict):
                            failed.append({
                                "target": item.get("target", item.get("host", "unknown")),
                                "tool": item.get("tool", self.bot_name),
                                "error": item.get("error", item.get("reason", "unknown")),
                                "timestamp": item.get("timestamp", ""),
                            })

            for result in tool_results:
                if isinstance(result, dict) and not result.get("success", True) and not result.get("scope_blocked"):
                    cmd = result.get("command", "")
                    tool_name = cmd.split()[0] if cmd else self.bot_name
                    failed.append({
                        "target": self.state.get("mission", {}).get("target", "unknown"),
                        "tool": tool_name,
                        "error": result.get("stderr", "exploit failed")[:200],
                        "timestamp": "",
                    })

            self.state["failed_vectors"] = failed

        except Exception as e:
            print(f"[MARKSMAN] _update_state error: {e}")
            try:
                self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision
                self.state["active_sessions"] = analysis.get("structured_data", {}).get("sessions", [])
            except Exception:
                pass