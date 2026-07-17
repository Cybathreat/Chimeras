#!/bin/bash
export OLLAMA_API_KEY=$(grep -v '^#' ~/.hermes/.env | grep OLLAMA_API_KEY | head -1 | cut -d= -f2-)
export OPENAI_API_KEY=$OLLAMA_API_KEY
cd /root/chimeras
rm -rf mission_demo
.venv/bin/python main.py setup --mission "Demo Operation" --objectives "Full penetration test of target infrastructure" --scope "scanme.nmap.org" --roe "No DoS, no data destruction, authorized target only" --dir mission_demo 2>&1
echo "n" | .venv/bin/python main.py run --mission-dir mission_demo 2>&1