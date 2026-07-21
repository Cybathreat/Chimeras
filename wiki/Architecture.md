# Architecture (v2)

## Overview

Chimeras v2 is a multi-agent AI penetration testing framework built on LangGraph with adaptive decision-making. WarChief acts as a decision router — re-entering after each phase to adapt the engagement based on actual findings. Each bot uses an LLM to decide which tools to run, executes real Kali Linux tools via subprocess, analyzes raw output with the LLM, and writes structured findings to engagement files.

## Core Design Principles

1. **WarChief is a decision router** — re-enters after each phase, 11 routing decisions, not a one-shot planner
2. **LLM is the brain** — no hardcoded fallback logic. Safe fallback only for malformed LLM output
3. **Real tool execution** — every tool runs via subprocess against real targets. No mock data
4. **3-tier scope enforcement** — category check → shell injection block → target validation
5. **File-based communication** — bots share state through engagement files only
6. **Provider-agnostic** — any LLM provider. Custom gateway support via `base_url`
7. **Two human-in-loop gates** — exploitation gate + lateral movement gate

## Adaptive Graph (v2)

```
                    ┌──────────┐
                    │ WarChief │ ◄── re-enters after each phase
                    │ (router) │
                    └────┬─────┘
                         │ conditional edge (11 routing decisions)
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     ┌─────────┐   ┌─────────┐   ┌────────────┐
     │  ARIA   │   │  Lisa   │   │ Bloodhound │
     │ (recon) │   │ (scan)  │   │  (vulns)   │
     └────┬────┘   └────┬────┘   └─────┬──────┘
          │              │              │
          └──────────────┴──────────────┘
                         │
                    ┌────▼─────┐
                    │HUMAN GATE│ ◄── exploitation approval
                    └────┬─────┘
                         │ (approved)
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   ┌───────────┐  ┌────────┐    ┌──────────┐
   │Pathologist│  │Surgeon │    │ Magician │
   │(payloads) │  │(exploit)│   │(privesc) │
   └───────────┘  └────────┘    └──────────┘
                                      │
                                ┌─────▼─────┐
                                │  Thief    │
                                │ (exfil)   │
                                └─────┬─────┘
                                      │
                                ┌─────▼──────┐
                                │Bookkeeper  │
                                │(report+    │
                                │ cleanup)   │
                                └────────────┘

  Loopback: WarChief can route back to ARIA/Lisa for deeper recon
  Lateral gate: second human approval before any internal pivot
  Abort: 3+ failed exploits or 5 loops per phase → Bookkeeper
```

### WarChief Routing Decisions (11)

| Decision | Routes To |
|----------|-----------|
| `recon` | ARIA |
| `scan` | Lisa |
| `vulns_found_exploit` | Human gate → exploitation chain |
| `insufficient_data_abort` | Bookkeeper |
| `lateral_recon` | Lateral gate → ARIA (internal) |
| `lateral_scan` | Lateral gate → Lisa (internal) |
| `pivot_lateral_recon` | Lateral gate → ARIA (full pivot) |
| `exploit` | Surgeon |
| `privesc` | Magician |
| `exfil` | Thief |
| `report` | Bookkeeper |

### Mission State Machine (11 states)

`init → recon → scanning → vuln_detection → exploitation_prep → exploitation → post_exploit → lateral_recon → lateral_scanning → reporting → complete`

### Loop Protection

- Max 5 cycles per phase (per-phase, not global)
- Exceeded → forced abort to Bookkeeper
- Graceful abort: 3+ failed exploits or 3 same decisions → Bookkeeper

## Bot Reasoning Loop

Every bot inherits from `BaseBot` and follows the same 6-step loop:

1. **Wake** — resolve engagement directory, read previous bot findings (rolling digest for context truncation)
2. **Think** — LLM analyzes context, decides what tools to run (or skip)
3. **Execute** — run real Kali tools via subprocess (3-tier scope enforced)
4. **Analyze** — LLM reads raw tool output, extracts structured findings
5. **Write** — bot file, findings.md, log.md, PoC files, artifact tracking
6. **Sleep** — state update, graph routes back to WarChief

## v2 State Schema

LangGraph shared state (`core/state.py`):

**v1 fields**: mission, swarm_config, reasoning_reports, recon_report, scan_report, vuln_report, active_sessions, payloads, exfil_report, movement_report, operation_ledger, human_approval, abort_flag, final_report

**v2 fields**:
- `warchief_decision` — last routing decision
- `warchief_fallback` — fallback mode flag
- `target_context` — "external" or "lateral"
- `external_targets` — external-facing hosts from initial scope
- `internal_targets` — internally-discovered hosts
- `exploited_hosts` — hosts with confirmed access
- `discovered_targets` — unique targets discovered
- `scope_exhausted` — scope exhaustion flag
- `mission_state` — current state in 11-state machine
- `decision_history` — rolling 5 last decisions
- `failed_vectors` — failed attempts: {target, tool, error}
- `target_artifacts` — artifacts on target: {host, type, path, cleaned}
- `aggressiveness` — normal / cautious / passive_only
- `loop_counts` — per-phase loop counters
- `lateral_approval` — lateral movement gate flag

## File Structure

```
mission/engagement/
├── plan.md                    # WarChief's plan + decision audit trail
├── log.md                     # Timestamped action log (all bots)
├── findings.md                # Accumulated findings (all bots)
├── warchief_decisions.json    # Machine-readable decision log (v2)
├── warchief.md                # Per-bot work logs
├── aria.md
├── lisa.md
├── bloodhound.md
├── pathologist.md
├── surgeon.md
├── magician.md
├── thief.md
├── bookkeeper.md
├── raw/                       # Raw tool output (audit trail)
├── poc/                       # Proof-of-concept artifacts
└── report/
    └── final_report.md        # Professional pentest report + cleanup status
```

## Graph Wiring

`graph.py` wires the adaptive LangGraph state machine:

- Entry point: `warchief`
- Conditional edges from WarChief based on `warchief_decision` in state
- Loopback paths: ARIA → WarChief → ARIA (deeper recon), Lisa → WarChief → Lisa (deeper scan)
- Two human gates: `human_approval_node` (exploitation) + `lateral_approval_node` (lateral movement)
- Every node wrapped in try/except — graph degrades gracefully
- `--approve` flag bypasses both gates for headless runs
- `--skip-wizard` flag bypasses TUI pre-flight for CI/headless