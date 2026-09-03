"""
Chimeras v3.1 — DOCX Report Exporter

Renders the structured pentest report to Microsoft Word (.docx) using
python-docx. Produces a client-editable document with Cyberian Defenses
branding, CVSS color-coded finding tables, and professional formatting.

Some clients demand Word format for internal editing and risk register
integration. This exporter gives them that without sacrificing structure.

Integration:
    Bookkeeper calls export_docx() at report time alongside
    structured_report.md, findings.sarif, and pentest_report.pdf.
    Output: pentest_report.docx in the engagement report directory.
"""

import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn, nsdecls
    from docx.oxml import parse_xml
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    Document = None

# ─── Severity color mapping ───────────────────────────────────────────

_SEVERITY_COLORS = {
    "critical": RGBColor(0x7f, 0x1d, 0x1d),  # dark red
    "high":     RGBColor(0xdc, 0x26, 0x26),  # red
    "medium":   RGBColor(0xf5, 0x9e, 0x0b),  # amber
    "low":      RGBColor(0x3b, 0x82, 0xf6),  # blue
    "info":     RGBColor(0x6b, 0x72, 0x80),  # gray
}

_DEFAULT_COLOR = RGBColor(0x6b, 0x72, 0x80)

# Hex strings for cell shading
_SEVERITY_SHADING = {
    "critical": "7F1D1D",
    "high":     "DC2626",
    "medium":   "F59E0B",
    "low":      "3B82F6",
    "info":     "6B7280",
}
_DEFAULT_SHADING = "6B7280"


def _severity_color(severity: str) -> RGBColor:
    return _SEVERITY_COLORS.get((severity or "").lower(), _DEFAULT_COLOR)


def _severity_shading(severity: str) -> str:
    return _SEVERITY_SHADING.get((severity or "").lower(), _DEFAULT_SHADING)


def _shade_cell(cell, color_hex: str):
    """Apply background shading to a table cell."""
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def _set_cell_text(cell, text: str, bold: bool = False, color: RGBColor = None,
                   font_size: int = 9, white_text: bool = False):
    """Set cell text with formatting."""
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run(str(text))
    run.bold = bold
    run.font.size = Pt(font_size)
    if white_text:
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    elif color:
        run.font.color.rgb = color


def _strip_md(text: str) -> str:
    """Strip markdown formatting markers for plain text display in DOCX."""
    if not text:
        return ""
    text = str(text)
    # Remove bold markers
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # Remove italic markers
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Remove inline code backticks
    text = re.sub(r'`(.+?)`', r'\1', text)
    # Convert links to "text (url)"
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'\1 (\2)', text)
    # Remove heading markers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bullet markers
    text = re.sub(r'^[-*]\s+', '', text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    return text.strip()


def _add_md_content(doc: Document, md_text: str, base_style: str = None):
    """Add markdown-formatted text to a DOCX document.

    Handles headings, bullet lists, numbered lists, code blocks, and paragraphs.
    """
    if not md_text:
        p = doc.add_paragraph("N/A")
        return

    lines = md_text.strip().split("\n")
    in_code_block = False
    code_lines: List[str] = []

    for line in lines:
        stripped = line.strip()

        # Code block fences
        if stripped.startswith("```"):
            if in_code_block:
                # End code block — flush as monospace paragraph
                code_text = "\n".join(code_lines)
                if code_text:
                    p = doc.add_paragraph()
                    run = p.add_run(code_text)
                    run.font.name = "Courier New"
                    run.font.size = Pt(8.5)
                    run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
                    p.paragraph_format.left_indent = Cm(0.5)
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Headings
        if stripped.startswith("### "):
            doc.add_heading(stripped[4:], level=3)
            continue
        if stripped.startswith("## "):
            doc.add_heading(stripped[3:], level=2)
            continue
        if stripped.startswith("# "):
            doc.add_heading(stripped[2:], level=1)
            continue

        # Horizontal rule
        if stripped in ("---", "***", "___"):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(6)
            # Add a bottom border to the paragraph
            pPr = p._p.get_or_add_pPr()
            pBdr = parse_xml(
                f'<w:pBdr {nsdecls("w")}>'
                f'<w:bottom w:val="single" w:sz="6" w:space="1" w:color="CCCCCC"/>'
                f'</w:pBdr>'
            )
            pPr.append(pBdr)
            continue

        # Bullet list
        if re.match(r'^[-*]\s+', stripped):
            content = re.sub(r'^[-*]\s+', '', stripped)
            p = doc.add_paragraph(_strip_md(content), style='List Bullet')
            continue

        # Numbered list
        if re.match(r'^\d+\.\s+', stripped):
            content = re.sub(r'^\d+\.\s+', '', stripped)
            p = doc.add_paragraph(_strip_md(content), style='List Number')
            continue

        # Empty line
        if not stripped:
            continue

        # Regular paragraph
        p = doc.add_paragraph(_strip_md(stripped))


def _add_findings_table(doc: Document, findings: List[Dict[str, Any]]):
    """Add the findings summary table to the document."""
    if not findings:
        p = doc.add_paragraph("No findings recorded.")
        p.runs[0].italic = True
        return

    table = doc.add_table(rows=1, cols=5)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Header row
    headers = ["ID", "Finding", "Severity", "CVSS", "Status"]
    widths = [Cm(2), Cm(7), Cm(2.5), Cm(1.5), Cm(3)]
    for i, (header, width) in enumerate(zip(headers, widths)):
        cell = table.rows[0].cells[i]
        _shade_cell(cell, "1E3A5F")
        _set_cell_text(cell, header, bold=True, white_text=True, font_size=9)
        cell.width = width

    # Data rows
    for idx, f in enumerate(findings):
        row = table.add_row()
        severity = (f.get("severity") or "info").lower()

        # Alternating row shading
        if idx % 2 == 1:
            for cell in row.cells:
                _shade_cell(cell, "F8FAFC")

        fid = f.get("id", f"FILL-{idx:03d}")
        title = f.get("title", "")
        sev = f.get("severity", "N/A")
        cvss = str(f.get("cvss", "N/A"))
        status = f.get("status", "")

        _set_cell_text(row.cells[0], fid, bold=True, font_size=9)
        _set_cell_text(row.cells[1], title, font_size=9)
        _set_cell_text(row.cells[2], sev, bold=True,
                       color=_severity_color(severity), font_size=9)
        _set_cell_text(row.cells[3], cvss, font_size=9)
        _set_cell_text(row.cells[4], status, font_size=9)

        # Set column widths
        for i, width in enumerate(widths):
            row.cells[i].width = width


def _add_finding_detail(doc: Document, finding: Dict[str, Any], index: int):
    """Add a detailed finding section to the document."""
    severity = (finding.get("severity") or "info").lower()
    fid = finding.get("id", f"FILL-{index:03d}")
    title = finding.get("title", "Untitled Finding")
    cvss = finding.get("cvss", "N/A")
    status = finding.get("status", "Confirmed")

    # Heading with severity color
    heading = doc.add_heading(f"{fid}: {title}", level=2)

    # Metadata line
    p = doc.add_paragraph()
    run = p.add_run(f"Severity: ")
    run.bold = True
    run.font.size = Pt(10)
    run = p.add_run(f"{severity.upper()}")
    run.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = _severity_color(severity)

    run = p.add_run(f"  |  CVSS: {cvss}  |  Status: {status}")
    run.font.size = Pt(10)

    # Sections
    sections = [
        ("Description", finding.get("description", "N/A")),
        ("Risks", finding.get("risks", "N/A")),
        ("Attack Vectors", finding.get("attack_vectors", "N/A")),
        ("Proof of Concept", finding.get("poc", "N/A")),
        ("Proof of Existence", finding.get("proof_of_existence", "N/A")),
    ]

    for section_title, content in sections:
        doc.add_heading(section_title, level=3)
        if section_title == "Proof of Existence":
            # Render as monospace block
            p = doc.add_paragraph()
            run = p.add_run(_strip_md(content) if content else "N/A")
            run.font.name = "Courier New"
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
            p.paragraph_format.left_indent = Cm(0.5)
        else:
            _add_md_content(doc, content)

    # Evidence hash (if present)
    evidence_hash = finding.get("evidence_hash")
    if evidence_hash:
        doc.add_heading("Evidence Hash (SHA-256)", level=3)
        p = doc.add_paragraph()
        run = p.add_run(evidence_hash)
        run.font.name = "Courier New"
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x1e, 0x3a, 0x5f)

    # Compliance mappings (if present)
    compliance = finding.get("compliance", {})
    compliance_mappings = compliance.get("compliance", {}) if compliance else {}
    if compliance_mappings:
        doc.add_heading("Compliance Mapping", level=3)
        comp_table = doc.add_table(rows=1, cols=3)
        comp_table.style = 'Table Grid'
        for i, header in enumerate(["Framework", "Control ID", "Control Name"]):
            cell = comp_table.rows[0].cells[i]
            _shade_cell(cell, "475569")
            _set_cell_text(cell, header, bold=True, white_text=True, font_size=9)
        for fw_name, controls in compliance_mappings.items():
            for ctrl in controls:
                row = comp_table.add_row()
                _set_cell_text(row.cells[0], fw_name, bold=True, font_size=9)
                _set_cell_text(row.cells[1], ctrl["control_id"], font_size=9)
                _set_cell_text(row.cells[2], ctrl["control_name"], font_size=9)

    # Remediation
    doc.add_heading("Remediation", level=3)
    _add_md_content(doc, finding.get("remediation", "N/A"))

    # Separator
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)


def export_docx(
    output_path: Path,
    engagement_name: str = "N/A",
    client_name: str = "",
    executive_summary: str = "",
    mission_scope: str = "",
    internal_scope: str = "",
    roe: str = "",
    targets: Optional[List[str]] = None,
    findings: Optional[List[Dict[str, Any]]] = None,
    engagement_flow: str = "",
    critical_findings: Optional[List[Dict]] = None,
    decision_audit: str = "",
    cleanup_status: str = "No cleanup performed.",
    mission_outcome: str = "",
    narrative_md: str = "",
) -> bool:
    """Export a professional pentest report to DOCX.

    When narrative_md is provided, the DOCX renders the LLM-written narrative
    as the primary body — the real pentest report. Evidence hashes and
    compliance mappings are appended as appendices.

    When narrative_md is empty, falls back to structured finding sections
    (backward compatibility).

    Args:
        output_path: Where to write the .docx file.
        narrative_md: LLM-generated report markdown (final_report.md content).

    Returns:
        True if DOCX was written, False if python-docx unavailable.
    """
    if not DOCX_AVAILABLE:
        logger.warning("python-docx not installed — DOCX export skipped")
        return False

    targets = targets or []
    findings = findings or []
    critical_findings = critical_findings or []

    report_date = datetime.utcnow().strftime("%Y-%m-%d")

    doc = Document()

    # ─── Page margins ───
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(1.8)
        section.right_margin = Cm(1.8)

    # ─── Cover page ───
    title = doc.add_heading("Penetration Test Report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    subtitle = doc.add_paragraph("Confidential — Authorized Security Assessment")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.runs[0].font.size = Pt(14)
    subtitle.runs[0].font.color.rgb = RGBColor(0x94, 0xa3, 0xb8)

    doc.add_paragraph()  # spacer

    # Cover metadata table
    meta_table = doc.add_table(rows=6, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("Engagement", engagement_name),
        ("Client", client_name or "N/A"),
        ("Date", report_date),
        ("Targets", ", ".join(targets) if targets else "N/A"),
        ("Tester", "Chimeras Autonomous AI Pentest Swarm"),
        ("Findings", f"{len(findings)} total ({sum(1 for f in findings if (f.get('severity','') or '').lower() == 'critical')} critical)"),
    ]
    for i, (label, value) in enumerate(meta_data):
        _set_cell_text(meta_table.rows[i].cells[0], label, bold=True, font_size=10)
        _set_cell_text(meta_table.rows[i].cells[1], str(value), font_size=10)
        _shade_cell(meta_table.rows[i].cells[0], "F1F5F9")

    doc.add_paragraph()  # spacer

    branding = doc.add_paragraph(
        f"Generated by Chimeras v3.1 — Cyberian Defenses\n"
        f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    )
    branding.alignment = WD_ALIGN_PARAGRAPH.CENTER
    branding.runs[0].font.size = Pt(9)
    branding.runs[0].font.color.rgb = RGBColor(0x64, 0x74, 0x8b)

    doc.add_page_break()

    if narrative_md:
        # ─── NARRATIVE MODE: render the LLM report as the body ───
        # Strip HTML comments (theme metadata)
        import re as _re
        clean_narrative = _re.sub(r'<!--.*?-->', '', narrative_md, flags=_re.DOTALL)
        _add_md_content(doc, clean_narrative)

        # ─── Appendices ───
        doc.add_page_break()
        doc.add_heading("Appendix A: Findings Summary Table", level=1)
        _add_findings_table(doc, findings)

        # Evidence hashes appendix
        has_evidence = any(f.get("evidence_hash") for f in findings)
        if has_evidence:
            doc.add_heading("Appendix B: Evidence Chain (SHA-256)", level=1)
            doc.add_paragraph(
                "Each finding is backed by SHA-256 hashed evidence artifacts. "
                "The evidence locker manifest is tamper-detectable."
            )
            ev_table = doc.add_table(rows=1, cols=2)
            ev_table.style = 'Table Grid'
            _set_cell_text(ev_table.rows[0].cells[0], "Finding ID", bold=True, white_text=True, font_size=9)
            _set_cell_text(ev_table.rows[0].cells[1], "Evidence SHA-256", bold=True, white_text=True, font_size=9)
            _shade_cell(ev_table.rows[0].cells[0], "1E3A5F")
            _shade_cell(ev_table.rows[0].cells[1], "1E3A5F")
            for f in findings:
                eh = f.get("evidence_hash")
                if eh:
                    row = ev_table.add_row()
                    _set_cell_text(row.cells[0], f.get("id", ""), bold=True, font_size=9)
                    _set_cell_text(row.cells[1], eh[:32] + "...", font_size=9)

        # Compliance mapping appendix
        has_compliance = any(
            f.get("compliance", {}).get("compliance") for f in findings
        )
        if has_compliance:
            doc.add_heading("Appendix C: Compliance Mapping", level=1)
            doc.add_paragraph(
                "Findings mapped to OWASP ASVS 4.0, PCI DSS 4.0, "
                "ISO 27001:2022, and NIST 800-53 Rev 5."
            )
            for f in findings:
                compliance = f.get("compliance", {})
                mappings = compliance.get("compliance", {})
                if not mappings:
                    continue
                doc.add_heading(f"{f.get('id', '')}: {f.get('title', '')}", level=3)
                comp_table = doc.add_table(rows=1, cols=3)
                comp_table.style = 'Table Grid'
                for j, header in enumerate(["Framework", "Control ID", "Control Name"]):
                    cell = comp_table.rows[0].cells[j]
                    _shade_cell(cell, "475569")
                    _set_cell_text(cell, header, bold=True, white_text=True, font_size=9)
                for fw_name, controls in mappings.items():
                    for ctrl in controls:
                        row = comp_table.add_row()
                        _set_cell_text(row.cells[0], fw_name, bold=True, font_size=9)
                        _set_cell_text(row.cells[1], ctrl["control_id"], font_size=9)
                        _set_cell_text(row.cells[2], ctrl["control_name"], font_size=9)

    else:
        # ─── STRUCTURED MODE: fallback (backward compat) ───
        # 1. Executive Summary
        doc.add_heading("1. Executive Summary", level=1)
        _add_md_content(doc, executive_summary or "N/A")

        # 2. Scope
        doc.add_heading("2. Scope", level=1)
        p = doc.add_paragraph()
        run = p.add_run("Mission Scope: ")
        run.bold = True
        p.add_run(mission_scope or "N/A")

        p = doc.add_paragraph()
        run = p.add_run("Internal Scope: ")
        run.bold = True
        p.add_run(internal_scope or "N/A")

        p = doc.add_paragraph()
        run = p.add_run("Rules of Engagement: ")
        run.bold = True
        p.add_run(roe or "N/A")

        doc.add_heading("Targets Tested", level=3)
        if targets:
            for t in targets:
                doc.add_paragraph(t, style='List Bullet')
        else:
            doc.add_paragraph("No targets listed.")

        # 3. Findings Summary
        doc.add_heading("3. Findings Summary", level=1)
        _add_findings_table(doc, findings)

        # 4. Detailed Findings
        doc.add_heading("4. Detailed Findings", level=1)
        if findings:
            for i, f in enumerate(findings):
                _add_finding_detail(doc, f, i)
        else:
            p = doc.add_paragraph("No detailed findings recorded.")
            p.runs[0].italic = True

        # 5. Engagement Flow
        doc.add_heading("5. Engagement Flow", level=1)
        _add_md_content(doc, engagement_flow or "N/A")

        # 6. Critical Findings
        doc.add_heading("6. Critical Findings", level=1)
        if critical_findings:
            for cf in critical_findings:
                bot = cf.get("bot", "").upper()
                cvss = cf.get("cvss", "")
                target = cf.get("target", "")
                finding_text = cf.get("finding", "")
                doc.add_paragraph(
                    f"[{bot}] CVSS {cvss} on {target}: {finding_text}",
                    style='List Bullet'
                )
        else:
            p = doc.add_paragraph("No critical findings (CVSS >= 7.0) recorded.")
            p.runs[0].italic = True

        # 7. Decision Audit Trail
        doc.add_heading("7. Decision Audit Trail", level=1)
        _add_md_content(doc, decision_audit or "N/A")

        # 8. Cleanup Status
        doc.add_heading("8. Cleanup Status", level=1)
        _add_md_content(doc, cleanup_status)

        # 9. Mission Outcome
        doc.add_heading("9. Mission Outcome", level=1)
        _add_md_content(doc, mission_outcome or "N/A")

    # ─── Footer ───
    doc.add_paragraph()  # spacer
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(
        f"Report generated by Chimeras v3.1 — Cyberian Defenses\n"
        f"{datetime.utcnow().isoformat()}"
    )
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(0x6b, 0x72, 0x80)

    try:
        doc.save(str(output_path))
        logger.info(f"DOCX exported: {len(findings)} findings → {output_path.name}")
        return True
    except Exception as e:
        logger.error(f"DOCX export failed: {e}")
        raise


def is_docx_available() -> bool:
    """Check if DOCX export is available (python-docx installed)."""
    return DOCX_AVAILABLE