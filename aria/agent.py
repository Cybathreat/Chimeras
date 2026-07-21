"""
Chimeras v2.0 — ARIA Agent

Passive reconnaissance bot. OSINT only. NO active scanning.
Scope: dig, host, whois, curl, whatweb

v2 Phase 3: Lateral recon substrat.
  - When target_context is "lateral", ARIA performs internal network recon:
    DNS enumeration, SMB enumeration, credential dumping for pivoting
  - Tracks discovered_targets in state (for scope exhaustion detection)
  - Updates internal_targets when operating in lateral context
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class ARIA(BaseBot):
    """ARIA — Passive Reconnaissance Specialist"""

    bot_name = "aria"
    role_description = "passive reconnaissance specialist — OSINT, DNS, subdomains, tech stack, internal network recon"
    scope_description = "Passive reconnaissance ONLY. No active scanning, no exploitation. DNS lookups, WHOIS, certificate transparency, web fingerprinting, internal network discovery."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    def _build_system_prompt(self) -> str:
        """Override to add lateral recon context when in lateral mode."""
        base_prompt = super()._build_system_prompt()

        target_context = self.state.get("target_context", "external")
        if target_context == "lateral":
            lateral_addendum = """

## LATERAL RECON MODE
You are now operating in LATERAL context — recon on newly-discovered internal targets.

Your recon objectives shift to internal network discovery:
- DNS enumeration on internal domains
- SMB share enumeration (if SMB ports found)
- Internal hostname resolution
- Credential dumping for pivoting (from exploited host's session)
- Identify high-value internal services (SQL Server, Domain Controllers, file shares)
- Map internal network topology from what you can see

The lateral_approval gate has been passed. These targets are authorized.
However, all commands are still scope-enforced at the code level — only
targets within the approved internal scope will execute.

Prioritize finding: Domain Controllers, database servers, file shares,
admin workstations, and any service that could yield credentials or
further lateral movement.
"""
            return base_prompt + lateral_addendum

        return base_prompt

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with recon findings.

        v2 Phase 3: Tracks discovered_targets and internal_targets.
        v2.1: Seeds discovered_targets with the mission scope targets on first run
              so scope exhaustion doesn't fire when ARIA confirms the scope is valid.
        """
        try:
            self.state["recon_report"] = analysis.get("structured_data", {})
            self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision

            # ─── Target tracking ───
            structured = analysis.get("structured_data", {})
            if not isinstance(structured, dict):
                structured = {}

            # Extract discovered targets from analysis
            new_targets = []
            for key in ("targets", "hosts", "subdomains", "internal_hosts", "discovered"):
                found = structured.get(key, [])
                if isinstance(found, list):
                    for t in found:
                        if isinstance(t, str) and t:
                            new_targets.append(t)
                        elif isinstance(t, dict):
                            # Extract host/ip field from dict entries
                            for field in ("host", "ip", "hostname", "target", "address"):
                                val = t.get(field)
                                if val and isinstance(val, str):
                                    new_targets.append(val)
                                    break

            # v2.1: Seed discovered_targets with mission scope targets on first run
            # This prevents scope exhaustion from firing when ARIA confirms the
            # initial scope is valid (the targets exist and resolve) but hasn't
            # found NEW subdomains beyond the scope.
            mission = self.state.get("mission", {})
            scope_str = mission.get("scope", "")
            if scope_str:
                for token in scope_str.replace(",", " ").split():
                    token = token.strip().lower()
                    if token and token not in ("any", "*"):
                        if token not in new_targets:
                            new_targets.append(token)

            # Update discovered_targets (deduplicate)
            discovered = self.state.get("discovered_targets", [])
            if not isinstance(discovered, list):
                discovered = []
            for t in new_targets:
                if t not in discovered:
                    discovered.append(t)
            self.state["discovered_targets"] = discovered

            # Update internal_targets if in lateral context
            target_context = self.state.get("target_context", "external")
            if target_context == "lateral":
                internal = self.state.get("internal_targets", [])
                if not isinstance(internal, list):
                    internal = []
                for t in new_targets:
                    if t not in internal:
                        internal.append(t)
                self.state["internal_targets"] = internal

        except Exception as e:
            print(f"[ARIA] _update_state error: {e}")
            # Still set the basics — don't lose the report
            try:
                self.state["recon_report"] = analysis.get("structured_data", {})
                self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision
            except Exception:
                pass