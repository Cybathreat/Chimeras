"""
Chimeras v1.0 — Tool Executor

Executes Kali Linux tools via subprocess. Captures stdout/stderr.
No mock data. Real tools, real output.
"""

import subprocess
import shlex
import time
from typing import Dict, Any, Optional, List
from pathlib import Path


class ToolExecutor:
    """Executes shell commands (Kali tools) and captures output."""

    def __init__(self, timeout: int = 120, workdir: Optional[str] = None):
        self.timeout = timeout
        self.workdir = workdir or "/tmp"

    @staticmethod
    def _sanitize_command(command: str) -> str:
        """Strip output-file flags that cause tools to fail when paths don't exist.
        The executor captures stdout directly, so -oN/-oX/-oG/-oS are redundant.
        Also caps nikto maxtime to 120s for demo reliability."""
        import re
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
        """
        t = timeout or self.timeout
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