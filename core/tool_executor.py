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
import time
import re
from typing import Dict, Any, Optional, List
from pathlib import Path

from core.scope import (
    ScopeEnforcer, ScopeViolation, TargetScopeViolation,
    ShellInjectionViolation, DestructiveCommandViolation,
)


class ToolExecutor:
    """Executes shell commands (Kali tools) and captures output.

    v2: Scope enforcement now includes target validation and shell
    metacharacter injection checks. The executor receives the mission
    scope and bot name so it can validate targets before execution.
    """

    def __init__(self, timeout: int = 120, workdir: Optional[str] = None,
                 bot_name: str = "", mission_scope: str = "",
                 internal_scope: str = "", roe: str = ""):
        self.timeout = timeout
        self.workdir = workdir or "/tmp"
        self.bot_name = bot_name
        self.mission_scope = mission_scope
        self.internal_scope = internal_scope
        self.roe = roe

    @staticmethod
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

        # v2: Full scope enforcement — destructive/DoS, injection, category, target
        if self.bot_name:
            try:
                ScopeEnforcer.enforce(
                    self.bot_name, command,
                    mission_scope=self.mission_scope or None,
                    internal_scope=self.internal_scope or None,
                    roe=self.roe or None,
                )
            except DestructiveCommandViolation as e:
                return {
                    "command": command,
                    "exit_code": -2,
                    "stdout": "",
                    "stderr": str(e),
                    "duration_sec": 0,
                    "success": False,
                    "scope_blocked": True,
                    "violation_type": "destructive_or_dos_command",
                }
            except ShellInjectionViolation as e:
                return {
                    "command": command,
                    "exit_code": -2,
                    "stdout": "",
                    "stderr": str(e),
                    "duration_sec": 0,
                    "success": False,
                    "scope_blocked": True,
                    "violation_type": "shell_injection",
                }
            except TargetScopeViolation as e:
                return {
                    "command": command,
                    "exit_code": -2,
                    "stdout": "",
                    "stderr": str(e),
                    "duration_sec": 0,
                    "success": False,
                    "scope_blocked": True,
                    "violation_type": "target_out_of_scope",
                }
            except ScopeViolation as e:
                return {
                    "command": command,
                    "exit_code": -2,
                    "stdout": "",
                    "stderr": str(e),
                    "duration_sec": 0,
                    "success": False,
                    "scope_blocked": True,
                    "violation_type": "tool_category",
                }

        command = self._sanitize_command(command)
        start = time.time()

        try:
            result = subprocess.run(
                command,
                shell=True,
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