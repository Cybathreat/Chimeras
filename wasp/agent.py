"""
Chimeras v2.0 — Wasp Agent

Web application pentesting specialist. Executes web-layer exploitation
after Bloodhound identifies web vulnerabilities.
Scope: sqlmap, nikto, nuclei, curl, python3, ffuf, wfuzz, dalfox, commix,
       gobuster, whatweb, nmap

Specializations:
  - XSS (reflected, stored, DOM-based)
  - CSRF (token analysis, bypass attempts)
  - SQL injection (error-based, blind, time-based, UNION)
  - File upload bypass
  - SSTI (Server-Side Template Injection)
  - SSRF (Server-Side Request Forgery)
  - XXE (XML External Entity)
  - LFI/RFI (Local/Remote File Inclusion)
  - IDOR (Insecure Direct Object Reference)
  - Authentication bypass
  - Authorization flaws

Runs after human approval gate (same as Surgeon) — web exploitation
is active exploitation and requires authorization.
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class Wasp(BaseBot):
    """Wasp — Web Application Pentesting Specialist. Human gate enforced."""

    bot_name = "wasp"
    role_description = (
        "web application penetration testing specialist — XSS, CSRF, SQLi, "
        "file upload, SSTI, SSRF, XXE, LFI/RFI, IDOR, auth bypass"
    )
    scope_description = (
        "Web application exploitation ONLY. Active exploitation of web-layer "
        "vulnerabilities. NO network exploitation, NO privilege escalation, "
        "NO data exfiltration."
    )

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    async def run(self) -> Dict[str, Any]:
        """Override to check human approval gate before doing anything."""
        if not self.state.get("human_approval", False):
            self._banner()
            self._log("HUMAN APPROVAL NOT GRANTED — web exploitation blocked", "GATE")
            self._append_log("BLOCKED: Human approval not granted. Web exploitation skipped.")
            self._write_bot_file("# WASP — BLOCKED\n\nHuman approval not granted. Web exploitation phase skipped.\n")
            decision = {"needed": True, "strategy": "await_approval", "confidence": 1.0,
                        "reasoning": "Human approval gate not passed."}
            self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision
            return {"reasoning": decision, "executed": False, "awaiting_approval": True}

        return await super().run()

    def _build_system_prompt(self) -> str:
        """Override to add web pentesting context."""
        base_prompt = super()._build_system_prompt()

        addendum = """

## Web Application Exploitation Context

You are the web application exploitation specialist. Bloodhound identified
potential web-layer vulnerabilities. Your job is to confirm and exploit them.

### Attack Categories (prioritize by Bloodhound findings)

1. **SQL Injection**
   - Use sqlmap for automated SQLi detection and exploitation
   - Test error-based, blind (boolean/time-based), UNION-based
   - Extract database structure, tables, and data samples
   - Try --dbs, --tables, --dump for evidence

2. **Cross-Site Scripting (XSS)**
   - Reflected: test URL parameters, search forms, error messages
   - Stored: test input fields that persist (comments, profiles, posts)
   - DOM-based: analyze JavaScript for sink/source patterns
   - Use dalfox for automated XSS detection
   - Craft manual payloads to bypass filters

3. **CSRF**
   - Check for anti-CSRF tokens
   - Test if tokens are validated server-side
   - Craft cross-origin request PoCs
   - Check SameSite cookie attributes

4. **File Upload**
   - Test for unrestricted file upload
   - Try bypassing filters: double extensions, null bytes, MIME spoofing
   - Upload web shells if upload is exploitable
   - Check if uploaded files are accessible and executable

5. **SSTI (Server-Side Template Injection)**
   - Test template engines (Jinja2, Twig, Freemarker, Velocity)
   - Use {{7*7}} and {{7*'7'}} probe payloads
   - Escalate to RCE if SSTI confirmed

6. **SSRF**
   - Test URL parameters that fetch remote resources
   - Try internal IP access (169.254.169.254 for cloud metadata)
   - Test protocol smuggling (file://, gopher://, dict://)

7. **LFI/RFI**
   - Test path traversal in file parameters
   - Try ../ sequences, null bytes, double encoding
   - Read sensitive files (/etc/passwd, web.config, .env)

8. **IDOR**
   - Test object references (user IDs, file IDs, API endpoints)
   - Try incrementing/decrementing IDs
   - Test vertical and horizontal privilege escalation

9. **Authentication Bypass**
   - Test default credentials
   - SQL injection in login forms
   - Session manipulation
   - JWT tampering (alg=none, key confusion)

10. **Authorization Flaws**
    - Test forced browsing to admin panels
    - Check if API endpoints enforce authorization
    - Test role escalation

### Approach
- Start with Bloodhound's findings — don't reinvent
- One attack vector at a time, verify before moving on
- Capture evidence: PoC requests, responses, screenshots-equivalent (curl output)
- Track every successful exploit in structured_data
- If a vector fails after 3 attempts, record it and move on
- Don't repeat what Surgeon already tried — check surgeon.md first

### Evidence Format
For each confirmed vulnerability, provide:
- Vulnerability type (XSS, SQLi, etc.)
- Target URL and parameter
- PoC payload/request
- Response snippet (proof)
- Impact assessment
- Remediation recommendation
"""

        return base_prompt + addendum

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with web exploitation findings and track sessions."""
        try:
            structured = analysis.get("structured_data", {})
            if not isinstance(structured, dict):
                structured = {}

            # Track confirmed web vulnerabilities
            web_vulns = structured.get("confirmed_vulns", [])
            self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision

            # Update vuln_report with confirmed exploits
            vuln_report = self.state.get("vuln_report", [])
            if not isinstance(vuln_report, list):
                vuln_report = []
            for vuln in web_vulns:
                if isinstance(vuln, dict):
                    vuln["status"] = "confirmed_exploited"
                    vuln_report.append(vuln)
            self.state["vuln_report"] = vuln_report

            # Track active sessions (e.g., if web shell uploaded)
            sessions = structured.get("sessions", [])
            if sessions:
                existing_sessions = self.state.get("active_sessions", [])
                if not isinstance(existing_sessions, list):
                    existing_sessions = []
                for session in sessions:
                    if isinstance(session, dict):
                        existing_sessions.append(session)
                self.state["active_sessions"] = existing_sessions

            # Track exploited hosts
            exploited = self.state.get("exploited_hosts", [])
            if not isinstance(exploited, list):
                exploited = []
            for key in ("exploited_hosts", "compromised", "access"):
                found = structured.get(key, [])
                if isinstance(found, list):
                    for h in found:
                        if isinstance(h, str) and h not in exploited:
                            exploited.append(h)
                        elif isinstance(h, dict):
                            host = h.get("host") or h.get("target") or h.get("url")
                            if host and isinstance(host, str) and host not in exploited:
                                exploited.append(host)
            self.state["exploited_hosts"] = exploited

            # Track artifacts (e.g., uploaded web shells)
            artifacts = self.state.get("target_artifacts", [])
            if not isinstance(artifacts, list):
                artifacts = []
            for key in ("artifacts", "uploaded_files", "web_shells", "modifications"):
                found = structured.get(key, [])
                if isinstance(found, list):
                    for a in found:
                        if isinstance(a, dict):
                            artifact = {
                                "host": a.get("host") or a.get("target", "unknown"),
                                "artifact_type": a.get("type", key),
                                "path": a.get("path", a.get("location", "unknown")),
                                "description": a.get("description", ""),
                                "cleaned": False,
                            }
                            artifacts.append(artifact)
            self.state["target_artifacts"] = artifacts

            # Track failed exploitation attempts
            failed = self.state.get("failed_vectors", [])
            if not isinstance(failed, list):
                failed = []
            for key in ("failed_exploits", "errors", "blocked_attempts"):
                found = structured.get(key, [])
                if isinstance(found, list):
                    for item in found:
                        if isinstance(item, dict):
                            failed.append({
                                "target": item.get("target", item.get("url", "unknown")),
                                "tool": item.get("tool", self.bot_name),
                                "error": item.get("error", item.get("reason", "unknown")),
                                "timestamp": item.get("timestamp", ""),
                            })
            for result in tool_results:
                if isinstance(result, dict) and not result.get("success", True) and not result.get("scope_blocked"):
                    cmd = result.get("command", "")
                    tool_name = cmd.split()[0] if cmd else self.bot_name
                    failed.append({
                        "target": self.state.get("mission", {}).get("target", "unknown"),
                        "tool": tool_name,
                        "error": result.get("stderr", "exploit failed")[:200],
                        "timestamp": "",
                    })
            self.state["failed_vectors"] = failed

        except Exception as e:
            print(f"[WASP] _update_state error: {e}")
            try:
                self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision
            except Exception:
                pass