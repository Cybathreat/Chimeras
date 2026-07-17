# Chimeras v1.0 — Autonomous Reasoning Swarm Architecture

**Cyberian Defenses** | Multi-Agent AI Security Testing Framework

---

## 1. Overview

Chimeras is an autonomous AI hacking swarm for penetration testing. 9 bots, each powered by an independently assigned LLM, each reasoning autonomously about whether they are needed and what strategy to use.

### Stack
- Python 3.11+
- LangGraph (multi-agent orchestration)
- Provider-agnostic LLM routing (Anthropic/Google/Groq/OpenRouter/Ollama)
- Kali Linux tools executed via subprocess

---

## 2. Bot Roster

| Bot | Role | LLM Assignment |
|-----|------|----------------|
| WarChief | Supervisor/orchestrator | Claude Opus 4.6 (Anthropic) |
| ARIA | Passive recon | Ollama qwen2.5:14b |
| Lisa | Scanner strategy | Gemini 2.5 Flash (Google) |
| Bloodhound | Vuln hunter | Claude Sonnet 4.6 (Anthropic) |
| Surgeon | Exploitation | Claude Opus 4.6 (Anthropic) |
| Pathologist | Payload fabrication | Llama 3.3 70B (Groq) |
| Thief | Exfil | Ollama qwen2.5:14b |
| Magician | PrivEsc/lateral | Claude Sonnet 4.6 (Anthropic) |
| Bookkeeper | Logger/auditor | Ollama qwen2.5:7b |

### Fallback Chain
`groq` → `openrouter` → `ollama`

---

## 3. Autonomous Reasoning Loop (9 Steps)

| # | Phase | Description |
|---|-------|-------------|
| 1 | Wake | Bot spawned by WarChief, reads mission state and swarm-config.json |
| 2 | Connect | LLMRouter instantiates the configured provider |
| 3 | Reason | Bot sends mission context + role prompt to LLM, streams thinking live to terminal |
| 4 | Decide | Bot decides: needed or not needed, and what strategy to use |
| 5 | Recommend | Bot writes structured ReasoningReport to shared state |
| 6 | Wait | Bot awaits WarChief acknowledgment before executing (or self-executes if authorized) |
| 7 | Execute | Bot runs its tools based on its own chosen strategy |
| 8 | Report | Bot writes final output report to state, Bookkeeper logs it |
| 9 | Sleep | Bot signals completion, WarChief decides next node |

---

## 4. Shared State Schema (LangGraph TypedDict)

| Field | Type | Owner | Description |
|-------|------|-------|-------------|
| mission | dict | WarChief | Objectives, scope, RoE, emergency contacts |
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
| abort_flag | bool | WarChief | Emergency stop, kills all active bots |
| final_report | dict | Bookkeeper | Technical + executive final report |

---

## 5. LangGraph Graph Design

### Nodes
- warchief_node — supervisor, reads all reasoning reports, routes next node
- aria_node — passive recon reasoning + execution
- lisa_node — scan strategy reasoning + execution
- bloodhound_node — vuln detection reasoning + execution
- human_approval_node — interrupt: operator reviews Bloodhound report, approves exploitation
- pathologist_node — payload fabrication reasoning + generation (on demand)
- surgeon_node — exploitation reasoning + execution
- magician_node — privesc/lateral movement reasoning + execution
- thief_node — exfil strategy reasoning + execution
- bookkeeper_node — passive observer, always running as background task

### Conditional Edges
- warchief → aria: always (first node after mission init)
- aria → lisa: always (even if ARIA decides recon not needed)
- lisa → bloodhound: always
- bloodhound → human_approval: always (human must see vuln report before exploitation)
- human_approval → surgeon: only if human_approval == True
- human_approval → END: if human_approval == False (operation stops at recon/vuln phase)
- surgeon → [magician, thief]: parallel if both in scope
- surgeon → pathologist: on demand when custom payload needed
- [magician, thief] → warchief: both must complete before final report
- warchief → bookkeeper_final: triggers final report generation

### Human-in-the-Loop
LangGraph's `interrupt()` is placed at the human_approval_node. The graph pauses, WarChief presents the Bloodhound report to the operator, and waits for explicit approval before any bot attempts exploitation. This is a hard gate — no automatic bypass.

---

## 6. Python Package Structure

```
chimeras/
├── core/
│   ├── base_bot.py          # Abstract base — reasoning loop + live streaming
│   ├── state.py             # Shared TypedDict state schema
│   ├── llm_router.py        # Universal LLM adapter — routes to any provider
│   ├── config.py            # Project setup CLI + swarm-config.json manager
│   └── providers/
│       ├── anthropic.py     # Claude Opus/Sonnet/Haiku
│       ├── google.py        # Gemini 2.5 Flash / Pro
│       ├── groq.py          # Llama 3.3 70B / Mixtral
│       ├── openrouter.py    # Any model via OpenRouter
│       ├── openai.py        # GPT-4o / GPT-4 Turbo
│       └── ollama.py        # Local Ollama (DEFAULT)
├── warchief/
│   ├── __init__.py
│   ├── agent.py             # Supervisor node — orchestrates all bots
│   └── questionnaire.py     # Mission intake prompts
├── aria/
│   ├── __init__.py
│   └── agent.py             # Passive recon — reasons strategy, executes OSINT
├── lisa/
│   ├── __init__.py
│   └── agent.py             # Scanner — reasons optimal scan strategy
├── bloodhound/
│   ├── __init__.py
│   └── agent.py             # Vuln hunter — reasons CVE and misconfiguration strategy
├── surgeon/
│   ├── __init__.py
│   └── agent.py             # Exploitation — reasons target selection and exploit choice
├── pathologist/
│   ├── __init__.py
│   └── agent.py             # Payload fabrication — reasons best payload architecture
├── thief/
│   ├── __init__.py
│   └── agent.py             # Exfil — reasons covert channel selection
├── magician/
│   ├── __init__.py
│   └── agent.py             # PrivEsc — reasons attack path through AD/hosts
├── bookkeeper/
│   ├── __init__.py
│   └── agent.py             # Logger — passively observes all state transitions
├── templates/
│   ├── technical.j2         # Technical report template
│   └── executive.j2         # Executive report template
├── graph.py                 # LangGraph graph — nodes, edges, human-in-loop
├── main.py                  # Entry point — project setup + operation launch
├── CLAUDE.md                # Context file for Claude Code development
└── mission/                 # Operation workspace (per operation)
    ├── swarm-config.json    # Per-bot LLM assignments
    ├── soul.md              # Bot identities and behavioral constraints
    ├── mission.md           # Objectives, scope, RoE, contacts
    ├── active-sessions.md   # Live exploit sessions
    ├── payloads/            # Payload artifacts
    ├── exfil-staging/       # Staged exfil data (encrypted)
    └── operation-vault/     # Final archive
```

---

## 7. CLAUDE.md — Claude Code Context File

```markdown
# CLAUDE.md — Chimeras Development Context

## Project
Chimeras is an autonomous AI hacking swarm for penetration testing.
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
```

---

## 8. Recommended Build Order (Claude Code)

| # | What to Build | Prompt |
|---|---------------|--------|
| 1 | core/state.py | Build the shared TypedDict state schema from the architecture doc |
| 2 | core/llm_router.py | Build the universal LLM router with all 6 provider adapters |
| 3 | core/base_bot.py | Build the abstract BaseBot with reasoning loop and live streaming |
| 4 | core/config.py | Build the project setup CLI + model selection and swarm-config.json |
| 5 | providers/*.py | Implement all 6 provider classes with unified stream() interface |
| 6 | warchief/agent.py | Build WarChief as LangGraph supervisor node |
| 7 | bookkeeper/agent.py | Build Bookkeeper as background observer node |
| 8 | aria/agent.py | Build ARIA with passive recon reasoning prompt and OSINT tools |
| 9 | lisa/agent.py | Build Lisa with scan strategy reasoning and nmap/masscan execution |
| 10 | bloodhound/agent.py | Build Bloodhound with CVE reasoning and nuclei/openvas execution |
| 11 | surgeon/agent.py | Build Surgeon with exploitation reasoning and metasploit integration |
| 12 | pathologist/agent.py | Build Pathologist with payload reasoning and msfvenom execution |
| 13 | magician/agent.py | Build Magician with AD reasoning and impacket/bloodhound execution |
| 14 | thief/agent.py | Build Thief with exfil channel reasoning and covert transfer tools |
| 15 | graph.py | Wire the full LangGraph graph with all nodes, edges, and human interrupt |
| 16 | main.py | Build the entry point — setup CLI + operation launch |

---

## 9. Testing Strategy

1. Unit test each provider adapter with a simple ping prompt
2. Unit test each bot's reasoning loop with a mock mission
3. Integration test: full operation on a local test network (e.g., VulnHub VM)
4. The Bookkeeper's report is the final validation — if it's complete, the operation worked

---

**End of Document — Chimeras v2.0**
*Cyberian Defenses | Autonomous Reasoning Swarm Architecture*
