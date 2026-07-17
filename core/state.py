"""
Chimeras v1.0 — Shared State Schema
TypedDict for LangGraph state management.
"""

from typing import TypedDict, List, Dict, Any, Optional


class SwarmState(TypedDict, total=False):
    """Shared state schema. All fields optional for incremental building."""

    # Mission definition
    mission: Dict[str, Any]

    # Configuration
    swarm_config: Dict[str, Any]

    # Engagement folder path
    engagement_dir: str

    # Reasoning outputs from all bots
    reasoning_reports: Dict[str, Dict[str, Any]]

    # ARIA's passive reconnaissance findings
    recon_report: Dict[str, Any]

    # Lisa's scan results
    scan_report: Dict[str, Any]

    # Bloodhound's vulnerability findings
    vuln_report: List[Dict[str, Any]]

    # Active exploitation sessions
    active_sessions: List[Dict[str, Any]]

    # Pathologist's payload manifest
    payloads: List[Dict[str, Any]]

    # Thief's exfiltration report
    exfil_report: Dict[str, Any]

    # Magician's privilege escalation and lateral movement
    movement_report: Dict[str, Any]

    # Operation ledger
    operation_ledger: List[Dict[str, Any]]

    # Human-in-loop approval flag
    human_approval: bool

    # Emergency stop flag
    abort_flag: bool

    # Final report
    final_report: Dict[str, Any]