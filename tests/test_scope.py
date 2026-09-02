"""
Tests for core/scope.py — TargetValidator and ScopeEnforcer.

Covers:
- TargetValidator: IP in scope, hostname in scope, out-of-scope blocking,
  CIDR matching, fail-closed when no scope
- ScopeEnforcer: category check, shell metachar detection, destructive
  command blocklist, DoS flag detection
"""
import pytest

from core.scope import (
    TargetValidator,
    ScopeEnforcer,
    check_shell_injection,
    check_destructive_command,
    BOT_CATEGORIES,
    TOOL_CATEGORIES,
    SHELL_CAPABLE_CATEGORIES,
    ScopeViolation,
)


# ─── TargetValidator ───


class TestTargetValidatorIPScope:
    """Tests for IP-based scope validation."""

    def test_ip_in_scope_single(self):
        v = TargetValidator("10.10.10.5")
        ok, _ = v.validate_command("nmap 10.10.10.5", "lisa")
        assert ok

    def test_ip_in_scope_cidr(self):
        v = TargetValidator("10.10.10.0/24")
        ok, _ = v.validate_command("nmap 10.10.10.100", "lisa")
        assert ok

    def test_ip_out_of_scope_cidr(self):
        v = TargetValidator("10.10.10.0/24")
        ok, reason = v.validate_command("nmap 192.168.99.1", "lisa")
        assert not ok
        assert "OUT OF SCOPE" in reason

    def test_ip_out_of_scope_single(self):
        v = TargetValidator("10.10.10.5")
        ok, reason = v.validate_command("nmap 10.10.10.6", "lisa")
        assert not ok

    def test_cidr_boundary_inclusive(self):
        """First and last IPs in a /24 should be in scope."""
        v = TargetValidator("10.10.10.0/24")
        ok, _ = v.validate_command("nmap 10.10.10.0", "lisa")
        assert ok
        ok, _ = v.validate_command("nmap 10.10.10.255", "lisa")
        assert ok

    def test_ip_with_cidr_suffix_in_command(self):
        """nmap 10.10.10.0/24 should validate against scope 10.10.10.0/24."""
        v = TargetValidator("10.10.10.0/24")
        ok, _ = v.validate_command("nmap 10.10.10.0/24", "lisa")
        assert ok

    def test_multiple_scope_entries(self):
        """Comma-separated scope should allow any listed IP."""
        v = TargetValidator("10.10.10.5, 192.168.1.1")
        ok, _ = v.validate_command("nmap 10.10.10.5", "lisa")
        assert ok
        ok, _ = v.validate_command("nmap 192.168.1.1", "lisa")
        assert ok
        ok, _ = v.validate_command("nmap 172.16.0.1", "lisa")
        assert not ok


class TestTargetValidatorHostnameScope:
    """Tests for hostname-based scope validation."""

    def test_hostname_in_scope_direct(self):
        v = TargetValidator("example.com")
        ok, _ = v.validate_command("dig example.com", "aria")
        assert ok

    def test_hostname_out_of_scope(self):
        v = TargetValidator("example.com")
        ok, reason = v.validate_command("dig evil.com", "aria")
        assert not ok
        assert "OUT OF SCOPE" in reason

    def test_subdomain_in_scope(self):
        """sub.example.com should be in scope when scope is example.com."""
        v = TargetValidator("example.com")
        ok, _ = v.validate_command("dig sub.example.com", "aria")
        assert ok


class TestTargetValidatorFailClosed:
    """Tests for fail-closed behaviour when no scope is defined."""

    def test_no_scope_blocks(self):
        """Empty scope string should block all targeting (fail-closed)."""
        v = TargetValidator("")
        ok, reason = v.validate_command("nmap 10.10.10.5", "lisa")
        assert not ok
        assert "NO SCOPE" in reason.upper()

    def test_none_scope_blocks(self):
        v = TargetValidator(None)
        ok, reason = v.validate_command("nmap 10.10.10.5", "lisa")
        assert not ok

    def test_empty_scope_hostname_blocks(self):
        v = TargetValidator("")
        ok, _ = v.validate_command("dig example.com", "aria")
        assert not ok


class TestTargetValidatorNoTargets:
    """Commands with no extractable targets should pass (vacuous truth)."""

    def test_no_target_passes(self):
        v = TargetValidator("10.10.10.0/24")
        ok, _ = v.validate_command("whoami", "lisa")
        assert ok

    def test_flag_only_command_passes(self):
        v = TargetValidator("10.10.10.0/24")
        ok, _ = v.validate_command("nmap -h", "lisa")
        assert ok


class TestTargetValidatorNmapValueFlags:
    """nmap --script, --script-args, etc. should not have their values
    mistaken for hostnames."""

    def test_script_arg_not_treated_as_target(self):
        v = TargetValidator("10.10.10.5")
        # ssl-cert is an nmap script name, not a target
        ok, _ = v.validate_command("nmap --script ssl-cert 10.10.10.5", "lisa")
        assert ok

    def test_script_args_not_treated_as_target(self):
        v = TargetValidator("10.10.10.5")
        ok, _ = v.validate_command(
            "nmap --script-args ssl-cert.timeout=30 10.10.10.5", "lisa"
        )
        assert ok


# ─── ScopeEnforcer ───


class TestScopeEnforcerCategory:
    """Tests for tool-category enforcement."""

    def test_allowed_tool_passes(self):
        """Lisa using nmap (active_scan category) should pass category check."""
        ok, _ = ScopeEnforcer.check("lisa", "nmap 10.10.10.5",
                                    mission_scope="10.10.10.0/24")
        assert ok

    def test_disallowed_tool_blocked(self):
        """ARIA using nmap (active_scan) should be blocked — ARIA is passive_recon."""
        ok, reason = ScopeEnforcer.check("aria", "nmap 10.10.10.5",
                                         mission_scope="10.10.10.0/24")
        assert not ok
        assert "SCOPE VIOLATION" in reason or "cannot use" in reason

    def test_warchief_no_tools(self):
        """WarChief has category 'none' — no tools allowed."""
        ok, reason = ScopeEnforcer.check("warchief", "nmap 10.10.10.5",
                                         mission_scope="10.10.10.0/24")
        assert not ok

    def test_bookkeeper_no_tools(self):
        ok, reason = ScopeEnforcer.check("bookkeeper", "whoami",
                                         mission_scope="10.10.10.0/24")
        assert not ok

    def test_tool_path_resolved(self):
        """/usr/bin/nmap should be treated as nmap."""
        ok, _ = ScopeEnforcer.check("lisa", "/usr/bin/nmap 10.10.10.5",
                                    mission_scope="10.10.10.0/24")
        assert ok

    def test_empty_command_blocked(self):
        ok, reason = ScopeEnforcer.check("lisa", "",
                                         mission_scope="10.10.10.0/24")
        assert not ok

    def test_get_bot_category(self):
        assert ScopeEnforcer.get_bot_category("aria") == "passive_recon"
        assert ScopeEnforcer.get_bot_category("lisa") == "active_scan"
        assert ScopeEnforcer.get_bot_category("warchief") == "none"

    def test_get_allowed_tools(self):
        tools = ScopeEnforcer.get_allowed_tools("lisa")
        assert "nmap" in tools
        assert "gobuster" in tools

    def test_unknown_bot_defaults_to_none(self):
        ok, reason = ScopeEnforcer.check("unknown_bot", "nmap 10.10.10.5",
                                         mission_scope="10.10.10.0/24")
        assert not ok


class TestScopeEnforcerShellInjection:
    """Tests for shell metacharacter detection."""

    def test_semicolon_blocked_for_passive_recon(self):
        """ARIA (passive_recon) using semicolon should be blocked."""
        ok, reason = check_shell_injection("dig example.com; nc attacker.com", "aria")
        assert not ok
        assert "SHELL INJECTION" in reason or "metachar" in reason.lower()

    def test_pipe_blocked_for_passive_recon(self):
        ok, reason = check_shell_injection("dig example.com | grep A", "aria")
        assert not ok

    def test_backtick_blocked_for_active_scan(self):
        """Lisa (active_scan) is not in SHELL_CAPABLE_CATEGORIES."""
        ok, reason = check_shell_injection("nmap `whoami`", "lisa")
        assert not ok

    def test_pipe_allowed_for_marksman(self):
        """Marksman is shell-capable — pipe should be allowed."""
        ok, _ = check_shell_injection("echo test | grep t", "marksman")
        assert ok

    def test_semicolon_allowed_for_privesc(self):
        ok, _ = check_shell_injection("cat /etc/shadow; ls", "magician")
        assert ok

    def test_dollar_paren_allowed_for_exfiltration(self):
        ok, _ = check_shell_injection("echo $(whoami)", "thief")
        assert ok

    def test_no_metachar_passes(self):
        ok, _ = check_shell_injection("nmap -sV 10.10.10.5", "lisa")
        assert ok

    def test_redirect_blocked_for_passive_recon(self):
        ok, _ = check_shell_injection("dig example.com > /tmp/out", "aria")
        assert not ok

    def test_redirect_allowed_for_web_exploit(self):
        """web_exploit is shell-capable."""
        ok, _ = check_shell_injection("curl http://test > /tmp/out", "wasp")
        assert ok


class TestDestructiveCommandBlocklist:
    """Tests for the destructive command blocklist."""

    def test_rm_rf_blocked(self):
        ok, reason = check_destructive_command("rm -rf /")
        assert not ok
        assert "DESTRUCTIVE" in reason

    def test_rm_fr_blocked(self):
        ok, reason = check_destructive_command("rm -fr /tmp/evidence")
        assert not ok

    def test_mkfs_blocked(self):
        ok, reason = check_destructive_command("mkfs.ext4 /dev/sda1")
        assert not ok

    def test_dd_to_device_blocked(self):
        ok, reason = check_destructive_command("dd if=/dev/zero of=/dev/sda bs=1M")
        assert not ok

    def test_fork_bomb_blocked(self):
        ok, reason = check_destructive_command(":(){ :|:& };:")
        assert not ok

    def test_sql_drop_blocked(self):
        ok, reason = check_destructive_command("echo 'DROP TABLE users' | mysql -u root")
        assert not ok

    def test_shutdown_blocked(self):
        ok, reason = check_destructive_command("shutdown -h now")
        assert not ok

    def test_safe_command_passes(self):
        ok, _ = check_destructive_command("nmap -sV 10.10.10.5")
        assert ok

    def test_safe_ls_passes(self):
        ok, _ = check_destructive_command("ls -la /tmp")
        assert ok


class TestDoSFlagDetection:
    """Tests for DoS-capable flag detection."""

    def test_hping_flood_blocked_with_roe(self):
        ok, reason = check_destructive_command(
            "hping3 --flood 10.10.10.5", roe="no dos"
        )
        assert not ok
        assert "DOS" in reason.upper() or "flood" in reason.lower()

    def test_hping_flood_blocked_no_roe(self):
        """No RoE supplied — fail toward safer assumption (blocked)."""
        ok, reason = check_destructive_command(
            "hping3 --flood 10.10.10.5", roe=None
        )
        assert not ok

    def test_nmap_high_rate_blocked(self):
        """max-rate >= 100000 should be flagged."""
        ok, reason = check_destructive_command(
            "nmap --max-rate 100000 10.10.10.5", roe="no dos"
        )
        assert not ok

    def test_nmap_normal_rate_passes(self):
        ok, _ = check_destructive_command(
            "nmap --max-rate 100 10.10.10.5", roe="no dos"
        )
        assert ok

    def test_slowloris_blocked(self):
        ok, reason = check_destructive_command("slowloris example.com", roe="no dos")
        assert not ok

    def test_dos_allowed_without_roe_restriction(self):
        """When RoE explicitly permits (doesn't mention dos), flood flags
        are downgraded to a warning but still pass."""
        ok, reason = check_destructive_command(
            "hping3 --flood 10.10.10.5", roe="authorized full scope"
        )
        assert ok
        assert "WARNING" in reason


class TestScopeEnforcerIntegration:
    """Integration tests combining multiple checks."""

    def test_destructive_overrides_category(self):
        """A destructive command should be blocked even for a shell-capable bot."""
        ok, reason = ScopeEnforcer.check(
            "marksman", "rm -rf /", mission_scope="10.10.10.0/24"
        )
        assert not ok
        assert "DESTRUCTIVE" in reason

    def test_out_of_scope_target_blocks(self):
        ok, reason = ScopeEnforcer.check(
            "lisa", "nmap 172.16.99.1", mission_scope="10.10.10.0/24"
        )
        assert not ok
        assert "SCOPE" in reason.upper()

    def test_full_valid_command_passes(self):
        ok, _ = ScopeEnforcer.check(
            "lisa", "nmap -sV -p 80,443 10.10.10.5",
            mission_scope="10.10.10.0/24"
        )
        assert ok

    def test_shell_injection_blocks_before_category(self):
        """Shell injection check runs before category check for non-shell bots."""
        ok, reason = ScopeEnforcer.check(
            "aria", "dig example.com; cat /etc/passwd",
            mission_scope="example.com"
        )
        assert not ok
        assert "SHELL INJECTION" in reason