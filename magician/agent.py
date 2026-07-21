"""
Chimeras v2.0 — Magician Agent

Privilege escalation and lateral movement.
Scope: linpeas, find, cat, ls, ssh, smbclient, python3, bash

v2 Phase 3: Lateral movement and credential tracking.
  - Tracks lateral movement findings (credentials, AD enumeration)
  - Updates target_artifacts (users created, scheduled tasks, etc.)
  - Lateral context: post-exploitation on internal hosts
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class Magician(BaseBot):
    """Magician — Privilege Escalation and Lateral Movement"""

    bot_name = "magician"
    role_description = "privilege escalation and lateral movement specialist — local privesc, AD movement, credential dumping, internal pivoting"
    scope_description = "Privilege escalation and lateral movement ONLY. NO exfiltration, NO initial exploitation."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    def _build_system_prompt(self) -> str:
        """Override to add lateral movement context."""
        base_prompt = super()._build_system_prompt()

        target_context = self.state.get("target_context", "external")
        exploited_hosts = self.state.get("exploited_hosts", [])

        addendum = ""

        if target_context == "lateral":
            addendum += """

## LATERAL MOVEMENT MODE
You are performing privilege escalation and lateral movement on INTERNAL hosts.

Objectives:
- Escalate privileges on exploited internal hosts (local admin → SYSTEM/DA)
- Dump credentials (SAM, NTDS.dit, lsass, /etc/shadow)
- Enumerate Active Directory (users, groups, GPOs, SPNs)
- Identify paths to Domain Admin
- Find credentials for further lateral movement (credential reuse)

Track all artifacts: users created, scheduled tasks, services installed,
files dropped, registry modifications. These must be cleaned up later.
"""

        if exploited_hosts:
            addendum += f"\n\n## Exploited Hosts ({len(exploited_hosts)})\n"
            for host in exploited_hosts:
                addendum += f"  - {host}\n"
            addendum += "You have access to these hosts. Use them for lateral movement.\n"

        if addendum:
            return base_prompt + addendum
        return base_prompt

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with movement findings and track artifacts.

        v2 Phase 3: Populates movement_report and target_artifacts.
        """
        try:
            structured = analysis.get("structured_data", {})
            if not isinstance(structured, dict):
                structured = {}

            self.state["movement_report"] = structured
            self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision

            # ─── Track credentials found ───
            # Credentials are stored in movement_report for Thief to use
            credentials = structured.get("credentials", [])
            if isinstance(credentials, list) and credentials:
                existing_creds = self.state.get("movement_report", {}).get("credentials", [])
                if not isinstance(existing_creds, list):
                    existing_creds = []
                # Merge — don't duplicate
                for cred in credentials:
                    if cred not in existing_creds:
                        existing_creds.append(cred)
                structured["credentials"] = existing_creds
                self.state["movement_report"] = structured

            # ─── Track artifacts left on target ───
            artifacts = self.state.get("target_artifacts", [])
            if not isinstance(artifacts, list):
                artifacts = []

            for key in ("artifacts", "created_users", "scheduled_tasks", "installed_services", "modifications"):
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

            # ─── Update exploited hosts with new lateral targets ───
            exploited = self.state.get("exploited_hosts", [])
            if not isinstance(exploited, list):
                exploited = []

            for key in ("lateral_hosts", "new_access", "pivoted_to"):
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

        except Exception as e:
            print(f"[MAGICIAN] _update_state error: {e}")
            try:
                self.state["movement_report"] = analysis.get("structured_data", {})
                self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision
            except Exception:
                pass