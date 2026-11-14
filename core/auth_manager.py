"""
Chimeras v3.3 — Authentication Manager

Handles authentication for grey-box and white-box engagements.
Supports: Web (forms, JWT, Bearer, Basic, cookies, OAuth2), Active Directory
(LDAP bind, Kerberos), Keycloak (OAuth2/OIDC, client_credentials, password
grant), LDAP (simple, SASL, anonymous bind).

Design principles:
- One AuthManager per engagement, instantiated by BaseBot.
- Credentials NEVER logged in plaintext. Redacted in all telemetry.
- Sessions are persisted to engagement/auth/ for reuse across bots.
- Each auth attempt returns an AuthSession with tokens/cookies/headers.
- ToolExecutor queries AuthManager to inject auth context into commands.
- Failed auth attempts are retried with backoff, then logged as failures.
- Credentials loaded from config (swarm-config.json auth section) or
  from environment variables (prefixed CHIMERAS_AUTH_).

Usage:
    manager = AuthManager(auth_config, engagement_dir)
    session = manager.authenticate("web_portal")
    if session.success:
        headers = session.get_headers()    # {'Cookie': '...', 'Authorization': 'Bearer ...'}
        cookies = session.get_cookies()    # {'session_id': '...'}
        token = session.get_token()        # 'eyJhbG...'
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import subprocess
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone


# ─── Enums ──────────────────────────────────────────────────────────────

class AuthMethod(Enum):
    """Supported authentication methods."""
    # Web
    WEB_FORM = "web_form"
    WEB_BASIC = "web_basic"
    WEB_BEARER = "web_bearer"
    WEB_JWT = "web_jwt"
    WEB_COOKIE = "web_cookie"
    WEB_OAUTH2_PASSWORD = "web_oauth2_password"
    WEB_OAUTH2_CLIENT_CREDENTIALS = "web_oauth2_client_credentials"
    WEB_API_KEY = "web_api_key"
    WEB_NTLM = "web_ntlm"
    # Active Directory
    AD_LDAP_BIND = "ad_ldap_bind"
    AD_KERBEROS = "ad_kerberos"
    AD_NTLM = "ad_ntlm"
    # Keycloak
    KEYCLOAK_OAUTH2_PASSWORD = "keycloak_oauth2_password"
    KEYCLOAK_OAUTH2_CLIENT_CREDENTIALS = "keycloak_oauth2_client_credentials"
    KEYCLOAK_OIDC = "keycloak_oidc"
    # LDAP
    LDAP_SIMPLE = "ldap_simple"
    LDAP_SASL = "ldap_sasl"
    LDAP_ANONYMOUS = "ldap_anonymous"
    # Database
    DB_MYSQL = "db_mysql"
    DB_POSTGRESQL = "db_postgresql"
    DB_MSSQL = "db_mssql"
    # SSH
    SSH_PASSWORD = "ssh_password"
    SSH_KEY = "ssh_key"


class AuthStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"
    PENDING = "pending"
    NOT_CONFIGURED = "not_configured"


# ─── Data Classes ───────────────────────────────────────────────────────

@dataclass
class AuthCredential:
    """Single credential set for a target service."""
    target_id: str          # logical name, e.g. "web_portal", "ad_primary"
    method: str             # AuthMethod value
    # Common fields
    username: str = ""
    password: str = ""
    domain: str = ""        # AD domain, e.g. "CORP"
    realm: str = ""         # Kerberos realm, e.g. "CORP.LOCAL"
    # Web-specific
    url: str = ""           # Login URL / token endpoint
    form_username_field: str = "username"
    form_password_field: str = "password"
    form_csrf_field: str = ""
    form_extra_fields: Dict[str, str] = field(default_factory=dict)
    # Token-based
    token: str = ""         # Pre-existing token (bearer/JWT/API key)
    token_type: str = "Bearer"  # Bearer, Basic, custom
    refresh_token: str = ""
    token_header: str = "Authorization"  # Header name for token
    token_prefix: str = "Bearer "   # Prefix before token in header
    # OAuth2 / Keycloak
    client_id: str = ""
    client_secret: str = ""
    scope: str = ""
    grant_type: str = "password"
    # LDAP / AD
    ldap_server: str = ""   # ldap://dc01.corp.local
    ldap_port: int = 389
    ldap_use_tls: bool = True
    ldap_base_dn: str = ""  # dc=corp,dc=local
    ldap_search_filter: str = "(sAMAccountName={username})"
    # Kerberos
    kdc: str = ""           # KDC server
    keytab_path: str = ""   # Path to keytab file
    # SSH
    ssh_key_path: str = ""
    ssh_port: int = 22
    # Database
    db_host: str = ""
    db_port: int = 0
    db_name: str = ""
    # Cookies
    cookies: Dict[str, str] = field(default_factory=dict)
    # Headers (extra)
    headers: Dict[str, str] = field(default_factory=dict)
    # Metadata
    description: str = ""
    # Security
    _password_hash: str = ""

    def __post_init__(self):
        if self.password:
            self._password_hash = hashlib.sha256(
                self.password.encode()
            ).hexdigest()[:16]

    def redact(self) -> Dict[str, Any]:
        """Return a redacted dict (no passwords/secrets) for logging."""
        d = asdict(self)
        for key in ("password", "token", "refresh_token", "client_secret",
                     "cookies", "headers", "_password_hash"):
            if d.get(key):
                d[key] = "***REDACTED***"
        return d


@dataclass
class AuthSession:
    """Result of an authentication attempt. Persisted for bot reuse."""
    target_id: str
    method: str
    status: str                     # AuthStatus value
    timestamp: str = ""             # ISO timestamp of auth attempt
    # Acquired tokens/cookies
    access_token: str = ""
    token_type: str = "Bearer"
    refresh_token: str = ""
    expires_at: str = ""            # ISO timestamp or empty
    cookies: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    # Raw response (truncated, for debugging)
    raw_response: str = ""
    error: str = ""
    # Metadata
    attempts: int = 0
    latency_ms: int = 0

    @property
    def success(self) -> bool:
        return self.status == AuthStatus.SUCCESS.value

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at)
            return datetime.now(timezone.utc) > exp
        except (ValueError, TypeError):
            return False

    def get_headers(self) -> Dict[str, str]:
        """Return HTTP headers for this session."""
        result = dict(self.headers)
        if self.access_token:
            prefix = "Bearer "
            if self.token_type and self.token_type != "Bearer":
                prefix = f"{self.token_type} "
            result["Authorization"] = f"{prefix}{self.access_token}"
        if self.cookies:
            cookie_str = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
            result["Cookie"] = cookie_str
        return result

    def get_cookies(self) -> Dict[str, str]:
        return dict(self.cookies)

    def get_token(self) -> str:
        return self.access_token

    def get_authorization_header(self) -> str:
        """Return the full Authorization header value."""
        if self.access_token:
            prefix = "Bearer "
            if self.token_type and self.token_type != "Bearer":
                prefix = f"{self.token_type} "
            return f"{prefix}{self.access_token}"
        return ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Redact sensitive fields for storage
        if d.get("access_token"):
            d["access_token"] = "***REDACTED***"
        if d.get("refresh_token"):
            d["refresh_token"] = "***REDACTED***"
        if d.get("cookies"):
            d["cookies"] = {k: "***REDACTED***" for k in d["cookies"]}
        return d


# ─── Auth Manager ───────────────────────────────────────────────────────

class AuthManager:
    """
    Central authentication manager for Chimeras engagements.

    Manages multiple auth targets (web portal, AD, LDAP, Keycloak, etc.).
    Each target has its own credential config and produces an AuthSession.
    Sessions are cached and persisted to engagement/auth/sessions.json.
    """

    def __init__(self, auth_config: Dict[str, Any],
                 engagement_dir: Optional[Path] = None):
        """
        Args:
            auth_config: Dict from swarm-config.json "auth" section.
                Format: {
                    "targets": [
                        {
                            "target_id": "web_portal",
                            "method": "web_form",
                            "url": "https://target.com/login",
                            "username": "testuser",
                            "password": "testpass",
                            ...
                        },
                        ...
                    ]
                }
            engagement_dir: Path to engagement folder. Sessions persisted
                to engagement/auth/sessions.json.
        """
        self.config = auth_config or {}
        self.targets: Dict[str, AuthCredential] = {}
        self.sessions: Dict[str, AuthSession] = {}
        self._engagement_dir = engagement_dir

        # Load targets from config
        self._load_targets()

        # Try to load existing sessions
        if engagement_dir:
            self._auth_dir = engagement_dir / "auth"
            self._auth_dir.mkdir(parents=True, exist_ok=True)
            self._load_sessions()
        else:
            self._auth_dir = None

    def _load_targets(self):
        """Parse auth config into AuthCredential objects."""
        targets = self.config.get("targets", [])
        if isinstance(targets, dict):
            # Allow dict format: {"web_portal": {...}, "ad_primary": {...}}
            for tid, tcfg in targets.items():
                tcfg = dict(tcfg)
                tcfg.setdefault("target_id", tid)
                cred = AuthCredential(**self._filter_credential_fields(tcfg))
                self.targets[cred.target_id] = cred
        elif isinstance(targets, list):
            for tcfg in targets:
                cred = AuthCredential(**self._filter_credential_fields(tcfg))
                self.targets[cred.target_id] = cred

    @staticmethod
    def _filter_credential_fields(config: Dict[str, Any]) -> Dict[str, Any]:
        """Filter config dict to only valid AuthCredential fields."""
        valid_fields = {f.name for f in AuthCredential.__dataclass_fields__.values()}
        # Allow _password_hash through
        valid_fields.add("_password_hash")
        return {k: v for k, v in config.items() if k in valid_fields}

    def _load_sessions(self):
        """Load persisted sessions from disk."""
        if not self._auth_dir:
            return
        sessions_path = self._auth_dir / "sessions.json"
        if not sessions_path.exists():
            return
        try:
            with open(sessions_path) as f:
                data = json.load(f)
            for tid, sdata in data.items():
                # Don't restore redacted tokens — they need re-auth
                session = AuthSession(**self._filter_session_fields(sdata))
                if session.access_token == "***REDACTED***":
                    session.access_token = ""
                    session.status = AuthStatus.EXPIRED.value
                self.sessions[tid] = session
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            pass  # Corrupt sessions file — start fresh

    @staticmethod
    def _filter_session_fields(config: Dict[str, Any]) -> Dict[str, Any]:
        """Filter config dict to only valid AuthSession fields."""
        valid_fields = {f.name for f in AuthSession.__dataclass_fields__.values()}
        return {k: v for k, v in config.items() if k in valid_fields}

    def _save_sessions(self):
        """Persist sessions to disk (redacted)."""
        if not self._auth_dir:
            return
        sessions_path = self._auth_dir / "sessions.json"
        try:
            data = {tid: s.to_dict() for tid, s in self.sessions.items()}
            with open(sessions_path, "w") as f:
                json.dump(data, f, indent=2)
        except (OSError, TypeError) as e:
            pass  # Non-fatal — sessions are cached in memory

    # ─── Public API ─────────────────────────────────────────────────────

    def authenticate(self, target_id: str, force: bool = False) -> AuthSession:
        """
        Authenticate to a target. Returns AuthSession.

        If a valid (non-expired) session exists and force=False, returns
        the cached session. Otherwise performs fresh authentication.

        Args:
            target_id: Logical target identifier.
            force: If True, ignore cached session and re-authenticate.
        """
        if target_id not in self.targets:
            return AuthSession(
                target_id=target_id,
                method="unknown",
                status=AuthStatus.NOT_CONFIGURED.value,
                error=f"No auth target '{target_id}' configured",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Check cache
        if not force and target_id in self.sessions:
            session = self.sessions[target_id]
            if session.success and not session.is_expired:
                return session

        # Perform auth
        cred = self.targets[target_id]
        try:
            method = AuthMethod(cred.method)
        except ValueError:
            return AuthSession(
                target_id=target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"Unknown auth method: {cred.method}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        session = self._dispatch_auth(cred, method)
        self.sessions[target_id] = session
        self._save_sessions()
        return session

    def authenticate_all(self, force: bool = False) -> Dict[str, AuthSession]:
        """Authenticate to all configured targets."""
        results = {}
        for target_id in self.targets:
            results[target_id] = self.authenticate(target_id, force=force)
        return results

    def get_session(self, target_id: str) -> Optional[AuthSession]:
        """Get cached session without re-authenticating."""
        return self.sessions.get(target_id)

    def get_headers(self, target_id: str) -> Dict[str, str]:
        """Convenience: get HTTP headers for a target. Empty if no session."""
        session = self.sessions.get(target_id)
        if session and session.success:
            return session.get_headers()
        return {}

    def get_cookies(self, target_id: str) -> Dict[str, str]:
        """Convenience: get cookies for a target. Empty if no session."""
        session = self.sessions.get(target_id)
        if session and session.success:
            return session.get_cookies()
        return {}

    def get_token(self, target_id: str) -> str:
        """Convenience: get access token for a target. Empty if none."""
        session = self.sessions.get(target_id)
        if session and session.success:
            return session.get_token()
        return ""

    def get_authorization_header(self, target_id: str) -> str:
        """Convenience: get full Authorization header value."""
        session = self.sessions.get(target_id)
        if session and session.success:
            return session.get_authorization_header()
        return ""

    def get_curl_auth_args(self, target_id: str) -> str:
        """
        Return curl-compatible auth arguments for a target.

        Examples:
            - Bearer token: -H "Authorization: Bearer eyJ..."
            - Cookies: -H "Cookie: session=abc; csrf=def"
            - Basic: -u user:pass
            - API key: -H "X-API-Key: ..."
        """
        session = self.sessions.get(target_id)
        if not session or not session.success:
            return ""

        cred = self.targets.get(target_id)
        if not cred:
            return ""

        parts: List[str] = []

        method = session.method
        if method in (AuthMethod.WEB_BASIC.value,):
            parts.append(f'-u "{cred.username}:{cred.password}"')
        elif method == AuthMethod.WEB_BEARER.value or method == AuthMethod.WEB_JWT.value:
            token = session.get_token()
            if token:
                parts.append(f'-H "Authorization: Bearer {token}"')
        elif method == AuthMethod.WEB_API_KEY.value:
            header = cred.token_header or "X-API-Key"
            parts.append(f'-H "{header}: {cred.token}"')
        elif method == AuthMethod.WEB_COOKIE.value:
            if session.cookies:
                cookie_str = "; ".join(f"{k}={v}" for k, v in session.cookies.items())
                parts.append(f'-H "Cookie: {cookie_str}"')
        elif method in (AuthMethod.WEB_FORM.value,
                        AuthMethod.WEB_OAUTH2_PASSWORD.value,
                        AuthMethod.WEB_OAUTH2_CLIENT_CREDENTIALS.value,
                        AuthMethod.KEYCLOAK_OAUTH2_PASSWORD.value,
                        AuthMethod.KEYCLOAK_OAUTH2_CLIENT_CREDENTIALS.value,
                        AuthMethod.KEYCLOAK_OIDC.value):
            # After auth, use the acquired token or cookies
            if session.access_token:
                parts.append(f'-H "Authorization: Bearer {session.access_token}"')
            if session.cookies:
                cookie_str = "; ".join(f"{k}={v}" for k, v in session.cookies.items())
                parts.append(f'-H "Cookie: {cookie_str}"')
        elif method == AuthMethod.WEB_NTLM.value:
            parts.append(f'--ntlm -u "{cred.domain}\\\\{cred.username}:{cred.password}"')
        else:
            # Generic: use session headers
            headers = session.get_headers()
            for k, v in headers.items():
                parts.append(f'-H "{k}: {v}"')

        return " ".join(parts)

    def get_sqlmap_auth_args(self, target_id: str) -> str:
        """Return sqlmap-compatible auth arguments."""
        session = self.sessions.get(target_id)
        if not session or not session.success:
            return ""

        cred = self.targets.get(target_id)
        if not cred:
            return ""

        method = session.method
        parts: List[str] = []

        if method == AuthMethod.WEB_BASIC.value:
            parts.append(f'--auth-type=Basic --auth-cred="{cred.username}:{cred.password}"')
        elif method in (AuthMethod.WEB_BEARER.value, AuthMethod.WEB_JWT.value):
            token = session.get_token()
            if token:
                parts.append(f'--auth-type=Bearer --auth-cred="{token}"')
        elif method == AuthMethod.WEB_COOKIE.value:
            if session.cookies:
                cookie_str = "; ".join(f"{k}={v}" for k, v in session.cookies.items())
                parts.append(f'--cookie="{cookie_str}"')
        else:
            # Use session cookies/token
            if session.cookies:
                cookie_str = "; ".join(f"{k}={v}" for k, v in session.cookies.items())
                parts.append(f'--cookie="{cookie_str}"')
            if session.access_token:
                parts.append(f'--header="Authorization: Bearer {session.access_token}"')

        return " ".join(parts)

    def get_nmap_auth_args(self, target_id: str) -> str:
        """Return nmap/auth-related arguments for SMB/AD targets."""
        cred = self.targets.get(target_id)
        if not cred:
            return ""

        method = cred.method
        parts: List[str] = []

        if method in (AuthMethod.AD_LDAP_BIND.value, AuthMethod.LDAP_SIMPLE.value):
            parts.append(f'--script-args "smbdomain={cred.domain},smbuser={cred.username},smbpass={cred.password}"')
        elif method == AuthMethod.SSH_PASSWORD.value:
            parts.append(f'--script-args "sshuser={cred.username},sshpass={cred.password}"')

        return " ".join(parts)

    def get_ssh_command_prefix(self, target_id: str) -> str:
        """Return SSH connection string for SSH targets."""
        cred = self.targets.get(target_id)
        if not cred:
            return ""

        if cred.method == AuthMethod.SSH_KEY.value and cred.ssh_key_path:
            return f"ssh -i {cred.ssh_key_path} -p {cred.ssh_port} {cred.username}@{cred.url or cred.db_host}"
        elif cred.method == AuthMethod.SSH_PASSWORD.value:
            # sshpass for non-interactive password auth
            return f"sshpass -p '{cred.password}' ssh -p {cred.ssh_port} {cred.username}@{cred.url or cred.db_host}"
        return ""

    def get_ldapsearch_command(self, target_id: str, search_filter: str = "",
                               extra_args: str = "") -> str:
        """Build an ldapsearch command for LDAP/AD targets."""
        cred = self.targets.get(target_id)
        if not cred:
            return ""

        server = cred.ldap_server or f"ldap://{cred.domain}"
        port = cred.ldap_port or 389
        base_dn = cred.ldap_base_dn
        filter_str = search_filter or cred.ldap_search_filter.replace(
            "{username}", cred.username
        )

        if cred.method == AuthMethod.LDAP_ANONYMOUS.value:
            return (
                f"ldapsearch -x -H {server}:{port} -b \"{base_dn}\" "
                f"\"{filter_str}\" {extra_args}"
            )
        else:
            user_dn = cred.username
            if cred.domain and "\\" not in cred.username and "@" not in cred.username:
                # Format as DOMAIN\username for AD
                user_dn = f"{cred.domain}\\{cred.username}"

            tls_flag = "-ZZ" if cred.ldap_use_tls else ""
            return (
                f"ldapsearch -x {tls_flag} -H {server}:{port} "
                f"-D \"{user_dn}\" -w '{cred.password}' "
                f"-b \"{base_dn}\" \"{filter_str}\" {extra_args}"
            )

    def list_targets(self) -> List[str]:
        """Return list of configured target IDs."""
        return list(self.targets.keys())

    def has_auth(self, target_id: str) -> bool:
        """Check if a target has a valid (successful) auth session."""
        session = self.sessions.get(target_id)
        return bool(session and session.success and not session.is_expired)

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Return auth status for all targets (redacted)."""
        result = {}
        for tid, cred in self.targets.items():
            session = self.sessions.get(tid)
            result[tid] = {
                "method": cred.method,
                "status": session.status if session else AuthStatus.PENDING.value,
                "expired": session.is_expired if session else False,
                "has_token": bool(session and session.access_token) if session else False,
                "has_cookies": bool(session and session.cookies) if session else False,
                "error": session.error if session else "",
                "credential": cred.redact(),
            }
        return result

    # ─── Auth Dispatch ──────────────────────────────────────────────────

    def _dispatch_auth(self, cred: AuthCredential,
                       method: AuthMethod) -> AuthSession:
        """Route to the appropriate auth handler based on method."""
        handlers = {
            AuthMethod.WEB_FORM: self._auth_web_form,
            AuthMethod.WEB_BASIC: self._auth_web_basic,
            AuthMethod.WEB_BEARER: self._auth_web_bearer,
            AuthMethod.WEB_JWT: self._auth_web_jwt,
            AuthMethod.WEB_COOKIE: self._auth_web_cookie,
            AuthMethod.WEB_OAUTH2_PASSWORD: self._auth_oauth2_password,
            AuthMethod.WEB_OAUTH2_CLIENT_CREDENTIALS: self._auth_oauth2_client_credentials,
            AuthMethod.WEB_API_KEY: self._auth_web_api_key,
            AuthMethod.WEB_NTLM: self._auth_web_ntlm,
            AuthMethod.AD_LDAP_BIND: self._auth_ad_ldap_bind,
            AuthMethod.AD_KERBEROS: self._auth_ad_kerberos,
            AuthMethod.AD_NTLM: self._auth_ad_ntlm,
            AuthMethod.KEYCLOAK_OAUTH2_PASSWORD: self._auth_keycloak_password,
            AuthMethod.KEYCLOAK_OAUTH2_CLIENT_CREDENTIALS: self._auth_keycloak_client_credentials,
            AuthMethod.KEYCLOAK_OIDC: self._auth_keycloak_oidc,
            AuthMethod.LDAP_SIMPLE: self._auth_ldap_simple,
            AuthMethod.LDAP_SASL: self._auth_ldap_sasl,
            AuthMethod.LDAP_ANONYMOUS: self._auth_ldap_anonymous,
            AuthMethod.DB_MYSQL: self._auth_db_mysql,
            AuthMethod.DB_POSTGRESQL: self._auth_db_postgresql,
            AuthMethod.DB_MSSQL: self._auth_db_mssql,
            AuthMethod.SSH_PASSWORD: self._auth_ssh_password,
            AuthMethod.SSH_KEY: self._auth_ssh_key,
        }

        handler = handlers.get(method)
        if not handler:
            return AuthSession(
                target_id=cred.target_id,
                method=method.value,
                status=AuthStatus.FAILED.value,
                error=f"No handler for method {method.value}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Retry with backoff
        max_attempts = 3
        base_delay = 1.0
        last_session = None

        for attempt in range(1, max_attempts + 1):
            start_time = time.time()
            try:
                session = handler(cred)
                session.attempts = attempt
                session.latency_ms = int((time.time() - start_time) * 1000)
                session.timestamp = datetime.now(timezone.utc).isoformat()

                if session.success:
                    return session

                last_session = session
                # Don't retry on NOT_CONFIGURED or wrong credentials
                if session.status == AuthStatus.NOT_CONFIGURED.value:
                    return session
                if "invalid" in session.error.lower() or "unauthorized" in session.error.lower():
                    return session  # Bad creds — no point retrying

            except Exception as e:
                last_session = AuthSession(
                    target_id=cred.target_id,
                    method=method.value,
                    status=AuthStatus.FAILED.value,
                    error=f"Auth handler exception: {type(e).__name__}: {e}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    attempts=attempt,
                )

            if attempt < max_attempts:
                time.sleep(base_delay * attempt)

        return last_session or AuthSession(
            target_id=cred.target_id,
            method=method.value,
            status=AuthStatus.FAILED.value,
            error="All retry attempts exhausted",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # ─── Web Auth Handlers ──────────────────────────────────────────────

    def _auth_web_form(self, cred: AuthCredential) -> AuthSession:
        """
        Web form login. Uses curl to POST credentials and extract
        session cookies from the response.
        """
        if not cred.url:
            return self._missing_config(cred, "url")

        # Build POST data
        post_data = {
            cred.form_username_field: cred.username,
            cred.form_password_field: cred.password,
        }
        if cred.form_csrf_field:
            # Try to fetch CSRF token first
            csrf_token = self._fetch_csrf_token(cred.url, cred.form_csrf_field)
            if csrf_token:
                post_data[cred.form_csrf_field] = csrf_token
        post_data.update(cred.form_extra_fields)

        post_str = "&".join(f"{k}={v}" for k, v in post_data.items())

        # Use curl for form login
        cmd = (
            f"curl -s -D - -X POST \"{cred.url}\" "
            f"-d \"{post_str}\" "
            f"-H \"Content-Type: application/x-www-form-urlencoded\" "
            f"-H \"User-Agent: Chimeras/3.3\" "
            f"--max-time 30"
        )

        result = self._run_command(cmd)
        if not result["success"]:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"Form login request failed: {result['stderr'][:200]}",
                raw_response=result["stdout"][:500],
            )

        # Parse Set-Cookie headers
        cookies = self._parse_set_cookies(result["stdout"])

        # Check for success indicators (no redirect to login, 200/302 to dashboard)
        status_code = self._extract_status_code(result["stdout"])

        # Heuristic: if we got cookies and not a 401/403, consider it successful
        if cookies and status_code and status_code not in (401, 403):
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.SUCCESS.value,
                cookies=cookies,
                raw_response=result["stdout"][:500],
            )
        elif cookies and status_code in (302, 303):
            # Redirect after login — likely successful
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.SUCCESS.value,
                cookies=cookies,
                raw_response=result["stdout"][:500],
            )
        else:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"Form login rejected (HTTP {status_code}, {len(cookies)} cookies)",
                cookies=cookies,
                raw_response=result["stdout"][:500],
            )

    def _auth_web_basic(self, cred: AuthCredential) -> AuthSession:
        """HTTP Basic Auth. Verify with curl."""
        if not cred.url:
            return self._missing_config(cred, "url")

        cmd = (
            f"curl -s -o /dev/null -w \"%{{http_code}}\" "
            f"-u \"{cred.username}:{cred.password}\" "
            f"\"{cred.url}\" --max-time 15"
        )
        result = self._run_command(cmd)
        status_code = result["stdout"].strip()

        if status_code in ("200", "301", "302"):
            token = base64.b64encode(
                f"{cred.username}:{cred.password}".encode()
            ).decode()
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.SUCCESS.value,
                access_token=token,
                token_type="Basic",
            )
        else:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"Basic auth rejected (HTTP {status_code})",
            )

    def _auth_web_bearer(self, cred: AuthCredential) -> AuthSession:
        """Pre-existing Bearer token. Verify with curl."""
        if not cred.token:
            return self._missing_config(cred, "token")
        if not cred.url:
            return self._missing_config(cred, "url")

        header = cred.token_header or "Authorization"
        prefix = cred.token_prefix or "Bearer "
        cmd = (
            f"curl -s -o /dev/null -w \"%{{http_code}}\" "
            f"-H \"{header}: {prefix}{cred.token}\" "
            f"\"{cred.url}\" --max-time 15"
        )
        result = self._run_command(cmd)
        status_code = result["stdout"].strip()

        if status_code in ("200", "301", "302"):
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.SUCCESS.value,
                access_token=cred.token,
                token_type="Bearer",
            )
        else:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"Bearer token rejected (HTTP {status_code})",
            )

    def _auth_web_jwt(self, cred: AuthCredential) -> AuthSession:
        """JWT token. Validate structure and (optionally) verify."""
        if not cred.token:
            return self._missing_config(cred, "token")

        # Validate JWT structure (header.payload.signature)
        parts = cred.token.split(".")
        if len(parts) != 3:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error="Invalid JWT structure (expected 3 parts)",
            )

        # Decode payload to check expiry
        try:
            # Add padding for base64url
            payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            exp = payload.get("exp")
            if exp and exp < time.time():
                return AuthSession(
                    target_id=cred.target_id,
                    method=cred.method,
                    status=AuthStatus.EXPIRED.value,
                    error=f"JWT expired at {datetime.fromtimestamp(exp).isoformat()}",
                )
            expires_at = datetime.fromtimestamp(exp).isoformat() if exp else ""
        except Exception as e:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"JWT decode failed: {e}",
            )

        # If URL provided, verify with curl
        if cred.url:
            cmd = (
                f"curl -s -o /dev/null -w \"%{{http_code}}\" "
                f"-H \"Authorization: Bearer {cred.token}\" "
                f"\"{cred.url}\" --max-time 15"
            )
            result = self._run_command(cmd)
            status_code = result["stdout"].strip()
            if status_code in ("401", "403"):
                return AuthSession(
                    target_id=cred.target_id,
                    method=cred.method,
                    status=AuthStatus.FAILED.value,
                    error=f"JWT rejected by server (HTTP {status_code})",
                )

        return AuthSession(
            target_id=cred.target_id,
            method=cred.method,
            status=AuthStatus.SUCCESS.value,
            access_token=cred.token,
            token_type="Bearer",
            expires_at=expires_at,
        )

    def _auth_web_cookie(self, cred: AuthCredential) -> AuthSession:
        """Pre-existing cookies. Verify with curl if URL provided."""
        if not cred.cookies:
            return self._missing_config(cred, "cookies")

        if cred.url:
            cookie_str = "; ".join(f"{k}={v}" for k, v in cred.cookies.items())
            cmd = (
                f"curl -s -o /dev/null -w \"%{{http_code}}\" "
                f"-H \"Cookie: {cookie_str}\" "
                f"\"{cred.url}\" --max-time 15"
            )
            result = self._run_command(cmd)
            status_code = result["stdout"].strip()
            if status_code in ("401", "403"):
                return AuthSession(
                    target_id=cred.target_id,
                    method=cred.method,
                    status=AuthStatus.FAILED.value,
                    error=f"Cookie rejected (HTTP {status_code})",
                )

        return AuthSession(
            target_id=cred.target_id,
            method=cred.method,
            status=AuthStatus.SUCCESS.value,
            cookies=dict(cred.cookies),
        )

    def _auth_web_api_key(self, cred: AuthCredential) -> AuthSession:
        """API key in header. Verify with curl if URL provided."""
        if not cred.token:
            return self._missing_config(cred, "token")

        header = cred.token_header or "X-API-Key"

        if cred.url:
            cmd = (
                f"curl -s -o /dev/null -w \"%{{http_code}}\" "
                f"-H \"{header}: {cred.token}\" "
                f"\"{cred.url}\" --max-time 15"
            )
            result = self._run_command(cmd)
            status_code = result["stdout"].strip()
            if status_code in ("401", "403"):
                return AuthSession(
                    target_id=cred.target_id,
                    method=cred.method,
                    status=AuthStatus.FAILED.value,
                    error=f"API key rejected (HTTP {status_code})",
                )

        return AuthSession(
            target_id=cred.target_id,
            method=cred.method,
            status=AuthStatus.SUCCESS.value,
            access_token=cred.token,
            token_type="ApiKey",
            headers={header: cred.token},
        )

    def _auth_web_ntlm(self, cred: AuthCredential) -> AuthSession:
        """NTLM auth via curl --ntlm."""
        if not cred.url:
            return self._missing_config(cred, "url")
        if not cred.username:
            return self._missing_config(cred, "username")

        user = f"{cred.domain}\\\\{cred.username}" if cred.domain else cred.username
        cmd = (
            f"curl -s -o /dev/null -w \"%{{http_code}}\" "
            f"--ntlm -u \"{user}:{cred.password}\" "
            f"\"{cred.url}\" --max-time 15"
        )
        result = self._run_command(cmd)
        status_code = result["stdout"].strip()

        if status_code in ("200", "301", "302"):
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.SUCCESS.value,
            )
        else:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"NTLM auth rejected (HTTP {status_code})",
            )

    def _auth_oauth2_password(self, cred: AuthCredential) -> AuthSession:
        """OAuth2 password grant flow."""
        if not cred.url:
            return self._missing_config(cred, "url (token endpoint)")
        if not cred.username:
            return self._missing_config(cred, "username")
        if not cred.password:
            return self._missing_config(cred, "password")

        post_data = (
            f"grant_type=password&username={cred.username}&password={cred.password}"
        )
        if cred.client_id:
            post_data += f"&client_id={cred.client_id}"
        if cred.client_secret:
            post_data += f"&client_secret={cred.client_secret}"
        if cred.scope:
            post_data += f"&scope={cred.scope}"

        return self._exchange_token(cred, post_data)

    def _auth_oauth2_client_credentials(self, cred: AuthCredential) -> AuthSession:
        """OAuth2 client_credentials grant flow."""
        if not cred.url:
            return self._missing_config(cred, "url (token endpoint)")
        if not cred.client_id:
            return self._missing_config(cred, "client_id")

        post_data = (
            f"grant_type=client_credentials&client_id={cred.client_id}"
        )
        if cred.client_secret:
            post_data += f"&client_secret={cred.client_secret}"
        if cred.scope:
            post_data += f"&scope={cred.scope}"

        return self._exchange_token(cred, post_data)

    # ─── Keycloak Auth Handlers ─────────────────────────────────────────

    def _auth_keycloak_password(self, cred: AuthCredential) -> AuthSession:
        """
        Keycloak OAuth2 password grant.
        URL should be the Keycloak token endpoint:
        https://keycloak.example.com/realms/myrealm/protocol/openid-connect/token
        """
        if not cred.url:
            return self._missing_config(cred, "url (Keycloak token endpoint)")
        if not cred.username or not cred.password:
            return self._missing_config(cred, "username and password")
        if not cred.client_id:
            return self._missing_config(cred, "client_id")

        post_data = (
            f"grant_type=password&username={cred.username}&password={cred.password}"
            f"&client_id={cred.client_id}"
        )
        if cred.client_secret:
            post_data += f"&client_secret={cred.client_secret}"
        if cred.scope:
            post_data += f"&scope={cred.scope}"

        return self._exchange_token(cred, post_data)

    def _auth_keycloak_client_credentials(self, cred: AuthCredential) -> AuthSession:
        """Keycloak client_credentials grant (service-to-service)."""
        if not cred.url:
            return self._missing_config(cred, "url (Keycloak token endpoint)")
        if not cred.client_id:
            return self._missing_config(cred, "client_id")

        post_data = (
            f"grant_type=client_credentials&client_id={cred.client_id}"
        )
        if cred.client_secret:
            post_data += f"&client_secret={cred.client_secret}"
        if cred.scope:
            post_data += f"&scope={cred.scope}"

        return self._exchange_token(cred, post_data)

    def _auth_keycloak_oidc(self, cred: AuthCredential) -> AuthSession:
        """
        Keycloak OIDC — same as password grant but with OIDC scope.
        The scope 'openid' is added automatically.
        """
        if not cred.scope:
            cred.scope = "openid profile email"
        return self._auth_keycloak_password(cred)

    # ─── Active Directory Handlers ──────────────────────────────────────

    def _auth_ad_ldap_bind(self, cred: AuthCredential) -> AuthSession:
        """
        AD authentication via LDAP bind.
        Uses ldapsearch to verify credentials.
        """
        if not cred.ldap_server and not cred.domain:
            return self._missing_config(cred, "ldap_server or domain")
        if not cred.username:
            return self._missing_config(cred, "username")

        server = cred.ldap_server or f"ldap://{cred.domain}"
        port = cred.ldap_port or 389
        user_dn = f"{cred.domain}\\{cred.username}" if cred.domain else cred.username
        base_dn = cred.ldap_base_dn or self._infer_base_dn(cred.domain)
        tls_flag = "-ZZ" if cred.ldap_use_tls else ""

        cmd = (
            f"ldapsearch -x {tls_flag} -H {server}:{port} "
            f"-D \"{user_dn}\" -w '{cred.password}' "
            f"-b \"{base_dn}\" \"(sAMAccountName={cred.username})\" dn "
            f"2>&1 | head -5"
        )
        result = self._run_command(cmd, timeout=15)

        # ldapsearch exit code 0 = success, 49 = invalid credentials
        if result["exit_code"] == 0:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.SUCCESS.value,
                raw_response=result["stdout"][:300],
            )
        elif "invalid credentials" in result["stdout"].lower() or result["exit_code"] == 49:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error="AD LDAP bind failed: invalid credentials",
                raw_response=result["stdout"][:300],
            )
        else:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"AD LDAP bind failed: {result['stderr'] or result['stdout'][:200]}",
                raw_response=result["stdout"][:300],
            )

    def _auth_ad_kerberos(self, cred: AuthCredential) -> AuthSession:
        """
        AD Kerberos authentication. Uses kinit to get a TGT.
        Requires krb5-configured host or explicit realm/KDC.
        """
        if not cred.username:
            return self._missing_config(cred, "username")
        if not cred.realm and not cred.domain:
            return self._missing_config(cred, "realm or domain")

        realm = cred.realm or cred.domain.upper()
        principal = f"{cred.username}@{realm}"

        # If KDC specified, set it for this command
        env = os.environ.copy()
        if cred.kdc:
            env["KRB5_KDC"] = cred.kdc
        if cred.realm:
            env["KRB5_REALM"] = cred.realm

        # Use keytab if provided, otherwise password
        if cred.keytab_path and Path(cred.keytab_path).exists():
            cmd = f"kinit -k -t {cred.keytab_path} {principal}"
            result = self._run_command(cmd, timeout=15, env=env)
        else:
            # Use expect-like approach with kinit
            # kinit reads password from stdin
            cmd = f"echo '{cred.password}' | kinit {principal}"
            result = self._run_command(cmd, timeout=15, env=env)

        if result["exit_code"] == 0:
            # Verify TGT with klist
            verify = self._run_command("klist 2>&1 | head -10", timeout=10, env=env)
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.SUCCESS.value,
                raw_response=verify["stdout"][:300],
            )
        else:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"Kerberos kinit failed: {result['stderr'] or result['stdout'][:200]}",
                raw_response=result["stdout"][:300],
            )

    def _auth_ad_ntlm(self, cred: AuthCredential) -> AuthSession:
        """AD NTLM auth — verify via curl --ntlm against a URL."""
        if not cred.url:
            return self._missing_config(cred, "url")
        return self._auth_web_ntlm(cred)

    # ─── LDAP Handlers ──────────────────────────────────────────────────

    def _auth_ldap_simple(self, cred: AuthCredential) -> AuthSession:
        """LDAP simple bind authentication."""
        if not cred.ldap_server:
            return self._missing_config(cred, "ldap_server")
        if not cred.username:
            return self._missing_config(cred, "username")

        server = cred.ldap_server
        port = cred.ldap_port or 389
        tls_flag = "-ZZ" if cred.ldap_use_tls else ""
        base_dn = cred.ldap_base_dn or ""
        filter_str = cred.ldap_search_filter.replace("{username}", cred.username) or "(objectClass=*)"

        cmd = (
            f"ldapsearch -x {tls_flag} -H {server}:{port} "
            f"-D \"{cred.username}\" -w '{cred.password}' "
            f"-b \"{base_dn}\" \"{filter_str}\" dn 2>&1 | head -5"
        )
        result = self._run_command(cmd, timeout=15)

        if result["exit_code"] == 0:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.SUCCESS.value,
                raw_response=result["stdout"][:300],
            )
        elif result["exit_code"] == 49 or "invalid credentials" in result["stdout"].lower():
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error="LDAP simple bind: invalid credentials",
            )
        else:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"LDAP bind failed: {result['stderr'] or result['stdout'][:200]}",
            )

    def _auth_ldap_sasl(self, cred: AuthCredential) -> AuthSession:
        """
        LDAP SASL authentication. Supports DIGEST-MD5 and GSSAPI.
        """
        if not cred.ldap_server:
            return self._missing_config(cred, "ldap_server")

        server = cred.ldap_server
        port = cred.ldap_port or 389

        # Default to DIGEST-MD5
        sasl_mech = cred.form_extra_fields.get("sasl_mech", "DIGEST-MD5")

        cmd = (
            f"ldapsearch -Y {sasl_mech} -H {server}:{port} "
            f"-U \"{cred.username}\" -w '{cred.password}' "
            f"-b \"{cred.ldap_base_dn}\" \"(objectClass=*)\" dn 2>&1 | head -5"
        )
        result = self._run_command(cmd, timeout=15)

        if result["exit_code"] == 0:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.SUCCESS.value,
                raw_response=result["stdout"][:300],
            )
        else:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"LDAP SASL ({sasl_mech}) failed: {result['stderr'] or result['stdout'][:200]}",
            )

    def _auth_ldap_anonymous(self, cred: AuthCredential) -> AuthSession:
        """LDAP anonymous bind."""
        if not cred.ldap_server:
            return self._missing_config(cred, "ldap_server")

        server = cred.ldap_server
        port = cred.ldap_port or 389
        base_dn = cred.ldap_base_dn or ""

        cmd = (
            f"ldapsearch -x -H {server}:{port} "
            f"-b \"{base_dn}\" \"(objectClass=*)\" dn 2>&1 | head -5"
        )
        result = self._run_command(cmd, timeout=15)

        if result["exit_code"] == 0:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.SUCCESS.value,
                raw_response=result["stdout"][:300],
            )
        else:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"LDAP anonymous bind failed: {result['stderr'] or result['stdout'][:200]}",
            )

    # ─── Database Handlers ──────────────────────────────────────────────

    def _auth_db_mysql(self, cred: AuthCredential) -> AuthSession:
        """MySQL authentication check."""
        if not cred.db_host:
            return self._missing_config(cred, "db_host")
        port = cred.db_port or 3306

        cmd = (
            f"mysql -h {cred.db_host} -P {port} "
            f"-u \"{cred.username}\" -p'{cred.password}' "
            f"-e \"SELECT 1\" 2>&1"
        )
        result = self._run_command(cmd, timeout=15)

        if result["exit_code"] == 0 and "1" in result["stdout"]:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.SUCCESS.value,
            )
        else:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"MySQL auth failed: {result['stderr'] or result['stdout'][:200]}",
            )

    def _auth_db_postgresql(self, cred: AuthCredential) -> AuthSession:
        """PostgreSQL authentication check."""
        if not cred.db_host:
            return self._missing_config(cred, "db_host")
        port = cred.db_port or 5432
        db = cred.db_name or "postgres"

        env = os.environ.copy()
        env["PGPASSWORD"] = cred.password
        cmd = (
            f"psql -h {cred.db_host} -p {port} -U \"{cred.username}\" "
            f"-d {db} -c \"SELECT 1\" 2>&1"
        )
        result = self._run_command(cmd, timeout=15, env=env)

        if result["exit_code"] == 0:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.SUCCESS.value,
            )
        else:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"PostgreSQL auth failed: {result['stderr'] or result['stdout'][:200]}",
            )

    def _auth_db_mssql(self, cred: AuthCredential) -> AuthSession:
        """MSSQL authentication check via sqlcmd or impacket."""
        if not cred.db_host:
            return self._missing_config(cred, "db_host")
        port = cred.db_port or 1433

        # Try sqlcmd first, fall back to impacket's mssqlclient
        cmd = (
            f"sqlcmd -S {cred.db_host},{port} -U \"{cred.username}\" "
            f"-P '{cred.password}' -Q \"SELECT 1\" -l 10 2>&1"
        )
        result = self._run_command(cmd, timeout=15)

        if result["exit_code"] == 0:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.SUCCESS.value,
            )

        # Fallback: impacket mssqlclient
        cmd2 = (
            f"python3 -c \"from impacket.mssql import MSSQL; "
            f"print('ok')\" 2>&1"
        )
        result2 = self._run_command(cmd2, timeout=10)
        if "ok" in result2["stdout"]:
            cmd3 = (
                f"impacket-mssqlclient '{cred.username}:{cred.password}@{cred.db_host}' "
                f"-port {port} -windows-auth 2>&1 | head -3"
            )
            result3 = self._run_command(cmd3, timeout=15)
            if result3["exit_code"] == 0 and "impersonate" not in result3["stdout"].lower():
                return AuthSession(
                    target_id=cred.target_id,
                    method=cred.method,
                    status=AuthStatus.SUCCESS.value,
                )

        return AuthSession(
            target_id=cred.target_id,
            method=cred.method,
            status=AuthStatus.FAILED.value,
            error=f"MSSQL auth failed: {result['stderr'] or result['stdout'][:200]}",
        )

    # ─── SSH Handlers ───────────────────────────────────────────────────

    def _auth_ssh_password(self, cred: AuthCredential) -> AuthSession:
        """SSH password authentication via sshpass."""
        if not cred.url and not cred.db_host:
            return self._missing_config(cred, "url or db_host (SSH host)")
        host = cred.url or cred.db_host
        port = cred.ssh_port or 22

        cmd = (
            f"sshpass -p '{cred.password}' ssh -o StrictHostKeyChecking=no "
            f"-o ConnectTimeout=10 -p {port} "
            f"{cred.username}@{host} 'echo OK' 2>&1"
        )
        result = self._run_command(cmd, timeout=20)

        if result["exit_code"] == 0 and "OK" in result["stdout"]:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.SUCCESS.value,
            )
        else:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"SSH auth failed: {result['stderr'] or result['stdout'][:200]}",
            )

    def _auth_ssh_key(self, cred: AuthCredential) -> AuthSession:
        """SSH key-based authentication."""
        if not cred.ssh_key_path:
            return self._missing_config(cred, "ssh_key_path")
        if not cred.url and not cred.db_host:
            return self._missing_config(cred, "url or db_host (SSH host)")
        if not Path(cred.ssh_key_path).exists():
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"SSH key not found: {cred.ssh_key_path}",
            )

        host = cred.url or cred.db_host
        port = cred.ssh_port or 22

        cmd = (
            f"ssh -i {cred.ssh_key_path} -o StrictHostKeyChecking=no "
            f"-o ConnectTimeout=10 -p {port} "
            f"{cred.username}@{host} 'echo OK' 2>&1"
        )
        result = self._run_command(cmd, timeout=20)

        if result["exit_code"] == 0 and "OK" in result["stdout"]:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.SUCCESS.value,
            )
        else:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"SSH key auth failed: {result['stderr'] or result['stdout'][:200]}",
            )

    # ─── Token Exchange (shared by OAuth2/Keycloak) ─────────────────────

    def _exchange_token(self, cred: AuthCredential,
                        post_data: str) -> AuthSession:
        """
        Exchange credentials for OAuth2/OIDC token via curl.
        Parses JSON response for access_token, refresh_token, expires_in.
        """
        cmd = (
            f"curl -s -X POST \"{cred.url}\" "
            f"-d \"{post_data}\" "
            f"-H \"Content-Type: application/x-www-form-urlencoded\" "
            f"-H \"User-Agent: Chimeras/3.3\" "
            f"--max-time 30"
        )
        result = self._run_command(cmd)

        if not result["success"]:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"Token endpoint request failed: {result['stderr'][:200]}",
                raw_response=result["stdout"][:500],
            )

        try:
            token_data = json.loads(result["stdout"])
        except json.JSONDecodeError:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error="Token endpoint returned non-JSON response",
                raw_response=result["stdout"][:500],
            )

        if "error" in token_data:
            error_desc = token_data.get("error_description", token_data["error"])
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error=f"OAuth2 error: {error_desc}",
                raw_response=result["stdout"][:500],
            )

        access_token = token_data.get("access_token", "")
        if not access_token:
            return AuthSession(
                target_id=cred.target_id,
                method=cred.method,
                status=AuthStatus.FAILED.value,
                error="Token response missing access_token",
                raw_response=result["stdout"][:500],
            )

        # Calculate expiry
        expires_in = token_data.get("expires_in", 0)
        expires_at = ""
        if expires_in:
            exp_dt = datetime.now(timezone.utc).timestamp() + expires_in
            expires_at = datetime.fromtimestamp(exp_dt, tz=timezone.utc).isoformat()

        return AuthSession(
            target_id=cred.target_id,
            method=cred.method,
            status=AuthStatus.SUCCESS.value,
            access_token=access_token,
            token_type=token_data.get("token_type", "Bearer"),
            refresh_token=token_data.get("refresh_token", ""),
            expires_at=expires_at,
            raw_response=result["stdout"][:500],
        )

    # ─── Utilities ──────────────────────────────────────────────────────

    @staticmethod
    def _missing_config(cred: AuthCredential, field_name: str) -> AuthSession:
        return AuthSession(
            target_id=cred.target_id,
            method=cred.method,
            status=AuthStatus.NOT_CONFIGURED.value,
            error=f"Missing required field: {field_name}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _run_command(command: str, timeout: int = 30,
                     env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Execute a shell command and return result dict."""
        import subprocess
        import shlex

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            return {
                "command": command,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "success": False,
            }
        except Exception as e:
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False,
            }

    @staticmethod
    def _parse_set_cookies(response: str) -> Dict[str, str]:
        """Extract cookies from Set-Cookie headers in HTTP response."""
        cookies = {}
        for match in re.finditer(r'[Ss]et-[Cc]ookie:\s*([^;=\r\n]+)=([^;\r\n]+)', response):
            name = match.group(1).strip()
            value = match.group(2).strip()
            cookies[name] = value
        return cookies

    @staticmethod
    def _extract_status_code(response: str) -> Optional[int]:
        """Extract HTTP status code from curl -D output."""
        match = re.search(r'HTTP/[\d.]+\s+(\d+)', response)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _fetch_csrf_token(url: str, csrf_field: str) -> Optional[str]:
        """Fetch a CSRF token from a login page."""
        cmd = f"curl -s \"{url}\" --max-time 10"
        result = AuthManager._run_command(cmd)
        if not result["success"]:
            return None

        # Try common CSRF token patterns
        patterns = [
            f'name="{csrf_field}"[^>]*value="([^"]+)"',
            f'name="{csrf_field}"\\s+value="([^"]+)"',
            f'<meta name="{csrf_field}" content="([^"]+)"',
            f'"{csrf_field}":"([^"]+)"',  # JSON
        ]
        for pattern in patterns:
            match = re.search(pattern, result["stdout"])
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _infer_base_dn(domain: str) -> str:
        """Infer LDAP base DN from domain name.

        Example: corp.local → dc=corp,dc=local
        """
        if not domain:
            return ""
        parts = domain.split(".")
        return ",".join(f"dc={p}" for p in parts)

    def export_status_report(self) -> str:
        """Generate a human-readable auth status report for the engagement."""
        lines = ["# Authentication Status Report", ""]
        lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append("")

        if not self.targets:
            lines.append("No authentication targets configured.")
            return "\n".join(lines)

        for tid, cred in self.targets.items():
            session = self.sessions.get(tid)
            status = session.status if session else "pending"
            icon = "✓" if status == "success" else "✗" if status == "failed" else "◯"
            lines.append(f"## {icon} {tid}")
            lines.append(f"- Method: `{cred.method}`")
            lines.append(f"- Status: **{status}**")
            if session and session.error:
                lines.append(f"- Error: {session.error}")
            if session and session.access_token:
                lines.append("- Token: acquired")
            if session and session.cookies:
                lines.append(f"- Cookies: {len(session.cookies)} acquired")
            if session and session.expires_at:
                lines.append(f"- Expires: {session.expires_at}")
            lines.append("")

        return "\n".join(lines)


# ─── Module-level helpers ───────────────────────────────────────────────

def load_auth_from_env() -> Dict[str, Any]:
    """
    Load auth configuration from environment variables.
    Variables: CHIMERAS_AUTH_<TARGET_ID>_<FIELD>

    Target IDs may contain underscores. The parser identifies the field
    name by matching against known AuthCredential fields.

    Example:
        CHIMERAS_AUTH_WEB_PORTAL_METHOD=web_form
        CHIMERAS_AUTH_WEB_PORTAL_URL=https://target.com/login
        CHIMERAS_AUTH_WEB_PORTAL_USERNAME=testuser
        CHIMERAS_AUTH_WEB_PORTAL_PASSWORD=testpass

    Returns auth config dict suitable for AuthManager.
    """
    # Known field names (from AuthCredential)
    known_fields = {
        "method", "username", "password", "domain", "realm",
        "url", "token", "token_type", "refresh_token", "token_header",
        "token_prefix", "client_id", "client_secret", "scope", "grant_type",
        "ldap_server", "ldap_port", "ldap_use_tls", "ldap_base_dn",
        "ldap_search_filter", "kdc", "keytab_path",
        "ssh_key_path", "ssh_port", "db_host", "db_port", "db_name",
        "form_username_field", "form_password_field", "form_csrf_field",
        "description",
    }

    targets: Dict[str, Dict[str, Any]] = {}
    prefix = "CHIMERAS_AUTH_"

    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        remainder = key[len(prefix):]
        remainder_upper = remainder.upper()
        # Find the field name by checking known fields from longest to shortest
        # to handle fields like "ldap_search_filter" vs "ldap_server"
        matched_field = None
        matched_target = None
        for field in sorted(known_fields, key=len, reverse=True):
            field_upper = field.upper()
            if remainder_upper.endswith("_" + field_upper) or remainder_upper == field_upper:
                # Extract target_id (everything before the field)
                if remainder_upper == field_upper:
                    matched_target = ""
                    matched_field = field
                else:
                    matched_target = remainder[:-(len(field) + 1)].lower()
                    matched_field = field
                break

        if matched_field is None:
            continue

        target_id = matched_target
        if target_id not in targets:
            targets[target_id] = {"target_id": target_id}
        targets[target_id][matched_field] = value

    return {"targets": list(targets.values()) if targets else []}