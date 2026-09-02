"""
Tests for graph.py — routing functions, loop limits, stuck detection,
force-complete-cycle logic.

Covers:
- route_after_recon, route_after_scan, route_after_vuln
- _check_loop_limit, _increment_loop
- _has_bot_report, _has_critical_findings
- _unified_router (scope expansion, stuck detection, force-complete-cycle)
"""
import json
from pathlib import Path

import pytest

from graph import (
    route_after_recon,
    route_after_scan,
    route_after_vuln,
    route_after_exploit,
    route_after_privesc,
    route_after_exfil,
    route_after_lateral_approval,
    _unified_router,
    _increment_loop,
    _check_loop_limit,
    _has_bot_report,
    _has_critical_findings,
    can_parallelize,
)


# ─── Loop counter tests ───


class TestLoopCounter:
    """Tests for _increment_loop and _check_loop_limit."""

    def test_increment_returns_new_count(self, mock_state):
        count = _increment_loop(mock_state, "recon")
        assert count == 1
        count = _increment_loop(mock_state, "recon")
        assert count == 2

    def test_increment_different_phases(self, mock_state):
        _increment_loop(mock_state, "recon")
        _increment_loop(mock_state, "scan")
        assert mock_state["loop_count"]["recon"] == 1
        assert mock_state["loop_count"]["scan"] == 1

    def test_check_loop_limit_not_exceeded(self, mock_state):
        _increment_loop(mock_state, "recon")
        assert not _check_loop_limit(mock_state, "recon")

    def test_check_loop_limit_exceeded(self, mock_state):
        for _ in range(5):
            _increment_loop(mock_state, "recon")
        assert _check_loop_limit(mock_state, "recon")

    def test_check_loop_limit_default_max(self, mock_state):
        """Default max_loops_per_phase is 5."""
        for _ in range(4):
            _increment_loop(mock_state, "scan")
        assert not _check_loop_limit(mock_state, "scan")
        _increment_loop(mock_state, "scan")
        assert _check_loop_limit(mock_state, "scan")

    def test_check_loop_limit_custom_max(self, mock_state):
        mock_state["max_loops_per_phase"] = 3
        for _ in range(3):
            _increment_loop(mock_state, "vuln")
        assert _check_loop_limit(mock_state, "vuln")

    def test_check_loop_limit_no_loops_dict(self, mock_state):
        mock_state["loop_count"] = "not a dict"
        assert not _check_loop_limit(mock_state, "recon")

    def test_check_loop_limit_missing_phase(self, mock_state):
        assert not _check_loop_limit(mock_state, "nonexistent")

    def test_increment_handles_missing_dict(self, mock_state):
        mock_state["loop_count"] = "invalid"
        count = _increment_loop(mock_state, "recon")
        # Should not crash; behavior is to reset
        assert isinstance(mock_state["loop_count"], dict)


# ─── route_after_recon ───


class TestRouteAfterRecon:
    """Tests for route_after_recon."""

    def test_scan_decision_routes_to_lisa(self, mock_state):
        mock_state["last_decision"] = "scan"
        assert route_after_recon(mock_state) == "lisa"

    def test_recon_decision_routes_to_aria(self, mock_state):
        mock_state["last_decision"] = "recon"
        assert route_after_recon(mock_state) == "aria"

    def test_vuln_detection_routes_to_bloodhound(self, mock_state):
        mock_state["last_decision"] = "vuln_detection"
        assert route_after_recon(mock_state) == "bloodhound"

    def test_loop_limit_forces_lisa(self, mock_state):
        for _ in range(5):
            _increment_loop(mock_state, "recon")
        mock_state["last_decision"] = "recon"
        assert route_after_recon(mock_state) == "lisa"

    def test_report_blocked_without_lisa(self, mock_state):
        """Cannot abort to report before scanning — force Lisa."""
        mock_state["last_decision"] = "report"
        assert route_after_recon(mock_state) == "lisa"

    def test_report_blocked_without_bloodhound(self, mock_state):
        """Cannot abort before vuln detection — force Bloodhound."""
        mock_state["last_decision"] = "report"
        # Simulate Lisa has run
        (Path(mock_state["engagement_dir"]) / "lisa.md").write_text("x" * 200)
        assert route_after_recon(mock_state) == "bloodhound"

    def test_report_allowed_when_all_phases_complete(self, mock_state):
        """When all phases have run, report should be allowed."""
        mock_state["last_decision"] = "report"
        eng = Path(mock_state["engagement_dir"])
        (eng / "lisa.md").write_text("x" * 200)
        (eng / "bloodhound.md").write_text("x" * 200)
        (eng / "marksman.md").write_text("x" * 200)
        assert route_after_recon(mock_state) == "bookkeeper"

    def test_force_exploit_when_critical_exists(self, mock_state):
        """Critical findings but no marksman → force human_approval."""
        mock_state["last_decision"] = "report"
        eng = Path(mock_state["engagement_dir"])
        (eng / "lisa.md").write_text("x" * 200)
        (eng / "bloodhound.md").write_text("x" * 200)
        # Write a critical finding
        findings_path = eng / "findings_bloodhound.jsonl"
        findings_path.write_text(
            json.dumps({"finding_id": "BH-001", "cvss": 9.5, "title": "RCE"}) + "\n"
        )
        assert route_after_recon(mock_state) == "human_approval"

    def test_lateral_recon_routes_to_approval(self, mock_state):
        mock_state["last_decision"] = "lateral_recon"
        assert route_after_recon(mock_state) == "lateral_approval"

    def test_unknown_decision_defaults_to_lisa(self, mock_state):
        mock_state["last_decision"] = "nonsensical"
        assert route_after_recon(mock_state) == "lisa"


# ─── route_after_scan ───


class TestRouteAfterScan:
    """Tests for route_after_scan."""

    def test_vulns_found_routes_to_bloodhound(self, mock_state):
        mock_state["last_decision"] = "vulns_found_exploit"
        assert route_after_scan(mock_state) == "bloodhound"

    def test_vuln_detection_routes_to_bloodhound(self, mock_state):
        mock_state["last_decision"] = "vuln_detection"
        assert route_after_scan(mock_state) == "bloodhound"

    def test_recon_routes_to_aria(self, mock_state):
        mock_state["last_decision"] = "recon"
        assert route_after_scan(mock_state) == "aria"

    def test_loop_limit_forces_bloodhound(self, mock_state):
        for _ in range(5):
            _increment_loop(mock_state, "scan")
        mock_state["last_decision"] = "scan"
        assert route_after_scan(mock_state) == "bloodhound"

    def test_report_blocked_without_bloodhound(self, mock_state):
        mock_state["last_decision"] = "report"
        assert route_after_scan(mock_state) == "bloodhound"

    def test_scan_repeat_forces_bloodhound(self, mock_state):
        """2+ scan cycles should force advance to Bloodhound."""
        _increment_loop(mock_state, "scan")
        _increment_loop(mock_state, "scan")
        mock_state["last_decision"] = "scan"
        assert route_after_scan(mock_state) == "bloodhound"

    def test_scan_first_cycle_returns_lisa(self, mock_state):
        _increment_loop(mock_state, "scan")
        mock_state["last_decision"] = "scan"
        assert route_after_scan(mock_state) == "lisa"

    def test_unknown_decision_defaults_to_bloodhound(self, mock_state):
        mock_state["last_decision"] = "nonsensical"
        assert route_after_scan(mock_state) == "bloodhound"


# ─── route_after_vuln ───


class TestRouteAfterVuln:
    """Tests for route_after_vuln."""

    def test_vulns_found_routes_to_human_approval(self, mock_state):
        mock_state["last_decision"] = "vulns_found_exploit"
        assert route_after_vuln(mock_state) == "human_approval"

    def test_scan_routes_to_lisa(self, mock_state):
        mock_state["last_decision"] = "scan"
        assert route_after_vuln(mock_state) == "lisa"

    def test_recon_routes_to_aria(self, mock_state):
        mock_state["last_decision"] = "recon"
        assert route_after_vuln(mock_state) == "aria"

    def test_loop_limit_forces_bookkeeper(self, mock_state):
        for _ in range(5):
            _increment_loop(mock_state, "vuln")
        mock_state["last_decision"] = "vulns_found_exploit"
        assert route_after_vuln(mock_state) == "bookkeeper"

    def test_report_with_critical_forces_exploit(self, mock_state):
        """Critical findings + no exploit attempted → force human_approval."""
        mock_state["last_decision"] = "report"
        eng = Path(mock_state["engagement_dir"])
        findings_path = eng / "findings_bloodhound.jsonl"
        findings_path.write_text(
            json.dumps({"finding_id": "BH-001", "cvss": 9.0}) + "\n"
        )
        mock_state["mission_state"] = "vuln_detection"
        assert route_after_vuln(mock_state) == "human_approval"

    def test_report_without_critical_goes_to_bookkeeper(self, mock_state):
        mock_state["last_decision"] = "report"
        mock_state["mission_state"] = "exploitation"
        assert route_after_vuln(mock_state) == "bookkeeper"

    def test_unknown_decision_defaults_to_human_approval(self, mock_state):
        mock_state["last_decision"] = "nonsensical"
        assert route_after_vuln(mock_state) == "human_approval"


# ─── route_after_exploit / privesc / exfil ───


class TestRouteAfterExploit:
    """Tests for route_after_exploit."""

    def test_privesc_routes_to_magician(self, mock_state):
        mock_state["last_decision"] = "privesc"
        assert route_after_exploit(mock_state) == "magician"

    def test_continue_exploit_routes_to_marksman(self, mock_state):
        mock_state["last_decision"] = "continue_exploit"
        assert route_after_exploit(mock_state) == "marksman"

    def test_report_routes_to_bookkeeper(self, mock_state):
        mock_state["last_decision"] = "report"
        assert route_after_exploit(mock_state) == "bookkeeper"

    def test_three_failed_exploits_forces_bookkeeper(self, mock_state):
        mock_state["failed_vectors"] = [
            {"tool": "msfconsole", "error": "failed"},
            {"tool": "sqlmap", "error": "failed"},
            {"tool": "nc", "error": "failed"},
        ]
        mock_state["last_decision"] = "privesc"
        assert route_after_exploit(mock_state) == "bookkeeper"

    def test_lateral_recon_routes_to_approval(self, mock_state):
        mock_state["last_decision"] = "lateral_recon"
        assert route_after_exploit(mock_state) == "lateral_approval"


class TestRouteAfterPrivesc:
    """Tests for route_after_privesc."""

    def test_exfiltrate_routes_to_thief(self, mock_state):
        mock_state["last_decision"] = "exfiltrate"
        assert route_after_privesc(mock_state) == "thief"

    def test_continue_exploit_routes_to_marksman(self, mock_state):
        mock_state["last_decision"] = "continue_exploit"
        assert route_after_privesc(mock_state) == "marksman"

    def test_report_routes_to_bookkeeper(self, mock_state):
        mock_state["last_decision"] = "report"
        assert route_after_privesc(mock_state) == "bookkeeper"


class TestRouteAfterExfil:
    """Tests for route_after_exfil."""

    def test_report_routes_to_bookkeeper(self, mock_state):
        mock_state["last_decision"] = "report"
        assert route_after_exfil(mock_state) == "bookkeeper"

    def test_exfiltrate_routes_to_thief(self, mock_state):
        mock_state["last_decision"] = "exfiltrate"
        assert route_after_exfil(mock_state) == "thief"


# ─── _has_bot_report / _has_critical_findings ───


class TestHasBotReport:
    """Tests for _has_bot_report."""

    def test_no_eng_dir_returns_false(self):
        assert not _has_bot_report("", "lisa")

    def test_nonexistent_dir_returns_false(self):
        assert not _has_bot_report("/nonexistent/path", "lisa")

    def test_md_report_exists(self, tmp_path):
        (tmp_path / "lisa.md").write_text("x" * 200)
        assert _has_bot_report(str(tmp_path), "lisa")

    def test_md_report_too_small_returns_false(self, tmp_path):
        """File smaller than 100 bytes should not count."""
        (tmp_path / "lisa.md").write_text("tiny")
        assert not _has_bot_report(str(tmp_path), "lisa")

    def test_jsonl_findings_exist(self, tmp_path):
        (tmp_path / "findings_lisa.jsonl").write_text(
            json.dumps({"finding_id": "LIS-001"}) + "\n"
        )
        assert _has_bot_report(str(tmp_path), "lisa")

    def test_no_report_returns_false(self, tmp_path):
        assert not _has_bot_report(str(tmp_path), "lisa")


class TestHasCriticalFindings:
    """Tests for _has_critical_findings."""

    def test_no_eng_dir_returns_false(self):
        assert not _has_critical_findings("")

    def test_critical_findings_json(self, tmp_path):
        (tmp_path / "critical_findings.json").write_text(
            json.dumps([{"cvss": 9.0}])
        )
        assert _has_critical_findings(str(tmp_path))

    def test_critical_in_jsonl(self, tmp_path):
        (tmp_path / "findings_bloodhound.jsonl").write_text(
            json.dumps({"cvss": 8.5}) + "\n"
        )
        assert _has_critical_findings(str(tmp_path))

    def test_no_critical_returns_false(self, tmp_path):
        (tmp_path / "findings_bloodhound.jsonl").write_text(
            json.dumps({"cvss": 5.0}) + "\n"
        )
        assert not _has_critical_findings(str(tmp_path))

    def test_empty_dir_returns_false(self, tmp_path):
        assert not _has_critical_findings(str(tmp_path))


# ─── _unified_router ───


class TestUnifiedRouter:
    """Tests for _unified_router."""

    def test_init_routes_to_aria(self, mock_state):
        """Initial WarChief with no decision should start recon."""
        mock_state["last_decision"] = ""
        mock_state["reasoning_reports"] = {}
        assert _unified_router(mock_state) == "aria"

    def test_scope_expansion_routes_to_gate(self, mock_state):
        mock_state["last_decision"] = "scan"
        mock_state["scope_expansion_candidates"] = [
            {"target": "new-host.com", "found_by": "aria", "reason": "discovered"}
        ]
        assert _unified_router(mock_state) == "scope_expansion"

    def test_stuck_detection_forces_bookkeeper(self, mock_state):
        """3 same exploitation decisions → force abort."""
        mock_state["last_decision"] = "continue_exploit"
        mock_state["reasoning_reports"] = {"marksman": {}}
        mock_state["decision_history"] = [
            {"decision": "continue_exploit"},
            {"decision": "continue_exploit"},
            {"decision": "continue_exploit"},
        ]
        assert _unified_router(mock_state) == "bookkeeper"

    def test_stuck_detection_not_triggered_for_recon(self, mock_state):
        """Recon loopback should not trigger stuck detection."""
        mock_state["last_decision"] = "recon"
        mock_state["reasoning_reports"] = {"aria": {}}
        mock_state["decision_history"] = [
            {"decision": "recon"},
            {"decision": "recon"},
            {"decision": "recon"},
        ]
        # Should route to aria (recon), not bookkeeper
        assert _unified_router(mock_state) == "aria"

    def test_report_forces_lisa_if_missing(self, mock_state):
        """WarChief wants report but Lisa never ran → force Lisa."""
        mock_state["last_decision"] = "report"
        mock_state["reasoning_reports"] = {"aria": {}}
        assert _unified_router(mock_state) == "lisa"

    def test_report_forces_bloodhound_if_missing(self, mock_state):
        mock_state["last_decision"] = "report"
        mock_state["reasoning_reports"] = {"aria": {}, "lisa": {}}
        eng = Path(mock_state["engagement_dir"])
        (eng / "lisa.md").write_text("x" * 200)
        assert _unified_router(mock_state) == "bloodhound"

    def test_report_forces_exploit_if_critical(self, mock_state):
        mock_state["last_decision"] = "report"
        mock_state["reasoning_reports"] = {"aria": {}, "lisa": {}, "bloodhound": {}}
        eng = Path(mock_state["engagement_dir"])
        (eng / "lisa.md").write_text("x" * 200)
        (eng / "bloodhound.md").write_text("x" * 200)
        (eng / "findings_bloodhound.jsonl").write_text(
            json.dumps({"cvss": 9.0}) + "\n"
        )
        assert _unified_router(mock_state) == "human_approval"

    def test_report_allowed_when_all_complete(self, mock_state):
        mock_state["last_decision"] = "report"
        mock_state["reasoning_reports"] = {
            "aria": {}, "lisa": {}, "bloodhound": {}, "marksman": {}
        }
        eng = Path(mock_state["engagement_dir"])
        for bot in ("lisa", "bloodhound", "marksman"):
            (eng / f"{bot}.md").write_text("x" * 200)
        assert _unified_router(mock_state) == "bookkeeper"

    def test_lateral_routes_to_approval(self, mock_state):
        mock_state["last_decision"] = "lateral_recon"
        mock_state["reasoning_reports"] = {"aria": {}}
        assert _unified_router(mock_state) == "lateral_approval"

    def test_unknown_bot_forward_progress(self, mock_state):
        """Unknown last_bot should try forward progress via decision."""
        mock_state["last_decision"] = "scan"
        mock_state["reasoning_reports"] = {"unknownbot": {}}
        # Should default to forward progress: scan → lisa
        assert _unified_router(mock_state) == "lisa"


# ─── can_parallelize ───


class TestCanParallelize:
    """Tests for can_parallelize utility."""

    def test_bloodhound_wasp_can_parallelize(self):
        assert can_parallelize("bloodhound", "wasp")

    def test_aria_lisa_can_parallelize(self):
        assert can_parallelize("aria", "lisa")

    def test_marksman_magician_cannot(self):
        """Sequential-only bots cannot parallelize."""
        assert not can_parallelize("marksman", "magician")

    def test_dependency_prevents_parallel(self):
        """marksman depends on magician — cannot parallelize."""
        assert not can_parallelize("marksman", "magician")


# ─── route_after_lateral_approval ───


class TestRouteAfterLateralApproval:
    """Tests for route_after_lateral_approval."""

    def test_denied_routes_to_bookkeeper(self, mock_state):
        mock_state["lateral_approval"] = False
        mock_state["last_decision"] = "lateral_recon"
        assert route_after_lateral_approval(mock_state) == "bookkeeper"

    def test_approved_lateral_recon_routes_to_aria(self, mock_state):
        mock_state["lateral_approval"] = True
        mock_state["last_decision"] = "lateral_recon"
        assert route_after_lateral_approval(mock_state) == "aria"

    def test_approved_lateral_scan_routes_to_lisa(self, mock_state):
        mock_state["lateral_approval"] = True
        mock_state["last_decision"] = "lateral_scan"
        assert route_after_lateral_approval(mock_state) == "lisa"