# Bot Reference (v2)

## The 10 Bots

### WarChief — Decision Router
- **Role**: Re-enters after each phase, analyzes accumulated findings, makes routing decisions. Not a one-shot planner.
- **Tool Category**: `none` (no tool execution)
- **Routing Decisions**: 12 — `init`, `recon`, `scan`, `vuln_detection`, `vulns_found_exploit`, `insufficient_data_abort`, `lateral_recon`, `lateral_scan`, `report`, `continue_exploit`, `privesc`, `exfiltrate`
- **State Machine**: 11 states — init → recon → scanning → vuln_detection → exploitation_prep → exploitation → post_exploit → lateral_recon → lateral_scanning → reporting → complete
- **Confidence Threshold**: below 0.6 → override to safe conservative route
- **Fallback**: malformed LLM output → defaults to `report` route, engagement degrades safely
- **Input**: All engagement files, decision history (rolling 5)
- **Output**: `plan.md` (with decision audit trail), `warchief_decisions.json`, `warchief.md`

### ARIA — Passive Reconnaissance
- **Role**: OSINT, DNS, WHOIS, web tech fingerprinting. v2: lateral recon substrat (internal DNS, SMB, credentials)
- **Tool Category**: `passive_recon`
- **Available Tools**: dig, host, whois, curl, whatweb, wafw00f, subfinder, amass, theHarvester, waybackurls, dnsrecon, dnsx, httpx
- **Input**: Target from WarChief's plan
- **Output**: `aria.md`, findings appended to `findings.md`, `discovered_targets` in state

### Lisa — Active Scanning
- **Role**: Port scanning, service enumeration, web scanning. v2: lateral scan mode (high-value services, DC detection)
- **Tool Category**: `active_scan`
- **Available Tools**: nmap, masscan, rustscan, nikto, gobuster, ffuf, dirb, wpscan, whatweb, httpx, dnsx, naabu
- **Input**: ARIA's recon findings
- **Output**: `lisa.md`, findings appended to `findings.md`, `internal_targets` in state

### Bloodhound — Vulnerability Detection (Infrastructure)
- **Role**: CVE matching, vulnerability scanning, SSL analysis. v2: WAF/IPS detection, failed vector tracking
- **Tool Category**: `vuln_detection`
- **Available Tools**: nmap (scripts), nuclei, searchsploit, nikto, wapiti, wafw00f, ssh-audit, sslscan, testssl, vulners
- **Input**: Lisa's scan results (open ports, services)
- **Output**: `bloodhound.md`, `vuln_report` in state, `failed_vectors` in state
- **Runs in parallel with Wasp** — Bloodhound covers infrastructure, Wasp covers web application
- **Gate**: After Bloodhound+Wasp, human must approve exploitation

### Wasp — Web Application Vulnerability Detection
- **Role**: Detects web-layer vulnerabilities: XSS, CSRF, SQLi, file upload, SSTI, SSRF, XXE, LFI/RFI, IDOR, auth bypass, authorization flaws, information disclosure. Proves vulnerabilities with lightweight PoCs.
- **Tool Category**: `web_exploit`
- **Available Tools**: sqlmap, nikto, nuclei, curl, python3, ffuf, wfuzz, dalfox, commix, gobuster, whatweb, nmap, httpx
- **Input**: Lisa's scan results + ARIA's recon findings — starts immediately, doesn't wait for Bloodhound
- **Output**: `wasp.md`, findings appended to `vuln_report` in state (with `detected_by: wasp`), `failed_vectors` in state
- **No human approval needed** — this is detection, not exploitation
- **Runs in parallel with Bloodhound** via asyncio.gather inside the bloodhound graph node

### Pathologist — Payload Fabrication
- **Role**: Generates payloads based on discovered vulnerabilities
- **Tool Category**: `payload_fab`
- **Available Tools**: msfvenom, msfconsole, searchsploit, curl
- **Input**: Bloodhound's vuln report + human approval
- **Output**: `pathologist.md`, payload artifacts in `poc/`

### Surgeon — Exploitation
- **Role**: Executes exploits against identified vulnerabilities. v2: lateral exploitation (SMB exec, WinRM, SSH reuse), failed vector tracking, artifact tracking
- **Tool Category**: `exploitation`
- **Available Tools**: msfconsole, msfvenom, sqlmap, curl, nc, ncat, python3, bash
- **Input**: Pathologist's payload manifest
- **Output**: `surgeon.md`, `active_sessions` in state, `failed_vectors` in state, `target_artifacts` in state, `exploited_hosts` in state

### Magician — Privilege Escalation & Lateral Movement
- **Role**: Escalates privileges, lateral movement. v2: cred dumping, AD enum, artifact tracking
- **Tool Category**: `privesc`
- **Available Tools**: linpeas, winpeas, pspy, find, cat, ls, python3, bash, ssh, smbclient, crackmapexec, impacket-secretsdump
- **Input**: Surgeon's exploit sessions
- **Output**: `magician.md`, `movement_report` in state, `target_artifacts` in state

### Thief — Data Exfiltration
- **Role**: Exfiltrates data as proof of compromise. v2: failed exfil tracking
- **Tool Category**: `exfiltration`
- **Available Tools**: curl, wget, nc, python3, bash, tar, gzip, scp, rsync
- **Input**: Magician's privesc results
- **Output**: `thief.md`, `exfil_report` in state, `failed_vectors` in state

### Bookkeeper — Report Generation, Cleanup & Rollback
- **Role**: Compiles all findings into a professional pentest report. v2: cleanup/rollback (iterates `target_artifacts`, attempts removal, flags failures), decision audit trail, metrics
- **Tool Category**: `none` (no tool execution)
- **Input**: All engagement files, findings, raw tool output, decision history, target artifacts
- **Output**: `report/final_report.md` — professional pentest report with:
  - Scope and executive summary
  - Engagement flow (all WarChief routing decisions with reasoning)
  - Findings table with severity, CVSS scores, status
  - Per-finding: description → risks → attack vectors → PoC → proof of existence → remediation
  - Decision metrics (total recon cycles, scanning cycles, exploitation cycles)
  - Cleanup status (artifacts removed, artifacts that couldn't be cleaned)
  - Mission outcome (complete, scope exhausted, authorization issues, target hardened)