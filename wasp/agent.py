"""
Chimeras v2.0 — Wasp Agent

Web application vulnerability detection specialist. Runs in parallel
with Bloodhound to cover web-layer vulnerabilities that Bloodhound misses.
Scope: sqlmap, nikto, nuclei, curl, python3, ffuf, wfuzz, dalfox, commix,
       gobuster, whatweb, nmap, httpx

Wasp is a DETECTION bot — it finds and proves web vulnerabilities exist
but does not exploit them for shell access. It runs WITHOUT human approval
because it's detection, not exploitation. Surgeon/Wasp-exploitation mode
handles active exploitation after human gate.

Specializations:
  - XSS (reflected, stored, DOM-based) detection
  - CSRF (token analysis, bypass attempts) detection
  - SQL injection detection (error-based, blind, time-based)
  - File upload vulnerability detection
  - SSTI (Server-Side Template Injection) detection
  - SSRF (Server-Side Request Forgery) detection
  - XXE (XML External Entity) detection
  - LFI/RFI (Local/Remote File Inclusion) detection
  - IDOR (Insecure Direct Object Reference) detection
  - Authentication bypass detection
  - Authorization flaws detection
"""

from typing import Dict, Any, Optional
from core.base_bot import BaseBot
from core.state import SwarmState


class Wasp(BaseBot):
    """Wasp — Web Application Vulnerability Detection Specialist.

    Runs in parallel with Bloodhound. No human approval needed — this is
    detection, not exploitation.
    """

    bot_name = "wasp"
    role_description = (
        "web application vulnerability detection specialist — XSS, CSRF, SQLi, "
        "file upload, SSTI, SSRF, XXE, LFI/RFI, IDOR, auth bypass detection"
    )
    scope_description = (
        "Web application vulnerability DETECTION ONLY. Probes for web vulns, "
        "crafts PoCs to confirm they exist, but does not exploit for shell. "
        "NO network exploitation, NO privilege escalation, NO data exfiltration."
    )

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    def _build_system_prompt(self) -> str:
        """Override to add web pentesting context."""
        base_prompt = super()._build_system_prompt()

        addendum = """

## Web Application Vulnerability Detection Context

You are the web application vulnerability detection specialist. You run
ALONGSIDE Bloodhound — Bloodhound handles infrastructure (SSL, network
services, CVE matching), you handle the web application layer.

### Your Job
Find and CONFIRM web vulnerabilities with lightweight PoCs. You are not
exploiting for shell — you are proving vulnerabilities exist so WarChief
can decide whether to escalate to exploitation.

### Detection Categories (test all applicable)

1. **SQL Injection** — Use sqlmap in detection mode (--batch --level 1).
   Test URL parameters, POST data, cookies, headers. Don't dump data —
   just confirm injection is possible.

2. **Cross-Site Scripting (XSS)** — Use dalfox or manual payloads.
   Reflected: test URL parameters, search, error messages.
   Stored: test input fields that persist (comments, profiles).
   DOM: look for dangerous JavaScript sinks (innerHTML, document.write).

3. **CSRF** — Check for anti-CSRF tokens on state-changing requests.
   Test if tokens are validated. Check SameSite cookie attributes.

4. **File Upload** — Test for unrestricted upload. Try bypassing filters:
   double extensions, null bytes, MIME spoofing. Don't upload shells —
   just confirm the bypass works.

5. **SSTI** — Probe template engines with {{7*7}} payloads.
   Jinja2, Twig, Freemarker, Velocity. Confirm if output reflects 49.

6. **SSRF** — Test URL parameters that fetch remote resources.
   Try internal IPs, cloud metadata (169.254.169.254).

7. **LFI/RFI** — Test path traversal in file parameters.
   ../ sequences, null bytes, double encoding. Read /etc/passwd or equivalent.

8. **IDOR** — Test object references (user IDs, file IDs, API endpoints).
   Try incrementing/decrementing IDs. Vertical and horizontal.

9. **Authentication Bypass** — Test default credentials, SQLi in login,
   session manipulation, JWT tampering (alg=none).

10. **Authorization Flaws** — Forced browsing to admin panels.
    Check if API endpoints enforce authorization.

11. **Information Disclosure** — Check /robots.txt, /.git/, /.env,
    /server-status, /admin, /api/docs, swagger endpoints, backup files.

12. **Parameter Discovery** — Use ffuf/gobuster for hidden parameters,
    API endpoints, and directories not covered by Lisa.

### Approach
- Start from Bloodhound's and Lisa's findings — don't reinvent
- Test one category at a time, verify before moving on
- Use --batch and non-interactive flags on all tools
- Capture evidence: request, response snippet, PoC payload
- Lightweight PoCs only — prove it works, don't do damage
- If a vector shows nothing after reasonable effort, move on
- 3 failures on the same payload type = filtered, move on

### Evidence Format
For each confirmed vulnerability, provide in structured_data.confirmed_vulns:
{
  "type": "XSS|SQLi|CSRF|...",
  "url": "https://target.com/page?param=value",
  "parameter": "param",
  "method": "GET|POST",
  "poc": "actual payload used",
  "response_evidence": "snippet of response proving vulnerability",
  "severity": "critical|high|medium|low",
  "impact": "what an attacker could do",
  "remediation": "how to fix"
}
"""

        return base_prompt + addendum

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with web vulnerability findings."""
        try:
            structured = analysis.get("structured_data", {})
            if not isinstance(structured, dict):
                structured = {}

            self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision

            # Track confirmed web vulnerabilities
            web_vulns = structured.get("confirmed_vulns", [])
            if not web_vulns:
                # Also check findings list for vuln entries
                findings = analysis.get("findings", [])
                for f in findings:
                    if isinstance(f, dict):
                        web_vulns.append(f)
                    elif isinstance(f, str) and any(x in f.lower() for x in
                                  ["xss", "sqli", "csrf", "ssrf", "lfi", "rfi", "ssti", "idor"]):
                        web_vulns.append({"description": f, "type": "unknown"})

            # Merge into vuln_report
            vuln_report = self.state.get("vuln_report", [])
            if not isinstance(vuln_report, list):
                vuln_report = []
            for vuln in web_vulns:
                if isinstance(vuln, dict):
                    vuln["detected_by"] = "wasp"
                    vuln["status"] = "confirmed_detected"
                    vuln_report.append(vuln)
            self.state["vuln_report"] = vuln_report

            # Track failed detection attempts
            failed = self.state.get("failed_vectors", [])
            if not isinstance(failed, list):
                failed = []
            for key in ("failed_checks", "errors", "blocked_scans"):
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
                        "error": result.get("stderr", "scan failed")[:200],
                        "timestamp": "",
                    })
            self.state["failed_vectors"] = failed

        except Exception as e:
            print(f"[WASP] _update_state error: {e}")
            try:
                self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision
            except Exception:
                pass