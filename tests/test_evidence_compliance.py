"""
Tests for v3.1 EvidenceLocker and ComplianceMapper.

EvidenceLocker tests:
- collect_all produces manifest with correct artifact count
- SHA-256 hashes are 64 hex chars
- manifest verification (tamper detection)
- finding-to-evidence linking
- empty directories handled gracefully
- get_findings_with_hashes enriches findings
- summary returns correct counts

ComplianceMapper tests:
- SQL injection maps to correct controls across all 4 frameworks
- XSS maps to correct controls
- SSL/TLS findings map to correct controls
- non-vuln findings (open port) produce no mappings
- map_findings enriches all findings
- summary produces correct counts
- format_for_report produces formatted text
- multiple vuln types in one finding
"""

import json
import pytest
from pathlib import Path

from core.evidence import EvidenceLocker
from core.compliance import ComplianceMapper, _detect_vuln_types


# ─── EvidenceLocker fixtures ──────────────────────────────────────────

@pytest.fixture
def engagement_dir(tmp_path):
    """Create a temporary engagement directory with raw/ and poc/ files."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "nmap_scan.txt").write_text(
        "22/tcp open ssh\n80/tcp open http\n443/tcp open https"
    )
    (raw_dir / "sslscan.txt").write_text(
        "TLS 1.0 enabled\nCipher: TLS_RSA_WITH_AES_128_CBC_SHA"
    )

    poc_dir = tmp_path / "poc"
    poc_dir.mkdir()
    (poc_dir / "sqli_payload.txt").write_text("admin' OR 1=1--")

    return tmp_path


@pytest.fixture
def sample_findings():
    return [
        {
            "id": "BH-001",
            "title": "SSL/TLS Weak Cipher Suites",
            "severity": "high",
            "cvss": "7.5",
            "proof_of_existence": "TLS 1.0 enabled\nCipher: TLS_RSA_WITH_AES_128_CBC_SHA",
        },
        {
            "id": "WASP-001",
            "title": "SQL Injection in Login Form",
            "severity": "critical",
            "cvss": "9.8",
            "proof_of_existence": "sqlmap confirmed: boolean-based blind, UNION query",
        },
    ]


# ─── EvidenceLocker tests ─────────────────────────────────────────────

class TestEvidenceLocker:
    def test_collect_all_creates_manifest(self, engagement_dir, sample_findings):
        """collect_all should create evidence_manifest.json."""
        locker = EvidenceLocker(engagement_dir)
        manifest = locker.collect_all(sample_findings)

        assert manifest is not None
        assert "evidence" in manifest
        assert manifest["total_artifacts"] > 0
        assert (engagement_dir / "evidence" / "evidence_manifest.json").exists()

    def test_collects_raw_outputs(self, engagement_dir, sample_findings):
        """Should collect files from raw/ directory."""
        locker = EvidenceLocker(engagement_dir)
        manifest = locker.collect_all(sample_findings)

        raw_entries = [e for e in manifest["evidence"] if e["source"] == "raw_output"]
        assert len(raw_entries) == 2  # nmap_scan.txt + sslscan.txt

    def test_collects_poc_files(self, engagement_dir, sample_findings):
        """Should collect files from poc/ directory."""
        locker = EvidenceLocker(engagement_dir)
        manifest = locker.collect_all(sample_findings)

        poc_entries = [e for e in manifest["evidence"] if e["source"] == "poc"]
        assert len(poc_entries) == 1  # sqli_payload.txt

    def test_collects_finding_proofs(self, engagement_dir, sample_findings):
        """Should create hashed proof files for each finding with proof_of_existence."""
        locker = EvidenceLocker(engagement_dir)
        manifest = locker.collect_all(sample_findings)

        proof_entries = [e for e in manifest["evidence"] if e["source"] == "finding_proof"]
        assert len(proof_entries) == 2  # both findings have proof_of_existence

    def test_hashes_are_sha256(self, engagement_dir, sample_findings):
        """All hashes should be 64-character hex strings (SHA-256)."""
        locker = EvidenceLocker(engagement_dir)
        manifest = locker.collect_all(sample_findings)

        for entry in manifest["evidence"]:
            assert len(entry["sha256"]) == 64
            assert all(c in "0123456789abcdef" for c in entry["sha256"])

    def test_manifest_hash_exists(self, engagement_dir, sample_findings):
        """Manifest should have a hash field."""
        locker = EvidenceLocker(engagement_dir)
        manifest = locker.collect_all(sample_findings)

        assert manifest["manifest_hash"] is not None
        assert len(manifest["manifest_hash"]) == 64

    def test_manifest_verification_pass(self, engagement_dir, sample_findings):
        """verify_manifest should return True for untampered manifest."""
        locker = EvidenceLocker(engagement_dir)
        locker.collect_all(sample_findings)
        assert locker.verify_manifest() is True

    def test_manifest_verification_fail_after_tamper(self, engagement_dir, sample_findings):
        """verify_manifest should return False after manifest is tampered."""
        locker = EvidenceLocker(engagement_dir)
        locker.collect_all(sample_findings)

        # Tamper with the manifest
        manifest_path = engagement_dir / "evidence" / "evidence_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["total_artifacts"] = 999  # tamper
        manifest_path.write_text(json.dumps(manifest))

        assert locker.verify_manifest() is False

    def test_finding_evidence_linking(self, engagement_dir, sample_findings):
        """Raw outputs containing proof text should be linked to findings."""
        locker = EvidenceLocker(engagement_dir)
        manifest = locker.collect_all(sample_findings)

        # BH-001 proof is "TLS 1.0 enabled..." which is in sslscan.txt
        bh001_entries = [
            e for e in manifest["evidence"]
            if e.get("finding_id") == "BH-001"
        ]
        assert len(bh001_entries) >= 1

    def test_get_findings_with_hashes(self, engagement_dir, sample_findings):
        """get_findings_with_hashes should add evidence_hash to findings."""
        locker = EvidenceLocker(engagement_dir)
        locker.collect_all(sample_findings)

        enriched = locker.get_findings_with_hashes(sample_findings)
        for f in enriched:
            assert "evidence_hash" in f
            assert "evidence_hashes" in f
            # Both findings have proof_of_existence, so should have hashes
            assert f["evidence_hash"] is not None

    def test_empty_engagement_dir(self, tmp_path):
        """Should handle engagement dir with no raw/ or poc/ directories."""
        locker = EvidenceLocker(tmp_path)
        manifest = locker.collect_all([])

        assert manifest["total_artifacts"] == 0
        assert manifest["evidence"] == []

    def test_empty_raw_dir(self, tmp_path):
        """Should handle empty raw/ directory."""
        (tmp_path / "raw").mkdir()
        locker = EvidenceLocker(tmp_path)
        manifest = locker.collect_all([])

        assert manifest["total_artifacts"] == 0

    def test_summary(self, engagement_dir, sample_findings):
        """summary should return correct counts."""
        locker = EvidenceLocker(engagement_dir)
        locker.collect_all(sample_findings)

        s = locker.summary()
        assert s["total"] > 0
        assert s["linked"] > 0
        assert s["verified"] is True
        assert "manifest_hash" in s

    def test_evidence_files_copied(self, engagement_dir, sample_findings):
        """Evidence files should be copied to evidence/ directory."""
        locker = EvidenceLocker(engagement_dir)
        locker.collect_all(sample_findings)

        evidence_files = list((engagement_dir / "evidence").glob("*"))
        # At least: manifest + raw files + poc file + proof files
        assert len(evidence_files) >= 4

    def test_finding_without_proof_skipped(self, tmp_path):
        """Findings without proof_of_existence should not create evidence entries."""
        (tmp_path / "raw").mkdir()
        locker = EvidenceLocker(tmp_path)
        findings = [
            {"id": "TEST-001", "title": "Test", "proof_of_existence": ""},
        ]
        manifest = locker.collect_all(findings)

        proof_entries = [e for e in manifest["evidence"] if e["source"] == "finding_proof"]
        assert len(proof_entries) == 0


# ─── ComplianceMapper tests ───────────────────────────────────────────

class TestComplianceMapper:
    @pytest.fixture
    def mapper(self):
        return ComplianceMapper()

    def test_sql_injection_mapping(self, mapper):
        """SQL injection should map to all 4 frameworks."""
        finding = {
            "id": "WASP-001",
            "title": "SQL Injection in Login Form",
            "description": "The login endpoint is vulnerable to SQL injection.",
            "risks": "Full database compromise.",
            "attack_vectors": "Enter admin' OR 1=1--",
            "poc": "sqlmap -u http://target/login",
            "proof_of_existence": "sqlmap confirmed: boolean-based blind",
            "remediation": "Use parameterized queries.",
        }

        result = mapper.map_finding(finding)
        assert "sql_injection" in result["vuln_types"]

        compliance = result["compliance"]
        assert "OWASP ASVS 4.0" in compliance
        assert "PCI DSS 4.0" in compliance
        assert "ISO 27001:2022" in compliance
        assert "NIST 800-53 Rev 5" in compliance

        # Check specific control IDs
        owasp_controls = [c["control_id"] for c in compliance["OWASP ASVS 4.0"]]
        assert "ASVS V5.3.4" in owasp_controls

    def test_xss_mapping(self, mapper):
        """XSS should map to injection prevention controls."""
        finding = {
            "id": "WASP-002",
            "title": "Reflected XSS in Search Parameter",
            "description": "Cross-site scripting vulnerability in search.",
            "risks": "Session theft, credential theft.",
            "attack_vectors": "Inject <script> in search param",
            "poc": "dalfox url http://target/search?q=test",
            "proof_of_existence": "Reflected XSS confirmed",
            "remediation": "Output encoding and CSP.",
        }

        result = mapper.map_finding(finding)
        assert "xss" in result["vuln_types"]
        assert "OWASP ASVS 4.0" in result["compliance"]

    def test_ssl_tls_mapping(self, mapper):
        """SSL/TLS findings should map to cryptography controls."""
        finding = {
            "id": "BH-001",
            "title": "SSL/TLS Weak Cipher Suites",
            "description": "The target supports deprecated TLS 1.0 and weak cipher suites.",
            "risks": "Man-in-the-middle attacks.",
            "attack_vectors": "Scan with sslscan",
            "poc": "sslscan --no-failed 10.0.0.1",
            "proof_of_existence": "TLS 1.0 enabled",
            "remediation": "Disable TLS 1.0/1.1.",
        }

        result = mapper.map_finding(finding)
        assert "ssl_tls" in result["vuln_types"]

        compliance = result["compliance"]
        pci_controls = [c["control_id"] for c in compliance.get("PCI DSS 4.0", [])]
        assert "PCI DSS 4.2.1" in pci_controls

    def test_no_vuln_mapping(self, mapper):
        """Non-vulnerability findings should produce no mappings."""
        finding = {
            "id": "LISA-001",
            "title": "Open SSH Port",
            "description": "SSH service is running on port 22.",
            "risks": "Informational.",
            "attack_vectors": "N/A",
            "poc": "nmap -p 22",
            "proof_of_existence": "22/tcp open ssh",
            "remediation": "Ensure SSH is secured.",
        }

        result = mapper.map_finding(finding)
        assert result["vuln_types"] == []
        assert result["compliance"] == {}

    def test_map_findings_enriches_all(self, mapper):
        """map_findings should add compliance to every finding."""
        findings = [
            {
                "id": "WASP-001",
                "title": "SQL Injection",
                "description": "SQL injection found.",
                "poc": "sqlmap",
            },
            {
                "id": "LISA-001",
                "title": "Open Port",
                "description": "Port 22 is open.",
                "poc": "nmap",
            },
        ]

        enriched = mapper.map_findings(findings)
        assert len(enriched) == 2
        assert "compliance" in enriched[0]
        assert "compliance" in enriched[1]

    def test_summary_counts(self, mapper):
        """summary should produce correct counts."""
        findings = [
            {
                "id": "WASP-001",
                "title": "SQL Injection",
                "description": "SQL injection found.",
                "poc": "sqlmap",
            },
            {
                "id": "WASP-002",
                "title": "XSS",
                "description": "Cross-site scripting.",
                "poc": "dalfox",
            },
            {
                "id": "LISA-001",
                "title": "Open Port",
                "description": "Port 22 is open.",
                "poc": "nmap",
            },
        ]

        enriched = mapper.map_findings(findings)
        summary = mapper.summary(enriched)

        assert summary["total_findings"] == 3
        assert summary["mapped_findings"] == 2  # SQLi + XSS, not open port
        assert "OWASP ASVS 4.0" in summary["framework_counts"]

    def test_format_for_report(self, mapper):
        """format_for_report should produce formatted text."""
        findings = [
            {
                "id": "WASP-001",
                "title": "SQL Injection",
                "description": "SQL injection found.",
                "poc": "sqlmap",
            },
        ]

        result = mapper.format_for_report(findings)
        assert "formatted_text" in result
        assert "per_finding" in result
        assert "summary" in result
        assert "Compliance Mapping Summary" in result["formatted_text"]
        assert "WASP-001" in result["per_finding"]

    def test_multiple_vuln_types(self, mapper):
        """A finding with multiple vuln types should map to multiple controls."""
        finding = {
            "id": "WASP-001",
            "title": "SQL Injection and XSS in Search",
            "description": "The search endpoint has both SQL injection and cross-site scripting vulnerabilities.",
            "risks": "Database compromise and session theft.",
            "attack_vectors": "sqlmap and dalfox",
            "poc": "sqlmap -u http://target/search; dalfox url http://target/search",
            "proof_of_existence": "Both SQLi and XSS confirmed",
            "remediation": "Parameterized queries and output encoding.",
        }

        result = mapper.map_finding(finding)
        assert "sql_injection" in result["vuln_types"]
        assert "xss" in result["vuln_types"]

    def test_csrf_mapping(self, mapper):
        """CSRF should map to anti-CSRF controls."""
        finding = {
            "id": "WASP-003",
            "title": "Missing CSRF Token",
            "description": "The form lacks anti-CSRF tokens.",
            "risks": "State-changing actions on behalf of users.",
            "poc": "Submit form without CSRF token",
            "proof_of_existence": "No CSRF token in form",
            "remediation": "Add CSRF tokens.",
        }

        result = mapper.map_finding(finding)
        assert "csrf" in result["vuln_types"]

    def test_default_credentials_mapping(self, mapper):
        """Default credentials should map to authenticator management."""
        finding = {
            "id": "BH-002",
            "title": "Default Credentials on Admin Panel",
            "description": "The admin panel uses factory default credentials admin/admin.",
            "risks": "Full administrative access.",
            "poc": "Login with admin:admin",
            "proof_of_existence": "Login succeeded with admin/admin",
            "remediation": "Change default credentials.",
        }

        result = mapper.map_finding(finding)
        assert "default_credentials" in result["vuln_types"]
        compliance = result["compliance"]
        nist_controls = [c["control_id"] for c in compliance.get("NIST 800-53 Rev 5", [])]
        assert "NIST 800-53 IA-5" in nist_controls


# ─── Detection pattern tests ──────────────────────────────────────────

class TestVulnDetection:
    def test_detect_sql_injection(self):
        types = _detect_vuln_types("SQL injection in login form. sqlmap confirmed.")
        assert "sql_injection" in types

    def test_detect_xss(self):
        types = _detect_vuln_types("Reflected XSS vulnerability. dalfox scan confirmed.")
        assert "xss" in types

    def test_detect_ssl_tls(self):
        types = _detect_vuln_types("TLS 1.0 enabled with weak cipher suites. sslscan output.")
        assert "ssl_tls" in types

    def test_detect_no_match(self):
        types = _detect_vuln_types("The server is running normally with no issues.")
        assert types == []

    def test_detect_empty_text(self):
        types = _detect_vuln_types("")
        assert types == []

    def test_detect_case_insensitive(self):
        types = _detect_vuln_types("SQL INJECTION detected")
        assert "sql_injection" in types