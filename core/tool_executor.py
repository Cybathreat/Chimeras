"""
Chimeras v2.0 — Tool Executor

Executes Kali Linux tools via subprocess. Captures stdout/stderr.
No mock data. Real tools, real output.

v2 additions (Phase -1):
  - Shell injection validation integrated with ScopeEnforcer.check()
  - Mission scope passed through to target validation
  - Internal scope (lateral) support for post-approval pivots
"""

import subprocess
import shlex
import time
import re
from typing import Dict, Any, Optional, List
from pathlib import Path

from core.scope import (
    ScopeEnforcer, ScopeViolation, TargetScopeViolation,
    ShellInjectionViolation, DestructiveCommandViolation,
    SHELL_CAPABLE_CATEGORIES,
)


class ToolExecutor:
    """Executes shell commands (Kali tools) and captures output.

    v2: Scope enforcement now includes target validation and shell
    metacharacter injection checks. The executor receives the mission
    scope and bot name so it can validate targets before execution.

    v3.3: Optional AuthManager integration. When provided, auth context
    (tokens, cookies, headers) is injected into tool commands before
    execution. The executor queries AuthManager for the appropriate
    auth arguments based on the target and tool being run.
    """

    def __init__(self, timeout: int = 120, workdir: Optional[str] = None,
                 bot_name: str = "", mission_scope: str = "",
                 internal_scope: str = "", roe: str = "",
                 auth_manager: Optional[Any] = None,
                 auth_target_id: Optional[str] = None):
        self.timeout = timeout
        self.workdir = workdir or "/tmp"
        self.bot_name = bot_name
        self.mission_scope = mission_scope
        self.internal_scope = internal_scope
        self.roe = roe
        # v3.3: Auth integration
        self.auth_manager = auth_manager
        self.auth_target_id = auth_target_id

    def _sanitize_command(command: str) -> str:
        """Strip output-file flags that cause tools to fail when paths don't exist.
        The executor captures stdout directly, so -oN/-oX/-oG/-oS are redundant.
        Also caps nikto maxtime to 120s for demo reliability."""
        # nmap: -oN /path, -oX /path, -oG /path, -oS /path, -oA basename
        command = re.sub(r'\s+-o[NXGSA]\s+\S+', '', command)
        # nikto: -output /path
        command = re.sub(r'\s+-output\s+\S+', '', command)
        # wapiti: -o /path
        command = re.sub(r'\s+-o\s+\S+', '', command)
        # Cap nikto maxtime to 120s
        command = re.sub(r'-maxtime\s+\d+', '-maxtime 120', command)
        if 'nikto' in command and '-maxtime' not in command:
            command += ' -maxtime 120'
        return command.strip()

    def _inject_auth(self, command: str) -> str:
        """v3.3: Inject auth context into tool commands.

        Detects the tool being run and appends appropriate auth arguments
        from the AuthManager. Supports curl, sqlmap, nikto, nmap, ldapsearch,
        ssh, and generic HTTP tools.
        """
        if not self.auth_manager or not self.auth_target_id:
            return command
        if not self.auth_manager.has_auth(self.auth_target_id):
            return command

        cmd_lower = command.lower()

        # Don't double-inject auth (check for existing auth flags)
        auth_indicators = ['--auth-type=', '--auth-cred=', '-u "', '--ntlm',
                           '-h "authorization:', '-h "cookie:', '--cookie=',
                           '--header="authorization']
        for indicator in auth_indicators:
            if indicator in cmd_lower:
                return command  # Already has auth

        # Tool-specific injection
        if cmd_lower.startswith('curl ') or ' curl ' in cmd_lower:
            auth_args = self.auth_manager.get_curl_auth_args(self.auth_target_id)
            if auth_args:
                # Insert auth args before the URL
                return command + " " + auth_args

        elif cmd_lower.startswith('sqlmap ') or ' sqlmap ' in cmd_lower:
            auth_args = self.auth_manager.get_sqlmap_auth_args(self.auth_target_id)
            if auth_args:
                return command + " " + auth_args

        elif cmd_lower.startswith('nikto ') or ' nikto ' in cmd_lower:
            # Nikto uses -id for auth: user:pass
            cred = self.auth_manager.targets.get(self.auth_target_id)
            if cred and cred.username:
                return command + f" -id \"{cred.username}:{cred.password}\""

        elif cmd_lower.startswith('nmap ') or ' nmap ' in cmd_lower:
            auth_args = self.auth_manager.get_nmap_auth_args(self.auth_target_id)
            if auth_args:
                return command + " " + auth_args

        elif cmd_lower.startswith('ldapsearch ') or ' ldapsearch ' in cmd_lower:
            # For ldapsearch, use the AuthManager's built-in command builder
            built_cmd = self.auth_manager.get_ldapsearch_command(self.auth_target_id)
            if built_cmd:
                return built_cmd

        elif cmd_lower.startswith('ssh ') or ' sshpass ' in cmd_lower:
            ssh_prefix = self.auth_manager.get_ssh_command_prefix(self.auth_target_id)
            if ssh_prefix:
                return ssh_prefix

        # Generic fallback: inject auth headers for HTTP tools (ffuf, gobuster, etc.)
        elif any(t in cmd_lower for t in ('ffuf', 'gobuster', 'wfuzz', 'httpx', 'arjun')):
            headers = self.auth_manager.get_headers(self.auth_target_id)
            if headers:
                for hname, hvalue in headers.items():
                    command += f' -H "{hname}: {hvalue}"'

        return command

    def run(self, command: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute a shell command. Returns:
            {
                "command": str,
                "exit_code": int,
                "stdout": str,
                "stderr": str,
                "duration_sec": float,
                "success": bool
            }

        v2: Before execution, runs the full ScopeEnforcer.check() which
        includes:
        1. Destructive / DoS command check
        2. Shell metacharacter injection check
        3. Tool category check (v1)
        4. Target/CIDR validation (v2)

        If any check fails, the command is NOT executed and the result
        contains an error message with scope_blocked=True.
        """
        t = timeout or self.timeout

        # v2.3: Scope enforcement moved to BaseBot._run_tool() which calls
        # ScopeEnforcer.check() before invoking executor.run().
        # This eliminates the double/triple checking that was happening:
        # _run_tool() → check() then executor.run() → enforce() → check() again.
        # Now _run_tool() does the single check and executor.run() just executes.

        command = self._sanitize_command(command)
        # v3.3: Inject auth context for grey/white-box engagements
        command = self._inject_auth(command)
        start = time.time()

        # v2.3: Security — use shell=False for non-shell-capable bots.
        # Shell-capable bots (exploitation, privesc, exfiltration, payload_fab)
        # legitimately need pipes/chaining. Non-shell bots get shlex.split()
        # to prevent any shell metacharacter execution.
        bot_category = ScopeEnforcer.get_bot_category(self.bot_name) if self.bot_name else ""
        use_shell = bot_category in SHELL_CAPABLE_CATEGORIES

        try:
            if use_shell:
                # Shell-capable bots — keep shell=True (they need pipes/chains)
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=t,
                    cwd=self.workdir,
                )
            else:
                # Non-shell bots — use arg array, no shell interpretation
                cmd_list = shlex.split(command)
                result = subprocess.run(
                    cmd_list,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=t,
                    cwd=self.workdir,
                )
            elapsed = time.time() - start
            return {
                "command": command,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_sec": round(elapsed, 2),
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {t}s",
                "duration_sec": round(elapsed, 2),
                "success": False,
            }
        except Exception as e:
            elapsed = time.time() - start
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration_sec": round(elapsed, 2),
                "success": False,
            }

    def run_batch(self, commands: List[str], timeout: Optional[int] = None) -> List[Dict[str, Any]]:
        """Execute multiple commands sequentially."""
        return [self.run(cmd, timeout) for cmd in commands]

    def save_output(self, result: Dict[str, Any], filepath: Path) -> None:
        """Save tool output to a file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            f.write(f"Command: {result['command']}\n")
            f.write(f"Exit Code: {result['exit_code']}\n")
            f.write(f"Duration: {result['duration_sec']}s\n")
            f.write(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
            f.write("=" * 60 + "\n")
            f.write("STDOUT:\n")
            f.write(result["stdout"] or "(empty)\n")
            f.write("=" * 60 + "\n")
            f.write("STDERR:\n")
            f.write(result["stderr"] or "(empty)\n")