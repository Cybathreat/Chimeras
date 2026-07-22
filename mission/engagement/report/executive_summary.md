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

The engagement completed passive reconnaissance and partial active scanning. A scope enforcement bug in the testing platform prevented direct targeting of www.raksha.tn, significantly limiting the depth of application-layer enumeration. Directory enumeration, API endpoint discovery, JavaScript bundle analysis, and security header auditing were all incomplete as a result. No exploitation, privilege escalation, or data exfiltration phases were reac