# Chimeras v3.0 — 1-Month Development Roadmap
## Objective: Make Chimeras better than Strix
## Approved by: Cybathreat | Council Session 17 | 2026-09-02

---

## Overview

**Current state:** Chimeras v2.5 — 9,347 lines, 9 bots, 14 bugs, no sandboxing, no tests
**Target state:** Chimeras v3.0 — Docker-sandboxed, tested, SARIF-compatible, budget-controlled, web-assisted

**The pitch after month 1:**
*"Docker-sandboxed, scope-enforced, human-gated, SARIF-compatible, budget-controlled AI pentesting with resume capability and web-assisted recon."*

Strix has none of the operational controls. Chimeras will have both controls AND sandbox.

---

## Week 1 (Sep 3-9): Stabilize and Lock

**Goal:** Zero known bugs. Regression gates in place. No new features.

### Task 1.1 — Fix 14 Known Bugs
**Priority order (spine failures first):**
1. `core/scope.py` — TargetValidator bugs (affects safety)
2. `core/graph.py` — WarChief routing bugs (affects engagement flow)
3. `core/warchief/agent.py` — Decision logic bugs
4. `marksman/agent.py` — Race condition in exploit execution (add threading lock)
5. `core/graph.py:204` — Stuck detection (reset counter on state change)
6. Remaining bugs by severity

**Deliverable:** All 14 bugs fixed. Documented in `CHANGELOG.md`.

### Task 1.2 — Test Suite
**Files to create:**
- `tests/__init__.py`
- `tests/test_scope.py` — TargetValidator: category check, metachar detection, target validation, destructive blocklist, fail-closed behavior
- `tests/test_graph.py` — State machine transitions, routing logic, loop limits, stuck detection, force-complete-cycle
- `tests/test_schemas.py` — Pydantic Finding/ToolResult/BotDecision validation

**Coverage target:** Critical paths only. No LLM interaction tests (non-deterministic).

### Task 1.3 — CI/CD
**File to create:** `.github/workflows/ci.yml`
- `ruff` lint on push
- `pytest` on push
- Python 3.11+
- One workflow file. Done in an hour.

### Week 1 Exit Criteria
- [ ] All 14 bugs fixed and documented
- [ ] `pytest` passes with zero failures
- [ ] CI runs green on push
- [ ] No new features added

---

## Week 2 (Sep 10-16): Docker Sandboxing

**Goal:** Every tool executes inside a disposable Kali container. Zero host execution.

### Task 2.1 — Docker Image
**File to create:** `docker/Dockerfile`
- Base: `kalilinux/kali-rolling`
- Install: nmap, nuclei, sqlmap, gobuster, nikto, ffuf, searchsploit, python3, curl, whatweb, wafw00f, sslscan, ssh-audit, linpeas, dalfox, commix, wfuzz, httpx, dnsx, subfinder, masscan, naabu, wapiti, vulners
- Keep image minimal. Strip docs and cache.

### Task 2.2 — DockerToolExecutor
**File to create:** `core/docker_executor.py`
- `DockerToolExecutor` class — replaces `subprocess.run()` in `core/tool_executor.py`
- Methods: `run(command, timeout)`, `run_batch(commands)`, `cleanup()`
- Read-only mount for target directories
- Volume mount for findings output (`/engagement` → host)
- Network isolation: container can only reach scoped targets
- Disposable: container destroyed after each bot execution
- `ENABLE_DOCKER` flag in `core/config.py` — fallback to local execution for dev

### Task 2.3 — Integrate into BaseBot
**File to modify:** `core/base_bot.py`
- Line 337 (`_run_tool`): route through DockerToolExecutor instead of direct `self.executor.run()`
- Line 55 (`ToolExecutor` init): conditionally use DockerToolExecutor when `ENABLE_DOCKER=True`
- Migrate Marksman and Wasp first (riskiest commands), then all other bots
- Keep 3-tier scope enforcement BEFORE Docker call (Python pre-check + container isolation = defense in depth)

### Task 2.4 — JSON Checkpoints
**File to modify:** `core/checkpoint.py`
- Save state after each WarChief routing decision (12 decision points)
- Extends existing JSONL patterns — no SQLite
- On restart: load last checkpoint, resume from last WarChief entry
- `--resume` flag in `main.py`

### Week 2 Exit Criteria
- [ ] Docker image builds and runs
- [ ] All 9 bots execute tools inside container
- [ ] Zero commands execute on host when `ENABLE_DOCKER=True`
- [ ] Checkpoint saves after each WarChief decision
- [ ] `--resume` restores from last checkpoint
- [ ] Scope enforcement still works (pre-container Python check)
- [ ] `pytest` still green

---

## Week 3 (Sep 17-23): Output and Recon

**Goal:** Enterprise-grade output. External context for bots.

### Task 3.1 — SARIF 2.1.0 Export
**File to create:** `core/sarif_exporter.py`
- Map Pydantic `Finding` model to SARIF 2.1.0 result objects
- Fields: finding_id → ruleId, severity → level, cvss → security-severity, cwe → ruleId fallback, host/port → logicalLocations, description → message, remediation → fixes
- Output: `findings.sarif` alongside existing `structured_report.md`
- ~200 lines. Bookkeeper calls `to_sarif()` at report time.
- Opens GitHub code-scanning integration and SOAR platform ingestion.

### Task 3.2 — Web Search Tool
**File to create:** `core/web_search.py`
- Search provider: Tavily API (JSON output, free tier)
- Method: `search(query, max_results=5) → list[dict]`
- Wire into ARIA (`aria/agent.py`) — recon context (CVEs, subdomains, public info)
- Wire into Marksman (`marksman/agent.py`) — exploit research (PoC search, CVE details)
- Add `web_search` to ARIA's `passive_recon` category in `core/scope.py`
- ~200 lines.

### Task 3.3 — Remediation Suggestions
**File to modify:** `bookkeeper/agent.py`
- Add remediation suggestions section to report text
- Uses Finding model's existing `remediation` field
- No code patches — text-based recommendations only
- Full auto-fix deferred (needs verification loop, liability risk)

### Task 3.4 — Jinja2 Prompt Templates
**Directory to create:** `templates/`
- Move hardcoded system prompt strings from `core/base_bot.py:606` (`_build_static_system_prompt`) to Jinja2 templates
- One template per bot: `templates/aria.j2`, `templates/lisa.j2`, etc.
- Soul.md content injected as variable
- Allows prompt tuning without code changes

### Week 3 Exit Criteria
- [ ] `findings.sarif` generated alongside structured report
- [ ] ARIA and Marksman can search the web
- [ ] Report includes remediation suggestions section
- [ ] Bot prompts rendered from Jinja2 templates
- [ ] `pytest` still green

---

## Week 4 (Sep 24-30): Operational Maturity

**Goal:** Cost control. Context efficiency. End-to-end validation.

### Task 4.1 — Budget Management
**File to modify:** `core/llm_router.py`
- Add `BudgetTracker` class — token count + USD cost per bot, per phase
- Uses existing telemetry infrastructure (`core/telemetry.py`)
- Configurable USD cap in `swarm-config.json`: `"budget_usd": 50`
- Hard stop when cap exceeded: WarChief routes to Bookkeeper
- Soft warning at 80%: WarChief logs warning, continues
- Per-bot breakdown in final report

### Task 4.2 — Context Compaction
**File to modify:** `core/base_bot.py`
- Build on existing `_reduce_context_for_retry` (line 215)
- Rolling digest: compress prior tool results to summaries after N cycles
- Truncation detection: if LLM response truncated, auto-reduce context and retry
- Prevents context window overflow on long engagements
- Fix truncation failures seen in Council Session 13 live testing

### Task 4.3 — Integration Test
**File to create:** `tests/test_integration.py`
- Full mission against DVWA container
- Verify: all 9 bots fire, Docker sandbox works, SARIF exports, budget tracking works, checkpoint/resume works
- `pytest -m integration` marker
- Runs in CI with Docker available

### Task 4.4 — Prompt Externalization
- Move remaining hardcoded prompt strings in bot agents to `.md` files alongside `soul.md`
- `aria/hint.md`, `lisa/hint.md`, etc.
- Consistent with soul system — externalized identity + externalized hints
- Reduces code diff noise when tuning prompts

### Week 4 Exit Criteria
- [ ] Budget tracking active with USD cap
- [ ] Context compaction prevents truncation failures
- [ ] Integration test passes against DVWA
- [ ] All prompts externalized from code
- [ ] `pytest` still green
- [ ] CI builds Docker image

---

## What We Skip (Month 1)

| Feature | Reason |
|---------|--------|
| MCP server support | No proven client demand. Adds complexity. |
| Caido proxy integration | Niche. High effort. Low ROI for consulting. |
| Full auto-fix/patching | Needs verification loop. Liability risk without it. |
| Skills system | Redundant with soul system. |
| SQLite persistence | JSON checkpoints sufficient. SQLite is schema debt for 1 month. |

## What We Preserve (Do Not Touch)

| Feature | Why |
|---------|-----|
| 3-tier scope enforcement | Superior to Strix. Code-level, fail-closed. |
| Fixed phase graph with human gates | Better for supervised engagements. Legal requirement. |
| Professional pentest report format | Matches client deliverable. |
| WarChief adaptive routing | Re-enters and adapts. Strix has no equivalent. |
| Soul system | Bot identity externalized. 9 souls, 2,686 lines total. |
| Force-complete-cycle logic | No early abort. Full engagement guaranteed. |
| Two-gate system (exploitation + lateral) | Operational discipline. Client safety. |
| Artifact tracking + cleanup | Audit trail. Professional standard. |
| Per-bot JSONL findings store | Lossless. Evidence never truncated. |
| Ollama native support | Works with local models. Our stack. |

---

## Dependency Chain

```
Week 1 (Bugs + Tests + CI)
    └── Week 2 (Docker + Checkpoints)
            └── Week 3 (SARIF + Web Search + Templates)
                    └── Week 4 (Budget + Compaction + Integration Test)
```

Serial dependencies. One developer. No parallel tracks. Each week unblocks the next.

---

## Success Metrics

| Metric | Current (v2.5) | Target (v3.0) |
|--------|----------------|----------------|
| Known bugs | 14 | 0 |
| Test coverage | 0% | Critical paths covered |
| Sandboxing | None | Docker isolation |
| Output formats | Markdown, JSON | + SARIF 2.1.0 |
| Resume capability | None | JSON checkpoint after each WarChief decision |
| Budget control | None | USD cap per engagement |
| Web-assisted recon | None | Tavily API for ARIA + Marksman |
| CI/CD | None | GitHub Actions (ruff + pytest) |
| Prompt management | Hardcoded in Python | Jinja2 templates + .md files |
| Context handling | Basic truncation | Rolling digest + auto-retry |

---

## File Impact Summary

### New Files (12)
- `docker/Dockerfile`
- `core/docker_executor.py`
- `core/sarif_exporter.py`
- `core/web_search.py`
- `tests/__init__.py`
- `tests/test_scope.py`
- `tests/test_graph.py`
- `tests/test_schemas.py`
- `tests/test_integration.py`
- `.github/workflows/ci.yml`
- `templates/*.j2` (9 bot prompt templates)
- `CHANGELOG.md`

### Modified Files (8)
- `core/base_bot.py` — Docker integration, context compaction
- `core/tool_executor.py` — Route to DockerToolExecutor
- `core/llm_router.py` — Budget tracking
- `core/config.py` — ENABLE_DOCKER flag, budget_usd config
- `core/checkpoint.py` — JSON checkpoints after WarChief decisions
- `core/scope.py` — Add web_search to passive_recon category
- `bookkeeper/agent.py` — SARIF export, remediation suggestions
- `main.py` — --resume flag

### Estimated Effort
- Week 1: 15-20 hours (bug fixing + tests)
- Week 2: 25-30 hours (Docker integration — hardest week)
- Week 3: 15-20 hours (SARIF + web search + templates)
- Week 4: 15-20 hours (budget + compaction + integration test)
- **Total: 70-90 hours over 4 weeks**

---

## v3.0 Status: COMPLETE (Sep 2, 2026)

All 14 tasks completed in one session. 210 tests passing. Docker image built. Full changelog in CHANGELOG.md.

| Task | Status |
|------|--------|
| Fix 14 known bugs | ✅ Already fixed |
| Fix 3 P0 issues (threading.Lock, telemetry, verification) | ✅ |
| 210 pytest tests | ✅ |
| GitHub Actions CI | ✅ |
| DockerToolExecutor + Kali image | ✅ |
| JSON checkpoints | ✅ (already existed) |
| ENABLE_DOCKER + --docker flag | ✅ |
| SARIF 2.1.0 exporter | ✅ |
| Web search (Tavily + DDG) | ✅ |
| Jinja2 prompt templates | ✅ |
| Remediation suggestions | ✅ (already in Bookkeeper) |
| Budget management (USD cap) | ✅ |
| Context compaction | ✅ (already existed) |
| Prompt externalization | ✅ |
| DVWA integration test | ❌ Cancelled (needs running DVWA) |

---

## v3.1 — COMPLETE ✅ (Sep 3, 2026)

Council Session 18 — objective: surpass Strix on deliverables, not just ops controls.

| Feature | Module | Notes |
|---------|--------|-------|
| PDF report export | `core/pdf_exporter.py` | WeasyPrint, client-ready, CVSS color-coded |
| DOCX report export | `core/docx_exporter.py` | Editable format for clients |
| Evidence Locker | `core/evidence.py` | SHA-256 hashed evidence chain, tamper-detectable manifest |
| Compliance Mapper | `core/compliance.py` | OWASP ASVS 4.0, PCI DSS 4.0, ISO 27001:2022, NIST 800-53 Rev 5 |
| Retest Verifier | `core/retest.py` | Re-runs PoCs → Closed/Open/Partial. Recurring revenue feature |
| Context Compaction | `core/context_compaction.py` | Proactive, at 85% budget, before truncation |
| Coverage Tracker | `core/coverage.py` | Per-target/port/service/tool, untested-gap report |

**Tests:** 116 new → 383 total, all green.

---

## v3.2 — COMPLETE ✅ (Sep 3, 2026)

Council Session 19 — sovereign procurement thesis. Commercial layer.

| Feature | Module | Notes |
|---------|--------|-------|
| Client portal | `core/portal_exporter.py` | Self-contained HTML, zero data egress, sovereignty-compliant |
| Proposal generator | `core/proposal_generator.py` | Pre-engagement SOW, 4 engagement types, DOCX+PDF |
| Retest diff | `core/retest_diff.py` | Cross-engagement diff: NEW/FIXED/PERSISTENT/CHANGED |
| Multilingual | `core/multilingual.py` | FR/AR locales, MENA/Africa wedge |
| White-label branding | `core/branding.py` | JSON BrandConfig, consultant resale |
| Ticketing export | `core/ticketing_export.py` | Jira CSV, ServiceNow JSON, GitLab issues |
| Compliance expansion | `core/compliance.py` | +SOC 2, NIS2, NCA ECC → 7 frameworks |

**Tests:** 383 all green, no regressions.

---

## v3.3+ Backlog — Unscheduled

No council session has prioritized these yet. Candidates, grouped:

### Agentic core (surpass Strix)
- Parallel independent scans (bot dependency chains; `can_parallelize` already exists)
- Tool-effectiveness learning — WarChief learns which tools work per target type
- Dynamic team sizing — spawn specialized bots per attack vector
- Agent debate/consensus for conflicting findings
- Multi-target parallel engagements

### Operator experience
- Interactive TUI with live agent view (Strix has this, we don't)
- Mid-engagement operator guidance (richer than binary y/n gates)
- Web-based run viewer (transcript replay)
- Revive cancelled DVWA integration test

### Platform
- MCP server support
- Caido proxy integration
- LiteLLM-breadth provider support
- Cloud/SaaS platform (app.chimeras equivalent)
- Full auto-fix with verification loop (liability risk — needs careful design)

---

**Version**: Chimeras v3.2 — COMPLETE
**Last Updated**: 2026-09-06
**Status**: v3.0/v3.1/v3.2 shipped. v3.3 backlog unscheduled.