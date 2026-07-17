"""
Chimeras v1.0 — LangGraph Graph Wiring

Linear flow with human-in-loop gate at exploitation.
WarChief → ARIA → Lisa → Bloodhound → [HUMAN APPROVAL]
→ Pathologist → Surgeon → Magician → Thief → Bookkeeper → END
"""

from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END

from core.state import SwarmState
from warchief.agent import WarChief
from aria.agent import ARIA
from lisa.agent import Lisa
from bloodhound.agent import Bloodhound
from surgeon.agent import Surgeon
from pathologist.agent import Pathologist
from thief.agent import Thief
from magician.agent import Magician
from bookkeeper.agent import Bookkeeper


def create_swarm_graph(swarm_config: Optional[Dict[str, Any]] = None,
                       auto_approve: bool = False) -> StateGraph:
    """Build the LangGraph state machine."""

    workflow = StateGraph(SwarmState)

    # ─── Node functions ───

    async def warchief_node(state: SwarmState) -> SwarmState:
        bot = WarChief(state, swarm_config)
        result = await bot.run()
        return state

    async def aria_node(state: SwarmState) -> SwarmState:
        bot = ARIA(state, swarm_config)
        result = await bot.run()
        return state

    async def lisa_node(state: SwarmState) -> SwarmState:
        bot = Lisa(state, swarm_config)
        result = await bot.run()
        return state

    async def bloodhound_node(state: SwarmState) -> SwarmState:
        bot = Bloodhound(state, swarm_config)
        result = await bot.run()
        return state

    def human_approval_node(state: SwarmState) -> SwarmState:
        """Human-in-loop gate. Presents findings, waits for y/n."""
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
        return state

    async def pathologist_node(state: SwarmState) -> SwarmState:
        bot = Pathologist(state, swarm_config)
        result = await bot.run()
        return state

    async def surgeon_node(state: SwarmState) -> SwarmState:
        bot = Surgeon(state, swarm_config)
        result = await bot.run()
        return state

    async def magician_node(state: SwarmState) -> SwarmState:
        bot = Magician(state, swarm_config)
        result = await bot.run()
        return state

    async def thief_node(state: SwarmState) -> SwarmState:
        bot = Thief(state, swarm_config)
        result = await bot.run()
        return state

    async def bookkeeper_node(state: SwarmState) -> SwarmState:
        bot = Bookkeeper(state, swarm_config)
        result = await bot.run()
        return state

    # ─── Add nodes ───
    workflow.add_node("warchief", warchief_node)
    workflow.add_node("aria", aria_node)
    workflow.add_node("lisa", lisa_node)
    workflow.add_node("bloodhound", bloodhound_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("pathologist", pathologist_node)
    workflow.add_node("surgeon", surgeon_node)
    workflow.add_node("magician", magician_node)
    workflow.add_node("thief", thief_node)
    workflow.add_node("bookkeeper", bookkeeper_node)

    # ─── Edges ───
    workflow.set_entry_point("warchief")
    workflow.add_edge("warchief", "aria")
    workflow.add_edge("aria", "lisa")
    workflow.add_edge("lisa", "bloodhound")
    workflow.add_edge("bloodhound", "human_approval")

    # Human Approval → Pathologist (if approved) or Bookkeeper (if denied)
    workflow.add_conditional_edges(
        "human_approval",
        lambda state: "pathologist" if state.get("human_approval") else "bookkeeper",
        {"pathologist": "pathologist", "bookkeeper": "bookkeeper"},
    )

    workflow.add_edge("pathologist", "surgeon")
    workflow.add_edge("surgeon", "magician")
    workflow.add_edge("magician", "thief")
    workflow.add_edge("thief", "bookkeeper")
    workflow.add_edge("bookkeeper", END)

    return workflow


def compile_graph(swarm_config: Optional[Dict[str, Any]] = None,
                  auto_approve: bool = False):
    """Compile the LangGraph workflow."""
    graph = create_swarm_graph(swarm_config, auto_approve)
    return graph.compile()