"""
Chimeras v3.0 — Budget Manager

Tracks LLM token usage and USD cost per bot, per phase.
Hard stop when configurable USD cap is exceeded.
Uses existing telemetry infrastructure.

Integration:
    core/llm_router.py calls BudgetTracker.record_usage() after each LLM call.
    main.py initializes BudgetTracker with budget_usd from swarm-config.json.
    graph.py checks budget before each node execution.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Rough per-1K-token costs (USD) by provider/model
# These are estimates — actual costs vary by provider
_COST_PER_1K_TOKENS = {
    "openai/gpt-4o": 0.005,
    "openai/gpt-4o-mini": 0.00015,
    "anthropic/claude-3-opus": 0.015,
    "anthropic/claude-3-sonnet": 0.003,
    "anthropic/claude-3-haiku": 0.00025,
    "google/gemini-1.5-pro": 0.0035,
    "google/gemini-1.5-flash": 0.000075,
    "ollama": 0.0,  # Local models — no cost
    "ollama-cloud": 0.0,  # Flat rate, no per-token cost
    "groq": 0.0,  # Free tier
    "default": 0.002,  # Conservative default estimate
}


def _estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for an LLM call."""
    key = f"{provider}/{model}".lower()
    cost_per_1k: float = _COST_PER_1K_TOKENS.get(key, _COST_PER_1K_TOKENS["default"])
    total_tokens = input_tokens + output_tokens
    return (total_tokens / 1000.0) * cost_per_1k


class BudgetTracker:
    """Tracks LLM cost per bot, per phase. Hard stop at configurable cap.

    Args:
        budget_usd: Maximum USD for the entire engagement. None = no limit.
        engagement_dir: Directory to write budget log.
    """

    def __init__(self, budget_usd: Optional[float] = None, engagement_dir: Optional[str] = None):
        self.budget_usd = budget_usd
        self.engagement_dir = Path(engagement_dir) if engagement_dir else None
        self._spent: float = 0.0
        self._by_bot: Dict[str, float] = {}
        self._by_phase: Dict[str, float] = {}
        self._call_count: int = 0
        self._stopped: bool = False
        self._warning_threshold: float = 0.8  # Warn at 80%
        self._warning_sent: bool = False

    @property
    def spent(self) -> float:
        return self._spent

    @property
    def remaining(self) -> Optional[float]:
        if self.budget_usd is None:
            return None
        return max(0.0, self.budget_usd - self._spent)

    @property
    def is_exhausted(self) -> bool:
        if self.budget_usd is None:
            return False
        return self._spent >= self.budget_usd

    def record_usage(
        self,
        bot_name: str,
        phase: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Dict[str, Any]:
        """Record an LLM call's token usage and estimated cost.

        Returns:
            Dict with: spent, remaining, is_exhausted, warning
        """
        if self._stopped:
            return {"spent": self._spent, "remaining": self.remaining,
                    "is_exhausted": True, "warning": "Budget already exhausted"}

        cost = _estimate_cost(provider, model, input_tokens, output_tokens)
        self._spent += cost
        self._by_bot[bot_name] = self._by_bot.get(bot_name, 0.0) + cost
        self._by_phase[phase] = self._by_phase.get(phase, 0.0) + cost
        self._call_count += 1

        # Check warning threshold
        warning = None
        if self.budget_usd is not None:
            ratio = self._spent / self.budget_usd
            if ratio >= self._warning_threshold and not self._warning_sent:
                warning = f"Budget warning: {ratio:.0%} of ${self.budget_usd:.2f} spent"
                self._warning_sent = True
                logger.warning(warning)

            if self.is_exhausted:
                self._stopped = True
                warning = f"Budget exhausted: ${self._spent:.4f} spent of ${self.budget_usd:.2f} cap"
                logger.error(warning)

        return {
            "spent": self._spent,
            "remaining": self.remaining,
            "is_exhausted": self.is_exhausted,
            "warning": warning,
        }

    def summary(self) -> Dict[str, Any]:
        """Get budget summary for report inclusion."""
        return {
            "budget_usd": self.budget_usd,
            "spent_usd": round(self._spent, 4),
            "remaining_usd": round(self.remaining, 4) if self.remaining is not None else None,
            "call_count": self._call_count,
            "by_bot": {k: round(v, 4) for k, v in sorted(self._by_bot.items(), key=lambda x: -x[1])},
            "by_phase": {k: round(v, 4) for k, v in sorted(self._by_phase.items(), key=lambda x: -x[1])},
            "is_exhausted": self.is_exhausted,
        }

    def save_log(self) -> None:
        """Write budget log to engagement directory."""
        if not self.engagement_dir:
            return
        try:
            log_path = self.engagement_dir / "budget_log.json"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "w") as f:
                json.dump(self.summary(), f, indent=2)
        except Exception as e:
            logger.error(f"Budget log write failed: {e}")