<div align="center">

<!-- HEADER -->
<h1>🔮 Chimeras</h1>

**Autonomous Adaptive AI Pentesting Swarm**

<p>
  10 AI agents. Each one reasons for itself.<br>
  Each one picks its own tools. Each one executes real Kali Linux commands against real targets.<br>
  <strong>No hardcoded logic. No mock data. The LLM is the brain.</strong>
</p>

<!-- BADGES -->
<p>
  <img src="https://img.shields.io/badge/Version-2.2-9B59B6?style=for-the-badge&logo=semver&logoColor=white" alt="v2.2">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/LangGraph-⚡-FF6B35?style=for-the-badge&logo=langchain&logoColor=white" alt="LangGraph">
  <img src="https://img.shields.io/badge/Kali-Linux-557C94?style=for-the-badge&logo=kali-linux&logoColor=white" alt="Kali Linux">
  <img src="https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge&logo=opensourceinitiative&logoColor=white" alt="MIT License">
</p>

<p>
  <a href="#-what-it-does">Overview</a> •
  <a href="#-bot-roster">Bots</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-quick-start">Install</a> •
  <a href="#-supported-llm-providers">Providers</a> •
  <a href="#-legal">Legal</a>
</p>

<p>
  <sub>Built by <a href="https://cyberian-defenses.com">Cyberian Defenses</a></sub>
</p>

---

</div>

## 📖 Overview

Chimeras runs a **full penetration test autonomously** with adaptive decision-making.

A WarChief agent acts as decision router — re-enters after every phase, adapts routing based on actual findings, loops back for deeper recon, pivots to lateral movement, handles failures gracefully. The swarm adapts in real-time.

```
Recon → Scan → Vuln Detection → [HUMAN GATE] → Exploit → Post-Exploit → Cleanup → Report
                ↑                                                    │
                └──── WarChief re-evaluates after each phase ────────┘
```

### ✨ Key Highlights

- **Adaptive AI routing** — WarChief re-enters after each phase with 12 routing decisions
- **Real tool execution** — every command runs via subprocess against real targets, no simulations
- **LLM is the brain** — no hardcoded fallback logic, bots reason autonomously
- **Provider-agnostic** — 6 LLM providers + custom gateway support
- **Two human-in-loop gates** — exploitation gate + lateral movement gate
- **Parallel vuln detection** — Bloodhound (infrastructure) + Wasp (web apps) run concurrently
- **Code-level scope enforcement** — target validation, shell injection blocking, destructive command blocklist
- **Full audit trail** — every decision logged, raw tool output saved, artifacts tracked

---

## 🔧 What It Does

| Phase | Action | Bot |
|-------|--------|-----|
| 1. **Recon** | Passive OSINT, DNS, WHOIS, web tech fingerprinting | ARIA |
| 2. **Scanning** | Port scans, service enumeration, web scanning | Lisa |
| 3. **Vuln Detection** | CVE matching, nuclei templates, SSL analysis | Bloodhound + Wasp |
| 4. **Human Gate** | Operator reviews findings before exploitation | — |
| 5. **Exploitation** | Payload generation, exploit execution | Pathologist → Surgeon |
| 6. **Post-Exploit** | Privilege escalation, lateral movement, exfiltration | Magician → Thief |
| 7. **Cleanup** | Artifacts tracked, removal attempted, failures flagged | Bookkeeper |
| 8. **Reporting** | Professional pentest report with CVSS scores, PoC, remediation | Bookkeeper |

WarChief re-evaluates after each phase. If recon finds nothing → loop back. If scanning finds zero services → pivot. If exploitation fails 3x → abort gracefully. The swarm adapts.

---

## 🤖 Bot Roster

| Bot | Role | Tool Category | Icon |
|-----|------|---------------|------|
| **WarChief** | Decision router — re-enters after each phase, routes dynamically | none | 🧠 |
| **ARIA** | Passive reconnaissance | `passive_recon` | 🕰️ |
| **Lisa** | Active scanning | `active_scan` | 🎯 |
| **Bloodhound** | Infrastructure vuln detection (SSL, CVEs, network services) | `vuln_detection` | 🩸 |
| **Wasp** | Web app vuln detection (XSS, CSRF, SQLi, SSTI, SSRF, LFI/RFI, IDOR) | `web_exploit` | 🐝 |
| **Pathologist** | Payload fabrication | `payload_fab` | 🧬 |
| **Surgeon** | Exploitation | `exploitation` | 🔪 |
| **Magician** | Privilege escalation & lateral movement | `privesc` | 🎩 |
| **Thief** | Data exfiltration | `exfiltration` | 🦹 |
| **Bookkeeper** | Report generation, cleanup & rollback | none | 📋 |

> Bloodhound and Wasp run **in parallel** during vuln detection. No human approval needed for detection — only for exploitation.

---

## 🏗️ Architecture

```
                    ┌──────────┐
                    │ WarChief │ ◄── re-enters after each phase
                    │ (router) │
                    └────┬─────┘
                         │ conditional edge (12 routing decisions)
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     ┌─────────┐   ┌─────────┐   ┌────────────────┐
     │  ARIA   │   │  Lisa   │   │ Bloodhound     │
     │ (recon) │   │ (scan)  │   │ + Wasp (PARALLEL)│
     └────┬────┘   └────┬────┘   └───────┬────────┘
          │              │                  │
          └──────────────┴──────────────────┘
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
```

### WarChief Routing Decisions (12)

| Decision | Meaning |
|----------|---------|
| `init` | Initial state — WarChief assesses mission parameters |
| `recon` | Route to ARIA for (deeper) reconnaissance |
| `scan` | Route to Lisa for (deeper) scanning |
| `vuln_detection` | Route to Bloodhound+Wasp for parallel vuln detection |
| `vulns_found_exploit` | Route to human gate, then exploitation |
| `insufficient_data_abort` | Not enough data, abort to report |
| `lateral_recon` | Pivot to internal recon (requires lateral gate) |
| `lateral_scan` | Scan internal targets (requires lateral gate) |
| `continue_exploit` | Continue exploitation with remaining vectors |
| `privesc` | Route to privilege escalation |
| `exfiltrate` | Route to data exfiltration |
| `report` | Route to Bookkeeper — mission complete or abort |

### Mission State Machine (11 states)

`init → recon → scanning → vuln_detection → exploitation_prep → exploitation → post_exploit → lateral_recon → lateral_scanning → reporting → complete`

---

## 🛡️ Key Design Principles

- **WarChief is a decision router** — re-enters after each phase, not a one-shot planner
- **LLM is the brain** — no hardcoded fallback logic. Safe fallback only for malformed LLM output
- **Real tool execution** — every tool runs via subprocess against real targets
- **Category-based scoping** — bots declare a tool *category*. Scope enforcer discovers installed tools dynamically
- **Code-level scope enforcement** — `TargetValidator` resolves IPs/hostnames, checks against CIDR scope
- **Shell injection blocked at code level** — metacharacters rejected for categories that don't need them
- **Destructive/DoS commands blocked at code level** — `rm -rf`, `mkfs`, `DROP TABLE`, flood-rate scan flags checked against RoE regardless of tool category
- **Every gate decision is logged** — exploitation and lateral-movement approvals written to `engagement/log.md` with timestamp, part of permanent mission record
- **File-based communication** — bots share state through engagement files only
- **Adaptive failure handling** — WAF detection, failed vector tracking, graceful abort (3+ failed exploits or 5 loops per phase → abort)
- **Artifact tracking & cleanup** — dropped tools/payloads tracked, removal attempted, failures flagged in report
- **Decision audit trail** — every WarChief routing decision logged in report + `warchief_decisions.json`

---

## 🚀 Quick Start

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
    "wasp":        {"provider": "openai", "model": "gpt-4o"},
    "surgeon":     {"provider": "openai", "model": "gpt-4o"},
    "pathologist": {"provider": "openai", "model": "gpt-4o"},
    "magician":    {"provider": "openai", "model": "gpt-4o"},
    "thief":       {"provider": "openai", "model": "gpt-4o"},
    "bookkeeper":  {"provider": "openai", "model": "gpt-4o"}
  }
}
```

<details>
<summary>📖 Using a custom gateway (Ollama Cloud, vLLM, LM Studio, any OpenAI-compatible API)</summary>

```json
{
  "bots": {
    "warchief": {
      "provider": "openai",
      "model": "glm-5.2",
      "base_url": "https://ollama.com/v1"
    }
  }
}
```

Set API keys via environment:

```bash
export OPENAI_API_KEY="sk-..."
# or for Ollama Cloud:
export OLLAMA_API_KEY="ollama-..."
```

</details>

### Run

```bash
# Interactive setup with TUI wizard (checks LLM connectivity for all 10 bots)
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
├── wasp.md
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

---

## 🔩 Tool Scoping

Bots don't have hardcoded tool lists. They declare a category:

```python
BOT_CATEGORIES = {
    "aria": "passive_recon",
    "lisa": "active_scan",
    "bloodhound": "vuln_detection",
    "wasp": "web_exploit",
    ...
}
```

The `ScopeEnforcer` maps categories to tool sets, discovers which tools are actually installed via `shutil.which()`, and tells the LLM only about available tools.

**Three-tier enforcement:**

1. **Category check** — tool must be in bot's allowed set
2. **Shell metacharacter check** — injection blocked for categories that don't need shell
3. **Target validation** — `TargetValidator` resolves IPs/hostnames, rejects out-of-scope targets

---

## 🌐 Supported LLM Providers

| Provider | Models | `base_url` Support |
|----------|--------|---------------------|
| **OpenAI** | GPT-4o, GPT-4 Turbo | Yes — any OpenAI-compatible endpoint |
| **Anthropic** | Claude Opus, Sonnet, Haiku | Yes |
| **Google** | Gemini 2.5 Flash/Pro | No |
| **Groq** | Llama 3.3 70B, Mixtral | No |
| **OpenRouter** | Any model | No |
| **Ollama** | Any local model | No |

Use `base_url` to route to custom gateways: Ollama Cloud, vLLM, LM Studio, Azure OpenAI, etc.

---

## 📋 Changelog

See [CHANGELOG.md](CHANGELOG.md) for full version history.

### v2.2

- Destructive/DoS command blocklist enforced at code level — `rm -rf`, `mkfs`, `DROP TABLE`, flood-rate flags blocked regardless of tool category
- Every gate decision now logged to `engagement/log.md` with timestamp

### v2.0

- WarChief becomes adaptive decision router (re-enters after each phase)
- 12 routing decisions, 11-state mission state machine
- Parallel vuln detection (Bloodhound + Wasp)
- Lateral movement with second human gate
- Failure handling: WAF/IPS detection, failed vector tracking, graceful abort
- Artifact tracking & cleanup
- Decision audit trail
- TUI pre-flight wizard with live LLM connectivity check
- v1 config auto-migration

---

## ⚖️ Legal

**For authorized security testing only.**

You must have explicit written permission to test any target. Two human approval gates exist to enforce this — do not bypass them in production use.

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

**Chimeras v2.2** — [Cyberian Defenses](https://cyberian-defenses.com)

<sub>🔮 10 minds. One swarm. Zero hardcoded logic.</sub>

</div>