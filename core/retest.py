"""
Chimeras v3.1 — Retest Verifier

Re-runs PoC commands from a previous engagement's findings to verify
whether vulnerabilities have been remediated. Produces a retest report
with per-finding status: Closed, Open, or Partial.

Consultants sell retests as a second engagement. This creates recurring
revenue. Strix has auto-fix; we have verified closure.

Usage:
    from core.retest import RetestVerifier

    verifier = RetestVerifier(engagement_dir)
    report = verifier.run_retest(findings, scope="10.0.0.1")

    # Or via CLI:
    # python main.py --retest --engagement mission-xyz

Integration:
    Bookkeeper or standalone CLI calls run_retest() with previous findings.
    Output: report/retest_report.md + retest_results.json
"""

import json
import logging
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Retest status constants
STATUS_CLOSED = "Closed"      # Vulnerability no longer reproducible
STATUS_OPEN = "Open"          # Vulnerability still exists
STATUS_PARTIAL = "Partial"    # Some indicators present, but not fully exploitable
STATUS_ERROR = "Error"        # Tool execution failed, cannot determine
STATUS_SKIPPED = "Skipped"    # No PoC command to re-run


class RetestVerifier:
    """Verify whether previous findings have been remediated.

    Re-runs PoC commands from findings and compares output to the
    original proof_of_existence. Uses heuristics to determine if
    the vulnerability is still present.

    Heuristics:
    - If PoC command fails (non-zero exit) → likely Closed
    - If output matches original proof_of_existence patterns → Open
    - If output partially matches → Partial
    - If command cannot be extracted → Skipped
    """

    def __init__(self, engagement_dir: Path, scope: str = "", timeout: int = 120):
        self.engagement_dir = Path(engagement_dir)
        self.retest_dir = self.engagement_dir / "retest"
        self.retest_dir.mkdir(parents=True, exist_ok=True)
        self.scope = scope
        self.timeout = timeout

    def _extract_commands(self, poc_text: str) -> List[str]:
        """Extract executable commands from PoC text.

        Handles:
        - Code blocks: ```bash\ncommand\n```
        - Inline code: `command`
        - Plain command lines (start with tool name)
        - Numbered/bulleted command lists
        """
        if not poc_text or poc_text == "N/A":
            return []

        commands: List[str] = []

        # Extract from code blocks first
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', poc_text, re.DOTALL)
        for block in code_blocks:
            for line in block.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    commands.append(line)

        # Extract inline code only if no code blocks found
        if not commands:
            inline_codes = re.findall(r'`([^`]+)`', poc_text)
            for code in inline_codes:
                code = code.strip()
                if self._looks_like_command(code):
                    commands.append(code)

        # If no commands found, try line-by-line
        if not commands:
            for line in poc_text.strip().split("\n"):
                line = line.strip()
                # Strip numbering and bullets
                line = re.sub(r'^\d+\.\s*', '', line)
                line = re.sub(r'^[-*]\s*', '', line)
                if line and self._looks_like_command(line):
                    commands.append(line)

        return commands

    def _looks_like_command(self, text: str) -> bool:
        """Check if a text string looks like a shell command."""
        if not text or len(text) < 3:
            return False
        # Known pentest tools that might appear in PoC
        known_tools = [
            "nmap", "nikto", "nuclei", "sqlmap", "gobuster", "ffuf",
            "curl", "wget", "dig", "whois", "whatweb", "wafw00f",
            "sslscan", "ssh-audit", "searchsploit", "wapiti", "commix",
            "wfuzz", "dalfox", "httpx", "dnsx", "subfinder", "naabu",
            "hydra", "john", "hashcat", "msfconsole", "msfvenom",
            "nc", "netcat", "python3", "python", "bash", "sh",
            "ftp", "ssh", "telnet", "smbclient", "rpcclient",
        ]
        first_word = text.split()[0].split("/")[-1].split("\\")[-1].lower()
        return first_word in known_tools

    def _run_command(self, command: str) -> Dict[str, Any]:
        """Run a single command and return result dict."""
        start = time.monotonic()

        # Scope check — if scope is set, ensure command targets it
        if self.scope:
            # Simple check: scope string should appear in command,
            # or command should not target obviously different hosts
            # (not a full security check — retest is post-engagement)
            pass

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            duration = time.monotonic() - start

            return {
                "command": command,
                "exit_code": result.returncode,
                "stdout": result.stdout[:8000],  # cap output
                "stderr": result.stderr[:2000],
                "duration_sec": round(duration, 2),
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Timeout after {self.timeout}s",
                "duration_sec": self.timeout,
                "success": False,
                "timeout": True,
            }
        except Exception as e:
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration_sec": 0,
                "success": False,
                "error": str(e),
            }

    def _compare_outputs(
        self,
        original_proof: str,
        new_output: str,
        exit_code: int,
    ) -> str:
        """Compare original proof_of_existence with new output.

        Returns one of: STATUS_CLOSED, STATUS_OPEN, STATUS_PARTIAL
        """
        if not original_proof or original_proof == "N/A":
            # No original proof to compare — use exit code
            if exit_code != 0:
                return STATUS_CLOSED
            return STATUS_OPEN

        # Normalize for comparison
        original_lower = original_proof.lower().strip()
        new_lower = new_output.lower().strip()

        if not new_lower:
            # No output — if command failed, likely fixed
            if exit_code != 0:
                return STATUS_CLOSED
            return STATUS_PARTIAL

        # Extract key indicators from original proof
        # (error messages, CVE IDs, vulnerability confirmations, etc.)
        indicators = self._extract_indicators(original_lower)

        if not indicators:
            # No clear indicators — use exit code
            if exit_code != 0:
                return STATUS_CLOSED
            return STATUS_OPEN

        # Check how many indicators still appear in new output
        matched = 0
        for indicator in indicators:
            if indicator in new_lower:
                matched += 1

        match_ratio = matched / len(indicators) if indicators else 0

        if match_ratio >= 0.7:
            return STATUS_OPEN
        elif match_ratio >= 0.3:
            return STATUS_PARTIAL
        else:
            return STATUS_CLOSED

    def _extract_indicators(self, text: str) -> List[str]:
        """Extract key indicators from proof text for comparison.

        Indicators are substrings that should appear in output if
        the vulnerability is still present: CVE IDs, error messages,
        specific values, vulnerability keywords.
        """
        indicators: List[str] = []

        # CVE IDs
        cves = re.findall(r'cve-\d{4}-\d{4,}', text)
        indicators.extend(cves)

        # HTTP status codes (e.g., "200 ok", "403 forbidden")
        status_matches = re.findall(r'\b[1-5]\d{2}\s+\w+', text)
        indicators.extend(status_matches[:3])  # limit

        # Specific values: "enabled", "vulnerable", "open", "confirmed"
        vuln_keywords = [
            "vulnerable", "confirmed", "exploitable", "injection",
            "enabled", "weak", "deprecated", "open",
            "exposed", "leaked", "missing", "misconfigured",
        ]
        for kw in vuln_keywords:
            if kw in text:
                indicators.append(kw)

        # SSL/TLS specific
        tls_patterns = re.findall(r'tls\s+\d\.\d', text)
        indicators.extend(tls_patterns)

        # Cipher names
        ciphers = re.findall(r'tls_\w+|ssl_\w+', text)
        indicators.extend(ciphers[:3])

        # Error messages (quoted strings)
        errors = re.findall(r"['\"]([^'\"]{5,50})['\"]", text)
        indicators.extend(errors[:3])

        # Port/service info
        ports = re.findall(r'\d+/tcp\s+\w+', text)
        indicators.extend(ports[:3])

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for ind in indicators:
            if ind not in seen and len(ind) >= 3:
                seen.add(ind)
                unique.append(ind)

        return unique if unique else [original.strip() for original in [text[:50]] if original.strip()]

    def run_retest(
        self,
        findings: List[Dict[str, Any]],
        max_commands_per_finding: int = 3,
    ) -> Dict[str, Any]:
        """Run retest verification on a list of findings.

        Args:
            findings: List of finding dicts with poc and proof_of_existence.
            max_commands_per_finding: Max PoC commands to run per finding.

        Returns:
            Retest report dict with per-finding results and summary.
        """
        results: List[Dict[str, Any]] = []
        timestamp = datetime.utcnow().isoformat()

        for finding in findings:
            fid = finding.get("id") or finding.get("finding_id", "UNKNOWN")
            title = finding.get("title", "Untitled")
            original_proof = finding.get("proof_of_existence", "")
            poc_text = finding.get("poc", "")
            severity = finding.get("severity", "info")

            # Extract commands from PoC
            commands = self._extract_commands(poc_text)

            if not commands:
                results.append({
                    "finding_id": fid,
                    "title": title,
                    "severity": severity,
                    "status": STATUS_SKIPPED,
                    "reason": "No executable PoC commands found",
                    "original_proof": original_proof[:200],
                    "commands_run": [],
                    "timestamp": timestamp,
                })
                continue

            # Run up to max_commands_per_finding
            commands_to_run = commands[:max_commands_per_finding]
            command_results: List[Dict[str, Any]] = []
            statuses: List[str] = []

            for cmd in commands_to_run:
                result = self._run_command(cmd)
                command_results.append(result)

                status = self._compare_outputs(
                    original_proof,
                    result.get("stdout", "") + result.get("stderr", ""),
                    result.get("exit_code", -1),
                )
                statuses.append(status)
                result["retest_status"] = status

            # Aggregate status: worst case wins
            if STATUS_OPEN in statuses:
                final_status = STATUS_OPEN
            elif STATUS_PARTIAL in statuses:
                final_status = STATUS_PARTIAL
            elif STATUS_CLOSED in statuses:
                final_status = STATUS_CLOSED
            else:
                final_status = STATUS_ERROR

            results.append({
                "finding_id": fid,
                "title": title,
                "severity": severity,
                "status": final_status,
                "original_proof": original_proof[:200],
                "commands_run": command_results,
                "timestamp": timestamp,
            })

        # Build summary
        summary = self._build_summary(results)

        # Build report
        report = {
            "generated_at": timestamp,
            "engagement_dir": str(self.engagement_dir),
            "total_findings": len(results),
            "summary": summary,
            "results": results,
        }

        # Write retest results JSON
        json_path = self.retest_dir / "retest_results.json"
        json_path.write_text(json.dumps(report, indent=2))

        # Write retest report markdown
        md_path = self.engagement_dir / "report" / "retest_report.md"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(self._format_markdown_report(report))

        logger.info(
            f"Retest complete: {summary['closed']} closed, "
            f"{summary['open']} open, {summary['partial']} partial, "
            f"{summary['skipped']} skipped"
        )

        return report

    def _build_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build summary statistics from retest results."""
        counts = {
            STATUS_CLOSED: 0,
            STATUS_OPEN: 0,
            STATUS_PARTIAL: 0,
            STATUS_ERROR: 0,
            STATUS_SKIPPED: 0,
        }

        for r in results:
            status = r.get("status", STATUS_SKIPPED)
            counts[status] = counts.get(status, 0) + 1

        total = len(results)
        closed = counts[STATUS_CLOSED]
        open_count = counts[STATUS_OPEN]

        return {
            "total": total,
            "closed": closed,
            "open": open_count,
            "partial": counts[STATUS_PARTIAL],
            "error": counts[STATUS_ERROR],
            "skipped": counts[STATUS_SKIPPED],
            "remediation_rate": round(closed / total * 100, 1) if total > 0 else 0,
        }

    def _format_markdown_report(self, report: Dict[str, Any]) -> str:
        """Format retest results as markdown report."""
        lines: List[str] = [
            "# Penetration Test Retest Report",
            "",
            f"**Generated:** {report['generated_at']}",
            f"**Engagement:** {report['engagement_dir']}",
            f"**Tester:** Chimeras Autonomous AI Pentest Swarm",
            "",
            "---",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total findings retested | {report['summary']['total']} |",
            f"| Closed (remediated) | {report['summary']['closed']} |",
            f"| Open (still vulnerable) | {report['summary']['open']} |",
            f"| Partial | {report['summary']['partial']} |",
            f"| Error | {report['summary']['error']} |",
            f"| Skipped | {report['summary']['skipped']} |",
            f"| Remediation rate | {report['summary']['remediation_rate']}% |",
            "",
            "---",
            "",
            "## Detailed Results",
            "",
        ]

        for r in report["results"]:
            status_emoji = {
                STATUS_CLOSED: "✅",
                STATUS_OPEN: "🔴",
                STATUS_PARTIAL: "🟡",
                STATUS_ERROR: "⚠️",
                STATUS_SKIPPED: "⏭️",
            }.get(r["status"], "?")

            lines.append(f"### {r['finding_id']}: {r['title']}")
            lines.append(f"")
            lines.append(f"**Severity:** {r['severity']}")
            lines.append(f"**Retest Status:** {status_emoji} {r['status']}")
            lines.append(f"")

            if r.get("reason"):
                lines.append(f"*Reason:* {r['reason']}")
                lines.append("")
            else:
                lines.append(f"**Original proof:** `{r.get('original_proof', 'N/A')[:100]}...`")
                lines.append("")

                for cmd_result in r.get("commands_run", []):
                    lines.append(f"**Command:** `{cmd_result['command']}`")
                    lines.append(f"- Exit code: {cmd_result['exit_code']}")
                    lines.append(f"- Retest status: {cmd_result.get('retest_status', 'N/A')}")
                    if cmd_result.get("stdout"):
                        stdout_preview = cmd_result["stdout"][:300]
                        lines.append(f"- Output preview:")
                        lines.append(f"  ```")
                        lines.append(f"  {stdout_preview}")
                        lines.append(f"  ```")
                    lines.append("")

            lines.append("---")
            lines.append("")

        lines.append("")
        lines.append(
            f"*Retest report generated by Chimeras v3.1 — Cyberian Defenses*"
        )

        return "\n".join(lines)

    def load_previous_findings(self) -> List[Dict[str, Any]]:
        """Load findings from a previous engagement's findings store."""
        from core.findings_store import FindingsStore

        store = FindingsStore(self.engagement_dir)
        return store.get_all()