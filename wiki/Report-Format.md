# Report Format (v2)

## Professional Penetration Test Report

The Bookkeeper bot generates a professional pentest report at `engagement/report/final_report.md`. v2 adds decision audit trail, cleanup status, and mission metrics.

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

## Engagement Flow (v2)
- Initial plan
- Phase-by-phase WarChief routing decisions with reasoning
- Why the swarm ended (mission complete, scope exhausted, etc.)

### Phase 1: Reconnaissance
- ARIA Run 1: Found 3 subdomains, 2 mail servers
- WarChief Decision: Route to Lisa (scanning)
- Reasoning: Sufficient OSINT targets, proceed to active scan

### Phase 2: Scanning
- Lisa Run 1: Found 5 open ports on web server
- WarChief Decision: Route to Bloodhound (vuln detection)
- Reasoning: Sufficient scanning data, proceed to vulnerability detection

[etc.]

## Findings Summary
| ID | Finding | Severity | CVSS | Status |
|----|---------|----------|------|--------|
| FILL-001 | ... | Critical | 8.1 | Confirmed |
| FILL-002 | ... | High | 7.5 | Confirmed |

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

## Decision Metrics (v2)
- Total recon cycles: N
- Total scanning cycles: N
- Total exploitation cycles: N
- Total lateral movement cycles: N
- Decision flow: [text-based diagram or summary]

## Cleanup Status (v2)
- Artifacts tracked: N
- Artifacts removed: N
- Artifacts that could not be cleaned: N
- [Per artifact: host, type, path, status, reason if not cleaned]

## Mission Outcome (v2)
- Status: [Complete | Scope Exhausted | Authorization Issues | Target Hardened]
- Reason: [description]
```

## How It Works

The Bookkeeper bot:
1. Reads all engagement files — `findings.md`, per-bot `.md` files, `log.md`, `warchief_decisions.json`
2. Reads `target_artifacts` from state for cleanup/rollback
3. Sends all accumulated findings + decision history to the LLM with a system prompt explaining the professional pentest report format
4. The LLM generates the complete report as markdown, including engagement flow, decision metrics, and cleanup status
5. Attempts cleanup of all tracked artifacts before generating the report
6. Uncleaned artifacts are flagged prominently — not buried
7. The report is saved directly as `final_report.md` — no JSON parsing, no truncation

The report generation uses `max_tokens=8192` to handle long reports with multiple findings.

## Machine-Readable Decision Log (v2)

`engagement/warchief_decisions.json` contains a complete machine-readable log of all WarChief routing decisions with full context. Useful for auditing, replay, and learning.

## Important Note

Findings are only as accurate as the tools that found them. If a bot scans the local filesystem instead of the remote target (e.g., Magician running `find /` on the local server), those local artifacts will appear in the report. Always review findings for relevance to the engagement scope before delivering to a client.