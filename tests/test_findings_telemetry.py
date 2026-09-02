"""
Tests for P0 fixes in core/findings_store.py and core/telemetry.py.

Covers:
- FindingsStore: thread-safe writes, get_verified(), merge_all()
- Telemetry: record_tool_exec parse_ok parameter, summary parse failure rate
"""
import json
import threading
from pathlib import Path

import pytest

from core.findings_store import FindingsStore
from core.telemetry import Telemetry


# ─── FindingsStore thread safety ───


class TestFindingsStoreThreadSafety:
    """Tests for threading.Lock around JSONL writes (P0 Fix 1)."""

    def test_concurrent_writes_no_corruption(self, findings_store):
        """Multiple threads writing to the same bot's JSONL should not
        produce corrupted/interleaved lines."""
        bot_name = "bloodhound"
        num_threads = 10
        writes_per_thread = 20

        def writer(thread_id):
            for i in range(writes_per_thread):
                findings_store.add(bot_name, {
                    "finding_id": f"BH-{thread_id:02d}{i:03d}",
                    "title": f"Finding from thread {thread_id} #{i}",
                    "severity": "Info",
                    "cvss": 0.0,
                    "source_bot": bot_name,
                })

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Every line should be valid JSON — no interleaving
        findings = findings_store.get_bot_findings(bot_name)
        assert len(findings) == num_threads * writes_per_thread
        for f in findings:
            assert "finding_id" in f
            assert f["finding_id"].startswith("BH-")

    def test_concurrent_writes_different_bots(self, findings_store):
        """Different bots writing to their own files concurrently."""
        bots = ["aria", "lisa", "bloodhound", "wasp"]
        writes_per_bot = 15

        def bot_writer(bot):
            for i in range(writes_per_bot):
                findings_store.add(bot, {
                    "finding_id": f"{bot[:2].upper()}-{i:03d}",
                    "title": f"Finding {i}",
                    "severity": "Info",
                    "source_bot": bot,
                })

        threads = [threading.Thread(target=bot_writer, args=(b,)) for b in bots]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        all_findings = findings_store.get_all()
        assert len(all_findings) == len(bots) * writes_per_bot

    def test_write_lock_is_threading_lock(self):
        """Verify the class has a threading.Lock attribute."""
        assert hasattr(FindingsStore, "_write_lock")
        assert isinstance(FindingsStore._write_lock, type(threading.Lock()))


# ─── FindingsStore get_verified ───


class TestFindingsStoreGetVerified:
    """Tests for get_verified() method (P0 Fix 3)."""

    def test_get_verified_returns_only_verified(self, findings_store):
        findings_store.add("bloodhound", {
            "finding_id": "BH-001",
            "title": "Verified finding",
            "verified_by_cycle": 3,
        })
        findings_store.add("bloodhound", {
            "finding_id": "BH-002",
            "title": "Unverified finding",
            "verified_by_cycle": None,
        })
        verified = findings_store.get_verified()
        assert len(verified) == 1
        assert verified[0]["finding_id"] == "BH-001"

    def test_get_verified_empty_when_none_verified(self, findings_store):
        findings_store.add("bloodhound", {
            "finding_id": "BH-001",
            "title": "Unverified",
            "verified_by_cycle": None,
        })
        assert findings_store.get_verified() == []

    def test_get_verified_all_when_all_verified(self, findings_store):
        findings_store.add("bloodhound", {
            "finding_id": "BH-001",
            "verified_by_cycle": 1,
        })
        findings_store.add("wasp", {
            "finding_id": "WASP-001",
            "verified_by_cycle": 2,
        })
        verified = findings_store.get_verified()
        assert len(verified) == 2

    def test_get_verified_empty_store(self, findings_store):
        assert findings_store.get_verified() == []

    def test_get_verified_excludes_missing_field(self, findings_store):
        """Findings without verified_by_cycle field at all should be excluded."""
        findings_store.add("bloodhound", {
            "finding_id": "BH-001",
            "title": "No verified field",
        })
        assert findings_store.get_verified() == []

    def test_get_verified_includes_cycle_zero(self, findings_store):
        """verified_by_cycle=0 is not None — should be included."""
        findings_store.add("bloodhound", {
            "finding_id": "BH-001",
            "verified_by_cycle": 0,
        })
        verified = findings_store.get_verified()
        assert len(verified) == 1


# ─── FindingsStore basic functionality ───


class TestFindingsStoreBasic:
    """Basic FindingsStore operations."""

    def test_add_and_get(self, findings_store):
        fid = findings_store.add("bloodhound", {
            "finding_id": "BH-001",
            "title": "Test finding",
            "severity": "Critical",
            "cvss": 9.0,
        })
        assert fid == "BH-001"
        findings = findings_store.get_bot_findings("bloodhound")
        assert len(findings) == 1
        assert findings[0]["title"] == "Test finding"

    def test_auto_generate_finding_id(self, findings_store):
        fid = findings_store.add("bloodhound", {"title": "No ID"})
        assert fid.startswith("BLA") or fid.startswith("BLO") or fid.startswith("BH-")

    def test_get_all_merges_bots(self, findings_store):
        findings_store.add("aria", {"finding_id": "ARI-001", "title": "a"})
        findings_store.add("lisa", {"finding_id": "LIS-001", "title": "l"})
        all_f = findings_store.get_all()
        assert len(all_f) == 2

    def test_get_critical_filters_by_cvss(self, findings_store):
        findings_store.add("bloodhound", {"finding_id": "BH-001", "cvss": 9.0})
        findings_store.add("bloodhound", {"finding_id": "BH-002", "cvss": 3.0})
        findings_store.add("bloodhound", {"finding_id": "BH-003", "cvss": 7.5})
        critical = findings_store.get_critical(min_cvss=7.0)
        assert len(critical) == 2

    def test_merge_all_creates_file(self, findings_store):
        findings_store.add("bloodhound", {"finding_id": "BH-001", "cvss": 9.0})
        findings_store.add("aria", {"finding_id": "ARI-001", "cvss": 5.0})
        merged_path = findings_store.merge_all()
        assert merged_path.exists()
        lines = merged_path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_deduplicate_removes_dupes(self, findings_store):
        findings_store.add("bloodhound", {"finding_id": "BH-001", "title": "a"})
        findings_store.add("bloodhound", {"finding_id": "BH-001", "title": "a"})
        findings_store.add("bloodhound", {"finding_id": "BH-002", "title": "b"})
        removed = findings_store.deduplicate()
        assert removed == 1
        remaining = findings_store.get_bot_findings("bloodhound")
        assert len(remaining) == 2


# ─── Telemetry parse_ok ───


class TestTelemetryParseOk:
    """Tests for parse_ok parameter in record_tool_exec (P0 Fix 2)."""

    def test_record_tool_exec_parse_ok_true(self, telemetry):
        telemetry.record_tool_exec(
            "bloodhound", "nmap", "10.10.10.5",
            1.5, exit_code=0, parse_ok=True,
        )
        events = telemetry.read_all()
        assert len(events) == 1
        assert events[0]["parse_ok"] is True
        assert events[0]["success"] is True

    def test_record_tool_exec_parse_ok_false(self, telemetry):
        telemetry.record_tool_exec(
            "bloodhound", "nmap", "10.10.10.5",
            1.5, exit_code=0, parse_ok=False,
        )
        events = telemetry.read_all()
        assert events[0]["parse_ok"] is False
        assert events[0]["success"] is False

    def test_record_tool_exec_parse_ok_defaults_true(self, telemetry):
        """parse_ok should default to True for backward compatibility."""
        telemetry.record_tool_exec(
            "bloodhound", "nmap", "10.10.10.5", 1.5, exit_code=0,
        )
        events = telemetry.read_all()
        assert events[0]["parse_ok"] is True

    def test_record_llm_call_parse_ok_false(self, telemetry):
        telemetry.record_llm_call(
            "bloodhound", "ollama", "deepseek",
            12.0, parse_ok=False,
        )
        events = telemetry.read_all()
        assert events[0]["parse_ok"] is False
        assert events[0]["success"] is False

    def test_summary_counts_tool_parse_failures(self, telemetry):
        """summary() should count tool_exec parse_ok=False in parse_failures."""
        telemetry.record_llm_call("bloodhound", "ollama", "model", 1.0, parse_ok=True)
        telemetry.record_tool_exec("bloodhound", "nmap", "target", 1.0, parse_ok=False)
        summary = telemetry.summary()
        assert summary["parse_failures"] == 1
        assert summary["parse_failure_rate"] > 0

    def test_summary_counts_both_llm_and_tool_failures(self, telemetry):
        telemetry.record_llm_call("a", "p", "m", 1.0, parse_ok=False)
        telemetry.record_tool_exec("a", "t", "tgt", 1.0, parse_ok=False)
        summary = telemetry.summary()
        assert summary["parse_failures"] == 2

    def test_summary_zero_failures_when_all_ok(self, telemetry):
        telemetry.record_llm_call("a", "p", "m", 1.0, parse_ok=True)
        telemetry.record_tool_exec("a", "t", "tgt", 1.0, parse_ok=True)
        summary = telemetry.summary()
        assert summary["parse_failures"] == 0
        assert summary["parse_failure_rate"] == 0

    def test_summary_empty(self, telemetry):
        summary = telemetry.summary()
        assert summary == {"total_events": 0}