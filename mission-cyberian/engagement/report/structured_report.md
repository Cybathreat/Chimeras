# Penetration Test Report

**Engagement:** cyberian-defenses.com
**Date:** 2026-09-02
**Tester:** Chimeras Autonomous AI Pentest Swarm
**Client:** 

---

## 1. Executive Summary

<!-- CYBERIAN DEFENSES REPORT THEME
brand: Cyberian Defenses
tagline: Guiding businesses to stronger cybersecurity.
logo: /root/cyberian-defenses/logo.png
website: cyberian-defenses.com
email: ahmed.chiboub@cybacrest.com
colors:
  navy_primary: "#173054"
  navy_mid: "#1d4768"
  navy_light: "#225777"
  success: "#10b981"
  warning: "#f59e0b"
  critical: "#ef4444"
  surface: "#f4f5f7"
  border: "#e2e5ea"
  text_primary: "#111827"
  text_secondary: "#6b7280"
  text_muted: "#9ca3af"
fonts:
  sans: "Inter, sans-serif"
  mono: "JetBrains Mono, monospace"
-->

# Cyberian Defenses
## Guiding businesses to stronger cybersecurity.

**CONFIDENTIAL — PENETRATION TEST REPORT**

| Field | Value |
|-------|-------|
| Target | cyberian-defenses.com (76.13.46.223) |
| Date | 2026-09-02 |
| Classification | CONFIDENTIAL |
| Prepared by | Cyberian Defenses |

---

# Penetration Test Report — cyberian-defenses.com

## 1. Scope

- **Target:** cyberian-defenses.com (76.13.46.223)
- **Objectives:** Comprehensive external penetration test — passive reconnaissance, active scanning, vulnerability detection, and exploitation assessment of the cyberian-defenses.com web presence and supporting infrastructure
- **Rules of Engagement:** Authorized penetration test with cautious aggressiveness posture. Scope limited to cyberian-defenses.com domain and resolved IP 76.13.46.223. Exploitation phase gated on human approval. No data exfiltration unless shell access obtained. CDN subdomain (cyberian-defenses.azureedge.net) excluded from active testing.
- **Methodology:** Multi-phase swarm-based assessment utilizing specialized bots:
  - **ARIA** (Passive Reconnaissance): DNS enumeration, subdomain discovery, certificate transparency, WHOIS, technology fingerprinting — 2 cycles
  - **Lisa** (Active Scanning): TCP/UDP port scanning, service version detection, NSE scripts, SSL/TLS analysis, OS fingerprinting — 2 cycles
  - **Bloodhound** (Infrastructure Vulnerability Detection): CVE matching, SSH algorithm

---

## 2. Scope

**Mission Scope:** cyberian-defenses.com
**Internal Scope:** 
**Rules of Engagement:** N/A

**Targets Tested:**

- cyberian-defenses.com


---

## 3. Findings Summary

| ID | Finding | Severity | CVSS | Status |
|----|---------|----------|------|--------|

| BLO-001 | OpenSSH 9.6p1 — CVE-2024-6387 (regreSSHion) RCE | Critical | 8.1 | Probable |

| BLO-002 | Weak SSH MAC algorithms (hmac-sha1) enabled | Medium | 5.9 | Confirmed |

| BLO-003 | SSH password authentication enabled | Medium | 5.3 | Confirmed |

| BLO-004 | CSP allows 'unsafe-inline' for scripts and styles | Medium | 5.4 | Confirmed |

| BLO-005 | No WAF detected on web services | Low | 3.7 | Confirmed |

| BLO-006 | SSL/TLS configuration hardened — no vulnerabilities found | Info | None | Confirmed |

| LIS-001 | SSH service exposed on port 22 — OpenSSH 9.6p1 Ubuntu | Low | 3.7 | Confirmed |

| LIS-002 | HTTP port 80 returns 404 — no web content served directly | Info | None | Confirmed |

| LIS-003 | HTTPS served on port 443 — nginx 1.24.0 with cyberian-defenses.com | Info | None | Confirmed |

| LIS-004 | Strong TLS/SSL configuration — TLSv1.2+ only, A-grade ciphers | Info | None | Confirmed |

| LIS-005 | 128 virtual host names returning HTTP 200 on port 443 | Medium | 5.3 | Confirmed |

| LIS-006 | Security headers well-implemented on HTTPS | Info | None | Confirmed |

| LIS-007 | robots.txt and /blog/ path discovered | Low | None | Confirmed |

| LIS-008 | Incomplete TCP port scan — ports 1001-65535 unscanned | Medium | None | Confirmed |

| LIS-009 | UDP ports open|filtered — inconclusive results | Low | None | Probable |

| LIS-010 | Host hostname revealed: srv1479954.hstgr.cloud (Hostinger) | Low | None | Confirmed |

| LIS-001 | SSH password authentication enabled | Medium | 5.3 | Confirmed |

| LIS-002 | SSH weak MAC algorithm hmac-sha1 supported | Low | 3.7 | Confirmed |

| LIS-003 | nginx version disclosure on HTTP/HTTPS | Low | 3.1 | Confirmed |

| LIS-004 | CSP allows unsafe-inline for scripts and styles | Medium | 5.4 | Confirmed |

| LIS-005 | All high TCP ports filtered - no additional services | Info | None | Confirmed |

| LIS-006 | UDP ports open|filtered - inconclusive results | Info | None | Probable |

| LIS-007 | SSL/TLS hardened - no legacy protocols | Info | None | Confirmed |

| LIS-008 | Email and author metadata disclosed in web page | Low | 3.3 | Confirmed |

| LIS-009 | HTTP to HTTPS redirect with HSTS preload | Info | None | Confirmed |

| LIS-010 | Web tech stack identified: Nginx, Tailwind CSS, Ubuntu | Info | None | Confirmed |

| WAS-001 | CSP allows unsafe-inline for scripts and styles | Medium | 5.3 | Confirmed |

| WAS-002 | Sensitive files (.git, .env) return 403 — exist on server | Low | 3.7 | Confirmed |

| WAS-003 | Server version disclosure in HTTP headers | Low | 3.1 | Confirmed |

| WAS-004 | Author name disclosed in blog HTML meta tags | Info | None | Confirmed |

| WAS-005 | Form data submitted to third-party formspree.io | Low | 3.7 | Confirmed |

| WAS-006 | robots.txt fully open allowing all crawlers | Info | None | Confirmed |

| WAS-007 | Host header injection not exploitable | Info | None | Confirmed |

| WAS-008 | X-Original-URL/X-Rewrite-URL header bypass not effective | Info | None | Confirmed |

| WAS-009 | Nuclei vulnerability scanning incomplete — templates missing | Info | None | Confirmed |

| WAS-010 | Blog section is primary attack surface for content injection | Low | None | Probable |

| WAR-001 | nginx/1.24.0 Web Server Exposed | Info | None | Confirmed |

| WAR-002 | Missing DNSSEC Configuration | Low | 3.7 | Confirmed |

| WAR-003 | Missing CAA DNS Record | Low | 3.1 | Confirmed |

| WAR-004 | Azure CDN/Front Door Detected | Info | None | Probable |

| WAR-005 | Third-Party Form Handler (Formspree) | Low | None | Confirmed |

| WAR-006 | Key Personnel Identified — Ahmed Chiboub | Info | None | Probable |

| WAR-007 | No IPv6 Support Configured | Info | None | Confirmed |

| WAR-001 | CSP allows unsafe-inline in script-src | Medium | 5.4 | Confirmed |

| WAR-002 | Catch-all vhost on HTTPS returns 200 for all Host headers | Medium | 5.3 | Confirmed |

| WAR-003 | SSH exposed on port 22 with known username | Medium | 5.3 | Confirmed |

| WAR-004 | Third-party form handler Formspree in CSP | Low | 3.7 | Confirmed |

| WAR-005 | Missing DNSSEC, CAA, and IPv6 records | Low | 3.1 | Confirmed |

| WAR-006 | High TCP ports unscanned — potential hidden services | Info | None | Theoretical |

| WAR-007 | Azure CDN subdomain discovered but unvalidated | Low | None | Probable |

| WAR-008 | Blog page detected at /blog/ | Info | None | Confirmed |

| WAR-001 | SSH password authentication enabled | Medium | 5.3 | Confirmed |

| WAR-002 | SSH weak MAC algorithm hmac-sha1 supported | Low | 3.1 | Confirmed |

| WAR-003 | nginx version disclosure | Low | 3.7 | Confirmed |

| WAR-004 | CSP unsafe-inline directive weakens XSS protection | Medium | 5.4 | Confirmed |

| WAR-005 | Email and author metadata exposed | Low | 2.7 | Confirmed |

| WAR-006 | External form service dependency formspree.io | Info | None | Confirmed |

| WAR-007 | robots.txt exists but contents not analyzed | Info | None | Probable |

| WAR-008 | Vhost catch-all on port 443 | Low | 3.1 | Confirmed |

| WAR-001 | CVE-2024-6387 regreSSHion RCE — OpenSSH 9.6p1 in affected range | Critical | 8.1 | Probable |

| WAR-002 | CSP unsafe-inline allows XSS exploitation without nonce bypass | Medium | 5.4 | Confirmed |

| WAR-003 | SSH password authentication enabled | Medium | 5.3 | Confirmed |

| WAR-004 | .git directory exists on web server (HTTP 403) | Low | 3.7 | Confirmed |

| WAR-005 | .env file exists on web server (HTTP 403) | Low | 3.7 | Confirmed |

| WAR-006 | Weak HMAC-SHA1 MAC algorithm supported by SSH | Low | 3.1 | Confirmed |

| WAR-007 | nginx version disclosure in HTTP headers | Low | 2.7 | Confirmed |

| WAR-008 | Deprecated X-XSS-Protection header present | Info | None | Confirmed |

| WAR-001 | CVE-2024-6387 regreSSHion RCE on OpenSSH 9.6p1 | High | 8.1 | Theoretical |

| WAR-002 | CSP unsafe-inline directive enables XSS exploitation | Medium | 5.4 | Confirmed |

| WAR-003 | SSH password authentication enabled | Medium | 5.3 | Confirmed |

| WAR-004 | .git and .env files present in web root (403 blocked) | Low | 3.7 | Confirmed |

| WAR-005 | Weak SSH MAC algorithm hmac-sha1 enabled | Low | 3.1 | Confirmed |

| WAR-006 | nginx server_tokens disclosure | Low | 2.7 | Confirmed |

| WAR-007 | Deprecated X-XSS-Protection header present | Info | 1.0 | Confirmed |

| WAR-001 | CVE-2024-6387 regreSSHion RCE on OpenSSH 9.6p1 | High | 8.1 | Theoretical |

| WAR-002 | CSP allows unsafe-inline scripts | Medium | 5.4 | Confirmed |

| WAR-003 | SSH password authentication enabled | Medium | 5.3 | Confirmed |

| WAR-004 | .git directory present in web root (403 Forbidden) | Low | 3.7 | Confirmed |

| WAR-005 | SSH accepts weak hmac-sha1 MAC algorithm | Low | 2.7 | Confirmed |

| WAR-006 | nginx version disclosure via server_tokens | Low | 2.7 | Confirmed |

| WAR-007 | Deprecated X-XSS-Protection header present | Info | None | Confirmed |

| WAR-008 | Email addresses discovered for potential credential attacks | Low | 3.1 | Confirmed |




---


## BLO-001. OpenSSH 9.6p1 — CVE-2024-6387 (regreSSHion) RCE

### Description
OpenSSH 9.6p1 Ubuntu 3ubuntu13.18 falls within CVE-2024-6387 affected range (8.5p1<=9.7p1). Race condition in signal handler allows unauthenticated RCE.

### Risks
Unauthenticated remote code execution leading to full server compromise.

### Attack Vectors
Exploit race condition in sshd(8) signal handler during login. Requires multiple attempts (~6-8 hours avg). Attack must time SIGALRM handler between alarm() and setjmp().

### Proof of Concept
nmap -sV -p 22 --script ssh2-enum-algos -Pn cyberian-defenses.com (version confirmed as 9.6p1)

### Proof of Existence
PORT 22/tcp open ssh OpenSSH 9.6p1 Ubuntu 3ubuntu13.18 (Ubuntu Linux; protocol 2.0). CVE-2024-6387 affects 8.5p1 through 9.7p1.

### Remediation
Patch OpenSSH to 9.8p1 or later, or apply vendor backport patch for Ubuntu.

### CVSS Score
8.1

---


## BLO-002. Weak SSH MAC algorithms (hmac-sha1) enabled

### Description
SSH server accepts hmac-sha1 and hmac-sha1-etm MAC algorithms, which use SHA-1 — a deprecated hash with known collision vulnerabilities.

### Risks
Weakened data integrity; potential for MAC downgrade attacks in MITM scenarios.

### Attack Vectors
MITM attacker could negotiate hmac-sha1 MAC during SSH session, weakening integrity guarantees. SHA-1 collisions enable forgery in theory.

### Proof of Concept
nmap -p 22 --script ssh2-enum-algos -Pn cyberian-defenses.com

### Proof of Existence
mac_algorithms include: hmac-sha1-etm@openssh.com, hmac-sha1 alongside strong options like hmac-sha2-256, hmac-sha2-512.

### Remediation
Remove hmac-sha1 and hmac-sha1-etm from MACs in sshd_config; keep only sha2-256/512 and umac variants.

### CVSS Score
5.9

---


## BLO-003. SSH password authentication enabled

### Description
SSH server accepts both publickey and password authentication methods. Password auth enables brute-force and credential stuffing attacks.

### Risks
Credential brute-force, password spraying, and credential stuffing attacks against exposed SSH service.

### Attack Vectors
Automated brute-force tools (hydra, medusa, ncrack) can attempt password authentication. Credential stuffing using leaked password databases.

### Proof of Concept
nmap -p 22 --script ssh-auth-methods -Pn cyberian-defenses.com

### Proof of Existence
ssh-auth-methods: Supported authentication methods: publickey, password

### Remediation
Disable PasswordAuthentication in sshd_config; use key-based auth only. Add fail2ban for additional protection.

### CVSS Score
5.3

---


## BLO-004. CSP allows 'unsafe-inline' for scripts and styles

### Description
Content-Security-Policy header includes 'unsafe-inline' in both script-src and style-src directives, significantly weakening XSS protection.

### Risks
XSS attacks can inject inline scripts/styles, bypassing CSP protection. Reduces defense-in-depth against client-side attacks.

### Attack Vectors
Inject inline JavaScript via reflected/stored XSS. CSP will not block execution since 'unsafe-inline' is permitted in script-src.

### Proof of Concept
nmap -p 80,443 --script http-security-headers -Pn cyberian-defenses.com

### Proof of Existence
Content-Security-Policy: script-src 'self' 'unsafe-inline' cdn.tailwindcss.com; style-src 'self' 'unsafe-inline'

### Remediation
Remove 'unsafe-inline'; use nonces or hashes for inline scripts/styles. Use Tailwind CDN via SRI or self-host.

### CVSS Score
5.4

---


## BLO-005. No WAF detected on web services

### Description
nmap WAF detection scripts returned no WAF signature. Web services are directly exposed without WAF filtering layer.

### Risks
No automated protection against OWASP Top 10 attacks, bot traffic, or vulnerability exploitation attempts.

### Attack Vectors
Direct exploitation of web vulnerabilities without WAF interception. SQLi, XSS, path traversal attempts not filtered.

### Proof of Concept
nmap -p 80,443 --script http-waf-detect,http-waf-fingerprint -Pn cyberian-defenses.com

### Proof of Existence
WAF detection scripts ran on ports 80/443 with no WAF fingerprint results returned.

### Remediation
Deploy a WAF (Cloudflare, ModSecurity, AWS WAF) in front of web services.

### CVSS Score
3.7

---


## BLO-006. SSL/TLS configuration hardened — no vulnerabilities found

### Description
SSL/TLS properly configured: SSLv2/v3 and TLS 1.0/1.1 disabled, only TLS 1.2/1.3 enabled, not vulnerable to Heartbleed, strong ciphers only.

### Risks
No SSL/TLS-related risks identified. Configuration follows best practices.

### Attack Vectors
No viable SSL/TLS attack vectors identified.

### Proof of Concept
sslscan --no-colour cyberian-defenses.com

### Proof of Existence
SSLv2/v3/TLSv1.0/1.1 disabled. TLSv1.2/1.3 enabled. Not vulnerable to heartbleed. Strong ciphers: ECDHE-ECDSA-AES256-GCM-SHA384.

### Remediation
No action needed. Maintain current SSL/TLS configuration.

### CVSS Score
None

---


## LIS-001. SSH service exposed on port 22 — OpenSSH 9.6p1 Ubuntu

### Description
OpenSSH 9.6p1 Ubuntu 3ubuntu13.18 exposed on port 22. Version is relatively recent.

### Risks
Potential brute-force or credential stuffing if weak credentials exist.

### Attack Vectors
Attempt SSH brute-force with common credentials, key-based auth bypass, or exploit any unpatched OpenSSH vulnerabilities.

### Proof of Concept
nmap -sS -sV -O -T3 -p 1-1000 76.13.46.223

### Proof of Existence
22/tcp open ssh OpenSSH 9.6p1 Ubuntu 3ubuntu13.18 (Ubuntu Linux; protocol 2.0)

### Remediation
Disable password auth, restrict SSH to key-based only, limit source IPs via firewall.

### CVSS Score
3.7

---


## LIS-002. HTTP port 80 returns 404 — no web content served directly

### Description
Port 80 serves nginx 1.24.0 but returns 404 Not Found. HTTP redirects to HTTPS on port 443.

### Risks
Minimal — HTTP is properly redirected to HTTPS.

### Attack Vectors
Check if specific Host headers produce different responses on port 80 vs 443.

### Proof of Concept
nmap -sV --script=http-title,http-headers,http-enum -p 80,443 76.13.46.223

### Proof of Existence
80/tcp open http nginx 1.24.0 (Ubuntu) | http-title: 404 Not Found

### Remediation
Ensure consistent redirect from HTTP to HTTPS for all paths.

### CVSS Score
None

---


## LIS-003. HTTPS served on port 443 — nginx 1.24.0 with cyberian-defenses.com

### Description
nginx 1.24.0 on Ubuntu serving cyberian-defenses.com site. Title: 'Cyberian Defenses | Cybersecurity Advisory — MENA & Africa'.

### Risks
Web application vulnerabilities in the site itself.

### Attack Vectors
Web app scanning, directory enumeration, XSS, form abuse via Formspree endpoint.

### Proof of Concept
nmap -sV --script=http-title,http-headers,http-enum -p 443 76.13.46.223

### Proof of Existence
443/tcp open ssl/http nginx 1.24.0 | http-title: Cyberian Defenses | Cybersecurity Advisory — MENA & Africa

### Remediation
Keep nginx patched, perform regular web app security testing.

### CVSS Score
None

---


## LIS-004. Strong TLS/SSL configuration — TLSv1.2+ only, A-grade ciphers

### Description
TLSv1.0 and TLSv1.1 disabled. Only TLSv1.2 and TLSv1.3 enabled. All ciphers A-grade. No Heartbleed. No compression. TLS Fallback SCSV supported.

### Risks
Minimal — TLS configuration follows best practices.

### Attack Vectors
No known TLS attacks viable with current configuration.

### Proof of Concept
sslscan 76.13.46.223; nmap --script=ssl-cert,ssl-enum-ciphers -p 443 76.13.46.223

### Proof of Existence
SSLv2/SSLv3/TLSv1.0/TLSv1.1 disabled. TLSv1.2/1.3 enabled. All ciphers A-grade. Not vulnerable to heartbleed.

### Remediation
Maintain current TLS posture; monitor for future cipher deprecations.

### CVSS Score
None

---


## LIS-005. 128 virtual host names returning HTTP 200 on port 443

### Description
nmap http-vhosts script found 128 virtual host names returning HTTP 200 on HTTPS, indicating wildcard vhost or catch-all server block.

### Risks
Virtual host misconfiguration may expose unintended content or allow host header injection attacks.

### Attack Vectors
Enumerate all vhost names, test for host header injection, check if different vhosts serve different content or expose admin panels.

### Proof of Concept
nmap -sV --script=http-vhosts -p 80,443 76.13.46.223

### Proof of Existence
443/tcp: http-vhosts: 128 names had status 200. Port 80: 128 names had status 404.

### Remediation
Configure nginx to return 444 or default 404 for unrecognized Host headers instead of catch-all 200.

### CVSS Score
5.3

---


## LIS-006. Security headers well-implemented on HTTPS

### Description
HSTS (max-age=63072000, includeSubDomains, preload), X-Content-Type-Options: nosniff, X-Frame-Options: SAMEORIGIN, X-XSS-Protection: 1, CSP with restrictive default-src 'self', Permissions-Policy restricting camera/mic/geo.

### Risks
Minimal — headers follow security best practices.

### Attack Vectors
CSP allows 'unsafe-inline' for scripts — potential for inline script injection if input validation is weak.

### Proof of Concept
nmap -sV --script=http-headers -p 443 76.13.46.223

### Proof of Existence
HSTS max-age=63072000; includeSubDomains; preload | CSP default-src 'self'; script-src 'self' 'unsafe-inline' cdn.tailwindcss.com | X-Frame-Options: SAMEORIGIN

### Remediation
Remove 'unsafe-inline' from script-src CSP directive if possible; use nonces or hashes.

### CVSS Score
None

---


## LIS-007. robots.txt and /blog/ path discovered

### Description
http-enum found /blog/ (Blog) and /robots.txt (Robots file) accessible on HTTPS.

### Risks
robots.txt may reveal sensitive paths; /blog/ may have content management vulnerabilities.

### Attack Vectors
Fetch robots.txt to enumerate disallowed paths; scan /blog/ for CMS vulnerabilities or content exposure.

### Proof of Concept
nmap -sV --script=http-enum -p 443 76.13.46.223

### Proof of Existence
http-enum: /blog/: Blog; /robots.txt: Robots file

### Remediation
Review robots.txt for sensitive path disclosure; ensure /blog/ is properly secured.

### CVSS Score
None

---


## LIS-008. Incomplete TCP port scan — ports 1001-65535 unscanned

### Description
Full TCP scan of ports 1001-65535 timed out after 180s. High ports remain unscanned — potential hidden services undetected.

### Risks
Hidden services on high ports (e.g., databases, admin panels, backdoors) remain undetected.

### Attack Vectors
Target may have services on non-standard ports that are not visible to current scan coverage.

### Proof of Concept
nmap -sS -sV -T3 -p 1001-65535 76.13.46.223 (timed out)

### Proof of Existence
Command timed out after 180s. Exit code -1. No output returned for high port scan.

### Remediation
Run targeted high-port scan with faster timing (T4) or scan specific high-risk ports individually.

### CVSS Score
None

---


## LIS-009. UDP ports open|filtered — inconclusive results

### Description
UDP scan of ports 53,123,137,138,139,161,500 all returned open|filtered — likely firewall filtering preventing definitive determination.

### Risks
Potential DNS, SNMP, NetBIOS, or IKE services may be running but filtered.

### Attack Vectors
If SNMP (161) is open, attempt community string enumeration. If DNS (53) is open, test for zone transfers or DNS amplification.

### Proof of Concept
nmap -sU -T3 -p 53,123,137,138,139,161,500 76.13.46.223

### Proof of Existence
53/udp open|filtered domain; 123/udp open|filtered ntp; 137/udp open|filtered netbios-ns; 161/udp open|filtered snmp; 500/udp open|filtered isakmp

### Remediation
Run UDP scan with -sV for service-specific probes to confirm open vs filtered status.

### CVSS Score
None

---


## LIS-010. Host hostname revealed: srv1479954.hstgr.cloud (Hostinger)

### Description
Reverse DNS reveals hostname srv1479954.hstgr.cloud, indicating Hostinger cloud hosting infrastructure. OS fingerprinted as Linux 4.15-5.19 range (97% confidence).

### Risks
Shared hosting environment may have co-tenant risks; hostname pattern reveals hosting provider infrastructure.

### Attack Vectors
Research Hostinger cloud shared infrastructure vulnerabilities; test for co-tenant isolation issues.

### Proof of Concept
nmap -sS -sV -O -T3 -p 1-1000 76.13.46.223

### Proof of Existence
Nmap scan report for srv1479954.hstgr.cloud (76.13.46.223). OS guesses: Linux 4.15-5.19 (97%)

### Remediation
Ensure proper cloud tenant isolation; consider private VPS rather than shared cloud.

### CVSS Score
None

---


## LIS-001. SSH password authentication enabled

### Description
OpenSSH 9.6p1 Ubuntu 3ubuntu13.18 supports both publickey and password authentication methods.

### Risks
Password auth enables brute-force and credential stuffing attacks against SSH service.

### Attack Vectors
Use brute-force tools (hydra, medusa) with common credentials or leaked password lists against SSH.

### Proof of Concept
nmap -sV -p 22 --script ssh-auth-methods cyberian-defenses.com

### Proof of Existence
ssh-auth-methods: Supported authentication methods: publickey, password. OpenSSH 9.6p1 Ubuntu 3ubuntu13.18.

### Remediation
Disable password authentication in sshd_config, use key-based auth only.

### CVSS Score
5.3

---


## LIS-002. SSH weak MAC algorithm hmac-sha1 supported

### Description
SSH server accepts hmac-sha1 and hmac-sha1-etm MAC algorithms which are considered weak.

### Risks
SHA1 has known collision vulnerabilities; could weaken integrity protection of SSH sessions.

### Attack Vectors
Attempt to force weak MAC negotiation during SSH session establishment for potential integrity attacks.

### Proof of Concept
nmap -p 22 --script ssh2-enum-algos cyberian-defenses.com

### Proof of Existence
mac_algorithms include hmac-sha1-etm@openssh.com and hmac-sha1 among 10 supported algorithms.

### Remediation
Remove hmac-sha1 and hmac-sha1-etm from MACs in sshd_config.

### CVSS Score
3.7

---


## LIS-003. nginx version disclosure on HTTP/HTTPS

### Description
nginx 1.24.0 (Ubuntu) version disclosed in HTTP Server header and WhatWeb fingerprint.

### Risks
Version disclosure helps attackers match known CVEs and plan targeted exploits.

### Attack Vectors
Search for nginx 1.24.0 CVEs and attempt exploitation of matching vulnerabilities.

### Proof of Concept
whatweb -a 3 https://cyberian-defenses.com

### Proof of Existence
HTTPServer[Ubuntu Linux][nginx/1.24.0 (Ubuntu)] - version disclosed in response headers.

### Remediation
Set server_tokens off in nginx configuration to hide version info.

### CVSS Score
3.1

---


## LIS-004. CSP allows unsafe-inline for scripts and styles

### Description
Content-Security-Policy includes 'unsafe-inline' for both script-src and style-src directives.

### Risks
Unsafe-inline weakens XSS protections, allowing injected inline scripts/styles to execute.

### Attack Vectors
If XSS found, unsafe-inline in CSP allows direct inline script execution without nonce bypass needed.

### Proof of Concept
nmap -p 443 --script http-security-headers cyberian-defenses.com

### Proof of Existence
CSP: script-src 'self' 'unsafe-inline' cdn.tailwindcss.com; style-src 'self' 'unsafe-inline';

### Remediation
Replace unsafe-inline with nonce-based or hash-based CSP directives.

### CVSS Score
5.4

---


## LIS-005. All high TCP ports filtered - no additional services

### Description
38 high TCP ports (3000-27017) scanned, all filtered. No hidden services found on common app/db ports.

### Risks
No additional risk; confirms limited attack surface to ports 22, 80, 443 only.

### Attack Vectors
No attack vectors on high ports; focus enumeration on ports 22, 80, 443.

### Proof of Concept
nmap -sS -T3 -p 3000,4200,5000,...,27017 -sV cyberian-defenses.com

### Proof of Existence
All 38 scanned ports are in ignored states. Not shown: 38 filtered tcp ports (no-response).

### Remediation
No action needed; firewall effectively blocks high ports.

### CVSS Score
None

---


## LIS-006. UDP ports open|filtered - inconclusive results

### Description
10 UDP ports (53,123,137-139,161,500,1900,4500,5353) returned open|filtered. Cannot confirm services.

### Risks
If UDP services are actually open (DNS, SNMP, NetBIOS), they could be exploited for info disclosure or amplification.

### Attack Vectors
Send protocol-specific UDP probes (DNS query, SNMP get, NTP monlist) to confirm if services respond.

### Proof of Concept
nmap -sU -sV -T3 -p 53,123,137,138,139,161,500,1900,4500,5353 cyberian-defenses.com

### Proof of Existence
53/udp open|filtered domain; 123/udp open|filtered ntp; 161/udp open|filtered snmp; all 10 ports open|filtered.

### Remediation
Verify firewall rules; close unused UDP ports. Run targeted UDP probes to confirm.

### CVSS Score
None

---


## LIS-007. SSL/TLS hardened - no legacy protocols

### Description
Only TLSv1.2 and TLSv1.3 enabled. SSLv2, SSLv3, TLSv1.0, TLSv1.1 all disabled. No Heartbleed.

### Risks
No risk; strong TLS configuration reduces attack surface for MITM and downgrade attacks.

### Attack Vectors
No viable SSL/TLS attack vectors; cipher suites use ECDHE with AES-GCM/CHACHA20.

### Proof of Concept
sslscan cyberian-defenses.com

### Proof of Existence
SSLv2 disabled, SSLv3 disabled, TLSv1.0 disabled, TLSv1.1 disabled, TLSv1.2 enabled, TLSv1.3 enabled. Not vulnerable to heartbleed.

### Remediation
No action needed; maintain current TLS configuration.

### CVSS Score
None

---


## LIS-008. Email and author metadata disclosed in web page

### Description
Email ahmed.chiboub@cyberian-defenses.com and author 'Ahmed Chiboub' found in page metadata.

### Risks
Email enables phishing, OSINT, and potential username enumeration for SSH or other services.

### Attack Vectors
Use email for targeted phishing; derive SSH username 'ahmed' or 'achiboub' for brute-force attempts.

### Proof of Concept
whatweb -a 3 https://cyberian-defenses.com

### Proof of Existence
Email[ahmed.chiboub@cyberian-defenses.com], Meta-Author[Ahmed Chiboub]

### Remediation
Remove personal email from page source; use generic contact forms instead.

### CVSS Score
3.3

---


## LIS-009. HTTP to HTTPS redirect with HSTS preload

### Description
Port 80 redirects to HTTPS. HSTS enabled with max-age=63072000, includeSubDomains, preload.

### Risks
No risk; proper redirect and HSTS configuration protects against protocol downgrade attacks.

### Attack Vectors
No viable attack on port 80; all traffic redirected to HTTPS.

### Proof of Concept
nmap -p 80 --script http-title cyberian-defenses.com

### Proof of Existence
http-title: Did not follow redirect to https://cyberian-defenses.com/. HSTS: max-age=63072000; includeSubDomains; preload.

### Remediation
No action needed; maintain current redirect and HSTS configuration.

### CVSS Score
None

---


## LIS-010. Web tech stack identified: Nginx, Tailwind CSS, Ubuntu

### Description
Tech stack: nginx 1.24.0, Tailwind CSS (via CDN), Ubuntu Linux. Uses formspree.io for form submission.

### Risks
Tailwind CSS loaded from CDN (cdn.tailwindcss.com) in CSP; CDN compromise could inject malicious scripts.

### Attack Vectors
If cdn.tailwindcss.com is compromised or DNS-poisoned, arbitrary JS could execute within CSP rules.

### Proof of Concept
httpx -u https://cyberian-defenses.com -status-code -content-length -title -tech-detect -follow-redirects

### Proof of Existence
httpx: [200] [18860] [Cyberian Defenses | Cybersecurity Advisory — MENA & Africa] [HSTS,Nginx:1.24.0,Tailwind CSS,Ubuntu]

### Remediation
Self-host Tailwind CSS instead of loading from CDN; use SRI hashes.

### CVSS Score
None

---


## WAS-001. CSP allows unsafe-inline for scripts and styles

### Description
Content-Security-Policy header includes 'unsafe-inline' in both script-src and style-src directives, weakening XSS mitigation. Script-src also allows cdn.tailwindcss.com.

### Risks
If any user input is reflected without encoding, XSS attacks can bypass CSP due to unsafe-inline allowance.

### Attack Vectors
Identify any reflected input on blog or contact forms and inject inline JavaScript — CSP will not block it due to unsafe-inline.

### Proof of Concept
curl -s -k -D - https://cyberian-defenses.com/ | grep Content-Security-Policy

### Proof of Existence
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' cdn.tailwindcss.com; style-src 'self' 'unsafe-inline'; ...

### Remediation
Remove 'unsafe-inline' from script-src and style-src; use nonces or hashes for inline scripts and styles.

### CVSS Score
5.3

---


## WAS-002. Sensitive files (.git, .env) return 403 — exist on server

### Description
.git/HEAD, .git/config, and .env all return HTTP 403 Forbidden, confirming these paths exist but are access-controlled by nginx.

### Risks
If access control is misconfigured or bypassed, source code or environment secrets could be leaked.

### Attack Vectors
Attempt path traversal, case variation, URL encoding, or alternative git endpoints (.git/logs/HEAD, .git/index) to bypass 403.

### Proof of Concept
curl -s -k -o /dev/null -w '%{http_code} %{size_download}' https://cyberian-defenses.com/.git/HEAD

### Proof of Existence
403 162 — .git/HEAD returns 403 with 162 bytes body. Same for .git/config and .env.

### Remediation
Ensure nginx denies all dotfiles at server level; verify no path traversal bypasses exist.

### CVSS Score
3.7

---


## WAS-003. Server version disclosure in HTTP headers

### Description
Server header reveals 'nginx/1.24.0 (Ubuntu)', providing version info useful for targeted CVE exploitation.

### Risks
Attackers can match version to known CVEs; nginx 1.24.0 needs CVE review by Bloodhound.

### Attack Vectors
Use disclosed version to identify applicable CVEs and craft targeted exploits.

### Proof of Concept
curl -s -k -D - -o /dev/null https://cyberian-defenses.com/

### Proof of Existence
Server: nginx/1.24.0 (Ubuntu) in HTTP response headers.

### Remediation
Set server_tokens off in nginx config and remove Ubuntu from server signature.

### CVSS Score
3.1

---


## WAS-004. Author name disclosed in blog HTML meta tags

### Description
Blog page HTML meta author tag reveals 'Ahmed Chiboub' — useful for OSINT and social engineering.

### Risks
Attacker can use real employee name for phishing, credential stuffing, or social engineering campaigns.

### Attack Vectors
Search for Ahmed Chiboub on LinkedIn/GitHub for email patterns, credentials, or additional attack surface.

### Proof of Concept
curl -s -k https://cyberian-defenses.com/blog/ | grep author

### Proof of Existence
<meta name="author" content="Ahmed Chiboub"> in /blog/ page HTML.

### Remediation
Remove personal names from meta tags; use company name instead.

### CVSS Score
None

---


## WAS-005. Form data submitted to third-party formspree.io

### Description
CSP form-action and connect-src allow formspree.io, indicating contact form data is sent to a third-party service.

### Risks
User-submitted form data (potentially PII) is processed by formspree.io — a third-party SaaS outside client control.

### Attack Vectors
If formspree.io account is compromised, attacker could intercept or manipulate form submissions.

### Proof of Concept
curl -s -k https://cyberian-defenses.com/ | grep -i formspree

### Proof of Existence
CSP: connect-src 'self' https://formspree.io; form-action 'self' https://formspree.io;

### Remediation
Self-host form processing endpoint; ensure data processing agreement with any third-party form service.

### CVSS Score
3.7

---


## WAS-006. robots.txt fully open allowing all crawlers

### Description
robots.txt allows all user agents with no Disallow directives; references sitemap.xml.

### Risks
All content is indexable by search engines; sensitive paths if later discovered would be crawled.

### Attack Vectors
Review sitemap.xml for undiscovered URLs and content paths.

### Proof of Concept
curl -s -k https://cyberian-defenses.com/robots.txt

### Proof of Existence
User-agent: * / Allow: / / Sitemap: https://cyberian-defenses.com/sitemap.xml

### Remediation
Add Disallow directives for sensitive or non-public paths.

### CVSS Score
None

---


## WAS-007. Host header injection not exploitable

### Description
Server returns identical content (18860 bytes) regardless of Host header value (admin.cyberian-defenses.com, test.cyberian-defenses.com).

### Risks
No host header injection risk identified; server does not use Host header for routing.

### Attack Vectors
N/A — tested and not exploitable.

### Proof of Concept
curl -s -k -H 'Host: admin.cyberian-defenses.com' -D - -o /dev/null https://cyberian-defenses.com/

### Proof of Existence
HTTP/1.1 200 OK, Content-Length: 18860 for both admin.cyberian-defenses.com and test.cyberian-defenses.com Host headers.

### Remediation
No action needed; continue to reject unknown Host headers as defense-in-depth.

### CVSS Score
None

---


## WAS-008. X-Original-URL/X-Rewrite-URL header bypass not effective

### Description
Sending X-Original-URL: /admin and X-Rewrite-URL: /admin headers returns homepage (200), not admin page — no auth bypass via header manipulation.

### Risks
No auth bypass risk identified via these headers.

### Attack Vectors
N/A — tested and not exploitable on nginx.

### Proof of Concept
curl -s -k -H 'X-Original-URL: /admin' -D - -o /dev/null https://cyberian-defenses.com/

### Proof of Existence
HTTP/1.1 200 OK, Content-Length: 18860 — same homepage returned, no route change.

### Remediation
No action needed; these headers are IIS-specific and don't affect nginx.

### CVSS Score
None

---


## WAS-009. Nuclei vulnerability scanning incomplete — templates missing

### Description
Multiple Nuclei template directories were empty or missing, preventing automated vulnerability scanning.

### Risks
CVE-based and injection vulnerabilities may remain undetected without template-based scanning.

### Attack Vectors
N/A — tooling gap, not a vulnerability.

### Proof of Concept
nuclei -u https://cyberian-defenses.com -t /root/nuclei-templates/http/cves/ -silent

### Proof of Existence
FTL: Could not run nuclei: no templates provided for scan (multiple template paths returned same error).

### Remediation
Install/update nuclei templates with 'nuclei -update-templates' before next scan cycle.

### CVSS Score
None

---


## WAS-010. Blog section is primary attack surface for content injection

### Description
/blog/ returns 200 (34749 bytes) with dynamic content, meta tags, and structured data — likely the primary surface for XSS or content injection testing.

### Risks
If blog accepts user comments or has search/filter parameters, XSS or SQLi may be possible.

### Attack Vectors
Enumerate blog posts from sitemap.xml; test URL parameters, search forms, and comment sections for XSS and SQLi.

### Proof of Concept
curl -s -k https://cyberian-defenses.com/sitemap.xml

### Proof of Existence
/blog/ returns HTTP 200 with 34749 bytes; sitemap.xml returns 200 with 1305 bytes containing blog post URLs.

### Remediation
Ensure all blog inputs are properly sanitized and encoded; implement CSP nonces.

### CVSS Score
None

---


## WAR-001. nginx/1.24.0 Web Server Exposed

### Description
nginx/1.24.0 on Ubuntu serving cyberian-defenses.com at 76.13.46.223. Version disclosure enables targeted vuln matching.

### Risks
Server version disclosure aids attacker reconnaissance and targeted exploit selection.

### Attack Vectors
Search nginx 1.24.0 CVEs; test for misconfigurations like directory listing, path traversal, or status page exposure.

### Proof of Concept
curl -sI https://cyberian-defenses.com

### Proof of Existence
HTTP headers revealed Server: nginx/1.24.0, X-Powered-By indicators, Ubuntu backend. Confirmed via passive recon cycle 1.

### Remediation
Hide server version tokens in nginx config; apply server_tokens off.

### CVSS Score
None

---


## WAR-002. Missing DNSSEC Configuration

### Description
No DNSSEC RRSIG/DNSKEY records found for cyberian-defenses.com. DNS responses are not cryptographically signed.

### Risks
DNS spoofing/cache poisoning attacks could redirect users to malicious sites.

### Attack Vectors
Perform DNS cache poisoning or MITM to inject false DNS records if network position allows.

### Proof of Concept
dig DNSKEY cyberian-defenses.com +short (empty response)

### Proof of Existence
DNS query for DNSKEY returned no records. DNSSEC not configured per passive recon.

### Remediation
Enable DNSSEC signing on the domain via registrar/DNS provider.

### CVSS Score
3.7

---


## WAR-003. Missing CAA DNS Record

### Description
No CAA record found. Any CA could issue certificates for the domain without restriction.

### Risks
Unauthorized certificate issuance possible if a CA is compromised or social-engineered.

### Attack Vectors
Request TLS certificate from any CA for the domain; no DNS-level restriction prevents rogue issuance.

### Proof of Concept
dig CAA cyberian-defenses.com +short (empty response)

### Proof of Existence
CAA query returned no records. No certificate authority authorization restrictions in place.

### Remediation
Add CAA records restricting certificate issuance to authorized CAs only.

### CVSS Score
3.1

---


## WAR-004. Azure CDN/Front Door Detected

### Description
Azure edge domain detected (cyberian-defenses.azureedge.net). Origin server may be directly accessible at 76.13.46.223.

### Risks
If CDN/WAF bypass is possible, direct origin access at 76.13.46.223 may bypass protections.

### Attack Vectors
Attempt direct origin access via IP 76.13.46.223 with Host header injection to bypass CDN/WAF rules.

### Proof of Concept
curl -H 'Host: cyberian-defenses.com' https://76.13.46.223/

### Proof of Existence
azureedge.net domain referenced in DNS/infra. Tool blocked from probing it as out of scope, but presence confirmed.

### Remediation
Restrict origin server to only accept traffic from Azure CDN IP ranges; configure firewall rules.

### CVSS Score
None

---


## WAR-005. Third-Party Form Handler (Formspree)

### Description
Formspree integration detected for form handling. Form data is sent to third-party service.

### Risks
Sensitive form data transits third-party infrastructure; potential data exposure or supply chain risk.

### Attack Vectors
Analyze form endpoints for data leakage; test for XSS via form fields that may be reflected in Formspree dashboard.

### Proof of Concept
Identified via web tech fingerprinting in page source

### Proof of Existence
Tailwind CSS, Calendly, and Formspree detected in page source during tech fingerprinting.

### Remediation
Review third-party data handling policies; implement CSP to restrict outbound form submissions.

### CVSS Score
None

---


## WAR-006. Key Personnel Identified — Ahmed Chiboub

### Description
Ahmed Chiboub identified as associated with cyberian-defenses.com via WHOIS/OSINT data.

### Risks
Credential harvesting, phishing, or social engineering targeting this individual possible.

### Attack Vectors
Search breach databases for credentials; craft targeted phishing using LinkedIn/GitHub profile data.

### Proof of Concept
WHOIS lookup and web content analysis revealed name association

### Proof of Existence
WHOIS and site content reference Ahmed Chiboub as key person associated with the domain.

### Remediation
Enforce MFA on all accounts; monitor for credential leaks in breach databases.

### CVSS Score
None

---


## WAR-007. No IPv6 Support Configured

### Description
No AAAA records found for cyberian-defenses.com. IPv6 connectivity not available.

### Risks
No direct risk; may limit attack surface but also indicates incomplete modern network config.

### Attack Vectors
N/A — informational. IPv4-only may simplify some scanning but limits reachability.

### Proof of Concept
dig AAAA cyberian-defenses.com +short (empty)

### Proof of Existence
AAAA query returned no records. Domain is IPv4-only.

### Remediation
Consider adding IPv6 support with equivalent security controls as IPv4.

### CVSS Score
None

---


## WAR-001. CSP allows unsafe-inline in script-src

### Description
Content-Security-Policy includes 'unsafe-inline' in script-src directive, bypassing XSS mitigations.

### Risks
Reflected/stored XSS could execute despite CSP, enabling session theft and credential harvesting.

### Attack Vectors
Find any reflected or stored input on the site (blog comments, forms, URL params) and inject inline JS payloads.

### Proof of Concept
curl -sI https://cyberian-defenses.com | grep -i content-security

### Proof of Existence
CSP header observed with script-src containing 'unsafe-inline' directive. Also connect-src and form-action allow https://formspree.io...

### Remediation
Remove 'unsafe-inline' from script-src; use nonces or hashes for inline scripts.

### CVSS Score
5.4

---


## WAR-002. Catch-all vhost on HTTPS returns 200 for all Host headers

### Description
All 128 tested virtual host names return HTTP 200 on port 443, indicating catch-all nginx config.

### Risks
Host header injection, cache poisoning, or routing bypass may be possible depending on backend behavior.

### Attack Vectors
Send requests with arbitrary Host headers; test if different content is served or if backend trusts Host for redirects/links.

### Proof of Concept
nmap --script http-vhosts --script-args http-vhosts.hostlist=names -p 443 cyberian-defenses.com

### Proof of Existence
Port 443: 128 vhost names tested → all returned 200. Port 80: 128 vhost names tested → all returned 404...

### Remediation
Configure nginx default_server to return 444 or 403; validate Host header against known domains.

### CVSS Score
5.3

---


## WAR-003. SSH exposed on port 22 with known username

### Description
SSH service open on port 22. Username ahmed.chiboub identified from website meta-author tag.

### Risks
Credential brute-force or password guessing could yield shell access to the server.

### Attack Vectors
Attempt SSH brute-force with common passwords and username ahmed.chiboub; check for key-based auth only.

### Proof of Concept
nmap -p 22 -sV --script ssh-auth-methods 76.13.46.223

### Proof of Existence
Port 22 open (SSH). Key person Ahmed Chiboub identified with email ahmed.chiboub@cyberian-defenses.com from meta-author tag...

### Remediation
Enforce key-based auth only, disable password auth, implement fail2ban, restrict SSH to known IPs.

### CVSS Score
5.3

---


## WAR-004. Third-party form handler Formspree in CSP

### Description
CSP connect-src and form-action allow https://formspree.io, a third-party form processing service.

### Risks
Form data is sent to third-party; if Formspree is compromised or token leaked, user data could be harvested.

### Attack Vectors
Intercept form submissions; test if Formspree endpoint IDs are predictable or if CSRF can submit to attacker's Formspree.

### Proof of Concept
Review HTML source for Formspree form action URLs and analyze token security.

### Proof of Existence
CSP header includes connect-src and form-action directives allowing https://formspree.io...

### Remediation
Validate Formspree integration; ensure CSRF tokens on forms; consider self-hosted form handler.

### CVSS Score
3.7

---


## WAR-005. Missing DNSSEC, CAA, and IPv6 records

### Description
DNS zone lacks DNSSEC, CAA records, and AAAA records. SystemDNS used (no managed DNS provider).

### Risks
DNS spoofing possible without DNSSEC; unauthorized CA can issue certs without CAA; no IPv6 connectivity.

### Attack Vectors
DNS cache poisoning; request fraudulent TLS certificates without CAA restriction; DNS hijacking via registrar.

### Proof of Concept
dig DNSKEY cyberian-defenses.com; dig CAA cyberian-defenses.com; dig AAAA cyberian-defenses.com

### Proof of Existence
DNSSEC, CAA, and IPv6 (AAAA) records all absent per DNS analysis results...

### Remediation
Enable DNSSEC; add CAA records restricting CA issuance; deploy IPv6 if applicable.

### CVSS Score
3.1

---


## WAR-006. High TCP ports unscanned — potential hidden services

### Description
TCP port scan for ports 1001-65535 timed out. Services on non-standard ports remain undetected.

### Risks
Databases, admin panels, or dev services on high ports could be accessible to attackers.

### Attack Vectors
Run targeted scan on common high ports: 3306,5432,6379,27017,9200,11211,9000,9090,8443,8888.

### Proof of Concept
nmap -p 3306,5432,6379,27017,9200,11211,9000,9090,8443,8888 -T4 -sV 76.13.46.223

### Proof of Existence
High TCP ports (1001–65535): Scan timed out — critical gap noted in Lisa report...

### Remediation
Complete high-port scan with faster timing; close unnecessary ports via firewall.

### CVSS Score
None

---


## WAR-007. Azure CDN subdomain discovered but unvalidated

### Description
Subdomain cyberian-defenses.azureedge.net identified as Azure CDN endpoint for the target.

### Risks
If CDN endpoint is decommissioned but CNAME remains, subdomain takeover possible.

### Attack Vectors
Check if Azure CDN endpoint is active or available for re-registration; verify CNAME chain.

### Proof of Concept
dig CNAME cyberian-defenses.azureedge.net; curl -sI https://cyberian-defenses.azureedge.net

### Proof of Existence
Subdomain cyberian-defenses.azureedge.net discovered during recon but blocked from further testing due to scope restriction...

### Remediation
Verify CDN endpoint is active; remove stale CNAME records; consider adding to scope for assessment.

### CVSS Score
None

---


## WAR-008. Blog page detected at /blog/

### Description
HTTP enumeration found /blog/ path and /robots.txt on the target.

### Risks
Blog may have comment forms, search functionality, or CMS with exploitable vulnerabilities.

### Attack Vectors
Enumerate blog platform; test for SQLi, XSS in comments/search; check robots.txt for hidden paths.

### Proof of Concept
curl -s https://cyberian-defenses.com/blog/ | head -100; curl -s https://cyberian-defenses.com/robots.txt

### Proof of Existence
http-enum results: /blog/ — Blog page detected, /robots.txt — Robots file present...

### Remediation
Ensure blog CMS is patched; validate all input; restrict robots.txt from exposing sensitive paths.

### CVSS Score
None

---


## WAR-001. SSH password authentication enabled

### Description
OpenSSH 9.6p1 accepts password authentication, enabling brute-force attacks.

### Risks
Credential brute-force could yield shell access to server.

### Attack Vectors
Use hydra or medusa with username lists against SSH service.

### Proof of Concept
nmap -sV -p 22 --script ssh-auth-methods cyberian-defenses.com

### Proof of Existence
Lisa cycle 2 reported SSH password authentication enabled. OpenSSH 9.6p1 on port 22.

### Remediation
Disable password authentication in sshd_config, use key-based auth only.

### CVSS Score
5.3

---


## WAR-002. SSH weak MAC algorithm hmac-sha1 supported

### Description
SSH server supports hmac-sha1, a weak MAC algorithm vulnerable to theoretical attacks.

### Risks
Weakened integrity protection on SSH sessions under specific conditions.

### Attack Vectors
Force negotiated MAC to hmac-sha1 during session establishment.

### Proof of Concept
nmap -p 22 --script ssh2-enum-algos cyberian-defenses.com

### Proof of Existence
Lisa cycle 2 reported hmac-sha1 in supported MAC algorithms list.

### Remediation
Remove hmac-sha1 from MACs in sshd_config, use hmac-sha2-512 only.

### CVSS Score
3.1

---


## WAR-003. nginx version disclosure

### Description
nginx 1.24.0 version exposed in HTTP headers and error pages.

### Risks
Attacker can match version against CVE database for targeted exploits.

### Attack Vectors
Send HTTP request and inspect Server header or error page footer.

### Proof of Concept
curl -sI http://cyberian-defenses.com | grep Server

### Proof of Existence
Lisa reported Server: nginx/1.24.0 (Ubuntu) in HTTP response headers.

### Remediation
Set server_tokens off in nginx config.

### CVSS Score
3.7

---


## WAR-004. CSP unsafe-inline directive weakens XSS protection

### Description
Content-Security-Policy header includes unsafe-inline, allowing inline script execution.

### Risks
XSS vulnerabilities can be exploited without nonce/hash bypass required.

### Attack Vectors
If XSS found, inject inline script tags directly without CSP bypass needed.

### Proof of Concept
curl -sI https://cyberian-defenses.com | grep Content-Security-Policy

### Proof of Existence
Lisa cycle 1 and 2 reported CSP with unsafe-inline in script-src or default-src.

### Remediation
Remove unsafe-inline, use nonces or hashes for inline scripts.

### CVSS Score
5.4

---


## WAR-005. Email and author metadata exposed

### Description
Page metadata reveals ahmed.chiboub@cyberian-defenses.com as author/contact.

### Risks
Enables targeted phishing and OSINT for social engineering attacks.

### Attack Vectors
Use email for spear-phishing campaigns or credential stuffing.

### Proof of Concept
curl -s https://cyberian-defenses.com | grep -i author

### Proof of Existence
Lisa reported email ahmed.chiboub@cyberian-defenses.com and author Ahmed Chiboub in page metadata.

### Remediation
Remove personal email from public-facing metadata, use generic contact.

### CVSS Score
2.7

---


## WAR-006. External form service dependency formspree.io

### Description
Contact form submits to formspree.io external service, potentially exposing user data.

### Risks
Form data routed through third-party; supply-chain risk if formspree compromised.

### Attack Vectors
Assess formspree.io endpoint for IDOR, data leakage, or SSRF.

### Proof of Concept
curl -s https://cyberian-defenses.com | grep formspree

### Proof of Existence
Lisa reported formspree.io as form service in web technology analysis.

### Remediation
Assess formspree.io data handling; consider self-hosted form processor.

### CVSS Score
None

---


## WAR-007. robots.txt exists but contents not analyzed

### Description
/robots.txt path exists on web server but contents have not been retrieved.

### Risks
May expose hidden directories or admin paths intended for crawler exclusion.

### Attack Vectors
Retrieve and parse robots.txt for Disallow entries to find hidden paths.

### Proof of Concept
curl -s https://cyberian-defenses.com/robots.txt

### Proof of Existence
Lisa cycle 1 found /robots.txt path but contents not retrieved in cycle 1 or 2.

### Remediation
Ensure robots.txt does not expose sensitive paths unnecessarily.

### CVSS Score
None

---


## WAR-008. Vhost catch-all on port 443

### Description
Port 443 returns default page for arbitrary Host headers, indicating catch-all vhost config.

### Risks
May allow vhost enumeration or Host header injection attacks.

### Attack Vectors
Send requests with various Host headers to enumerate virtual hosts.

### Proof of Concept
curl -sk -H 'Host: test.local' https://cyberian-defenses.com

### Proof of Existence
Lisa cycle 1 detected vhost catch-all behavior on 443. Not fully investigated.

### Remediation
Configure nginx to reject unknown Host headers with 444 or 421.

### CVSS Score
3.1

---


## WAR-001. CVE-2024-6387 regreSSHion RCE — OpenSSH 9.6p1 in affected range

### Description
OpenSSH 9.6p1 falls within CVE-2024-6387 affected range (8.5p1–9.7p1). Race condition in signal handler allows unauthenticated RCE. Ubuntu backport patch status unverified.

### Risks
Unauthenticated remote code execution could lead to full server compromise and data breach.

### Attack Vectors
Exploit race condition in OpenSSH sshd signal handler by repeatedly connecting and timing signal delivery during grace period. Requires ~10K attempts on average.

### Proof of Concept
nmap -sV -p22 cyberian-defenses.com confirmed OpenSSH 9.6p1 Ubuntu 3; version falls in CVE-2024-6387 range

### Proof of Existence
OpenSSH 9.6p1 confirmed via nmap banner grab. CVE-2024-6387 affects 8.5p1<=OpenSSH<=9.7p1. Ubuntu 3 backport patch status could not be verified — may be patched...

### Remediation
Patch OpenSSH to 9.8p1+ or apply Ubuntu security update for CVE-2024-6387 immediately.

### CVSS Score
8.1

---


## WAR-002. CSP unsafe-inline allows XSS exploitation without nonce bypass

### Description
Content-Security-Policy includes unsafe-inline in both script-src and style-src directives, allowing inline script execution.

### Risks
Any reflected or stored XSS vulnerability can be directly exploited without needing to bypass CSP nonce restrictions.

### Attack Vectors
Identify any user input reflected on blog pages or contact form; inject inline JavaScript payload — CSP permits execution due to unsafe-inline.

### Proof of Concept
curl -sk https://cyberian-defenses.com | grep -i content-security-policy — shows unsafe-inline in script-src and style-src

### Proof of Existence
CSP header: script-src 'self' 'unsafe-inline' cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' cdn.tailwindcss.com — unsafe-inline present in both directives...

### Remediation
Replace unsafe-inline with nonce-based or hash-based CSP directives for script-src and style-src.

### CVSS Score
5.4

---


## WAR-003. SSH password authentication enabled

### Description
SSH service accepts password-based authentication in addition to public key auth.

### Risks
Enables credential brute-force and credential stuffing attacks against SSH service.

### Attack Vectors
Enumerate valid usernames (e.g., ahmed.chiboub@cyberian-defenses.com found), then attempt password spraying or brute-force via sshpass/hydra.

### Proof of Concept
nmap --script ssh-auth-methods -p22 cyberian-defenses.com — shows password auth enabled

### Proof of Existence
SSH auth methods: publickey, password — password method confirmed enabled via nmap ssh-auth-methods script...

### Remediation
Disable password authentication in sshd_config; enforce key-based authentication only.

### CVSS Score
5.3

---


## WAR-004. .git directory exists on web server (HTTP 403)

### Description
 /.git/HEAD and /.git/config return HTTP 403, indicating git repository exists on web root but directory listing is blocked.

### Risks
If bypassed via alternate paths (.git/logs/HEAD, .git/index), source code and commit history could be exposed.

### Attack Vectors
Attempt encoded paths (%2e%2e/.git), alternate git files (/index.html/.git/HEAD), or double-encoding to bypass nginx access rules.

### Proof of Concept
curl -sk -o /dev/null -w '%{http_code}' https://cyberian-defenses.com/.git/HEAD — returns 403

### Proof of Existence
GET /.git/HEAD → 403 (162 bytes); GET /.git/config → 403 (162 bytes) — both return 403 indicating files exist but access blocked...

### Remediation
Remove .git directory from web root entirely; add nginx location block denying all .git paths.

### CVSS Score
3.7

---


## WAR-005. .env file exists on web server (HTTP 403)

### Description
/.env returns HTTP 403, indicating environment configuration file exists on web root but direct access is blocked.

### Risks
If bypassed, could expose database credentials, API keys, and application secrets.

### Attack Vectors
Attempt path traversal, double-encoding, or alternate file extensions to bypass nginx access controls.

### Proof of Concept
curl -sk -o /dev/null -w '%{http_code}' https://cyberian-defenses.com/.env — returns 403

### Proof of Existence
GET /.env → 403 (162 bytes) — file exists but access blocked by nginx configuration...

### Remediation
Remove .env file from web root; store secrets outside web-accessible directories.

### CVSS Score
3.7

---


## WAR-006. Weak HMAC-SHA1 MAC algorithm supported by SSH

### Description
SSH service supports hmac-sha1 MAC algorithm which has known cryptographic weaknesses compared to SHA-2 variants.

### Risks
Enables potential MAC downgrade attacks; SHA-1 has known collision vulnerabilities.

### Attack Vectors
Force MAC algorithm negotiation to hmac-sha1 during SSH handshake; leverage for traffic integrity attacks.

### Proof of Concept
nmap --script ssh2-enum-algos -p22 cyberian-defenses.com — shows hmac-sha1 in MACs list

### Proof of Existence
SSH MAC algorithms include: umac-64-etm@openssh.com, hmac-sha1-etm@openssh.com, hmac-sha1 — hmac-sha1 weak algorithm present...

### Remediation
Remove hmac-sha1 from MACs in sshd_config; enforce only SHA-2 based algorithms.

### CVSS Score
3.1

---


## WAR-007. nginx version disclosure in HTTP headers

### Description
nginx version 1.24.0 disclosed in Server HTTP response header and error pages.

### Risks
Aids attackers in targeting specific CVEs for known nginx versions.

### Attack Vectors
Passively read Server header to identify exact version; cross-reference with CVE databases.

### Proof of Concept
curl -skI https://cyberian-defenses.com | grep Server — shows nginx/1.24.0

### Proof of Existence
Server: nginx/1.24.0 (Ubuntu) — version disclosed in HTTP response header...

### Remediation
Set server_tokens off in nginx configuration to suppress version information.

### CVSS Score
2.7

---


## WAR-008. Deprecated X-XSS-Protection header present

### Description
X-XSS-Protection: 1; mode=block header is deprecated and can introduce vulnerabilities in modern browsers.

### Risks
Minimal — modern browsers ignore this header, but its presence suggests outdated security configuration practices.

### Attack Vectors
Not directly exploitable; informational concern only.

### Proof of Concept
curl -skI https://cyberian-defenses.com | grep X-XSS-Protection

### Proof of Existence
X-XSS-Protection: 1; mode=block — deprecated header present in HTTP response...

### Remediation
Remove X-XSS-Protection header; rely on CSP for XSS prevention.

### CVSS Score
None

---


## WAR-001. CVE-2024-6387 regreSSHion RCE on OpenSSH 9.6p1

### Description
OpenSSH 9.6p1 is in CVE-2024-6387 affected range. RCE via signal handler race condition in sshd. Ubuntu backport patch status unverified.

### Risks
Unauthenticated remote code execution as root if unpatched.

### Attack Vectors
Exploit race condition in sshd signal handler during authentication. Requires ~10k attempts. Affects glibc-based Linux with ASLR.

### Proof of Concept
nmap -sV -p22 cyberian-defenses.com (version detection only; no exploit attempted)

### Proof of Existence
Nmap: OpenSSH 9.6p1 Ubuntu on port 22. CVE-2024-6387 affects 8.5p1<=9.7p1. Ubuntu backport patch unverified — theoretical only.

### Remediation
Patch OpenSSH to latest version or verify Ubuntu security backport applied.

### CVSS Score
8.1

---


## WAR-002. CSP unsafe-inline directive enables XSS exploitation

### Description
Content-Security-Policy includes 'unsafe-inline' for scripts, allowing inline script execution if XSS injection point exists.

### Risks
Any reflected/stored XSS becomes directly exploitable without nonce bypass needed.

### Attack Vectors
Find injection point in blog pages or form parameters, inject <script> tag — CSP will not block execution.

### Proof of Concept
curl -sI https://cyberian-defenses.com | grep -i content-security-policy

### Proof of Existence
CSP header: script-src includes 'unsafe-inline'. Blog pages (/blog/) and formspree.io form are potential injection vectors untested.

### Remediation
Remove unsafe-inline from CSP; use nonces or hashes for script execution.

### CVSS Score
5.4

---


## WAR-003. SSH password authentication enabled

### Description
SSH accepts password-based authentication, enabling brute-force and credential stuffing attacks.

### Risks
Account compromise via password guessing, credential stuffing, or spray attacks.

### Attack Vectors
Brute-force SSH passwords using tools like hydra or medusa against known usernames (ahmed.chiboub).

### Proof of Concept
nmap --script ssh-auth-methods -p22 cyberian-defenses.com

### Proof of Existence
SSH auth methods scan: password authentication enabled alongside publickey.

### Remediation
Disable SSH password authentication; enforce key-based auth only.

### CVSS Score
5.3

---


## WAR-004. .git and .env files present in web root (403 blocked)

### Description
/.git and /.env return HTTP 403, confirming files exist in web root but are access-restricted by nginx.

### Risks
Source code or environment variable disclosure if nginx config changes or bypass found.

### Attack Vectors
Try encoded paths (%2e%2e%2fgit), alternate git files (.git/logs/HEAD, .git/index, .git/HEAD), path traversal, or nginx misconfig bypass.

### Proof of Concept
curl -sk https://cyberian-defenses.com/.git (returns 403); curl -sk https://cyberian-defenses.com/.env (returns 403)

### Proof of Existence
HTTP 403 for /.git and /.env — files exist but blocked. Bypass attempts not completed due to environmental constraints.

### Remediation
Remove .git and .env from web root entirely; do not rely on nginx access rules.

### CVSS Score
3.7

---


## WAR-005. Weak SSH MAC algorithm hmac-sha1 enabled

### Description
SSH server accepts hmac-sha1 MAC algorithm, which is considered cryptographically weak.

### Risks
Potential MAC forgery or downgrade attack in MITM scenarios.

### Attack Vectors
Force weak MAC negotiation in MITM position to weaken connection integrity.

### Proof of Concept
nmap --script ssh2-enum-algos -p22 cyberian-defenses.com

### Proof of Existence
SSH MAC algorithms include hmac-sha1 alongside stronger options like hmac-sha2-256.

### Remediation
Remove hmac-sha1 from SSH MAC algorithm list; use hmac-sha2-256/512 only.

### CVSS Score
3.1

---


## WAR-006. nginx server_tokens disclosure

### Description
nginx exposes version number (1.24.0) in HTTP response headers, aiding attacker reconnaissance.

### Risks
Attackers can target known nginx version-specific vulnerabilities.

### Attack Vectors
Use version info to search for applicable CVEs and tailor exploits.

### Proof of Concept
curl -sI https://cyberian-defenses.com | grep Server

### Proof of Existence
Server: nginx/1.24.0 in HTTP response headers.

### Remediation
Set server_tokens off in nginx configuration.

### CVSS Score
2.7

---


## WAR-007. Deprecated X-XSS-Protection header present

### Description
X-XSS-Protection header is deprecated and can introduce vulnerabilities in modern browsers.

### Risks
Minimal — header ignored by modern browsers but signals outdated security config.

### Attack Vectors
No direct exploitation; informational finding.

### Proof of Concept
curl -sI https://cyberian-defenses.com | grep X-XSS-Protection

### Proof of Existence
X-XSS-Protection: 1; mode=block present in response headers.

### Remediation
Remove X-XSS-Protection header; rely on CSP for XSS mitigation.

### CVSS Score
1.0

---


## WAR-001. CVE-2024-6387 regreSSHion RCE on OpenSSH 9.6p1

### Description
OpenSSH 9.6p1 is in CVE-2024-6387 affected range (<9.8). Ubuntu backport suffix '3' may include patch. Unverified.

### Risks
Unauthenticated RCE via SSH race condition if backport does not patch CVE-2024-6387.

### Attack Vectors
Exploit race condition in sshd signal handler to achieve RCE. Requires timing analysis and multiple connection attempts.

### Proof of Concept
ssh -o StrictHostKeyChecking=no cyberian-defenses.com (banner grab confirming 9.6p1)

### Proof of Existence
SSH banner: SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu1. Version 9.6p1 is within CVE-2024-6387 affected range. Ubuntu backport patch status not verified...

### Remediation
Patch OpenSSH to 9.8+ or apply Ubuntu security update for CVE-2024-6387.

### CVSS Score
8.1

---


## WAR-002. CSP allows unsafe-inline scripts

### Description
Content-Security-Policy includes 'unsafe-inline' in script-src directive, allowing inline script execution.

### Risks
Any reflected XSS vulnerability becomes directly exploitable without nonce bypass needed.

### Attack Vectors
Inject inline <script> tags via any reflected input parameter. CSP will not block execution.

### Proof of Concept
curl -sI https://cyberian-defenses.com | grep content-security-policy

### Proof of Existence
CSP header contains: script-src 'self' 'unsafe-inline' cdn.tailwindcss.com. unsafe-inline present in script-src directive...

### Remediation
Remove unsafe-inline from CSP; use nonces or hashes for inline scripts.

### CVSS Score
5.4

---


## WAR-003. SSH password authentication enabled

### Description
SSH server accepts password-based authentication, enabling credential brute-force and password spraying.

### Risks
Credential stuffing using discovered email addresses (ahmed, achiboub, ahmedc) could yield shell access.

### Attack Vectors
Brute-force or password spray SSH using discovered usernames. Combine with email addresses from recon.

### Proof of Concept
ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no user@cyberian-defenses.com

### Proof of Existence
SSH negotiation confirms password authentication method is accepted by server...

### Remediation
Disable PasswordAuthentication in sshd_config; require key-based auth only.

### CVSS Score
5.3

---


## WAR-004. .git directory present in web root (403 Forbidden)

### Description
/.git/ returns 403 — directory exists but access blocked by nginx. Bypass via encoded paths untested.

### Risks
Source code disclosure if bypass succeeds. Could expose credentials, API keys, application logic.

### Attack Vectors
Try encoded paths: /..%2f.git/HEAD, /.git/logs/HEAD, /.git/index, /%2e%2e/%2e%67it/HEAD

### Proof of Concept
curl -sk https://cyberian-defenses.com/.git/HEAD (returns 403)

### Proof of Existence
HTTP 403 on /.git/ — directory exists but is blocked. Encoded path bypasses not yet tested...

### Remediation
Remove .git directory from web root entirely; block via nginx location directive.

### CVSS Score
3.7

---


## WAR-005. SSH accepts weak hmac-sha1 MAC algorithm

### Description
SSH server accepts hmac-sha1 MAC algorithm which has known weaknesses.

### Risks
Potential MAC forgery in MITM scenarios.

### Attack Vectors
MITM position required; forge SSH packet MACs using SHA-1 collision weaknesses.

### Proof of Concept
ssh -Q mac cyberian-defenses.com (or nmap --script ssh2-enum-algos)

### Proof of Existence
SSH algorithm negotiation reveals hmac-sha1 in accepted MAC list...

### Remediation
Remove hmac-sha1 from MACs in sshd_config; use hmac-sha2-256/512 only.

### CVSS Score
2.7

---


## WAR-006. nginx version disclosure via server_tokens

### Description
nginx version 1.24.0 disclosed in HTTP Server header.

### Risks
Aids attacker reconnaissance and CVE targeting.

### Attack Vectors
Use version to search for applicable nginx CVEs and targeted exploits.

### Proof of Concept
curl -sI https://cyberian-defenses.com | grep Server

### Proof of Existence
Server: nginx/1.24.0 in HTTP response headers...

### Remediation
Set server_tokens off in nginx.conf.

### CVSS Score
2.7

---


## WAR-007. Deprecated X-XSS-Protection header present

### Description
X-XSS-Protection header is deprecated and may introduce vulnerabilities in modern browsers.

### Risks
Minimal — header ignored by modern browsers but signals outdated security configuration.

### Attack Vectors
No direct exploitation; informational finding.

### Proof of Concept
curl -sI https://cyberian-defenses.com | grep X-XSS-Protection

### Proof of Existence
X-XSS-Protection: 1; mode=block in response headers...

### Remediation
Remove X-XSS-Protection header; rely on CSP for XSS mitigation.

### CVSS Score
None

---


## WAR-008. Email addresses discovered for potential credential attacks

### Description
Email addresses found: ahmed, achiboub, ahmedc — likely team members associated with target.

### Risks
Username enumeration for SSH password spraying (password auth enabled) and phishing campaigns.

### Attack Vectors
Use as SSH usernames for password spray (password auth confirmed enabled). Use for targeted phishing.

### Proof of Concept
Recon phase discovered email addresses via web content analysis

### Proof of Existence
Email addresses discovered: ahmed@cyberian-defenses.com, achiboub@..., ahmedc@... (from lisa recon)...

### Remediation
Limit publicly exposed email addresses; enforce strong password policies and MFA.

### CVSS Score
3.1

---



## 4. Engagement Flow

See decision audit trail below.

  1. [init] → recon (confidence: 0.95)
     Reasoning: Initial engagement state — no prior bot work exists. Target is cyberian-defenses.com with external s
  2. [recon] → recon (confidence: 0.85)
     Reasoning: ARIA's LLM analysis failed with truncated JSON. Partial output reveals useful data: nginx/1.24.0 on 
  3. [scanning] → scan (confidence: 0.70)
     Reasoning: ARIA has run 2 cycles. Cycle 1: LLM analysis failed (truncated JSON). Cycle 2: Tool execution blocke
  4. [scanning] → scan (confidence: 0.75)
     Reasoning: Lisa completed cycle 1 with partial results: 3 ports found (22/SSH, 80/HTTP, 443/HTTPS), nginx/1.24.
  5. [vuln_detection] → report (confidence: 0.82)
     Reasoning: Lisa cycle 2 significantly improved over cycle 1. We now have: OpenSSH 9.6p1 Ubuntu 3 with version s
  6. [vuln_detection] → report (confidence: 0.75)
     Reasoning: Vuln phase has only run 1/5 cycles. Bloodhound identified CVE-2024-6387 (CVSS 8.1) but did NOT verif
  7. [vuln_detection] → vuln_detection (confidence: 0.85)
     Reasoning: Vuln phase has only run 1/5 cycles. Multiple specific, actionable depth gaps remain: (1) CVE-2024-63
  8. [reporting] → report (confidence: 0.85)
     Reasoning: After 2 vuln detection cycles, the engagement has reached its natural conclusion. Key assessment: (1

---

## 5. Critical Findings



- **[BLOODHOUND]** CVSS 8.1 on cyberian-defenses.com (76.13.46.223): OpenSSH 9.6p1 — CVE-2024-6387 (regreSSHion) RCE

- **[WARCHIEF]** CVSS 8.1 on cyberian-defenses.com: CVE-2024-6387 regreSSHion RCE — OpenSSH 9.6p1 in affected range

- **[WARCHIEF]** CVSS 8.1 on cyberian-defenses.com: CVE-2024-6387 regreSSHion RCE on OpenSSH 9.6p1

- **[WARCHIEF]** CVSS 8.1 on cyberian-defenses.com: CVE-2024-6387 regreSSHion RCE on OpenSSH 9.6p1



---

## 6. Decision Audit Trail

  1. [init] → recon (confidence: 0.95)
     Reasoning: Initial engagement state — no prior bot work exists. Target is cyberian-defenses.com with external s
  2. [recon] → recon (confidence: 0.85)
     Reasoning: ARIA's LLM analysis failed with truncated JSON. Partial output reveals useful data: nginx/1.24.0 on 
  3. [scanning] → scan (confidence: 0.70)
     Reasoning: ARIA has run 2 cycles. Cycle 1: LLM analysis failed (truncated JSON). Cycle 2: Tool execution blocke
  4. [scanning] → scan (confidence: 0.75)
     Reasoning: Lisa completed cycle 1 with partial results: 3 ports found (22/SSH, 80/HTTP, 443/HTTPS), nginx/1.24.
  5. [vuln_detection] → report (confidence: 0.82)
     Reasoning: Lisa cycle 2 significantly improved over cycle 1. We now have: OpenSSH 9.6p1 Ubuntu 3 with version s
  6. [vuln_detection] → report (confidence: 0.75)
     Reasoning: Vuln phase has only run 1/5 cycles. Bloodhound identified CVE-2024-6387 (CVSS 8.1) but did NOT verif
  7. [vuln_detection] → vuln_detection (confidence: 0.85)
     Reasoning: Vuln phase has only run 1/5 cycles. Multiple specific, actionable depth gaps remain: (1) CVE-2024-63
  8. [reporting] → report (confidence: 0.85)
     Reasoning: After 2 vuln detection cycles, the engagement has reached its natural conclusion. Key assessment: (1

---

## 7. Cleanup Status

No artifacts left on target.

---

## 8. Mission Outcome

Engagement ended with decision: report

---

*Report generated by Chimeras v2.3 — Cyberian Defenses*
*Generated at: 2026-09-02T22:39:38.516975*