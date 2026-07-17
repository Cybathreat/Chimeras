# Security and Legal

## Authorization

Chimeras is a penetration testing tool designed for **authorized security testing only**. You must have explicit written permission to test any target before running Chimeras against it.

## Human-in-Loop Gate

Chimeras includes a hard gate between vulnerability detection and exploitation:

- After Bloodhound identifies vulnerabilities, the pipeline pauses
- The operator reviews the vulnerability report
- The operator explicitly approves or denies exploitation
- No exploitation bot runs without human approval

The `--approve` flag bypasses the interactive prompt for headless/automated runs. Use this only in controlled environments (CI/CD, demo, lab) where the operator has pre-authorized exploitation.

## Scope Enforcement

Each bot is restricted to a tool category. The scope enforcer blocks any tool outside a bot's category before execution. This prevents:
- Recon bots from running exploits
- Exfiltration bots from scanning
- Any bot from running tools outside its authorized scope

## Audit Trail

Every tool execution is logged:
- Raw tool output saved to `engagement/raw/` directory
- Timestamped action log in `engagement/log.md`
- Per-bot work logs in `engagement/*.md` files
- All findings accumulated in `engagement/findings.md`

This provides a complete audit trail for compliance and post-engagement review.

## Responsible Use

- **Do not** run Chimeras against targets you do not own or have written authorization to test
- **Do not** bypass the human approval gate in production engagements
- **Do not** use the `--approve` flag for production engagements — it's for headless/demonstration use only
- **Always** review the final report for accuracy before delivering to a client
- **Always** verify findings are from the remote target, not local filesystem artifacts

## Disclaimer

The authors of Chimeras are not responsible for misuse of this tool. The operator bears full responsibility for ensuring they have proper authorization before testing any target. Unauthorized penetration testing is illegal in most jurisdictions.