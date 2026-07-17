# CLAUDE.md — Chimeras Development Context

## Project
Chimeras is an autonomous AI pentest swarm. 9 bots, each powered by an
independently assigned LLM, each reasoning autonomously about what tools
to run and what strategy to use. No hardcoded tool lists — bots declare
a tool category and the LLM picks tools dynamically.

## Stack
- Python 3.11+
- LangGraph (multi-agent orchestration)
- Provider-agnostic LLM routing (Anthropic/Google/Groq/OpenRouter/Ollama/OpenAI-compatible)
- Kali Linux tools executed via subprocess
- Custom gateway support (any OpenAI/Anthropic-compatible endpoint via `base_url`)

## Core Rules
- Every bot inherits from `core/base_bot.py`
- The LLM IS the brain — no hardcoded fallback logic
- Tools are NOT hardcoded in bot agents — bots declare a category, scope enforcer maps to installed tools
- Bots communicate ONLY through engagement files (plan.md, log.md, findings.md, per-bot .md)
- State is shared via `core/state.py` TypedDict
- Raw tool output saved to `engagement/raw/` for audit trail

## Bot Order (Linear Pipeline)
WarChief → ARIA → Lisa → Bloodhound → [HUMAN APPROVAL GATE]
→ Pathologist → Surgeon → Magician → Thief → Bookkeeper → END

If human denies exploitation: Bloodhound → Bookkeeper → END

## Human-in-Loop
Gate between Bloodhound and exploitation bots. Operator reviews vuln report.
`--approve` flag bypasses for headless/piped runs.

## Tool Scoping (Category-based, NOT hardcoded)
Bots declare a category in `core/scope.py` (`BOT_CATEGORIES`):
- ARIA → `passive_recon` (dig, whois, whatweb, wafw00f, subfinder, ...)
- Lisa → `active_scan` (nmap, nikto, gobuster, ffuf, wpscan, ...)
- Bloodhound → `vuln_detection` (nuclei, searchsploit, wapiti, ssh-audit, sslscan, ...)
- Pathologist → `payload_fab` (msfvenom, msfconsole, searchsploit, curl)
- Surgeon → `exploitation` (msfconsole, sqlmap, nc, python3, bash, ...)
- Magician → `privesc` (linpeas, find, cat, ssh, smbclient, ...)
- Thief → `exfiltration` (curl, wget, nc, tar, scp, rsync, ...)
- WarChief/Bookkeeper → `none` (no tool execution)

Tools are discovered dynamically via `shutil.which()`. LLM only sees installed tools.

## Package Structure
```
Chimeras/
├── core/
│   ├── base_bot.py       # Abstract bot — LLM reasoning loop + tool execution
│   ├── state.py          # LangGraph TypedDict state schema
│   ├── llm_router.py     # Universal LLM adapter — 6 providers + custom base_url
│   ├── tool_executor.py  # Subprocess wrapper with timeout + raw output capture
│   ├── scope.py          # Category-based tool scoping + dynamic discovery
│   ├── config.py         # Setup CLI + swarm-config.json manager
│   └── providers/        # Provider implementations
│       ├── anthropic.py  # Claude Opus/Sonnet/Haiku
│       ├── google.py     # Gemini
│       ├── groq.py       # Llama 3.3 70B / Mixtral
│       ├── openrouter.py # Any model via OpenRouter
│       ├── openai.py     # GPT-4o / any OpenAI-compatible endpoint
│       └── ollama.py     # Local Ollama
├── bots/
│   ├── warchief/agent.py    # Orchestrator — plans engagement
│   ├── aria/agent.py        # Passive recon
│   ├── lisa/agent.py        # Active scanning
│   ├── bloodhound/agent.py  # Vulnerability detection
│   ├── pathologist/agent.py # Payload fabrication
│   ├── surgeon/agent.py     # Exploitation
│   ├── magician/agent.py    # Privilege escalation
│   ├── thief/agent.py       # Data exfiltration
│   └── bookkeeper/agent.py  # Report generation
├── graph.py              # LangGraph wiring
├── main.py               # Entry point
└── mission_*/            # Per-operation workspace
    ├── swarm-config.json  # Per-bot LLM config
    ├── mission.md         # Objectives, scope, RoE
    └── engagement/
        ├── plan.md         # WarChief's plan
        ├── log.md          # Timestamped action log
        ├── findings.md     # Accumulated findings
        ├── *.md            # Per-bot work logs
        ├── raw/            # Raw tool output (audit trail)
        ├── poc/            # Proof-of-concept artifacts
        └── report/         # Final report
```

## Config
Per-bot config in `swarm-config.json`:
```json
{
  "bots": {
    "warchief": {"provider": "openai", "model": "glm-5.2", "base_url": "https://ollama.com/v1"},
    "aria": {"provider": "openai", "model": "glm-5.2", "base_url": "https://ollama.com/v1"}
  }
}
```
`base_url` enables any OpenAI-compatible gateway (Ollama Cloud, vLLM, LM Studio, etc.).

## Default Config
- Ollama: qwen2.5:14b (fallback if no config present)
- Tested with: glm-5.2 via ollama-cloud (OpenAI-compatible API at `https://ollama.com/v1`)