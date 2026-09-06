# Chimeras Development Roadmap

> **This document covers v2.x only.** Current status: **v3.2 shipped** — see [ROADMAP-v3.0.md](ROADMAP-v3.0.md) for v3.0/v3.1/v3.2 and the v3.3+ backlog.

**Scope**: Transform Chimeras from a fixed linear pipeline into a true **adaptive reasoning swarm** where WarChief acts as a real pentester lead: dispatching agents, adapting to findings, improvising when plans fail, and routing dynamically based on what the team discovers.

---

## v2.4 — COMPLETE ✅

Council-driven efficiency and quality improvements. 4 sprints, all implemented, live-tested, and pushed to `main`.

| Sprint | What Shipped | Commit |
|--------|-------------|--------|
| S1 | Pydantic schemas, lossless findings store, telemetry expansion | `088660b`, `8d4e5e4` |
| S4 | Report template wired into Bookkeeper, structured report | `eda6c2e` |
| S2 | Verification cache (feature-flagged), content_hash on tool results | `b9feb68` |
| S3 | dispatch_parallel utility, can_parallelize, bot dependency map | `ab656df` |
| Soul | WarChief team knowledge — all 9 bots documented | `f9ba2b5` |

**Live tested**: Full engagement against cyberian-defenses.com — 6 min, 285 tool execs, 23 structured findings, 0 parse failures.

---

## v2.0-v2.3 — COMPLETE ✅

| Phase | What Shipped | Commit | Tests |
|-------|-------------|--------|-------|
| -1 | Hard scope enforcement, target validation, shell injection fix, safe fallback, lateral gate | `cb6c0ba` | 14/14 |
| TUI | Rich-based pre-flight wizard with LLM connectivity check | `b3236d1` | — |
| 0 | WarChief routing decisions, context truncation, config migration | `e14516e` | 6/6 |
| 1 | Adaptive graph rewiring — WarChief as decision router, loopback paths | `c5d9340` | 14/14 |
| Cleanup | Zero pyflakes, all v1.0 docstrings → v2.0, dead code removed | `ad62bf8` | — |
| 2 | Decision logic — state machine, confidence threshold, scope exhaustion, history | `b46f668` | 14/14 |
| 3 | Lateral movement — internal recon, target tracking, artifact tracking | `a424aa4` | 14/14 |
| 4 | Failure handling — WAF detection, failed vector tracking, graceful abort | `a0d4b1c` | 12/12 |
| 4.5+5+6 | Cleanup/rollback, audit trail, integration tests | `6406898` | 10/10 |

**Total**: ~3,500 lines changed across 11 commits. Zero pyflakes warnings. Zero v1.0 references.

---

## What v2 Does Now

- WarChief re-enters after each phase as a decision router (not one-shot planner)
- 11 routing decisions, 11-state mission state machine
- Loopback paths (deeper recon, deeper scanning) with per-phase 5-cycle limit
- Lateral movement with second human approval gate
- WAF detection triggers aggressiveness downgrade
- Failed vectors tracked — 3+ failures force abort
- Scope exhaustion detection — 2x recon with zero new targets → report
- Confidence threshold — below 0.6 → safe conservative route
- Artifacts tracked for cleanup — uncleaned items flagged in report
- Decision audit trail in report + machine-readable JSON
- TUI wizard with live LLM connectivity check for all 9 bots
- Shell injection blocked at code level (not prompt level)
- Out-of-scope IPs/hostnames blocked at code level
- Every node wrapped in try/except — graph degrades gracefully

---

## Phase Details

### Phase -1: Prerequisites & Risk Closure ✅
- `core/scope.py` — `TargetValidator` class: extract IPs/hostnames, DNS resolution, CIDR matching
- `core/scope.py` — `SHELL_METACHARS` detection, category-based allow/deny
- `core/tool_executor.py` — 3-tier enforcement: category → shell safety → target validation
- `core/base_bot.py` — safe fallback for malformed LLM output (conservative skip, not crash)
- `core/state.py` — 12 new fields (lateral_approval, target_context, external/internal_targets, etc.)
- `graph.py` — `lateral_approval_node` gate

### Phase 0: Foundation ✅
- `warchief/agent.py` — 11 routing decisions, JSON-lines audit log
- `core/base_bot.py` — rolling digest context truncation (last N entries, not full file re-reads)
- `core/config.py` — ConfigManager with auto-migration v1→v2 on load

### Phase 1: Graph Rewiring ✅
- `graph.py` (550 lines) — adaptive routing, WarChief as decision router, conditional edges, loopback paths, per-phase loop counter (max 5), exception handling on every node
- Dead `create_swarm_graph` removed

### Phase 2: WarChief Decision Logic ✅
- 11-state mission state machine
- Confidence threshold (<0.6 → safe route)
- Scope exhaustion detection (2+ recon cycles, zero new targets)
- Backtracking rule enforcement (no scan after shell in external scope, allowed in lateral)
- Decision history (rolling 5)

### Phase 3: Lateral Movement ✅
- ARIA lateral recon substrat (internal DNS, SMB, creds)
- Lisa lateral scan mode (high-value services, DC detection)
- Surgeon lateral exploitation (SMB exec, WinRM, SSH reuse)
- Magician lateral movement (privesc, cred dumping, AD enum)
- Mission setup: `lateral_objectives`, `internal_scope` params

### Phase 4: Failure Handling ✅
- Bloodhound WAF/IPS detection
- Bloodhound/Surgeon/Thief failed vector tracking
- Graceful abort (3+ failed exploits or 3 same decisions → Bookkeeper)
- WarChief failure-aware routing criteria

### Phase 4.5: Cleanup & Rollback ✅
- Bookkeeper iterates `target_artifacts`, attempts removal
- Uncleaned artifacts flagged prominently in report

### Phase 5: Reporting & Audit Trail ✅
- Decision audit trail in `plan.md` (engagement flow with all routing decisions)
- Decision metrics in report (total cycles, mission outcome)
- `warchief_decisions.json` — machine-readable log

### Phase 6: Integration Testing ✅
- Graph compiles and all paths reach Bookkeeper
- Loop limits verified (5-cycle per phase)
- Routing decisions verified (all 11 decisions route correctly)
- 10/10 integration tests passing

---

## Resolved Decisions

- **Loop bounds**: Per-phase, 5 cycles max. Not global.
- **Aggressiveness default**: `cautious`. Upgrade to `normal` only on explicit WarChief decision.
- **Operator feedback at decision points**: No. WarChief decides unilaterally. Gates are the human checkpoint.
- **Context growth**: Rolling digest of last N entries, not full file re-reads. Implemented in Phase 0.
- **Config migration**: Version flag in `swarm-config.json`, auto-migrated on load. Implemented in Phase 0.

---

## Known Limitations & Future Work (v3+)

- **Dependency chains**: Each bot waits for the previous one. v3 could parallelize independent scans.
- **Tool learning**: WarChief doesn't learn tool effectiveness over time.
- **Dynamic team sizing**: 9 fixed bots. v3 could spawn specialized bots for specific vectors.
- **Conflict resolution**: v3 could implement debate/consensus between agents.
- **Real-time operator input**: Gates are binary (y/n). v3 could allow mid-engagement guidance.
- **Multi-target engagement**: Single target/CIDR. v3 could parallelize multiple targets.

---

**Version**: Chimeras v2.0 — COMPLETE
**Last Updated**: 2026-07-21
**Status**: Shipped