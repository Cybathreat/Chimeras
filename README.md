# Chimeras v2.0

**Autonomous Adaptive AI Pentesting Swarm**

9 AI agents. Each one reasons for itself. Each one picks its own tools. Each one executes real Kali Linux commands against real targets. No hardcoded logic. No mock data. The LLM is the brain.

**v2**: WarChief is now a decision router — re-enters after every phase, adapts routing based on actual findings, loops back for deeper recon, pivots to lateral movement, handles failures gracefully.

Built by [Cyberian Defenses](https://cyberian-defenses.com).

---

## What It Does

Chimeras runs a full penetration test autonomously with adaptive decision-making:

1. **Recon** — passive OSINT, DNS, WHOIS, web tech fingerprinting
2. **Scanning** — port scans, service enumeration, web scanning
3. **Vulnerability Detection** — CVE matching, nuclei templates, SSL analysis
4. **Human Approval Gate** — operator reviews findings before exploitation
5. **Exploitation** — payload generation, exploit execution
6. **Post-Exploitation** — privilege escalation, lateral movement, data exfiltration
7. **Cleanup & Rollback** — artifacts tracked, removal attempted, failures flagged in report
8. **Reporting** — professional pentest report with CVSS scores, PoC, remediation, decision audit trail

WarChief re-evaluates after each phase and routes dynamically. If recon finds nothing, it can loop back. If scanning finds zero services, it pivots. If exploitation fails 3x, it aborts gracefully. The swarm adapts.

## Bot Roster

| Bot | Role | Tool Category |
|-----|------|---------------|
| WarChief | Decision router — re-enters after each phase, routes dynamically | none |
| ARIA | Passive reconnaissance | passive_recon |
| Lisa | Active scanning | active_scan |
| Bloodhound | Vulnerability detection | vuln_detection |
| Pathologist | Payload fabrication | payload_fab |
| Surgeon | Exploitation | exploitation |
| Magician | Privilege escalation & lateral movement | privesc |
| Thief | Data exfiltration | exfiltration |
| Bookkeeper | Report generation, cleanup & rollback | none |

## Architecture (v2 — Adaptive Graph)

```
                    ┌──────────┐
                    │ WarChief │ ◄── re-enters after each phase
                    │ (router) │
                    └────┬─────┘
                         │ conditional edge (11 routing decisions)
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     ┌─────────┐   ┌─────────┐   ┌────────────┐
     │  ARIA   │   │  Lisa   │   │ Bloodhound │
     │ (recon) │   │ (scan)  │   │  (vulns)   │
     └────┬────┘   └────┬────┘   └─────┬──────┘
          │              │              │
          └──────────────┴──────────────┘
                         │
                    ┌────▼─────┐
                    │HUMAN GATE│ ◄── exploitation approval
                    └────┬─────┘
                         │ (approved)
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   ┌───────────┐  ┌────────┐    ┌──────────┐
   │Pathologist│  │Surgeon │    │ Magician │
   │(payloads) │  │(exploit)│   │(privesc) │
   └───────────┘  └────────┘    └──────────┘
                                      │
                                ┌─────▼─────┐
                                │  Thief    │
                                │ (exfil)   │
                                └─────┬─────┘
                                      │
                                ┌─────▼──────┐
                                │Bookkeeper  │
                                │(report+    │
                                │ cleanup)   │
                                └────────────┘

  Loopback paths: WarChief can route back to ARIA/Lisa for deeper recon
  Lateral gate: second human approval before any internal pivot
  Abort: 3+ failed exploits or 5 loops per phase → Bookkeeper
```

### WarChief Routing Decisions (11)

| Decision | Meaning |
|----------|---------|
| `recon` | Route to ARIA for (deeper) reconnaissance |
| `scan` | Route to Lisa for (deeper) scanning |
| `vulns_found_exploit` | Route to human gate, then exploitation |
| `insufficient_data_abort` | Not enough data, abort to report |
| `lateral_recon` | Pivot to internal recon (requires lateral gate) |
| `lateral_scan` | Scan internal targets (requires lateral gate) |
| `pivot_lateral_recon` | Full pivot — triggers lateral approval gate |
| `exploit` | Route to exploitation chain |
| `privesc` | Route to privilege escalation |
| `exfil` | Route to data exfiltration |
| `report` | Route to Bookkeeper — mission complete or abort |

### Mission State Machine (11 states)

`init → recon → scanning → vuln_detection → exploitation_prep → exploitation → post_exploit → lateral_recon → lateral_scanning → reporting → complete`

## Key Design Principles (v2)

- **WarChief is a decision router** — re-enters after each phase, not a one-shot planner
- **LLM is the brain** — no hardcoded fallback logic. Safe fallback only for malformed LLM output
- **Real tool execution** — every tool runs via subprocess against real targets
- **Category-based scoping** — bots declare a tool *category*. Scope enforcer discovers installed tools dynamically
- **Code-level scope enforcement** — `TargetValidator` resolves IPs/hostnames, checks against CIDR scope. Not a prompt instruction
- **Shell injection blocked at code level** — metacharacters rejected for categories that don't need them
- **File-based communication** — bots share state through engagement files only
- **Provider-agnostic** — any LLM provider. Custom gateway support via `base_url`
- **Two human-in-loop gates** — exploitation gate + lateral movement gate
- **Adaptive failure handling** — WAF detection, failed vector tracking, graceful abort
- **Artifact tracking & cleanup** — dropped tools/payloads tracked, removal attempted, failures flagged in report
- **Decision audit trail** — every WarChief routing decision logged in report + JSON

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
pip install langgraph httpx openai anthropic rich
```

### Configure

Create a `swarm-config.json` in your mission directory. v1 configs are auto-migrated to v2 on load:

```json
{
  "version": "2.0",
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
# Interactive setup with TUI wizard (checks LLM connectivity for all 9 bots)
python main.py

# Setup with flags
python main.py setup --mission "Op Alpha" --objectives "Pentest web app" --scope "10.10.10.0/24" --roe "No DoS"

# Run operation (interactive human gates)
python main.py run --mission-dir mission

# Run operation (auto-approve exploitation + lateral — headless/piped)
python main.py run --mission-dir mission --approve

# Skip the TUI wizard (headless/CI)
python main.py run --mission-dir mission --approve --skip-wizard

# Check status
python main.py status --mission-dir mission
```

### Output

After a run, the engagement folder contains:

```
mission/engagement/
├── plan.md                    # WarChief's plan + decision audit trail
├── log.md                     # Timestamped action log (all bots)
├── findings.md                # Accumulated findings (all bots)
├── warchief.md                # Per-bot work logs
├── aria.md
├── lisa.md
├── bloodhound.md
├── ...
├── warchief_decisions.json    # Machine-readable decision audit log
├── raw/                       # Raw tool output (audit trail)
├── poc/                       # Proof-of-concept artifacts
└── report/
    └── final_report.md        # Professional pentest report + cleanup status
```

The final report includes:
- Scope and executive summary
- Engagement flow (all WarChief routing decisions with reasoning)
- Findings table with severity, CVSS scores, status
- Per-finding: description → risks → attack vectors → proof of concept → proof of existence → remediation
- Decision metrics (total recon cycles, scanning cycles, exploitation cycles)
- Cleanup status (artifacts removed, artifacts that couldn't be cleaned)
- Mission outcome (complete, scope exhausted, authorization issues, target hardened)

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

The `ScopeEnforcer` maps categories to tool sets, discovers which tools are actually installed, and tells the LLM only about available tools. Three-tier enforcement:

1. **Category check** — tool must be in bot's category
2. **Shell metacharacter check** — injection blocked for categories that don't need shell
3. **Target validation** — `TargetValidator` resolves IPs/hostnames, rejects out-of-scope targets

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

For authorized security testing only. You must have explicit written permission to test any target. Two human approval gates exist to enforce this — do not bypass them in production use.

## License

MIT — see [LICENSE](LICENSE).

---

**Chimeras v2.0** — Cyberian Defenses