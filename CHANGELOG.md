# Chimeras v3.0 — Changelog

All notable changes to Chimeras. Dates in Paris time (CEST/UTC+2).

## v3.0 — 2026-09-02

### Added — Docker Sandboxing
- **DockerToolExecutor** (`core/docker_executor.py`) — executes all Kali tools inside disposable Docker containers. Read-only rootfs, memory/CPU/PID limits, cap-drop ALL + NET_RAW/NET_ADMIN. Zero host execution when enabled.
- **Kali Docker image** (`docker/Dockerfile`) — minimal Kali Linux with 30+ pentest tools (nmap, nuclei, sqlmap, gobuster, nikto, ffuf, whatweb, wafw00f, sslscan, ssh-audit, commix, wfuzz, httpx, dnsx, subfinder, naabu, wapiti, exploitdb, linpeas, dalfox, etc.)
- **ENABLE_DOCKER config flag** — `enable_docker` in swarm-config.json, `--docker` CLI flag. Graceful fallback to host execution when Docker daemon unavailable.
- **Defense in depth** — Python 3-tier scope enforcement runs BEFORE Docker call. Container isolation is second gate, not only gate.

### Added — SARIF 2.1.0 Export
- **SARIF exporter** (`core/sarif_exporter.py`) — GitHub code-scanning compatible output. Maps Pydantic Finding model to SARIF result objects. CWE/CVE rule IDs, security-severity scoring, logicalLocations for endpoint findings, fixes from remediation field.
- **Bookkeeper integration** — `findings.sarif` generated alongside `structured_report.md` and `final_report.md` at report time.

### Added — Web Search
- **Web search tool** (`core/web_search.py`) — Tavily API (primary, free tier 1000/month) with DuckDuckGo HTML fallback. `web_search()`, `search_cve()`, `search_exploit()` functions.
- **Scope integration** — `web_search` added to `passive_recon` tool category. ARIA and Marksman can use it.

### Added — Budget Management
- **BudgetTracker** (`core/budget.py`) — per-bot, per-phase USD cost tracking. Configurable cap via `budget_usd` in swarm-config.json. Warning at 80%, hard stop at 100%. Cost estimates for 10+ provider/model combinations. Ollama/cloud providers = $0.
- **Config integration** — `budget_usd` in DEFAULT_SWARM_CONFIG.

### Added — Jinja2 Prompt Templates
- **Template system** (`templates/base_prompt.j2`) — system prompt rendered via Jinja2. Falls back to f-string if Jinja2 or template unavailable. Enables prompt tuning without code changes.

### Added — Test Suite
- **210 pytest tests** — `tests/test_scope.py` (TargetValidator, ScopeEnforcer, shell injection, destructive blocklist, DoS detection), `tests/test_graph.py` (routing, loop limits, stuck detection, force-complete-cycle), `tests/test_schemas.py` (Pydantic models), `tests/test_json_parser.py` (fence stripping, truncation repair), `tests/test_findings_telemetry.py` (thread safety, telemetry).
- **Test fixtures** — `tests/conftest.py` with temporary engagement dirs, mock state.

### Added — CI/CD
- **GitHub Actions** (`.github/workflows/ci.yml`) — ruff lint + pytest on push. Python 3.11 + 3.12 matrix.

### Fixed — P0 Issues (Council Session 7)
- **Thread-safe JSONL writes** — `findings_store.py` now uses `threading.Lock` around all file appends. fcntl kept as cross-process defense in depth. Prevents interleaved writes when Bloodhound+Wasp run in parallel.
- **Telemetry truncation as failure** — `record_tool_exec()` now has `parse_ok` parameter. Truncation/fallback counted as parse failure in telemetry summary. Callers in `base_bot.py` pass `parse_ok=False` on truncation.
- **Verification filtering** — `findings_store.py` has `get_verified()` method returning only findings where `verified_by_cycle is not None`. Bookkeeper can generate verified-only reports.

### Changed
- `core/base_bot.py` — imports DockerToolExecutor, routes `_run_tool` through Docker when enabled. Jinja2 template rendering in `_build_static_system_prompt`. `parse_ok=False` on LLM truncation passed to telemetry.
- `core/config.py` — `enable_docker` and `budget_usd` in DEFAULT_SWARM_CONFIG.
- `core/scope.py` — `web_search` added to `passive_recon` category.
- `bookkeeper/agent.py` — SARIF export after structured report generation.
- `main.py` — `--docker` CLI flag, `enable_docker` in state initialization.

### Preserved (Do Not Touch)
- 3-tier scope enforcement (code-level, fail-closed)
- Fixed phase graph with human gates (exploitation + lateral movement)
- Professional pentest report format (Scope→Exec Summary→Findings→Remediation)
- WarChief adaptive routing (12 decisions, 11-state machine)
- Soul system (9 souls, 3,018 lines total)
- Force-complete-cycle logic
- Per-bot JSONL findings store (lossless)
- Artifact tracking + cleanup
- Ollama native support
- JSON checkpoint/resume system

---

## v2.5 — 2026-08-24

### Added
- **Marksman bot** — merged Pathologist (research) + Surgeon (execution) into single bot. No feedback loop. Human gate enforced.
- **Graph state checkpointing** — `core/checkpoint.py` saves state after every node. `--resume` restores full state.
- **14 bug fixes from live testing** — see CLAUDE.md for full list.

### Changed
- `core/scope.py` — merged `payload_fab` + `exploitation` into `marksman` category. `web_exploit` added to SHELL_CAPABLE_CATEGORIES.
- `graph.py` — merged pathologist+surgeon nodes into marksman_node. Force-complete-cycle in `_unified_router`.

---

## v2.4 — 2026-08-22

### Added
- Pydantic schema models (Finding, ToolResult, BotDecision, BotAnalysis)
- Lossless per-bot JSONL findings store
- Telemetry with per-provider LLM latency
- Verification cache (content hash-based)
- Parallel dispatch utility
- Structured report generation

---

## v2.3 — 2026-08-18

### Added
- Hardened JSON parser with truncation repair
- Telemetry logger
- Tool result cache (scope-invalidated)
- Critical findings buffer (CVSS >= 7.0)
- Report template (Jinja2)
- ROE prompt cache
- Depth matrix and compliance brief
- Destructive/DoS command blocklist
- Gate decision logging

---

## v2.1 — 2026-07-30

### Added
- Wasp bot (web application pentesting specialist)
- Scope expansion gate
- Soul.md system
- Lateral movement and pivoting

---

## v2.0 — 2026-07-21

### Added
- Adaptive graph rewiring (WarChief as decision router)
- 11-state mission state machine
- Hard scope enforcement (TargetValidator)
- TUI pre-flight wizard
- Config auto-migration

---

## v1.0 — 2026-07-17

### Added
- Initial release. 9 bots, LangGraph orchestration, provider-agnostic LLM routing.