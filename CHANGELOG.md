# Chimeras — Changelog

All notable changes to Chimeras. Dates in Paris time (CEST/UTC+2).

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