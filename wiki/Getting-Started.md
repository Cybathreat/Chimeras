# Getting Started (v2)

## Prerequisites

- Python 3.11+
- Kali Linux recommended (or install tools individually)
- An LLM API key

### Required Kali Tools

The system dynamically discovers which tools are installed. Missing tools are reported but don't crash the system. Bots simply can't use tools that aren't installed.

Core tools: nmap, nikto, nuclei, gobuster, whatweb, sqlmap, ssh-audit, sslscan, testssl, wafw00f, wapiti

Install on Kali:
```bash
sudo apt update && sudo apt install -y nmap nikto gobuster whatweb sqlmap sslscan testssl ncat
```

nuclei (via Go):
```bash
go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
```

## Installation

```bash
git clone https://github.com/Cybathreat/Chimeras.git
cd Chimeras
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Pick your LLM provider SDK (only what you configure):
pip install anthropic      # or: google-genai / groq / openai — Ollama needs no SDK

# Dev only (tests + lint):
pip install -r requirements-dev.txt
```

## TUI Pre-Flight Wizard (v2)

When you run `python main.py`, a Rich-based TUI wizard launches automatically. It performs a 3-step pre-flight check:

1. **Config check** — verifies `swarm-config.json` exists and is valid. v1 configs are auto-migrated to v2.
2. **LLM connectivity** — tests all 9 bot LLM connections live, shows a table with status and latency for each.
3. **Summary** — shows mission parameters, bot configs, and asks for confirmation before launching.

To skip the wizard (CI/headless):
```bash
python main.py run --mission-dir mission --approve --skip-wizard
```

## First Run

### Option 1: Interactive Setup

```bash
python main.py
```

The TUI wizard launches, checks LLM connectivity for all 9 bots, and prompts for mission name, objectives, scope, and rules of engagement. Creates the mission directory and engagement folder structure automatically.

### Option 2: CLI Setup

```bash
python main.py setup \
  --mission "Op Alpha" \
  --objectives "Full pentest of web application and infrastructure" \
  --scope "10.10.10.0/24" \
  --roe "No DoS, no social engineering, authorized testing only" \
  --dir mission_alpha
```

### Run the Operation

```bash
# Interactive (human gates ask y/n before exploitation and lateral movement)
python main.py run --mission-dir mission_alpha

# Headless (auto-approve both gates)
python main.py run --mission-dir mission_alpha --approve

# Headless + skip wizard
python main.py run --mission-dir mission_alpha --approve --skip-wizard
```

### Check Status

```bash
python main.py status --mission-dir mission_alpha
```

Shows mission info, bot configurations, and engagement folder contents.

## What to Expect

A full v2 adaptive run takes approximately 10-30 minutes depending on:
- LLM response latency
- Number of routing loops (WarChief can loop back for deeper recon)
- Number of tools the LLM decides to run
- Tool execution time (nmap scans, nikto scans, etc.)
- Whether lateral movement is triggered

During the run, you'll see:
1. TUI wizard (if not skipped): config check, LLM connectivity table, summary
2. Each bot prints a banner with its name, role, and scope
3. LLM reasoning is streamed live to terminal
4. Tool commands and their results are logged
5. WarChief routing decisions are logged with reasoning
6. After Bloodhound, the exploitation gate presents vulnerabilities found
7. Before any lateral pivot, the lateral gate presents internal targets discovered

After completion:
- `engagement/report/final_report.md` — the professional pentest report with decision audit trail and cleanup status
- `engagement/warchief_decisions.json` — machine-readable decision log
- `engagement/raw/` — all raw tool output for audit
- `engagement/findings.md` — accumulated findings from all bots
- Per-bot `.md` files with detailed work logs

## Troubleshooting

### LLM call failed
Check API key and provider config. Verify `base_url` if using a custom gateway. The TUI wizard will show which bots fail connectivity.

### SCOPE BLOCKED messages
This is normal — the 3-tier scope enforcer blocks out-of-category tools, shell injection, and out-of-scope targets. The LLM sees the blocked result and adjusts.

### WarChief fallback
If WarChief's LLM output is malformed, the system defaults to a safe `report` route. Check `warchief.md` for the fallback reason. This is by design — the engagement degrades safely.

### Tool not found
The system only shows installed tools to the LLM. Install missing tools or the bot will skip them.

### JSON parse errors
The system has a robust JSON parser that handles markdown code blocks, truncated responses, and bare JSON objects. If parsing still fails, the bot reports the error and continues.

### Config migration
v1 `swarm-config.json` files are auto-migrated to v2 on load. You'll see a migration message in the TUI wizard. No manual action needed.