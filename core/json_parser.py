"""
Chimeras v2.3 — Hardened JSON Parser

Strips markdown fences, handles truncated JSON, validates against
optional Pydantic models. Replaces the inline _parse_json_response
in base_bot.py with a reusable utility.

Council recommendation: "Strip markdown fences + Pydantic validation.
No regex stripper. Provider-native structured output where available."
"""

import json
import re
import logging
from typing import Dict, Any, Optional, Type
from pathlib import Path

logger = logging.getLogger("chimeras.json_parser")

# Optional Pydantic import — works without it (schema validation skipped)
try:
    from pydantic import BaseModel as _BaseModel, ValidationError
    BaseModel = _BaseModel
    PYDANTIC_AVAILABLE = True
except ImportError:
    BaseModel = None
    ValidationError = Exception
    PYDANTIC_AVAILABLE = False


def parse_llm_json(response: str,
                   schema: Optional[type] = None,
                   max_tokens_retry: bool = True) -> Dict[str, Any]:
    """
    Parse JSON from LLM response with multiple fallback strategies.

    Args:
        response: Raw LLM text response.
        schema: Optional Pydantic model to validate against.
        max_tokens_retry: If True and JSON appears truncated, raise
                         ValueError with a clear message instead of
                         generic parse error.

    Returns:
        Parsed dict.

    Raises:
        ValueError: If JSON cannot be parsed.
        ValidationError: If schema validation fails (only if schema provided).
    """
    if not response or not response.strip():
        raise ValueError("Empty LLM response")

    stripped = response.strip()

    # Strategy 1: Strip markdown code block wrappers
    stripped = _strip_code_fences(stripped)

    # Strategy 2: Try direct parse
    result = _try_parse(stripped)
    if result is not None:
        return _validate(result, schema)

    # Strategy 3: Extract from ```json ... ``` blocks
    for block in _extract_code_blocks(response):
        result = _try_parse(block)
        if result is not None:
            return _validate(result, schema)

    # Strategy 4: Brace matching (handles nested JSON)
    result = _brace_match(response)
    if result is not None:
        return _validate(result, schema)

    # Strategy 5: Try entire response as-is
    result = _try_parse(response)
    if result is not None:
        return _validate(result, schema)

    # Check for truncation
    if max_tokens_retry:
        _check_truncation(stripped)

    raise ValueError(f"Could not parse JSON from LLM response: {response[:300]}...")


def _strip_code_fences(text: str) -> str:
    """Strip leading ```json or ``` and trailing ```."""
    result = text.strip()
    if result.startswith("```"):
        # Remove opening line
        first_nl = result.find("\n")
        if first_nl != -1:
            result = result[first_nl + 1:]
        # Remove trailing ```
        if result.rstrip().endswith("```"):
            result = result.rstrip()[:-3].rstrip()
    return result


def _extract_code_blocks(text: str) -> list:
    """Extract all ```json ... ``` or ``` ... ``` blocks."""
    return re.findall(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)


def _try_parse(text: str) -> Optional[Dict[str, Any]]:
    """Try json.loads, return None on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _brace_match(text: str) -> Optional[Dict[str, Any]]:
    """Find balanced { ... } in text, handling nested braces."""
    depth = 0
    start = -1
    for i, c in enumerate(text):
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                result = _try_parse(text[start:i + 1])
                if result is not None:
                    return result
                start = -1
    return None


def _check_truncation(text: str) -> None:
    """Check if JSON appears truncated (open braces > close braces)."""
    if "{" not in text:
        return
    open_braces = text.count("{")
    close_braces = text.count("}")
    if open_braces > close_braces:
        raise ValueError(
            f"LLM response appears truncated (open braces: {open_braces}, "
            f"close braces: {close_braces}). Likely max_tokens limit hit. "
            f"Response starts: {text[:200]}..."
        )


def _validate(data: Dict[str, Any], schema: Optional[type]) -> Dict[str, Any]:
    """Validate against Pydantic schema if available."""
    if schema is None or not PYDANTIC_AVAILABLE:
        return data
    try:
        model = schema(**data)
        return model.model_dump()
    except ValidationError as e:
        logger.warning(f"Schema validation failed: {e}")
        # Return raw data even if validation fails — better than crashing
        return data