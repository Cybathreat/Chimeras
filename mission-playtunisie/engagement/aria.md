# ARIA — Work Log

Bot: aria
Role: passive reconnaissance specialist — OSINT, DNS, subdomains, tech stack, internal network recon
Scope: aria [passive_recon]: curl, dig, host, httpx, whatweb, whois (not installed: amass, censys, crtsh, dnsrecon, dnsx, fierce, ghdb, shodan, subfinder, theHarvester, wafw00f, waybackurls)
Timestamp: 2026-08-24T01:18:37.610402

## LLM Reasoning

- Needed: True
- Strategy: Full passive reconnaissance sweep: DNS all record classes + zone transfer attempt, WHOIS/RDAP, certificate transparency via crt.sh, web fingerprinting with whatweb/httpx/curl headers, page source for JS endpoint extraction, robots.txt/sitemap.xml, subdomain permutation validation via dig, SRV records for AD/service discovery, DKIM/DMARC check, predictable cloud bucket checks, and HTTP header analysis on main domain over HTTP and HTTPS.
- Confidence: 0.95
- Reasoning: Init phase with zero prior data. I must build the complete attack surface map before Lisa can scan. DNS topology, subdomains from CT logs, tech stack with versions, WAF/CDN detection, cloud assets, email/SPF/DMARC posture, and takeover candidates all need to be established passively. No active scanning — only lookups, passive HTTP requests, and OSINT sources.

## Tool Execution

### Command: dig playtunisie.com A
- Exit Code: 0
- Duration: 0.02s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 63984
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;playtunisie.com.		IN	A

;; ANSWER SECTION:
playtunisie.com.	430	IN	A	34.76.215.208

;; Query time: 0 msec
;; SERVER: 127.0.0.53#53(127.0.0.53) (UDP)
;; WHEN: Mon Aug 24 03:18:37 CEST 
```

### Command: dig playtunisie.com AAAA
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> playtunisie.com AAAA
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 52262
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;playtunisie.com.		IN	AAAA

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 22 msec
;;
```

### Command: dig playtunisie.com MX
- Exit Code: 0
- Duration: 0.02s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> playtunisie.com MX
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 265
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 9

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;playtunisie.com.		IN	MX

;; ANSWER SECTION:
playtunisie.com.	413	IN	MX	10 mail.playtunisie.com.

;; ADDITIONAL SECTION:
playtunisie.com.	413	IN	NS	ns10.lwsdns.com.
playtunisie.com.	413
```

### Command: dig playtunisie.com TXT
- Exit Code: 0
- Duration: 0.03s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> playtunisie.com TXT
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 63214
;; flags: qr rd ra; QUERY: 1, ANSWER: 2, AUTHORITY: 0, ADDITIONAL: 8

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;playtunisie.com.		IN	TXT

;; ANSWER SECTION:
playtunisie.com.	413	IN	TXT	"v=spf1 mx:playtunisie.com a:mail.playtunisie.com a:mailphp.lws-hosting.com -all"
playtunisie.com.	413	IN	TX
```

### Command: dig playtunisie.com NS
- Exit Code: 0
- Duration: 0.03s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> playtunisie.com NS
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 44217
;; flags: qr rd ra; QUERY: 1, ANSWER: 4, AUTHORITY: 0, ADDITIONAL: 6

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;playtunisie.com.		IN	NS

;; ANSWER SECTION:
playtunisie.com.	413	IN	NS	ns12.lwsdns.com.
playtunisie.com.	413	IN	NS	ns10.lwsdns.com.
playtunisie.com.	413	IN	NS	ns9.lwsdns.com.
playtun
```

### Command: dig playtunisie.com SOA
- Exit Code: 0
- Duration: 0.02s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> playtunisie.com SOA
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 20139
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 9

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;playtunisie.com.		IN	SOA

;; ANSWER SECTION:
playtunisie.com.	413	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; ADDITIONAL SECTION:
playtun
```

### Command: dig playtunisie.com CAA
- Exit Code: 0
- Duration: 0.02s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> playtunisie.com CAA
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 15213
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;playtunisie.com.		IN	CAA

;; AUTHORITY SECTION:
playtunisie.com.	414	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 6 msec
;; SE
```

### Command: dig playtunisie.com DNSKEY
- Exit Code: 0
- Duration: 0.03s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> playtunisie.com DNSKEY
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: SERVFAIL, id: 36882
;; flags: qr aa rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;playtunisie.com.		IN	DNSKEY

;; Query time: 0 msec
;; SERVER: 127.0.0.53#53(127.0.0.53) (UDP)
;; WHEN: Mon Aug 24 03:18:37 CEST 2026
;; MSG SIZE  rcvd: 44


```

### Command: dig playtunisie.com ANY
- Exit Code: 0
- Duration: 0.06s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> playtunisie.com ANY
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 52422
;; flags: qr rd ra; QUERY: 1, ANSWER: 9, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;playtunisie.com.		IN	ANY

;; ANSWER SECTION:
playtunisie.com.	900	IN	TXT	"v=spf1 mx:playtunisie.com a:mail.playtunisie.com a:mailphp.lws-hosting.com -all"
playtunisie.com.	900	IN	TX
```

### Command: dig axfr playtunisie.com @ns1.playtunisie.com
- Exit Code: 1
- Duration: 0.07s
- Success: False

```

```

### Command: dig www.playtunisie.com A
- Exit Code: 0
- Duration: 0.03s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> www.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 44759
;; flags: qr rd ra; QUERY: 1, ANSWER: 2, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;www.playtunisie.com.		IN	A

;; ANSWER SECTION:
www.playtunisie.com.	429	IN	CNAME	playtunisie.com.
playtunisie.com.	429	IN	A	34.76.215.208

;; Query time: 0 msec
;; SERVER: 127.0.0
```

### Command: dig www.playtunisie.com CNAME
- Exit Code: 0
- Duration: 0.03s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> www.playtunisie.com CNAME
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 5956
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 2

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;www.playtunisie.com.		IN	CNAME

;; ANSWER SECTION:
www.playtunisie.com.	428	IN	CNAME	playtunisie.com.

;; ADDITIONAL SECTION:
playtunisie.com.	428	IN	A	34.76.215.208

;; Query 
```

### Command: dig mail.playtunisie.com A
- Exit Code: 0
- Duration: 0.03s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> mail.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 20465
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;mail.playtunisie.com.		IN	A

;; ANSWER SECTION:
mail.playtunisie.com.	6732	IN	A	193.203.239.21

;; Query time: 0 msec
;; SERVER: 127.0.0.53#53(127.0.0.53) (UDP)
;; WHEN: Mon Aug 
```

### Command: dig dev.playtunisie.com A
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> dev.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 45830
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;dev.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 22 msec
```

### Command: dig staging.playtunisie.com A
- Exit Code: 0
- Duration: 0.04s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> staging.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 114
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;staging.playtunisie.com.	IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 26
```

### Command: dig test.playtunisie.com A
- Exit Code: 0
- Duration: 0.03s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> test.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 42564
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;test.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	429	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 6 mse
```

### Command: dig api.playtunisie.com A
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> api.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 6052
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;api.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 22 msec

```

### Command: dig admin.playtunisie.com A
- Exit Code: 0
- Duration: 0.04s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> admin.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 41007
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;admin.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 25 
```

### Command: dig vpn.playtunisie.com A
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> vpn.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 14983
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;vpn.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 24 msec
```

### Command: dig app.playtunisie.com A
- Exit Code: 0
- Duration: 0.04s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> app.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 18262
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;app.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 16 msec
```

### Command: dig blog.playtunisie.com A
- Exit Code: 0
- Duration: 0.03s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> blog.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 43978
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;blog.playtunisie.com.		IN	A

;; ANSWER SECTION:
blog.playtunisie.com.	813	IN	A	34.77.166.175

;; Query time: 0 msec
;; SERVER: 127.0.0.53#53(127.0.0.53) (UDP)
;; WHEN: Mon Aug 24
```

### Command: dig shop.playtunisie.com A
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> shop.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 13724
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;shop.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 27 ms
```

### Command: dig portal.playtunisie.com A
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> portal.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 52153
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;portal.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 2
```

### Command: dig git.playtunisie.com A
- Exit Code: 0
- Duration: 0.04s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> git.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 24294
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;git.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 22 msec
```

### Command: dig jenkins.playtunisie.com A
- Exit Code: 0
- Duration: 0.06s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> jenkins.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 64607
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;jenkins.playtunisie.com.	IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 
```

### Command: dig intranet.playtunisie.com A
- Exit Code: 0
- Duration: 0.06s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> intranet.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 203
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;intranet.playtunisie.com.	IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 
```

### Command: dig cpanel.playtunisie.com A
- Exit Code: 0
- Duration: 0.04s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> cpanel.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 56398
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;cpanel.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	432	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 8
```

### Command: dig webmail.playtunisie.com A
- Exit Code: 0
- Duration: 0.04s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> webmail.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 4457
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;webmail.playtunisie.com.	IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 2
```

### Command: dig autodiscover.playtunisie.com A
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> autodiscover.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 151
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;autodiscover.playtunisie.com.	IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Quer
```

### Command: dig ftp.playtunisie.com A
- Exit Code: 0
- Duration: 0.03s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> ftp.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 48693
;; flags: qr rd ra; QUERY: 1, ANSWER: 2, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;ftp.playtunisie.com.		IN	A

;; ANSWER SECTION:
ftp.playtunisie.com.	429	IN	CNAME	playtunisie.com.
playtunisie.com.	429	IN	A	34.76.215.208

;; Query time: 1 msec
;; SERVER: 127.0.0
```

### Command: dig secure.playtunisie.com A
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> secure.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 37046
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;secure.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 2
```

### Command: dig m.playtunisie.com A
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> m.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 32308
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;m.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 24 msec
;; 
```

### Command: dig cdn.playtunisie.com A
- Exit Code: 0
- Duration: 0.06s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> cdn.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 31140
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;cdn.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 29 msec
```

### Command: dig static.playtunisie.com A
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> static.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 50166
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;static.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 2
```

### Command: dig assets.playtunisie.com A
- Exit Code: 0
- Duration: 0.04s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> assets.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 40005
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;assets.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 1
```

### Command: dig backup.playtunisie.com A
- Exit Code: 0
- Duration: 0.03s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> backup.playtunisie.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 55208
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;backup.playtunisie.com.		IN	A

;; AUTHORITY SECTION:
playtunisie.com.	429	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query time: 7
```

### Command: dig _ldap._tcp.playtunisie.com SRV
- Exit Code: 0
- Duration: 0.03s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> _ldap._tcp.playtunisie.com SRV
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 60297
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;_ldap._tcp.playtunisie.com.	IN	SRV

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Qu
```

### Command: dig _kerberos._tcp.playtunisie.com SRV
- Exit Code: 0
- Duration: 0.02s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> _kerberos._tcp.playtunisie.com SRV
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 15681
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;_kerberos._tcp.playtunisie.com.	IN	SRV

;; AUTHORITY SECTION:
playtunisie.com.	412	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 90
```

### Command: dig _gc._tcp.playtunisie.com SRV
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> _gc._tcp.playtunisie.com SRV
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 53401
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;_gc._tcp.playtunisie.com.	IN	SRV

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Query 
```

### Command: dig _sip._tcp.playtunisie.com SRV
- Exit Code: 0
- Duration: 0.05s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> _sip._tcp.playtunisie.com SRV
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 43301
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;_sip._tcp.playtunisie.com.	IN	SRV

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 604800 900

;; Quer
```

### Command: dig _autodiscover._tcp.playtunisie.com SRV
- Exit Code: 0
- Duration: 0.04s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> _autodiscover._tcp.playtunisie.com SRV
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 9555
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;_autodiscover._tcp.playtunisie.com. IN	SRV

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 60
```

### Command: dig default._domainkey.playtunisie.com TXT
- Exit Code: 0
- Duration: 0.03s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> default._domainkey.playtunisie.com TXT
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 60572
;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 1, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;default._domainkey.playtunisie.com. IN	TXT

;; AUTHORITY SECTION:
playtunisie.com.	900	IN	SOA	ns9.lwsdns.com. hostmaster.playtunisie.com. 1783091714 25200 3600 6
```

### Command: dig _dmarc.playtunisie.com TXT
- Exit Code: 0
- Duration: 0.06s
- Success: True

```

; <<>> DiG 9.18.39-0ubuntu0.24.04.6-Ubuntu <<>> _dmarc.playtunisie.com TXT
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 14967
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 65494
;; QUESTION SECTION:
;_dmarc.playtunisie.com.		IN	TXT

;; ANSWER SECTION:
_dmarc.playtunisie.com.	3600	IN	TXT	"v=DMARC1; p=quarantine;"

;; Query time: 30 msec
;; SERVER: 127.0.0.53#53(127.0.0.53)
```

### Command: whois playtunisie.com
- Exit Code: 0
- Duration: 0.09s
- Success: True

```
   Domain Name: PLAYTUNISIE.COM
   Registry Domain ID: 2552736751_DOMAIN_COM-VRSN
   Registrar WHOIS Server: whois.lws.net
   Registrar URL: http://www.lws.fr/nom-de-domaine.php
   Updated Date: 2026-07-01T14:15:36Z
   Creation Date: 2020-08-13T13:56:03Z
   Registry Expiry Date: 2027-08-13T13:56:03Z
   Registrar: Ligne Web Services SAS dba LWS
   Registrar IANA ID: 1630
   Registrar Abuse Contact Email: abuse@lws.fr
   Registrar Abuse Contact Phone: 0177627129
   Domain Status: clientTransferPro
```

### Command: curl -sI https://playtunisie.com
- Exit Code: 28
- Duration: 136.18s
- Success: False

```

```

### Command: curl -sI http://playtunisie.com
- Exit Code: 28
- Duration: 135.17s
- Success: False

```

```

### Command: curl -sI https://www.playtunisie.com
- Exit Code: 28
- Duration: 135.17s
- Success: False

```

```

### Command: curl -sI http://www.playtunisie.com
- Exit Code: 28
- Duration: 135.17s
- Success: False

```

```

### Command: whatweb -a 3 https://playtunisie.com
- Exit Code: 0
- Duration: 16.44s
- Success: True

```

```

### Command: whatweb -a 3 http://playtunisie.com
- Exit Code: 0
- Duration: 15.9s
- Success: True

```

```

### Command: httpx -sc -title -tech-detect -follow-redirects -u https://playtunisie.com
- Exit Code: 2
- Duration: 0.18s
- Success: False

```

```

### Command: curl -s https://playtunisie.com
- Exit Code: 28
- Duration: 135.41s
- Success: False

```

```

### Command: curl -s http://playtunisie.com
- Exit Code: 28
- Duration: 135.16s
- Success: False

```

```

### Command: curl -s https://playtunisie.com/robots.txt
- Exit Code: 0
- Duration: 68.14s
- Success: True

```
# robots.txt automatically generated by PrestaShop e-commerce open-source solution
# http://www.prestashop.com - http://www.prestashop.com/forums
# This file is to prevent the crawling and indexing of certain parts
# of your site by web crawlers and spiders run by sites like Yahoo!
# and Google. By telling these "robots" where not to go on your site,
# you save bandwidth and server resources.
# For more information about the robots.txt standard, see:
# http://www.robotstxt.org/robotstxt.html
Use
```

### Command: curl -s https://playtunisie.com/sitemap.xml
- Exit Code: 0
- Duration: 0.3s
- Success: True

```
<!doctype html>
<html lang="fr">

  <head>
    
      





  <meta charset="utf-8">


  <meta http-equiv="x-ua-compatible" content="ie=edge">






<!-- safwen, manually adding tagmanager, and removing desinstalling  google analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XNNPS1YCN8"></script>

<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=AW-825632289">
</script>


<script>
  window.dataLayer = window.dataLayer || [];
```

### Command: curl -s http://playtunisie.com/robots.txt
- Exit Code: 0
- Duration: 0.03s
- Success: True

```
# robots.txt automatically generated by PrestaShop e-commerce open-source solution
# http://www.prestashop.com - http://www.prestashop.com/forums
# This file is to prevent the crawling and indexing of certain parts
# of your site by web crawlers and spiders run by sites like Yahoo!
# and Google. By telling these "robots" where not to go on your site,
# you save bandwidth and server resources.
# For more information about the robots.txt standard, see:
# http://www.robotstxt.org/robotstxt.html
Use
```

### Command: curl -s http://playtunisie.com/sitemap.xml
- Exit Code: 0
- Duration: 0.29s
- Success: True

```
<!doctype html>
<html lang="fr">

  <head>
    
      





  <meta charset="utf-8">


  <meta http-equiv="x-ua-compatible" content="ie=edge">






<!-- safwen, manually adding tagmanager, and removing desinstalling  google analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XNNPS1YCN8"></script>

<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=AW-825632289">
</script>


<script>
  window.dataLayer = window.dataLayer || [];
```

### Command: curl -s https://crt.sh/?q=playtunisie.com&output=json
- Exit Code: 0
- Duration: 0.1s
- Success: True

```
<html>
<head><title>502 Bad Gateway</title></head>
<body>
<center><h1>502 Bad Gateway</h1></center>
<hr><center>nginx</center>
</body>
</html>

```

### Command: curl -s https://crt.sh/?q=%.playtunisie.com&output=json
- Exit Code: 0
- Duration: 0.1s
- Success: True

```
<html>
<head><title>502 Bad Gateway</title></head>
<body>
<center><h1>502 Bad Gateway</h1></center>
<hr><center>nginx</center>
</body>
</html>

```

### Command: curl -s https://playtunisie.com.s3.amazonaws.com
- Exit Code: -2
- Duration: 0s
- Success: False

- BLOCKED: TARGET OUT OF SCOPE: hostname 'playtunisie.com.s3.amazonaws.com' is not within mission scope (playtunisie.com, playtunisie.com)

### Command: curl -s https://s3.amazonaws.com/playtunisie.com
- Exit Code: -2
- Duration: 0s
- Success: False

- BLOCKED: TARGET OUT OF SCOPE: hostname 's3.amazonaws.com' is not within mission scope (playtunisie.com, playtunisie.com)

### Command: curl -sI https://storage.googleapis.com/playtunisie.com
- Exit Code: -2
- Duration: 0s
- Success: False

- BLOCKED: TARGET OUT OF SCOPE: hostname 'storage.googleapis.com' is not within mission scope (playtunisie.com, playtunisie.com)

### Command: curl -sI https://playtunisie.com.blob.core.windows.net
- Exit Code: -2
- Duration: 0s
- Success: False

- BLOCKED: TARGET OUT OF SCOPE: hostname 'playtunisie.com.blob.core.windows.net' is not within mission scope (playtunisie.com, playtunisie.com)


## Analysis

Summary: Passive DNS reconnaissance of playtunisie.com revealed a Google Cloud-hosted web server (34.76.215.208), LWS Hosting DNS infrastructure, a separate mail server (193.203.239.21), conflicting SPF records, no DNSSEC, no CAA, and no IPv6. Common subdomain brute (dev, staging, test, api, admin, vpn) returned NXDOMAIN. Additional 44 commands were truncated.

Findings:
- Main domain hosted on Google Cloud Platform (34.76.215.208)
- Mail server on separate LWS Hosting IP (193.203.239.21)
- Conflicting SPF TXT records — two separate SPF1 entries
- No DNSSEC configured — DNSKEY query returns SERVFAIL
- No CAA records — unrestricted certificate authority issuance
- No IPv6 (AAAA) support
- DNS managed by LWS Hosting (ns9-12.lwsdns.com)
- www subdomain is CNAME to apex domain
- Common subdomains (dev, staging, test, api, admin, vpn) do not exist (NXDOMAIN)

Recommendations:
- Lisa: Perform active port scan on 34.76.215.208 (web) and 193.239.21 (mail) — focus on 80/443/22/25/587/993
- Lisa: Run HTTP fingerprinting on playtunisie.com — identify web server, CMS, framework versions
- Lisa: Check for WAF presence and bypass testing on web endpoints
- Aria: Query crt.sh for certificate transparency subdomain discovery (crt.sh?q=playtunisie.com)
- Aria: Perform passive DNS lookup via SecurityTrails or VirusTotal for historical subdomains
- Aria: Fetch and analyze JS files from playtunisie.com for API endpoints and secrets
- Aria: Attempt zone transfer against actual LWS nameservers (ns9-12.lwsdns.com)
- Lisa: Test SMTP on mail.playtunisie.com for open relay, AUTH brute, VRFY/EXPN enumeration
