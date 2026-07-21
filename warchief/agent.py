"""
Chimeras v2.0 — WarChief Agent

Supervisor/orchestrator. Reads engagement files, decides next bot,
writes strategic plan. No tool execution — file I/O only.

v2 Phase 0: WarChief now produces real routing decisions.
  - "decision" field with defined routing values
  - last_decision stored in state for downstream bots
  - Decision log written to engagement/warchief_decisions.log
  - Fallback for malformed output: defaults to "report" (safe route)
"""

from typing import Dict, Any, Optional
from datetime import datetime
import json

from core.base_bot import BaseBot
from core.state import SwarmState


# ─── Valid routing decisions ───
# These are the values WarChief can output in the "decision" field.
# Phase 1's graph routing functions will read these to determine edges.
VALID_DECISIONS = {
    "init":              "Initial planning — no prior work exists",
    "recon":             "Route to ARIA for passive reconnaissance",
    "scan":              "Route to Lisa for active scanning",
    "vulns_found_exploit": "Exploitable vulns found — route to human approval gate",
    "insufficient_data_abort": "Not enough data to continue — abort to report",
    "lateral_recon":     "Pivot to lateral recon (internal network) — requires lateral_approval gate",
    "lateral_scan":      "Pivot to lateral scanning — requires lateral_approval gate",
    "report":            "Mission complete or scope exhausted — route to Bookkeeper",
    "continue_exploit":  "Continue exploitation phase — route to Surgeon",
    "privesc":           "Shell obtained — route to Magician for privilege escalation",
    "exfiltrate":        "Privileges escalated — route to Thief for data exfiltration",
}


class WarChief(BaseBot):
    """WarChief — Supervisor and Orchestrator. File I/O only, no tools."""

    bot_name = "warchief"
    role_description = "swarm supervisor and orchestrator — reads all bot reports, decides next action, writes engagement plan"
    scope_description = "Orchestrator ONLY. Reads engagement files, writes plan.md, coordinates bot flow. NO tool execution."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    def _build_system_prompt(self) -> str:
        """Override — WarChief decides flow, doesn't run tools.

        v2: Prompt now requires a "decision" field with defined routing values.
        """
        decisions_help = "\n".join(
            f"  - \"{d}\": {desc}" for d, desc in VALID_DECISIONS.items()
        )

        # Include loop count if available (for scope exhaustion awareness)
        loop_count = self.state.get("loop_count", {})
        loop_info = ""
        if loop_count:
            loop_info = f"\n\n## Loop Counters (per phase, max {self.state.get('max_loops_per_phase', 5)})\n"
            for phase, count in loop_count.items():
                loop_info += f"  {phase}: {count} cycles\n"

        # Include aggressiveness level
        aggressiveness = self.state.get("aggressiveness", "cautious")
        agg_info = f"\n\n## Aggressiveness Level: {aggressiveness}\n"
        if aggressiveness == "cautious":
            agg_info += "Scan carefully. If target shows WAF/IPS signs, do not escalate to aggressive scanning.\n"
        elif aggressiveness == "normal":
            agg_info += "Normal scanning speed. Can use more aggressive tools if needed.\n"
        elif aggressiveness == "passive_only":
            agg_info += "Target is hardened. Passive recon only — no active scanning.\n"

        # Include failed vectors if any
        failed = self.state.get("failed_vectors", [])
        failed_info = ""
        if failed:
            failed_info = f"\n\n## Failed Attack Vectors ({len(failed)} recorded)\n"
            for fv in failed[-5:]:  # Last 5 only
                failed_info += f"  - {fv.get('target', '?')}: {fv.get('tool', '?')} — {fv.get('error', '?')[:60]}\n"

        return f"""You are {self.bot_name}, {self.role_description}.

## YourScope
{self.scope_description}

## Pipeline Order (v2 — adaptive)
WarChief (init) → ARIA (recon) → WarChief (route) → Lisa (scan) → WarChief (route)
→ Bloodhound (vuln) → [HUMAN APPROVAL] → Pathologist → Surgeon → WarChief (route)
→ Magician → Thief → WarChief (final) → Bookkeeper → END

In v2, you re-enter after each phase to assess findings and route the next action.
You are NOT a one-shot planner. You are a dynamic router — a real pentester lead.

## Valid Routing Decisions
You MUST output a "decision" field with one of these exact values:
{decisions_help}

## Decision Criteria
- If ARIA found no new targets and we've scanned common OSINT sources → "scan"
- If Lisa found only low-value ports (SMTP, DNS) → "recon" for lateral movement
- If Bloodhound found 0 CVEs but config misconfigs → "scan" for deeper scanning
- If Bloodhound found exploitable vulns → "vulns_found_exploit"
- If Surgeon got shell but no privesc viable → "lateral_recon"
- If Thief confirmed data exfil → "report"
- If 3+ decision cycles with no forward progress → "insufficient_data_abort"
- If scope exhausted (ARIA ran 2x, zero new targets) → "report" with "scope depleted"
{loop_info}{agg_info}{failed_info}

## Your Task
1. Read the engagement files to understand what bots have reported
2. Assess the current mission phase and what has been completed
3. Decide which action to take next (output a valid decision value)
4. Write a strategic plan update for plan.md
5. If confidence is low (< 0.6), default to a safe conservative route

## Response Format
Respond ONLY with a JSON block:
```json
{{
  "needed": true,
  "strategy": "brief description of coordination approach",
  "confidence": 0.95,
  "reasoning": "why you chose this route — reference specific findings",
  "commands": [],
  "decision": "one of the valid routing decisions above",
  "assessment": "brief summary of current engagement state",
  "updated_plan": "markdown plan update for plan.md — include what was done and what's next",
  "mission_phase": "init/recon/scanning/vuln_detection/exploitation/post_exploit/lateral_recon/reporting/complete",
  "loop_count_update": {{"phase_name": increment}}
}}
```
No other text. Just the JSON."""

    def _build_analysis_prompt(self, raw_output: str, context: str) -> str:
        """WarChief doesn't analyze tool output — it writes the plan."""
        return f"""## Current Engagement State

{context}

## Your Task
Based on the engagement files above, determine:
1. What phase are we in?
2. What has been completed?
3. What decision should we make? (use a valid routing decision value)
4. Write a strategic plan update for plan.md

Be specific in your reasoning. Reference actual findings from the bot reports.
If you are unsure, default to "scan" to gather more data, or "report" if scope is exhausted."""

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with WarChief's coordination.

        v2: Stores last_decision in state, writes decision log,
        updates plan.md with timestamped assessment.
        """
        # Extract and validate the decision
        raw_decision = decision.get("decision") or "report"
        if raw_decision not in VALID_DECISIONS:
            # Invalid decision — fallback to safe route
            raw_decision = "report"
            decision["decision"] = raw_decision
            decision["_fallback"] = True
            decision["_fallback_reason"] = f"Invalid decision value, defaulted to 'report'"

        # Store in state for downstream bots and graph routing
        self.state["last_decision"] = raw_decision

        # Update loop count if WarChief provided an update
        loop_update = decision.get("loop_count_update", {})
        if loop_update:
            current_loops = self.state.get("loop_count", {})
            for phase, increment in loop_update.items():
                current_loops[phase] = current_loops.get(phase, 0) + int(increment)
            self.state["loop_count"] = current_loops

        # Update mission phase
        mission_phase = decision.get("mission_phase", "")
        if mission_phase:
            self.state.setdefault("mission", {})["phase"] = mission_phase

        # Write plan to plan.md
        plan_content = decision.get("updated_plan", analysis.get("updated_plan", ""))
        if plan_content:
            plan_path = self.engagement_dir / "plan.md"
            existing = plan_path.read_text() if plan_path.exists() else ""
            plan_path.write_text(
                existing + f"\n\n## WarChief Assessment ({datetime.utcnow().isoformat()})\n\n"
                f"**Decision**: {raw_decision}\n"
                f"**Confidence**: {decision.get('confidence', 'N/A')}\n"
                f"**Phase**: {mission_phase or 'N/A'}\n\n"
                f"{plan_content}\n"
            )

        # Write decision log (machine-readable audit trail)
        self._log_decision(decision, raw_decision)

        self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision

    def _log_decision(self, decision: Dict[str, Any], routed_decision: str) -> None:
        """Write routing decision to warchief_decisions.log (audit trail).

        Format: timestamped JSON lines — one per decision.
        Also writes a human-readable summary to warchief_decisions.log.
        """
        log_path = self.engagement_dir / "warchief_decisions.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "decision": routed_decision,
            "confidence": decision.get("confidence", 0),
            "reasoning": decision.get("reasoning", ""),
            "assessment": decision.get("assessment", ""),
            "mission_phase": decision.get("mission_phase", ""),
            "loop_count": self.state.get("loop_count", {}),
            "fallback": decision.get("_fallback", False),
        }

        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")