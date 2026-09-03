"""
Chimeras v3.2 — Ticketing Export

Exports findings to ticketing system formats for dev team handoff.
Consultants hand off to dev teams in one command. SARIF is for tools;
tickets are for humans.

Supported formats:
- Jira CSV (importable via Jira Import CSV feature)
- ServiceNow JSON (REST API importable)
- GitLab Issues (curl/API importable)
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

_SEVERITY_TO_JIRA_PRIORITY = {
    "critical": "Highest",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "info": "Lowest",
}

_SEVERITY_TO_GITLAB_LABEL = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "info": "info",
}


def export_jira_csv(
    output_path: Path,
    findings: List[Dict[str, Any]],
    project_key: str = "PENTEST",
) -> bool:
    """Export findings as Jira-importable CSV.

    Jira CSV import expects columns: Summary, Description, Priority, Labels, etc.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for f in findings:
        fid = f.get("id") or f.get("finding_id", "")
        severity = (f.get("severity") or "info").lower()
        priority = _SEVERITY_TO_JIRA_PRIORITY.get(severity, "Low")

        description_parts = [
            f"Finding ID: {fid}",
            f"CVSS: {f.get('cvss', 'N/A')}",
            f"Status: {f.get('status', 'N/A')}",
            f"Host: {f.get('host', 'N/A')}",
            "",
            f"Description: {f.get('description', 'N/A')}",
            "",
            f"Risks: {f.get('risks', 'N/A')}",
            "",
            f"Attack Vectors: {f.get('attack_vectors', 'N/A')}",
            "",
            f"Proof of Existence: {f.get('proof_of_existence', 'N/A')}",
            "",
            f"Remediation: {f.get('remediation', 'N/A')}",
        ]

        if f.get("evidence_hash"):
            description_parts.append(f"\nEvidence Hash: {f['evidence_hash']}")

        rows.append({
            "Summary": f"[{fid}] {f.get('title', 'Untitled Finding')}",
            "Description": "\n".join(description_parts),
            "Priority": priority,
            "Labels": f"security pentest {severity}",
            "Issue Type": "Bug",
            "Project": project_key,
        })

    try:
        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            if rows:
                writer = csv.DictWriter(csvfile, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
        logger.info(f"Jira CSV exported: {len(rows)} findings → {output_path.name}")
        return True
    except Exception as e:
        logger.error(f"Jira CSV export failed: {e}")
        raise


def export_servicenow_json(
    output_path: Path,
    findings: List[Dict[str, Any]],
) -> bool:
    """Export findings as ServiceNow-importable JSON."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tickets = []
    for f in findings:
        fid = f.get("id") or f.get("finding_id", "")
        severity = (f.get("severity") or "info").lower()

        tickets.append({
            "short_description": f"[{fid}] {f.get('title', 'Untitled Finding')}",
            "description": f.get("description", "N/A"),
            "urgency": severity if severity in ("critical", "high", "medium", "low") else "low",
            "impact": severity if severity in ("critical", "high", "medium", "low") else "low",
            "category": "Security",
            "sub_category": "Vulnerability",
            "business_service": f.get("host", "N/A"),
            "cvss_score": f.get("cvss", "N/A"),
            "remediation": f.get("remediation", "N/A"),
            "evidence": f.get("proof_of_existence", "N/A"),
            "source": "Chimeras v3.2",
            "finding_id": fid,
        })

    try:
        output_path.write_text(json.dumps({"tickets": tickets}, indent=2))
        logger.info(f"ServiceNow JSON exported: {len(tickets)} findings → {output_path.name}")
        return True
    except Exception as e:
        logger.error(f"ServiceNow JSON export failed: {e}")
        raise


def export_gitlab_issues(
    output_path: Path,
    findings: List[Dict[str, Any]],
    project_id: int = 1,
) -> bool:
    """Export findings as GitLab issues JSON (importable via API).

    Each issue includes title, description with markdown, and labels.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    issues = []
    for f in findings:
        fid = f.get("id") or f.get("finding_id", "")
        severity = (f.get("severity") or "info").lower()
        label = _SEVERITY_TO_GITLAB_LABEL.get(severity, "info")

        body_parts = [
            f"**Severity:** {f.get('severity', 'N/A')} | **CVSS:** {f.get('cvss', 'N/A')} | **Status:** {f.get('status', 'N/A')}",
            "",
            f"## Description",
            f.get("description", "N/A"),
            "",
            f"## Risks",
            f.get("risks", "N/A"),
            "",
            f"## Attack Vectors",
            f.get("attack_vectors", "N/A"),
            "",
            f"## Proof of Existence",
            f"```{f.get('proof_of_existence', 'N/A')}```",
            "",
            f"## Remediation",
            f.get("remediation", "N/A"),
        ]

        if f.get("evidence_hash"):
            body_parts.append(f"\n**Evidence Hash:** `{f['evidence_hash']}`")

        issues.append({
            "title": f"[{fid}] {f.get('title', 'Untitled Finding')}",
            "description": "\n".join(body_parts),
            "labels": [label, "security", "pentest"],
            "project_id": project_id,
        })

    try:
        output_path.write_text(json.dumps({"issues": issues}, indent=2))
        logger.info(f"GitLab issues exported: {len(issues)} findings → {output_path.name}")
        return True
    except Exception as e:
        logger.error(f"GitLab issues export failed: {e}")
        raise


def export_all_tickets(
    output_dir: Path,
    findings: List[Dict[str, Any]],
    project_key: str = "PENTEST",
    project_id: int = 1,
) -> Dict[str, bool]:
    """Export findings to all ticketing formats.

    Returns dict of format → success bool.
    """
    output_dir = Path(output_dir)
    results = {}

    try:
        export_jira_csv(output_dir / "findings_jira.csv", findings, project_key)
        results["jira_csv"] = True
    except Exception:
        results["jira_csv"] = False

    try:
        export_servicenow_json(output_dir / "findings_servicenow.json", findings)
        results["servicenow_json"] = True
    except Exception:
        results["servicenow_json"] = False

    try:
        export_gitlab_issues(output_dir / "findings_gitlab.json", findings, project_id)
        results["gitlab_issues"] = True
    except Exception:
        results["gitlab_issues"] = False

    return results