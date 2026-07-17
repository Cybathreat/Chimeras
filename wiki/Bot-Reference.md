# Bot Reference

## The 9 Bots

### WarChief — Orchestrator
- **Role**: Plans the engagement, reads all bot reports, routes next steps
- **Tool Category**: `none` (no tool execution)
- **Scope**: Reads/writes engagement files only
- **Input**: Mission objectives, scope, RoE from mission.md
- **Output**: `plan.md`, `warchief.md`

### ARIA — Passive Reconnaissance
- **Role**: OSINT, DNS, WHOIS, web tech fingerprinting
- **Tool Category**: `passive_recon`
- **Available Tools**: dig, host, whois, curl, whatweb, wafw00f, subfinder, amass, theHarvester, waybackurls, dnsrecon, dnsx, httpx
- **Input**: Target from WarChief's plan
- **Output**: `aria.md`, findings appended to `findings.md`

### Lisa — Active Scanning
- **Role**: Port scanning, service enumeration, web scanning
- **Tool Category**: `active_scan`
- **Available Tools**: nmap, masscan, rustscan, nikto, gobuster, ffuf, dirb, wpscan, whatweb, httpx, dnsx, naabu
- **Input**: ARIA's recon findings
- **Output**: `lisa.md`, findings appended to `findings.md`

### Bloodhound — Vulnerability Detection
- **Role**: CVE matching, vulnerability scanning, SSL analysis
- **Tool Category**: `vuln_detection`
- **Available Tools**: nmap (scripts), nuclei, searchsploit, nikto, wapiti, wafw00f, ssh-audit, sslscan, testssl, vulners
- **Input**: Lisa's scan results (open ports, services)
- **Output**: `bloodhound.md`, `vuln_report` in state
- **Gate**: After Bloodhound, human must approve exploitation

### Pathologist — Payload Fabricrication
- **Role**: Generates payloads based on discovered vulnerabilities
- **Tool Category**: `payload_fab`
- **Available Tools**: msfvenom, msfconsole, searchsploit, curl
- **Input**: Bloodhound's vuln report + human approval
- **Output**: `pathologist.md`, payload artifacts in `poc/`

### Surgeon — Exploitation
- **Role**: Executes exploits against identified vulnerabilities
- **Tool Category**: `exploitation`
- **Available Tools**: msfconsole, msfvenom, sqlmap, curl, nc, ncat, python3, bash
- **Input**: Pathologist's payload manifest
- **Output**: `surgeon.md`, `active_sessions` in state

### Magician — Privilege Escalation
- **Role**: Escalates privileges, lateral movement
- **Tool Category**: `privesc`
- **Available Tools**: linpeas, winpeas, pspy, find, cat, ls, python3, bash, ssh, smbclient, crackmapexec, impacket-secretsdump
- **Input**: Surgeon's exploit sessions
- **Output**: `magician.md`, `movement_report` in state

### Thief — Data Exfiltration
- **Role**: Exfiltrates data as proof of compromise
- **Tool Category**: `exfiltration`
- **Available Tools**: curl, wget, nc, python3, bash, tar, gzip, scp, rsync
- **Input**: Magician's privesc results
- **Output**: `thief.md`, `exfil_report` in state

### Bookkeeper — Report Generation
- **Role**: Compiles all findings into a professional pentest report
- **Tool Category**: `none` (no tool execution)
- **Input**: All engagement files, findings, raw tool output
- **Output**: `report/final_report.md` — professional pentest report with scope, executive summary, findings table, per-finding sections (description → risks → attack vectors → PoC → proof of existence → remediation)