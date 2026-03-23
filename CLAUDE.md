# CLAUDE.md — Swarmbots Development Context

## Project
Swarmbots is an autonomous AI hacking swarm for penetration testing.
9 bots, each powered by an independently assigned LLM, each reasoning
autonomously about whether they are needed and what strategy to use.

## Stack
- Python 3.11+
- LangGraph (multi-agent orchestration)
- Provider-agnostic LLM routing (Anthropic/Google/Groq/OpenRouter/Ollama)
- Kali Linux tools executed via subprocess

## Core Rules
- Every bot inherits from core/base_bot.py
- Every bot streams its reasoning LIVE to terminal before executing
- State is shared via core/state.py TypedDict
- No bot communicates with another bot directly — only via state
- LLM provider is resolved at runtime from mission/swarm-config.json
- Default provider: ollama with qwen2.5 if no config present

## Bot Order
WarChief → ARIA → Lisa → Bloodhound → [HUMAN APPROVAL]
  → Pathologist (on demand) → Surgeon → Magician + Thief (parallel)
  → Bookkeeper (always running, first spawned, last killed)

## Package Structure
```
swarmbots/
├── core/
│   ├── state.py          # TypedDict state schema
│   ├── llm_router.py     # 6 provider adapters
│   ├── base_bot.py       # Abstract BaseBot
│   ├── config.py         # Setup CLI + config manager
│   └── providers/        # All 6 provider classes
├── warchief/agent.py     # Supervisor
├── aria/agent.py         # Passive recon
├── lisa/agent.py         # Scanner
├── bloodhound/agent.py   # Vuln hunter
├── surgeon/agent.py      # Exploitation
├── pathologist/agent.py  # Payload fabrication
├── thief/agent.py        # Exfil
├── magician/agent.py     # PrivEsc/lateral
├── bookkeeper/agent.py   # Logger/auditor
├── graph.py              # LangGraph wiring
├── main.py               # Entry point
└── mission/              # Operation workspace
```

## Human-in-Loop
LangGraph interrupt() at bloodhound → surgeon edge.
Exploitation requires explicit human approval. No bypass.

## Default Config
- Ollama: qwen2.5:14b (ARIA, Thief, Bookkeeper)
- Anthropic: claude-opus-4-6 (WarChief, Surgeon)
- Anthropic: claude-sonnet-4-6 (Bloodhound, Magician)
- Google: gemini-2.5-flash (Lisa)
- Groq: llama-3.3-70b (Pathologist)
