"""
Chimeras v2.0 — Thief Agent

Data exfiltration specialist. Extracts data from compromised systems.
Scope: curl, wget, nc, python3, tar, gzip, scp

v2 Phase 4: Failure tracking for exfiltration attempts.
  - Tracks failed exfil vectors in failed_vectors
  - Reports partial success (some data exfiled, some failed)
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class Thief(BaseBot):
    """Thief — Data Exfiltration Specialist"""

    bot_name = "thief"
    role_description = "data exfiltration and covert transfer specialist — identifies valuable data, stages and transfers covertly"
    scope_description = "Data exfiltration ONLY. Identifies and extracts valuable data. NO exploitation, NO privilege escalation."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with exfil findings.

        v2 Phase 4: Track failed exfil attempts.
        """
        try:
            structured = analysis.get("structured_data", {})
            if not isinstance(structured, dict):
                structured = {}

            self.state["exfil_report"] = structured
            self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision

            # ─── Track failed exfil attempts ───
            failed = self.state.get("failed_vectors", [])
            if not isinstance(failed, list):
                failed = []

            for key in ("failed_transfers", "errors", "blocked_exfil"):
                found = structured.get(key, [])
                if isinstance(found, list):
                    for item in found:
                        if isinstance(item, dict):
                            failed.append({
                                "target": item.get("target", item.get("host", "unknown")),
                                "tool": item.get("tool", self.bot_name),
                                "error": item.get("error", item.get("reason", "unknown")),
                                "timestamp": item.get("timestamp", ""),
                            })

            # Check tool_results for failures
            for result in tool_results:
                if isinstance(result, dict) and not result.get("success", True):
                    cmd = result.get("command", "")
                    tool_name = cmd.split()[0] if cmd else self.bot_name
                    failed.append({
                        "target": self.state.get("mission", {}).get("target", "unknown"),
                        "tool": tool_name,
                        "error": result.get("stderr", "exfil failed")[:200],
                        "timestamp": "",
                    })

            self.state["failed_vectors"] = failed

        except Exception as e:
            print(f"[THIEF] _update_state error: {e}")
            try:
                self.state["exfil_report"] = analysis.get("structured_data", {})
                self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision
            except Exception:
                pass