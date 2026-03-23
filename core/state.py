"""
SwarmBots v2.0 — Shared State Schema

TypedDict definition for LangGraph state management.
All bots communicate exclusively through this shared state.
"""

from typing import TypedDict, List, Dict, Any, Optional


class SwarmState(TypedDict, total=False):
    """
    Shared state schema for the SwarmBots multi-agent system.
    
    Every field is optional (total=False) to allow incremental building.
    """
    
    # Mission definition
    mission: Dict[str, Any]  # objectives, scope, RoE, emergency contacts
    
    # Configuration loaded from swarm-config.json
    swarm_config: Dict[str, Any]  # per-bot LLM provider and model assignments
    
    # Reasoning outputs from all bots
    reasoning_reports: Dict[str, Dict[str, Any]]  # bot_name -> {reasoning, strategy, decision}
    
    # ARIA's passive reconnaissance findings
    recon_report: Dict[str, Any]  # OSINT data, domain info, employee data, tech stack
    
    # Lisa's scan results
    scan_report: Dict[str, Any]  # ports, services, OS, versions, banners
    
    # Bloodhound's vulnerability findings
    vuln_report: List[Dict[str, Any]]  # list of {cve, cvss, evidence, target, recommendation}
    
    # Active exploitation sessions
    active_sessions: List[Dict[str, Any]]  # {session_id, target, shell_type, user, timestamp}
    
    # Pathologist's payload manifest
    payloads: List[Dict[str, Any]]  # {payload_id, type, hash, delivery_method, target}
    
    # Thief's exfiltration report
    exfil_report: Dict[str, Any]  # {data_exposed, channels_used, evidence_paths}
    
    # Magician's privilege escalation and lateral movement
    movement_report: Dict[str, Any]  # {privilege_chain, lateral_path, compromised_hosts}
    
    # Bookkeeper's append-only action log
    operation_ledger: List[Dict[str, Any]]  # {timestamp, bot, action, details}
    
    # Human-in-loop approval flag for exploitation phase
    human_approval: bool  # True = proceed with exploitation, False = stop at recon/vuln
    
    # Emergency stop flag
    abort_flag: bool  # True = kill all active bots immediately
    
    # Final report (technical + executive)
    final_report: Dict[str, Any]  # {executive_summary, technical_findings, recommendations}
