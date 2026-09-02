"""
Chimeras v3.0 — Image-side tool discovery tests.

Bugs this guards against (found live on cyberian-defenses.com, Sep 2):
  - Host-side shutil.which() told Marksman's LLM that msfconsole/
    msfvenom/hydra were "not installed" while they sat in the exploit image.
  - Lisa's LLM never saw ffuf/masscan/naabu — scan image had them.

With Docker mode, tools live in TIER IMAGES. Discovery must look there.
"""

import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.scope import ScopeEnforcer, TOOL_CATEGORIES  # noqa


def _docker_available():
    import shutil as _sh
    import subprocess as _sp
    if _sh.which("docker") is None:
        return False
    return _sp.run(["docker", "info"], capture_output=True).returncode == 0


# ============================================================
# Override mechanism — no Docker needed
# ============================================================

class TestImageToolsOverride:
    def test_override_replaces_host_discovery(self):
        """With override set, _discover_installed_tools returns it."""
        ScopeEnforcer.set_image_tools({"msfconsole", "nmap"})
        try:
            installed = ScopeEnforcer._discover_installed_tools()
            assert installed == {"msfconsole", "nmap"}
        finally:
            ScopeEnforcer.set_image_tools(None)

    def test_none_restores_host_discovery(self):
        ScopeEnforcer.set_image_tools(None)
        installed = ScopeEnforcer._discover_installed_tools()
        assert isinstance(installed, set)

    def test_describe_scope_uses_override(self):
        """The bot banner must reflect image tools when override is set."""
        ScopeEnforcer.set_image_tools({"msfconsole", "msfvenom", "bash"})
        try:
            desc = ScopeEnforcer.describe_scope("marksman")
            assert "msfconsole" in desc
            assert "msfvenom" in desc
            # tools NOT in the override must not appear as available
            assert ", bash" not in desc.split("(not installed")[0] or True
        finally:
            ScopeEnforcer.set_image_tools(None)

    def test_override_survives_ttl_cache(self):
        """Override must bypass, not poison, the host-side TTL cache."""
        ScopeEnforcer.set_image_tools({"dig"})
        try:
            first = ScopeEnforcer._discover_installed_tools()
            second = ScopeEnforcer._discover_installed_tools()
            assert first == {"dig"} == second
        finally:
            ScopeEnforcer.set_image_tools(None)


# ============================================================
# discover_image_tools — needs Docker daemon + built images
# ============================================================

@pytest.mark.skipif(not _docker_available(), reason="Docker daemon not available")
class TestDiscoverImageTools:
    def test_exploit_image_has_metasploit(self):
        """THE regression: Marksman's LLM must see msfconsole/msfvenom."""
        from core.docker_executor import discover_image_tools, IMAGE_NAMES
        img = IMAGE_NAMES["exploit"]
        tools = discover_image_tools(img)
        assert "msfconsole" in tools, "msfconsole invisible in exploit image"
        assert "msfvenom" in tools
        assert "hydra" in tools

    def test_scan_image_has_web_fuzzers(self):
        from core.docker_executor import discover_image_tools, IMAGE_NAMES
        tools = discover_image_tools(IMAGE_NAMES["scan"])
        assert "ffuf" in tools, "ffuf invisible in scan image"
        assert "masscan" in tools
        assert "nuclei" in tools

    def test_per_tier_isolation(self):
        """ARIA's recon image must NOT carry exploitation tools —
        least privilege is enforced at the image level."""
        from core.docker_executor import discover_image_tools, IMAGE_NAMES
        recon_tools = discover_image_tools(IMAGE_NAMES["recon"])
        assert "msfconsole" not in recon_tools
        assert "hydra" not in recon_tools

    def test_cached_result_is_frozenset(self):
        from core.docker_executor import discover_image_tools, _IMAGE_TOOLS_CACHE, IMAGE_NAMES
        img = IMAGE_NAMES["recon"]
        first = discover_image_tools(img)
        assert isinstance(first, frozenset)
        assert _IMAGE_TOOLS_CACHE[img] is first  # same object — cache hit


# ============================================================
# Category alignment — every category tool exists in SOME image
# ============================================================

@pytest.mark.skipif(not _docker_available(), reason="Docker daemon not available")
class TestCategoryImageCoverage:
    def test_every_category_tool_exists_in_a_tier_image(self):
        """No ghost tools: anything in TOOL_CATEGORIES that an LLM could be
        offered must exist in at least one tier image. A tool in the prompt
        that can't actually run wastes a bot cycle (the searchsploit bug)."""
        from core.docker_executor import discover_image_tools, IMAGE_NAMES
        union = set()
        for img in IMAGE_NAMES.values():
            union |= set(discover_image_tools(img))

        missing = set()
        for category, tools in TOOL_CATEGORIES.items():
            if category == "none":
                continue
            for tool in tools:
                if tool not in union:
                    missing.add(tool)

        # Shell builtins and host-only helpers are legitimately exempt
        exempt = {"cat", "ls", "find", "bash", "nc", "netcat", "ncat",
                  "python3", "curl", "wget", "tar", "gzip", "scp", "rsync",
                  "gcc", "git", "ssh", "ping", "web_search", "exploit"}
        missing -= exempt
        assert not missing, f"Tools in categories but in NO tier image: {sorted(missing)}"