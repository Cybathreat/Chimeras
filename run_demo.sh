#!/bin/bash
# Demo script — requires OLLAMA_API_KEY or OPENAI_API_KEY in environment
# Export your key before running: export OLLAMA_API_KEY=your-key-here

cd "$(dirname "$0")"
rm -rf mission_demo
.venv/bin/python main.py setup \
  --mission "Demo Operation" \
  --objectives "Full penetration test of target infrastructure" \
  --scope "scanme.nmap.org" \
  --roe "No DoS, no data destruction, authorized target only" \
  --dir mission_demo 2>&1
echo "n" | .venv/bin/python main.py run --mission-dir mission_demo 2>&1