"""
Chimeras v2.0 — WarChief Agent

Supervisor/orchestrator. Reads engagement files, decides next bot,
writes strategic plan. No tool execution — file I/O only.

v2 Phase 0: WarChief produces routing decisions, decision log.
v2 Phase 2: Full decision logic:
  - Mission state machine (init → recon → scanning → ... → complete)
  - Decision history (rolling context window, last 5 entries)
  - Confidence threshold (below 0.6 → safe conservative route)
  - Scope exhaustion detection (ARIA 2x zero new targets → force report)
  - Backtracking rule enforcement (no scan after shell in external scope)
"""

from typing import Dict, Any, Optional
from datetime import datetime
import json

from core.base_bot import BaseBot
from core.state import SwarmState


# ─── Valid routing decisions ───
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


# ─── Mission state machine ───
# Ordered lifecycle. WarChief transitions through these states.
# Used to determine routing context and enforce backtracking rules.
MISSION_STATES = [
    "init",
    "recon",
    "scanning",
    "vuln_detection",
    "exploitation_prep",
    "exploitation",
    "post_exploit",
    "lateral_recon",
    "lateral_scanning",
    "reporting",
    "complete",
]

# Map WarChief decisions to next mission state
DECISION_TO_STATE = {
    "init": "recon",
    "recon": "recon",
    "scan": "scanning",
    "vulns_found_exploit": "exploitation_prep",
    "insufficient_data_abort": "reporting",
    "lateral_recon": "lateral_recon",
    "lateral_scan": "lateral_scanning",
    "report": "reporting",
    "continue_exploit": "exploitation",
    "privesc": "post_exploit",
    "exfiltrate": "post_exploit",
}

# Default confidence threshold — below this, WarChief defaults to safe route
DEFAULT_CONFIDENCE_THRESHOLD = 0.6

# Maximum decision history entries kept (rolling window)
MAX_HISTORY = 5

# Scope exhaustion: how many recon cycles with zero new targets before flagging
SCOPE_EXHAUSTION_THRESHOLD = 2


class WarChief(BaseBot):
    """WarChief — Supervisor and Orchestrator. File I/O only, no tools.

    v2 Phase 2: Full decision logic with state machine, confidence threshold,
    scope exhaustion detection, and decision history for trend awareness.
    """

    bot_name = "warchief"
    role_description = "swarm supervisor and orchestrator — reads all bot reports, decides next action, writes engagement plan"
    scope_description = "Orchestrator ONLY. Reads engagement files, writes plan.md, coordinates bot flow. NO tool execution."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)
        # Initialize Phase 2 state fields if not present
        if "decision_history" not in self.state:
            self.state["decision_history"] = []
        if "mission_state" not in self.state:
            self.state["mission_state"] = "init"
        if "scope_exhausted" not in self.state:
            self.state["scope_exhausted"] = False
        if "confidence_threshold" not in self.state:
            self.state["confidence_threshold"] = DEFAULT_CONFIDENCE_THRESHOLD

    def _build_system_prompt(self) -> str:
        """WarChief system prompt with full decision logic.

        v2 Phase 2 additions:
        - Mission state machine context
        - Decision history (last 5 entries for trend awareness)
        - Confidence threshold guidance
        - Scope exhaustion warning
        - Backtracking rule enforcement
        """
        decisions_help = "\n".join(
            f"  - \"{d}\": {desc}" for d, desc in VALID_DECISIONS.items()
        )

        # ─── Loop counters ───
        loop_count = self.state.get("loop_count", {})
        loop_info = ""
        if loop_count:
            max_loops = self.state.get("max_loops_per_phase", 5)
            loop_info = f"\n\n## Loop Counters (per phase, max {max_loops})\n"
            for phase, count in loop_count.items():
                warning = " ⚠ APPROACHING LIMIT" if count >= max_loops - 1 else ""
                loop_info += f"  {phase}: {count} cycles{warning}\n"

        # ─── Aggressiveness level ───
        aggressiveness = self.state.get("aggressiveness", "cautious")
        agg_info = f"\n\n## Aggressiveness Level: {aggressiveness}\n"
        if aggressiveness == "cautious":
            agg_info += "Scan carefully. If target shows WAF/IPS signs, do not escalate to aggressive scanning.\n"
        elif aggressiveness == "normal":
            agg_info += "Normal scanning speed. Can use more aggressive tools if needed.\n"
        elif aggressiveness == "passive_only":
            agg_info += "Target is hardened. Passive recon only — no active scanning.\n"

        # ─── Failed vectors ───
        failed = self.state.get("failed_vectors", [])
        failed_info = ""
        if failed:
            failed_info = f"\n\n## Failed Attack Vectors ({len(failed)} recorded)\n"
            for fv in failed[-5:]:
                target = fv.get("target", "?")
                tool = fv.get("tool", "?")
                error = fv.get("error", "?")
                if len(error) > 60:
                    error = error[:60] + "..."
                failed_info += f"  - {target}: {tool} — {error}\n"

        # ─── Decision history (context window for trends) ───
        history = self.state.get("decision_history", [])
        history_info = ""
        if history:
            history_info = f"\n\n## Decision History (last {len(history)} decisions — look for trends)\n"
            for i, h in enumerate(history, 1):
                h_decision = h.get("decision", "?")
                h_reasoning = h.get("reasoning", "?")
                h_phase = h.get("phase", "?")
                if len(h_reasoning) > 80:
                    h_reasoning = h_reasoning[:80] + "..."
                history_info += f"  {i}. [{h_phase}] {h_decision}: {h_reasoning}\n"
            history_info += (
                "\nLook at this history carefully. If the same phase has run "
                "multiple times with no new findings, it's time to pivot or abort.\n"
            )

        # ─── Scope exhaustion warning ───
        scope_exhausted = self.state.get("scope_exhausted", False)
        scope_info = ""
        if scope_exhausted:
            scope_info = (
                "\n\n## ⚠ SCOPE EXHAUSTED\n"
                "Recon has run multiple times with zero new targets discovered.\n"
                "You MUST route to \"report\" with reason \"scope depleted\".\n"
                "Do NOT route to \"recon\" again — there is nothing left to find.\n"
            )

        # ─── Mission state machine ───
        current_state = self.state.get("mission_state", "init")
        target_context = self.state.get("target_context", "external")
        state_info = f"\n\n## Mission State: {current_state} (context: {target_context})\n"
        state_info += "State progression: init → recon → scanning → vuln_detection → exploitation_prep → exploitation → post_exploit → lateral_recon → lateral_scanning → reporting → complete\n"

        # ─── Backtracking rule ───
        backtrack_info = ""
        if target_context == "external":
            backtrack_info = (
                "\n## Backtracking Rule (EXTERNAL scope)\n"
                "Once exploitation is achieved (shell obtained), do NOT route back to "
                "scanning or recon within the external scope. Move forward to privesc "
                "or lateral movement. Re-scanning the same external targets after "
                "getting a shell wastes cycles.\n"
            )
        elif target_context == "lateral":
            backtrack_info = (
                "\n## Backtracking Rule (LATERAL scope)\n"
                "Backtracking to scanning IS allowed in lateral context — these are "
                "newly-discovered internal targets that haven't been scanned yet.\n"
                "Standard progression applies: recon → scan → vuln → exploit.\n"
            )

        # ─── Confidence threshold guidance ───
        threshold = self.state.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
        confidence_info = (
            f"\n\n## Confidence Threshold: {threshold}\n"
            f"If your confidence is below {threshold}, you MUST default to a safe "
            "conservative route:\n"
            "  - In recon/scan phase → default to \"scan\" (let Lisa gather more data)\n"
            "  - In vuln phase → default to \"scan\" for deeper scanning\n"
            "  - In exploitation → default to \"privesc\" (try escalating)\n"
            "  - If truly stuck → default to \"report\" (don't loop forever)\n"
            "Do NOT route aggressively if you're unsure. Uncertainty = gather more data.\n"
        )

        return f"""You are {self.bot_name}, {self.role_description}.

## Your Scope
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
- If Lisa found only low-value ports (SMTP, DNS) → "recon" for deeper OSINT
- If Bloodhound found 0 CVEs but config misconfigs → "scan" for deeper scanning
- If Bloodhound found exploitable vulns → "vulns_found_exploit"
- If Surgeon got shell but no privesc viable → "lateral_recon"
- If Thief confirmed data exfil → "report"
- If 3+ decision cycles with no forward progress → "insufficient_data_abort"
- If scope exhausted (ARIA ran 2x, zero new targets) → "report" with "scope depleted"
- If recon found internal network and we have shell → "lateral_recon" (needs approval)
{state_info}{backtrack_info}{history_info}{scope_info}{loop_info}{agg_info}{failed_info}{confidence_info}

## Your Task
1. Read the engagement files to understand what bots have reported
2. Assess the current mission state and what has been completed
3. Check decision history — are we looping? Is progress being made?
4. Decide which action to take next (output a valid decision value)
5. Write a strategic plan update for plan.md
6. If confidence is low (< {threshold}), default to a safe conservative route

## Response Format
Respond ONLY with a JSON block:
```json
{{
  "needed": true,
  "strategy": "brief description of coordination approach",
  "confidence": 0.95,
  "reasoning": "why you chose this route — reference specific findings and decision history",
  "commands": [],
  "decision": "one of the valid routing decisions above",
  "assessment": "brief summary of current engagement state",
  "updated_plan": "markdown plan update for plan.md — include what was done and what's next",
  "mission_phase": "init/recon/scanning/vuln_detection/exploitation/post_exploit/lateral_recon/lateral_scanning/reporting/complete",
  "loop_count_update": {{"phase_name": 1}}
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
4. Are we making progress or looping? Check decision history.
5. Write a strategic plan update for plan.md

Be specific in your reasoning. Reference actual findings from the bot reports.
If you are unsure, default to "scan" to gather more data, or "report" if scope is exhausted."""

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with WarChief's coordination.

        v2 Phase 2: Full state machine, decision history, confidence enforcement,
        scope exhaustion detection, and backtracking rule enforcement.
        """
        try:
            # ─── Extract and validate the decision ───
            raw_decision = decision.get("decision") or "report"
            if raw_decision not in VALID_DECISIONS:
                raw_decision = "report"
                decision["decision"] = raw_decision
                decision["_fallback"] = True
                decision["_fallback_reason"] = "Invalid decision value, defaulted to 'report'"

            # ─── Confidence threshold enforcement ───
            confidence = decision.get("confidence", 0.0)
            try:
                confidence = float(confidence)
            except (ValueError, TypeError):
                confidence = 0.0
                decision["confidence"] = 0.0

            threshold = self.state.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
            if confidence < threshold:
                # Low confidence — override to safe conservative route
                safe_route = self._get_safe_route()
                if safe_route != raw_decision:
                    original_decision = raw_decision
                    raw_decision = safe_route
                    decision["decision"] = raw_decision
                    decision["_confidence_override"] = True
                    decision["_original_decision"] = original_decision
                    decision["_override_reason"] = (
                        f"Confidence {confidence:.2f} below threshold {threshold:.2f} — "
                        f"overridden to safe route '{safe_route}'"
                    )

            # ─── Scope exhaustion enforcement ───
            if self.state.get("scope_exhausted", False):
                if raw_decision in ("recon", "scan"):
                    raw_decision = "report"
                    decision["decision"] = raw_decision
                    decision["_scope_exhausted_override"] = True
                    decision["_override_reason"] = (
                        "Scope exhausted — forced route to 'report'"
                    )

            # ─── Backtracking rule enforcement ───
            target_context = self.state.get("target_context", "external")
            current_state = self.state.get("mission_state", "init")
            if target_context == "external":
                # No backtrack to scanning/recon after shell in external scope
                if current_state in ("exploitation", "post_exploit"):
                    if raw_decision in ("scan", "recon"):
                        raw_decision = "privesc"
                        decision["decision"] = raw_decision
                        decision["_backtrack_override"] = True
                        decision["_override_reason"] = (
                            f"Backtracking to '{raw_decision}' blocked in external scope "
                            f"after exploitation — forced to 'privesc'"
                        )

            # ─── Store in state ───
            self.state["last_decision"] = raw_decision

            # ─── Update mission state machine ───
            mission_phase = decision.get("mission_phase", "")
            if mission_phase and mission_phase in MISSION_STATES:
                self.state["mission_state"] = mission_phase
            else:
                # Derive state from decision
                new_state = DECISION_TO_STATE.get(raw_decision, current_state)
                self.state["mission_state"] = new_state
                decision["mission_phase"] = new_state

            # Also store phase in mission dict for graph routing compatibility
            self.state.setdefault("mission", {})["phase"] = self.state["mission_state"]

            # ─── Update loop count ───
            loop_update = decision.get("loop_count_update", {})
            if loop_update and isinstance(loop_update, dict):
                current_loops = self.state.get("loop_count", {})
                if not isinstance(current_loops, dict):
                    current_loops = {}
                for phase, increment in loop_update.items():
                    try:
                        current_loops[phase] = current_loops.get(phase, 0) + int(increment)
                    except (ValueError, TypeError):
                        pass  # Bad increment value — skip
                self.state["loop_count"] = current_loops

            # ─── Update decision history (rolling window) ───
            history = self.state.get("decision_history", [])
            if not isinstance(history, list):
                history = []
            history_entry = {
                "decision": raw_decision,
                "reasoning": decision.get("reasoning", ""),
                "phase": self.state.get("mission_state", ""),
                "confidence": confidence,
                "timestamp": datetime.utcnow().isoformat(),
                "overrides": {
                    k: v for k, v in decision.items()
                    if k.startswith("_") and k.endswith("_override")
                } or None,
            }
            history.append(history_entry)
            # Trim to last MAX_HISTORY entries
            if len(history) > MAX_HISTORY:
                history = history[-MAX_HISTORY:]
            self.state["decision_history"] = history

            # ─── Scope exhaustion detection ───
            self._check_scope_exhaustion()

            # ─── Write plan to plan.md ───
            plan_content = decision.get("updated_plan", analysis.get("updated_plan", ""))
            if plan_content:
                try:
                    if self.engagement_dir is None:
                        raise ValueError("No engagement directory set")
                    plan_path = self.engagement_dir / "plan.md"
                    existing = plan_path.read_text() if plan_path.exists() else ""
                    plan_path.write_text(
                        existing + f"\n\n## WarChief Assessment ({datetime.utcnow().isoformat()})\n\n"
                        f"**Decision**: {raw_decision}\n"
                        f"**Confidence**: {confidence:.2f}\n"
                        f"**State**: {self.state.get('mission_state', 'N/A')}\n"
                        f"**Phase**: {decision.get('mission_phase', 'N/A')}\n"
                        + (f"**Override**: {decision.get('_override_reason', '')}\n" if decision.get('_override_reason') else "")
                        + f"\n{plan_content}\n"
                    )
                except Exception as e:
                    print(f"[WARCHELF] Failed to write plan.md: {e}")

            # ─── Write decision log (audit trail) ───
            self._log_decision(decision, raw_decision, confidence)

            self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision

        except Exception as e:
            # Never let _update_state crash the graph
            print(f"[WARCHELF] _update_state error: {e}")
            try:
                self.state["last_decision"] = "report"
                self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision
            except Exception:
                pass

    def _get_safe_route(self) -> str:
        """Determine the safe conservative route based on current state.

        When confidence is below threshold, WarChief defaults to this route
        instead of the LLM's potentially uncertain decision.
        """
        try:
            current_state = self.state.get("mission_state", "init")
            safe_map = {
                "init": "recon",
                "recon": "scan",
                "scanning": "scan",
                "vuln_detection": "scan",
                "exploitation_prep": "vulns_found_exploit",
                "exploitation": "privesc",
                "post_exploit": "report",
                "lateral_recon": "lateral_recon",
                "lateral_scanning": "lateral_scan",
                "reporting": "report",
                "complete": "report",
            }
            return safe_map.get(current_state, "report")
        except Exception:
            return "report"

    def _check_scope_exhaustion(self) -> None:
        """Check if scope is exhausted based on recon loop count and targets.

        Sets state["scope_exhausted"] = True when:
        - Recon phase has run >= SCOPE_EXHAUSTION_THRESHOLD times (2)
        - AND zero new targets were discovered in those cycles

        Once flagged, WarChief is forced to route to "report".
        """
        try:
            loops = self.state.get("loop_count", {})
            if not isinstance(loops, dict):
                return

            recon_cycles = loops.get("recon", 0)
            if recon_cycles < SCOPE_EXHAUSTION_THRESHOLD:
                return

            # Check if discovered_targets has grown
            discovered = self.state.get("discovered_targets", [])
            external = self.state.get("external_targets", [])

            # If we have no more discovered targets than our initial scope,
            # and recon has run 2+ times, scope is exhausted
            if not discovered or len(discovered) <= len(external):
                self.state["scope_exhausted"] = True
                print(f"[WARCHELF] Scope exhausted — {recon_cycles} recon cycles, "
                      f"zero new targets beyond initial scope")
        except Exception as e:
            print(f"[WARCHELF] Scope exhaustion check error: {e}")

    def _log_decision(self, decision: Dict[str, Any], routed_decision: str,
                      confidence: float) -> None:
        """Write routing decision to warchief_decisions.log (audit trail).

        Format: timestamped JSON lines — one per decision.
        Includes overrides (confidence, scope exhaustion, backtracking).
        """
        try:
            if self.engagement_dir is None:
                raise ValueError("No engagement directory set")
            log_path = self.engagement_dir / "warchief_decisions.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)

            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "decision": routed_decision,
                "confidence": confidence,
                "reasoning": decision.get("reasoning", ""),
                "assessment": decision.get("assessment", ""),
                "mission_phase": decision.get("mission_phase", ""),
                "mission_state": self.state.get("mission_state", ""),
                "loop_count": self.state.get("loop_count", {}),
                "scope_exhausted": self.state.get("scope_exhausted", False),
                "target_context": self.state.get("target_context", "external"),
                "fallback": decision.get("_fallback", False),
                "confidence_override": decision.get("_confidence_override", False),
                "scope_exhausted_override": decision.get("_scope_exhausted_override", False),
                "backtrack_override": decision.get("_backtrack_override", False),
                "override_reason": decision.get("_override_reason", ""),
            }

            with open(log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"[WARCHELF] Failed to write decision log: {e}")