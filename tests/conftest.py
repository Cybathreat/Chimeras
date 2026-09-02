"""
Shared pytest fixtures for the Chimeras test suite.

Provides:
- tmp_engagement_dir: a temporary engagement directory for per-test isolation
- mock_state: a minimal SwarmState-like dict for routing/graph tests
- findings_store / telemetry: pre-wired to the temp engagement dir
"""
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from core.findings_store import FindingsStore
from core.telemetry import Telemetry


@pytest.fixture
def tmp_engagement_dir(tmp_path: Path) -> Path:
    """Create a temporary engagement directory that is cleaned up after the test."""
    eng = tmp_path / "engagement"
    eng.mkdir(parents=True, exist_ok=True)
    return eng


@pytest.fixture
def findings_store(tmp_engagement_dir: Path) -> FindingsStore:
    """FindingsStore pointed at the temp engagement dir."""
    return FindingsStore(tmp_engagement_dir)


@pytest.fixture
def telemetry(tmp_engagement_dir: Path) -> Telemetry:
    """Telemetry logger pointed at the temp engagement dir."""
    return Telemetry(tmp_engagement_dir)


@pytest.fixture
def mock_state(tmp_engagement_dir: Path) -> Dict[str, Any]:
    """A minimal SwarmState-like dict for routing / graph tests.

    Contains only the fields that routing functions read. Individual tests
    can override or extend as needed.
    """
    return {
        "engagement_dir": str(tmp_engagement_dir),
        "last_decision": "",
        "loop_count": {},
        "max_loops_per_phase": 5,
        "mission": {
            "scope": "10.10.10.0/24",
            "target": "10.10.10.5",
            "roe": "no dos, no destruction",
        },
        "reasoning_reports": {},
        "decision_history": [],
        "mission_state": "init",
        "target_context": "external",
        "human_approval": False,
        "lateral_approval": False,
        "scope_expansion_candidates": [],
        "approved_extra_targets": [],
        "failed_vectors": [],
        "internal_scope": "",
    }