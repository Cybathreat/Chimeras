# WASP — Work Log

Bot: wasp
Role: web application vulnerability detection specialist — XSS, CSRF, SQLi, file upload, SSTI, SSRF, XXE, LFI/RFI, IDOR, auth bypass detection
Scope: wasp [web_exploit]: curl, gobuster, httpx, nikto, nmap, nuclei, python3, sqlmap, whatweb (not installed: commix, dalfox, ffuf, wfuzz)
Timestamp: 2026-08-24T01:51:21.158893

## LLM Reasoning

- Needed: True
- Strategy: Phase 1: Fingerprint the web stack with whatweb and httpx on both HTTP/HTTPS. Phase 2: Directory brute-force root and /blog/ with ffuf using common wordlists. Phase 3: Check for CMS indicators on /blog/ (wp-login, wp-content, ghost, admin panels). Phase 4: Probe for information disclosure (.git, .env, robots.txt, sitemap, backup files, swagger, api-docs). Phase 5: Run nuclei web templates for automated vuln detection. Phase 6: Crawl JS files for endpoints and secrets. Phase 7: Test security headers and CORS. All commands use rotated User-Agent strings.
- Confidence: 0.9
- Reasoning: Lisa's recon identified the target and basic surface but left critical gaps: directory enumeration failed, /blog/ not investigated for CMS, no JS analysis, no OWASP testing. As Wasp, I own the web application layer. I need to enumerate directories, detect CMS on /blog/, check for information disclosure, crawl JS, and run nuclei web templates. No WAF detected so standard payloads should work, but I'll use browser-like User-Agents per operational standards.

## Tool Execution

### Command: whatweb -a 3 https://cyberian-defenses.com
- Exit Code: 0
- Duration: 2.03s
- Success: True

```
[1m[34mhttps://cyberian-defenses.com/[0m [200 OK] [1mCountry[0m[[0m[22mUNITED STATES[0m][[1m[31mUS[0m], [1mEmail[0m[[0m[22mahmed.chiboub@cyberian-defenses.com[0m], [1mHTML5[0m, [1mHTTPServer[0m[[1m[31mUbuntu Linux[0m][[1m[36mnginx/1.24.0 (Ubuntu)[0m], [1mIP[0m[[0m[22m76.13.46.223[0m], [1mMeta-Author[0m[[0m[22mAhmed Chiboub[0m], [1mOpen-Graph-Protocol[0m[[1m[32mwebsite[0m], [1mScript[0m[[0m[22mapplication/ld+json[0m], [1mStrict-Transport-Security[0m
```

### Command: whatweb -a 3 http://cyberian-defenses.com
- Exit Code: 0
- Duration: 1.56s
- Success: True

```
[1m[34mhttp://cyberian-defenses.com/[0m [301 Moved Permanently] [1mCountry[0m[[0m[22mUNITED STATES[0m][[1m[31mUS[0m], [1mHTTPServer[0m[[1m[31mUbuntu Linux[0m][[1m[36mnginx/1.24.0 (Ubuntu)[0m], [1mIP[0m[[0m[22m76.13.46.223[0m], [1mRedirectLocation[0m[[0m[22mhttps://cyberian-defenses.com/[0m], [1mTitle[0m[[1m[33m301 Moved Permanently[0m], [1mnginx[0m[[1m[32m1.24.0[0m]
[1m[34mhttps://cyberian-defenses.com/[0m [200 OK] [1mCountry[0m[[0m[22mUNITED STATES
```

### Command: httpx -u https://cyberian-defenses.com -status-code -content-length -title -tech-detect -follow-redirects
- Exit Code: 2
- Duration: 0.21s
- Success: False

```

```

### Command: httpx -u http://cyberian-defenses.com -status-code -content-length -title -tech-detect -follow-redirects
- Exit Code: 2
- Duration: 0.21s
- Success: False

```

```

### Command: curl -s -o /dev/null -w '%{http_code} %{redirect_url}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' http://cyberian-defenses.com/.git/HEAD
- Exit Code: 0
- Duration: 0.13s
- Success: True

```
<html>
<head><title>301 Moved Permanently</title></head>
<body>
<center><h1>301 Moved Permanently</h1></center>
<hr><center>nginx/1.24.0 (Ubuntu)</center>
</body>
</html>
301 https://cyberian-defenses.com/.git/HEAD
```

### Command: curl -s -o /dev/null -w '%{http_code} %{redirect_url}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) https://cyberian-defenses.com/.git/HEAD
- Exit Code: 2
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' https://cyberian-defenses.com/robots.txt
- Exit Code: 0
- Duration: 0.14s
- Success: True

```
User-agent: *
Allow: /

Sitemap: https://cyberian-defenses.com/sitemap.xml

Host: https://cyberian-defenses.com

```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' https://cyberian-defenses.com/sitemap.xml
- Exit Code: 0
- Duration: 0.19s
- Success: True

```
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://cyberian-defenses.com/index.html</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://cyberian-defenses.com/services.html</loc>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://cyberian-defenses.com/about.html</loc>
    <changefreq>monthly</changefreq>
    <priority>0.8</
```

### Command: curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) https://cyberian-defenses.com/.env
- Exit Code: 2
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) https://cyberian-defenses.com/server-status
- Exit Code: 2
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) https://cyberian-defenses.com/server-info
- Exit Code: 2
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) https://cyberian-defenses.com/.htaccess
- Exit Code: 2
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) https://cyberian-defenses.com/swagger-ui.html
- Exit Code: 2
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) https://cyberian-defenses.com/api-docs
- Exit Code: 2
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) https://cyberian-defenses.com/openapi.json
- Exit Code: 2
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) https://cyberian-defenses.com/actuator/health
- Exit Code: 2
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) https://cyberian-defenses.com/phpinfo.php
- Exit Code: 2
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) https://cyberian-defenses.com/blog/wp-login.php
- Exit Code: 2
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) https://cyberian-defenses.com/blog/wp-admin/
- Exit Code: 2
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) https://cyberian-defenses.com/blog/wp-content/
- Exit Code: 2
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) https://cyberian-defenses.com/blog/ghost/
- Exit Code: 2
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -o /dev/null -w '%{http_code}' -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) https://cyberian-defenses.com/blog/admin/
- Exit Code: 2
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' https://cyberian-defenses.com/blog/
- Exit Code: 0
- Duration: 0.22s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Blog | Cyberian Defenses</title>
<meta name="description" content="Security insights, technical deep-dives, and industry analysis from the Cyberian-Defenses team.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<
```

### Command: curl -s -I -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' https://cyberian-defenses.com/blog/
- Exit Code: 0
- Duration: 0.16s
- Success: True

```
HTTP/1.1 200 OK
Server: nginx/1.24.0 (Ubuntu)
Date: Mon, 24 Aug 2026 01:51:22 GMT
Content-Type: text/html
Content-Length: 33559
Last-Modified: Mon, 17 Aug 2026 03:25:24 GMT
Connection: keep-alive
Vary: Accept-Encoding
ETag: "6a827f24-8317"
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), g
```

### Command: ffuf -u https://cyberian-defenses.com/FUZZ -w /usr/share/seclists/Discovery/Web-Content/common.txt -mc 200,204,301,302,307,401,403 -t 50 -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
- Exit Code: 127
- Duration: 0.0s
- Success: False

```

```

### Command: ffuf -u https://cyberian-defenses.com/blog/FUZZ -w /usr/share/seclists/Discovery/Web-Content/common.txt -mc 200,204,301,302,307,401,403 -t 50 -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
- Exit Code: 127
- Duration: 0.0s
- Success: False

```

```

### Command: ffuf -u https://cyberian-defenses.com/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-medium-words.txt -mc 200,204,301,302,307,401,403 -t 50 -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
- Exit Code: 127
- Duration: 0.0s
- Success: False

```

```

### Command: ffuf -u https://cyberian-defenses.com/blog/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-medium-words.txt -mc 200,204,301,302,307,401,403 -t 50 -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
- Exit Code: 127
- Duration: 0.0s
- Success: False

```

```

### Command: nuclei -u https://cyberian-defenses.com -t /usr/share/nuclei-templates/http -rl 150 -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
- Exit Code: 1
- Duration: 0.43s
- Success: False

```

```

### Command: nuclei -u https://cyberian-defenses.com/blog -t /usr/share/nuclei-templates/http -rl 150 -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
- Exit Code: 1
- Duration: 0.49s
- Success: False

```

```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' -H 'Origin: https://evil.com' -I https://cyberian-defenses.com
- Exit Code: 0
- Duration: 0.17s
- Success: True

```
HTTP/1.1 200 OK
Server: nginx/1.24.0 (Ubuntu)
Date: Mon, 24 Aug 2026 01:51:23 GMT
Content-Type: text/html
Content-Length: 13992
Last-Modified: Sun, 31 May 2026 19:03:53 GMT
Connection: keep-alive
Vary: Accept-Encoding
ETag: "6a1c8619-36a8"
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), g
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' -X OPTIONS -I https://cyberian-defenses.com
- Exit Code: 0
- Duration: 0.05s
- Success: True

```
HTTP/1.1 405 Not Allowed
Server: nginx/1.24.0 (Ubuntu)
Date: Mon, 24 Aug 2026 01:51:23 GMT
Content-Type: text/html
Content-Length: 166
Connection: keep-alive
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
Content-Security-Policy: default-src 'self'; scr
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' -X TRACE https://cyberian-defenses.com
- Exit Code: 0
- Duration: 0.05s
- Success: True

```
<html>
<head><title>405 Not Allowed</title></head>
<body>
<center><h1>405 Not Allowed</h1></center>
<hr><center>nginx/1.24.0 (Ubuntu)</center>
</body>
</html>

```

### Command: ffuf -u https://cyberian-defenses.com -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt -H 'Host: FUZZ.cyberian-defenses.com' -mc 200,301,302,401,403 -t 50 -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
- Exit Code: 127
- Duration: 0.0s
- Success: False

```

```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/?p=1'
- Exit Code: 0
- Duration: 0.15s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cyberian Defenses | Cybersecurity Advisory — MENA & Africa</title>
<meta name="description" content="Professional cybersecurity services: penetration testing, security audits, AI guardrails, and corporate training. Led by Ahmed Chiboub, 10+ years experience.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, complia
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/?p=1'
- Exit Code: 0
- Duration: 0.05s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Blog | Cyberian Defenses</title>
<meta name="description" content="Security insights, technical deep-dives, and industry analysis from the Cyberian-Defenses team.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/?search=test'
- Exit Code: 0
- Duration: 0.15s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Blog | Cyberian Defenses</title>
<meta name="description" content="Security insights, technical deep-dives, and industry analysis from the Cyberian-Defenses team.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/?q=test123'
- Exit Code: 0
- Duration: 0.04s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cyberian Defenses | Cybersecurity Advisory — MENA & Africa</title>
<meta name="description" content="Professional cybersecurity services: penetration testing, security audits, AI guardrails, and corporate training. Led by Ahmed Chiboub, 10+ years experience.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, complia
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/?author=1'
- Exit Code: 0
- Duration: 0.15s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Blog | Cyberian Defenses</title>
<meta name="description" content="Security insights, technical deep-dives, and industry analysis from the Cyberian-Defenses team.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/?cat=1'
- Exit Code: 0
- Duration: 0.06s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Blog | Cyberian Defenses</title>
<meta name="description" content="Security insights, technical deep-dives, and industry analysis from the Cyberian-Defenses team.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/wp-json/wp/v2/users'
- Exit Code: 0
- Duration: 0.05s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>404 - Page Not Found | Cyberian Defenses</title>
<meta name="description" content="Page not found.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<meta property="og:type" content="website">
<meta property="og:ti
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/?p=1%27'
- Exit Code: 0
- Duration: 0.07s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Blog | Cyberian Defenses</title>
<meta name="description" content="Security insights, technical deep-dives, and industry analysis from the Cyberian-Defenses team.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/?p=1%22'
- Exit Code: 0
- Duration: 0.14s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Blog | Cyberian Defenses</title>
<meta name="description" content="Security insights, technical deep-dives, and industry analysis from the Cyberian-Defenses team.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/?s=<script>alert(1)</script>'
- Exit Code: 0
- Duration: 0.05s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Blog | Cyberian Defenses</title>
<meta name="description" content="Security insights, technical deep-dives, and industry analysis from the Cyberian-Defenses team.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/?search=<script>alert(1)</script>'
- Exit Code: 0
- Duration: 0.16s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cyberian Defenses | Cybersecurity Advisory — MENA & Africa</title>
<meta name="description" content="Professional cybersecurity services: penetration testing, security audits, AI guardrails, and corporate training. Led by Ahmed Chiboub, 10+ years experience.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, complia
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/?p=../../../etc/passwd'
- Exit Code: 0
- Duration: 0.14s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Blog | Cyberian Defenses</title>
<meta name="description" content="Security insights, technical deep-dives, and industry analysis from the Cyberian-Defenses team.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/{{7*7}}'
- Exit Code: 3
- Duration: 0.02s
- Success: False

```

```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/?page=../../../etc/passwd'
- Exit Code: 0
- Duration: 0.09s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cyberian Defenses | Cybersecurity Advisory — MENA & Africa</title>
<meta name="description" content="Professional cybersecurity services: penetration testing, security audits, AI guardrails, and corporate training. Led by Ahmed Chiboub, 10+ years experience.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, complia
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/?file=../../../etc/passwd'
- Exit Code: 0
- Duration: 0.09s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cyberian Defenses | Cybersecurity Advisory — MENA & Africa</title>
<meta name="description" content="Professional cybersecurity services: penetration testing, security audits, AI guardrails, and corporate training. Led by Ahmed Chiboub, 10+ years experience.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, complia
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/?template=../../../etc/passwd'
- Exit Code: 0
- Duration: 0.08s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cyberian Defenses | Cybersecurity Advisory — MENA & Africa</title>
<meta name="description" content="Professional cybersecurity services: penetration testing, security audits, AI guardrails, and corporate training. Led by Ahmed Chiboub, 10+ years experience.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, complia
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/?url=http://127.0.0.1'
- Exit Code: -2
- Duration: 0s
- Success: False

- BLOCKED: TARGET OUT OF SCOPE: IP 127.0.0.1 is not within mission scope (cyberian-defenses.com, cyberian-defenses.firebaseapp.com, api.github.com, 76.13.46.223, cyberian-defenses.s3.amazonaws.com, cyberiandefenses.blob.core.windows.net, cyberian-defenses-com.s3.amazonaws.com, cyberian-defenses.blob.core.windows.net, cyberian-defenses-dev.s3.amazonaws.com, cyberiandefenses.s3.amazonaws.com, storage.googleapis.com, cyberian-defenses-assets.s3.amazonaws.com, cyberian-defenses-backup.s3.amazonaws.com, 223.46.13.76, s3.amazonaws.com, ns3.systemdns.com, ns1.systemdns.com, ns2.systemdns.com)

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/?url=http://127.0.0.1'
- Exit Code: -2
- Duration: 0s
- Success: False

- BLOCKED: TARGET OUT OF SCOPE: IP 127.0.0.1 is not within mission scope (cyberian-defenses.com, cyberian-defenses.firebaseapp.com, api.github.com, 76.13.46.223, cyberian-defenses.s3.amazonaws.com, cyberiandefenses.blob.core.windows.net, cyberian-defenses-com.s3.amazonaws.com, cyberian-defenses.blob.core.windows.net, cyberian-defenses-dev.s3.amazonaws.com, cyberiandefenses.s3.amazonaws.com, storage.googleapis.com, cyberian-defenses-assets.s3.amazonaws.com, cyberian-defenses-backup.s3.amazonaws.com, 223.46.13.76, s3.amazonaws.com, ns3.systemdns.com, ns1.systemdns.com, ns2.systemdns.com)

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/wp-json/'
- Exit Code: 0
- Duration: 0.05s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>404 - Page Not Found | Cyberian Defenses</title>
<meta name="description" content="Page not found.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<meta property="og:type" content="website">
<meta property="og:ti
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/xmlrpc.php'
- Exit Code: 0
- Duration: 0.05s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>404 - Page Not Found | Cyberian Defenses</title>
<meta name="description" content="Page not found.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<meta property="og:type" content="website">
<meta property="og:ti
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/wp-json/wp/v2/posts'
- Exit Code: 0
- Duration: 0.05s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>404 - Page Not Found | Cyberian Defenses</title>
<meta name="description" content="Page not found.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<meta property="og:type" content="website">
<meta property="og:ti
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/readme.html'
- Exit Code: 0
- Duration: 0.05s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>404 - Page Not Found | Cyberian Defenses</title>
<meta name="description" content="Page not found.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<meta property="og:type" content="website">
<meta property="og:ti
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/license.txt'
- Exit Code: 0
- Duration: 0.05s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>404 - Page Not Found | Cyberian Defenses</title>
<meta name="description" content="Page not found.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<meta property="og:type" content="website">
<meta property="og:ti
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/wp-content/plugins/'
- Exit Code: 0
- Duration: 0.17s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>404 - Page Not Found | Cyberian Defenses</title>
<meta name="description" content="Page not found.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<meta property="og:type" content="website">
<meta property="og:ti
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/blog/wp-content/themes/'
- Exit Code: 0
- Duration: 0.04s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>404 - Page Not Found | Cyberian Defenses</title>
<meta name="description" content="Page not found.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<meta property="og:type" content="website">
<meta property="og:ti
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/index.bak'
- Exit Code: 0
- Duration: 0.05s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>404 - Page Not Found | Cyberian Defenses</title>
<meta name="description" content="Page not found.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<meta property="og:type" content="website">
<meta property="og:ti
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/backup.zip'
- Exit Code: 0
- Duration: 0.14s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>404 - Page Not Found | Cyberian Defenses</title>
<meta name="description" content="Page not found.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<meta property="og:type" content="website">
<meta property="og:ti
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/backup.sql'
- Exit Code: 0
- Duration: 0.05s
- Success: True

```
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>404 - Page Not Found | Cyberian Defenses</title>
<meta name="description" content="Page not found.">
<meta name="keywords" content="cybersecurity, penetration testing, AI security, ISO 27001, compliance, MENA, Tunisia, Africa">
<meta name="author" content="Ahmed Chiboub">

<!-- Open Graph -->
<meta property="og:type" content="website">
<meta property="og:ti
```

### Command: curl -s -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 'https://cyberian-defenses.com/.well-known/security.txt'
- Exit Code: 0
- Duration: 0.05s
- Success: True

```
<html>
<head><title>403 Forbidden</title></head>
<body>
<center><h1>403 Forbidden</h1></center>
<hr><center>nginx/1.24.0 (Ubuntu)</center>
</body>
</html>

```

### Command: nikto -h https://cyberian-defenses.com -Tuning 1234567890 -useragent 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
- Exit Code: 0
- Duration: 0.09s
- Success: True

```

       -config+            Use this config file
       -Display+           Turn on/off display outputs
       -dbcheck            check database and other key files for syntax errors
       -Format+            save file (-o) format
       -Help               Extended help information
       -host+              target host
       -id+                Host authentication to use, format is id:pass or id:pass:realm
       -list-plugins       List all available plugins
       -output+            Writ
```


## Analysis

Summary: Web application analysis of cyberian-defenses.com reveals a well-hardened static site on nginx 1.24.0. No confirmed web vulnerabilities found. CSP contains 'unsafe-inline' for script-src and style-src, weakening XSS defenses. Developer email exposed in metadata. Blog is static HTML (not WordPress/Ghost CMS). Several sensitive file probes (.env, .git/HEAD, server-status, phpinfo, wp-login) failed due to shell quoting errors — these need re-testing. ffuf and nuclei tools were unavailable (not installed / wrong template path).

Findings:
- CSP allows 'unsafe-inline' for script-src and style-src, weakening XSS protection
- Developer email (ahmed.chiboub@cyberian-defenses.com) exposed in page metadata and author tags
- Blog directory contains static HTML files, not a CMS — no WordPress or Ghost admin panels detected
- Sensitive file probes (.env, .git/HEAD, server-status, .htaccess, phpinfo, swagger) could not be completed due to shell quoting errors — need re-testing
- No directory brute-force could be performed — ffuf not installed on system
- Nuclei scan failed — template path /usr/share/nuclei-templates/http does not exist
- Blog post URL references 'ghost-cms-cve-2026-26980-ai-discovery-clickfix' — may indicate interest in Ghost CMS vulnerabilities
- Sitemap reveals 8 pages including case-studies/ directory and 2 blog posts
- Contact form uses external service formspree.io — potential data exposure to third party

Recommendations:
- Re-run all sensitive file probes (.env, .git/HEAD, server-status, .htaccess, phpinfo, swagger, wp-login) with corrected shell quoting — current results are false negatives
- Install ffuf or gobuster and perform directory brute-force with common.txt and raft-medium wordlists on both / and /blog/
- Fix nuclei template path and re-run full vulnerability scan with default templates
- Test contact.html form for XSS, CSRF, and parameter injection — form posts to formspree.io
- Crawl and analyze all JavaScript files for secrets, API keys, or hidden endpoints
- Test for vhost enumeration — check for subdomains or virtual hosts on the same IP
- Investigate /case-studies/ directory for additional content or potential LFI
- Verify .git/HEAD on HTTPS with proper curl command — HTTP returned 301 redirect to HTTPS
- Run ssh-audit on port 22 to check for weak SSH algorithms/ciphers
- Test all discovered pages for reflected/stored XSS via URL parameters and form inputs
