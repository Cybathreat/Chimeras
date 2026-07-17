"""
Chimeras v1.0 — WarChief Agent

Supervisor/orchestrator. Reads engagement files, decides next bot,
writes strategic plan. No tool execution — file I/O only.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import json

from core.base_bot import BaseBot
from core.state import SwarmState


class WarChief(BaseBot):
    """WarChief — Supervisor and Orchestrator. File I/O only, no tools."""

    bot_name = "warchief"
    role_description = "swarm supervisor and orchestrator — reads all bot reports, decides next action, writes engagement plan"
    scope_description = "Orchestrator ONLY. Reads engagement files, writes plan.md, coordinates bot flow. NO tool execution."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    def _build_system_prompt(self) -> str:
        """Override — WarChief decides flow, doesn't run tools."""
        return f"""You are {self.bot_name}, {self.role_description}.

## Your Scope
{self.scope_description}

## Pipeline Order
WarChief → ARIA (recon) → Lisa (scan) → Bloodhound (vuln) → [HUMAN APPROVAL]
→ Pathologist (payloads) → Surgeon (exploit) → Magician (privesc) → Thief (exfil) → Bookkeeper (report)

## Your Task
1. Read the engagement files to understand what bots have reported
2. Assess the current mission phase
3. Write a strategic plan for the next phase
4. Decide which bot should run next

## Response Format
Respond ONLY with a JSON block:
```json
{{
  "needed": true,
  "strategy": "brief description of coordination approach",
  "confidence": 0.95,
  "reasoning": "why you are needed and what you will coordinate",
  "commands": [],
  "next_bot": "name of the next bot to activate (or 'END' if mission complete)",
  "mission_phase": "current phase: init/recon/scan/vuln/exploitation/post-exploit/report/complete",
  "plan_content": "markdown strategic plan for plan.md"
}}
```
No other text. Just the JSON."""

    def _build_analysis_prompt(self, raw_output: str, context: str) -> str:
        """WarChief doesn't analyze tool output — it writes the plan."""
        return f"""## Current Engagement State

{context}

## Your Task
Based on the engagement files above, determine:
1. What phase are we in?
2. What has been completed?
3. What bot should run next?
4. Write a strategic plan update for plan.md"""

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with WarChief's coordination."""
        # Write plan to plan.md
        plan_content = decision.get("plan_content", analysis.get("plan_content", ""))
        if plan_content:
            plan_path = self.engagement_dir / "plan.md"
            existing = plan_path.read_text() if plan_path.exists() else ""
            plan_path.write_text(existing + f"\n\n## WarChief Assessment ({datetime.utcnow().isoformat()})\n\n{plan_content}\n")

        self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision