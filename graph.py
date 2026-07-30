"""
Chimeras v2.0 — LangGraph Graph Wiring (Adaptive)

v2 flow (adaptive loop — WarChief re-enters after each phase):

  WarChief (init)
    → ARIA (recon) → WarChief (route) → {ARIA, Lisa, Bookkeeper}
    → Lisa (scan)  → WarChief (route) → {ARIA, Lisa, Bloodhound, Bookkeeper}
    → Bloodhound+Wasp (vuln detection, parallel) → WarChief (route) → {ARIA, Lisa, Human Gate, Bookkeeper}
    → [HUMAN APPROVAL]
    → Pathologist → Surgeon → WarChief (route) → {Surgeon, Magician, Bookkeeper}
    → Magician → WarChief (route) → {Surgeon, Thief, Bookkeeper}
    → Thief → WarChief (route) → {Surgeon, Thief, Bookkeeper}
    → Bookkeeper → END

  Lateral: WarChief 'lateral_recon'/'lateral_scan' → lateral_approval gate
  → if approved: ARIA/Lisa with target_context=lateral
  → if denied: Bookkeeper

Loop protection: per-phase max 5 cycles. If exceeded, force abort to
Bookkeeper. Tracked in state.loop_count.

Exception handling: every node wrapped in try/except. On failure, logs
error to engagement log.md, sets fallback state, routes to Bookkeeper.
No unhandled exceptions — the graph degrades gracefully.
"""

import asyncio
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END

from core.state import SwarmState
from warchief.agent import WarChief
from aria.agent import ARIA
from lisa.agent import Lisa
from bloodhound.agent import Bloodhound
from surgeon.agent import Surgeon
from wasp.agent import Wasp
from pathologist.agent import Pathologist
from thief.agent import Thief
from magician.agent import Magician
from bookkeeper.agent import Bookkeeper


# ─── Loop counter management ───

def _increment_loop(state: SwarmState, phase: str) -> int:
    """Increment the loop counter for a phase. Returns new count.

    Never raises — if loop tracking fails, returns 0.
    """
    try:
        loops = state.get("loop_count", {})
        if not isinstance(loops, dict):
            loops = {}
        loops[phase] = loops.get(phase, 0) + 1
        state["loop_count"] = loops
        return loops[phase]
    except Exception as e:
        print(f"[LOOP COUNTER ERROR] {e}")
        return 0


def _check_loop_limit(state: SwarmState, phase: str) -> bool:
    """Check if a phase has exceeded its loop limit.

    Returns True if limit exceeded (should abort). Never raises.
    """
    try:
        loops = state.get("loop_count", {})
        if not isinstance(loops, dict):
            return False
        max_loops = state.get("max_loops_per_phase", 5)
        return loops.get(phase, 0) >= max_loops
    except Exception:
        return False


# ─── Error logging utility ───

def _log_error(state: SwarmState, bot_name: str, error: Exception) -> None:
    """Log an error to the engagement log file.

    Never raises — if logging fails, silently continues.
    """
    try:
        eng_dir = state.get("engagement_dir", "")
        if not eng_dir:
            return
        from pathlib import Path
        from datetime import datetime
        log_path = Path(eng_dir) / "log.md"
        if log_path.parent.exists():
            with open(log_path, "a") as f:
                f.write(f"\n[{datetime.utcnow().isoformat()}] [{bot_name}] ERROR: {error}\n")
    except Exception:
        pass


# ─── Phase-specific routing functions ───
# Each checks loop limit, reads last_decision, returns next node name.

def route_after_recon(state: SwarmState) -> str:
    """Route after ARIA (recon phase)."""
    try:
        if _check_loop_limit(state, "recon"):
            print("[LOOP LIMIT] Recon phase exceeded max cycles — forcing abort to report")
            return "bookkeeper"

        decision = state.get("last_decision", "scan")

        if decision == "scan":
            return "lisa"
        elif decision == "vuln_detection":
            return "bloodhound"
        elif decision == "recon":
            return "aria"
        elif decision in ("report", "insufficient_data_abort"):
            return "bookkeeper"
        elif decision in ("lateral_recon", "lateral_scan"):
            return "lateral_approval"
        else:
            print(f"[ROUTING] Unknown decision '{decision}' after recon — defaulting to scan")
            return "lisa"
    except Exception as e:
        print(f"[ROUTING ERROR] route_after_recon: {e} — defaulting to bookkeeper")
        return "bookkeeper"


def route_after_scan(state: SwarmState) -> str:
    """Route after Lisa (scan phase)."""
    try:
        if _check_loop_limit(state, "scan"):
            print("[LOOP LIMIT] Scan phase exceeded max cycles — forcing abort to report")
            return "bookkeeper"

        decision = state.get("last_decision", "vulns_found_exploit")

        if decision == "vulns_found_exploit":
            return "bloodhound"
        elif decision == "vuln_detection":
            return "bloodhound"
        elif decision == "scan":
            # If scan has run 2+ cycles, force advance to Bloodhound
            # WarChief keeps saying "scan" when it means "advance to vuln detection"
            loop_count = state.get("loop_count", {})
            if not isinstance(loop_count, dict):
                loop_count = {}
            scan_cycles = loop_count.get("scan", 0)
            if scan_cycles >= 2:
                print(f"[FORCED ADVANCE] Scan ran {scan_cycles} cycles — forcing Bloodhound")
                return "bloodhound"
            return "lisa"
        elif decision == "recon":
            return "aria"
        elif decision in ("report", "insufficient_data_abort"):
            return "bookkeeper"
        elif decision in ("lateral_recon", "lateral_scan"):
            return "lateral_approval"
        else:
            print(f"[ROUTING] Unknown decision '{decision}' after scan — defaulting to bloodhound")
            return "bloodhound"
    except Exception as e:
        print(f"[ROUTING ERROR] route_after_scan: {e} — defaulting to bookkeeper")
        return "bookkeeper"


def route_after_vuln(state: SwarmState) -> str:
    """Route after Bloodhound (vuln detection phase)."""
    try:
        if _check_loop_limit(state, "vuln"):
            print("[LOOP LIMIT] Vuln phase exceeded max cycles — forcing abort to report")
            return "bookkeeper"

        decision = state.get("last_decision", "vulns_found_exploit")

        if decision == "vulns_found_exploit":
            return "human_approval"
        elif decision == "scan":
            return "lisa"
        elif decision == "recon":
            return "aria"
        elif decision in ("report", "insufficient_data_abort"):
            return "bookkeeper"
        elif decision in ("lateral_recon", "lateral_scan"):
            return "lateral_approval"
        else:
            print(f"[ROUTING] Unknown decision '{decision}' after vuln — defaulting to human_approval")
            return "human_approval"
    except Exception as e:
        print(f"[ROUTING ERROR] route_after_vuln: {e} — defaulting to bookkeeper")
        return "bookkeeper"


def route_after_exploit(state: SwarmState) -> str:
    """Route after Surgeon (exploitation phase).

    v2 Phase 4: If 3+ failed exploitation attempts on the same target,
    don't retry — pivot to lateral movement or report.

    Backtracking rule: no backtrack to scanning after shell within
    external scope. Allowed when context is lateral (Phase 3).
    """
    try:
        if _check_loop_limit(state, "exploit"):
            print("[LOOP LIMIT] Exploit phase exceeded max cycles — forcing abort to report")
            return "bookkeeper"

        decision = state.get("last_decision", "privesc")
        target_context = state.get("target_context", "external")

        # v2 Phase 4: Check if exploitation is failing repeatedly
        failed = state.get("failed_vectors", [])
        if isinstance(failed, list):
            # Count failed exploitation attempts
            exploit_failures = [f for f in failed if isinstance(f, dict) and f.get("tool", "") in ("msfconsole", "sqlmap", "nc", "python3", "bash")]
            if len(exploit_failures) >= 3:
                print(f"[FAILURE] {len(exploit_failures)} failed exploitation attempts — pivoting")
                return "bookkeeper"

        if decision == "privesc":
            return "magician"
        elif decision == "continue_exploit":
            return "surgeon"
        elif decision in ("lateral_recon", "lateral_scan"):
            return "lateral_approval"
        elif decision == "recon" and target_context == "lateral":
            return "aria"
        elif decision in ("report", "insufficient_data_abort"):
            return "bookkeeper"
        else:
            print(f"[ROUTING] Unknown decision '{decision}' after exploit — defaulting to magician")
            return "magician"
    except Exception as e:
        print(f"[ROUTING ERROR] route_after_exploit: {e} — defaulting to bookkeeper")
        return "bookkeeper"


def route_after_privesc(state: SwarmState) -> str:
    """Route after Magician (privesc phase)."""
    try:
        if _check_loop_limit(state, "privesc"):
            print("[LOOP LIMIT] Privesc phase exceeded max cycles — forcing abort to report")
            return "bookkeeper"

        decision = state.get("last_decision", "exfiltrate")

        if decision == "exfiltrate":
            return "thief"
        elif decision == "privesc":
            return "magician"
        elif decision in ("lateral_recon", "lateral_scan"):
            return "lateral_approval"
        elif decision == "continue_exploit":
            return "surgeon"
        elif decision in ("report", "insufficient_data_abort"):
            return "bookkeeper"
        else:
            print(f"[ROUTING] Unknown decision '{decision}' after privesc — defaulting to thief")
            return "thief"
    except Exception as e:
        print(f"[ROUTING ERROR] route_after_privesc: {e} — defaulting to bookkeeper")
        return "bookkeeper"


def route_after_exfil(state: SwarmState) -> str:
    """Route after Thief (exfiltration phase)."""
    try:
        if _check_loop_limit(state, "exfil"):
            print("[LOOP LIMIT] Exfil phase exceeded max cycles — forcing abort to report")
            return "bookkeeper"

        decision = state.get("last_decision", "report")

        if decision == "report":
            return "bookkeeper"
        elif decision == "exfiltrate":
            return "thief"
        elif decision in ("lateral_recon", "lateral_scan"):
            return "lateral_approval"
        elif decision == "continue_exploit":
            return "surgeon"
        elif decision == "insufficient_data_abort":
            return "bookkeeper"
        else:
            print(f"[ROUTING] Unknown decision '{decision}' after exfil — defaulting to bookkeeper")
            return "bookkeeper"
    except Exception as e:
        print(f"[ROUTING ERROR] route_after_exfil: {e} — defaulting to bookkeeper")
        return "bookkeeper"


def route_after_lateral_approval(state: SwarmState) -> str:
    """Route after lateral approval gate.

    If approved: switch target_context to lateral, route to ARIA/Lisa.
    If denied: route to Bookkeeper (no retry loop).
    """
    try:
        approved = state.get("lateral_approval", False)
        if not approved:
            print("[LATERAL] Lateral movement denied — routing to report")
            return "bookkeeper"

        state["target_context"] = "lateral"
        print("[LATERAL] Lateral movement approved — switching to internal scope")

        decision = state.get("last_decision", "lateral_recon")
        if decision == "lateral_scan":
            return "lisa"
        else:
            return "aria"
    except Exception as e:
        print(f"[ROUTING ERROR] route_after_lateral_approval: {e} — defaulting to bookkeeper")
        return "bookkeeper"


# ─── Unified WarChief router ───

def _unified_router(state: SwarmState) -> str:
    """Unified WarChief routing function.

    Determines the next node based on the last bot that actually ran and
    WarChief's routing decision. This is the single conditional edge from
    WarChief — it dispatches to phase-specific routing functions.

    v2.1: Uses last_bot from reasoning_reports instead of mission.phase.
    WarChief's LLM sets mission_phase to where it WANTS to go, not where
    the engagement IS. This caused Bloodhound to be skipped (WarChief set
    phase=vuln_detection before Bloodhound ran, so the router called
    route_after_vuln which routes to human_approval, skipping Bloodhound).

    Fallback: any unknown state routes to Bookkeeper (safe).
    """
    try:
        decision = state.get("last_decision", "")

        # Determine which bot ran last (most recent entry in reasoning_reports)
        reasoning_reports = state.get("reasoning_reports", {})
        if not isinstance(reasoning_reports, dict):
            reasoning_reports = {}
        bot_order = ["warchief", "aria", "lisa", "bloodhound",
                     "pathologist", "surgeon", "magician", "thief"]
        # Find the last non-warchief bot that ran
        last_bot = "warchief"
        for bot in reversed(bot_order):
            if bot in reasoning_reports and bot != "warchief":
                last_bot = bot
                break

        # Init phase — always start with recon
        if last_bot == "warchief" and not decision:
            return "aria"

        # v2.1: Scope expansion gate — if bots discovered out-of-scope targets,
        # route to scope_expansion before proceeding with the actual routing.
        # The scope_expansion node presents candidates to the user, then routes
        # back to warchief for the real routing decision.
        candidates = state.get("scope_expansion_candidates", [])
        if isinstance(candidates, list) and candidates:
            # Check if there are any candidates not already approved
            approved = set(state.get("approved_extra_targets", []))
            new_candidates = [c for c in candidates
                              if isinstance(c, dict) and c.get("target") not in approved]
            if new_candidates:
                return "scope_expansion"

        # v2 Phase 4: Graceful abort — 3+ decision cycles with no forward progress
        # Only applies to exploitation/post-exploit phases. Recon and scan have
        # their own _check_loop_limit guards — WarChief can wake multiple times
        # before a bot actually runs, causing false positives on "scan"/"recon".
        history = state.get("decision_history", [])
        if isinstance(history, list) and len(history) >= 3:
            # Check last 3 decisions — if all the same and not making progress
            last_3 = history[-3:]
            decisions_3 = [h.get("decision", "") for h in last_3 if isinstance(h, dict)]
            if len(decisions_3) == 3 and len(set(decisions_3)) == 1:
                stuck_decision = decisions_3[0]
                # Only force abort for exploitation/post-exploit stuck decisions
                # recon/scan loopback is legitimate and guarded by _check_loop_limit
                if stuck_decision in ("exploit", "privesc", "exfil",
                                      "vulns_found_exploit", "continue_exploit"):
                    print(f"[NO PROGRESS] Same decision '{stuck_decision}' 3 times — forcing abort to report")
                    return "bookkeeper"

        # Explicit report/abort — always go to bookkeeper
        if decision in ("report", "insufficient_data_abort"):
            return "bookkeeper"

        # Lateral movement — always through approval gate
        if decision in ("lateral_recon", "lateral_scan"):
            return "lateral_approval"

        # Phase-specific routing based on last bot that actually ran
        bot_routers = {
            "aria": route_after_recon,
            "lisa": route_after_scan,
            "bloodhound": route_after_vuln,
            "pathologist": route_after_exploit,
            "surgeon": route_after_exploit,
            "magician": route_after_privesc,
            "thief": lambda s: "bookkeeper",
        }

        router_fn = bot_routers.get(last_bot)
        if router_fn:
            return router_fn(state)

        # Unknown last_bot — try forward progress based on decision
        print(f"[ROUTING] Unknown last_bot '{last_bot}' with decision '{decision}' — trying forward progress")
        forward_map = {
            "recon": "aria",
            "scan": "lisa",
            "vuln_detection": "bloodhound",
            "vulns_found_exploit": "human_approval",
            "continue_exploit": "surgeon",
            "privesc": "magician",
            "exfiltrate": "thief",
        }
        return forward_map.get(decision, "bookkeeper")

    except Exception as e:
        print(f"[ROUTING ERROR] _unified_router: {e} — defaulting to bookkeeper")
        return "bookkeeper"


# ─── Graph builder ───

def create_swarm_graph(swarm_config: Optional[Dict[str, Any]] = None,
                       auto_approve: bool = False) -> StateGraph:
    """Build the v2 adaptive LangGraph state machine.

    WarChief re-enters after each phase as a decision router.
    All nodes have exception handling — degrade to Bookkeeper on failure.
    """

    workflow = StateGraph(SwarmState)

    # ─── Node functions ───

    async def warchief_node(state: SwarmState) -> SwarmState:
        """WarChief — orchestrator and decision router.

        On failure: sets last_decision to 'report' (safe route to Bookkeeper).
        """
        try:
            bot = WarChief(state, swarm_config)
            await bot.run()
        except Exception as e:
            print(f"[WARCHELF ERROR] {e} — setting safe fallback route")
            try:
                state["last_decision"] = "report"
                _log_error(state, "WARCHELF", e)
            except Exception:
                pass
        return state

    async def aria_node(state: SwarmState) -> SwarmState:
        """ARIA — passive reconnaissance. On failure: WarChief reroutes."""
        try:
            _increment_loop(state, "recon")
            bot = ARIA(state, swarm_config)
            await bot.run()
        except Exception as e:
            print(f"[ARIA ERROR] {e}")
            _log_error(state, "ARIA", e)
        return state

    async def lisa_node(state: SwarmState) -> SwarmState:
        """Lisa — active scanning. On failure: WarChief reroutes."""
        try:
            _increment_loop(state, "scan")
            bot = Lisa(state, swarm_config)
            await bot.run()
        except Exception as e:
            print(f"[LISA ERROR] {e}")
            _log_error(state, "LISA", e)
        return state

    async def bloodhound_node(state: SwarmState) -> SwarmState:
        """Bloodhound — vulnerability detection. Runs Wasp in parallel."""
        try:
            _increment_loop(state, "vuln")
            bot = Bloodhound(state, swarm_config)
            wasp = Wasp(state, swarm_config)
            # Run both in parallel threads — bot.run() is async but has no
            # await points (all blocking LLM/subprocess calls are sync).
            # asyncio.gather alone would run them sequentially on the event
            # loop. asyncio.to_thread runs each in a real OS thread so they
            # truly execute in parallel.
            results = await asyncio.gather(
                asyncio.to_thread(lambda: asyncio.run(bot.run())),
                asyncio.to_thread(lambda: asyncio.run(wasp.run())),
                return_exceptions=True,
            )
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    bot_name = "bloodhound" if i == 0 else "wasp"
                    print(f"[{bot_name.upper()} ERROR] {result}")
                    import traceback
                    traceback.print_exc()
                    _log_error(state, bot_name.upper(), result)
        except Exception as e:
            print(f"[BLOODHOUND ERROR] {e}")
            import traceback
            traceback.print_exc()
            _log_error(state, "BLOODHOUND", e)
        return state

    def human_approval_node(state: SwarmState) -> SwarmState:
        """Human-in-loop gate. On EOFError/OSError: deny (fail safe)."""
        try:
            vuln_report = state.get("vuln_report", [])

            print("\n" + "=" * 60)
            print("HUMAN APPROVAL REQUIRED — EXPLOITATION PHASE GATE")
            print("=" * 60)
            print(f"Vulnerabilities found: {len(vuln_report)}")
            for i, vuln in enumerate(vuln_report, 1):
                if isinstance(vuln, dict):
                    print(f"  {i}. {vuln.get('cve', vuln.get('id', 'N/A'))} "
                          f"(CVSS: {vuln.get('cvss', vuln.get('severity', 'N/A'))}) "
                          f"on {vuln.get('host', vuln.get('target', 'N/A'))}")
                else:
                    print(f"  {i}. {vuln}")
            print("=" * 60)

            if not vuln_report:
                print("No vulnerabilities cataloged by Bloodhound.")
                if auto_approve:
                    print("Proceeding with exploitation phase anyway (--approve flag)")
                    state["human_approval"] = True
                    return state
                print("Skipping exploitation phase.")
                state["human_approval"] = False
                return state

            if auto_approve:
                print("\nExploitation AUTO-APPROVED (--approve flag)\n")
                state["human_approval"] = True
                return state

            try:
                response = input("\nProceed with exploitation? (y/n): ").strip().lower()
            except (EOFError, OSError):
                response = "n"
            if response == "y":
                print("\nExploitation APPROVED — proceeding\n")
                state["human_approval"] = True
            else:
                print("\nExploitation DENIED — skipping to final report\n")
                state["human_approval"] = False
        except Exception as e:
            print(f"[HUMAN APPROVAL ERROR] {e} — defaulting to deny")
            state["human_approval"] = False
        return state

    def lateral_approval_node(state: SwarmState) -> SwarmState:
        """Lateral movement gate. On EOFError/OSError: deny (fail safe)."""
        try:
            last_decision = state.get("last_decision", "")

            if not last_decision.startswith("lateral"):
                state["lateral_approval"] = True
                return state

            print("\n" + "=" * 60)
            print("LATERAL MOVEMENT APPROVAL REQUIRED — PIVOT GATE")
            print("=" * 60)
            print(f"WarChief decision: {last_decision}")
            print("This will redirect the swarm to newly-discovered internal targets.")
            print("External scope and internal scope are separate authorizations.")
            print("=" * 60)

            if auto_approve:
                print("\nLateral movement AUTO-APPROVED (--approve flag)\n")
                state["lateral_approval"] = True
                return state

            try:
                response = input("\nApprove lateral movement to internal targets? (y/n): ").strip().lower()
            except (EOFError, OSError):
                response = "n"

            if response == "y":
                print("\nLateral movement APPROVED — proceeding\n")
                state["lateral_approval"] = True
            else:
                print("\nLateral movement DENIED — routing to final report\n")
                state["lateral_approval"] = False
        except Exception as e:
            print(f"[LATERAL APPROVAL ERROR] {e} — defaulting to deny")
            state["lateral_approval"] = False
        return state

    def scope_expansion_node(state: SwarmState) -> SwarmState:
        """v2.1: Scope expansion gate — debrief user about out-of-scope targets.

        When bots discover targets outside the mission scope (e.g., third-party
        dependencies like Prismic CMS), WarChief collects them and presents a
        debrief to the user. The user decides which targets to add to scope.

        On auto_approve: all candidates are added silently.
        On EOFError/OSError: no candidates added (fail safe).
        """
        try:
            candidates = state.get("scope_expansion_candidates", [])
            if not candidates:
                return state

            # Filter out already-approved targets
            approved = set(state.get("approved_extra_targets", []))
            new_candidates = [c for c in candidates
                              if isinstance(c, dict) and c.get("target") not in approved]
            if not new_candidates:
                return state

            print("\n" + "=" * 60)
            print("SCOPE EXPANSION REQUEST — NEW TARGETS DISCOVERED")
            print("=" * 60)
            print(f"WarChief discovered {len(new_candidates)} target(s) outside the")
            print("current mission scope during the engagement.")
            print()
            for i, c in enumerate(new_candidates, 1):
                target = c.get("target", "?")
                found_by = c.get("found_by", "?")
                reason = c.get("reason", "")
                # Truncate reason for display
                if len(reason) > 100:
                    reason = reason[:100] + "..."
                print(f"  {i}. {target}")
                print(f"     Found by: {found_by}")
                print(f"     Reason: {reason}")
                print()

            if auto_approve:
                print("AUTO-APPROVED (--approve flag) — adding all candidates to scope\n")
                for c in new_candidates:
                    target = c.get("target", "")
                    if target and target not in approved:
                        approved.add(target)
                state["approved_extra_targets"] = list(approved)
                # Clear candidates after processing
                state["scope_expansion_candidates"] = []
                return state

            print("Options:")
            print("  - Type a number (e.g., '1') to approve that target")
            print("  - Type 'all' to approve all targets")
            print("  - Type 'none' or press Enter to reject all")
            print("=" * 60)

            try:
                response = input("\nAdd which targets to scope? ").strip().lower()
            except (EOFError, OSError):
                response = "none"

            if response == "none" or response == "":
                print("\nNo targets added to scope.\n")
            elif response == "all":
                print("\nAll targets APPROVED — adding to scope\n")
                for c in new_candidates:
                    target = c.get("target", "")
                    if target and target not in approved:
                        approved.add(target)
            else:
                # Parse comma-separated numbers
                approved_any = False
                for part in response.split(","):
                    part = part.strip()
                    try:
                        idx = int(part) - 1
                        if 0 <= idx < len(new_candidates):
                            target = new_candidates[idx].get("target", "")
                            if target and target not in approved:
                                approved.add(target)
                                approved_any = True
                                print(f"  APPROVED: {target}")
                    except ValueError:
                        pass
                if approved_any:
                    print("\nSelected targets added to scope.\n")
                else:
                    print("\nNo valid selections — no targets added.\n")

            state["approved_extra_targets"] = list(approved)
            # Clear candidates after processing
            state["scope_expansion_candidates"] = []
        except Exception as e:
            print(f"[SCOPE EXPANSION ERROR] {e} — no targets added")
        return state

    async def pathologist_node(state: SwarmState) -> SwarmState:
        """Pathologist — payload fabrication. On failure: logged, graph continues."""
        try:
            bot = Pathologist(state, swarm_config)
            await bot.run()
        except Exception as e:
            print(f"[PATHOLOGIST ERROR] {e}")
            _log_error(state, "PATHOLOGIST", e)
        return state

    async def surgeon_node(state: SwarmState) -> SwarmState:
        """Surgeon — exploitation. On failure: WarChief reroutes."""
        try:
            bot = Surgeon(state, swarm_config)
            await bot.run()
        except Exception as e:
            print(f"[SURGEON ERROR] {e}")
            _log_error(state, "SURGEON", e)
        return state

    async def magician_node(state: SwarmState) -> SwarmState:
        """Magician — privilege escalation. On failure: WarChief reroutes."""
        try:
            bot = Magician(state, swarm_config)
            await bot.run()
        except Exception as e:
            print(f"[MAGICIAN ERROR] {e}")
            _log_error(state, "MAGICIAN", e)
        return state

    async def thief_node(state: SwarmState) -> SwarmState:
        """Thief — data exfiltration. On failure: WarChief reroutes."""
        try:
            bot = Thief(state, swarm_config)
            await bot.run()
        except Exception as e:
            print(f"[THIEF ERROR] {e}")
            _log_error(state, "THIEF", e)
        return state

    async def bookkeeper_node(state: SwarmState) -> SwarmState:
        """Bookkeeper — report generation.

        On failure: writes a minimal error report so engagement isn't empty.
        """
        try:
            bot = Bookkeeper(state, swarm_config)
            await bot.run()
        except Exception as e:
            print(f"[BOOKKEEPER ERROR] {e} — report generation failed")
            try:
                eng_dir = state.get("engagement_dir", "")
                if eng_dir:
                    from pathlib import Path
                    from datetime import datetime
                    report_dir = Path(eng_dir) / "report"
                    report_dir.mkdir(parents=True, exist_ok=True)
                    error_report = (
                        f"# Penetration Test Report — Generation Failed\n\n"
                        f"**Error**: {e}\n\n"
                        f"**Timestamp**: {datetime.utcnow().isoformat()}\n\n"
                        f"The automated report generator encountered an error.\n"
                        f"Check engagement files in {eng_dir} for raw findings.\n"
                    )
                    (report_dir / "final_report.md").write_text(error_report)
                    state["final_report"] = {
                        "generated_at": datetime.utcnow().isoformat(),
                        "error": str(e),
                        "report": error_report,
                    }
            except Exception:
                print("[BOOKKEEPER] Could not write error report")
        return state

    # ─── Add all nodes ───
    workflow.add_node("warchief", warchief_node)
    workflow.add_node("aria", aria_node)
    workflow.add_node("lisa", lisa_node)
    workflow.add_node("bloodhound", bloodhound_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("lateral_approval", lateral_approval_node)
    workflow.add_node("scope_expansion", scope_expansion_node)
    workflow.add_node("pathologist", pathologist_node)
    workflow.add_node("surgeon", surgeon_node)
    workflow.add_node("magician", magician_node)
    workflow.add_node("thief", thief_node)
    workflow.add_node("bookkeeper", bookkeeper_node)

    # ─── Edges: Adaptive routing ───

    # Entry: WarChief (init planning)
    workflow.set_entry_point("warchief")

    # All phase bots → WarChief (re-enter for routing)
    workflow.add_edge("aria", "warchief")
    workflow.add_edge("lisa", "warchief")
    workflow.add_edge("bloodhound", "warchief")
    workflow.add_edge("surgeon", "warchief")
    workflow.add_edge("magician", "warchief")
    workflow.add_edge("thief", "warchief")

    # WarChief → unified conditional router (one edge, all destinations)
    workflow.add_conditional_edges(
        "warchief",
        _unified_router,
        {
            "aria": "aria",
            "lisa": "lisa",
            "bloodhound": "bloodhound",
            "human_approval": "human_approval",
            "pathologist": "pathologist",
            "surgeon": "surgeon",
            "magician": "magician",
            "thief": "thief",
            "lateral_approval": "lateral_approval",
            "scope_expansion": "scope_expansion",
            "bookkeeper": "bookkeeper",
        },
    )

    # Scope expansion → back to WarChief (after user decision, WarChief routes normally)
    workflow.add_edge("scope_expansion", "warchief")

    # Human approval → Pathologist (approved) or Bookkeeper (denied)
    workflow.add_conditional_edges(
        "human_approval",
        lambda state: "pathologist" if state.get("human_approval") else "bookkeeper",
        {"pathologist": "pathologist", "bookkeeper": "bookkeeper"},
    )

    # Pathologist → Surgeon (linear within exploitation phase)
    workflow.add_edge("pathologist", "surgeon")

    # Lateral approval → conditional (approved: ARIA/Lisa, denied: Bookkeeper)
    workflow.add_conditional_edges(
        "lateral_approval",
        route_after_lateral_approval,
        {
            "aria": "aria",
            "lisa": "lisa",
            "bookkeeper": "bookkeeper",
        },
    )

    # Bookkeeper → END
    workflow.add_edge("bookkeeper", END)

    return workflow


def compile_graph(swarm_config: Optional[Dict[str, Any]] = None,
                  auto_approve: bool = False):
    """Compile the v2 adaptive LangGraph workflow."""
    graph = create_swarm_graph(swarm_config, auto_approve)
    return graph.compile()