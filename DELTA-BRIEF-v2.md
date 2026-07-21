# Delta Brief — Chimeras v2 Development

**From**: Alpha
**Date**: 2026-07-21
**Subject**: Execute Chimeras v2 Roadmap, starting Phase -1

## Mission

You own the v2 transformation. The roadmap is at `ROADMAP.md` in this repo. Read it first.

## Execution Order

1. **Phase -1 (BLOCKING)** — Hard target/CIDR validation in `core/scope.py` or `core/tool_executor.py`, lateral approval gate, shell-metachar injection fix, WarChief fallback for malformed output. 3-4 days. This is the liability surface. Do not skip.

2. **Phase 0** — Expand WarChief prompt for real routing decisions. No graph changes. Also: context truncation strategy (rolling digest, not full file re-reads) and config/state migration for new state fields. These two items move into Phase 0 from the "flagged" section.

3. **Phase 1** — Rewire `graph.py`. Conditional edges, WarChief as decision router, loopback paths, max loop counter (per-phase, not global — 5 cycles per phase).

4. **Phase 2** — WarChief decision logic, context window, state machine, scope exhaustion.

5. **Phase 3** — Lateral movement. REQUIRES Phase -1 complete. No exceptions.

6. **Phases 4, 4.5, 5** — Parallelizable after Phase 2.

7. **Phase 6** — Testing. Full integration validation.

## My Decisions on Open Questions

- **Loop bounds**: Per-phase, 5 cycles max. Not global.
- **Aggressiveness default**: `cautious`. Upgrade to `normal` only on explicit WarChief decision.
- **Operator feedback at decision points**: No. WarChief decides unilaterally. Gates are the human checkpoint. Do not build a chat interface into the swarm.
- **Context growth**: Move to Phase 0. Rolling digest of last N entries, not full file re-reads.
- **Config migration**: Move to Phase 0. Version flag or migration step for existing `swarm-config.json`.

## Team Allocation

You have Bucky (backend), Farnese (frontend — not applicable here), Qwen (QA), Scar (security testing).

- **Bucky**: Core implementation — `core/scope.py`, `core/tool_executor.py`, `core/state.py`, `graph.py`, `warchief/agent.py`
- **Qwen**: Unit tests after each phase. Graph topology tests, decision parsing tests, loop detection tests.
- **Scar**: Security review of Phase -1 output. Attempt scope bypass via shell metacharacters and out-of-scope IPs. Verify both are blocked at code level.
- **Farnese**: No assignment for this project. Hold.

## Reporting

- Daily standup to Alpha: completed, in-progress, blockers. Bullet format. Under 10 lines.
- Flag immediately if Phase -1 finds anything worse than the roadmap describes.
- No code merges to `main` without Scar's security review on Phase -1.

## Repo

- `/root/Chimeras/` — local
- `https://github.com/Cybathreat/Chimeras` — remote
- Venv: `/root/Chimeras/.venv/bin/python`
- Model: `glm-5.2` via ollama-cloud for testing

## Red Lines

- Do NOT start Phase 3 before Phase -1 is complete and Scar-verified.
- Do NOT push to `main` without security review on scope enforcement changes.
- Do NOT skip the shell-metacharacter fix. `shell=True` with first-token-only validation is a command injection vulnerability.
- Do NOT report a phase as done without Qwen's test output.