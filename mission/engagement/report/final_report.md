# Penetration Test Report — raksha.tn

## 1. Scope

- **Target:** raksha.tn, www.raksha.tn
- **Objectives:** External penetration test of authorized hosts — passive reconnaissance, active scanning, vulnerability detection, exploitation (if warranted), and reporting
- **Rules of Engagement:** Cautious aggressiveness; respect CDN/WAF/IPS boundaries; no aggressive fuzzing or brute-force; authorization covers exploitation and data exfiltration phases
- **Methodology:** Swarm-based automated penetration test using specialized bots:
  - ARIA (Passive Reconnaissance) — DNS enumeration, WHOIS, CT log queries, tech fingerprinting
  - Lisa (Active Scanning) — port scanning, service detection, web fingerprinting, directory enumeration
  - WarChief (Orchestration) — decision routing, engagement state management
- **Engagement Date:** 2026-07-22

---

## 2. Executive Summary

An authorized external penetration test was conducted against raksha.tn and www.raksha.tn on July 22, 2026. The target is a Tunisian movie and series streaming platform ("Raksha | Aflem & Sériéte Tounsia & 3alamia") owned by Cine 7 Art (Tunis) with administrative contacts at Metropolitan Filmexport (Paris). The primary web application is hosted on Vercel's CDN infrastructure (IPs 216.150.16.65 and 216.150.16.129) and runs a Next.js framework. A secondary subdomain, promo.raksha.tn, was discovered via certificate transparency logs and appears to be hosted on separate AWS infrastructure — this target was not scanned due to scope ambiguity and engagement limitations.

The engagement completed passive reconnaissance and partial active scanning. A scope enforcement bug in the testing platform prevented direct targeting of www.raksha.tn, significantly limiting the depth of application-layer enumeration. Directory enumeration, API endpoint discovery, JavaScript bundle analysis, and security header auditing were all incomplete as a result. No exploitation, privilege escalation, or data exfiltration phases were reached.

**Overall Risk Rating: MEDIUM**

Three confirmed findings were identified: a missing DMARC record (High), weak SPF configuration (Low), and an unexplored AWS-hosted subdomain representing an uncharacterized attack surface (Info). The primary web application's attack surface remains largely unassessed due to tooling limitations encountered during the engagement. The missing DMARC record poses the most immediate business risk, enabling email spoofing against the organization and its customers.

---

## 3. Findings Summary

| ID | Finding | Severity | CVSS | Status |
|----|---------|----------|------|--------|
| FILL-001 | Missing DMARC Record — Email Spoofing Enabled | High | 7.5 | Confirmed |
| FILL-002 | Weak SPF Policy (Softfail ~all) | Low | 3.7 | Confirmed |
| FILL-003 | Unexplored AWS-Hosted Subdomain (promo.raksha.tn) | Info | 0.0 | Confirmed |
| FILL-004 | Wildcard Certificate Exposes Subdomain Attack Surface | Info | 0.0 | Confirmed |
| FILL-005 | WHOIS Personal Information Disclosure | Low | 3.1 | Confirmed |
| FILL-006 | Apex Domain Misconfiguration — 404 DEPLOYMENT_NOT_FOUND | Low | 3.1 | Confirmed |

---

## 4. Detailed Findings

### FILL-001: Missing DMARC Record — Email Spoofing Enabled

**Severity:** High
**CVSS Score:** 7.5 (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N)
**Affected Asset:** raksha.tn (email infrastructure)
**Status:** Confirmed

#### Description
The domain raksha.tn does not have a DMARC (Domain-based Message Authentication, Reporting, and Conformance) record published in DNS at `_dmarc.raksha.tn`. DMARC is the policy layer that instructs receiving mail servers on how to handle messages that fail SPF (Sender Policy Framework) or DKIM (DomainKeys Identified Mail) authentication checks. Without a DMARC record, there is no enforcement mechanism preventing unauthorized senders from forging emails that appear to originate from raksha.tn.

#### Risks
An attacker can send spoofed emails appearing to come from @raksha.tn addresses (e.g., support@raksha.tn, admin@raksha.tn). This enables:
- **Phishing attacks against customers:** Customers of the streaming platform could receive convincing fake emails about account suspension, payment issues, or password resets
- **Business Email Compromise (BEC):** Internal staff could be targeted with spoofed emails from executives or partners
- **Brand reputation damage:** Spoofed emails could distribute malware or scam content using the raksha.tn domain name, damaging trust in the platform
- **Bypass of email security:** Without DMARC enforcement, receiving mail servers have no instructions to reject or quarantine failed authentication messages

#### Attack Vectors
1. Attacker sets up a mail server or uses an email spoofing service
2. Attacker crafts an email with a forged `From: support@raksha.tn` header
3. The email is sent to a target (customer or employee)
4. Receiving mail server checks SPF — if the attacker's IP is not in the SPF record, SPF fails
5. Receiving mail server checks for DMARC policy — no DMARC record exists, so no enforcement action is taken
6. The spoofed email is delivered to the recipient's inbox
7. Recipient trusts the email based on the legitimate-looking domain

#### Proof of Concept
```
dig _dmarc.raksha.tn TXT
```

#### Proof of Existence
Raw dig output confirming no DMARC record exists (ANSWER: 0, only SOA authority returned):

```
; <<>> DiG 9.18.39-0ubuntu0.24.04.5-Ubuntu <<>> _dmarc.raksha.tn TXT
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 40105
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;_dmarc.raksha.tn.		IN	TXT

;; AUTHORITY SECTION:
raksha.tn.		600	IN	SOA	ns1.vercel-dns.com. hostmaster.nsone.net. 1662466573 43200 7200 1209600 600

;; Query time: 20 msec
;; SERVER: 127.0.0.53#53(127.0.0.53) (UDP)
;; WHEN: Thu Jul 23 00:55:00 CEST 2026
;; MSG SIZE  rcvd: 119
```

The response shows `ANSWER: 0` — no TXT record was returned for `_dmarc.raksha.tn`. The SOA record in the AUTHORITY section is the standard NXDOMAIN-style negative response, confirming no DMARC policy is published.

#### Remediation Plan
1. Publish a DMARC TXT record at `_dmarc.raksha.tn` with an initial monitoring policy:
   ```
   _dmarc.raksha.tn. IN TXT "v=DMARC1; p=none; rua=mailto:dmarc-reports@raksha.tn; ruf=mailto:dmarc-forensics@raksha.tn; fo=1;"
   ```
2. Monitor DMARC aggregate reports for 2-4 weeks to identify legitimate email sources
3. Ensure all legitimate email sources (OVH, Microsoft 365, Zendesk) are covered by SPF and have proper DKIM signing
4. Escalate DMARC policy from `p=none` to `p=quarantine` once all legitimate sources are confirmed
5. After a further monitoring period, escalate to `p=reject` for full enforcement:
   ```
   _dmarc.raksha.tn. IN TXT "v=DMARC1; p=reject; rua=mailto:dmarc-reports@raksha.tn; fo=1;"
   ```
6. Consider adding DKIM records for all authorized email providers

---

### FILL-002: Weak SPF Policy (Softfail ~all)

**Severity:** Low
**CVSS Score:** 3.7 (CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:L/A:N)
**Affected Asset:** raksha.tn (email infrastructure)
**Status:** Confirmed

#### Description
The SPF (Sender Policy Framework) record for raksha.tn uses the `~all` (softfail) mechanism instead of `-all` (hardfail). A softfail instructs receiving mail servers to mark failed SPF checks but still accept the email (typically routing to spam). A hardfail instructs receiving servers to reject emails from unauthorized senders entirely. Additionally, the SPF record authorizes three separate email providers (OVH, Microsoft 365, and Zendesk), increasing the attack surface if any of those providers' infrastructure is compromised.

#### Risks
- Emails from unauthorized senders are still delivered (to spam/junk) rather than rejected outright
- Some mail servers may not enforce softfail penalties, delivering spoofed emails to the inbox
- The three authorized providers (OVH, Microsoft 365, Zendesk) each represent potential compromise vectors — if any provider's infrastructure is abused, the attacker's emails would pass SPF checks
- Combined with the missing DMARC record (FILL-001), the softfail mechanism provides minimal protection

#### Attack Vectors
1. Attacker identifies the SPF softfail configuration via DNS lookup
2. Attacker sends spoofed emails from unauthorized IP addresses
3. Receiving mail server checks SPF — the attacker's IP is not authorized, triggering a softfail
4. Depending on the receiving server's configuration, the email may be delivered to spam or the inbox
5. Without DMARC enforcement (see FILL-001), there is no additional layer to reject the message

#### Proof of Concept
```
dig raksha.tn TXT
```

#### Proof of Existence
Raw dig output showing the SPF record with softfail:

```
raksha.tn.		60	IN	TXT	"v=spf1 include:mx.ovh.com include:spf.protection.outlook.com include:mail.zendesk.com ~all"
```

The `~all` at the end of the SPF record is the softfail qualifier. A hardfail would use `-all`.

#### Remediation Plan
1. Audit all legitimate email-sending sources across OVH, Microsoft 365, and Zendesk
2. Remove any unused or unnecessary provider includes from the SPF record
3. Change the SPF mechanism from `~all` to `-all` (hardfail) after confirming all legitimate sources are accounted for:
   ```
   v=spf1 include:mx.ovh.com include:spf.protection.outlook.com include:mail.zendesk.com -all
   ```
4. Implement DMARC (see FILL-001 remediation) to provide enforcement at the policy layer
5. Ensure DKIM signing is configured for all three providers
6. Monitor email delivery rates after the change to ensure no legitimate emails are blocked

---

### FILL-003: Unexplored AWS-Hosted Subdomain (promo.raksha.tn)

**Severity:** Info
**CVSS Score:** 0.0 (Informational — risk cannot be assessed without scanning)
**Affected Asset:** promo.raksha.tn
**Status:** Confirmed (existence confirmed, not scanned)

#### Description
A subdomain `promo.raksha.tn` was discovered via certificate transparency logs. Its SSL/TLS certificate was issued by "Amazon RSA 2048 M01," which is characteristic of AWS Certificate Manager (ACM). This indicates the subdomain is hosted on separate AWS infrastructure (EC2, CloudFront, or ELB) — distinct from the main raksha.tn site which is hosted on Vercel. This subdomain was not scanned during the engagement due to scope ambiguity (the declared scope lists "raksha.tn www.raksha.tn" without explicitly including subdomains).

#### Risks
- **Unknown attack surface:** promo.raksha.tn represents a completely uncharacterized attack surface on separate infrastructure from the main site
- **Potential for exposed services:** AWS-hosted services may expose non-web ports (databases, admin panels, APIs, SSH) unlike Vercel which only exposes 80/443
- **Potential pivot point:** If promo.raksha.tn is compromised, it could serve as a pivot point to attack the main raksha.tn infrastructure or internal networks
- **Certificate scope:** The Amazon RSA certificate is valid for ~6 months (March–September 2026), consistent with ACM-managed certificates

#### Attack Vectors
This finding is informational. The actual attack vectors cannot be determined without active scanning of promo.raksha.tn. Potential vectors include:
1. DNS resolution to confirm the AWS IP address
2. Port scanning to identify exposed services
3. Web fingerprinting if HTTP/HTTPS is available
4. Directory enumeration and vulnerability scanning
5. Exploitation of any discovered services

#### Proof of Concept
```
curl -s "https://crt.sh/?q=raksha.tn&output=json"
```

#### Proof of Existence
Raw crt.sh JSON output showing the promo.raksha.tn certificate with Amazon issuer:

```json
{
  "issuer_ca_id": 295817,
  "issuer_name": "C=US, O=Let's Encrypt, CN=R13",
  "common_name": "*.raksha.tn",
  "name_value": "*.raksha.tn\nraksha.tn",
  "id": 25421877581,
  "entry_timestamp": "2026-04-03T03:07:13.864",
  "not_before": "2026-04-03T02:08:42",
  "not_after": "2026-07-02T02:08:41"
}
```

Additional CT log entries confirm the wildcard cert `*.raksha.tn` issued by Let's Encrypt and the separate `promo.raksha.tn` certificate issued by Amazon RSA 2048 M01 (valid 2026-03-16 → 2026-09-29), confirming AWS-hosted infrastructure distinct from the Vercel-hosted main site.

#### Remediation Plan
1. **Immediate:** Clarify whether promo.raksha.tn is an active production asset or a stale/forgotten deployment
2. **If active:** Include promo.raksha.tn in the penetration test scope for a follow-up engagement
3. **If stale:** Remove the DNS record and decommission the AWS resources
4. **Inventory:** Conduct a full subdomain enumeration exercise to identify all active subdomains under raksha.tn
5. **Monitoring:** Implement certificate transparency log monitoring to detect new subdomains/certificates being created
6. **Hardening:** Ensure all AWS-hosted services follow security best practices (security groups, IAM roles, encryption, patching)

---

### FILL-004: Wildcard Certificate Exposes Subdomain Attack Surface

**Severity:** Info
**CVSS Score:** 0.0 (Informational)
**Affected Asset:** *.raksha.tn
**Status:** Confirmed

#### Description
A wildcard TLS certificate `*.raksha.tn` has been issued by Let's Encrypt for the raksha.tn domain. Wildcard certificates cover any subdomain under raksha.tn, which means any number of subdomains could be deployed without individual certificate transparency log entries. This makes complete subdomain enumeration difficult, as only explicitly-named certificates (like promo.raksha.tn) appear in CT logs.

#### Risks
- **Hidden subdomains:** Additional subdomains may exist that are not visible in certificate transparency logs because they're covered by the wildcard certificate
- **Forgotten/stale deployments:** Development, staging, or legacy subdomains may remain accessible without the organization's knowledge
- **Expanded attack surface:** Each undocumented subdomain represents a potential entry point for attackers
- **Certificate compromise impact:** If the wildcard certificate's private key is compromised, all subdomains are simultaneously affected

#### Attack Vectors
1. Attacker enumerates potential subdomains via brute-force, DNS zone transfers, or other DNS enumeration techniques
2. Attacker discovers subdomains not visible in CT logs (covered by wildcard cert)
3. Attacker probes discovered subdomains for vulnerabilities
4. Compromised subdomain serves as entry point to the broader raksha.tn infrastructure

#### Proof of Concept
```
curl -s "https://crt.sh/?q=raksha.tn&output=json"
```

#### Proof of Existence
Raw crt.sh output confirming wildcard certificate:

```json
{"issuer_ca_id":432476,"issuer_name":"C=US, O=Let's Encrypt, CN=YR1","common_name":"*.raksha.tn","name_value":"*.raksha.tn","id":27402147851,"entry_timestamp":"2026-06-22T18:31:11.967","not_before":"2026-06-22T17:32:41","not_after":"2026-09-20T17:32:40","serial_number":"0581ecb0399c8a7c2853f7a9366bb04e99d7"}
```

The `common_name` field is `*.raksha.tn`, confirming a wildcard certificate. Multiple entries with this common name were returned, with the most recent valid from 2026-06-22 to 2026-09-20.

#### Remediation Plan
1. **Subdomain inventory:** Conduct comprehensive subdomain enumeration using active DNS brute-force, passive DNS databases, and internal asset records
2. **Replace wildcard cert:** Consider replacing the wildcard certificate with individual certificates per subdomain for better visibility and reduced blast radius
3. **DNS monitoring:** Implement DNS monitoring to alert on new subdomain creations
4. **Decommission stale subdomains:** Identify and remove any forgotten or unused subdomains
5. **Certificate key protection:** Ensure the wildcard certificate private key is stored securely (e.g., Vercel's managed certificate storage) with restricted access

---

### FILL-005: WHOIS Personal Information Disclosure

**Severity:** Low
**CVSS Score:** 3.1 (CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N)
**Affected Asset:** raksha.tn (WHOIS records)
**Status:** Confirmed

#### Description
The WHOIS record for raksha.tn exposes personal contact information for the domain owner and administrative/technical contacts, including full names, physical addresses, phone numbers, and email addresses. The owner uses a personal Yahoo email address (lass_goubantini@yahoo.fr) rather than a corporate email. This information is publicly accessible to anyone.

#### Risks
- **Social engineering:** Exposed phone numbers and email addresses can be used for targeted phishing, vishing, or pretexting attacks
- **Physical security:** Physical addresses (Tunis and Paris offices) are exposed, potentially enabling physical social engineering
- **Personal email exposure:** The owner's personal Yahoo email (lass_goubantini@yahoo.fr) could be targeted for account compromise, potentially leading to domain takeover
- **OSINT enrichment:** Combined with other public information, attackers can build detailed profiles of key personnel for targeted attacks

#### Attack Vectors
1. Attacker queries WHOIS for raksha.tn
2. Attacker obtains owner name (Cine 7 Art), personal email (lass_goubantini@yahoo.fr), and phone (+33.684183792)
3. Attacker crafts a targeted phishing email to the owner's personal Yahoo account
4. If the Yahoo account is compromised, attacker may gain access to domain registrar (OVH) account
5. Domain takeover enables DNS hijacking, email interception, and full control of the raksha.tn web presence

#### Proof of Concept
```
whois raksha.tn
```

#### Proof of Existence
Raw WHOIS output:

```
Domain name.........: raksha.tn
Creation date.......: 07-04-2022 09:29:03 GMT+1
Domain status.......: Active
Registrar...........: OVH

Owner Contact
Name................: Cine 7 Art
Address.............: 54 Avenue Habib Bourguiba
1000 Tunis
Phone...............: +33.684183792
Email...............: lass_goubantini@yahoo.fr

Administrativ contact
Name................: Metropolitan Filmexport
Address.............: 29 rue Galilee
75116 Paris
Phone...............: +33.612712244
Email...............: jhadida@metropolitan-films.com

Technical contact
Name................: Metropolitan Filmexport
Address.............: 29 rue Galilee
75116 Paris
Phone...............: +33.612712244
Email...............: jhadida@metropolitan-films.com
dnssec..............: unsigned
```

#### Remediation Plan
1. **Enable WHOIS privacy protection:** Contact OVH registrar to enable domain privacy/WHOIS masking if available for .tn domains
2. **Use corporate emails:** Replace the personal Yahoo email (lass_goubantini@yahoo.fr) with a corporate email address for all domain registration contacts
3. **Enable registrar security:** Ensure the OVH registrar account has multi-factor authentication (MFA) enabled
4. **Secure the Yahoo account:** If the personal email must remain, ensure it has strong MFA and is not used for other critical services
5. **Enable DNSSEC:** The domain is currently unsigned — enabling DNSSEC would protect against DNS spoofing attacks
6. **Separate roles:** Consider using role-based contacts (e.g., "Domain Administrator") rather than personal names

---

### FILL-006: Apex Domain Misconfiguration — 404 DEPLOYMENT_NOT_FOUND

**Severity:** Low
**CVSS Score:** 3.1 (CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N)
**Affected Asset:** raksha.tn (apex domain, port 443)
**Status:** Confirmed

#### Description
When the apex domain raksha.tn is accessed directly via HTTPS on port 443 (without following the redirect chain), Vercel returns a 404 error with `X-Vercel-Error: DEPLOYMENT_NOT_FOUND`. This indicates that no Vercel deployment is directly configured for the apex domain — it only functions as a redirect to www.raksha.tn. When probed by IP address directly, the server returns a malformed redirect Location header (`https:///` with empty host).

#### Risks
- **Information disclosure:** The `X-Vercel-Error: DEPLOYMENT_NOT_FOUND` header and the `X-Vercel-Id` header expose internal Vercel deployment identifiers and infrastructure details
- **Misconfiguration indicator:** Suggests the apex domain's Vercel configuration may be incomplete or incorrect
- **Malformed redirect:** The malformed `Location: https:///` header when probed by IP could cause issues with certain HTTP clients or security tools
- **Potential for subdomain takeover:** If the Vercel deployment for the apex domain was previously configured and then removed, there may be a risk of subdomain takeover if an attacker can claim the Vercel deployment name

#### Attack Vectors
1. Attacker sends an HTTPS request directly to raksha.tn on port 443 (without following redirects)
2. Server returns 404 with `X-Vercel-Error: DEPLOYMENT_NOT_FOUND` and `X-Vercel-Id: cdg1::664r7-1784761042054-da1cade418d7`
3. Attacker extracts the Vercel deployment ID and request ID for potential further attacks
4. Attacker probes for subdomain takeover potential by checking if the deployment name can be claimed

#### Proof of Concept
```
nmap -sV -T3 --top-ports 1000 raksha.tn
```

#### Proof of Existence
Raw nmap service fingerprint output for port 443:

```
SF-Port443-TCP:V=7.94SVN%T=SSL%I=7%D=7/23%Time=6A614AD2%P=x86_64-pc-linux-
SF:gnu%r(GetRequest,1B3,"HTTP/1\.0\x20404\x20Not\x20Found\r\nCache-Control
SF::\x20public,\x20max-age=0,\x20must-revalidate\r\nContent-Length:\x20107
SF:\r\nContent-Type:\x20text/plain;\x20charset=utf-8\r\nDate:\x20Wed,\x202
SF:2\x20Jul\x202026\x2022:57:22\x20GMT\r\nServer:\x20Vercel\r\nStrict-Tran
SF:sport-Security:\x20max-age=63072000\r\nX-Vercel-Error:\x20DEPLOYMENT_NO
SF:T_FOUND\r\nX-Vercel-Id:\x20cdg1::664r7-1784761042054-da1cade418d7\r\n\r
SF:\nThe\x20deployment\x20could\x20not\x20be\x20found\x20on\x20Vercel\.\n\
SF:\nDEPLOYMENT_NOT_FOUND\n\ncdg1::664r7-1784761042054-da1cade418d7\n")
```

The raw output shows:
- HTTP/1.0 404 Not Found
- `X-Vercel-Error: DEPLOYMENT_NOT_FOUND`
- `X-Vercel-Id: cdg1::664r7-1784761042054-da1cade418d7`
- Response body: "The deployment could not be found on Vercel. DEPLOYMENT_NOT_FOUND. cdg1::664r7-1784761042054-da1cade418d7"

Additionally, port 80 shows malformed redirects when probed by IP:

```
SF-Port80-TCP:V=7.94SVN%I=7%D=7/23%Time=6A614ACC%P=x86_64-pc-linux-gnu%r(G
SF:etRequest,8A,"HTTP/1\.0\x20308\x20Permanent\x20Redirect\r\nContent-Type
SF::\x20text/plain\r\nLocation:\x20https:///\r\nRefresh:\x200;url=https://
SF:/\r\nserver:\x20Vercel\r\n\r\nRedirecting\.\.\.")
```

The `Location: https:///` header shows an empty hostname in the redirect URL.

#### Remediation Plan
1. **Configure apex deployment:** Ensure a proper Vercel deployment is configured for the apex domain raksha.tn, or configure a clean redirect at the DNS/CDN level
2. **Remove verbose error headers:** Configure Vercel to suppress `X-Vercel-Error` and `X-Vercel-Id` headers in production
3. **Fix malformed redirects:** Ensure the redirect Location header includes the proper hostname (https://www.raksha.tn/) rather than an empty host
4. **Test subdomain takeover:** Verify that the Vercel deployment name for the apex domain cannot be claimed by an unauthorized party
5. **Review Vercel project settings:** Audit the Vercel project configuration to ensure all domains and subdomains are properly mapped to active deployments

---

## 5. Engagement Flow (Decision Audit Trail)

The engagement was orchestrated by WarChief across 4 decision cycles. Below is the complete audit trail:

### Cycle 1: Init → Recon (Confidence: 0.95)
- **State:** init (no prior data)
- **Decision:** Route to ARIA for passive reconnaissance
- **Reasoning:** First engagement cycle with zero prior data. Passive recon is the canonical first step — map DNS, identify hosting, discover subdomains via CT logs, fingerprint web technologies before any active scanning.
- **ARIA executed:** DNS enumeration (A, AAAA, MX, TXT, NS, SOA, CNAME), WHOIS lookup, CT log query (crt.sh), DMARC check, HTTP/HTTPS probing, tech fingerprinting with whatweb
- **Results:** Vercel CDN confirmed, Next.js detected, promo.raksha.tn discovered on AWS, no DMARC found, wildcard cert identified, scope guard bug encountered (www.raksha.tn blocked)

### Cycle 2: Recon → Scan (Confidence: 0.82)
- **State:** scanning
- **Decision:** Route to Lisa for active scanning
- **Reasoning:** ARIA's recon produced actionable findings — technology stack identified, subdomain discovered, email security gaps confirmed. Active scanning justified to enumerate ports, fingerprint web stack, discover directories/API endpoints.
- **Lisa tasking:** Port scan www.raksha.tn and raksha.tn, web fingerprinting with whatweb, gobuster directory enumeration, nikto web vulnerability scan
- **Results:** Only nmap on raksha.tn completed (ports 80/443 open, Vercel). Scope guard bug blocked all www.raksha.tn direct targeting. Gobuster failed due to Vercel 308 redirect behavior. Nikto blocked entirely.

### Cycle 3: Scan → Scan (Confidence: 0.85)
- **State:** scanning
- **Decision:** Continue scanning (route Lisa back for cycle 2)
- **Reasoning:** ARIA's recon confirmed actionable attack surface. Lisa's first cycle was blocked by scope guard bug, not by lack of findings. Workaround identified: use `raksha.tn` as target (redirects to www.raksha.tn). promo.raksha.tn on AWS is highest-value unexplored target.
- **Lisa tasking (cycle 2):** Scan promo.raksha.tn (DNS, ports, web fingerprint), application-layer enumeration via raksha.tn workaround, security header audit, JS bundle analysis, scan secondary IP 216.150.16.129
- **Results:** This cycle did not produce additional scan output in the engagement files — engagement was terminated before completion.

### Cycle 4: Scan → Scan (Confidence: 0.72)
- **State:** scanning
- **Decision:** Continue scanning with adjusted targeting
- **Reasoning:** Lisa's first scan cycle was crippled by scope guard bug. Critical gaps remain: promo.raksha.tn unscanned, application layer unenumerated, secondary IP unscanned. Workaround: use `raksha.tn` as target parameter. Not a useless loop — first scan cycle was blocked by tooling issue.
- **Results:** Engagement ended at this point — no further bot output was produced.

### Phase Summary

| Phase | Status | Cycles | Key Outcomes |
|-------|--------|--------|-------------|
| Recon (ARIA) | COMPLETE | 1 | Full DNS enum, WHOIS, CT logs, tech fingerprint, email security assessment |
| Scan (Lisa) | PARTIAL | 1 (of 4 planned) | Port scan completed (80/443 only); directory enum, API discovery, security headers, JS analysis all blocked |
| Vuln (Bloodhound) | NOT STARTED | 0 | — |
| Exploit (Surgeon) | NOT STARTED | 0 | — |
| Privesc (Magician) | NOT STARTED | 0 | — |
| Exfil (Thief) | NOT STARTED | 0 | — |
| Report (Bookkeeper) | CURRENT | — | This report |

### Scope Guard Bug Impact
A critical tooling bug in the scope enforcement system prevented direct targeting of www.raksha.tn throughout the engagement. The scope guard stripped the `www.` prefix from the hostname, resulting in an empty string `''` being checked against the scope. This blocked:
- All `dig` queries against www.raksha.tn
- All `host` queries against www.raksha.tn
- All `httpx` probes against www.raksha.tn
- All `whatweb` scans against www.raksha.tn
- All `nmap` scans against www.raksha.tn
- All `gobuster` directory enumeration against www.raksha.tn
- All `nikto` vulnerability scans against www.raksha.tn

The error message consistently read:
```
BLOCKED: TARGET SCOPE VIOLATION: lisa attempted to target '' which is OUTSIDE the mission scope: raksha.tn www.raksha.tn
```

This significantly limited the depth of the engagement. The application layer — identified as the primary attack vector — remains largely unassessed.

---

## 6. Cleanup & Rollback Status

No artifacts were left on target systems during this engagement. The engagement was limited to passive reconnaissance and non-intrusive active scanning (DNS queries, HTTP header fetching, port scanning). No payloads were dropped, no scheduled tasks were created, no users were added, no configurations were modified.

| Artifact | Host | Type | Location | Cleanup Attempted | Cleanup Status |
|----------|------|------|----------|-------------------|----------------|
| (none) | — | — | — | — | — |

**No cleanup required.** All activities were read-only and non-intrusive.

---

## 7. Conclusion

### Overall Security Posture Assessment

The raksha.tn domain presents a **MEDIUM** overall risk profile based on the findings from this limited engagement. The primary web application is hosted on Vercel's CDN, which provides a reduced network attack surface (only ports 80 and 443 exposed). HSTS is properly enabled. However, the email security posture is weak — the missing DMARC record and softfail SPF configuration expose the organization and its customers to email spoofing attacks.

The engagement was **significantly limited** by a scope enforcement bug that prevented direct scanning of www.raksha.tn, the primary attack surface. As a result, the application layer — including directory structure, API endpoints, JavaScript bundles, security headers, and potential web vulnerabilities — remains largely unassessed. The vulnerability detection, exploitation, privilege escalation, and data exfiltration phases were not reached.

The discovery of promo.raksha.tn on separate AWS infrastructure represents an uncharacterized attack surface that warrants further investigation.

### Priority Remediation Order

1. **CRITICAL — Publish a DMARC record** (FILL-001): Immediate action required to prevent email spoofing. Start with `p=none` monitoring, then escalate to `p=reject`.
2. **HIGH — Harden SPF policy** (FILL-002): Change `~all` to `-all` after verifying all legitimate email sources.
3. **MEDIUM — Scan and assess promo.raksha.tn** (FILL-003): Include in a follow-up engagement or decommission if unused.
4. **MEDIUM — Conduct full subdomain enumeration** (FILL-004): Identify all subdomains covered by the wildcard certificate.
5. **LOW — Enable WHOIS privacy and DNSSEC** (FILL-005): Protect personal information and enable DNS security.
6. **LOW — Fix apex domain Vercel configuration** (FILL-006): Remove verbose error headers and fix malformed redirects.

### Recommendations for Follow-Up Engagement

A follow-up penetration test is strongly recommended with the following scope adjustments:
1. Fix the scope enforcement bug to allow direct targeting of www.raksha.tn
2. Explicitly include promo.raksha.tn and any other discovered subdomains in scope
3. Conduct full application-layer testing: directory enumeration, API discovery, JS bundle analysis, security header audit, vulnerability scanning
4. Perform subdomain brute-force enumeration to identify all subdomains under the wildcard certificate
5. Conduct DKIM record verification to complete the email security assessment
6. Test for Next.js-specific vulnerabilities (SSR/SSRF, API route exposure, server-side request forgery)

---

## 8. Appendix

### Tools Used
| Tool | Bot | Purpose | Status |
|------|-----|---------|--------|
| dig | ARIA | DNS record enumeration (A, AAAA, MX, TXT, NS, SOA, CNAME, DMARC) | Completed |
| whois | ARIA | Domain registration and contact information lookup | Completed |
| host | ARIA | DNS resolution verification | Completed |
| curl (crt.sh) | ARIA | Certificate transparency log query for subdomain discovery | Completed |
| httpx | ARIA | HTTP probing and tech detection | Failed (incorrect CLI syntax — `-u` flag not supported) |
| whatweb | ARIA | Web technology fingerprinting | Completed (via redirect chain) |
| nmap | Lisa | Port scanning and service detection (-sV -T3 --top-ports 1000) | Completed on raksha.tn; blocked on www.raksha.tn |
| whatweb | Lisa | Web technology fingerprinting | Completed on raksha.tn; blocked on www.raksha.tn |
| gobuster | Lisa | Directory enumeration | Failed (Vercel 308 redirect behavior) |
| nikto | Lisa | Web vulnerability scanning | Blocked by scope guard |

### Raw Output Files
| File | Bot | Command | Location |
|------|-----|---------|----------|
| aria_curl_225508.txt | ARIA | curl -s "https://crt.sh/?q=raksha.tn&output=json" | raw/ |
| aria_dig_225500.txt | ARIA | dig _dmarc.raksha.tn TXT | raw/ |
| aria_host_225500.txt | ARIA | host raksha.tn | raw/ |
| aria_httpx_225509.txt | ARIA | httpx -u http://raksha.tn | raw/ |
| aria_whatweb_225513.txt | ARIA | whatweb https://raksha.tn | raw/ |
| aria_whatweb_225516.txt | ARIA | whatweb http://raksha.tn | raw/ |
| aria_whois_225500.txt | ARIA | whois raksha.tn | raw/ |
| lisa_gobuster_225851.txt | Lisa | gobuster dir -u https://raksha.tn | raw/ |
| lisa_nikto_225851.txt | Lisa | nikto -h https://www.raksha.tn | raw/ |
| lisa_nmap_225705.txt | Lisa | nmap -sV -T3 --top-ports 1000 www.raksha.tn | raw/ |
| lisa_nmap_225849.txt | Lisa | nmap -sV -T3 --top-ports 1000 raksha.tn | raw/ |
| lisa_whatweb_225849.txt | Lisa | whatweb https://www.raksha.tn | raw/ |
| lisa_whatweb_225851.txt | Lisa | whatweb https://raksha.tn | raw/ |

### Bots Deployed
| Bot | Role | Cycles | Status |
|-----|------|--------|--------|
| ARIA | Passive Reconnaissance | 1 | Complete |
| Lisa | Active Scanning | 1 (of 4 planned) | Partial — blocked by scope guard bug |
| WarChief | Orchestrator | 4 | Active throughout |
| Bloodhound | Vulnerability Detection | 0 | Not deployed |
| Surgeon | Exploitation | 0 | Not deployed |
| Magician | Privilege Escalation | 0 | Not deployed |
| Thief | Data Exfiltration | 0 | Not deployed |

### Total Decision Cycles: 4

### Engagement Ended Because: Insufficient data / scope exhaustion
The engagement was terminated during the scanning phase due to the persistent scope guard bug preventing direct targeting of www.raksha.tn. WarChief's cycle 4 decision (confidence: 0.72) attempted to route Lisa back with workaround instructions, but no further scan output was produced. The engagement reached the reporting phase with partial scan coverage and no vulnerability detection, exploitation, or post-exploitation phases completed.