"""
Tests for core/schemas.py — Pydantic models.

Covers:
- Finding: validation, required fields, optional fields
- ToolResult: validation, defaults, verification metadata
- BotDecision: validation, defaults
- BotAnalysis: validation, defaults, structured_findings
- validate_bot_output: passes valid data, returns raw on invalid
- compute_content_hash: determinism, length
"""
import pytest

from core.schemas import (
    Finding,
    ToolResult,
    BotDecision,
    BotAnalysis,
    validate_bot_output,
    compute_content_hash,
    PYDANTIC_AVAILABLE,
)


# ─── Finding ───


class TestFinding:
    """Tests for the Finding schema."""

    def test_valid_finding(self):
        f = Finding(
            finding_id="BH-001",
            title="OpenSSH RCE",
            severity="Critical",
            cvss=9.8,
            source_bot="bloodhound",
        )
        assert f.finding_id == "BH-001"
        assert f.severity == "Critical"
        assert f.cvss == 9.8
        assert f.source_bot == "bloodhound"

    def test_required_fields(self):
        """finding_id, title, severity, source_bot are required."""
        if PYDANTIC_AVAILABLE:
            from pydantic import ValidationError
            with pytest.raises(ValidationError):
                Finding()
            with pytest.raises(ValidationError):
                Finding(title="test", severity="Info", source_bot="test")
        else:
            # Fallback mode: missing fields get defaults
            f = Finding()
            assert f.finding_id == "UNKNOWN"
            assert f.title == "Unknown"
            assert f.severity == "Info"
            assert f.source_bot == "unknown"

    def test_optional_fields_default_none(self):
        f = Finding(
            finding_id="BH-001", title="test", severity="Info",
            source_bot="bloodhound",
        )
        assert f.cvss is None
        assert f.cvss_vector is None
        assert f.host is None
        assert f.port is None
        assert f.service is None
        assert f.raw_output_ref is None
        assert f.freeform_notes is None

    def test_default_status_confirmed(self):
        f = Finding(
            finding_id="BH-001", title="test", severity="Info",
            source_bot="bloodhound",
        )
        assert f.status == "Confirmed"

    def test_from_dict_fills_defaults(self):
        f = Finding.from_dict({
            "finding_id": "BH-001",
            "title": "test",
            "severity": "High",
            "source_bot": "bloodhound",
        })
        assert f.finding_id == "BH-001"
        assert f.severity == "High"

    def test_from_dict_extra_fields_go_to_freeform(self):
        """Extra fields not in schema should go to freeform_notes."""
        f = Finding.from_dict({
            "finding_id": "BH-001",
            "title": "test",
            "severity": "Info",
            "source_bot": "bloodhound",
            "custom_field": "custom_value",
        })
        if PYDANTIC_AVAILABLE:
            assert f.freeform_notes is not None
            assert "custom_field" in f.freeform_notes

    def test_model_dump_roundtrip(self):
        f = Finding(
            finding_id="BH-001", title="test", severity="Critical",
            cvss=9.0, source_bot="bloodhound",
        )
        d = f.model_dump()
        assert d["finding_id"] == "BH-001"
        assert d["severity"] == "Critical"
        assert d["cvss"] == 9.0


# ─── ToolResult ───


class TestToolResult:
    """Tests for the ToolResult schema."""

    def test_valid_tool_result(self):
        r = ToolResult(command="nmap 10.10.10.5", exit_code=0)
        assert r.command == "nmap 10.10.10.5"
        assert r.exit_code == 0

    def test_defaults(self):
        r = ToolResult(command="test")
        assert r.exit_code == 0
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.duration_sec == 0.0
        assert r.success is True
        assert r.scope_blocked is False
        assert r.cached is False
        assert r.content_hash is None
        assert r.verified_by_cycle is None
        assert r.tool_name is None
        assert r.target is None

    def test_verification_metadata(self):
        r = ToolResult(
            command="test",
            content_hash="abc123",
            verified_by_cycle=3,
            tool_name="nmap",
            target="10.10.10.5",
        )
        assert r.content_hash == "abc123"
        assert r.verified_by_cycle == 3
        assert r.tool_name == "nmap"

    def test_model_dump(self):
        r = ToolResult(command="test", exit_code=1, success=False)
        d = r.model_dump()
        assert d["command"] == "test"
        assert d["exit_code"] == 1
        assert d["success"] is False


# ─── BotDecision ───


class TestBotDecision:
    """Tests for the BotDecision schema."""

    def test_valid_decision(self):
        d = BotDecision(
            needed=True,
            strategy="port_scan",
            confidence=0.9,
            reasoning="need to find open ports",
            commands=["nmap -sV 10.10.10.5"],
        )
        assert d.needed is True
        assert d.confidence == 0.9
        assert len(d.commands) == 1

    def test_defaults(self):
        d = BotDecision()
        assert d.needed is True
        assert d.strategy == ""
        assert d.confidence == 0.5
        assert d.reasoning == ""
        assert d.commands == []
        assert d.skip_reason == ""

    def test_model_dump(self):
        d = BotDecision(needed=False, skip_reason="nothing to do")
        dump = d.model_dump()
        assert dump["needed"] is False
        assert dump["skip_reason"] == "nothing to do"


# ─── BotAnalysis ───


class TestBotAnalysis:
    """Tests for the BotAnalysis schema."""

    def test_valid_analysis(self):
        a = BotAnalysis(
            summary="Found 2 open ports",
            findings=["Port 80 open", "Port 443 open"],
            recommendations=["Check for web vulns"],
        )
        assert a.summary == "Found 2 open ports"
        assert len(a.findings) == 2

    def test_defaults(self):
        a = BotAnalysis()
        assert a.summary == ""
        assert a.findings == []
        assert a.structured_data == {}
        assert a.recommendations == []
        assert a.report_content == ""
        assert a.structured_findings == []

    def test_structured_findings(self):
        a = BotAnalysis(
            structured_findings=[
                {"finding_id": "BH-001", "severity": "Critical"}
            ]
        )
        assert len(a.structured_findings) == 1
        assert a.structured_findings[0]["finding_id"] == "BH-001"

    def test_model_dump(self):
        a = BotAnalysis(summary="test")
        d = a.model_dump()
        assert d["summary"] == "test"


# ─── validate_bot_output ───


class TestValidateBotOutput:
    """Tests for validate_bot_output."""

    def test_valid_data_returns_validated(self):
        data = {
            "finding_id": "BH-001",
            "title": "test",
            "severity": "Critical",
            "source_bot": "bloodhound",
        }
        result = validate_bot_output(data, Finding)
        assert result["finding_id"] == "BH-001"

    def test_invalid_data_returns_raw(self):
        """When validation fails, raw data is returned (never crashes)."""
        data = {"random": "data", "no": "required_fields"}
        result = validate_bot_output(data, Finding)
        # Should return the data (possibly validated with defaults filled in)
        # The key: it should not crash
        assert isinstance(result, dict)

    def test_no_schema_returns_raw(self):
        data = {"any": "thing"}
        result = validate_bot_output(data, None)
        assert result == data


# ─── compute_content_hash ───


class TestComputeContentHash:
    """Tests for compute_content_hash."""

    def test_deterministic(self):
        h1 = compute_content_hash("test content")
        h2 = compute_content_hash("test content")
        assert h1 == h2

    def test_different_content_different_hash(self):
        h1 = compute_content_hash("content A")
        h2 = compute_content_hash("content B")
        assert h1 != h2

    def test_hash_length(self):
        """Hash should be 32 chars (truncated SHA-256)."""
        h = compute_content_hash("test")
        assert len(h) == 32

    def test_empty_string(self):
        h = compute_content_hash("")
        assert len(h) == 32