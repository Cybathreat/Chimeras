"""
Chimeras v3.0 — SARIF 2.1.0 Exporter

Generates GitHub code-scanning compatible SARIF output from Chimeras findings.
Maps Pydantic Finding model to SARIF 2.1.0 result objects.

SARIF spec: https://json.schemastore.org/sarif-2.1.0.json
GitHub code-scanning uses this for vulnerability ingestion.

Integration:
    Bookkeeper calls write_sarif() at report time alongside structured_report.md.
    Output: findings.sarif in the engagement report directory.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# SARIF severity mapping (Chimeras 5-level → SARIF 3-level)
_SEVERITY_TO_LEVEL = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
}

# SARIF security-severity (0.0-10.0) from CVSS or severity label
_SEVERITY_TO_SCORE = {
    "critical": 9.5,
    "high": 7.5,
    "medium": 5.0,
    "low": 2.5,
    "info": 0.0,
}


def _extract_cwe(finding: Dict[str, Any]) -> Optional[str]:
    """Extract CWE ID from finding, normalizing various formats."""
    # Check explicit cwe field
    cwe = finding.get("cwe") or finding.get("CWE")
    if cwe:
        cwe_str = str(cwe).strip()
        if cwe_str.startswith("CWE-"):
            return cwe_str
        if cwe_str.isdigit():
            return f"CWE-{cwe_str}"
        return f"CWE-{cwe_str}"
    return None


def _extract_cve(finding: Dict[str, Any]) -> Optional[str]:
    """Extract CVE ID from finding."""
    cve = finding.get("cve") or finding.get("CVE")
    if cve:
        cve_str = str(cve).strip()
        if cve_str.startswith("CVE-"):
            return cve_str
    return None


def _get_security_severity(finding: Dict[str, Any]) -> str:
    """Get numeric security-severity score (0.0-10.0) as string for SARIF."""
    cvss = finding.get("cvss")
    if cvss is not None:
        try:
            score = float(cvss)
            return f"{score:.1f}"
        except (ValueError, TypeError):
            pass
    severity = (finding.get("severity") or "info").lower()
    return f"{_SEVERITY_TO_SCORE.get(severity, 0.0):.1f}"


def _get_logical_location(finding: Dict[str, Any]) -> Dict[str, Any]:
    """Build SARIF logicalLocation from finding host/port."""
    host = finding.get("host") or finding.get("target") or ""
    port = finding.get("port")
    service = finding.get("service") or ""

    parts = []
    if host:
        parts.append(host)
    if port:
        parts.append(str(port))
    if service:
        parts.append(service)

    return {
        "name": ":".join(parts) if parts else "unknown",
        "fullyQualifiedName": f"endpoint/{':'.join(parts)}" if parts else "endpoint/unknown",
    }


def _get_fixes(finding: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build SARIF fixes from remediation field."""
    remediation = finding.get("remediation") or ""
    if not remediation or remediation.strip().upper() == "TBD":
        return []
    return [{
        "description": {
            "text": remediation[:500],  # SARIF text fields can be large but we cap
        }
    }]


def finding_to_sarif_result(finding: Dict[str, Any], rule_id: str) -> Dict[str, Any]:
    """Convert a single Chimeras finding to a SARIF result object."""
    severity = (finding.get("severity") or "info").lower()
    title = finding.get("title") or finding.get("finding_id") or "Unnamed finding"
    description = finding.get("description") or ""
    poc = finding.get("poc") or ""
    proof = finding.get("proof_of_existence") or ""

    # Build message with PoC and proof if available
    message_text = description
    if poc:
        message_text += f"\n\nPoC: {poc[:300]}"
    if proof:
        message_text += f"\n\nProof: {proof[:300]}"

    result = {
        "ruleId": rule_id,
        "level": _SEVERITY_TO_LEVEL.get(severity, "note"),
        "message": {
            "text": message_text[:2000],  # SARIF message cap
        },
        "logicalLocations": [_get_logical_location(finding)],
        "properties": {
            "strix": {  # Use "strix" namespace for custom properties (SARIF convention)
                "severity": severity,
                "cvss": finding.get("cvss"),
                "cvss_vector": finding.get("cvss_vector"),
                "cve": _extract_cve(finding),
                "cwe": _extract_cwe(finding),
                "status": finding.get("status") or "Confirmed",
                "host": finding.get("host") or finding.get("target"),
                "port": finding.get("port"),
                "service": finding.get("service"),
                "finding_id": finding.get("finding_id"),
                "discovered_by": finding.get("discovered_by") or finding.get("bot_name"),
            }
        },
    }

    # Add security-severity for GitHub code-scanning ranking
    result["properties"]["strix"]["security-severity"] = _get_security_severity(finding)

    # Add fixes if remediation is provided
    fixes = _get_fixes(finding)
    if fixes:
        result["fixes"] = fixes

    return result


def findings_to_sarif(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert a list of Chimeras findings to a complete SARIF 2.1.0 document.

    Args:
        findings: List of finding dicts (from FindingsStore.get_all() or merge_all())

    Returns:
        SARIF 2.1.0 compliant dict
    """
    # Build rules from unique CWE/CVE/finding_id
    rules = {}
    results = []

    for finding in findings:
        # Determine rule ID: CWE > CVE > finding_id > title slug
        rule_id = _extract_cwe(finding) or _extract_cve(finding)
        if not rule_id:
            fid = finding.get("finding_id") or finding.get("title") or "unknown"
            rule_id = f"CHIMERAS-{str(fid).replace(' ', '-').lower()[:50]}"

        # Register rule if not seen
        if rule_id not in rules:
            severity = (finding.get("severity") or "info").lower()
            rules[rule_id] = {
                "id": rule_id,
                "name": (finding.get("title") or rule_id)[:100],
                "shortDescription": {
                    "text": (finding.get("title") or rule_id)[:200],
                },
                "fullDescription": {
                    "text": (finding.get("description") or "")[:1000],
                },
                "properties": {
                    "tags": ["security"],
                    "precision": "high" if finding.get("status") == "Exploited" else "medium",
                    "security-severity": _get_security_severity(finding),
                },
            }

        results.append(finding_to_sarif_result(finding, rule_id))

    # Sort results by severity (critical first)
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    results.sort(key=lambda r: severity_order.get(
        r.get("properties", {}).get("strix", {}).get("severity", "info"), 4
    ))

    sarif_doc = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "Chimeras",
                    "version": "3.0.0",
                    "informationUri": "https://github.com/Cybathreat/Chimeras",
                    "rules": list(rules.values()),
                }
            },
            "results": results,
            "invocations": [{
                "executionSuccessful": True,
                "endTimeUtc": datetime.now(timezone.utc).isoformat(),
            }],
        }]
    }

    return sarif_doc


def write_sarif(findings: List[Dict[str, Any]], output_path: Path) -> bool:
    """Write SARIF document to file.

    Args:
        findings: List of finding dicts
        output_path: Path to write findings.sarif

    Returns:
        True on success, False on failure
    """
    try:
        sarif_doc = findings_to_sarif(findings)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(sarif_doc, f, indent=2, ensure_ascii=False)
        logger.info(f"SARIF written: {output_path} ({len(findings)} findings)")
        return True
    except Exception as e:
        logger.error(f"SARIF write failed: {e}")
        return False