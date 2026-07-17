# Chimeras

**Autonomous AI Penetration Testing Swarm**

9 AI agents. Each one reasons for itself. Each one picks its own tools. Each one executes real Kali Linux commands against real targets. No hardcoded logic. No mock data. The LLM is the brain.

Built by [Cyberian Defenses](https://cyberian-defenses.com).

---

## What It Does

Chimeras runs a full penetration test pipeline autonomously:

1. **Recon** — passive OSINT, DNS, WHOIS, web tech fingerprinting
2. **Scanning** — port scans, service enumeration, web scanning
3. **Vulnerability Detection** — CVE matching, nuclei templates, SSL analysis
4. **Human Approval Gate** — operator reviews findings before exploitation
5. **Exploitation** — payload generation, exploit execution
6. **Post-Exploitation** — privilege escalation, data exfiltration
7. **Reporting** — professional pentest report with CVSS scores, PoC, remediation

Every bot uses an LLM to decide what tools to run, analyzes raw tool output, and writes structured findings. Bots communicate only through files. No direct bot-to-bot chatter.

## Bot Roster

| Bot | Role | Tool Category |
|-----|------|---------------|
| WarChief | Orchestrator — plans the engagement | none |
| ARIA | Passive reconnaissance | passive_recon |
| Lisa | Active scanning | active_scan |
| Bloodhound | Vulnerability detection | vuln_detection |
| Pathologist | Payload fabrication | payload_fab |
| Surgeon | Exploitation | exploitation |
| Magician | Privilege escalation | privesc |
| Thief | Data exfiltration | exfiltration |
| Bookkeeper | Report generation | none |

## Pipeline

```
WarChief → ARIA → Lisa → Bloodhound → [HUMAN GATE]
  → Pathologist → Surgeon → Magician → Thief → Bookkeeper → END

  (if denied at gate)
  → Bookkeeper → END
```

## Key Design Principles

- **LLM is the brain** — no hardcoded fallback logic. If the LLM fails, the bot fails.
- **Real tool execution** — every tool runs via subprocess against real targets. No simulated data.
- **Category-based scoping** — bots declare a tool *category*, not a tool list. The scope enforcer dynamically discovers installed tools and checks commands against the bot's category. Adding a new tool = add it to the category, every bot in that category gets it.
- **File-based communication** — bots share state through engagement files only. No direct bot-to-bot communication.
- **Provider-agnostic** — any LLM provider (Anthropic, Google, Groq, OpenRouter, OpenAI, Ollama). Custom gateway support via `base_url` for any OpenAI-compatible endpoint.
- **Human-in-loop** — hard gate between vulnerability detection and exploitation. No automatic bypass.

## Quick Start

### Prerequisites

- Python 3.11+
- Kali Linux (or install tools individually: nmap, nikto, nuclei, gobuster, sqlmap, etc.)
- An LLM API key (any supported provider)

### Install

```bash
git clone https://github.com/Cybathreat/Chimeras.git
cd Chimeras
python -m venv .venv
source .venv/bin/activate
pip install langgraph httpx openai anthropic
```

### Configure

Create a `swarm-config.json` in your mission directory:

```json
{
  "version": "1.0",
  "mission_name": "My Pentest",
  "bots": {
    "warchief":   {"provider": "openai", "model": "gpt-4o"},
    "aria":        {"provider": "openai", "model": "gpt-4o"},
    "lisa":        {"provider": "openai", "model": "gpt-4o"},
    "bloodhound":  {"provider": "openai", "model": "gpt-4o"},
    "surgeon":     {"provider": "openai", "model": "gpt-4o"},
    "pathologist": {"provider": "openai", "model": "gpt-4o"},
    "magician":    {"provider": "openai", "model": "gpt-4o"},
    "thief":       {"provider": "openai", "model": "gpt-4o"},
    "bookkeeper":  {"provider": "openai", "model": "gpt-4o"}
  }
}
```

Using a custom gateway (Ollama Cloud, vLLM, LM Studio, any OpenAI-compatible API):

```json
{
  "bots": {
    "warchief": {"provider": "openai", "model": "glm-5.2", "base_url": "https://ollama.com/v1"}
  }
}
```

Set API keys via environment:

```bash
export OPENAI_API_KEY="sk-..."
# or for Ollama Cloud:
export OLLAMA_API_KEY="ollama-..."
```

### Run

```bash
# Interactive setup (prompts for mission name, objectives, scope, RoE)
python main.py

# Setup with flags
python main.py setup --mission "Op Alpha" --objectives "Pentest web app" --scope "10.10.10.0/24" --roe "No DoS"

# Run operation (interactive human gate)
python main.py run --mission-dir mission

# Run operation (auto-approve exploitation — headless/piped)
python main.py run --mission-dir mission --approve

# Check status
python main.py status --mission-dir mission
```

### Output

After a run, the engagement folder contains:

```
mission/engagement/
├── plan.md            # WarChief's engagement plan
├── log.md             # Timestamped action log (all bots)
├── findings.md        # Accumulated findings (all bots)
├── warchief.md        # Per-bot work logs
├── aria.md
├── lisa.md
├── bloodhound.md
├── ...
├── raw/               # Raw tool output (audit trail)
├── poc/               # Proof-of-concept artifacts
└── report/
    └── final_report.md  # Professional pentest report
```

The final report includes:
- Scope and executive summary
- Findings table with severity, CVSS scores, status
- Per-finding: description → risks → attack vectors → proof of concept → proof of existence → remediation plan

## Architecture

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌────────────┐    ┌────────────┐
│WarChief │───▶│  ARIA   │───▶│  Lisa   │───▶│Bloodhound │───▶│ HUMAN GATE │
│ (plan)  │    │(recon)  │    │ (scan)  │    │ (vulns)   │    │   y / n    │
└─────────┘    └─────────┘    └─────────┘    └────────────┘    └─────┬──────┘
                                                                    │
                    ┌───────────────────────────────────────────────┘
                    │
                    ▼
              ┌───────────┐   ┌────────┐   ┌──────────┐   ┌───────┐   ┌────────────┐
              │Pathologist│──▶│Surgeon │──▶│Magician  │──▶│ Thief │──▶│Bookkeeper  │
              │(payloads) │   │(exploit)│   │(privesc) │   │(exfil)│   │(report)    │
              └───────────┘   └────────┘   └──────────┘   └───────┘   └────────────┘
```

Each bot follows the same reasoning loop:

1. **Wake** — read engagement files from previous bots
2. **Think** — LLM analyzes context, decides strategy and tool selection
3. **Execute** — real Kali tools run via subprocess (scope-enforced)
4. **Analyze** — LLM reads raw tool output, extracts structured findings
5. **Write** — findings, logs, and PoC saved to engagement folder
6. **Sleep** — next bot picks up

## Tool Scoping

Bots don't have hardcoded tool lists. They declare a category:

```python
BOT_CATEGORIES = {
    "aria": "passive_recon",
    "lisa": "active_scan",
    "bloodhound": "vuln_detection",
    ...
}
```

The `ScopeEnforcer` maps categories to tool sets, discovers which tools are actually installed on the system, and tells the LLM only about available tools. If a bot tries to run a tool outside its category, the command is blocked before execution.

## Supported LLM Providers

| Provider | Models | `base_url` Support |
|----------|--------|---------------------|
| OpenAI | GPT-4o, GPT-4 Turbo | Yes — any OpenAI-compatible endpoint |
| Anthropic | Claude Opus, Sonnet, Haiku | Yes |
| Google | Gemini 2.5 Flash/Pro | No |
| Groq | Llama 3.3 70B, Mixtral | No |
| OpenRouter | Any model | No |
| Ollama | Any local model | No |

Use `base_url` to route to custom gateways: Ollama Cloud, vLLM, LM Studio, Azure OpenAI, etc.

## Legal

For authorized security testing only. You must have explicit written permission to test any target. The human approval gate exists to enforce this — do not bypass it in production use.

## License

MIT — see [LICENSE](LICENSE).

---

**Chimeras** — Cyberian Defenses