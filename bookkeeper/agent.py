"""
Chimeras v1.0 — Bookkeeper Agent

Logger/auditor. Reads all engagement files, generates final report.
No tool execution — file I/O only.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import json

from core.base_bot import BaseBot
from core.state import SwarmState


class Bookkeeper(BaseBot):
    """Bookkeeper — Logger and Report Generator. No tools, reads files only."""

    bot_name = "bookkeeper"
    role_description = "operation logger and report generator — reads all findings, generates final report"
    scope_description = "Report generation ONLY. Reads engagement files, generates final report. NO tool execution."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)

    def _build_system_prompt(self) -> str:
        """Override — Bookkeeper doesn't run tools, it reads files and generates reports."""
        return f"""You are {self.bot_name}, {self.role_description}.

## Your Scope
{self.scope_description}

## Engagement Context
This is an AUTHORIZED penetration test. The client has signed off on all phases including exploitation and data exfiltration. All findings are part of the legal engagement scope. Your job is to document them objectively.

## Your Task
Read ALL engagement files and synthesize every finding into a professional penetration test report.

## Report Format (MANDATORY — follow this structure exactly)

# Penetration Test Report — [Target]

## 1. Scope
- Target: [domain/IP]
- Objectives: [from mission]
- Rules of Engagement: [from mission]
- Methodology: [bots used, tools run]
- Engagement Date: [date]

## 2. Executive Summary
[2-3 paragraph high-level overview: what was tested, what was found, overall risk rating, business impact]

## 3. Findings Summary
| ID | Finding | Severity | CVSS | Status |
|----|---------|----------|------|--------|
[FILL-001] | [name] | [Critical/High/Medium/Low/Info] | [score] | [Exploited/Not Exploited/Confirmed] |

## 4. Detailed Findings

For EACH finding, use this exact structure:

### FILL-00X: [Finding Name]

**Severity:** [Critical/High/Medium/Low/Info]
**CVSS Score:** [X.X]
**Affected Asset:** [host:port or URL]
**Status:** [Exploited / Confirmed / Not Exploited]

#### Description
[What the vulnerability is, in technical terms]

#### Risks
[Business impact: what an attacker could do if they exploited this, data exposure, system compromise, lateral movement potential]

#### Attack Vectors
[How an attacker would exploit this — step by step, from initial access to impact]

#### Proof of Concept
[The actual commands, payloads, or techniques used during the engagement to test this finding. Include EXACT tool commands that were run, verbatim. Show the full command string.]

#### Proof of Existence
[Evidence that the vulnerability exists. You MUST include ACTUAL RAW TOOL OUTPUT here — exact response codes, HTTP headers, DNS records, banner text, CVE matches, database entries, error messages, leaked data values. Do NOT summarize. Paste the real values from the engagement files. This is the critical evidence section — if there is raw output in the engagement files or raw/ folder, include it here verbatim.]

#### Remediation Plan
[Specific, actionable steps to fix this vulnerability. Include configuration changes, patches, version upgrades, architecture recommendations.]

---

[Repeat for each finding]

## 5. Conclusion
[Overall security posture assessment, summary of risk, priority remediation order]

## 6. Appendix
- Tools Used: [list]
- Raw Output Files: [count, locations]
- Bots Deployed: [list]

## Response Format
Respond with the complete report as markdown. Do NOT wrap in JSON. Do NOT wrap in code blocks. Just write the report directly."""

    async def run(self) -> Dict[str, Any]:
        """Bookkeeper override — doesn't use the standard JSON pipeline.
        Reads all engagement files, asks LLM for a plain-text report, writes it."""
        self._banner()
        self._log("Bot awakened — reading engagement files", "WAKE")
        self._append_log("Bot awakened — generating final report")

        # Build context from all engagement files
        context = self._build_context()
        system = self._build_system_prompt()

        # Ask LLM to generate the report as plain markdown (NOT JSON)
        self._log("Asking LLM to generate final report...", "THINK")
        report_prompt = self._build_analysis_prompt("", context)

        try:
            report_response = self._llm(report_prompt, system, max_tokens=16384)
            self._log("LLM report received", "ANALYZE")

            print(f"\n[{self.bot_name.upper()} LLM REPORT]", flush=True)
            print(report_response[:2000], flush=True)
            print(f"[/{self.bot_name.upper()} LLM REPORT]\n", flush=True)
        except Exception as e:
            self._log(f"LLM report generation failed: {e}", "ERROR")
            report_response = f"# Final Report — Generation Failed\n\nError: {e}\n\nPlease check engagement files manually."

        # Strip any markdown code block wrappers if present
        report_text = report_response.strip()
        if report_text.startswith("```"):
            # Remove opening ```markdown or ```
            first_nl = report_text.find("\n")
            if first_nl != -1:
                report_text = report_text[first_nl + 1:]
            if report_text.rstrip().endswith("```"):
                report_text = report_text.rstrip()[:-3].rstrip()

        # Write the report
        self._write_report("final_report.md", report_text)

        # Also write executive summary (first section)
        self._write_report("executive_summary.md", report_text[:2000])

        # Write bot file
        self._write_bot_file(f"# {self.bot_name.upper()} — Final Report\n\nReport generated and saved to report/final_report.md\n")

        # Update findings
        self._append_findings("Final Report", report_text[:3000])

        self._append_log("Final report generated and saved")

        # Update state
        self._update_state(
            {"needed": True, "strategy": "final report", "confidence": 1.0},
            {"report_content": report_text},
            []
        )

        self._log("Bot complete", "SLEEP")
        return {"report": report_text, "executed": True}

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with final report."""
        report_content = analysis.get("report_content", "")

        final_report = {
            "generated_at": datetime.utcnow().isoformat(),
            "mission": self.state.get("mission", {}),
            "bots_deployed": list(self.state.get("reasoning_reports", {}).keys()),
            "report": report_content,
        }

        self.state["final_report"] = final_report
        self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision

    def _build_context(self) -> str:
        """Override — Bookkeeper needs FULL findings + raw tool output, not truncated summaries."""
        findings = self._read_file("findings.md")
        log = self._read_log()
        plan = self._read_plan()

        # Read ALL bot files in full (not truncated to 500 chars)
        bot_reports = []
        for f in sorted(self.engagement_dir.glob("*.md")):
            if f.name in ("plan.md", "log.md", "findings.md"):
                continue
            bname = f.stem
            if bname == self.bot_name:
                continue
            content = f.read_text()
            bot_reports.append(f"### {bname}\n{content}")

        # Read raw tool output files — this is the actual PoC evidence
        raw_dir = self.engagement_dir / "raw"
        raw_outputs = []
        if raw_dir.exists():
            for rf in sorted(raw_dir.glob("*.txt")):
                try:
                    raw_content = rf.read_text()
                    # Include up to 4000 chars per raw file — enough for PoC evidence
                    if len(raw_content) > 4000:
                        raw_content = raw_content[:4000] + "\n... (truncated, see full in raw/ folder)"
                    raw_outputs.append(f"### Raw Output: {rf.name}\n```\n{raw_content}\n```")
                except Exception:
                    pass

        parts = []
        parts.append(f"## Target\n{self.state.get('mission', {}).get('target', 'N/A')}")
        parts.append(f"## Scope\n{self.state.get('mission', {}).get('scope', 'N/A')}")
        if plan:
            parts.append(f"## Plan\n{plan}")
        if findings:
            parts.append(f"## Findings (FULL)\n{findings}")
        if bot_reports:
            parts.append(f"## Bot Reports (FULL)\n{chr(10).join(bot_reports)}")
        if raw_outputs:
            parts.append(f"## Raw Tool Output (PoC Evidence)\n{chr(10).join(raw_outputs)}")

        return "\n\n".join(parts)

    def _build_analysis_prompt(self, raw_output: str, context: str) -> str:
        """Override — Bookkeeper's analysis IS the report."""
        return f"""## Engagement Files

Read all the context below — it contains findings from all bots that ran, plus raw tool output.

{context}

## Your Task
Generate a professional penetration test report following the MANDATORY format from your system prompt. The report MUST include:

1. Scope section with target, objectives, RoE, methodology
2. Executive summary with overall risk rating
3. Findings summary table (ID, Finding, Severity, CVSS, Status)
4. For EACH finding:
   - Description (technical)
   - Risks (business impact)
   - Attack Vectors (step-by-step exploitation path)
   - Proof of Concept (exact commands used — verbatim, full command strings)
   - Proof of Existence (ACTUAL RAW TOOL OUTPUT — paste the real values: HTTP response codes, headers, banners, CVE IDs, error messages, leaked data. Do NOT summarize. Include the verbatim evidence from the engagement files and raw tool output above.)
   - Remediation Plan (actionable fix steps)
5. Conclusion
6. Appendix

CRITICAL: The Proof of Existence section for each finding MUST contain actual raw tool output — real HTTP response codes, real banner text, real CVE numbers, real error messages, real leaked values. Do NOT write "see tool output" or summarize. Paste the actual evidence. The client requires verbatim PoC output and proof of existence values in every finding.

This is a legal, authorized penetration test. Document all findings objectively using the exact format specified. Write it as a complete markdown report."""