# Architecture

## Overview

Chimeras is a multi-agent AI penetration testing framework built on LangGraph. Each bot is a true AI agent — it uses an LLM to decide which tools to run, executes real Kali Linux tools via subprocess, analyzes raw output with the LLM, and writes structured findings to engagement files.

## Core Design Principles

1. **LLM is the brain** — no hardcoded fallback logic. If the LLM fails, the bot fails.
2. **Real tool execution** — every tool runs via subprocess against real targets. No mock data.
3. **Category-based scoping** — bots declare a tool category, not a tool list. The scope enforcer dynamically discovers installed tools.
4. **File-based communication** — bots share state through engagement files only. No direct bot-to-bot communication.
5. **Provider-agnostic** — any LLM provider. Custom gateway support via `base_url`.
6. **Human-in-loop** — hard gate between vulnerability detection and exploitation.

## Pipeline

```
WarChief → ARIA → Lisa → Bloodhound → [HUMAN GATE]
  → Pathologist → Surgeon → Magician → Thief → Bookkeeper → END

  (if denied at gate)
  → Bookkeeper → END
```

All bots run sequentially. LangGraph orchestrates the flow.

## Bot Reasoning Loop

Every bot inherits from `BaseBot` and follows the same 6-step loop:

1. **Wake** — resolve engagement directory, read previous bot findings from files
2. **Think** — LLM analyzes context, decides what tools to run (or skip)
3. **Execute** — run real Kali tools via subprocess (scope-enforced)
4. **Analyze** — LLM reads raw tool output, extracts structured findings
5. **Write** — bot file, findings.md, log.md, PoC files
6. **Sleep** — state update for graph flow

## State Schema

LangGraph shared state (`core/state.py`):

- `mission` — objectives, scope, RoE, target
- `swarm_config` — per-bot LLM provider assignments
- `reasoning_reports` — each bot's reasoning output
- `recon_report` — ARIA's passive recon findings
- `scan_report` — Lisa's port/service enumeration
- `vuln_report` — Bloodhound's scored vulnerability findings
- `active_sessions` — Surgeon/Magician's live exploit sessions
- `payloads` — Pathologist's payload manifest
- `exfil_report` — Thief's exfil log
- `movement_report` — Magician's privesc/lateral map
- `operation_ledger` — Bookkeeper's timestamped action log
- `human_approval` — exploitation phase gate flag
- `final_report` — Bookkeeper's final report

## File Structure

```
mission/engagement/
├── plan.md            # WarChief's engagement plan
├── log.md             # Timestamped action log (all bots)
├── findings.md        # Accumulated findings (all bots)
├── warchief.md        # Per-bot work logs
├── aria.md
├── lisa.md
├── bloodhound.md
├── pathologist.md
├── surgeon.md
├── magician.md
├── thief.md
├── bookkeeper.md
├── raw/               # Raw tool output (audit trail)
├── poc/               # Proof-of-concept artifacts
└── report/
    └── final_report.md  # Professional pentest report
```

## Graph Wiring

`graph.py` wires the LangGraph state machine:

- Entry point: `warchief`
- Linear edges: warchief → aria → lisa → bloodhound → human_approval
- Conditional edge: human_approval → pathologist (if approved) OR bookkeeper (if denied)
- Exploitation chain: pathologist → surgeon → magician → thief → bookkeeper → END

The `--approve` flag sets `auto_approve=True` which bypasses the interactive `input()` prompt for headless/piped runs.