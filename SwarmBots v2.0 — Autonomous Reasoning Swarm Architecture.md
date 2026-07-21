# Chimeras v2.0 — Autonomous Adaptive Reasoning Swarm Architecture

**Cyberian Defenses** | Multi-Agent AI Security Testing Framework

---

## 1. Overview

Chimeras v2 is an autonomous AI hacking swarm for penetration testing with adaptive decision-making. 9 bots, each powered by an independently assigned LLM, each reasoning autonomously about what tools to run and what strategy to use. WarChief acts as a decision router — re-entering after each phase to adapt the engagement based on actual findings.

### What Changed in v2

- **WarChief is a decision router** — re-enters after each phase, 11 routing decisions, not a one-shot planner
- **Adaptive graph** — conditional edges, loopback paths for deeper recon/scanning
- **Lateral movement** — internal recon, lateral scan, lateral exploitation, gated by second human approval
- **Failure handling** — WAF detection, failed vector tracking, graceful abort
- **Scope enforcement at code level** — TargetValidator resolves IPs/hostnames, checks against CIDR
- **Shell injection blocked** — metacharacters rejected for non-shell categories
- **Artifact tracking & cleanup** — dropped tools tracked, removal attempted, failures flagged in report
- **Decision audit trail** — all routing decisions logged in report + JSON
- **TUI wizard** — Rich-based pre-flight with live LLM connectivity check
- **Config auto-migration** — v1 configs upgraded to v2 on load

### Stack
- Python 3.11+
- LangGraph (multi-agent orchestration, conditional edges, loopback paths)
- Rich (TUI pre-flight wizard)
- Provider-agnostic LLM routing (Anthropic/Google/Groq/OpenRouter/Ollama/OpenAI-compatible)
- Kali Linux tools executed via subprocess

---

## 2. Bot Roster

| Bot | Role | Tool Category |
|-----|------|---------------|
| WarChief | Decision router — re-enters after each phase | none |
| ARIA | Passive recon + lateral recon | passive_recon |
| Lisa | Active scanning + lateral scan | active_scan |
| Bloodhound | Vuln detection + WAF/IPS detection | vuln_detection |
| Pathologist | Payload fabrication | payload_fab |
| Surgeon | Exploitation + lateral exploitation | exploitation |
| Magician | Privesc + lateral movement | privesc |
| Thief | Data exfiltration | exfiltration |
| Bookkeeper | Report generation + cleanup/rollback | none |

### Fallback Chain
`groq` → `openrouter` → `ollama`

---

## 3. Adaptive Reasoning Loop

### WarChief Decision Router

WarChief re-enters the graph after each phase bot completes. It analyzes accumulated findings, makes a routing decision, and the graph follows a conditional edge to the next node.

**11 routing decisions**: `recon`, `scan`, `vulns_found_exploit`, `insufficient_data_abort`, `lateral_recon`, `lateral_scan`, `pivot_lateral_recon`, `exploit`, `privesc`, `exfil`, `report`

**11-state mission state machine**: `init → recon → scanning → vuln_detection → exploitation_prep → exploitation → post_exploit → lateral_recon → lateral_scanning → reporting → complete`

**Confidence threshold**: below 0.6 → override to safe conservative route based on current state

**Scope exhaustion**: 2+ recon cycles with zero new targets → forced report

**Backtracking rule**: no scan after shell in external scope; allowed in lateral scope

### Per-Bot Reasoning Loop (6 steps)

| # | Phase | Description |
|---|-------|-------------|
| 1 | Wake | Read engagement files from previous bots |
| 2 | Think | LLM analyzes context (with rolling digest for context truncation), decides strategy |
| 3 | Execute | Real Kali tools run via subprocess (3-tier scope enforced) |
| 4 | Analyze | LLM reads raw tool output, extracts structured findings |
| 5 | Write | Findings, logs, PoC, artifact tracking saved to engagement folder |
| 6 | Sleep | State update, graph routes back to WarChief |

---

## 4. v2 Shared State Schema

| Field | Type | Owner | Description |
|-------|------|-------|-------------|
| mission | dict | WarChief | Objectives, scope, RoE, target |
| swarm_config | dict | CLI Setup | Per-bot LLM provider and model assignments |
| reasoning_reports | dict[str] | All bots | Each bot's reasoning output and strategy decision |
| recon_report | dict | ARIA | Passive recon findings |
| scan_report | dict | Lisa | Port, service, OS enumeration data |
| vuln_report | list[dict] | Bloodhound | Scored and evidenced vulnerability findings |
| active_sessions | list[dict] | Surgeon/Magician | Live exploit sessions and footholds |
| payloads | list[dict] | Pathologist | Payload manifest, hashes, delivery instructions |
| exfil_report | dict | Thief | Exfil log and data exposure evidence |
| movement_report | dict | Magician | PrivEsc and lateral movement map |
| operation_ledger | list[dict] | Bookkeeper | Append-only timestamped action log |
| human_approval | bool | Human-in-Loop | Exploitation phase gate flag |
| lateral_approval | bool | Human-in-Loop | Lateral movement gate flag (v2) |
| abort_flag | bool | WarChief | Emergency stop, kills all active bots |
| final_report | dict | Bookkeeper | Technical + executive final report |
| warchief_decision | str | WarChief | Last routing decision (v2) |
| warchief_fallback | bool | WarChief | Whether WarChief is in fallback mode (v2) |
| target_context | str | WarChief | "external" or "lateral" (v2) |
| external_targets | list[str] | WarChief | External-facing hosts from initial scope (v2) |
| internal_targets | list[str] | ARIA/Lisa | Internally-discovered hosts (v2) |
| exploited_hosts | list[str] | Surgeon | Hosts with confirmed access (v2) |
| discovered_targets | list[str] | ARIA | Unique targets discovered (v2) |
| scope_exhausted | bool | WarChief | Scope exhaustion flag (v2) |
| mission_state | str | WarChief | Current state in 11-state machine (v2) |
| decision_history | list[dict] | WarChief | Rolling 5 last decisions (v2) |
| failed_vectors | list[dict] | Bloodhound/Surgeon/Thief | Failed attempts: {target, tool, error} (v2) |
| target_artifacts | list[dict] | Surgeon/Magician/Thief | Artifacts left on target: {host, type, path, cleaned} (v2) |
| aggressiveness | str | WarChief | normal / cautious / passive_only (v2) |
| loop_counts | dict | Graph | Per-phase loop counters (v2) |

---

## 5. v2 LangGraph Graph Design

### Nodes
- warchief_node — decision router, re-enters after each phase
- aria_node — passive recon + lateral recon
- lisa_node — active scanning + lateral scan
- bloodhound_node — vuln detection + WAF/IPS detection
- human_approval_node — exploitation gate (interrupt)
- lateral_approval_node — lateral movement gate (interrupt) (v2)
- pathologist_node — payload fabrication
- surgeon_node — exploitation + lateral exploitation
- magician_node — privesc + lateral movement
- thief_node — exfiltration
- bookkeeper_node — report generation + cleanup/rollback

### Conditional Edges
WarChief is the decision router. After each phase bot, the graph routes back to WarChief, which produces a decision. A routing function maps the decision to the next node:

- WarChief → ARIA (recon)
- WarChief → Lisa (scan)
- WarChief → Bloodhound (vulns)
- WarChief → human_approval (vulns_found_exploit)
- WarChief → lateral_approval → ARIA (pivot_lateral_recon)
- WarChief → Surgeon (exploit)
- WarChief → Magician (privesc)
- WarChief → Thief (exfil)
- WarChief → Bookkeeper (report / insufficient_data_abort)

### Loop Protection
- Max 5 cycles per phase (per-phase, not global)
- Exceeded → forced abort to Bookkeeper
- Graceful abort: 3+ failed exploits or 3 same decisions → Bookkeeper

### Human-in-the-Loop (Two Gates)
1. **Exploitation gate**: after Bloodhound, before any exploitation bot
2. **Lateral movement gate**: before any internal/lateral pivot (v2)

`--approve` flag bypasses both gates for headless runs.

---

## 6. v2 Failure Handling

- **WAF/IPS detection**: Bloodhound detects 403 rates, rate limiting, honeypots. WarChief downgrades aggressiveness.
- **Failed vector tracking**: Bloodhound, Surgeon, Thief track failed attempts in `failed_vectors`.
- **Graceful abort**: 3+ failed exploits or 3 same decisions → WarChief routes to Bookkeeper with abort reason.
- **Aggressiveness calibration**: `normal` → `cautious` → `passive_only`. Default: `cautious`.

---

## 7. v2 Cleanup & Rollback

- Surgeon, Magician, Thief append to `target_artifacts` whenever they drop a file, create a scheduled task, add a user, etc.
- Bookkeeper iterates `target_artifacts`, attempts removal, flags failures.
- Uncleaned artifacts are surfaced prominently in the final report.

---

## 8. v2 Decision Audit Trail

- `plan.md` includes a dynamic engagement flow showing all routing decisions with reasoning.
- `warchief_decisions.json` — machine-readable log of all routing decisions with full context.
- Report includes decision metrics: total recon cycles, scanning cycles, exploitation cycles, mission outcome.

---

## 9. Python Package Structure

```
chimeras/
├── core/
│   ├── base_bot.py          # Abstract base — reasoning loop + context truncation + safe fallback
│   ├── state.py             # Shared TypedDict state schema (v2 fields)
│   ├── llm_router.py        # Universal LLM adapter — routes to any provider
│   ├── tool_executor.py     # Subprocess wrapper + 3-tier scope enforcement
│   ├── scope.py             # Category-based scoping + TargetValidator + shell injection check
│   ├── config.py            # ConfigManager with v1→v2 auto-migration
│   ├── wizard.py            # Rich TUI pre-flight wizard
│   └── providers/           # Provider implementations
├── warchief/agent.py        # Decision router — 11 decisions, state machine, confidence threshold
├── bots/
│   ├── aria/agent.py        # Passive recon + lateral recon
│   ├── lisa/agent.py        # Active scanning + lateral scan
│   ├── bloodhound/agent.py  # Vuln detection + WAF/IPS + failed vector tracking
│   ├── pathologist/agent.py # Payload fabrication
│   ├── surgeon/agent.py     # Exploitation + lateral exploitation + artifact tracking
│   ├── magician/agent.py    # Privesc + lateral movement + artifact tracking
│   ├── thief/agent.py       # Exfiltration + failed exfil tracking
│   └── bookkeeper/agent.py  # Report + cleanup/rollback + decision audit trail + metrics
├── graph.py                 # Adaptive LangGraph wiring — conditional edges, loopback paths
├── main.py                  # Entry point — wizard integration, v2 state init
└── mission/                 # Operation workspace (per operation)
```

---

**Chimeras v2.0** — Cyberian Defenses | Autonomous Adaptive Reasoning Swarm Architecture