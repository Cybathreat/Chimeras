"""
Chimeras v2.0 — Bookkeeper Agent

Logger/auditor. Reads all engagement files, generates final report.
No tool execution — file I/O only.

v2 Phase 4.5: Cleanup & rollback section.
  - Iterates target_artifacts from state
  - Documents what was left on target and cleanup status
  - Flags uncleaned artifacts prominently in the report

v2 Phase 5: Decision audit trail.
  - Reads warchief_decisions.log
  - Includes engagement flow with all routing decisions
  - Adds decision metrics (total cycles, why engagement ended)
  - Writes machine-readable audit JSON alongside markdown report
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from core.base_bot import BaseBot
from core.state import SwarmState
from core.report_template import render_report
from core.findings_store import FindingsStore
from core.sarif_exporter import write_sarif
from core.pdf_exporter import export_pdf, is_pdf_available
from core.docx_exporter import export_docx, is_docx_available
from core.evidence import EvidenceLocker
from core.compliance import ComplianceMapper


class Bookkeeper(BaseBot):
    """Bookkeeper — Logger and Report Generator. No tools, reads files only.

    v2 Phase 4.5 + 5: Cleanup documentation and decision audit trail.
    """

    bot_name = "bookkeeper"
    role_description = "operation logger and report generator — reads all findings, generates final report with cleanup status and decision audit trail"
    scope_description = "Report generation ONLY. Reads engagement files, generates final report. NO tool execution."

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        super().__init__(state, swarm_config)
        # v2.4: Findings store for lossless report generation
        self.findings_store = FindingsStore(self.engagement_dir)

    def _build_system_prompt(self) -> str:
        """Override — Bookkeeper doesn't run tools, it reads files and generates reports."""
        soul_block = ""
        if self._soul:
            soul_block = f"## Your Soul\n\n{self._soul}\n\n---\n\n"
        return f"""{soul_block}You are {self.bot_name}, {self.role_description}.

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

## 5. Engagement Flow (Decision Audit Trail)
[Document the sequence of phases the swarm went through. Include WarChief's routing decisions and reasoning. This is the audit trail showing how the engagement progressed from recon to report. List each phase, what was found, and WarChief's decision to proceed, loop back, or abort.]

## 6. Cleanup & Rollback Status
[List ALL artifacts left on target during the engagement — dropped payloads, scheduled tasks, created users, modified configs. For each artifact, document:
- Host where artifact was left
- Type (payload, scheduled task, user, config change)
- Path or location
- Whether cleanup was attempted
- Whether cleanup succeeded or failed

If any artifacts were NOT cleaned up, flag them prominently with ⚠ WARNING. The client needs to know exactly what was left on their systems.]

## 7. Conclusion
[Overall security posture assessment, summary of risk, priority remediation order]

## 8. Appendix
- Tools Used: [list]
- Raw Output Files: [count, locations]
- Bots Deployed: [list]
- Total Decision Cycles: [count]
- Engagement Ended Because: [mission complete / scope exhausted / authorization issues / insufficient data]

## Response Format
Respond with the complete report as markdown. Do NOT wrap in JSON. Do NOT wrap in code blocks. Just write the report directly."""

    async def run(self) -> Dict[str, Any]:
        """Bookkeeper override — reads all engagement files, generates report.

        v2 Phase 4.5: Includes cleanup status from target_artifacts.
        v2 Phase 5: Includes decision audit trail from warchief_decisions.log.
        Also writes machine-readable audit JSON.
        """
        self._banner()
        self._log("Bot awakened — reading engagement files", "WAKE")
        self._append_log("Bot awakened — generating final report")

        try:
            # Build context from all engagement files
            context = self._build_context()
            system = self._build_system_prompt()

            # ─── Phase 5: Read decision audit trail ───
            decision_log = self._read_decision_log()
            if decision_log:
                context += f"\n\n## WarChief Decision Log (Audit Trail)\n{decision_log}"

            # ─── Phase 4.5: Read artifact tracking ───
            artifacts = self.state.get("target_artifacts", [])
            if artifacts:
                context += "\n\n## Artifacts Left on Target (Cleanup Tracking)\n"
                context += self._format_artifacts_for_report(artifacts)

            # v3.0.2 NOTE: tool_requests.csv is deliberately NOT included in
            # the client report. It is internal arsenal-improvement data.
            # Per-engagement copy: engagement/tool_requests.csv
            # Cross-engagement accumulator: tool_requests_registry.csv (repo root)

            # Ask LLM to generate the report
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
                report_response = (
                    f"# Final Report — Generation Failed\n\n"
                    f"**Error**: {e}\n\n"
                    f"**Timestamp**: {datetime.utcnow().isoformat()}\n\n"
                    f"The automated report generator encountered an error.\n"
                    f"Check engagement files in {self.state.get('engagement_dir', 'N/A')} for raw findings.\n"
                )

            # Strip markdown code block wrappers if present
            report_text = report_response.strip()
            if report_text.startswith("```"):
                first_nl = report_text.find("\n")
                if first_nl != -1:
                    report_text = report_text[first_nl + 1:]
                if report_text.rstrip().endswith("```"):
                    report_text = report_text.rstrip()[:-3].rstrip()

            # Write the report
            self._write_report("final_report.md", report_text)

            # Also write executive summary
            self._write_report("executive_summary.md", report_text[:2000])

            # v2.4: Generate structured report from lossless findings store
            # The LLM report is the narrative. The structured report is the
            # deterministic, schema-validated version. Both are written.
            try:
                # Merge all per-bot findings into one file
                self.findings_store.merge_all()

                # Get structured findings for the template
                structured_findings = self.findings_store.format_for_report()
                critical_findings = self.findings_store.format_critical_for_report()

                # Extract engagement metadata
                mission = self.state.get("mission", {})
                targets = self.state.get("discovered_targets", [])
                if not targets:
                    target_str = mission.get("target", "N/A")
                    targets = [target_str] if target_str else []

                # Decision audit trail
                decision_log_text = self._read_decision_log() or "N/A"

                # Cleanup status
                artifacts = self.state.get("target_artifacts", [])
                if artifacts:
                    cleanup_status = self._format_artifacts_for_report(artifacts)
                else:
                    cleanup_status = "No artifacts left on target."

                # Engagement flow — LLM writes this, we extract from report
                engagement_flow = "See decision audit trail below.\n\n" + decision_log_text

                # Mission outcome
                last_decision = self.state.get("last_decision", "report")
                mission_outcome = f"Engagement ended with decision: {last_decision}"

                # Generate the structured report
                structured_report = render_report(
                    engagement_name=mission.get("target", "N/A"),
                    client_name="",
                    executive_summary=report_text[:2000],  # LLM writes this
                    mission_scope=mission.get("scope", "N/A"),
                    internal_scope=self.state.get("internal_scope", ""),
                    roe=mission.get("roe", "N/A"),
                    targets=targets,
                    findings=structured_findings,
                    engagement_flow=engagement_flow,
                    critical_findings=critical_findings,
                    decision_audit=decision_log_text,
                    cleanup_status=cleanup_status,
                    mission_outcome=mission_outcome,
                )

                self._write_report("structured_report.md", structured_report)

                # v3.0: SARIF 2.1.0 export for GitHub code-scanning / SOAR integration
                try:
                    all_findings = self.findings_store.get_all()
                    sarif_path = self.engagement_dir / "report" / "findings.sarif"
                    write_sarif(all_findings, sarif_path)
                    self._log(f"SARIF exported: {len(all_findings)} findings → {sarif_path.name}", "SARIF")
                except Exception as e:
                    self._log(f"SARIF export failed: {e}", "ERROR")

                # v3.1: PDF report export — the client-ready deliverable
                try:
                    pdf_path = self.engagement_dir / "report" / "pentest_report.pdf"
                    export_pdf(
                        output_path=pdf_path,
                        engagement_name=mission.get("target", "N/A"),
                        client_name="",
                        executive_summary=report_text[:2000],
                        mission_scope=mission.get("scope", "N/A"),
                        internal_scope=self.state.get("internal_scope", ""),
                        roe=mission.get("roe", "N/A"),
                        targets=targets,
                        findings=structured_findings,
                        engagement_flow=engagement_flow,
                        critical_findings=critical_findings,
                        decision_audit=decision_log_text,
                        cleanup_status=cleanup_status,
                        mission_outcome=mission_outcome,
                    )
                    self._log(f"PDF exported: {len(structured_findings)} findings → {pdf_path.name}", "PDF")
                except Exception as e:
                    self._log(f"PDF export failed: {e}", "ERROR")

                # v3.1: DOCX report export — for clients who need Word format
                try:
                    docx_path = self.engagement_dir / "report" / "pentest_report.docx"
                    export_docx(
                        output_path=docx_path,
                        engagement_name=mission.get("target", "N/A"),
                        client_name="",
                        executive_summary=report_text[:2000],
                        mission_scope=mission.get("scope", "N/A"),
                        internal_scope=self.state.get("internal_scope", ""),
                        roe=mission.get("roe", "N/A"),
                        targets=targets,
                        findings=structured_findings,
                        engagement_flow=engagement_flow,
                        critical_findings=critical_findings,
                        decision_audit=decision_log_text,
                        cleanup_status=cleanup_status,
                        mission_outcome=mission_outcome,
                    )
                    self._log(f"DOCX exported: {len(structured_findings)} findings → {docx_path.name}", "DOCX")
                except Exception as e:
                    self._log(f"DOCX export failed: {e}", "ERROR")

                # v3.1: Evidence Locker — SHA-256 hashed evidence chain
                try:
                    locker = EvidenceLocker(self.engagement_dir)
                    evidence_manifest = locker.collect_all(structured_findings)
                    self._log(
                        f"Evidence locker: {evidence_manifest['total_artifacts']} artifacts, "
                        f"manifest hash: {evidence_manifest['manifest_hash'][:16]}...",
                        "EVIDENCE"
                    )

                    # Enrich findings with evidence hashes for PDF/DOCX
                    structured_findings = locker.get_findings_with_hashes(structured_findings)

                    # Verify manifest integrity
                    if locker.verify_manifest():
                        self._log("Evidence manifest verified (tamper-free)", "EVIDENCE")
                    else:
                        self._log("Evidence manifest verification FAILED", "WARN")
                except Exception as e:
                    self._log(f"Evidence locker failed: {e}", "ERROR")

                # v3.1: Compliance Mapper — OWASP ASVS / PCI DSS / ISO 27001 / NIST 800-53
                try:
                    mapper = ComplianceMapper()
                    compliance_data = mapper.format_for_report(structured_findings)

                    # Enrich findings with compliance mappings
                    structured_findings = mapper.map_findings(structured_findings)

                    # Write compliance report
                    compliance_path = self.engagement_dir / "report" / "compliance_mapping.md"
                    compliance_path.parent.mkdir(parents=True, exist_ok=True)
                    compliance_path.write_text(compliance_data["formatted_text"])
                    self._log(
                        f"Compliance mapping: {compliance_data['summary']['mapped_findings']}/"
                        f"{compliance_data['summary']['total_findings']} findings mapped → "
                        f"compliance_mapping.md",
                        "COMPLIANCE"
                    )
                except Exception as e:
                    self._log(f"Compliance mapping failed: {e}", "ERROR")

                self._log(f"Structured report generated: {len(structured_findings)} findings, "
                          f"{len(critical_findings)} critical", "REPORT")
            except Exception as e:
                self._log(f"Structured report generation failed: {e}", "ERROR")

            # ─── Phase 4.5: Write cleanup report ───
            cleanup_report = self._generate_cleanup_report()
            if cleanup_report:
                self._write_report("cleanup_report.md", cleanup_report)

            # ─── Phase 5: Write machine-readable audit JSON ───
            audit_json = self._generate_audit_json()
            if audit_json:
                try:
                    if self.engagement_dir is None:
                        raise ValueError("No engagement directory set")
                    audit_path = self.engagement_dir / "report" / "engagement_audit.json"
                    audit_path.parent.mkdir(parents=True, exist_ok=True)
                    audit_path.write_text(json.dumps(audit_json, indent=2))
                    self._log(f"Audit JSON written to {audit_path.name}", "REPORT")
                except Exception as e:
                    self._log(f"Failed to write audit JSON: {e}", "ERROR")

            # Write bot file
            self._write_bot_file(
                f"# {self.bot_name.upper()} — Final Report\n\n"
                f"Report generated and saved to report/final_report.md\n"
                f"Structured report: report/structured_report.md\n"
                f"PDF report: report/pentest_report.pdf\n"
                f"DOCX report: report/pentest_report.docx\n"
                f"SARIF export: report/findings.sarif\n"
                f"Compliance mapping: report/compliance_mapping.md\n"
                f"Evidence locker: evidence/evidence_manifest.json\n"
                f"Cleanup report: {'report/cleanup_report.md' if artifacts else 'N/A (no artifacts)'}\n"
                f"Audit JSON: report/engagement_audit.json\n"
            )

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

        except Exception as e:
            # Full exception handling — never leave engagement with zero output
            self._log(f"Bookkeeper run error: {e}", "ERROR")
            self._append_log(f"ERROR: Bookkeeper failed: {e}")
            try:
                error_report = (
                    f"# Penetration Test Report — Generation Failed\n\n"
                    f"**Error**: {e}\n\n"
                    f"**Timestamp**: {datetime.utcnow().isoformat()}\n\n"
                    f"The report generator encountered a fatal error.\n"
                    f"Check engagement files for raw findings.\n"
                )
                self._write_report("final_report.md", error_report)
                self._write_bot_file(f"# {self.bot_name.upper()} — FAILED\n\nError: {e}\n")
            except Exception:
                # Absolute last resort
                print(f"[BOOKKEEPER] Could not write any report: {e}")
            return {"report": "", "executed": False, "error": str(e)}

    def _read_decision_log(self) -> str:
        """Read warchief_decisions.log and format for inclusion in report.

        v2 Phase 5: Decision audit trail.
        """
        try:
            if self.engagement_dir is None:
                return ""
            log_path = self.engagement_dir / "warchief_decisions.log"
            if not log_path.exists():
                return ""

            lines = log_path.read_text().strip().split("\n")
            if not lines or lines == [""]:
                return ""

            formatted = []
            for i, line in enumerate(lines, 1):
                try:
                    entry = json.loads(line)
                    decision = entry.get("decision", "?")
                    confidence = entry.get("confidence", 0)
                    reasoning = entry.get("reasoning", "")[:100]
                    phase = entry.get("mission_state", entry.get("mission_phase", "?"))
                    overrides = []
                    if entry.get("confidence_override"):
                        overrides.append("confidence")
                    if entry.get("scope_exhausted_override"):
                        overrides.append("scope_exhausted")
                    if entry.get("backtrack_override"):
                        overrides.append("backtrack")
                    override_str = f" [overrides: {', '.join(overrides)}]" if overrides else ""
                    formatted.append(
                        f"  {i}. [{phase}] → {decision} (confidence: {confidence:.2f}){override_str}\n"
                        f"     Reasoning: {reasoning}"
                    )
                except (json.JSONDecodeError, Exception):
                    formatted.append(f"  {i}. [unparseable entry]")

            return "\n".join(formatted)
        except Exception as e:
            print(f"[BOOKKEEPER] Failed to read decision log: {e}")
            return ""

    def _format_artifacts_for_report(self, artifacts: List[Dict[str, Any]]) -> str:
        """Format target_artifacts for inclusion in the LLM context.

        v2 Phase 4.5: Cleanup tracking.
        """
        try:
            if not artifacts:
                return "No artifacts left on target.\n"

            lines = ["| Host | Type | Path | Cleaned | Description |"]
            lines.append("|------|------|------|---------|-------------|")
            for a in artifacts:
                if not isinstance(a, dict):
                    continue
                host = a.get("host", "unknown")
                art_type = a.get("artifact_type", "unknown")
                path = a.get("path", "unknown")
                cleaned = "✓ Yes" if a.get("cleaned", False) else "⚠ NO"
                desc = a.get("description", "")
                lines.append(f"| {host} | {art_type} | {path} | {cleaned} | {desc} |")

            uncleaned = [a for a in artifacts if isinstance(a, dict) and not a.get("cleaned", False)]
            if uncleaned:
                lines.append(f"\n⚠ WARNING: {len(uncleaned)} artifacts were NOT cleaned up!")
                lines.append("The client must manually verify and remove these.")

            return "\n".join(lines)
        except Exception as e:
            print(f"[BOOKKEEPER] Failed to format artifacts: {e}")
            return f"Error formatting artifacts: {e}\n"

    def _generate_cleanup_report(self) -> str:
        """Generate a standalone cleanup report.

        v2 Phase 4.5: Separate cleanup report for client.
        Lists all artifacts, cleanup status, and warnings for uncleaned items.
        """
        try:
            artifacts = self.state.get("target_artifacts", [])
            if not artifacts or not isinstance(artifacts, list):
                return ""

            lines = [
                "# Cleanup & Rollback Report",
                f"\nGenerated: {datetime.utcnow().isoformat()}\n",
                f"Total artifacts tracked: {len(artifacts)}\n",
            ]

            cleaned = [a for a in artifacts if isinstance(a, dict) and a.get("cleaned", False)]
            uncleaned = [a for a in artifacts if isinstance(a, dict) and not a.get("cleaned", False)]

            if cleaned:
                lines.append(f"\n## Cleaned Artifacts ({len(cleaned)})\n")
                for a in cleaned:
                    lines.append(f"- **{a.get('host', '?')}**: {a.get('artifact_type', '?')} at {a.get('path', '?')}")
                    if a.get("description"):
                        lines.append(f"  - {a['description']}")

            if uncleaned:
                lines.append(f"\n## ⚠ UNCLENED ARTIFACTS ({len(uncleaned)})\n")
                lines.append("**These artifacts were left on target and require manual removal.**\n")
                for a in uncleaned:
                    lines.append(f"- **{a.get('host', '?')}**: {a.get('artifact_type', '?')} at {a.get('path', '?')}")
                    if a.get("description"):
                        lines.append(f"  - {a['description']}")

            if not cleaned and not uncleaned:
                lines.append("\nNo artifacts were left on target during this engagement.")

            return "\n".join(lines)
        except Exception as e:
            print(f"[BOOKKEEPER] Failed to generate cleanup report: {e}")
            return ""

    def _generate_audit_json(self) -> Dict[str, Any]:
        """Generate machine-readable audit JSON.

        v2 Phase 5: Machine-readable engagement audit trail.
        Contains: decisions, metrics, bots deployed, artifacts, state at end.
        """
        try:
            # Read decision log entries
            decisions = []
            if self.engagement_dir is not None:
                log_path = self.engagement_dir / "warchief_decisions.log"
                if log_path.exists():
                    for line in log_path.read_text().strip().split("\n"):
                        try:
                            decisions.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass

            # Determine why engagement ended
            last_decision = self.state.get("last_decision", "report")
            end_reason_map = {
                "report": "mission complete or scope exhausted",
                "insufficient_data_abort": "insufficient data to continue",
                "init": "premature end (init phase)",
            }
            end_reason = end_reason_map.get(last_decision, f"ended with decision: {last_decision}")

            # Count artifacts
            artifacts = self.state.get("target_artifacts", [])
            cleaned_count = sum(1 for a in artifacts if isinstance(a, dict) and a.get("cleaned", False))
            uncleaned_count = len(artifacts) - cleaned_count

            audit = {
                "generated_at": datetime.utcnow().isoformat(),
                "mission": self.state.get("mission", {}),
                "bots_deployed": list(self.state.get("reasoning_reports", {}).keys()),
                "decision_count": len(decisions),
                "decisions": decisions,
                "end_reason": end_reason,
                "mission_state": self.state.get("mission_state", "unknown"),
                "target_context": self.state.get("target_context", "external"),
                "aggressiveness": self.state.get("aggressiveness", "cautious"),
                "loop_count": self.state.get("loop_count", {}),
                "scope_exhausted": self.state.get("scope_exhausted", False),
                "failed_vectors_count": len(self.state.get("failed_vectors", [])),
                "discovered_targets": self.state.get("discovered_targets", []),
                "exploited_hosts": self.state.get("exploited_hosts", []),
                "internal_targets": self.state.get("internal_targets", []),
                "artifacts_total": len(artifacts),
                "artifacts_cleaned": cleaned_count,
                "artifacts_uncleaned": uncleaned_count,
                "uncleaned_artifacts": [
                    a for a in artifacts if isinstance(a, dict) and not a.get("cleaned", False)
                ],
            }

            # v2.4: Add findings store summary to audit
            try:
                all_findings = self.findings_store.get_all()
                audit["findings_total"] = len(all_findings)
                audit["findings_critical"] = len(self.findings_store.get_critical())
                audit["findings_by_bot"] = {}
                for f in all_findings:
                    bot = f.get("source_bot", "unknown")
                    audit["findings_by_bot"][bot] = audit["findings_by_bot"].get(bot, 0) + 1
            except Exception:
                pass
            return audit
        except Exception as e:
            print(f"[BOOKKEEPER] Failed to generate audit JSON: {e}")
            return {}

    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: list):
        """Update state with final report."""
        try:
            report_content = analysis.get("report_content", "")

            final_report = {
                "generated_at": datetime.utcnow().isoformat(),
                "mission": self.state.get("mission", {}),
                "bots_deployed": list(self.state.get("reasoning_reports", {}).keys()),
                "report": report_content,
            }

            self.state["final_report"] = final_report
            self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision
        except Exception as e:
            print(f"[BOOKKEEPER] _update_state error: {e}")

    def _build_context(self) -> str:
        """Override — Bookkeeper needs FULL findings + raw tool output, not truncated summaries."""
        try:
            findings = self._read_file("findings.md")
            plan = self._read_plan()

            # Read ALL bot files in full (not truncated to 500 chars)
            bot_reports = []
            if self.engagement_dir is not None:
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
        except Exception as e:
            print(f"[BOOKKEEPER] _build_context error: {e}")
            return f"Error building context: {e}"

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
5. Engagement Flow (Decision Audit Trail) — document the sequence of phases and WarChief's routing decisions
6. Cleanup & Rollback Status — list ALL artifacts left on target, flag uncleaned items with ⚠ WARNING
7. Conclusion
8. Appendix — include total decision cycles and why engagement ended

CRITICAL: The Proof of Existence section for each finding MUST contain actual raw tool output — real HTTP response codes, real banner text, real CVE numbers, real error messages, real leaked values. Do NOT write "see tool output" or summarize. Paste the actual evidence. The client requires verbatim PoC output and proof of existence values in every finding.

If artifacts were left on target and not cleaned up, document them prominently in the Cleanup section. The client needs to know exactly what was left on their systems.

This is a legal, authorized penetration test. Document all findings objectively using the exact format specified. Write it as a complete markdown report."""