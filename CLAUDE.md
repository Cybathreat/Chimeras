# CLAUDE.md — Chimeras v2.0 Development Context

## Project
Chimeras is an autonomous AI pentest swarm with adaptive decision-making. 9 bots, each powered by an independently assigned LLM, each reasoning autonomously about what tools to run and what strategy to use. No hardcoded tool lists — bots declare a tool category and the LLM picks tools dynamically. WarChief acts as a decision router, re-entering after each phase to adapt the engagement based on actual findings.

## Stack
- Python 3.11+
- LangGraph (multi-agent orchestration, conditional edges, loopback paths)
- Rich (TUI pre-flight wizard)
- Provider-agnostic LLM routing (Anthropic/Google/Groq/OpenRouter/Ollama/OpenAI-compatible)
- Kali Linux tools executed via subprocess
- Custom gateway support (any OpenAI/Anthropic-compatible endpoint via `base_url`)

## Core Rules
- Every bot inherits from `core/base_bot.py`
- The LLM IS the brain — no hardcoded fallback logic
- Safe fallback exists only for malformed LLM output (WarChief defaults to `report` route)
- Tools are NOT hardcoded in bot agents — bots declare a category, scope enforcer maps to installed tools
- Bots communicate ONLY through engagement files (plan.md, log.md, findings.md, per-bot .md)
- State is shared via `core/state.py` TypedDict
- Raw tool output saved to `engagement/raw/` for audit trail
- WarChief re-enters the graph after each phase — it is NOT a one-shot planner

## Bot Order (v2 Adaptive Graph)
WarChief is the entry point and decision router. After each phase bot completes, the graph routes back to WarChief, which makes a routing decision based on findings:

```
WarChief (init) → ARIA → WarChief (route) → Lisa → WarChief (route)
→ Bloodhound → WarChief (route) → [HUMAN GATE] → Pathologist → Surgeon
→ WarChief (route) → Magician → Thief → WarChief (final) → Bookkeeper → END
```

WarChief can route back to ARIA or Lisa for deeper recon, pivot to lateral movement (second gate), or abort to Bookkeeper if scope is exhausted or failures accumulate.

## WarChief Routing Decisions (11)
`recon`, `scan`, `vulns_found_exploit`, `insufficient_data_abort`, `lateral_recon`, `lateral_scan`, `pivot_lateral_recon`, `exploit`, `privesc`, `exfil`, `report`

## Mission State Machine (11 states)
`init → recon → scanning → vuln_detection → exploitation_prep → exploitation → post_exploit → lateral_recon → lateral_scanning → reporting → complete`

## Human-in-Loop (Two Gates)
1. **Exploitation gate** — between Bloodhound and exploitation bots. Operator reviews vuln report.
2. **Lateral movement gate** — before any internal/lateral pivot. Operator reviews discovered internal targets.

`--approve` flag bypasses both gates for headless/piped runs.

## Tool Scoping (Category-based, 3-tier enforcement)
Bots declare a category in `core/scope.py` (`BOT_CATEGORIES`):
- ARIA → `passive_recon` (dig, whois, whatweb, wafw00f, subfinder, ...)
- Lisa → `active_scan` (nmap, nikto, gobuster, ffuf, wpscan, ...)
- Bloodhound → `vuln_detection` (nuclei, searchsploit, wapiti, ssh-audit, sslscan, ...)
- Pathologist → `payload_fab` (msfvenom, msfconsole, searchsploit, curl)
- Surgeon → `exploitation` (msfconsole, sqlmap, nc, python3, bash, ...)
- Wasp → `web_exploit` (sqlmap, nikto, nuclei, curl, ffuf, wfuzz, dalfox, commix, ...)
- Magician → `privesc` (linpeas, find, cat, ssh, smbclient, ...)
- Thief → `exfiltration` (curl, wget, nc, tar, scp, rsync, ...)
- WarChief/Bookkeeper → `none` (no tool execution)

Three-tier enforcement:
1. Category check (tool must be in bot's allowed set)
2. Shell metacharacter check (injection blocked for non-shell categories)
3. Target validation (`TargetValidator` resolves IPs/hostnames, checks against CIDR scope)

Tools are discovered dynamically via `shutil.which()`. LLM only sees installed tools.

## v2 Key Features
- **Adaptive routing**: WarChief re-enters after each phase, 11 routing decisions
- **Loopback paths**: deeper recon, deeper scanning (max 5 cycles per phase)
- **Lateral movement**: internal recon, lateral scan, lateral exploitation — gated by second human approval
- **Failure handling**: WAF/IPS detection, failed vector tracking, graceful abort (3+ failed exploits or 3 same decisions)
- **Scope exhaustion**: 2+ recon cycles with zero new targets → forced report
- **Confidence threshold**: WarChief confidence < 0.6 → safe conservative route
- **Artifact tracking**: dropped tools/payloads tracked, cleanup attempted, failures flagged in report
- **Decision audit trail**: all routing decisions logged in report + `warchief_decisions.json`
- **Context truncation**: rolling digest of last N entries, not full file re-reads
- **Config auto-migration**: v1 `swarm-config.json` auto-migrated to v2 on load
- **TUI wizard**: Rich-based pre-flight with live LLM connectivity check for all 9 bots (`--skip-wizard` to bypass)

## Package Structure
```
Chimeras/
├── core/
│   ├── base_bot.py       # Abstract bot — LLM reasoning loop + tool execution + context truncation
│   ├── state.py          # LangGraph TypedDict state schema (v2 fields)
│   ├── llm_router.py     # Universal LLM adapter — 6 providers + custom base_url
│   ├── tool_executor.py  # Subprocess wrapper with timeout, raw output capture, scope enforcement
│   ├── scope.py          # Category-based tool scoping + dynamic discovery + TargetValidator + shell injection check
│   ├── config.py         # ConfigManager with v1→v2 auto-migration
│   ├── wizard.py         # Rich TUI pre-flight wizard (3-step: config check, LLM connectivity, summary)
│   └── providers/        # Provider implementations
│       ├── anthropic.py  # Claude Opus/Sonnet/Haiku
│       ├── google.py     # Gemini
│       ├── groq.py       # Llama 3.3 70B / Mixtral
│       ├── openrouter.py # Any model via OpenRouter
│       ├── openai.py     # GPT-4o / any OpenAI-compatible endpoint
│       └── ollama.py     # Local Ollama
├── warchief/
│   └── agent.py          # Decision router — 11 routing decisions, state machine, confidence threshold, fallback
├── bots/
│   ├── aria/agent.py     # Passive recon + lateral recon substrat
│   ├── lisa/agent.py     # Active scanning + lateral scan mode
│   ├── bloodhound/agent.py  # Vuln detection + WAF/IPS detection + failed vector tracking
│   ├── wasp/agent.py     # Web app exploitation (XSS, CSRF, SQLi, file upload, SSTI, SSRF, etc.)
│   ├── pathologist/agent.py # Payload fabrication
│   ├── surgeon/agent.py  # Exploitation + lateral exploitation + failed vector tracking + artifact tracking
│   ├── magician/agent.py # Privesc + lateral movement + artifact tracking
│   ├── thief/agent.py    # Exfiltration + failed exfil tracking
│   └── bookkeeper/agent.py  # Report generation + cleanup/rollback + decision audit trail + metrics
├── graph.py              # Adaptive LangGraph wiring — conditional edges, loopback paths, loop protection
├── main.py               # Entry point — wizard integration, v2 state initialization
└── mission_*/            # Per-operation workspace
    ├── swarm-config.json  # Per-bot LLM config (auto-migrated v1→v2)
    ├── mission.md         # Objectives, scope, RoE
    └── engagement/
        ├── plan.md         # WarChief's plan + decision audit trail
        ├── log.md          # Timestamped action log
        ├── findings.md     # Accumulated findings
        ├── warchief_decisions.json  # Machine-readable decision log
        ├── *.md            # Per-bot work logs
        ├── raw/            # Raw tool output (audit trail)
        ├── poc/            # Proof-of-concept artifacts
        └── report/         # Final report
```

## Config
Per-bot config in `swarm-config.json`. v1 configs auto-migrated to v2 on load:
```json
{
  "version": "2.0",
  "bots": {
    "warchief": {"provider": "openai", "model": "glm-5.2", "base_url": "https://ollama.com/v1"}
  }
}
```

## Default Config
- Ollama: qwen2.5:14b (fallback if no config present)
- Tested with: glm-5.2 via ollama-cloud (OpenAI-compatible API at `https://ollama.com/v1`)