"""
Tests for v3.1 PDF and DOCX report exporters.

Tests cover:
- Export produces valid files
- Files are non-empty
- Empty findings handled gracefully
- Single finding works
- Multiple findings with all severity levels
- Availability checks return correctly
- Exporter functions handle missing data gracefully
- Markdown-to-HTML conversion (PDF)
- Markdown stripping (DOCX)
- Severity color mapping
"""

import pytest
from pathlib import Path
import tempfile

from core.pdf_exporter import (
    export_pdf,
    is_pdf_available,
    _severity_style,
    _escape_html,
    _md_inline_to_html,
    _md_block_to_html,
)
from core.docx_exporter import (
    export_docx,
    is_docx_available,
    _severity_color,
    _severity_shading,
    _strip_md,
)


# ─── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def sample_findings():
    return [
        {
            "id": "BH-001",
            "title": "SSL/TLS Weak Cipher Suites",
            "severity": "high",
            "cvss": "7.5",
            "status": "Confirmed",
            "description": "The target supports deprecated TLS 1.0.",
            "risks": "Man-in-the-middle attacks can decrypt traffic.",
            "attack_vectors": "- Scan with sslscan\n- Identify weak ciphers",
            "poc": "sslscan --no-failed 10.0.0.1",
            "proof_of_existence": "TLS 1.0 enabled\nCipher: TLS_RSA_WITH_AES_128_CBC_SHA",
            "remediation": "Disable TLS 1.0/1.1. Enforce TLS 1.2+.",
        },
        {
            "id": "WASP-001",
            "title": "SQL Injection in Login Form",
            "severity": "critical",
            "cvss": "9.8",
            "status": "Exploited",
            "description": "Login endpoint vulnerable to SQL injection.",
            "risks": "Full database compromise. Credential theft.",
            "attack_vectors": "1. Navigate to /login\n2. Enter payload",
            "poc": "sqlmap -u http://target/login --batch",
            "proof_of_existence": "sqlmap confirmed: boolean-based blind",
            "remediation": "Use parameterized queries. Input validation.",
        },
        {
            "id": "LISA-001",
            "title": "Open SSH Port",
            "severity": "info",
            "cvss": "0.0",
            "status": "Confirmed",
            "description": "SSH service is running on port 22.",
            "risks": "Informational — no direct risk.",
            "attack_vectors": "N/A",
            "poc": "nmap -p 22 10.0.0.1",
            "proof_of_existence": "22/tcp open ssh",
            "remediation": "Ensure SSH is properly secured.",
        },
    ]


@pytest.fixture
def sample_critical():
    return [
        {"bot": "wasp", "cvss": "9.8", "target": "10.0.0.1", "finding": "SQL Injection"},
    ]


@pytest.fixture
def export_kwargs(sample_findings, sample_critical):
    return {
        "engagement_name": "test.cyberian-defenses.com",
        "client_name": "Test Client",
        "executive_summary": "This engagement found 3 findings including 1 critical.",
        "mission_scope": "External black-box assessment",
        "internal_scope": "N/A",
        "roe": "Authorized penetration test.",
        "targets": ["10.0.0.1", "test.cyberian-defenses.com"],
        "findings": sample_findings,
        "critical_findings": sample_critical,
        "engagement_flow": "1. ARIA recon, 2. Lisa scan, 3. Report",
        "decision_audit": "1. [recon] scan (0.95)",
        "cleanup_status": "No artifacts left on target.",
        "mission_outcome": "Engagement completed.",
    }


# ─── Availability tests ───────────────────────────────────────────────

class TestAvailability:
    def test_pdf_available(self):
        """is_pdf_available should return True in the test env."""
        assert is_pdf_available() is True

    def test_docx_available(self):
        """is_docx_available should return True in the test env."""
        assert is_docx_available() is True


# ─── PDF export tests ─────────────────────────────────────────────────

class TestPDFExport:
    def test_pdf_file_created(self, tmp_path, export_kwargs):
        """export_pdf should produce a non-empty PDF file."""
        pdf_path = tmp_path / "report.pdf"
        result = export_pdf(output_path=pdf_path, **export_kwargs)
        assert result is True
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 1000  # at least 1KB

    def test_pdf_magic_bytes(self, tmp_path, export_kwargs):
        """PDF file should start with %PDF magic bytes."""
        pdf_path = tmp_path / "report.pdf"
        export_pdf(output_path=pdf_path, **export_kwargs)
        with open(pdf_path, "rb") as f:
            magic = f.read(5)
        assert magic == b"%PDF-"

    def test_pdf_empty_findings(self, tmp_path):
        """export_pdf should handle zero findings gracefully."""
        pdf_path = tmp_path / "empty.pdf"
        result = export_pdf(
            output_path=pdf_path,
            engagement_name="empty.test",
            findings=[],
            targets=["10.0.0.1"],
        )
        assert result is True
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 500

    def test_pdf_single_finding(self, tmp_path, sample_findings):
        """export_pdf should work with exactly one finding."""
        pdf_path = tmp_path / "single.pdf"
        result = export_pdf(
            output_path=pdf_path,
            engagement_name="single.test",
            findings=[sample_findings[0]],
            targets=["10.0.0.1"],
        )
        assert result is True
        assert pdf_path.exists()

    def test_pdf_all_severities(self, tmp_path):
        """export_pdf should handle all severity levels without errors."""
        severities = ["critical", "high", "medium", "low", "info"]
        findings = [
            {
                "id": f"F-{i:03d}",
                "title": f"Test {s}",
                "severity": s,
                "cvss": str(i * 2.5),
                "status": "Confirmed",
                "description": f"Test finding with {s} severity.",
                "risks": "Test risk.",
                "attack_vectors": "Test vector.",
                "poc": "test command",
                "proof_of_existence": "test evidence",
                "remediation": "Fix it.",
            }
            for i, s in enumerate(severities)
        ]
        pdf_path = tmp_path / "severities.pdf"
        result = export_pdf(
            output_path=pdf_path,
            engagement_name="severity.test",
            findings=findings,
            targets=["10.0.0.1"],
        )
        assert result is True
        assert pdf_path.stat().st_size > 2000

    def test_pdf_no_targets(self, tmp_path, sample_findings):
        """export_pdf should handle empty targets list."""
        pdf_path = tmp_path / "notargets.pdf"
        result = export_pdf(
            output_path=pdf_path,
            engagement_name="notargets.test",
            findings=sample_findings,
            targets=[],
        )
        assert result is True
        assert pdf_path.exists()

    def test_pdf_minimal_data(self, tmp_path):
        """export_pdf should work with absolute minimal data."""
        pdf_path = tmp_path / "minimal.pdf"
        result = export_pdf(output_path=pdf_path)
        assert result is True
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 500


# ─── DOCX export tests ────────────────────────────────────────────────

class TestDOCXExport:
    def test_docx_file_created(self, tmp_path, export_kwargs):
        """export_docx should produce a non-empty DOCX file."""
        docx_path = tmp_path / "report.docx"
        result = export_docx(output_path=docx_path, **export_kwargs)
        assert result is True
        assert docx_path.exists()
        assert docx_path.stat().st_size > 1000

    def test_docx_zip_magic(self, tmp_path, export_kwargs):
        """DOCX file is a ZIP archive — should start with PK magic."""
        docx_path = tmp_path / "report.docx"
        export_docx(output_path=docx_path, **export_kwargs)
        with open(docx_path, "rb") as f:
            magic = f.read(2)
        assert magic == b"PK"

    def test_docx_empty_findings(self, tmp_path):
        """export_docx should handle zero findings gracefully."""
        docx_path = tmp_path / "empty.docx"
        result = export_docx(
            output_path=docx_path,
            engagement_name="empty.test",
            findings=[],
            targets=["10.0.0.1"],
        )
        assert result is True
        assert docx_path.exists()

    def test_docx_single_finding(self, tmp_path, sample_findings):
        """export_docx should work with exactly one finding."""
        docx_path = tmp_path / "single.docx"
        result = export_docx(
            output_path=docx_path,
            engagement_name="single.test",
            findings=[sample_findings[0]],
            targets=["10.0.0.1"],
        )
        assert result is True
        assert docx_path.exists()

    def test_docx_all_severities(self, tmp_path):
        """export_docx should handle all severity levels without errors."""
        severities = ["critical", "high", "medium", "low", "info"]
        findings = [
            {
                "id": f"F-{i:03d}",
                "title": f"Test {s}",
                "severity": s,
                "cvss": str(i * 2.5),
                "status": "Confirmed",
                "description": f"Test finding with {s} severity.",
                "risks": "Test risk.",
                "attack_vectors": "Test vector.",
                "poc": "test command",
                "proof_of_existence": "test evidence",
                "remediation": "Fix it.",
            }
            for i, s in enumerate(severities)
        ]
        docx_path = tmp_path / "severities.docx"
        result = export_docx(
            output_path=docx_path,
            engagement_name="severity.test",
            findings=findings,
            targets=["10.0.0.1"],
        )
        assert result is True
        assert docx_path.stat().st_size > 2000

    def test_docx_no_targets(self, tmp_path, sample_findings):
        """export_docx should handle empty targets list."""
        docx_path = tmp_path / "notargets.docx"
        result = export_docx(
            output_path=docx_path,
            engagement_name="notargets.test",
            findings=sample_findings,
            targets=[],
        )
        assert result is True
        assert docx_path.exists()

    def test_docx_minimal_data(self, tmp_path):
        """export_docx should work with absolute minimal data."""
        docx_path = tmp_path / "minimal.docx"
        result = export_docx(output_path=docx_path)
        assert result is True
        assert docx_path.exists()

    def test_docx_content_has_findings(self, tmp_path, export_kwargs):
        """DOCX content should include finding titles."""
        from docx import Document
        docx_path = tmp_path / "content.docx"
        export_docx(output_path=docx_path, **export_kwargs)
        doc = Document(str(docx_path))
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "SQL Injection" in full_text
        assert "SSL/TLS" in full_text

    def test_docx_has_table(self, tmp_path, export_kwargs):
        """DOCX should contain at least one table (findings summary)."""
        from docx import Document
        docx_path = tmp_path / "table.docx"
        export_docx(output_path=docx_path, **export_kwargs)
        doc = Document(str(docx_path))
        assert len(doc.tables) >= 1
        # Findings table should have header + 3 data rows
        findings_table = doc.tables[0]
        assert len(findings_table.rows) >= 4  # header + 3 findings


# ─── Unit tests: helper functions ─────────────────────────────────────

class TestSeverityStyles:
    def test_critical_style(self):
        style = _severity_style("critical")
        assert style["bg"] == "#7f1d1d"

    def test_high_style(self):
        style = _severity_style("high")
        assert style["bg"] == "#dc2626"

    def test_unknown_severity_defaults(self):
        style = _severity_style("nonexistent")
        assert style == {
            "bg": "#6b7280", "text": "#ffffff", "border": "#4b5563",
        }

    def test_case_insensitive(self):
        assert _severity_style("CRITICAL") == _severity_style("critical")
        assert _severity_style("High") == _severity_style("high")


class TestSeverityColorsDOCX:
    def test_critical_color(self):
        color = _severity_color("critical")
        assert color is not None

    def test_unknown_color(self):
        color = _severity_color("unknown")
        assert color is not None

    def test_shading_hex(self):
        assert _severity_shading("critical") == "7F1D1D"
        assert _severity_shading("info") == "6B7280"


class TestEscapeHtml:
    def test_basic_escape(self):
        assert _escape_html("<script>") == "&lt;script&gt;"

    def test_amp_escape(self):
        assert _escape_html("a & b") == "a &amp; b"

    def test_empty(self):
        assert _escape_html("") == ""

    def test_none(self):
        assert _escape_html(None) == ""


class TestMdInlineToHtml:
    def test_bold(self):
        result = _md_inline_to_html("**bold**")
        assert "<strong>bold</strong>" in result

    def test_italic(self):
        result = _md_inline_to_html("*italic*")
        assert "<em>italic</em>" in result

    def test_code(self):
        result = _md_inline_to_html("`code`")
        assert "<code>code</code>" in result

    def test_link(self):
        result = _md_inline_to_html("[text](http://url)")
        assert '<a href="http://url">text</a>' in result

    def test_plain_text_escaped(self):
        result = _md_inline_to_html("plain & text")
        assert "&amp;" in result


class TestMdBlockToHtml:
    def test_heading(self):
        result = _md_block_to_html("## Heading")
        assert "<h2>Heading</h2>" in result

    def test_bullet_list(self):
        result = _md_block_to_html("- item 1\n- item 2")
        assert "<ul>" in result
        assert "<li>" in result
        assert "item 1" in result

    def test_numbered_list(self):
        result = _md_block_to_html("1. first\n2. second")
        assert "<ol>" in result
        assert "first" in result

    def test_code_block(self):
        result = _md_block_to_html("```\ncode here\n```")
        assert "<pre><code>" in result
        assert "code here" in result

    def test_table(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = _md_block_to_html(md)
        assert "<table" in result
        assert "<th>" in result
        assert "<td>" in result

    def test_empty(self):
        assert _md_block_to_html("") == ""

    def test_paragraph(self):
        result = _md_block_to_html("Just a paragraph.")
        assert "<p>" in result
        assert "Just a paragraph." in result


class TestStripMd:
    def test_strip_bold(self):
        assert _strip_md("**bold**") == "bold"

    def test_strip_italic(self):
        assert _strip_md("*italic*") == "italic"

    def test_strip_code(self):
        assert _strip_md("`code`") == "code"

    def test_strip_link(self):
        result = _strip_md("[text](http://url)")
        assert "text" in result
        assert "http://url" in result

    def test_strip_heading(self):
        assert _strip_md("## Heading") == "Heading"

    def test_strip_bullet(self):
        assert _strip_md("- item") == "item"

    def test_empty(self):
        assert _strip_md("") == ""

    def test_plain_text(self):
        assert _strip_md("plain text") == "plain text"