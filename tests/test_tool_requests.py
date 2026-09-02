"""
Chimeras v3.0.2 — Tool request registry tests.

The arsenal improvement loop: bots that hit a missing tool file a request
(LLM-initiated or auto-detected from 'command not found'), requests land
in per-engagement CSV + global registry, Bookkeeper surfaces them in the
report, and summarize_registry() aggregates for image/category planning.
"""

import csv
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.tool_requests import (
    HEADER,
    detect_not_found,
    log_tool_requests,
    summarize_registry,
    _GLOBAL_REGISTRY,
    _append_csv,
)


@pytest.fixture(autouse=True)
def clean_registry(tmp_path, monkeypatch):
    """Point the global registry at a temp file — tests never touch the real one."""
    import core.tool_requests as tr
    fake = tmp_path / "registry.csv"
    monkeypatch.setattr(tr, "_GLOBAL_REGISTRY", fake, raising=True)
    yield fake


class TestLogToolRequests:
    def test_llm_request_lands_in_engagement_csv(self, tmp_path):
        eng = tmp_path / "engagement"
        filed = log_tool_requests(
            bot_name="wasp",
            requests=[{
                "tool": "ffuf",
                "description": "fast web fuzzer",
                "use_case": "directory brute force on https target",
                "arguments": "ffuf -u https://x/FUZZ -w words.txt",
            }],
            engagement_dir=str(eng),
            source="llm_request",
        )
        assert filed == 1
        csv_path = eng / "tool_requests.csv"
        assert csv_path.exists()
        with open(csv_path) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["agent"] == "wasp"
        assert rows[0]["tool"] == "ffuf"
        assert rows[0]["source"] == "llm_request"
        assert rows[0]["date"]  # ISO timestamp present

    def test_request_without_tool_is_noise(self, tmp_path):
        filed = log_tool_requests(
            bot_name="lisa",
            requests=[{"description": "no tool name"}],
            engagement_dir=str(tmp_path),
        )
        assert filed == 0

    def test_global_registry_accumulates_across_engagements(self, tmp_path):
        log_tool_requests("aria", [{"tool": "amass"}], engagement_dir=str(tmp_path / "e1"))
        log_tool_requests("lisa", [{"tool": "amass"}], engagement_dir=str(tmp_path / "e2"))
        log_tool_requests("wasp", [{"tool": "ffuf"}], engagement_dir=str(tmp_path / "e3"))

        agg = summarize_registry()
        assert agg["amass"]["count"] == 2
        assert agg["ffuf"]["count"] == 1
        assert agg["amass"]["by_agent"] == {"aria": 1, "lisa": 1}

    def test_header_written_once_on_append(self, tmp_path):
        path = tmp_path / "out.csv"
        _append_csv(path, [{"date": "d", "agent": "a", "tool": "t",
                            "description": "", "use_case": "", "arguments": "",
                            "source": "s"}])
        _append_csv(path, [{"date": "d2", "agent": "a", "tool": "t2",
                            "description": "", "use_case": "", "arguments": "",
                            "source": "s"}])
        with open(path) as f:
            lines = f.read().strip().split("\n")
        assert lines[0].split(",") == HEADER
        assert len(lines) == 3  # header + 2 rows


class TestDetectNotFound:
    def test_command_not_found_becomes_request(self):
        results = [{
            "command": "searchsploit nginx 1.24",
            "success": False,
            "exit_code": 127,
            "stderr": "sh: 1: searchsploit: not found",
            "stdout": "",
        }]
        implicit = detect_not_found(results)
        assert len(implicit) == 1
        assert implicit[0]["tool"] == "searchsploit"
        assert "nginx 1.24" in implicit[0]["use_case"]

    def test_successful_run_is_not_a_request(self):
        results = [{
            "command": "nmap -sV target",
            "success": True,
            "exit_code": 0,
            "stderr": "",
            "stdout": "Starting Nmap...",
        }]
        assert detect_not_found(results) == []

    def test_other_failures_are_not_requests(self):
        """A failed ping is a dead host, not a missing tool."""
        results = [{
            "command": "ping -c 1 10.0.0.1",
            "success": False,
            "exit_code": 1,
            "stderr": "",
            "stdout": "1 packets transmitted, 0 received",
        }]
        assert detect_not_found(results) == []

    def test_docker_sh_message_detected(self):
        """Docker containers report 'executable file not found'."""
        results = [{
            "command": "wafw00f https://target",
            "success": False,
            "exit_code": 127,
            "stderr": "sh: wafw00f: executable file not found",
            "stdout": "",
        }]
        implicit = detect_not_found(results)
        assert len(implicit) == 1
        assert implicit[0]["tool"] == "wafw00f"


class TestImprovementLoopEndToEnd:
    def test_full_loop_detect_log_summarize(self, tmp_path):
        """The complete cycle: failed execution → CSV → registry → aggregation."""
        results = [{
            "command": "sqlmap -u https://target/?id=1 --batch",
            "success": False,
            "exit_code": 127,
            "stderr": "sh: sqlmap: command not found",
            "stdout": "",
        }]
        implicit = detect_not_found(results)
        filed = log_tool_requests(
            bot_name="wasp",
            requests=implicit,
            engagement_dir=str(tmp_path / "eng"),
            source="auto_not_found",
        )
        assert filed == 1

        # engagement CSV exists and the report would include it
        assert (tmp_path / "eng" / "tool_requests.csv").exists()

        # global registry aggregated correctly
        agg = summarize_registry()
        assert "sqlmap" in agg
        assert agg["sqlmap"]["count"] == 1
        assert agg["sqlmap"]["by_agent"] == {"wasp": 1}