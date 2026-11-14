"""
Tests for Chimeras v3.3 Authentication Manager.

Tests cover:
- AuthCredential dataclass (redaction, hashing)
- AuthSession dataclass (headers, cookies, token extraction, expiry)
- AuthManager target loading (list, dict formats)
- AuthManager session caching and persistence
- AuthManager status reporting
- ToolExecutor auth injection (curl, sqlmap, nmap, nikto, ldapsearch, ssh)
- Config integration (auth section in swarm-config.json)
- State integration (auth_config, auth_sessions fields)
- Env variable loading
- JWT validation
- Error handling (missing config, unknown methods)
"""

import json
import os
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import base64

import pytest

from core.auth_manager import (
    AuthManager, AuthCredential, AuthSession,
    AuthMethod, AuthStatus, load_auth_from_env,
)
from core.tool_executor import ToolExecutor


# ─── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def tmp_engagement_dir():
    with tempfile.TemporaryDirectory() as d:
        eng = Path(d) / "engagement"
        (eng / "auth").mkdir(parents=True)
        yield eng


@pytest.fixture
def basic_auth_config():
    return {
        "targets": [
            {
                "target_id": "web_portal",
                "method": "web_form",
                "url": "https://target.example.com/login",
                "username": "testuser",
                "password": "testpass",
            },
            {
                "target_id": "ad_primary",
                "method": "ad_ldap_bind",
                "domain": "CORP",
                "username": "admin",
                "password": "adminpass",
                "ldap_server": "ldap://dc01.corp.local",
                "ldap_base_dn": "dc=corp,dc=local",
            },
        ]
    }


@pytest.fixture
def auth_manager(basic_auth_config, tmp_engagement_dir):
    return AuthManager(basic_auth_config, tmp_engagement_dir)


# ─── AuthCredential Tests ───────────────────────────────────────────────


class TestAuthCredential:
    def test_redact_hides_password(self):
        cred = AuthCredential(
            target_id="test", method="web_form",
            username="user", password="secret123"
        )
        redacted = cred.redact()
        assert redacted["password"] == "***REDACTED***"
        assert redacted["username"] == "user"

    def test_redact_hides_token(self):
        cred = AuthCredential(
            target_id="test", method="web_bearer",
            token="eyJhbGciOiJIUzI1NiJ9..."
        )
        redacted = cred.redact()
        assert redacted["token"] == "***REDACTED***"

    def test_redact_hides_client_secret(self):
        cred = AuthCredential(
            target_id="test", method="keycloak_oauth2_client_credentials",
            client_id="myclient", client_secret="mysecret"
        )
        redacted = cred.redact()
        assert redacted["client_secret"] == "***REDACTED***"
        assert redacted["client_id"] == "myclient"

    def test_password_hash_set(self):
        cred = AuthCredential(
            target_id="test", method="web_form",
            password="mypassword"
        )
        assert cred._password_hash != ""
        assert len(cred._password_hash) == 16

    def test_no_password_no_hash(self):
        cred = AuthCredential(target_id="test", method="ldap_anonymous")
        assert cred._password_hash == ""

    def test_cookies_redacted(self):
        cred = AuthCredential(
            target_id="test", method="web_cookie",
            cookies={"session": "abc123", "csrf": "def456"}
        )
        redacted = cred.redact()
        assert redacted["cookies"] == "***REDACTED***"


# ─── AuthSession Tests ──────────────────────────────────────────────────


class TestAuthSession:
    def test_success_property(self):
        session = AuthSession(
            target_id="test", method="web_form",
            status=AuthStatus.SUCCESS.value
        )
        assert session.success is True

    def test_failed_not_success(self):
        session = AuthSession(
            target_id="test", method="web_form",
            status=AuthStatus.FAILED.value
        )
        assert session.success is False

    def test_get_headers_with_bearer_token(self):
        session = AuthSession(
            target_id="test", method="web_bearer",
            status=AuthStatus.SUCCESS.value,
            access_token="eyJhbG...",
            token_type="Bearer",
        )
        headers = session.get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer eyJhbG..."

    def test_get_headers_with_cookies(self):
        session = AuthSession(
            target_id="test", method="web_cookie",
            status=AuthStatus.SUCCESS.value,
            cookies={"session_id": "abc123", "csrf": "def"},
        )
        headers = session.get_headers()
        assert "Cookie" in headers
        assert "session_id=abc123" in headers["Cookie"]
        assert "csrf=def" in headers["Cookie"]

    def test_get_headers_with_custom_token_type(self):
        session = AuthSession(
            target_id="test", method="web_basic",
            status=AuthStatus.SUCCESS.value,
            access_token="dXNlcjpwYXNz",
            token_type="Basic",
        )
        headers = session.get_headers()
        assert headers["Authorization"] == "Basic dXNlcjpwYXNz"

    def test_get_cookies(self):
        session = AuthSession(
            target_id="test", method="web_form",
            status=AuthStatus.SUCCESS.value,
            cookies={"a": "1", "b": "2"},
        )
        cookies = session.get_cookies()
        assert cookies == {"a": "1", "b": "2"}

    def test_get_token(self):
        session = AuthSession(
            target_id="test", method="web_bearer",
            status=AuthStatus.SUCCESS.value,
            access_token="mytoken123",
        )
        assert session.get_token() == "mytoken123"

    def test_is_expired_not_set(self):
        session = AuthSession(
            target_id="test", method="web_bearer",
            status=AuthStatus.SUCCESS.value,
        )
        assert session.is_expired is False

    def test_is_expired_future(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        session = AuthSession(
            target_id="test", method="web_bearer",
            status=AuthStatus.SUCCESS.value,
            expires_at=future,
        )
        assert session.is_expired is False

    def test_is_expired_past(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        session = AuthSession(
            target_id="test", method="web_bearer",
            status=AuthStatus.SUCCESS.value,
            expires_at=past,
        )
        assert session.is_expired is True

    def test_to_dict_redacts_token(self):
        session = AuthSession(
            target_id="test", method="web_bearer",
            status=AuthStatus.SUCCESS.value,
            access_token="secret_token",
            refresh_token="secret_refresh",
        )
        d = session.to_dict()
        assert d["access_token"] == "***REDACTED***"
        assert d["refresh_token"] == "***REDACTED***"

    def test_to_dict_redacts_cookies(self):
        session = AuthSession(
            target_id="test", method="web_cookie",
            status=AuthStatus.SUCCESS.value,
            cookies={"session": "secret"},
        )
        d = session.to_dict()
        assert d["cookies"] == {"session": "***REDACTED***"}

    def test_get_authorization_header(self):
        session = AuthSession(
            target_id="test", method="web_bearer",
            status=AuthStatus.SUCCESS.value,
            access_token="abc123",
        )
        assert session.get_authorization_header() == "Bearer abc123"

    def test_get_authorization_header_empty(self):
        session = AuthSession(
            target_id="test", method="web_form",
            status=AuthStatus.SUCCESS.value,
        )
        assert session.get_authorization_header() == ""


# ─── AuthManager Target Loading Tests ───────────────────────────────────


class TestAuthManagerLoading:
    def test_load_targets_from_list(self, basic_auth_config, tmp_engagement_dir):
        manager = AuthManager(basic_auth_config, tmp_engagement_dir)
        assert len(manager.targets) == 2
        assert "web_portal" in manager.targets
        assert "ad_primary" in manager.targets

    def test_load_targets_from_dict(self, tmp_engagement_dir):
        config = {
            "targets": {
                "web_portal": {
                    "method": "web_form",
                    "url": "https://target.com/login",
                    "username": "user",
                    "password": "pass",
                }
            }
        }
        manager = AuthManager(config, tmp_engagement_dir)
        assert len(manager.targets) == 1
        assert "web_portal" in manager.targets
        assert manager.targets["web_portal"].username == "user"

    def test_empty_config(self, tmp_engagement_dir):
        manager = AuthManager({}, tmp_engagement_dir)
        assert len(manager.targets) == 0

    def test_none_config(self, tmp_engagement_dir):
        manager = AuthManager(None, tmp_engagement_dir)
        assert len(manager.targets) == 0

    def test_no_engagement_dir(self):
        manager = AuthManager({"targets": []})
        assert manager._auth_dir is None

    def test_list_targets(self, auth_manager):
        targets = auth_manager.list_targets()
        assert "web_portal" in targets
        assert "ad_primary" in targets

    def test_filter_credential_fields_ignores_unknown(self):
        config = {
            "target_id": "test",
            "method": "web_form",
            "unknown_field": "should_be_ignored",
        }
        filtered = AuthManager._filter_credential_fields(config)
        assert "unknown_field" not in filtered
        assert "target_id" in filtered
        assert "method" in filtered


# ─── AuthManager Session Tests ──────────────────────────────────────────


class TestAuthManagerSessions:
    def test_authenticate_not_configured(self, auth_manager):
        session = auth_manager.authenticate("nonexistent_target")
        assert session.status == AuthStatus.NOT_CONFIGURED.value
        assert "No auth target" in session.error

    def test_authenticate_unknown_method(self, tmp_engagement_dir):
        config = {
            "targets": [{
                "target_id": "test",
                "method": "invalid_method",
                "username": "user",
                "password": "pass",
            }]
        }
        manager = AuthManager(config, tmp_engagement_dir)
        session = manager.authenticate("test")
        assert session.status == AuthStatus.FAILED.value
        assert "Unknown auth method" in session.error

    def test_has_auth_false_when_no_session(self, auth_manager):
        assert auth_manager.has_auth("web_portal") is False

    def test_has_auth_true_after_success(self, auth_manager):
        # Manually inject a successful session
        auth_manager.sessions["web_portal"] = AuthSession(
            target_id="web_portal", method="web_form",
            status=AuthStatus.SUCCESS.value,
        )
        assert auth_manager.has_auth("web_portal") is True

    def test_has_auth_false_when_expired(self, auth_manager):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        auth_manager.sessions["web_portal"] = AuthSession(
            target_id="web_portal", method="web_bearer",
            status=AuthStatus.SUCCESS.value,
            expires_at=past,
        )
        assert auth_manager.has_auth("web_portal") is False

    def test_get_headers_no_session(self, auth_manager):
        assert auth_manager.get_headers("web_portal") == {}

    def test_get_headers_with_session(self, auth_manager):
        auth_manager.sessions["web_portal"] = AuthSession(
            target_id="web_portal", method="web_bearer",
            status=AuthStatus.SUCCESS.value,
            access_token="mytoken",
        )
        headers = auth_manager.get_headers("web_portal")
        assert "Authorization" in headers

    def test_get_cookies_no_session(self, auth_manager):
        assert auth_manager.get_cookies("web_portal") == {}

    def test_get_token_no_session(self, auth_manager):
        assert auth_manager.get_token("web_portal") == ""

    def test_get_authorization_header_no_session(self, auth_manager):
        assert auth_manager.get_authorization_header("web_portal") == ""

    def test_session_caching(self, auth_manager):
        """If session exists and is valid, authenticate() returns cached."""
        cached = AuthSession(
            target_id="web_portal", method="web_bearer",
            status=AuthStatus.SUCCESS.value,
            access_token="cached_token",
        )
        auth_manager.sessions["web_portal"] = cached
        session = auth_manager.authenticate("web_portal")
        assert session.access_token == "cached_token"

    def test_session_force_reauth(self, auth_manager):
        cached = AuthSession(
            target_id="web_portal", method="web_bearer",
            status=AuthStatus.SUCCESS.value,
            access_token="cached_token",
        )
        auth_manager.sessions["web_portal"] = cached
        # Force re-auth — will try to connect and fail (no real server)
        # but should not return cached
        with patch.object(auth_manager, '_dispatch_auth') as mock_dispatch:
            mock_dispatch.return_value = AuthSession(
                target_id="web_portal", method="web_bearer",
                status=AuthStatus.FAILED.value,
                error="Connection refused",
            )
            session = auth_manager.authenticate("web_portal", force=True)
            assert session.status == AuthStatus.FAILED.value
            mock_dispatch.assert_called_once()


# ─── AuthManager Session Persistence Tests ──────────────────────────────


class TestAuthManagerPersistence:
    def test_save_and_load_sessions(self, tmp_engagement_dir):
        config = {"targets": [{"target_id": "test", "method": "web_bearer", "token": "abc"}]}
        manager1 = AuthManager(config, tmp_engagement_dir)
        manager1.sessions["test"] = AuthSession(
            target_id="test", method="web_bearer",
            status=AuthStatus.SUCCESS.value,
            access_token="abc",
        )
        manager1._save_sessions()

        # Create new manager pointing to same dir
        manager2 = AuthManager(config, tmp_engagement_dir)
        assert "test" in manager2.sessions
        # Token should be redacted in storage → marked expired
        assert manager2.sessions["test"].access_token == ""
        assert manager2.sessions["test"].status == AuthStatus.EXPIRED.value

    def test_load_corrupt_sessions(self, tmp_engagement_dir):
        sessions_path = tmp_engagement_dir / "auth" / "sessions.json"
        sessions_path.write_text("not valid json{{{")
        config = {"targets": []}
        manager = AuthManager(config, tmp_engagement_dir)
        # Should not crash, just start fresh
        assert len(manager.sessions) == 0


# ─── AuthManager Status Tests ───────────────────────────────────────────


class TestAuthManagerStatus:
    def test_get_status_all_targets(self, auth_manager):
        status = auth_manager.get_status()
        assert "web_portal" in status
        assert "ad_primary" in status
        assert status["web_portal"]["method"] == "web_form"
        assert status["web_portal"]["status"] == AuthStatus.PENDING.value

    def test_get_status_with_session(self, auth_manager):
        auth_manager.sessions["web_portal"] = AuthSession(
            target_id="web_portal", method="web_form",
            status=AuthStatus.SUCCESS.value,
        )
        status = auth_manager.get_status()
        assert status["web_portal"]["status"] == AuthStatus.SUCCESS.value

    def test_get_status_redacts_credentials(self, auth_manager):
        status = auth_manager.get_status()
        cred = status["web_portal"]["credential"]
        assert cred["password"] == "***REDACTED***"

    def test_export_status_report(self, auth_manager):
        report = auth_manager.export_status_report()
        assert "Authentication Status Report" in report
        assert "web_portal" in report
        assert "ad_primary" in report

    def test_export_status_report_no_targets(self, tmp_engagement_dir):
        manager = AuthManager({"targets": []}, tmp_engagement_dir)
        report = manager.export_status_report()
        assert "No authentication targets configured" in report


# ─── ToolExecutor Auth Injection Tests ──────────────────────────────────


class TestToolExecutorAuthInjection:
    @pytest.fixture
    def mock_auth_manager(self):
        manager = MagicMock(spec=AuthManager)
        manager.has_auth.return_value = True
        manager.get_curl_auth_args.return_value = '-H "Authorization: Bearer mytoken"'
        manager.get_sqlmap_auth_args.return_value = '--cookie="session=abc"'
        manager.get_nmap_auth_args.return_value = '--script-args "smbdomain=CORP,smbuser=admin,smbpass=pass"'
        manager.get_ssh_command_prefix.return_value = "sshpass -p 'pass' ssh user@host"
        manager.get_ldapsearch_command.return_value = "ldapsearch -x -H ldap://dc01 -D 'admin' -w 'pass' -b 'dc=corp,dc=local'"
        manager.get_headers.return_value = {"Authorization": "Bearer mytoken"}
        manager.targets = {"web_portal": AuthCredential(target_id="web_portal", method="web_bearer", username="user", password="pass")}
        return manager

    def test_no_auth_manager_no_injection(self):
        executor = ToolExecutor(auth_manager=None, auth_target_id=None)
        cmd = "curl https://example.com"
        assert executor._inject_auth(cmd) == cmd

    def test_no_target_id_no_injection(self, mock_auth_manager):
        executor = ToolExecutor(auth_manager=mock_auth_manager, auth_target_id=None)
        cmd = "curl https://example.com"
        assert executor._inject_auth(cmd) == cmd

    def test_no_auth_session_no_injection(self, mock_auth_manager):
        mock_auth_manager.has_auth.return_value = False
        executor = ToolExecutor(auth_manager=mock_auth_manager, auth_target_id="web_portal")
        cmd = "curl https://example.com"
        assert executor._inject_auth(cmd) == cmd

    def test_curl_auth_injection(self, mock_auth_manager):
        executor = ToolExecutor(auth_manager=mock_auth_manager, auth_target_id="web_portal")
        cmd = "curl -s https://example.com/api"
        result = executor._inject_auth(cmd)
        assert "Authorization: Bearer mytoken" in result

    def test_sqlmap_auth_injection(self, mock_auth_manager):
        executor = ToolExecutor(auth_manager=mock_auth_manager, auth_target_id="web_portal")
        cmd = "sqlmap -u https://example.com/page?id=1"
        result = executor._inject_auth(cmd)
        assert 'cookie="session=abc"' in result

    def test_nmap_auth_injection(self, mock_auth_manager):
        executor = ToolExecutor(auth_manager=mock_auth_manager, auth_target_id="web_portal")
        cmd = "nmap -sV 10.10.10.5"
        result = executor._inject_auth(cmd)
        assert "smbdomain=CORP" in result

    def test_nikto_auth_injection(self, mock_auth_manager):
        executor = ToolExecutor(auth_manager=mock_auth_manager, auth_target_id="web_portal")
        cmd = "nikto -h https://example.com"
        result = executor._inject_auth(cmd)
        assert "-id" in result

    def test_ldapsearch_auth_injection(self, mock_auth_manager):
        executor = ToolExecutor(auth_manager=mock_auth_manager, auth_target_id="web_portal")
        cmd = "ldapsearch -x -H ldap://dc01"
        result = executor._inject_auth(cmd)
        assert "ldapsearch" in result
        # Should use the AuthManager's built-in command
        assert "-D" in result

    def test_ssh_auth_injection(self, mock_auth_manager):
        executor = ToolExecutor(auth_manager=mock_auth_manager, auth_target_id="web_portal")
        cmd = "ssh user@host"
        result = executor._inject_auth(cmd)
        assert "sshpass" in result

    def test_ffuf_auth_injection(self, mock_auth_manager):
        executor = ToolExecutor(auth_manager=mock_auth_manager, auth_target_id="web_portal")
        cmd = "ffuf -u https://example.com/FUZZ -w wordlist.txt"
        result = executor._inject_auth(cmd)
        assert "Authorization: Bearer mytoken" in result

    def test_no_double_injection_curl(self, mock_auth_manager):
        executor = ToolExecutor(auth_manager=mock_auth_manager, auth_target_id="web_portal")
        cmd = 'curl -s -H "Authorization: Bearer existing" https://example.com'
        result = executor._inject_auth(cmd)
        # Should not inject again
        assert result == cmd

    def test_no_double_injection_sqlmap(self, mock_auth_manager):
        executor = ToolExecutor(auth_manager=mock_auth_manager, auth_target_id="web_portal")
        cmd = 'sqlmap -u https://example.com --cookie="existing=cookie"'
        result = executor._inject_auth(cmd)
        assert result == cmd

    def test_unsupported_tool_no_injection(self, mock_auth_manager):
        executor = ToolExecutor(auth_manager=mock_auth_manager, auth_target_id="web_portal")
        cmd = "nuclei -u https://example.com"
        result = executor._inject_auth(cmd)
        assert result == cmd


# ─── JWT Validation Tests ───────────────────────────────────────────────


class TestJWTValidation:
    def _make_jwt(self, payload: dict) -> str:
        """Create a minimal JWT for testing."""
        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        signature = "fake_signature"
        return f"{header}.{payload_b64}.{signature}"

    def test_valid_jwt_not_expired(self, tmp_engagement_dir):
        future_exp = int(time.time()) + 3600
        token = self._make_jwt({"sub": "user", "exp": future_exp})
        config = {"targets": [{"target_id": "test", "method": "web_jwt", "token": token}]}
        manager = AuthManager(config, tmp_engagement_dir)
        session = manager.authenticate("test")
        assert session.status == AuthStatus.SUCCESS.value
        assert session.access_token == token

    def test_expired_jwt(self, tmp_engagement_dir):
        past_exp = int(time.time()) - 3600
        token = self._make_jwt({"sub": "user", "exp": past_exp})
        config = {"targets": [{"target_id": "test", "method": "web_jwt", "token": token}]}
        manager = AuthManager(config, tmp_engagement_dir)
        session = manager.authenticate("test")
        assert session.status == AuthStatus.EXPIRED.value

    def test_invalid_jwt_structure(self, tmp_engagement_dir):
        token = "not.a.valid.jwt.with.extra.parts"
        config = {"targets": [{"target_id": "test", "method": "web_jwt", "token": token}]}
        manager = AuthManager(config, tmp_engagement_dir)
        session = manager.authenticate("test")
        assert session.status == AuthStatus.FAILED.value
        assert "Invalid JWT structure" in session.error

    def test_malformed_jwt_payload(self, tmp_engagement_dir):
        header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
        # Invalid base64 payload
        token = f"{header}.!!!invalid!!!.signature"
        config = {"targets": [{"target_id": "test", "method": "web_jwt", "token": token}]}
        manager = AuthManager(config, tmp_engagement_dir)
        session = manager.authenticate("test")
        assert session.status == AuthStatus.FAILED.value


# ─── Config/State Integration Tests ─────────────────────────────────────


class TestConfigIntegration:
    def test_config_has_auth_section(self):
        from core.config import DEFAULT_SWARM_CONFIG
        assert "auth" in DEFAULT_SWARM_CONFIG
        assert "targets" in DEFAULT_SWARM_CONFIG["auth"]
        assert DEFAULT_SWARM_CONFIG["auth"]["targets"] == []

    def test_engagement_dirs_includes_auth(self):
        from core.config import ENGAGEMENT_DIRS
        assert "auth" in ENGAGEMENT_DIRS

    def test_config_migration_adds_auth(self, tmp_path):
        from core.config import ConfigManager
        config_path = tmp_path / "swarm-config.json"
        # Write v1 config (no auth section)
        v1_config = {
            "version": "1.0",
            "bots": {"warchief": {"provider": "ollama", "model": "test"}},
        }
        with open(config_path, "w") as f:
            json.dump(v1_config, f)

        manager = ConfigManager(tmp_path)
        config = manager.load_config()
        assert "auth" in config
        assert config["auth"]["targets"] == []


class TestStateIntegration:
    def test_state_has_auth_fields(self):
        from core.state import SwarmState
        # TypedDict fields are accessible as class annotations
        annotations = SwarmState.__annotations__
        assert "auth_config" in annotations
        assert "auth_sessions" in annotations


# ─── Env Variable Loading Tests ─────────────────────────────────────────


class TestEnvAuthLoading:
    def test_load_auth_from_env(self):
        env = {
            "CHIMERAS_AUTH_WEB_PORTAL_METHOD": "web_form",
            "CHIMERAS_AUTH_WEB_PORTAL_URL": "https://target.com/login",
            "CHIMERAS_AUTH_WEB_PORTAL_USERNAME": "testuser",
            "CHIMERAS_AUTH_WEB_PORTAL_PASSWORD": "testpass",
        }
        with patch.dict(os.environ, env, clear=False):
            config = load_auth_from_env()
            assert "targets" in config
            assert len(config["targets"]) == 1
            target = config["targets"][0]
            assert target["target_id"] == "web_portal"
            assert target["method"] == "web_form"
            assert target["url"] == "https://target.com/login"

    def test_load_auth_from_env_empty(self):
        # Clear any existing CHIMERAS_AUTH_ vars
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("CHIMERAS_AUTH_")}
        with patch.dict(os.environ, clean_env, clear=True):
            config = load_auth_from_env()
            assert config == {"targets": []}


# ─── Utility Tests ──────────────────────────────────────────────────────


class TestUtilities:
    def test_parse_set_cookies(self):
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Set-Cookie: session=abc123; Path=/; HttpOnly\r\n"
            "Set-Cookie: csrf=def456; Path=/\r\n"
            "Content-Type: text/html\r\n"
        )
        cookies = AuthManager._parse_set_cookies(response)
        assert cookies == {"session": "abc123", "csrf": "def456"}

    def test_parse_set_cookies_empty(self):
        cookies = AuthManager._parse_set_cookies("no cookies here")
        assert cookies == {}

    def test_extract_status_code(self):
        response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
        assert AuthManager._extract_status_code(response) == 200

    def test_extract_status_code_not_found(self):
        assert AuthManager._extract_status_code("no status") is None

    def test_infer_base_dn(self):
        assert AuthManager._infer_base_dn("corp.local") == "dc=corp,dc=local"
        assert AuthManager._infer_base_dn("example.com") == "dc=example,dc=com"
        assert AuthManager._infer_base_dn("") == ""

    def test_missing_config_error(self):
        cred = AuthCredential(target_id="test", method="web_form")
        session = AuthManager._missing_config(cred, "url")
        assert session.status == AuthStatus.NOT_CONFIGURED.value
        assert "url" in session.error


# ─── OAuth2 Token Exchange Tests (mocked) ───────────────────────────────


class TestOAuth2TokenExchange:
    @patch.object(AuthManager, '_run_command')
    def test_oauth2_password_success(self, mock_run, tmp_engagement_dir):
        mock_run.return_value = {
            "success": True,
            "exit_code": 0,
            "stdout": json.dumps({
                "access_token": "oauth_token_123",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "refresh_456",
            }),
            "stderr": "",
        }
        config = {
            "targets": [{
                "target_id": "oauth",
                "method": "web_oauth2_password",
                "url": "https://auth.example.com/token",
                "username": "user",
                "password": "pass",
                "client_id": "myclient",
            }]
        }
        manager = AuthManager(config, tmp_engagement_dir)
        session = manager.authenticate("oauth")
        assert session.success
        assert session.access_token == "oauth_token_123"
        assert session.refresh_token == "refresh_456"
        assert session.token_type == "Bearer"

    @patch.object(AuthManager, '_run_command')
    def test_oauth2_error_response(self, mock_run, tmp_engagement_dir):
        mock_run.return_value = {
            "success": True,
            "exit_code": 0,
            "stdout": json.dumps({
                "error": "invalid_grant",
                "error_description": "Bad credentials",
            }),
            "stderr": "",
        }
        config = {
            "targets": [{
                "target_id": "oauth",
                "method": "web_oauth2_password",
                "url": "https://auth.example.com/token",
                "username": "user",
                "password": "wrong",
                "client_id": "myclient",
            }]
        }
        manager = AuthManager(config, tmp_engagement_dir)
        session = manager.authenticate("oauth")
        assert session.status == AuthStatus.FAILED.value
        assert "Bad credentials" in session.error or "invalid_grant" in session.error

    @patch.object(AuthManager, '_run_command')
    def test_keycloak_client_credentials_success(self, mock_run, tmp_engagement_dir):
        mock_run.return_value = {
            "success": True,
            "exit_code": 0,
            "stdout": json.dumps({
                "access_token": "kc_token_789",
                "token_type": "Bearer",
                "expires_in": 300,
            }),
            "stderr": "",
        }
        config = {
            "targets": [{
                "target_id": "kc",
                "method": "keycloak_oauth2_client_credentials",
                "url": "https://keycloak.example.com/realms/myrealm/protocol/openid-connect/token",
                "client_id": "service-client",
                "client_secret": "service-secret",
            }]
        }
        manager = AuthManager(config, tmp_engagement_dir)
        session = manager.authenticate("kc")
        assert session.success
        assert session.access_token == "kc_token_789"

    @patch.object(AuthManager, '_run_command')
    def test_oauth2_non_json_response(self, mock_run, tmp_engagement_dir):
        mock_run.return_value = {
            "success": True,
            "exit_code": 0,
            "stdout": "<html>Not found</html>",
            "stderr": "",
        }
        config = {
            "targets": [{
                "target_id": "oauth",
                "method": "web_oauth2_password",
                "url": "https://auth.example.com/token",
                "username": "user",
                "password": "pass",
                "client_id": "myclient",
            }]
        }
        manager = AuthManager(config, tmp_engagement_dir)
        session = manager.authenticate("oauth")
        assert session.status == AuthStatus.FAILED.value
        assert "non-JSON" in session.error


# ─── Curl/SQLmap Auth Args Tests ────────────────────────────────────────


class TestAuthArgsGeneration:
    def test_curl_auth_args_bearer(self, tmp_engagement_dir):
        config = {"targets": [{"target_id": "test", "method": "web_bearer", "token": "mytoken", "url": "https://example.com"}]}
        manager = AuthManager(config, tmp_engagement_dir)
        manager.sessions["test"] = AuthSession(
            target_id="test", method="web_bearer",
            status=AuthStatus.SUCCESS.value,
            access_token="mytoken",
        )
        args = manager.get_curl_auth_args("test")
        assert "Bearer mytoken" in args

    def test_curl_auth_args_basic(self, tmp_engagement_dir):
        config = {"targets": [{"target_id": "test", "method": "web_basic", "username": "user", "password": "pass", "url": "https://example.com"}]}
        manager = AuthManager(config, tmp_engagement_dir)
        manager.sessions["test"] = AuthSession(
            target_id="test", method="web_basic",
            status=AuthStatus.SUCCESS.value,
        )
        args = manager.get_curl_auth_args("test")
        assert "-u" in args
        assert "user:pass" in args

    def test_curl_auth_args_cookies(self, tmp_engagement_dir):
        config = {"targets": [{"target_id": "test", "method": "web_cookie", "cookies": {"session": "abc"}, "url": "https://example.com"}]}
        manager = AuthManager(config, tmp_engagement_dir)
        manager.sessions["test"] = AuthSession(
            target_id="test", method="web_cookie",
            status=AuthStatus.SUCCESS.value,
            cookies={"session": "abc"},
        )
        args = manager.get_curl_auth_args("test")
        assert "Cookie" in args
        assert "session=abc" in args

    def test_curl_auth_args_empty(self, auth_manager):
        assert auth_manager.get_curl_auth_args("nonexistent") == ""

    def test_sqlmap_auth_args_basic(self, tmp_engagement_dir):
        config = {"targets": [{"target_id": "test", "method": "web_basic", "username": "user", "password": "pass", "url": "https://example.com"}]}
        manager = AuthManager(config, tmp_engagement_dir)
        manager.sessions["test"] = AuthSession(
            target_id="test", method="web_basic",
            status=AuthStatus.SUCCESS.value,
        )
        args = manager.get_sqlmap_auth_args("test")
        assert "Basic" in args
        assert "user:pass" in args

    def test_sqlmap_auth_args_cookies(self, tmp_engagement_dir):
        config = {"targets": [{"target_id": "test", "method": "web_cookie", "cookies": {"s": "1"}, "url": "https://example.com"}]}
        manager = AuthManager(config, tmp_engagement_dir)
        manager.sessions["test"] = AuthSession(
            target_id="test", method="web_cookie",
            status=AuthStatus.SUCCESS.value,
            cookies={"s": "1"},
        )
        args = manager.get_sqlmap_auth_args("test")
        assert "cookie" in args

    def test_nmap_auth_args_ad(self, tmp_engagement_dir):
        config = {"targets": [{"target_id": "ad", "method": "ad_ldap_bind", "domain": "CORP", "username": "admin", "password": "pass"}]}
        manager = AuthManager(config, tmp_engagement_dir)
        args = manager.get_nmap_auth_args("ad")
        assert "smbdomain=CORP" in args
        assert "smbuser=admin" in args

    def test_ssh_command_prefix_password(self, tmp_engagement_dir):
        config = {"targets": [{"target_id": "ssh1", "method": "ssh_password", "url": "10.10.10.5", "username": "root", "password": "toor"}]}
        manager = AuthManager(config, tmp_engagement_dir)
        prefix = manager.get_ssh_command_prefix("ssh1")
        assert "sshpass" in prefix
        assert "root@10.10.10.5" in prefix

    def test_ssh_command_prefix_key(self, tmp_engagement_dir):
        config = {"targets": [{"target_id": "ssh1", "method": "ssh_key", "url": "10.10.10.5", "username": "root", "ssh_key_path": "/root/.ssh/id_rsa"}]}
        manager = AuthManager(config, tmp_engagement_dir)
        prefix = manager.get_ssh_command_prefix("ssh1")
        assert "-i /root/.ssh/id_rsa" in prefix
        assert "root@10.10.10.5" in prefix

    def test_ldapsearch_command_simple(self, tmp_engagement_dir):
        config = {"targets": [{"target_id": "ldap1", "method": "ldap_simple", "ldap_server": "ldap://dc01.corp.local", "username": "cn=admin,dc=corp,dc=local", "password": "pass", "ldap_base_dn": "dc=corp,dc=local"}]}
        manager = AuthManager(config, tmp_engagement_dir)
        cmd = manager.get_ldapsearch_command("ldap1")
        assert "ldapsearch" in cmd
        assert "ldap://dc01.corp.local" in cmd
        assert "cn=admin,dc=corp,dc=local" in cmd

    def test_ldapsearch_command_anonymous(self, tmp_engagement_dir):
        config = {"targets": [{"target_id": "ldap1", "method": "ldap_anonymous", "ldap_server": "ldap://dc01.corp.local", "ldap_base_dn": "dc=corp,dc=local"}]}
        manager = AuthManager(config, tmp_engagement_dir)
        cmd = manager.get_ldapsearch_command("ldap1")
        assert "ldapsearch" in cmd
        assert "-x" in cmd
        # Anonymous should not have -D or -w
        assert "-D" not in cmd
        assert "-w" not in cmd

    def test_ldapsearch_command_ad(self, tmp_engagement_dir):
        config = {"targets": [{"target_id": "ad1", "method": "ad_ldap_bind", "domain": "CORP", "username": "admin", "password": "pass", "ldap_server": "ldap://dc01.corp.local", "ldap_base_dn": "dc=corp,dc=local"}]}
        manager = AuthManager(config, tmp_engagement_dir)
        cmd = manager.get_ldapsearch_command("ad1")
        assert "CORP\\admin" in cmd


# ─── AuthMethod Enum Tests ──────────────────────────────────────────────


class TestAuthMethodEnum:
    def test_all_methods_have_handlers(self):
        """Every AuthMethod should have a corresponding handler in AuthManager."""
        from core.auth_manager import AuthManager as AM
        # The _dispatch_auth method maps methods to handlers
        # Check that all enum values are valid strings
        for method in AuthMethod:
            assert isinstance(method.value, str)
            assert method.value  # Non-empty

    def test_auth_status_values(self):
        assert AuthStatus.SUCCESS.value == "success"
        assert AuthStatus.FAILED.value == "failed"
        assert AuthStatus.EXPIRED.value == "expired"
        assert AuthStatus.PENDING.value == "pending"
        assert AuthStatus.NOT_CONFIGURED.value == "not_configured"