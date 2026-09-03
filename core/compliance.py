"""
Chimeras v3.1 — Compliance Mapper

Maps each pentest finding to relevant security compliance controls:
- OWASP ASVS 4.0 (Application Security Verification Standard)
- PCI DSS 4.0 (Payment Card Industry Data Security Standard)
- ISO 27001:2022 Annex A
- NIST 800-53 Rev 5

When a client asks "which control does this violate?" we answer.
Strix answers nothing. This alone wins enterprise deals.

Mapping uses keyword/CWE-based lookup against a static control database.
Not perfect — but enough for a consultant to cite in a report and
validate during review.

Integration:
    Bookkeeper calls map_findings() at report time.
    Output: compliance_mapping added to each finding dict.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── Compliance Control Database ──────────────────────────────────────
# Static mapping of vulnerability keywords → control IDs.
# Each entry: (keywords, framework, control_id, control_name, description)

_OWASP_ASVS = {
    "sql_injection": ("ASVS V5.3.4", "Database queries are parameterized"),
    "xss": ("ASVS V5.3.3", "Output encoding and auto-escaping"),
    "csrf": ("ASVS V4.2.6", "Anti-CSRF tokens for state-changing requests"),
    "ssrf": ("ASVS V12.4.1", "Server-side URL fetch validation"),
    "ssti": ("ASVS V5.2.4", "Template injection prevention"),
    "lfi": ("ASVS V12.3.1", "Path traversal protection"),
    "rfi": ("ASVS V12.3.1", "Remote file inclusion prevention"),
    "idor": ("ASVS V4.1.3", "Object-level authorization"),
    "auth_bypass": ("ASVS V2.1.1", "Authentication mechanism security"),
    "weak_password": ("ASVS V2.1.2", "Password strength requirements"),
    "mfa": ("ASVS V2.2.1", "Multi-factor authentication"),
    "session_fixation": ("ASVS V3.2.1", "Session token rotation"),
    "open_redirect": ("ASVS V4.2.7", "Unvalidated redirects"),
    "xxe": ("ASVS V12.3.2", "XML external entity prevention"),
    "deserialization": ("ASVS V5.3.5", "Unsafe deserialization prevention"),
    "ssl_tls": ("ASVS V8.3.1", "TLS configuration and cipher suites"),
    "info_disclosure": ("ASVS V7.1.1", "Information leakage prevention"),
    "missing_encryption": ("ASVS V8.3.1", "Transport layer encryption"),
    "insecure_headers": ("ASVS V8.3.3", "HTTP security headers"),
    "cors": ("ASVS V14.5.3", "Cross-Origin Resource Sharing policy"),
    "rate_limit": ("ASVS V11.1.1", "Rate limiting and anti-automation"),
    "jwt": ("ASVS V3.4.1", "Token-based authentication security"),
    "api_auth": ("ASVS V4.1.3", "API authorization controls"),
    "mass_assignment": ("ASVS V5.3.7", "Mass assignment protection"),
    "command_injection": ("ASVS V5.3.6", "OS command injection prevention"),
    "path_traversal": ("ASVS V12.3.1", "Path traversal protection"),
    "privilege_escalation": ("ASVS V4.2.1", "Privilege separation"),
    "buffer_overflow": ("ASVS V5.3.8", "Memory safety controls"),
    "default_credentials": ("ASVS V2.1.7", "Default credential removal"),
    "debug_enabled": ("ASVS V7.1.1", "Debug information disclosure"),
}

_PCI_DSS = {
    "sql_injection": ("PCI DSS 6.2.4", "Secure coding — injection prevention"),
    "xss": ("PCI DSS 6.2.4", "Secure coding — injection prevention"),
    "csrf": ("PCI DSS 6.2.4", "Secure coding — input validation"),
    "ssrf": ("PCI DSS 6.2.4", "Secure coding — server-side validation"),
    "ssl_tls": ("PCI DSS 4.2.1", "Strong cryptography in transit"),
    "missing_encryption": ("PCI DSS 4.2.1", "Strong cryptography in transit"),
    "weak_password": ("PCI DSS 8.3.2", "Strong authentication"),
    "auth_bypass": ("PCI DSS 8.2.1", "Authentication controls"),
    "default_credentials": ("PCI DSS 8.2.2", "Remove default credentials"),
    "info_disclosure": ("PCI DSS 3.5.1", "Cardholder data protection"),
    "privilege_escalation": ("PCI DSS 7.2.1", "Least privilege access"),
    "idor": ("PCI DSS 7.2.2", "Access control enforcement"),
    "rate_limit": ("PCI DSS 6.2.4", "Input validation and rate limiting"),
    "session_fixation": ("PCI DSS 8.2.3", "Session management security"),
    "insecure_headers": ("PCI DSS 4.2.1", "Strong cryptography in transit"),
    "debug_enabled": ("PCI DSS 6.2.4", "Secure coding practices"),
    "command_injection": ("PCI DSS 6.2.4", "Secure coding — injection prevention"),
    "open_redirect": ("PCI DSS 6.2.4", "Secure coding — input validation"),
}

_ISO_27001 = {
    "sql_injection": ("ISO 27001 A.8.25", "Secure development — injection prevention"),
    "xss": ("ISO 27001 A.8.25", "Secure development — injection prevention"),
    "csrf": ("ISO 27001 A.8.25", "Secure development — input validation"),
    "ssl_tls": ("ISO 27001 A.8.24", "Cryptography — transport encryption"),
    "missing_encryption": ("ISO 27001 A.8.24", "Cryptography — transport encryption"),
    "weak_password": ("ISO 27001 A.5.17", "Authentication — password policy"),
    "auth_bypass": ("ISO 27001 A.5.16", "Identity and access management"),
    "default_credentials": ("ISO 27001 A.5.16", "Identity and access management"),
    "info_disclosure": ("ISO 27001 A.5.12", "Information classification and handling"),
    "privilege_escalation": ("ISO 27001 A.8.2", "Privileged access rights"),
    "idor": ("ISO 27001 A.8.2", "Access control — object-level"),
    "rate_limit": ("ISO 27001 A.8.6", "Capacity management — rate limiting"),
    "session_fixation": ("ISO 27001 A.5.17", "Authentication — session management"),
    "insecure_headers": ("ISO 27001 A.8.24", "Cryptography — security headers"),
    "debug_enabled": ("ISO 27001 A.5.12", "Information classification — debug info"),
    "command_injection": ("ISO 27001 A.8.25", "Secure development — injection prevention"),
    "ssrf": ("ISO 27001 A.8.25", "Secure development — server-side validation"),
    "ssti": ("ISO 27001 A.8.25", "Secure development — template injection"),
    "lfi": ("ISO 27001 A.8.25", "Secure development — path traversal"),
    "rfi": ("ISO 27001 A.8.25", "Secure development — file inclusion"),
    "open_redirect": ("ISO 27001 A.8.25", "Secure development — redirect validation"),
    "xxe": ("ISO 27001 A.8.25", "Secure development — XML processing"),
    "deserialization": ("ISO 27001 A.8.25", "Secure development — deserialization"),
    "cors": ("ISO 27001 A.8.25", "Secure development — CORS policy"),
    "jwt": ("ISO 27001 A.5.17", "Authentication — token security"),
    "mass_assignment": ("ISO 27001 A.8.25", "Secure development — input binding"),
    "buffer_overflow": ("ISO 27001 A.8.25", "Secure development — memory safety"),
    "path_traversal": ("ISO 27001 A.8.25", "Secure development — path traversal"),
    "mfa": ("ISO 27001 A.5.17", "Authentication — multi-factor"),
}

_NIST_800_53 = {
    "sql_injection": ("NIST 800-53 SI-10", "Information input validation"),
    "xss": ("NIST 800-53 SI-10", "Information input validation"),
    "csrf": ("NIST 800-53 SI-10", "Information input validation"),
    "ssrf": ("NIST 800-53 SI-10", "Information input validation"),
    "ssl_tls": ("NIST 800-53 SC-8", "Transmission confidentiality and integrity"),
    "missing_encryption": ("NIST 800-53 SC-8", "Transmission confidentiality and integrity"),
    "weak_password": ("NIST 800-53 IA-5", "Authenticator management"),
    "auth_bypass": ("NIST 800-53 IA-2", "Identification and authentication"),
    "default_credentials": ("NIST 800-53 IA-5", "Authenticator management"),
    "info_disclosure": ("NIST 800-53 SC-13", "Cryptographic protection"),
    "privilege_escalation": ("NIST 800-53 AC-6", "Least privilege"),
    "idor": ("NIST 800-53 AC-3", "Access enforcement"),
    "rate_limit": ("NIST 800-53 SC-5", "Denial of service protection"),
    "session_fixation": ("NIST 800-53 IA-5", "Authenticator management"),
    "insecure_headers": ("NIST 800-53 SC-8", "Transmission confidentiality and integrity"),
    "debug_enabled": ("NIST 800-53 AC-21", "Information sharing — debug controls"),
    "command_injection": ("NIST 800-53 SI-10", "Information input validation"),
    "open_redirect": ("NIST 800-53 SI-10", "Information input validation"),
    "ssti": ("NIST 800-53 SI-10", "Information input validation"),
    "lfi": ("NIST 800-53 SI-10", "Information input validation"),
    "rfi": ("NIST 800-53 SI-10", "Information input validation"),
    "xxe": ("NIST 800-53 SI-10", "Information input validation"),
    "deserialization": ("NIST 800-53 SI-10", "Information input validation"),
    "cors": ("NIST 800-53 AC-3", "Access enforcement"),
    "jwt": ("NIST 800-53 IA-5", "Authenticator management"),
    "mass_assignment": ("NIST 800-53 SI-10", "Information input validation"),
    "buffer_overflow": ("NIST 800-53 SI-10", "Information input validation"),
    "path_traversal": ("NIST 800-53 SI-10", "Information input validation"),
    "mfa": ("NIST 800-53 IA-2", "Identification and authentication"),
}

# ─── v3.2: MENA/Enterprise compliance expansion ──────────────────────

_SOC2 = {
    "sql_injection": ("SOC 2 CC7.1", "System monitoring — vulnerability detection"),
    "xss": ("SOC 2 CC7.1", "System monitoring — vulnerability detection"),
    "ssl_tls": ("SOC 2 CC6.7", "Transmission and disposal — encryption in transit"),
    "missing_encryption": ("SOC 2 CC6.7", "Transmission and disposal — encryption in transit"),
    "weak_password": ("SOC 2 CC6.1", "Logical access — password policy"),
    "auth_bypass": ("SOC 2 CC6.1", "Logical access — authentication controls"),
    "default_credentials": ("SOC 2 CC6.1", "Logical access — credential management"),
    "info_disclosure": ("SOC 2 CC6.5", "Data disposal — information protection"),
    "privilege_escalation": ("SOC 2 CC6.3", "Access restrictions — least privilege"),
    "idor": ("SOC 2 CC6.3", "Access restrictions — object-level authorization"),
    "rate_limit": ("SOC 2 CC7.1", "System monitoring — rate limiting"),
    "session_fixation": ("SOC 2 CC6.1", "Logical access — session management"),
    "insecure_headers": ("SOC 2 CC6.7", "Transmission — security headers"),
    "debug_enabled": ("SOC 2 CC7.1", "System monitoring — debug controls"),
    "command_injection": ("SOC 2 CC7.1", "System monitoring — input validation"),
    "ssrf": ("SOC 2 CC7.1", "System monitoring — server-side validation"),
    "csrf": ("SOC 2 CC6.1", "Logical access — request authenticity"),
    "ssti": ("SOC 2 CC7.1", "System monitoring — template injection"),
    "lfi": ("SOC 2 CC7.1", "System monitoring — path traversal"),
    "rfi": ("SOC 2 CC7.1", "System monitoring — file inclusion"),
    "open_redirect": ("SOC 2 CC7.1", "System monitoring — redirect validation"),
    "xxe": ("SOC 2 CC7.1", "System monitoring — XML processing"),
    "deserialization": ("SOC 2 CC7.1", "System monitoring — deserialization"),
    "cors": ("SOC 2 CC6.3", "Access restrictions — CORS policy"),
    "jwt": ("SOC 2 CC6.1", "Logical access — token security"),
    "mass_assignment": ("SOC 2 CC7.1", "System monitoring — input binding"),
    "buffer_overflow": ("SOC 2 CC7.1", "System monitoring — memory safety"),
    "path_traversal": ("SOC 2 CC7.1", "System monitoring — path traversal"),
    "mfa": ("SOC 2 CC6.1", "Logical access — multi-factor authentication"),
}

_NIS2 = {
    "sql_injection": ("NIS2 Article 21(1)", "Risk management — vulnerability remediation"),
    "xss": ("NIS2 Article 21(1)", "Risk management — vulnerability remediation"),
    "ssl_tls": ("NIS2 Article 21(2)(d)", "Cryptography — transport encryption"),
    "missing_encryption": ("NIS2 Article 21(2)(d)", "Cryptography — transport encryption"),
    "weak_password": ("NIS2 Article 21(2)(b)", "Access control — authentication"),
    "auth_bypass": ("NIS2 Article 21(2)(b)", "Access control — authentication"),
    "default_credentials": ("NIS2 Article 21(2)(b)", "Access control — default credentials"),
    "info_disclosure": ("NIS2 Article 21(2)(e)", "Data protection — information handling"),
    "privilege_escalation": ("NIS2 Article 21(2)(b)", "Access control — least privilege"),
    "idor": ("NIS2 Article 21(2)(b)", "Access control — object-level auth"),
    "rate_limit": ("NIS2 Article 21(2)(f)", "Availability — DoS protection"),
    "session_fixation": ("NIS2 Article 21(2)(b)", "Access control — session management"),
    "insecure_headers": ("NIS2 Article 21(2)(d)", "Cryptography — security headers"),
    "debug_enabled": ("NIS2 Article 21(2)(e)", "Data protection — debug information"),
    "command_injection": ("NIS2 Article 21(1)", "Risk management — input validation"),
    "ssrf": ("NIS2 Article 21(1)", "Risk management — server-side validation"),
    "mfa": ("NIS2 Article 21(2)(b)", "Access control — multi-factor authentication"),
}

_NCA_ECC = {
    "sql_injection": ("NCA ECC 1.3.2", "Secure software development — injection prevention"),
    "xss": ("NCA ECC 1.3.2", "Secure software development — injection prevention"),
    "ssl_tls": ("NCA ECC 1.4.1", "Encryption — TLS configuration"),
    "missing_encryption": ("NCA ECC 1.4.1", "Encryption — transport security"),
    "weak_password": ("NCA ECC 1.2.1", "Authentication — password policy"),
    "auth_bypass": ("NCA ECC 1.2.1", "Authentication — access control"),
    "default_credentials": ("NCA ECC 1.2.1", "Authentication — default credentials"),
    "info_disclosure": ("NCA ECC 1.5.1", "Data protection — information classification"),
    "privilege_escalation": ("NCA ECC 1.2.3", "Access control — privilege management"),
    "idor": ("NCA ECC 1.2.3", "Access control — object-level auth"),
    "rate_limit": ("NCA ECC 1.3.4", "Application security — rate limiting"),
    "session_fixation": ("NCA ECC 1.2.2", "Authentication — session management"),
    "insecure_headers": ("NCA ECC 1.4.1", "Encryption — security headers"),
    "debug_enabled": ("NCA ECC 1.5.1", "Data protection — debug exposure"),
    "command_injection": ("NCA ECC 1.3.2", "Secure software development — injection prevention"),
    "ssrf": ("NCA ECC 1.3.2", "Secure software development — server-side validation"),
    "mfa": ("NCA ECC 1.2.1", "Authentication — multi-factor authentication"),
}


# ─── Vulnerability detection patterns ─────────────────────────────────

_VULN_PATTERNS: List[Tuple[str, List[str]]] = [
    ("sql_injection", [r"sql\s*injection", r"sqlmap", r"union\s+select", r"blind\s+injection", r"or\s+1=1", r"parameterized\s+quer"]),
    ("xss", [r"\bxss\b", r"cross.?site\s+script", r"reflected\s+xss", r"stored\s+xss", r"dom\s+xss", r"<script>", r"dalfox"]),
    ("csrf", [r"\bcsrf\b", r"cross.?site\s+request", r"anti.?csrf", r"xsrf", r"csrf\s+token"]),
    ("ssrf", [r"\bssrf\b", r"server.?side\s+request", r"server.?side\s+forge"]),
    ("ssti", [r"\bssti\b", r"server.?side\s+template", r"template\s+inject"]),
    ("lfi", [r"\blfi\b", r"local\s+file\s+inclusion", r"path\s+traversal", r"directory\s+traversal", r"\.\./", r"\.\.%2f"]),
    ("rfi", [r"\brfi\b", r"remote\s+file\s+inclusion"]),
    ("idor", [r"\bidor\b", r"insecure\s+direct\s+object", r"object\s+level\s+auth", r"broken\s+object"]),
    ("auth_bypass", [r"auth\s+bypass", r"authentication\s+bypass", r"login\s+bypass", r"password\s+bypass"]),
    ("weak_password", [r"weak\s+password", r"default\s+password", r"password\s+policy", r"password\s+complex"]),
    ("mfa", [r"\bmfa\b", r"multi.?factor", r"two.?factor", r"2fa", r"otp\s+bypass"]),
    ("session_fixation", [r"session\s+fixation", r"session\s+token\s+not\s+rotat", r"session\s+id\s+predictable"]),
    ("open_redirect", [r"open\s+redirect", r"unvalidated\s+redirect", r"url\s+redirect"]),
    ("xxe", [r"\bxxe\b", r"xml\s+external\s+entity", r"xml\s+injection"]),
    ("deserialization", [r"deserializ", r"unsafe\s+deserial", r"object\s+injection"]),
    ("ssl_tls", [r"\bssl\b", r"\btls\b", r"cipher\s+suit", r"weak\s+cipher", r"tls\s+1\.0", r"tls\s+1\.1", r"deprecat.*\btls", r"heartbleed", r"poodle", r"\bsslv3\b", r"sslscan", r"ssl.?audit"]),
    ("info_disclosure", [r"information\s+disclos", r"info\s+leak", r"sensitive\s+info", r"verbose\s+error", r"stack\s+trace", r"debug\s+mode", r"banner\s+disclos"]),
    ("missing_encryption", [r"missing\s+encryption", r"no\s+encryption", r"unencrypted", r"cleartext\s+trans", r"http\s+only\s+no\s+https"]),
    ("insecure_headers", [r"security\s+header", r"missing\s+header", r"x-frame", r"x-content", r"strict-transport", r"hsts", r"csp\s+header", r"x-xss"]),
    ("cors", [r"\bcors\b", r"cross.?origin", r"access-control-allow-origin\s*\*"]),
    ("rate_limit", [r"rate\s+limit", r"brute.?force", r"no\s+rate\s+limit", r"account\s+lockout"]),
    ("jwt", [r"\bjwt\b", r"json\s+web\s+token", r"jwt\s+secret", r"alg.?none", r"jwt\s+bypass"]),
    ("api_auth", [r"api\s+key\s+leak", r"api\s+auth", r"api\s+token"]),
    ("mass_assignment", [r"mass\s+assignment", r"auto.?binding", r"over.?posting"]),
    ("command_injection", [r"command\s+inject", r"os\s+command", r"code\s+inject", r"shell\s+inject", r"commix"]),
    ("path_traversal", [r"path\s+traversal", r"directory\s+traversal", r"\.\./", r"\.\.%2f"]),
    ("privilege_escalation", [r"privilege\s+esc", r"privesc", r"linpeas", r"root\s+escal", r"sudo\s+abuse", r"misconfigured\s+sudo"]),
    ("buffer_overflow", [r"buffer\s+overflow", r"stack\s+overflow", r"heap\s+overflow", r"\bbof\b"]),
    ("default_credentials", [r"default\s+credential", r"default\s+password", r"factory\s+password", r"admin\s+admin", r"root\s+root"]),
    ("debug_enabled", [r"debug\s+enabled", r"debug\s+mode", r"debug\s+endpoint", r"trace\s+enabled"]),
]


def _detect_vuln_types(text: str) -> List[str]:
    """Detect vulnerability types from text using keyword patterns.

    Scans title, description, risks, poc, and proof_of_existence fields.
    Returns list of matched vulnerability type keys.
    """
    if not text:
        return []

    text_lower = text.lower()
    matched: List[str] = []

    for vuln_type, patterns in _VULN_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text_lower):
                if vuln_type not in matched:
                    matched.append(vuln_type)
                break  # one match per vuln type is enough

    return matched


def _map_to_framework(vuln_types: List[str], framework_db: Dict) -> List[Dict[str, str]]:
    """Map vulnerability types to a specific compliance framework."""
    mappings: List[Dict[str, str]] = []
    seen_controls: set = set()

    for vt in vuln_types:
        entry = framework_db.get(vt)
        if entry and entry[0] not in seen_controls:
            mappings.append({
                "control_id": entry[0],
                "control_name": entry[1],
                "vuln_type": vt,
            })
            seen_controls.add(entry[0])

    return mappings


class ComplianceMapper:
    """Maps pentest findings to compliance framework controls.

    Uses keyword-based detection to identify vulnerability types from
    finding text, then maps each type to relevant controls in:
    - OWASP ASVS 4.0
    - PCI DSS 4.0
    - ISO 27001:2022 Annex A
    - NIST 800-53 Rev 5
    """

    def __init__(self):
        self.frameworks = {
            "OWASP ASVS 4.0": _OWASP_ASVS,
            "PCI DSS 4.0": _PCI_DSS,
            "ISO 27001:2022": _ISO_27001,
            "NIST 800-53 Rev 5": _NIST_800_53,
            "SOC 2": _SOC2,
            "NIS2": _NIS2,
            "NCA ECC (Saudi)": _NCA_ECC,
        }

    def map_finding(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        """Map a single finding to compliance controls.

        Args:
            finding: Finding dict with title, description, poc, etc.

        Returns:
            Dict with vuln_types and per-framework control mappings.
        """
        # Combine all text fields for detection
        text_parts = [
            finding.get("title", ""),
            finding.get("description", ""),
            finding.get("risks", ""),
            finding.get("attack_vectors", ""),
            finding.get("poc", ""),
            finding.get("proof_of_existence", ""),
            finding.get("remediation", ""),
        ]
        combined_text = " ".join(str(p) for p in text_parts if p)

        vuln_types = _detect_vuln_types(combined_text)

        mappings: Dict[str, List[Dict[str, str]]] = {}
        for fw_name, fw_db in self.frameworks.items():
            fw_mappings = _map_to_framework(vuln_types, fw_db)
            if fw_mappings:
                mappings[fw_name] = fw_mappings

        return {
            "vuln_types": vuln_types,
            "compliance": mappings,
        }

    def map_findings(
        self, findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Map all findings to compliance controls.

        Enriches each finding dict with a 'compliance' field containing
        the vuln types and per-framework control mappings.

        Returns a new list of finding dicts with compliance added.
        """
        enriched: List[Dict[str, Any]] = []

        for f in findings:
            f_copy = dict(f)
            mapping = self.map_finding(f_copy)
            f_copy["compliance"] = mapping
            enriched.append(f_copy)

        return enriched

    def summary(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a compliance summary across all findings.

        Returns counts of findings per framework and per control.
        """
        framework_counts: Dict[str, int] = {}
        control_findings: Dict[str, List[str]] = {}  # control_id → finding IDs
        total_mapped = 0

        for f in findings:
            compliance = f.get("compliance", {})
            has_mapping = False

            for fw_name, controls in compliance.get("compliance", {}).items():
                for ctrl in controls:
                    has_mapping = True
                    fw_name_key = fw_name
                    framework_counts[fw_name_key] = framework_counts.get(fw_name_key, 0) + 1

                    ctrl_id = ctrl["control_id"]
                    fid = f.get("id") or f.get("finding_id", "UNKNOWN")
                    control_findings.setdefault(ctrl_id, []).append(fid)

            if has_mapping:
                total_mapped += 1

        return {
            "total_findings": len(findings),
            "mapped_findings": total_mapped,
            "framework_counts": framework_counts,
            "control_findings": control_findings,
            "frameworks_covered": list(self.frameworks.keys()),
        }

    def format_for_report(
        self, findings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Format compliance mappings for inclusion in the report.

        Returns a dict with:
        - per_finding: finding_id → list of control IDs
        - summary: framework counts
        - formatted_text: markdown-ready text for the report
        """
        enriched = self.map_findings(findings)
        summary = self.summary(enriched)

        per_finding: Dict[str, List[str]] = {}
        for f in enriched:
            fid = f.get("id") or f.get("finding_id", "UNKNOWN")
            compliance = f.get("compliance", {})
            controls: List[str] = []
            for fw_name, fw_controls in compliance.get("compliance", {}).items():
                for ctrl in fw_controls:
                    controls.append(f"{fw_name}: {ctrl['control_id']} — {ctrl['control_name']}")
            if controls:
                per_finding[fid] = controls

        # Build formatted text
        lines: List[str] = []
        lines.append("## Compliance Mapping Summary\n")
        lines.append(f"- Total findings: {summary['total_findings']}")
        lines.append(f"- Findings with compliance mappings: {summary['mapped_findings']}")
        lines.append(f"- Frameworks covered: {', '.join(summary['frameworks_covered'])}\n")

        if summary["framework_counts"]:
            lines.append("### Findings per Framework\n")
            for fw, count in sorted(summary["framework_counts"].items()):
                lines.append(f"- **{fw}**: {count} control(s) referenced")

        if per_finding:
            lines.append("\n### Per-Finding Control References\n")
            for fid, controls in sorted(per_finding.items()):
                lines.append(f"**{fid}:**")
                for c in controls:
                    lines.append(f"  - {c}")
                lines.append("")

        return {
            "per_finding": per_finding,
            "summary": summary,
            "formatted_text": "\n".join(lines),
        }