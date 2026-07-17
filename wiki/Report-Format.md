# Report Format

## Professional Penetration Test Report

The Bookkeeper bot generates a professional pentest report at `engagement/report/final_report.md`.

## Structure

```
# Penetration Test Report — [Mission Name]

## Scope
- Target(s)
- Objectives
- Rules of Engagement

## Executive Summary
- High-level overview of findings and risk posture
- Summary of vulnerabilities by severity

## Findings Summary
| ID | Finding | Severity | CVSS | Status |
|----|---------|----------|------|--------|
| FILL-001 | ... | Critical | 8.1 | Confirmed |
| FILL-002 | ... | High | 7.5 | Confirmed |
| ...

## Detailed Findings

### FILL-001: [Finding Title]
**Severity**: Critical | **CVSS**: 8.1 | **Status**: Confirmed

#### Description
What the vulnerability is and how it was identified.

#### Risks
Business and technical impact if exploited.

#### Attack Vectors
How an attacker could exploit this vulnerability.

#### Proof of Concept
Step-by-step reproduction of the exploit.

#### Proof of Existence
Evidence from tool output confirming the finding.

#### Remediation Plan
Specific, actionable steps to fix the vulnerability.
```

## How It Works

The Bookkeeper bot:
1. Reads all engagement files — `findings.md`, per-bot `.md` files, `log.md`
2. Sends all accumulated findings to the LLM with a system prompt explaining the professional pentest report format
3. The LLM generates the complete report as markdown
4. The report is saved directly as `final_report.md` — no JSON parsing, no truncation

The report generation uses `max_tokens=8192` to handle long reports with multiple findings.

## Important Note

Findings are only as accurate as the tools that found them. If a bot scans the local filesystem instead of the remote target (e.g., Magician running `find /` on the local server), those local artifacts will appear in the report. Always review findings for relevance to the engagement scope before delivering to a client.