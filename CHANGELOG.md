# Chimeras — Changelog

All notable changes to Chimeras. Dates in Paris time (CEST/UTC+2).

## v2.4 — 2026-08-22

### Added
- **Pydantic schema models** (`core/schemas.py`) — `Finding`, `ToolResult`, `BotDecision`, `BotAnalysis` with validation. Fallback when Pydantic not installed. `compute_content_hash()` utility. (088660b)
- **Lossless findings store** (`core/findings_store.py`) — per-bot JSONL files. File-locked writes. `merge_all()`, `get_critical()`, `format_for_report()`, `deduplicate()`. Evidence never truncated. (088660b)
- **Telemetry expansion** — `record_llm_call()` with provider/model metrics, `record_tool_exec()` with structured tool metrics, `summary()` for baseline comparison (cache hit rate, parse failure rate, per-provider latency). (8d4e5e4)
- **Verification cache** — WarChief skips re-verification when tool output `content_hash` unchanged. `_mark_verified()`, `_is_verified()` in BaseBot. Feature-flagged (default off). (b9feb68)
- **Parallel dispatch utility** — `dispatch_parallel()` in graph.py generalizes Bloodhound+Wasp parallelism. `can_parallelize()` checks `BOT_DEPENDENCIES` map. `PARALLEL_CAPABLE` and `SEQUENTIAL_ONLY` sets. (ab656df)
- **Structured report** — Bookkeeper generates `structured_report.md` from FindingsStore via `render_report()` template. Audit JSON includes `findings_total`, `findings_critical`, `findings_by_bot`. (eda6c2e)
- **WarChief soul: team knowledge** — all 9 specialists documented with roles, tool categories, boundaries, expected output, re-dispatch triggers, dependency map, parallel dispatch instructions. (f9ba2b5)
- **Verification metadata on tool results** — `content_hash`, `tool_name`, `target`, `verified_by_cycle` added to every tool execution result. (088660b)
- **Analysis prompt upgrade** — bots now asked to output `structured_findings` with full schema (finding_id, severity, cvss, host, port, service, status, description, risks, attack_vectors, poc, proof_of_existence, remediation). (088660b)

### Changed
- **base_bot.py** — imports schemas, FindingsStore, compute_content_hash. `_parse_json_response()` accepts optional schema for validation. Tool results carry verification metadata. Analysis output saves structured findings to JSONL and feeds critical findings to critical_buffer.
- **warchief/agent.py** — `_update_state()` marks tool results as verified after each decision cycle (when feature-flag enabled).
- **bookkeeper/agent.py** — imports `render_report` and `FindingsStore`. Generates structured report alongside LLM narrative. Merges per-bot JSONL findings. Audit JSON includes findings summary.
- **graph.py** — `bloodhound_node` refactored to use `dispatch_parallel([Bloodhound, Wasp])` instead of inline asyncio.gather. Added `BOT_DEPENDENCIES`, `can_parallelize()`, `dispatch_parallel()`.
- **telemetry.py** — LLM calls now record `provider_name` and `model` via `record_llm_call()` instead of generic `record()`.

### Live Tested
- Full engagement against cyberian-defenses.com: 6 min, 285 tool executions, 11 LLM calls, 7 cache hits, 0 parse failures, 23 structured findings, 3 WarChief decisions. Structured report and audit JSON generated successfully.

---

## v2.3 — 2026-08-18

### Added
- **Hardened JSON parser** (`core/json_parser.py`) — strips markdown fences, brace matching, truncation detection, optional Pydantic validation. Replaces inline `_parse_json_response` in base_bot.py.
- **Telemetry logger** (`core/telemetry.py`) — JSONL telemetry for every LLM call and tool execution. Context manager for timing blocks.
- **Tool result cache** (`core/tool_cache.py`) — file-based cache keyed by (scope_version, tool, target, args). Scope-invalidated. WarChief can force-invalidate.
- **Critical findings buffer** (`core/critical_buffer.py`) — append-only buffer for CVSS >= 7.0 findings. Never truncated. Read first by WarChief and Bookkeeper.
- **Report template** (`core/report_template.py`) — Jinja2 template with schema validation. Fallback f-string renderer. Full pentest report structure.
- **ROE prompt cache** (`core/roe_cache.py`) — caches WarChief's system prompt ROE block. Delta injection for scope changes.
- **Depth matrix** (`core/depth_matrix.py`) — pentest depth assessment categories for WarChief's quality checks.
- **Compliance brief** (`core/compliance_brief.py`) — compliance brief builder for WarChief's ROE enforcement.
- **WarChief compliance officer** — `forbidden_commands`, `depth_gap_carryforward`, `scope_version` fields in state. WarChief enforces RoE, checks scope expansion, invalidates cache on scope change.
- **18 bug fixes from Council code review** — P0 security + P1 integrity + P2 performance. (6ad4b27)
- **Council-rewritten souls** — ARIA, Lisa, Bloodhound soul.md files rewritten through multi-LLM council debate. Embedded real pentest domain expertise.

### Changed
- **base_bot.py** — imports json_parser, telemetry, tool_cache, critical_buffer. Tool cache check before execution. Telemetry on every LLM call and tool exec. Sanitize tool output for prompt injection. Static system prompt caching.
- **warchief/agent.py** — imports compliance_brief, roe_cache, depth_matrix. ROE cache for system prompt. Delta context injection. Depth assessment per finding. Scope version tracking.

---

### Added
- **Destructive/DoS command blocklist** — code-level enforcement of Rules of Engagement. `rm -rf`, `mkfs`, `dd of=/dev/`, fork bombs, `DROP TABLE`, `TRUNCATE TABLE`, `shutdown/reboot/halt`, Windows `format`, and flood-rate scan flags (nmap `--max-rate >=100000`, hping3 `--flood`, slowloris, goldeneye) are blocked before execution, independent of tool category. Hard destructive patterns always blocked; DoS-capable flags blocked when RoE restricts DoS or when no RoE is supplied (fail safe). `DestructiveCommandViolation` exception class added to `core/scope.py`.
- **Gate decision logging** — every exploitation and lateral-movement gate decision (approved, denied, auto-approved, errored) is now written to `engagement/log.md` with timestamp, gate name, mode, and detail. The decision to bypass human review via `--approve` is now part of the permanent mission record, not just terminal scrollback. `_log_gate_decision()` function added to `graph.py`.
- **RoE parameter** propagated through the full enforcement chain: `ScopeEnforcer.check()`, `ScopeEnforcer.enforce()`, `ToolExecutor.__init__()`, `BaseBot._execute_tool()`.

### Changed
- **Scope enforcement order** — now 4 checks instead of 3: destructive/DoS → shell injection → tool category → target/CIDR. Destructive check runs first because it's category-independent.
- **README** — two new design principles documented (destructive command blocking, gate decision logging).

---

## v2.1 — 2026-07-30

### Added
- **Wasp bot** — web application pentesting specialist. Detects XSS, CSRF, SQLi, SSTI, SSRF, LFI/RFI, IDOR, auth bypass. Runs in parallel with Bloodhound during vuln detection phase. (b16e6f6)
- **`vuln_detection` routing decision** — WarChief now explicitly routes to Bloodhound+Wasp before considering exploitation. (ec5e47a)
- **Scope expansion gate** — when out-of-scope targets are discovered, operator decides whether to expand scope. (d55fcee)
- **Soul.md system** — bot identity externalized from code into per-bot `soul.md` files. (b5b6060)
- **Wiki documentation** updated for Wasp integration and v2 architecture. (fb5494c)

### Changed
- **Wasp refactored** from exploitation to detection-only role. Runs parallel with Bloodhound, no human approval needed for detection. (08d7a65)
- **WarChief soul** updated — always runs Bloodhound before reporting, no premature abort. (5aca901)
- **Bot count**: 9 → 10 bots (Wasp added).

### Fixed
- **asyncio.gather parallel execution** — `bot.run()` is async but has no await points (all blocking LLM/subprocess calls). `asyncio.gather` alone ran them sequentially — Bloodhound blocked, Wasp never started. Fix: wrap each `bot.run()` in `asyncio.to_thread(lambda: asyncio.run(bot.run()))` for true OS-thread parallelism. Added `return_exceptions=True` and per-bot error logging with traceback to prevent silent Wasp failures. (e5c222e)
- **Router using `mission.phase` instead of `last_bot`** — Bloodhound was silently skipped because router checked phase state instead of which bot last ran. (d6c58b4)
- **NO PROGRESS guard false positive** — scope parsing didn't handle space-separated targets. (b6f1ae6)
- **Scope parsing and scope exhaustion** root causes fixed. (bcbf7c8)
- **3 bugs from first real engagement** (raksha.tn) — scope parsing, target validation, routing edge cases. (19b7a30)
- **WarChief always runs Bloodhound** before reporting — prevents premature abort on first scan cycle. (5aca901)
- **Force advance after 2 scan cycles** — prevents infinite scan loops. (ec5e47a)

### Removed
- **`mission/` directory** removed from git tracking — mission data is per-operation, not version-controlled. (87c1b1d)

---

## v2.0 — 2026-07-21

### Added
- **Adaptive graph rewiring** — WarChief is now a decision router that re-enters after each phase. 11 routing decisions, 11-state mission state machine. (c5d9340, b46f668, e14516e)
- **Lateral movement & pivoting** — internal recon, lateral scan, lateral exploitation. Second human approval gate. (a424aa4)
- **Failure handling & resilience** — WAF/IPS detection, failed vector tracking, graceful abort (3+ failed exploits or 3 same decisions). (a0d4b1c)
- **Cleanup/rollback** — artifact tracking, removal attempted, failures flagged in report. (6406898)
- **Decision audit trail** — all WarChief routing decisions logged in report + `warchief_decisions.json`. (6406898)
- **Context truncation** — rolling digest of last N entries, not full file re-reads. (e14516e)
- **Config auto-migration** — v1 `swarm-config.json` auto-migrated to v2 on load. (e14516e)
- **TUI pre-flight wizard** — Rich-based, 3-step: config check, LLM connectivity for all bots, summary. `--skip-wizard` to bypass. (b3236d1)
- **Hard scope enforcement** — `TargetValidator` resolves IPs/hostnames, checks against CIDR scope. Shell metacharacter injection blocked for non-shell categories. (cb6c0ba)
- **`.gitignore`** — Python, venv, IDE, mission data, secrets, logs. (37ad9d9)

### Changed
- **All v1.0 docstrings → v2.0**. (ad62bf8)
- **All MD files and wiki rewritten** for v2.0. (c4b8c0a)
- **Project renamed** to Chimeras — all references updated. (7e231a3)

### Fixed
- **Zero pyflakes warnings** — full code cleanup. (ad62bf8)

---

## v1.0 — 2026-07-17

### Added
- Initial release. 9 bots: WarChief, ARIA, Lisa, Bloodhound, Pathologist, Surgeon, Magician, Thief, Bookkeeper.
- LangGraph-based multi-agent orchestration.
- Provider-agnostic LLM routing (6 providers + custom base_url).
- Category-based tool scoping with dynamic discovery.
- File-based bot communication via engagement files.
- Bookkeeper: full context + raw tool output for PoC/Proof of Existence sections. (e5b9436)
- Scope system, tool executor, base bot architecture. (7e231a3)
- Chimeras v2 development roadmap. (9de35e5)