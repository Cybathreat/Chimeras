"""
Chimeras v2.0 — Shared State Schema
TypedDict for LangGraph state management.

v2 additions (Phase -1):
  - last_decision: WarChief's latest routing decision (str)
  - loop_count: Per-phase loop counter dict (Dict[str, int])
  - discovered_targets: All targets found during engagement (Set[str])
  - external_targets: Initial scope targets (Set[str])
  - internal_targets: Lateral-discovered targets (Set[str])
  - exploited_hosts: Hosts with confirmed access (Set[str])
  - target_context: "external" or "lateral" — which scope we're in (str)
  - target_artifacts: Artifacts left on target — tracked for cleanup (List[Dict])
  - lateral_approval: Second human gate for lateral movement (bool)
  - aggressiveness: Scan intensity level — "cautious" default (str)
  - failed_vectors: Failed attack attempts (List[Dict])
  - max_loops_per_phase: Safety limit per phase (int, default 5)
"""

from typing import TypedDict, List, Dict, Any, Optional, Set


class SwarmState(TypedDict, total=False):
    """Shared state schema. All fields optional for incremental building."""

    # ─── Mission definition ───
    mission: Dict[str, Any]

    # ─── Configuration ───
    swarm_config: Dict[str, Any]

    # ─── Engagement folder path ───
    engagement_dir: str

    # ─── Reasoning outputs from all bots ───
    reasoning_reports: Dict[str, Dict[str, Any]]

    # ─── ARIA's passive reconnaissance findings ───
    recon_report: Dict[str, Any]

    # ─── Lisa's scan results ───
    scan_report: Dict[str, Any]

    # ─── Bloodhound's vulnerability findings ───
    vuln_report: List[Dict[str, Any]]

    # ─── Active exploitation sessions ───
    active_sessions: List[Dict[str, Any]]

    # ─── Pathologist's payload manifest ───
    payloads: List[Dict[str, Any]]

    # ─── Thief's exfiltration report ───
    exfil_report: Dict[str, Any]

    # ─── Magician's privilege escalation and lateral movement ───
    movement_report: Dict[str, Any]

    # ─── Operation ledger ───
    operation_ledger: List[Dict[str, Any]]

    # ─── Human-in-loop approval flags ───
    human_approval: bool          # Exploitation gate
    lateral_approval: bool        # Lateral movement gate (v2 Phase -1)

    # ─── Emergency stop flag ───
    abort_flag: bool

    # ─── Final report ───
    final_report: Dict[str, Any]

    # ─── v2: WarChief adaptive routing ───
    # WarChief's last routing decision: "recon" | "scan" | "vulns_found_exploit"
    # | "insufficient_data_abort" | "lateral_recon" | "lateral_scan" | "report"
    last_decision: str

    # Per-phase loop counter: {"recon": 0, "scan": 0, "vuln": 0, ...}
    # Prevents infinite loops. Max 5 cycles per phase before forced abort.
    loop_count: Dict[str, int]

    # Maximum loops allowed per phase before graceful abort
    max_loops_per_phase: int

    # ─── v2: Target tracking ───
    # All unique targets discovered during the engagement
    discovered_targets: List[str]

    # Initial external scope targets (from mission scope)
    external_targets: List[str]

    # Internally-discovered targets (from lateral movement)
    internal_targets: List[str]

    # Hosts with confirmed access (post-exploitation)
    exploited_hosts: List[str]

    # Current scope context: "external" or "lateral"
    # Determines which backtracking rule applies (Phase 2)
    target_context: str

    # ─── v2: Artifact tracking (for Phase 4.5 cleanup) ───
    # List of {host, artifact_type, path, cleaned: bool}
    target_artifacts: List[Dict[str, Any]]

    # ─── v2: Failure tracking (for Phase 4 resilience) ───
    # List of {target, tool, error, timestamp}
    failed_vectors: List[Dict[str, Any]]

    # ─── v2: Aggressiveness calibration ───
    # "cautious" (default) | "normal" | "passive_only"
    # WarChief can downgrade based on target response (WAF detection, etc.)
    # Lisa/Bloodhound honor this by adjusting tool flags
    aggressiveness: str