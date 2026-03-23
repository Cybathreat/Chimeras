"""
SwarmBots v2.0 — LangGraph Graph Wiring

Multi-agent orchestration with human-in-loop interrupt at exploitation phase.
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import interrupt

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


def create_swarm_graph(swarm_config: Optional[Dict[str, Any]] = None) -> StateGraph:
    """
    Build the LangGraph state machine for the SwarmBots multi-agent system.
    
    Graph flow:
    WarChief → ARIA → Lisa → Bloodhound → [HUMAN APPROVAL]
      → Pathologist (on demand) → Surgeon → Magician + Thief (parallel)
      → Bookkeeper (always running, first spawned, last killed)
    """
    
    # Initialize state graph with SwarmState schema
    workflow = StateGraph(SwarmState)
    
    # Define node functions
    async def warchief_node(state: SwarmState) -> SwarmState:
        bot = WarChief(state, swarm_config)
        result = await bot.run()
        state["reasoning_reports"]["warchief"] = result.get("reasoning", {})
        return state
    
    async def aria_node(state: SwarmState) -> SwarmState:
        bot = ARIA(state, swarm_config)
        result = await bot.run()
        state["reasoning_reports"]["aria"] = result.get("reasoning", {})
        if result.get("execution"):
            state["recon_report"] = result["execution"]
        return state
    
    async def lisa_node(state: SwarmState) -> SwarmState:
        bot = Lisa(state, swarm_config)
        result = await bot.run()
        state["reasoning_reports"]["lisa"] = result.get("reasoning", {})
        if result.get("execution"):
            state["scan_report"] = result["execution"]
        return state
    
    async def bloodhound_node(state: SwarmState) -> SwarmState:
        bot = Bloodhound(state, swarm_config)
        result = await bot.run()
        state["reasoning_reports"]["bloodhound"] = result.get("reasoning", {})
        if result.get("execution"):
            state["vuln_report"] = result["execution"].get("vulnerabilities", [])
        return state
    
    def human_approval_node(state: SwarmState) -> SwarmState:
        """
        Human-in-loop interrupt: pause graph, present Bloodhound report,
        wait for explicit approval before exploitation.
        """
        vuln_report = state.get("vuln_report", [])
        
        # Present findings to human operator
        print("\n" + "="*60)
        print("HUMAN APPROVAL REQUIRED - EXPLOITATION PHASE GATE")
        print("="*60)
        print(f"Vulnerabilities found: {len(vuln_report)}")
        for vuln in vuln_report:
            print(f"  - {vuln.get('cve')} (CVSS: {vuln.get('cvss')}) on {vuln.get('host')}")
        print("="*60)
        print("Proceed with exploitation? (y/n)")
        
        # LangGraph interrupt - pauses execution
        # In production, this would be a proper interrupt() call with UI
        # For MVP, we check state flag set by external UI
        if not state.get("human_approval", False):
            print("Exploitation BLOCKED - awaiting approval")
            return state
        
        print("Exploitation APPROVED - proceeding")
        state["human_approval"] = True
        return state
    
    async def pathologist_node(state: SwarmState) -> SwarmState:
        bot = Pathologist(state, swarm_config)
        result = await bot.run()
        state["reasoning_reports"]["pathologist"] = result.get("reasoning", {})
        if result.get("execution"):
            state["payloads"] = result["execution"].get("payloads_generated", [])
        return state
    
    async def surgeon_node(state: SwarmState) -> SwarmState:
        bot = Surgeon(state, swarm_config)
        result = await bot.run()
        state["reasoning_reports"]["surgeon"] = result.get("reasoning", {})
        if result.get("execution"):
            state["active_sessions"] = result["execution"].get("sessions_established", [])
        return state
    
    async def magician_node(state: SwarmState) -> SwarmState:
        bot = Magician(state, swarm_config)
        result = await bot.run()
        state["reasoning_reports"]["magician"] = result.get("reasoning", {})
        if result.get("execution"):
            state["movement_report"] = result["execution"]
        return state
    
    async def thief_node(state: SwarmState) -> SwarmState:
        bot = Thief(state, swarm_config)
        result = await bot.run()
        state["reasoning_reports"]["thief"] = result.get("reasoning", {})
        if result.get("execution"):
            state["exfil_report"] = result["execution"]
        return state
    
    async def bookkeeper_node(state: SwarmState) -> SwarmState:
        bot = Bookkeeper(state, swarm_config)
        result = await bot.run()
        state["reasoning_reports"]["bookkeeper"] = result.get("reasoning", {})
        if result.get("execution"):
            state["final_report"] = result["execution"]
        return state
    
    # Add all nodes to graph
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
    
    # Define edges (graph flow)
    # WarChief always starts, then ARIA
    workflow.set_entry_point("warchief")
    workflow.add_edge("warchief", "aria")
    
    # ARIA → Lisa (always, even if recon not needed)
    workflow.add_edge("aria", "lisa")
    
    # Lisa → Bloodhound (always)
    workflow.add_edge("lisa", "bloodhound")
    
    # Bloodhound → Human Approval (hard gate)
    workflow.add_edge("bloodhound", "human_approval")
    
    # Human Approval → Surgeon (only if approved)
    # Conditional edge handled in human_approval_node
    workflow.add_conditional_edges(
        "human_approval",
        lambda state: "surgeon" if state.get("human_approval") else "bookkeeper_final",
        {"surgeon": "surgeon", "bookkeeper_final": "bookkeeper"}
    )
    
    # Surgeon → Magician + Thief (parallel)
    workflow.add_edge("surgeon", "magician")
    workflow.add_edge("surgeon", "thief")
    
    # Magician + Thief → WarChief (both must complete)
    workflow.add_edge("magician", "warchief")
    workflow.add_edge("thief", "warchief")
    
    # WarChief → Bookkeeper (final report)
    workflow.add_conditional_edges(
        "warchief",
        lambda state: "bookkeeper" if state.get("reasoning_reports", {}).get("thief") else "warchief",
        {"bookkeeper": "bookkeeper", "warchief": "warchief"}
    )
    
    # Bookkeeper → END (operation complete)
    workflow.add_edge("bookkeeper", END)
    
    return workflow


def compile_graph(swarm_config: Optional[Dict[str, Any]] = None):
    """Compile the LangGraph workflow."""
    graph = create_swarm_graph(swarm_config)
    return graph.compile()
