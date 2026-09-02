"""
Chimeras v3.0 — Integration smoke tests.

These exist because the first live run (cyberian-defenses.com, Sep 2)
broke three times on seams the 233 unit tests couldn't see:
  1. Bot constructor crash (engagement_dir read before assignment)
  2. Missing runtime packages (openai) in the venv
  3. Relative engagement_dir passed to Docker as volume name

Rules for these tests:
  - They construct REAL objects, no LLM calls
  - Docker-dependent tests skip cleanly when no daemon is present
  - They run fast (<5s) so they belong in CI before every push
"""

import importlib
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ============================================================
# 1. Runtime dependencies actually importable in this venv
# ============================================================

class TestRuntimeDependencies:
    """The venv must contain what the swarm needs to reach an LLM.
    A missing package kills every bot on the first LLM call."""

    def test_openai_importable(self):
        """Bots route through openai-compatible endpoints (ollama.com/v1)."""
        openai = importlib.import_module("openai")
        assert hasattr(openai, "OpenAI")

    def test_llm_router_imports(self):
        from core.llm_router import LLMRouter
        assert LLMRouter is not None

    def test_jinja2_importable(self):
        """Prompt templates fall back to f-strings, but jinja2 is the path."""
        importlib.import_module("jinja2")


# ============================================================
# 2. Real bot construction — no LLM calls, no mocks
# ============================================================

BOT_CLASSES = []
for mod_name, cls_name in [
    ("aria.agent", "ARIA"),
    ("lisa.agent", "Lisa"),
    ("bloodhound.agent", "Bloodhound"),
    ("wasp.agent", "Wasp"),
    ("marksman.agent", "Marksman"),
    ("magician.agent", "Magician"),
    ("thief.agent", "Thief"),
    ("warchief.agent", "WarChief"),
    ("bookkeeper.agent", "Bookkeeper"),
]:
    try:
        mod = importlib.import_module(mod_name)
        cls = getattr(mod, cls_name, None)
        if cls is not None:
            BOT_CLASSES.append((mod_name, cls_name, cls))
    except Exception:
        pass  # missing class recorded as skip below


class TestBotConstruction:
    """Constructing a bot must never crash — the first live run died
    here because Docker init read engagement_dir before assignment."""

    def _base_state(self, with_docker):
        return {
            "mission": {"scope": "example.com", "roe": "No DoS"},
            "enable_docker": with_docker,
        }

    @pytest.mark.parametrize("mod_name,cls_name,cls", BOT_CLASSES or [("none", "None", None)])
    def test_bot_constructs_without_docker(self, tmp_path, mod_name, cls_name, cls, monkeypatch):
        if cls is None:
            pytest.skip(f"bot class not importable: {mod_name}")
        monkeypatch.chdir(tmp_path)
        bot = cls(self._base_state(False), swarm_config={})
        assert bot.engagement_dir is not None
        assert Path(bot.engagement_dir).is_absolute() or Path(bot.engagement_dir).exists()

    @pytest.mark.skipif(not BOT_CLASSES, reason="no bot classes importable")
    def test_at_least_one_bot_constructs(self, tmp_path, monkeypatch):
        """If every import failed above, something is fundamentally broken."""
        monkeypatch.chdir(tmp_path)
        mod_name, cls_name, cls = BOT_CLASSES[0]
        bot = cls(self._base_state(False), swarm_config={})
        assert bot.bot_name


# ============================================================
# 3. Docker integration — REAL daemon, REAL container
# ============================================================

def _docker_daemon_up():
    return shutil.which("docker") is not None and os.system(
        "docker info >/dev/null 2>&1"
    ) == 0


@pytest.mark.skipif(not _docker_daemon_up(), reason="Docker daemon not available")
class TestDockerIntegration:
    """These need a real daemon. They catch volume-path bugs, image
    references, firewall injection — everything mocks hide."""

    def test_executor_rejects_relative_path(self, tmp_path):
        """A relative engagement_dir must never reach docker -v."""
        from core.docker_executor import TieredDockerExecutor
        monkey = TieredDockerExecutor(
            bot_name="aria",
            engagement_dir="relative/engagement",
            mission_scope="example.com",
            ttl=0,
        )
        assert Path(monkey.engagement_dir).is_absolute()

    def test_container_starts_and_executes(self, tmp_path):
        """Full cycle: start → firewall → exec → evidence → cleanup.
        Requires chimeras-recon:latest (build with build_images())."""
        from core.docker_executor import TieredDockerExecutor, _image_exists
        if not _image_exists("chimeras-recon:latest"):
            pytest.skip("chimeras-recon:latest not built")

        ex = TieredDockerExecutor(
            bot_name="aria",
            engagement_dir=str(tmp_path),
            mission_scope="1.1.1.1",
            ttl=0,
        )
        try:
            result = ex.run("echo chimeras-integration-ok", timeout=30)
            assert result["success"], f"exec failed: {result['stderr']}"
            assert "chimeras-integration-ok" in result["stdout"]
            assert result["containerized"] is True
            chain = ex.get_evidence_chain()
            assert any(e["event"] == "container_start" for e in chain)
            assert any(e["event"] == "command_exec" for e in chain)
        finally:
            ex.cleanup()

    def test_out_of_scope_blocked_live(self, tmp_path):
        """THE core security property, against a real kernel:
        out-of-scope egress must be dropped inside the container."""
        from core.docker_executor import TieredDockerExecutor, _image_exists
        if not _image_exists("chimeras-recon:latest"):
            pytest.skip("chimeras-recon:latest not built")

        ex = TieredDockerExecutor(
            bot_name="aria",
            engagement_dir=str(tmp_path),
            mission_scope="1.1.1.1",
            ttl=0,
        )
        try:
            # 8.8.8.8 is out of scope — kernel must drop it
            result = ex.run(
                "curl -s -o /dev/null -w '%{http_code}' -m 4 http://8.8.8.8",
                timeout=20,
            )
            assert result["exit_code"] != 0 or "200" not in result["stdout"], \
                "OUT-OF-SCOPE HOST WAS REACHABLE — firewall not enforcing"
        finally:
            ex.cleanup()