"""
Chimeras v3.1 — Context Compaction

Proactive context management for long engagements. Instead of waiting
for truncation and retrying (v2.5), this module:

1. Estimates token count before sending to LLM
2. If over budget, summarizes oversized tool outputs
3. Preserves raw data in JSONL (never lost)
4. Maintains a rolling summary of engagement history

Strix has SDK-managed compaction (is_context_overflow, maybe_compact).
We have explicit, transparent compaction with raw data preservation.

Usage:
    from core.context_compaction import ContextCompactor

    compactor = ContextCompactor(max_tokens=120000)
    compacted, stats = compactor.compact(prompt, tool_results)
    # compacted: reduced prompt string
    # stats: {original_tokens, compacted_tokens, items_summarized, ...}
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Rough token estimation: ~4 chars per token for English text
_CHARS_PER_TOKEN = 4

# Max tool output length before summarization (in chars)
_MAX_TOOL_OUTPUT_CHARS = 4000
# Summary length when truncating (in chars)
_SUMMARY_CHARS = 500
# Max engagement history entries before rolling summary
_MAX_HISTORY_ENTRIES = 20


class ContextCompactor:
    """Proactive context compaction for LLM prompts.

    Estimates token count, identifies oversized content, and produces
    a compacted prompt that fits within the token budget. Raw data is
    never lost — it's preserved in per-bot JSONL files.

    Compaction strategy (in priority order):
    1. Truncate raw tool output blocks to summaries
    2. Collapse repeated empty lines and whitespace
    3. Summarize old engagement history entries
    4. If still over budget, truncate oldest context sections
    """

    def __init__(
        self,
        max_tokens: int = 120000,
        chars_per_token: int = _CHARS_PER_TOKEN,
        max_tool_output_chars: int = _MAX_TOOL_OUTPUT_CHARS,
        summary_chars: int = _SUMMARY_CHARS,
    ):
        self.max_tokens = max_tokens
        self.chars_per_token = chars_per_token
        self.max_tool_output_chars = max_tool_output_chars
        self.summary_chars = summary_chars
        self.max_budget_chars = max_tokens * chars_per_token

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text string.

        Uses a simple chars-per-token heuristic. Not exact, but
        sufficient for budget management. Real tokenization would
        require the provider's tokenizer (not available generically).
        """
        if not text:
            return 0
        return len(text) // self.chars_per_token

    def is_over_budget(self, text: str) -> bool:
        """Check if text exceeds the token budget."""
        return self.estimate_tokens(text) > self.max_tokens

    def compact(
        self,
        prompt: str,
        tool_results: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Compact a prompt to fit within the token budget.

        Args:
            prompt: The full prompt string to compact.
            tool_results: Optional list of tool result dicts for
                          targeted summarization.

        Returns:
            Tuple of (compacted_prompt, stats_dict).
        """
        original_chars = len(prompt)
        original_tokens = self.estimate_tokens(prompt)

        if original_tokens <= self.max_tokens:
            return prompt, {
                "original_tokens": original_tokens,
                "compacted_tokens": original_tokens,
                "items_summarized": 0,
                "bytes_saved": 0,
                "compaction_needed": False,
            }

        compacted = prompt
        items_summarized = 0

        # Step 1: Truncate raw tool output code blocks
        compacted, count = self._truncate_code_blocks(compacted)
        items_summarized += count

        # Step 2: Collapse whitespace
        compacted = self._collapse_whitespace(compacted)

        # Check if we're under budget now
        if self.estimate_tokens(compacted) <= self.max_tokens:
            return compacted, self._build_stats(
                original_chars, compacted, items_summarized, True
            )

        # Step 3: Summarize tool result sections
        if tool_results:
            compacted, count = self._summarize_tool_results(compacted, tool_results)
            items_summarized += count

        if self.estimate_tokens(compacted) <= self.max_tokens:
            return compacted, self._build_stats(
                original_chars, compacted, items_summarized, True
            )

        # Step 4: Truncate oldest context (keep the most recent)
        compacted = self._truncate_oldest(compacted)

        return compacted, self._build_stats(
            original_chars, compacted, items_summarized, True
        )

    def _truncate_code_blocks(self, text: str) -> Tuple[str, int]:
        """Truncate code blocks to summary length.

        Replaces oversized code blocks with a truncated version plus
        a note that the full output is in the JSONL store.
        """
        count = 0

        def truncate_block(match):
            nonlocal count
            content = match.group(1)
            if len(content) > self.max_tool_output_chars:
                count += 1
                truncated = content[:self.summary_chars]
                return (
                    f"```\n{truncated}\n"
                    f"... (truncated — full output in JSONL findings store)\n```"
                )
            return match.group(0)

        result = re.sub(r'```(?:\w+)?\n(.*?)```', truncate_block, text, flags=re.DOTALL)
        return result, count

    def _collapse_whitespace(self, text: str) -> str:
        """Collapse multiple blank lines and trailing whitespace."""
        # Collapse 3+ blank lines to 1
        result = re.sub(r'\n{3,}', '\n\n', text)
        # Strip trailing whitespace from each line
        result = '\n'.join(line.rstrip() for line in result.split('\n'))
        return result

    def _summarize_tool_results(
        self, text: str, tool_results: List[Dict[str, Any]]
    ) -> Tuple[str, int]:
        """Summarize tool result sections in the prompt.

        Replaces full tool output sections with one-line summaries
        of each tool result.
        """
        count = 0

        for result in tool_results:
            command = result.get("command", "unknown")
            stdout = result.get("stdout", "")
            exit_code = result.get("exit_code", 0)

            if len(stdout) > self.max_tool_output_chars:
                # Create a one-line summary
                first_line = stdout.strip().split("\n")[0][:100] if stdout.strip() else ""
                summary = f"[Tool: {command.split()[0] if command else 'unknown'}] exit={exit_code} → {first_line}"
                count += 1

                # Try to replace the full output in the prompt
                # Look for the stdout content in the text
                if stdout[:200] in text:
                    text = text.replace(
                        stdout[:200],
                        summary + "\n[... full output in JSONL store]",
                        1
                    )

        return text, count

    def _truncate_oldest(self, text: str) -> str:
        """Truncate oldest context sections to fit budget.

        Keeps the most recent ~50% of the prompt (which contains
        the current phase context and recent findings) and trims
        the oldest ~50% to a summary.
        """
        target_chars = self.max_budget_chars

        if len(text) <= target_chars:
            return text

        # Split into sections by ## headers
        sections = re.split(r'(?=^## )', text, flags=re.MULTILINE)

        if len(sections) <= 1:
            # No clear sections — just truncate from the front
            keep = text[-target_chars:]
            return f"[... earlier context compacted ...]\n\n{keep}"

        # Keep the last 40% of sections fully, summarize the rest
        split_point = int(len(sections) * 0.6)
        old_sections = sections[:split_point]
        new_sections = sections[split_point:]

        # Summarize old sections
        old_summary_parts = []
        for section in old_sections:
            # Keep section header and first 2 lines
            lines = section.strip().split("\n")
            if lines:
                header = lines[0]
                preview = " ".join(lines[1:3])[:150]
                old_summary_parts.append(f"{header}: {preview}...")

        old_summary = "\n".join(old_summary_parts)
        new_content = "\n\n".join(new_sections)

        result = f"## Earlier Context (Compacted)\n{old_summary}\n\n---\n\n{new_content}"

        # If still too long, hard truncate
        if len(result) > target_chars:
            result = result[-target_chars:]
            result = f"[... earlier context compacted ...]\n\n{result}"

        return result

    def _build_stats(
        self, original_chars: int, compacted: str, items_summarized: int, needed: bool
    ) -> Dict[str, Any]:
        """Build compaction statistics dict."""
        compacted_chars = len(compacted)
        compacted_tokens = self.estimate_tokens(compacted)
        return {
            "original_tokens": original_chars // self.chars_per_token,
            "compacted_tokens": compacted_tokens,
            "items_summarized": items_summarized,
            "bytes_saved": original_chars - compacted_chars,
            "compaction_needed": needed,
            "compression_ratio": round(
                compacted_chars / original_chars, 2
            ) if original_chars > 0 else 1.0,
        }

    def should_compact(self, text: str, threshold: float = 0.85) -> bool:
        """Check if text should be compacted (above threshold of budget).

        Proactive check — compact before hitting the hard limit.
        """
        tokens = self.estimate_tokens(text)
        return tokens > (self.max_tokens * threshold)

    def compact_if_needed(
        self, text: str, tool_results: Optional[List[Dict]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Compact only if over budget. Otherwise return unchanged.

        Convenience method for integration points that want to
        compact proactively without always running the compactor.
        """
        if self.should_compact(text):
            return self.compact(text, tool_results)
        return text, {
            "original_tokens": self.estimate_tokens(text),
            "compacted_tokens": self.estimate_tokens(text),
            "items_summarized": 0,
            "bytes_saved": 0,
            "compaction_needed": False,
        }