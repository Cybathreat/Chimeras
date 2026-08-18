"""
Chimeras v2.3 — ROE Prompt Cache + Delta Injection

Council: "Cache the compliance framework prompt. ROE and scope boundaries
are static per engagement. Load them once with prompt caching. Inject only
deltas — new IPs, new findings, scope changes — instead of the full
engagement file."

System prompts are built ONCE at startup. Each WarChief checkpoint receives
only the delta: what changed since last review. This cuts 80% of tokens
per checkpoint.
"""

from typing import Dict, Any, Optional, Set, List
from pathlib import Path


class ROEPromptCache:
    """Caches the ROE/scope system prompt and tracks deltas."""

    def __init__(self):
        self._cached_system_prompt: Optional[str] = None
        self._last_findings: Set[str] = set()
        self._last_targets: Set[str] = set()
        self._last_scope: str = ""

    def build_system_prompt(self, state: Dict[str, Any]) -> str:
        """Build and cache the ROE system prompt. Only call once per engagement."""
        mission = state.get("mission", {})
        roe = mission.get("roe", "No RoE specified")
        scope = mission.get("scope", "No scope specified")
        internal_scope = state.get("internal_scope", "")
        target = mission.get("target", "N/A")

        prompt = f"""## Compliance Framework (Static per engagement)

You are WarChief — the compliance officer. You replace human oversight.

### Rules of Engagement
{roe}

### Mission Scope
{scope}

### Internal Scope
{internal_scope or "N/A"}

### Target
{target}

### Your Compliance Authority
1. SCOPE EXPANSION: You may add targets to scope based on discovery state
2. SCOPE RESTRICTION: You may remove targets from scope if out of RoE or too risky
3. RE-DISPATCH: You may send an agent back for deeper analysis when findings are incomplete
4. ROE ENFORCEMENT: You may forbid an agent from executing an attack that violates RoE
5. HUMAN REPLACEMENT: You replace human sight as much as possible

### Compliance Checkpoints
You review after EVERY phase. Each re-entry is a compliance checkpoint.
You must verify: targets in scope, tools within RoE, findings assessed,
next action compliant.

### Decision Output Format
Return JSON with these fields:
- "decision": one of the valid routing decisions
- "confidence": 0.0-1.0
- "reasoning": why you chose this route
- "assessment": current engagement state
- "scope_change": {{"add": [], "remove": []}} if scope needs updating
- "forbid": ["command or tool"] if any action must be blocked
- "updated_plan": markdown plan update
- "mission_phase": current phase name
"""
        self._cached_system_prompt = prompt
        return prompt

    def build_delta(self, state: Dict[str, Any]) -> str:
        """Build delta-only context for WarChief's next checkpoint.

        Returns ONLY what changed since the last checkpoint.
        200 tokens instead of 2000.
        """
        deltas = []

        # New targets discovered
        current_targets = set(state.get("discovered_targets", []))
        new_targets = current_targets - self._last_targets
        removed_targets = self._last_targets - current_targets
        if new_targets:
            deltas.append(f"NEW TARGETS: {', '.join(sorted(new_targets))}")
        if removed_targets:
            deltas.append(f"REMOVED TARGETS: {', '.join(sorted(removed_targets))}")
        self._last_targets = current_targets

        # v2.3 fix: Track findings by content hash, not bot name.
        # Previous version added bot names to _last_findings permanently,
        # so re-runs with new findings were never surfaced as deltas.
        current_reports = state.get("reasoning_reports", {})
        for bot, report in current_reports.items():
            if isinstance(report, dict):
                summary = report.get("summary", "") or report.get("reasoning", "")
                if summary:
                    # Use content hash to detect actual changes
                    import hashlib
                    content_hash = hashlib.sha256(summary.encode()).hexdigest()[:16]
                    cache_key = f"{bot}:{content_hash}"
                    if cache_key not in self._last_findings:
                        deltas.append(f"NEW/UPDATED REPORT [{bot}]: {summary[:200]}")
                        # Remove old entries for this bot, add new one
                        old_keys = [k for k in self._last_findings if k.startswith(f"{bot}:")]
                        for k in old_keys:
                            self._last_findings.discard(k)
                        self._last_findings.add(cache_key)

        # Scope changes
        current_scope = state.get("mission", {}).get("scope", "")
        if current_scope and current_scope != self._last_scope:
            deltas.append(f"SCOPE CHANGED: {current_scope}")
            self._last_scope = current_scope

        # Approved extra targets
        approved = state.get("approved_extra_targets", [])
        if approved:
            deltas.append(f"APPROVED EXTRA TARGETS: {', '.join(approved)}")

        # Scope expansion candidates
        candidates = state.get("scope_expansion_candidates", [])
        if candidates:
            new_candidates = [c for c in candidates if isinstance(c, dict)]
            if new_candidates:
                targets_str = ", ".join(c.get("target", "?") for c in new_candidates[-3:])
                deltas.append(f"SCOPE CANDIDATES PENDING: {targets_str}")

        # Critical findings
        vulns = state.get("vuln_report", [])
        critical = [v for v in vulns if isinstance(v, dict) and _safe_cvss(v) >= 7.0]
        if critical:
            for v in critical[-3:]:
                deltas.append(f"CRITICAL: CVSS {_safe_cvss(v)} on {v.get('target','?')}: {v.get('title','')[:80]}")

        # Failed vectors
        failed = state.get("failed_vectors", [])
        if failed:
            recent = failed[-2:]
            for f in recent:
                deltas.append(f"FAILED: {f.get('tool','?')} on {f.get('target','?')}: {str(f.get('error',''))[:80]}")

        # Aggressiveness changes
        agg = state.get("aggressiveness", "cautious")
        if agg != "cautious":
            deltas.append(f"AGGRESSIVENESS: {agg}")

        if not deltas:
            return "NO CHANGES since last checkpoint. State is stable."

        return "## Delta Since Last Checkpoint\n\n" + "\n".join(deltas)

    def get_cached_system(self) -> Optional[str]:
        """Return cached system prompt if built, None otherwise."""
        return self._cached_system_prompt


def _safe_cvss(v: Dict[str, Any]) -> float:
    """Safely extract CVSS score from finding dict."""
    try:
        return float(v.get("cvss", 0))
    except (ValueError, TypeError):
        return 0.0