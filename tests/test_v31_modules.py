"""
Tests for v3.1 RetestVerifier, ContextCompactor, CoverageTracker.
"""

import json
import pytest
from pathlib import Path

from core.retest import RetestVerifier, STATUS_CLOSED, STATUS_OPEN, STATUS_PARTIAL, STATUS_SKIPPED
from core.context_compaction import ContextCompactor
from core.coverage import CoverageTracker


# ─── RetestVerifier tests ─────────────────────────────────────────────

class TestRetestCommandExtraction:
    @pytest.fixture
    def verifier(self, tmp_path):
        return RetestVerifier(tmp_path, timeout=5)

    def test_extract_from_code_block(self, verifier):
        cmds = verifier._extract_commands("```\nnmap -p 22 10.0.0.1\n```")
        assert len(cmds) == 1
        assert "nmap" in cmds[0]

    def test_extract_multiple_from_code_block(self, verifier):
        cmds = verifier._extract_commands("```\nsslscan 10.0.0.1\nnmap -p 22 10.0.0.1\n```")
        assert len(cmds) == 2

    def test_extract_inline_code(self, verifier):
        cmds = verifier._extract_commands("Run `nmap -p 22 10.0.0.1` to test")
        assert len(cmds) == 1

    def test_extract_empty(self, verifier):
        assert verifier._extract_commands("") == []
        assert verifier._extract_commands("N/A") == []

    def test_extract_plain_lines(self, verifier):
        cmds = verifier._extract_commands("nmap -p 22 10.0.0.1")
        assert len(cmds) >= 1

    def test_skips_comments(self, verifier):
        cmds = verifier._extract_commands("```\n# this is a comment\nnmap -p 22 10.0.0.1\n```")
        assert len(cmds) == 1
        assert "nmap" in cmds[0]


class TestRetestCompareOutputs:
    @pytest.fixture
    def verifier(self, tmp_path):
        return RetestVerifier(tmp_path, timeout=5)

    def test_same_output_is_open(self, verifier):
        status = verifier._compare_outputs(
            "TLS 1.0 enabled",
            "TLS 1.0 enabled and weak ciphers found",
            0,
        )
        assert status == STATUS_OPEN

    def test_different_output_is_closed(self, verifier):
        status = verifier._compare_outputs(
            "TLS 1.0 enabled",
            "All TLS 1.2+ with strong ciphers only",
            1,
        )
        assert status == STATUS_CLOSED

    def test_empty_new_output_closed(self, verifier):
        status = verifier._compare_outputs(
            "Vulnerable: SQL injection confirmed",
            "",
            1,
        )
        assert status == STATUS_CLOSED

    def test_no_original_proof_uses_exit_code(self, verifier):
        status = verifier._compare_outputs("", "some output", 0)
        assert status == STATUS_OPEN
        status = verifier._compare_outputs("", "some output", 1)
        assert status == STATUS_CLOSED

    def test_partial_match(self, verifier):
        status = verifier._compare_outputs(
            "CVE-2024-1234 vulnerable enabled weak",
            "CVE-2024-1234 found but not vulnerable",
            0,
        )
        # Some indicators match (CVE), some don't (vulnerable, enabled, weak)
        assert status in (STATUS_PARTIAL, STATUS_OPEN)


class TestRetestRunRetest:
    def test_skipped_finding(self, tmp_path):
        """Finding with no PoC commands should be skipped."""
        verifier = RetestVerifier(tmp_path, timeout=5)
        findings = [
            {"id": "T-001", "title": "Test", "severity": "info", "poc": "N/A", "proof_of_existence": "N/A"},
        ]
        report = verifier.run_retest(findings)
        assert report["results"][0]["status"] == STATUS_SKIPPED
        assert report["summary"]["skipped"] == 1

    def test_report_files_created(self, tmp_path):
        """Retest should create report files."""
        verifier = RetestVerifier(tmp_path, timeout=5)
        findings = [
            {"id": "T-001", "title": "Test", "severity": "info", "poc": "N/A", "proof_of_existence": "N/A"},
        ]
        verifier.run_retest(findings)
        assert (tmp_path / "retest" / "retest_results.json").exists()
        assert (tmp_path / "report" / "retest_report.md").exists()

    def test_retest_results_json_valid(self, tmp_path):
        """retest_results.json should be valid JSON with correct structure."""
        verifier = RetestVerifier(tmp_path, timeout=5)
        findings = [{"id": "T-001", "title": "Test", "poc": "N/A"}]
        verifier.run_retest(findings)
        data = json.loads((tmp_path / "retest" / "retest_results.json").read_text())
        assert "summary" in data
        assert "results" in data
        assert data["total_findings"] == 1

    def test_markdown_report_has_title(self, tmp_path):
        """Markdown report should have the title."""
        verifier = RetestVerifier(tmp_path, timeout=5)
        verifier.run_retest([{"id": "T-001", "title": "Test", "poc": "N/A"}])
        md = (tmp_path / "report" / "retest_report.md").read_text()
        assert "Retest Report" in md

    def test_summary_remediation_rate(self, tmp_path):
        """Summary should calculate remediation rate."""
        verifier = RetestVerifier(tmp_path, timeout=5)
        findings = [
            {"id": "T-001", "title": "Test", "poc": "N/A"},
            {"id": "T-002", "title": "Test2", "poc": "N/A"},
        ]
        report = verifier.run_retest(findings)
        # Both skipped → 0% remediation
        assert report["summary"]["remediation_rate"] == 0.0


# ─── ContextCompactor tests ───────────────────────────────────────────

class TestContextCompactor:
    def test_estimate_tokens(self):
        c = ContextCompactor()
        assert c.estimate_tokens("hello") == 1  # 5 chars // 4 = 1
        assert c.estimate_tokens("hello world!") == 3  # 12 // 4 = 3
        assert c.estimate_tokens("") == 0

    def test_over_budget(self):
        c = ContextCompactor(max_tokens=10)
        assert c.is_over_budget("a" * 100)  # 25 tokens > 10
        assert not c.is_over_budget("a" * 10)  # 2 tokens < 10

    def test_no_compaction_needed(self):
        c = ContextCompactor(max_tokens=1000)
        text = "Hello world"
        compacted, stats = c.compact_if_needed(text)
        assert not stats["compaction_needed"]
        assert compacted == text

    def test_compaction_reduces_size(self):
        c = ContextCompactor(max_tokens=50)  # 200 chars budget
        large = "A" * 1000  # 250 tokens
        compacted, stats = c.compact(large)
        assert stats["compaction_needed"]
        assert len(compacted) < len(large)
        assert stats["bytes_saved"] > 0

    def test_code_block_truncation(self):
        c = ContextCompactor(max_tokens=50)
        text = "Some text\n```\n" + "B" * 5000 + "\n```\nMore text"
        compacted, stats = c.compact(text)
        assert stats["items_summarized"] >= 1
        assert "truncated" in compacted.lower() or "compacted" in compacted.lower()

    def test_whitespace_collapse(self):
        c = ContextCompactor(max_tokens=100000)
        text = "Line 1\n\n\n\n\nLine 2   \n\n\n\nLine 3"
        # Call _collapse_whitespace directly (compact won't trigger for small text)
        compacted = c._collapse_whitespace(text)
        # Should not have 3+ consecutive newlines
        assert "\n\n\n" not in compacted

    def test_should_compact_threshold(self):
        c = ContextCompactor(max_tokens=100)
        # 85 tokens → above 85% threshold
        assert c.should_compact("a" * 400)  # 100 tokens > 85
        # 50 tokens → below threshold
        assert not c.should_compact("a" * 100)  # 25 tokens < 85

    def test_compact_if_needed_under_budget(self):
        c = ContextCompactor(max_tokens=1000)
        text = "Small text"
        result, stats = c.compact_if_needed(text)
        assert result == text
        assert not stats["compaction_needed"]

    def test_compression_ratio(self):
        c = ContextCompactor(max_tokens=50)
        large = "A" * 1000
        _, stats = c.compact(large)
        assert stats["compression_ratio"] < 1.0

    def test_preserves_recent_content(self):
        """Compaction should preserve the most recent context."""
        c = ContextCompactor(max_tokens=50)
        text = "## Old Section\n" + "A" * 500 + "\n\n## Recent Section\nImportant finding"
        compacted, _ = c.compact(text)
        # Recent section should be preserved
        assert "Important finding" in compacted or "Recent" in compacted


# ─── CoverageTracker tests ────────────────────────────────────────────

class TestCoverageTracker:
    @pytest.fixture
    def tracker(self, tmp_path):
        return CoverageTracker(tmp_path)

    def test_record_and_get_all(self, tracker):
        id1 = tracker.record("10.0.0.1", 22, "ssh", "nmap", "port_scan", "open")
        id2 = tracker.record("10.0.0.1", 80, "http", "nikto", "web_scan", "clean")
        entries = tracker.get_all()
        assert len(entries) == 2
        assert entries[0]["target"] == "10.0.0.1"
        assert entries[0]["port"] == 22

    def test_get_by_target(self, tracker):
        tracker.record("10.0.0.1", 22, "ssh", "nmap", "port_scan", "open")
        tracker.record("10.0.0.2", 22, "ssh", "nmap", "port_scan", "open")
        target1 = tracker.get_by_target("10.0.0.1")
        assert len(target1) == 1
        assert target1[0]["target"] == "10.0.0.1"

    def test_get_by_tool(self, tracker):
        tracker.record("10.0.0.1", 22, "ssh", "nmap", "port_scan", "open")
        tracker.record("10.0.0.1", 443, "https", "sslscan", "ssl_scan", "weak")
        nmap_entries = tracker.get_by_tool("nmap")
        assert len(nmap_entries) == 1

    def test_untested_targets(self, tracker):
        tracker.record("10.0.0.1", 22, "ssh", "nmap", "port_scan", "open")
        untested = tracker.get_untested_targets(["10.0.0.1", "10.0.0.2", "10.0.0.3"])
        assert "10.0.0.2" in untested
        assert "10.0.0.3" in untested
        assert "10.0.0.1" not in untested

    def test_summary(self, tracker):
        tracker.record("10.0.0.1", 22, "ssh", "nmap", "port_scan", "open")
        tracker.record("10.0.0.1", 80, "http", "nikto", "web_scan", "clean")
        tracker.record("10.0.0.2", 22, "ssh", "nmap", "port_scan", "open")
        s = tracker.summary()
        assert s["total_checks"] == 3
        assert s["unique_targets"] == 2
        assert s["unique_tools"] == 2

    def test_coverage_report(self, tracker):
        tracker.record("10.0.0.1", 22, "ssh", "nmap", "port_scan", "open")
        tracker.record("10.0.0.1", 443, "https", "sslscan", "ssl_scan", "weak")
        report = tracker.coverage_report(["10.0.0.1", "10.0.0.2"])
        assert "Coverage Report" in report
        assert "10.0.0.1" in report
        assert "10.0.0.2" in report  # untested
        assert (tracker.report_path).exists()

    def test_empty_coverage(self, tmp_path):
        tracker = CoverageTracker(tmp_path)
        entries = tracker.get_all()
        assert entries == []
        s = tracker.summary()
        assert s["total_checks"] == 0

    def test_record_from_tool_result(self, tracker):
        tool_result = {
            "command": "nmap -p 22 10.0.0.5",
            "exit_code": 0,
            "stdout": "22/tcp open ssh",
        }
        cov_id = tracker.record_from_tool_result(tool_result, "aria", "10.0.0.5")
        assert cov_id is not None
        entries = tracker.get_all()
        assert len(entries) == 1
        assert entries[0]["tool"] == "nmap"
        assert entries[0]["port"] == 22

    def test_record_from_tool_result_scope_blocked(self, tracker):
        tool_result = {
            "command": "nmap 10.0.0.99",
            "exit_code": -2,
            "stdout": "",
            "scope_blocked": True,
        }
        cov_id = tracker.record_from_tool_result(tool_result, "aria", "10.0.0.99")
        assert cov_id is not None
        entries = tracker.get_all()
        assert entries[0]["result"] == "scope_blocked"

    def test_coverage_file_persistence(self, tmp_path):
        """Coverage entries should persist to JSONL file."""
        tracker1 = CoverageTracker(tmp_path)
        tracker1.record("10.0.0.1", 22, "ssh", "nmap", "port_scan", "open")
        # New tracker instance reads same file
        tracker2 = CoverageTracker(tmp_path)
        entries = tracker2.get_all()
        assert len(entries) == 1