"""
Chimeras v3.1 — Coverage Tracker

Records what was tested, what wasn't, and what was out of scope.
Reduces liability: "Scope excluded Z, here's proof."

When a client challenges thoroughness, we produce a coverage report
showing every target, port, service, and tool combination that was
tested, along with timestamp and result status.

Strix has coverage tracking (list_coverage, record_coverage,
update_coverage). We integrate ours with the existing per-bot JSONL
forensic trail — stronger evidence integrity.

Usage:
    from core.coverage import CoverageTracker

    tracker = CoverageTracker(engagement_dir)
    tracker.record("10.0.0.1", 22, "ssh", "nmap", "scanned", "open")
    tracker.record("10.0.0.1", 443, "https", "sslscan", "scanned", "weak ciphers")

    report = tracker.coverage_report()
    # → report/coverage_report.md

Integration:
    BaseBot calls tracker.record() after each tool execution.
    Bookkeeper calls tracker.coverage_report() at report time.
"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class CoverageTracker:
    """Tracks what was tested during an engagement.

    Records per-target, per-port, per-service, per-tool coverage
    with timestamps and result status. Produces a coverage report
    at the end of the engagement proving thoroughness.

    Thread-safe: module-level lock guards all writes.
    """

    _write_lock = threading.Lock()

    def __init__(self, engagement_dir: Path):
        self.engagement_dir = Path(engagement_dir)
        self.coverage_dir = self.engagement_dir / "coverage"
        self.coverage_dir.mkdir(parents=True, exist_ok=True)
        self.coverage_path = self.coverage_dir / "coverage.jsonl"
        self.report_path = self.engagement_dir / "report" / "coverage_report.md"

    def record(
        self,
        target: str,
        port: Optional[int] = None,
        service: Optional[str] = None,
        tool: str = "",
        check_type: str = "",
        result: str = "",
        bot: str = "",
        notes: str = "",
    ) -> str:
        """Record a coverage entry.

        Args:
            target: Target IP/hostname.
            port: Port number (if applicable).
            service: Service name (ssh, http, https, etc.).
            tool: Tool name (nmap, nuclei, sslscan, etc.).
            check_type: Type of check (port_scan, vuln_scan, exploit, etc.).
            result: Result status (open, closed, vulnerable, clean, error).
            bot: Which bot performed the check.
            notes: Additional notes.

        Returns:
            Coverage entry ID.
        """
        entry = {
            "id": f"COV-{datetime.utcnow().strftime('%H%M%S')}-{abs(hash((target, port, tool))) % 10000:04d}",
            "target": target,
            "port": port,
            "service": service or "unknown",
            "tool": tool,
            "check_type": check_type,
            "result": result,
            "bot": bot,
            "notes": notes,
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            with CoverageTracker._write_lock:
                with open(self.coverage_path, "a") as f:
                    f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning(f"Failed to record coverage entry: {e}")

        return entry["id"]

    def record_from_tool_result(
        self,
        tool_result: Dict[str, Any],
        bot_name: str,
        target: str,
    ) -> Optional[str]:
        """Record a coverage entry from a tool result dict.

        Extracts tool name, target, and result from a standard
        tool result dict (as produced by BaseBot._run_tool).

        Args:
            tool_result: Tool result dict with command, exit_code, stdout.
            bot_name: Name of the bot that ran the tool.
            target: Target IP/hostname.

        Returns:
            Coverage entry ID, or None if could not extract info.
        """
        command = tool_result.get("command", "")
        tool_name = command.split()[0].split("/")[-1] if command else "unknown"
        exit_code = tool_result.get("exit_code", 0)
        stdout = tool_result.get("stdout", "")

        # Determine result status
        if exit_code == 0:
            result = "completed"
        elif exit_code == -2:
            result = "scope_blocked"
        elif exit_code == -1:
            result = "error"
        else:
            result = f"exit_{exit_code}"

        # Try to extract port from command (e.g., -p 22)
        port = None
        import re
        port_match = re.search(r'-p\s+(\d+)', command)
        if port_match:
            port = int(port_match.group(1))

        # Try to extract service from stdout
        service = None
        if port:
            service_map = {
                22: "ssh", 21: "ftp", 23: "telnet", 25: "smtp",
                53: "dns", 80: "http", 443: "https", 445: "smb",
                3389: "rdp", 8080: "http-proxy", 8443: "https-alt",
            }
            service = service_map.get(port, "unknown")

        # Determine check type from tool name
        check_type_map = {
            "nmap": "port_scan",
            "nikto": "web_vuln_scan",
            "nuclei": "vuln_scan",
            "sslscan": "ssl_scan",
            "ssh-audit": "ssh_audit",
            "gobuster": "dir_brute",
            "ffuf": "dir_brute",
            "sqlmap": "sqli_test",
            "dalfox": "xss_test",
            "whatweb": "web_fingerprint",
            "wafw00f": "waf_detect",
            "dig": "dns_lookup",
            "whois": "whois_lookup",
            "subfinder": "subdomain_enum",
            "searchsploit": "exploit_search",
            "wapiti": "web_vuln_scan",
            "commix": "command_injection_test",
            "wfuzz": "fuzzing",
        }
        check_type = check_type_map.get(tool_name, "tool_execution")

        return self.record(
            target=target,
            port=port,
            service=service,
            tool=tool_name,
            check_type=check_type,
            result=result,
            bot=bot_name,
            notes=stdout[:200] if stdout else "",
        )

    def get_all(self) -> List[Dict[str, Any]]:
        """Read all coverage entries."""
        if not self.coverage_path.exists():
            return []

        entries: List[Dict[str, Any]] = []
        try:
            with open(self.coverage_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            logger.warning(f"Failed to read coverage entries: {e}")

        return entries

    def get_by_target(self, target: str) -> List[Dict[str, Any]]:
        """Get all coverage entries for a specific target."""
        return [e for e in self.get_all() if e.get("target") == target]

    def get_by_tool(self, tool: str) -> List[Dict[str, Any]]:
        """Get all coverage entries for a specific tool."""
        return [e for e in self.get_all() if e.get("tool") == tool]

    def get_untested_targets(
        self, discovered_targets: List[str]
    ) -> List[str]:
        """Find targets that were discovered but never tested.

        Args:
            discovered_targets: All targets discovered during recon.

        Returns:
            List of targets with no coverage entries.
        """
        tested = {e.get("target") for e in self.get_all()}
        return [t for t in discovered_targets if t not in tested]

    def summary(self) -> Dict[str, Any]:
        """Generate coverage summary statistics."""
        entries = self.get_all()

        if not entries:
            return {
                "total_checks": 0,
                "unique_targets": 0,
                "unique_tools": 0,
                "unique_services": 0,
                "check_types": {},
                "targets_tested": [],
                "tools_used": [],
            }

        targets = {e.get("target", "") for e in entries if e.get("target")}
        tools = {e.get("tool", "") for e in entries if e.get("tool")}
        services = {e.get("service", "") for e in entries if e.get("service")}

        check_types: Dict[str, int] = {}
        for e in entries:
            ct = e.get("check_type", "unknown")
            check_types[ct] = check_types.get(ct, 0) + 1

        return {
            "total_checks": len(entries),
            "unique_targets": len(targets),
            "unique_tools": len(tools),
            "unique_services": len(services),
            "check_types": check_types,
            "targets_tested": sorted(targets),
            "tools_used": sorted(tools),
        }

    def coverage_report(self, discovered_targets: Optional[List[str]] = None) -> str:
        """Generate a markdown coverage report.

        Args:
            discovered_targets: All discovered targets (to identify untested).

        Returns:
            Markdown report string. Also writes to report/coverage_report.md.
        """
        entries = self.get_all()
        summary = self.summary()

        lines: List[str] = [
            "# Coverage Report",
            "",
            f"**Generated:** {datetime.utcnow().isoformat()}",
            f"**Tester:** Chimeras Autonomous AI Pentest Swarm",
            "",
            "---",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total checks performed | {summary['total_checks']} |",
            f"| Unique targets tested | {summary['unique_targets']} |",
            f"| Unique tools used | {summary['unique_tools']} |",
            f"| Unique services tested | {summary['unique_services']} |",
            "",
        ]

        # Check type breakdown
        if summary["check_types"]:
            lines.append("## Checks by Type")
            lines.append("")
            lines.append("| Check Type | Count |")
            lines.append("|------------|-------|")
            for ct, count in sorted(summary["check_types"].items()):
                lines.append(f"| {ct} | {count} |")
            lines.append("")

        # Per-target coverage
        if entries:
            lines.append("## Per-Target Coverage")
            lines.append("")
            lines.append("| Target | Port | Service | Tool | Check Type | Result | Timestamp |")
            lines.append("|--------|------|---------|------|------------|--------|-----------|")
            for e in entries:
                target = e.get("target", "N/A")
                port = e.get("port", "N/A")
                service = e.get("service", "N/A")
                tool = e.get("tool", "N/A")
                check_type = e.get("check_type", "N/A")
                result = e.get("result", "N/A")
                ts = e.get("timestamp", "N/A")[:19]
                lines.append(f"| {target} | {port} | {service} | {tool} | {check_type} | {result} | {ts} |")
            lines.append("")

        # Untested targets
        if discovered_targets:
            untested = self.get_untested_targets(discovered_targets)
            if untested:
                lines.append("## ⚠ Untested Targets")
                lines.append("")
                lines.append("The following targets were discovered but not tested:")
                lines.append("")
                for t in untested:
                    lines.append(f"- {t}")
                lines.append("")
            else:
                lines.append("## All Discovered Targets Tested ✅")
                lines.append("")

        # Tools used
        if summary["tools_used"]:
            lines.append("## Tools Used")
            lines.append("")
            for tool in summary["tools_used"]:
                lines.append(f"- {tool}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("*Coverage report generated by Chimeras v3.1 — Cyberian Defenses*")

        report_text = "\n".join(lines)

        # Write to file
        try:
            self.report_path.parent.mkdir(parents=True, exist_ok=True)
            self.report_path.write_text(report_text)
        except Exception as e:
            logger.warning(f"Failed to write coverage report: {e}")

        return report_text