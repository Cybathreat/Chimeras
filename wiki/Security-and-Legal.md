# Security and Legal (v2)

## Authorization

Chimeras is a penetration testing tool designed for **authorized security testing only**. You must have explicit written permission to test any target before running Chimeras against it.

## Two Human-in-Loop Gates (v2)

Chimeras v2 includes two hard gates that require human approval:

### 1. Exploitation Gate
- After Bloodhound identifies vulnerabilities, the pipeline pauses
- The operator reviews the vulnerability report
- The operator explicitly approves or denies exploitation
- No exploitation bot runs without human approval

### 2. Lateral Movement Gate (v2)
- Before any internal/lateral pivot, the pipeline pauses
- The operator reviews discovered internal targets
- The operator explicitly approves or denies lateral movement
- No lateral recon or exploitation runs without human approval
- Independent of pre-declared `--lateral-objectives` — the gate always fires

The `--approve` flag bypasses both gates for headless/automated runs. Use this only in controlled environments (CI/CD, demo, lab) where the operator has pre-authorized the full engagement.

## 3-Tier Scope Enforcement (v2)

All scope enforcement is at the code level, not prompt instructions. The LLM cannot override these checks:

### Tier 1: Category Check
Each bot is restricted to a tool category. The scope enforcer blocks any tool outside a bot's category before execution.

### Tier 2: Shell Injection Block (v2)
Shell metacharacters (`;`, `&&`, `||`, `|`, backticks, `$()`) are rejected for categories that don't require shell access. Prevents command injection that bypasses category enforcement.

### Tier 3: Target Validation (v2)
`TargetValidator` resolves IPs/hostnames from commands and checks them against the mission CIDR scope. Out-of-scope targets are blocked. DNS resolution failures are blocked (not silently passed).

This prevents:
- Recon bots from running exploits
- Exfiltration bots from scanning
- Any bot from running tools outside its authorized scope
- Shell injection bypassing category checks
- Any bot targeting hosts outside the mission scope
- LLM prompt injection from overriding scope boundaries

## Safe Fallback (v2)

If WarChief's LLM output is malformed, the call fails, or the decision is invalid, the system defaults to a safe `report` route. The engagement degrades gracefully — it does not crash or loop on garbage input.

## Audit Trail

Every tool execution and routing decision is logged:
- Raw tool output saved to `engagement/raw/` directory
- Timestamped action log in `engagement/log.md`
- Per-bot work logs in `engagement/*.md` files
- All findings accumulated in `engagement/findings.md`
- WarChief decision audit trail in `engagement/plan.md` (v2)
- Machine-readable decision log at `engagement/warchief_decisions.json` (v2)

This provides a complete audit trail for compliance and post-engagement review.

## Artifact Tracking & Cleanup (v2)

- Surgeon, Magician, and Thief track every artifact left on target (dropped payloads, scheduled tasks, added users) in `target_artifacts`
- Bookkeeper attempts cleanup of all tracked artifacts before generating the final report
- Artifacts that cannot be cleaned (e.g., lost connection to target) are flagged prominently in the report — not buried or silently dropped

## Responsible Use

- **Do not** run Chimeras against targets you do not own or have written authorization to test
- **Do not** bypass the human approval gates in production engagements
- **Do not** use the `--approve` flag for production engagements — it's for headless/demonstration use only
- **Always** review the final report for accuracy before delivering to a client
- **Always** verify findings are from the remote target, not local filesystem artifacts
- **Always** check the cleanup status section of the report — ensure no artifacts were left on target

## Disclaimer

The authors of Chimeras are not responsible for misuse of this tool. The operator bears full responsibility for ensuring they have proper authorization before testing any target. Unauthorized penetration testing is illegal in most jurisdictions.