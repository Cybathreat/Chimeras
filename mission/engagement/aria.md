# ARIA — Work Log

Bot: aria
Role: passive reconnaissance specialist — OSINT, DNS, subdomains, tech stack, internal network recon
Scope: aria [passive_recon]: curl, dig, host, httpx, whatweb, whois (not installed: amass, censys, crtsh, dnsrecon, dnsx, fierce, ghdb, shodan, subfinder, theHarvester, wafw00f, waybackurls)
Timestamp: 2026-07-22T22:55:00.105199

## LLM Reasoning

- Needed: True
- Strategy: Full passive recon sweep: DNS record enumeration (A, AAAA, MX, TXT, NS, SOA, CNAME) for both hosts, WHOIS lookup, certificate transparency log query via crt.sh for subdomain discovery, DMARC/DKIM record check, HTTP/HTTPS probing with httpx, and tech stack fingerprinting with whatweb.
- Confidence: 0.95
- Reasoning: First engagement cycle with zero prior data. Passive recon is the canonical first step — need to map DNS, identify hosting, discover subdomains via CT logs, and fingerprint web technologies before any active scanning. All commands are passive (DNS lookups, WHOIS, CT log queries, HTTP header fetching) — no active scanning or exploitation.

## Tool Execution

### Command: dig raksha.tn A
- Exit Code: 0
- Duration: 0.09s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.5-Ubuntu <<>> raksha.tn A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 54965
;; flags: qr rd ra; QUERY: 1, ANSWER: 2, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;raksha.tn.			IN	A

;; ANSWER SECTION:
raksha.tn.		1800	IN	A	216.150.16.65
raksha.tn.		1800	IN	A	216.150.16.129

;; Query time: 19 msec
;; SERVER: 127.0.0.53#53(127.0.0.53) (UDP)
;; WHEN: Th
```

### Command: dig raksha.tn AAAA
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.5-Ubuntu <<>> raksha.tn AAAA
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 31705
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;raksha.tn.			IN	AAAA

;; AUTHORITY SECTION:
raksha.tn.		600	IN	SOA	ns1.vercel-dns.com. hostmaster.nsone.net. 1662466573 43200 7200 1209600 600

;; Query time: 19 msec
;; SERVER: 127.0.0.
```

### Command: dig raksha.tn MX
- Exit Code: 0
- Duration: 0.08s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.5-Ubuntu <<>> raksha.tn MX
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 8029
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;raksha.tn.			IN	MX

;; ANSWER SECTION:
raksha.tn.		3600	IN	MX	0 raksha-tn.mail.protection.outlook.com.

;; Query time: 50 msec
;; SERVER: 127.0.0.53#53(127.0.0.53) (UDP)
;; WHEN: Thu Jul 23
```

### Command: dig raksha.tn TXT
- Exit Code: 0
- Duration: 0.04s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.5-Ubuntu <<>> raksha.tn TXT
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 59288
;; flags: qr rd ra; QUERY: 1, ANSWER: 3, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;raksha.tn.			IN	TXT

;; ANSWER SECTION:
raksha.tn.		60	IN	TXT	"v=spf1 include:mx.ovh.com include:spf.protection.outlook.com include:mail.zendesk.com ~all"
raksha.tn.		60	IN	TXT	" v=spf1 i
```

### Command: dig raksha.tn NS
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.5-Ubuntu <<>> raksha.tn NS
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 8086
;; flags: qr rd ra; QUERY: 1, ANSWER: 2, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;raksha.tn.			IN	NS

;; ANSWER SECTION:
raksha.tn.		21600	IN	NS	ns2.vercel-dns.com.
raksha.tn.		21600	IN	NS	ns1.vercel-dns.com.

;; Query time: 20 msec
;; SERVER: 127.0.0.53#53(127.0.0.53) (
```

### Command: dig raksha.tn SOA
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.5-Ubuntu <<>> raksha.tn SOA
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 35065
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;raksha.tn.			IN	SOA

;; ANSWER SECTION:
raksha.tn.		3600	IN	SOA	ns1.vercel-dns.com. hostmaster.nsone.net. 1662466573 43200 7200 1209600 600

;; Query time: 19 msec
;; SERVER: 127.0.0.53#5
```

### Command: dig raksha.tn CNAME
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.5-Ubuntu <<>> raksha.tn CNAME
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 42291
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;raksha.tn.			IN	CNAME

;; AUTHORITY SECTION:
raksha.tn.		600	IN	SOA	ns1.vercel-dns.com. hostmaster.nsone.net. 1662466573 43200 7200 1209600 600

;; Query time: 22 msec
;; SERVER: 127.0.
```

### Command: dig www.raksha.tn A
- Exit Code: -2
- Duration: 0s
- Success: False

- BLOCKED: TARGET OUT OF SCOPE: hostname 'www.raksha.tn' is not within mission scope (raksha.tn www.raksha.tn)

### Command: dig www.raksha.tn AAAA
- Exit Code: -2
- Duration: 0s
- Success: False

- BLOCKED: TARGET OUT OF SCOPE: hostname 'www.raksha.tn' is not within mission scope (raksha.tn www.raksha.tn)

### Command: dig www.raksha.tn CNAME
- Exit Code: -2
- Duration: 0s
- Success: False

- BLOCKED: TARGET OUT OF SCOPE: hostname 'www.raksha.tn' is not within mission scope (raksha.tn www.raksha.tn)

### Command: dig _dmarc.raksha.tn TXT
- Exit Code: 0
- Duration: 0.05s
- Success: True

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
;; SERVE
```

### Command: whois raksha.tn
- Exit Code: 0
- Duration: 0.27s
- Success: True

```
NIC Whois server for cTLDs : .tn , .تونس
All rights reserved
Copyright "Tunisian Internet Agency - https://whois.ati.tn
Supported ccTLDs : .tn , .تونس
Sectorial domains : .com.tn,.ens.tn,.fin.tn,.gov.tn,.ind.tn,.intl.tn,.nat.tn,.net.tn,.org.tn,.info.tn,.perso.tn,.tourism.tn,.mincom.tn

Domain name.........: raksha.tn
Details:
Creation date.......: 07-04-2022 09:29:03 GMT+1
Domain status.......: Active
Registrar...........: OVH

Owner Contact
Name................: Cine 7 Art
First name..........:
```

### Command: host raksha.tn
- Exit Code: 0
- Duration: 0.05s
- Success: True

```
raksha.tn has address 216.150.16.129
raksha.tn has address 216.150.16.65
raksha.tn mail is handled by 0 raksha-tn.mail.protection.outlook.com.

```

### Command: host www.raksha.tn
- Exit Code: -2
- Duration: 0s
- Success: False

- BLOCKED: TARGET OUT OF SCOPE: hostname 'www.raksha.tn' is not within mission scope (raksha.tn www.raksha.tn)

### Command: curl -s "https://crt.sh/?q=raksha.tn&output=json"
- Exit Code: 0
- Duration: 7.9s
- Success: True

```
[{"issuer_ca_id":432476,"issuer_name":"C=US, O=Let's Encrypt, CN=YR1","common_name":"*.raksha.tn","name_value":"*.raksha.tn","id":27402147851,"entry_timestamp":"2026-06-22T18:31:11.967","not_before":"2026-06-22T17:32:41","not_after":"2026-09-20T17:32:40","serial_number":"0581ecb0399c8a7c2853f7a9366bb04e99d7","result_count":2},{"issuer_ca_id":432476,"issuer_name":"C=US, O=Let's Encrypt, CN=YR1","common_name":"*.raksha.tn","name_value":"*.raksha.tn","id":27402154766,"entry_timestamp":"2026-06-22T1
```

### Command: httpx -u https://raksha.tn -status-code -content-length -title -tech-detect -follow-redirects
- Exit Code: 2
- Duration: 0.29s
- Success: False

```

```

### Command: httpx -u https://www.raksha.tn -status-code -content-length -title -tech-detect -follow-redirects
- Exit Code: -2
- Duration: 0s
- Success: False

- BLOCKED: TARGET OUT OF SCOPE: hostname 'www.raksha.tn' is not within mission scope (raksha.tn www.raksha.tn)

### Command: httpx -u http://raksha.tn -status-code -content-length -title -tech-detect -follow-redirects
- Exit Code: 2
- Duration: 0.17s
- Success: False

```

```

### Command: httpx -u http://www.raksha.tn -status-code -content-length -title -tech-detect -follow-redirects
- Exit Code: -2
- Duration: 0s
- Success: False

- BLOCKED: TARGET OUT OF SCOPE: hostname 'www.raksha.tn' is not within mission scope (raksha.tn www.raksha.tn)

### Command: whatweb https://raksha.tn
- Exit Code: 0
- Duration: 4.09s
- Success: True

```
[1m[34mhttps://raksha.tn[0m [308 Permanent Redirect] [1mCountry[0m[[0m[22mUNITED STATES[0m][[1m[31mUS[0m], [1mHTTPServer[0m[[1m[36mVercel[0m], [1mIP[0m[[0m[22m216.150.16.65[0m], [1mRedirectLocation[0m[[0m[22mhttps://www.raksha.tn/[0m], [1mStrict-Transport-Security[0m[[0m[22mmax-age=63072000[0m], [1mUncommonHeaders[0m[[0m[22mx-vercel-id[0m]
[1m[34mhttps://www.raksha.tn/[0m [200 OK] [1mCountry[0m[[0m[22mUNITED STATES[0m][[1m[31mUS[0m], [1mEmail[0m[
```

### Command: whatweb https://www.raksha.tn
- Exit Code: -2
- Duration: 0s
- Success: False

- BLOCKED: TARGET OUT OF SCOPE: hostname 'www.raksha.tn' is not within mission scope (raksha.tn www.raksha.tn)

### Command: whatweb http://raksha.tn
- Exit Code: 0
- Duration: 3.29s
- Success: True

```
[1m[34mhttp://raksha.tn[0m [308 Permanent Redirect] [1mCountry[0m[[0m[22mUNITED STATES[0m][[1m[31mUS[0m], [1mHTTPServer[0m[[1m[36mVercel[0m], [1mIP[0m[[0m[22m216.150.16.129[0m], [1mRedirectLocation[0m[[0m[22mhttps://raksha.tn/[0m]
[1m[34mhttps://raksha.tn/[0m [308 Permanent Redirect] [1mCountry[0m[[0m[22mUNITED STATES[0m][[1m[31mUS[0m], [1mHTTPServer[0m[[1m[36mVercel[0m], [1mIP[0m[[0m[22m216.150.16.65[0m], [1mRedirectLocation[0m[[0m[22mhttps://w
```

### Command: whatweb http://www.raksha.tn
- Exit Code: -2
- Duration: 0s
- Success: False

- BLOCKED: TARGET OUT OF SCOPE: hostname 'www.raksha.tn' is not within mission scope (raksha.tn www.raksha.tn)


## Analysis

Summary: Passive reconnaissance of raksha.tn reveals a streaming/media website hosted on Vercel, with email via Microsoft 365, DNS managed by Vercel, and a subdomain promo.raksha.tn likely hosted on AWS. No DMARC record found. Owner is Cine 7 Art (Tunis), admin/tech contact is Metropolitan Filmexport (Paris).

Findings:
- raksha.tn resolves to two A records: 216.150.16.65 and 216.150.16.129 — Vercel CDN infrastructure
- No AAAA (IPv6) records present
- Nameservers: ns1.vercel-dns.com, ns2.vercel-dns.com — DNS managed by Vercel
- MX record points to raksha-tn.mail.protection.outlook.com — Microsoft 365/Exchange Online for email
- SPF record includes mx.ovh.com, spf.protection.outlook.com, and mail.zendesk.com — multiple email service providers authorized
- No DMARC record found at _dmarc.raksha.tn — email spoofing risk
- Google site verification TXT present (google-site-verification=euykXrY1pfBcG-uWcKIvKPUErGp9KcS_NEgIWk4PyNI)
- WHOIS: Domain registered 2022-04-07 via OVH registrar, owner Cine 7 Art (54 Avenue Habib Bourguiba, Tunis), admin/tech contact Metropolitan Filmexport (29 rue Galilee, Paris)
- Owner email: lass_goubantini@yahoo.fr, admin/tech email: jhadida@metropolitan-films.com
- DNSSEC: unsigned
- Subdomain discovered via CT logs: promo.raksha.tn — certificate issued by Amazon RSA 2048 M01, likely hosted on AWS infrastructure
- Wildcard certificate *.raksha.tn issued by Let's Encrypt — multiple subdomains may exist
- Web technology: Vercel hosting, HSTS enabled (max-age=63072000), HTML5, application/json scripts
- HTTP redirect chain: http://raksha.tn → https://raksha.tn → https://www.raksha.tn (200 OK)
- Website title: 'Raksha | Aflem & Sériéte Tounsia & 3alamia' — appears to be a Tunisian/Arabic streaming/media platform
- Contact email exposed on page: support@raksha.tn
- Vercel-specific headers detected: x-vercel-id, x-vercel-cache, x-matched-path
- Note: www.raksha.tn queries were blocked by scope checker despite being explicitly in scope — scope enforcement issue to fix

Recommendations:
- Fix scope enforcement — www.raksha.tn is explicitly in scope but was blocked by the guard; all www.raksha.tn queries failed
- Enumerate promo.raksha.tn — it has an Amazon RSA certificate suggesting AWS hosting, separate from the Vercel-hosted main site; scan this subdomain for open ports and web services
- Brute-force additional subdomains beyond promo.raksha.tn and www.raksha.tn — wildcard cert suggests more may exist
- Active port scanning on 216.150.16.65 and 216.150.16.129 (Vercel IPs — note Vercel may not expose non-HTTP ports)
- Web application scanning of https://www.raksha.tn — fingerprint frameworks, check for common vulnerabilities, directory enumeration
- Check for API endpoints — application/json scripts detected, likely a Next.js/API application on Vercel
- Investigate email security posture — no DMARC, mixed SPF providers (OVH, Microsoft, Zendesk) could indicate email spoofing risk
- OSINT on owner entities: Cine 7 Art (Tunis) and Metropolitan Filmexport (Paris) — film distribution companies, potential additional infrastructure
