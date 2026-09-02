"""
Tests for core/json_parser.py — hardened JSON parser.

Covers:
- Markdown fence stripping (```json ... ```)
- Direct JSON parse
- Code block extraction (multiple blocks)
- Brace matching (nested JSON in surrounding text)
- Truncated JSON repair (open braces/brackets)
- Empty response handling
- Schema validation pass-through
"""
import pytest

from core.json_parser import (
    parse_llm_json,
    _strip_code_fences,
    _extract_code_blocks,
    _try_parse,
    _brace_match,
    _check_truncation,
    _repair_truncated_json,
)


# ─── Direct parse ───


class TestDirectParse:
    """Tests for direct JSON parsing (strategy 2)."""

    def test_valid_json(self):
        result = parse_llm_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_nested_json(self):
        result = parse_llm_json('{"a": {"b": [1, 2, 3]}}')
        assert result == {"a": {"b": [1, 2, 3]}}

    def test_array_at_root(self):
        """Array at root should parse via _try_parse."""
        result = parse_llm_json('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_numbers_and_bools(self):
        result = parse_llm_json('{"int": 42, "float": 3.14, "bool": true, "null": null}')
        assert result["int"] == 42
        assert result["float"] == 3.14
        assert result["bool"] is True
        assert result["null"] is None


# ─── Markdown fence stripping ───


class TestFenceStripping:
    """Tests for markdown code fence handling."""

    def test_json_fence_stripped(self):
        response = '```json\n{"key": "value"}\n```'
        result = parse_llm_json(response)
        assert result == {"key": "value"}

    def test_plain_fence_stripped(self):
        response = '```\n{"key": "value"}\n```'
        result = parse_llm_json(response)
        assert result == {"key": "value"}

    def test_fence_with_surrounding_text(self):
        response = 'Here is the JSON:\n```json\n{"key": "value"}\n```\nDone.'
        result = parse_llm_json(response)
        assert result == {"key": "value"}

    def test_strip_code_fences_helper(self):
        assert _strip_code_fences('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_strip_code_fences_no_fence(self):
        assert _strip_code_fences('{"a": 1}') == '{"a": 1}'

    def test_multiple_code_blocks(self):
        """Multiple code blocks — first valid one should be used."""
        response = '```json\n{"first": true}\n```\n```json\n{"second": true}\n```'
        result = parse_llm_json(response)
        assert result == {"first": True}

    def test_extract_code_blocks_helper(self):
        blocks = _extract_code_blocks('```json\n{"a": 1}\n```\n```\n{"b": 2}\n```')
        assert len(blocks) == 2


# ─── Brace matching ───


class TestBraceMatching:
    """Tests for brace matching strategy."""

    def test_brace_match_in_text(self):
        response = 'Some text before {"key": "value"} some text after'
        result = parse_llm_json(response)
        assert result == {"key": "value"}

    def test_brace_match_nested(self):
        response = 'Output: {"a": {"b": {"c": 1}}}'
        result = parse_llm_json(response)
        assert result == {"a": {"b": {"c": 1}}}

    def test_brace_match_multiple_objects(self):
        """First balanced object should be returned."""
        response = '{"first": 1} and {"second": 2}'
        result = parse_llm_json(response)
        assert result == {"first": 1}

    def test_brace_match_helper(self):
        assert _brace_match('text {"a": 1} text') == {"a": 1}

    def test_brace_match_no_braces(self):
        assert _brace_match("no braces here") is None


# ─── Truncated JSON repair ───


class TestTruncatedJSONRepair:
    """Tests for truncated JSON repair (strategy 6)."""

    def test_truncated_object_repaired(self):
        """Missing closing brace should be repaired."""
        truncated = '{"key": "value", "key2": "value2"'
        result = parse_llm_json(truncated, max_tokens_retry=False)
        assert result is not None
        assert result.get("key") == "value"

    def test_truncated_nested_repaired(self):
        """Truncated nested object should be salvaged."""
        truncated = '{"outer": {"inner": "value"'
        result = parse_llm_json(truncated, max_tokens_retry=False)
        assert result is not None

    def test_truncated_array_repaired(self):
        """Missing closing bracket should be repaired."""
        truncated = '{"items": [1, 2, 3'
        result = parse_llm_json(truncated, max_tokens_retry=False)
        assert result is not None
        assert "items" in result

    def test_truncated_with_string_value(self):
        """Truncated mid-string-value should be salvaged at last comma."""
        truncated = '{"a": 1, "b": "incomplete'
        result = parse_llm_json(truncated, max_tokens_retry=False)
        assert result is not None
        assert result.get("a") == 1

    def test_repair_helper_returns_none_for_valid(self):
        """Valid JSON should not trigger repair."""
        assert _repair_truncated_json('{"a": 1}') is None

    def test_repair_helper_returns_none_for_no_braces(self):
        assert _repair_truncated_json("no json here") is None

    def test_truncation_check_raises(self):
        """_check_truncation should raise for unbalanced braces."""
        with pytest.raises(ValueError, match="truncated"):
            _check_truncation('{"a": 1, "b":')

    def test_truncation_check_passes_balanced(self):
        """_check_truncation should not raise for balanced JSON."""
        _check_truncation('{"a": 1}')  # should not raise

    def test_truncation_check_no_braces(self):
        """No braces at all — should not raise."""
        _check_truncation("plain text")

    def test_max_tokens_retry_raises_value_error(self):
        """With max_tokens_retry=True, truncated JSON should raise ValueError."""
        with pytest.raises(ValueError, match="truncated"):
            parse_llm_json('{"a": 1, "b":', max_tokens_retry=True)


# ─── Empty / invalid responses ───


class TestEmptyAndInvalid:
    """Tests for empty and completely invalid responses."""

    def test_empty_response_raises(self):
        with pytest.raises(ValueError, match="Empty"):
            parse_llm_json("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="Empty"):
            parse_llm_json("   \n\t  ")

    def test_no_json_raises(self):
        with pytest.raises(ValueError):
            parse_llm_json("This is just plain text with no JSON at all.")

    def test_none_response_raises(self):
        with pytest.raises(ValueError):
            parse_llm_json(None)


# ─── _try_parse helper ───


class TestTryParse:
    """Tests for _try_parse helper."""

    def test_valid_json(self):
        assert _try_parse('{"a": 1}') == {"a": 1}

    def test_invalid_json_returns_none(self):
        assert _try_parse("not json") is None

    def test_none_returns_none(self):
        assert _try_parse(None) is None

    def test_empty_string_returns_none(self):
        assert _try_parse("") is None


# ─── Schema validation ───


class TestSchemaValidation:
    """Tests for schema validation pass-through."""

    def test_schema_validation_passes_valid(self):
        from core.schemas import BotDecision
        result = parse_llm_json(
            '{"needed": true, "strategy": "test", "confidence": 0.9}',
            schema=BotDecision,
        )
        assert result["needed"] is True
        assert result["confidence"] == 0.9

    def test_no_schema_returns_raw(self):
        result = parse_llm_json('{"custom": "data"}')
        assert result == {"custom": "data"}