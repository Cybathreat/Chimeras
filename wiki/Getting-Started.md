# Getting Started

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
pip install langgraph httpx openai anthropic
```

## First Run

### Option 1: Interactive Setup

```bash
python main.py
```

Prompts for mission name, objectives, scope, and rules of engagement. Creates the mission directory and engagement folder structure automatically.

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
# Interactive (human gate asks y/n before exploitation)
python main.py run --mission-dir mission_alpha

# Headless (auto-approve exploitation)
python main.py run --mission-dir mission_alpha --approve
```

### Check Status

```bash
python main.py status --mission-dir mission_alpha
```

Shows mission info, bot configurations, and engagement folder contents.

## What to Expect

A full pipeline run takes approximately 5-10 minutes depending on:
- LLM response latency
- Number of tools the LLM decides to run
- Tool execution time (nmap scans, nikto scans, etc.)

During the run, you'll see:
1. Each bot prints a banner with its name, role, and scope
2. LLM reasoning is streamed live to terminal
3. Tool commands and their results are logged
4. After Bloodhound, the human gate presents vulnerabilities found

After completion:
- `engagement/report/final_report.md` — the professional pentest report
- `engagement/raw/` — all raw tool output for audit
- `engagement/findings.md` — accumulated findings from all bots
- Per-bot `.md` files with detailed work logs

## Troubleshooting

### LLM call failed
Check API key and provider config. Verify `base_url` if using a custom gateway.

### SCOPE BLOCKED messages
This is normal — the LLM sometimes suggests tools outside a bot's category. The system blocks them and the LLM adjusts.

### Tool not found
The system only shows installed tools to the LLM. Install missing tools or the bot will skip them.

### JSON parse errors
The system has a robust JSON parser that handles markdown code blocks, truncated responses, and bare JSON objects. If parsing still fails, the bot reports the error and continues.