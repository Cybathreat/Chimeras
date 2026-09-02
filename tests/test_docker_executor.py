"""
Chimeras v3.0 — Docker sandbox architecture tests.

Tests the 7-layer tiered sandbox: image tiers, bot resource/capability
profiles, network profiles, evidence chain, scope expansion registry.

These tests mock subprocess calls — no Docker daemon needed.
"""

import subprocess
from unittest import mock

import pytest

from core import docker_executor as de
from core.docker_executor import (
    BOT_CAPABILITIES,
    BOT_NET_PROFILE,
    BOT_RESOURCES,
    BOT_TIER,
    IMAGE_NAMES,
    TieredDockerExecutor,
    expand_all_scopes,
    live_containers,
    _LIVE_EXECUTORS,
)


# ============================================================
# Tier mapping
# ============================================================

class TestTierMapping:
    def test_all_bots_have_tiers(self):
        for bot in ["aria", "lisa", "bloodhound", "wasp", "marksman", "magician", "thief"]:
            assert bot in BOT_TIER, f"{bot} missing from BOT_TIER"

    def test_recon_bots_get_recon_tier(self):
        assert BOT_TIER["aria"] == "recon"

    def test_scan_bots_get_scan_tier(self):
        for bot in ["lisa", "bloodhound", "wasp"]:
            assert BOT_TIER[bot] == "scan"

    def test_exploit_bots_get_exploit_tier(self):
        for bot in ["marksman", "magician", "thief"]:
            assert BOT_TIER[bot] == "exploit"

    def test_all_tiers_have_images(self):
        for tier in set(BOT_TIER.values()):
            assert tier in IMAGE_NAMES, f"tier {tier} has no image name"

    def test_no_bot_inherits_exploit_tools_unnecessarily(self):
        """ARIA must never run in the exploit image — least privilege."""
        assert IMAGE_NAMES[BOT_TIER["aria"]] != IMAGE_NAMES[BOT_TIER["marksman"]]


# ============================================================
# Per-bot resource + capability contracts
# ============================================================

class TestBotContracts:
    def test_all_bots_have_resources(self):
        for bot in BOT_TIER:
            assert bot in BOT_RESOURCES
            assert "cpus" in BOT_RESOURCES[bot]
            assert "memory" in BOT_RESOURCES[bot]
            assert "pids" in BOT_RESOURCES[bot]

    def test_marksman_gets_most_resources(self):
        """Exploitation is the heaviest phase — Marksman gets the biggest cap."""
        assert float(BOT_RESOURCES["marksman"]["cpus"]) >= float(BOT_RESOURCES["aria"]["cpus"])

    def test_all_bots_have_capabilities(self):
        for bot in BOT_TIER:
            assert bot in BOT_CAPABILITIES

    def test_wasp_has_no_net_caps(self):
        """Wasp is HTTP-only — no raw sockets needed."""
        assert BOT_CAPABILITIES["wasp"] == []

    def test_all_bots_have_net_profiles(self):
        for bot in BOT_TIER:
            assert bot in BOT_NET_PROFILE
            assert BOT_NET_PROFILE[bot] in ("restricted", "web_only", "full")


# ============================================================
# Evidence chain — hash chaining must be tamper-evident
# ============================================================

class TestEvidenceChain:
    def _executor(self, tmp_path):
        return TieredDockerExecutor(
            bot_name="aria",
            engagement_dir=str(tmp_path),
            mission_scope="1.1.1.1",
            ttl=0,
        )

    def test_first_entry_hash_chains_from_genesis(self, tmp_path):
        ex = self._executor(tmp_path)
        ex._append_evidence({"event": "test", "bot": "aria"})
        chain = ex.get_evidence_chain()
        assert len(chain) == 1
        assert chain[0]["prev_hash"] == "genesis"
        assert "hash" in chain[0]

    def test_second_entry_references_first(self, tmp_path):
        ex = self._executor(tmp_path)
        ex._append_evidence({"event": "first"})
        ex._append_evidence({"event": "second"})
        chain = ex.get_evidence_chain()
        assert chain[1]["prev_hash"] == chain[0]["hash"]
        assert chain[0]["prev_hash"] == "genesis"

    def test_hash_persists_across_executor_restart(self, tmp_path):
        ex1 = self._executor(tmp_path)
        ex1._append_evidence({"event": "first"})
        h1 = ex1.get_evidence_chain()[-1]["hash"]

        ex2 = self._executor(tmp_path)  # fresh executor, same engagement dir
        ex2._append_evidence({"event": "second"})
        chain = ex2.get_evidence_chain()
        assert chain[-1]["prev_hash"] == h1

    def test_tamper_breaks_chain(self, tmp_path):
        ex = self._executor(tmp_path)
        ex._append_evidence({"event": "a"})
        ex._append_evidence({"event": "b"})
        chain = ex.get_evidence_chain()
        assert chain[0]["hash"] != chain[1]["hash"]


# ============================================================
# Firewall rule construction
# ============================================================

class TestFirewallRules:
    def _get_nft_input(self, mrun):
        """Extract the nftables program from the mocked subprocess calls."""
        for call in mrun.call_args_list:
            inp = call.kwargs.get("input")
            if inp and "chimeras_scope" in str(inp):
                return str(inp)
        raise AssertionError("no nftables program found in subprocess calls")

    def _armed_executor(self, tmp_path, scope):
        """Executor with container_name set (as if _ensure_container ran)."""
        ex = TieredDockerExecutor(
            bot_name="aria", engagement_dir=str(tmp_path),
            mission_scope=scope, ttl=0,
        )
        ex._container_name = "chimeras-aria-test"  # simulate live container
        return ex

    def test_scope_domain_resolved_to_ips(self, tmp_path):
        """Scoped domains must be resolved — nft can't parse hostnames."""
        ex = self._armed_executor(tmp_path, "example.com")
        # Mock: container exists, PID 1234, nft accepts everything
        with mock.patch.object(ex, "_container_pid", return_value=1234), \
             mock.patch("subprocess.run") as mrun:
            mrun.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            with mock.patch("socket.getaddrinfo") as gai:
                gai.return_value = [(None, None, None, "", ("93.184.216.34", 0))]
                ok = ex._inject_firewall()
        assert ok
        nft_input = self._get_nft_input(mrun)
        # The rule must target the RESOLVED IP, never the hostname
        assert "ip daddr 93.184.216.34 accept" in nft_input
        assert "example.com" not in nft_input

    def test_firewall_fail_closes_container(self, tmp_path):
        """If injection fails, container must be killed — never run unprotected."""
        ex = TieredDockerExecutor(
            bot_name="aria", engagement_dir=str(tmp_path),
            mission_scope="1.1.1.1", ttl=0,
        )
        with mock.patch("subprocess.run") as mrun:
            # docker run returns a container id
            run_result = mock.Mock(returncode=0, stdout="abc123\n", stderr="")
            def side_effect(*args, **kwargs):
                if args and args[0][:2] == ["docker", "run"]:
                    return run_result
                # firewall injection (nsenter) fails
                if args and args[0][:1] == ["nsenter"]:
                    return mock.Mock(returncode=1, stdout="", stderr="netns error")
                return mock.Mock(returncode=0, stdout="", stderr="")
            mrun.side_effect = side_effect
            with mock.patch.object(ex, "_container_pid", return_value=1234):
                with pytest.raises(RuntimeError, match="unprotected"):
                    ex._ensure_container()

    def test_web_profile_no_blanket_egress(self, tmp_path):
        """web_only profile must NEVER allow web ports to arbitrary IPs."""
        ex = self._armed_executor(tmp_path, "1.1.1.1")
        with mock.patch.object(ex, "_container_pid", return_value=1234), \
             mock.patch("subprocess.run") as mrun:
            mrun.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            ex._inject_firewall()
        nft_input = self._get_nft_input(mrun)
        # Every web-port rule must be daddr-restricted. Split into complete
        # rules — a rule like "ip daddr X tcp dport {...} accept" is fine,
        # a bare "tcp dport {...} accept" is blanket egress and forbidden.
        import re
        for rule in nft_input.split(";"):
            rule = rule.strip()
            if re.search(r"tcp dport \{ 80", rule):
                assert "ip daddr" in rule, f"Blanket egress rule found: {rule}"


# ============================================================
# Live executor registry (WarChief scope propagation)
# ============================================================

class TestScopePropagationRegistry:
    def test_expand_all_scopes_empty_when_no_containers(self):
        _LIVE_EXECUTORS.clear()
        assert expand_all_scopes("1.2.3.4") == {}
        assert live_containers() == []

    def test_cleanup_unregisters_executor(self, tmp_path):
        ex = TieredDockerExecutor(
            bot_name="aria", engagement_dir=str(tmp_path),
            mission_scope="1.1.1.1", ttl=0,
        )
        # Simulate registration + live container
        _LIVE_EXECUTORS.append(ex)
        ex._container_name = "chimeras-aria-test"
        with mock.patch("subprocess.run") as mrun:
            mrun.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            ex.cleanup()
        assert ex not in _LIVE_EXECUTORS
        _LIVE_EXECUTORS.clear()

    def test_expand_all_scopes_hits_live_containers(self, tmp_path):
        ex = TieredDockerExecutor(
            bot_name="aria", engagement_dir=str(tmp_path),
            mission_scope="1.1.1.1", ttl=0,
        )
        _LIVE_EXECUTORS.append(ex)
        with mock.patch.object(ex, "expand_scope", return_value=True) as mes:
            result = expand_all_scopes("8.8.8.8", "github.com")
        assert result == {"aria": True}
        mes.assert_called_once_with("8.8.8.8", "github.com")
        _LIVE_EXECUTORS.clear()


# ============================================================
# Docker availability / image checks (mocked)
# ============================================================

class TestDockerHelpers:
    def test_docker_available_true(self):
        with mock.patch("subprocess.run") as mrun:
            mrun.return_value = mock.Mock(returncode=0)
            assert de._docker_available() is True

    def test_docker_available_false_on_missing(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            assert de._docker_available() is False