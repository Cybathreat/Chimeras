"""
Chimeras v3.2 — Proposal & SOW Generator

Pre-engagement tool. Input: target scope + client details. Output: professional
proposal with pricing tiers, rules of engagement, and SOW — ready for client signature.

Compresses scoping from 3 days to 3 hours. Also serves as BizDev ammunition —
feeds the sales pipeline with Chimeras-generated scope inventories.

Usage:
    from core.proposal_generator import generate_proposal

    generate_proposal(
        output_path=Path("proposals/client_xyz_proposal.docx"),
        client_name="Bank of Tunisia",
        targets=["10.0.0.0/24", "example.com"],
        engagement_type="external_pentest",
        day_rate=500,
        estimated_days=5,
        currency="USD",
    )
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from docx import Document as _Doc
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import nsdecls
    from docx.oxml import parse_xml
    DOCX_OK = True
except ImportError:
    DOCX_OK = False

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_OK = True
except ImportError:
    WEASYPRINT_OK = False


# Engagement type templates
_ENGAGEMENT_TYPES = {
    "external_pentest": {
        "title": "External Network Penetration Test",
        "phases": [
            "Passive Reconnaissance (OSINT, DNS, certificate transparency)",
            "Active Scanning (port scanning, service enumeration, fingerprinting)",
            "Vulnerability Detection (CVE matching, SSL/TLS analysis, web app testing)",
            "Exploitation Assessment (human-gated, PoC only, no data exfiltration)",
            "Reporting (executive summary, findings, remediation, compliance mapping)",
        ],
        "deliverables": [
            "Penetration test report (PDF + DOCX)",
            "Findings in SARIF format",
            "Compliance mapping (OWASP ASVS, PCI DSS, ISO 27001, NIST 800-53)",
            "SHA-256 hashed evidence chain",
            "Static client portal (self-contained HTML)",
            "Coverage report (thoroughness proof)",
        ],
    },
    "web_app_pentest": {
        "title": "Web Application Penetration Test",
        "phases": [
            "Reconnaissance (technology fingerprint, WAF detection, DNS)",
            "Content Discovery (directory enumeration, hidden paths)",
            "OWASP Top 10 Testing (XSS, SQLi, CSRF, SSRF, IDOR, SSTI, LFI/RFI)",
            "Authentication & Session Testing",
            "API Security Testing",
            "Reporting (executive summary, findings, remediation, compliance)",
        ],
        "deliverables": [
            "Penetration test report (PDF + DOCX)",
            "Findings in SARIF format",
            "OWASP ASVS 4.0 compliance mapping",
            "SHA-256 hashed evidence chain",
            "Static client portal",
            "Retest report template (for remediation verification)",
        ],
    },
    "internal_pentest": {
        "title": "Internal Network Penetration Test",
        "phases": [
            "Network Discovery (internal host enumeration)",
            "Service Scanning (port scan, service identification)",
            "Vulnerability Detection (CVE matching, misconfiguration analysis)",
            "Exploitation & Lateral Movement (human-gated)",
            "Privilege Escalation Assessment",
            "Reporting (executive summary, findings, remediation)",
        ],
        "deliverables": [
            "Penetration test report (PDF + DOCX)",
            "Findings in SARIF format",
            "Compliance mapping (ISO 27001, NIST 800-53)",
            "Evidence chain with artifact tracking",
            "Lateral movement audit trail",
            "Static client portal",
        ],
    },
    "retest": {
        "title": "Penetration Test Retest Verification",
        "phases": [
            "Load previous engagement findings",
            "Re-run PoC commands for each finding",
            "Compare before/after output",
            "Generate delta report (Closed/Open/Partial per finding)",
            "Update compliance mapping with remediation status",
        ],
        "deliverables": [
            "Retest report (PDF + DOCX) with remediation rate",
            "Delta findings (NEW regressions, FIXED wins)",
            "Updated compliance mapping",
            "Evidence chain re-verification",
        ],
    },
}


def _shade_cell(cell, color_hex: str):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def _set_cell(cell, text: str, bold=False, white=False, size=10):
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run(str(text))
    run.bold = bold
    run.font.size = Pt(size)
    if white:
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def generate_proposal(
    output_path: Path,
    client_name: str = "",
    targets: Optional[List[str]] = None,
    engagement_type: str = "external_pentest",
    day_rate: int = 500,
    estimated_days: int = 5,
    currency: str = "USD",
    roe: str = "",
    tester: str = "Cyberian Defenses",
    language: str = "en",
) -> bool:
    """Generate a professional proposal/SOW as DOCX.

    Args:
        output_path: Where to write the .docx file.
        client_name: Client company name.
        targets: List of in-scope targets.
        engagement_type: One of external_pentest, web_app_pentest, internal_pentest, retest.
        day_rate: Daily rate in the specified currency.
        estimated_days: Estimated engagement duration.
        currency: Currency code (USD, EUR, TND).
        roe: Rules of engagement text (optional, auto-generated if empty).
        tester: Testing firm name.

    Returns:
        True if proposal was written.
    """
    if not DOCX_OK:
        logger.warning("python-docx not installed — proposal generation skipped")
        return False

    targets = targets or []
    eng = _ENGAGEMENT_TYPES.get(engagement_type, _ENGAGEMENT_TYPES["external_pentest"])
    total_cost = day_rate * estimated_days

    if not roe:
        roe = (
            "Authorized penetration test. No denial of service. "
            "No data destruction. No data exfiltration without explicit approval. "
            "Exploitation phase gated on human approval. "
            "All activities logged with audit trail."
        )

    doc = _Doc()

    # Margins
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(1.8)
        section.right_margin = Cm(1.8)

    # Title
    title = doc.add_heading(f"Proposal: {eng['title']}", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p = doc.add_paragraph("Confidential — For Client Review")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].font.color.rgb = RGBColor(0x94, 0xa3, 0xb8)
    p.runs[0].font.size = Pt(12)

    doc.add_paragraph()  # spacer

    # Engagement metadata table
    meta = doc.add_table(rows=7, cols=2)
    meta_data = [
        ("Client", client_name or "N/A"),
        ("Engagement Type", eng["title"]),
        ("Testing Firm", tester),
        ("Date", datetime.utcnow().strftime("%Y-%m-%d")),
        ("Estimated Duration", f"{estimated_days} days"),
        ("Day Rate", f"{currency} {day_rate:,}"),
        ("Total Estimated Cost", f"{currency} {total_cost:,}"),
    ]
    for i, (label, value) in enumerate(meta_data):
        _set_cell(meta.rows[i].cells[0], label, bold=True, size=10)
        _set_cell(meta.rows[i].cells[1], str(value), size=10)
        _shade_cell(meta.rows[i].cells[0], "F1F5F9")

    doc.add_page_break()

    # 1. Scope
    doc.add_heading("1. Scope", level=1)
    doc.add_paragraph(
        "The following targets are in scope for this engagement:"
    )
    if targets:
        for t in targets:
            doc.add_paragraph(t, style='List Bullet')
    else:
        doc.add_paragraph("To be determined during scoping call.")

    doc.add_heading("Out of Scope", level=3)
    doc.add_paragraph(
        "Any systems, networks, or applications not explicitly listed above are out of scope. "
        "Scope expansion requires written client approval and may incur additional costs."
    )

    # 2. Rules of Engagement
    doc.add_heading("2. Rules of Engagement", level=1)
    doc.add_paragraph(roe)

    # 3. Methodology
    doc.add_heading("3. Methodology", level=1)
    doc.add_paragraph(
        "The engagement follows a multi-phase swarm-based methodology using "
        "the Chimeras Autonomous AI Pentest Swarm:"
    )
    for i, phase in enumerate(eng["phases"], 1):
        doc.add_paragraph(f"Phase {i}: {phase}", style='List Number')

    # 4. Deliverables
    doc.add_heading("4. Deliverables", level=1)
    doc.add_paragraph("The following deliverables are provided upon completion:")
    for d in eng["deliverables"]:
        doc.add_paragraph(d, style='List Bullet')

    # 5. Pricing
    doc.add_heading("5. Pricing", level=1)
    price_table = doc.add_table(rows=4, cols=3)
    price_data = [
        ("Item", "Rate", "Total"),
        (f"Professional services ({estimated_days} days)", f"{currency} {day_rate:,}/day", f"{currency} {total_cost:,}"),
        ("Travel & expenses", "—", "Billed at cost"),
        ("Total", "", f"{currency} {total_cost:,}"),
    ]
    for i, (a, b, c) in enumerate(price_data):
        for j, val in enumerate([a, b, c]):
            cell = price_table.rows[i].cells[j]
            if i == 0:
                _shade_cell(cell, "173054")
                _set_cell(cell, val, bold=True, white=True, size=10)
            elif i == 3:
                _shade_cell(cell, "F1F5F9")
                _set_cell(cell, val, bold=True, size=10)
            else:
                _set_cell(cell, val, size=10)

    doc.add_paragraph()
    doc.add_paragraph(
        "Payment terms: 50% upon signature, 50% upon delivery of final report. "
        f"Prices in {currency}. Valid for 30 days from proposal date."
    )

    # 6. Timeline
    doc.add_heading("6. Timeline", level=1)
    doc.add_paragraph(
        f"Estimated duration: {estimated_days} business days from kickoff. "
        "Actual duration may vary based on scope complexity and target availability. "
        "A detailed schedule will be agreed upon during the scoping call."
    )

    # 7. Acceptance
    doc.add_heading("7. Acceptance", level=1)
    doc.add_paragraph(
        "By signing below, the client authorizes Cyberian Defenses to conduct "
        "the penetration test as described in this proposal, in accordance with "
        "the stated rules of engagement and scope."
    )

    doc.add_paragraph()  # spacer
    sign_table = doc.add_table(rows=2, cols=2)
    sign_data = [
        ("Client Signature", "Cyberian Defenses"),
        ("Date: _______________", "Date: _______________"),
    ]
    for i, (a, b) in enumerate(sign_data):
        _set_cell(sign_table.rows[i].cells[0], a, size=10)
        _set_cell(sign_table.rows[i].cells[1], b, size=10)

    # Footer
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(
        f"Generated by Chimeras v3.2 — {tester}\n"
        f"{datetime.utcnow().isoformat()}"
    )
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(0x6b, 0x72, 0x80)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        logger.info(f"Proposal generated: {output_path.name}")
        return True
    except Exception as e:
        logger.error(f"Proposal generation failed: {e}")
        raise


def generate_proposal_pdf(
    output_path: Path,
    **kwargs,
) -> bool:
    """Generate proposal as PDF using WeasyPrint.

    Same params as generate_proposal(). Generates DOCX first, then
    converts via a simple HTML intermediate.
    """
    if not WEASYPRINT_OK:
        logger.warning("WeasyPrint not installed — PDF proposal skipped")
        return False

    # Generate HTML directly
    client_name = kwargs.get("client_name", "")
    targets = kwargs.get("targets", [])
    engagement_type = kwargs.get("engagement_type", "external_pentest")
    day_rate = kwargs.get("day_rate", 500)
    estimated_days = kwargs.get("estimated_days", 5)
    currency = kwargs.get("currency", "USD")
    roe = kwargs.get("roe", "")
    tester = kwargs.get("tester", "Cyberian Defenses")

    eng = _ENGAGEMENT_TYPES.get(engagement_type, _ENGAGEMENT_TYPES["external_pentest"])
    total_cost = day_rate * estimated_days

    if not roe:
        roe = (
            "Authorized penetration test. No denial of service. "
            "No data destruction. No data exfiltration without explicit approval. "
            "Exploitation phase gated on human approval."
        )

    targets_html = "".join(f"<li>{t}</li>" for t in targets) if targets else "<li>To be determined during scoping call.</li>"
    phases_html = "".join(f"<li>{p}</li>" for p in eng["phases"])
    deliverables_html = "".join(f"<li>{d}</li>" for d in eng["deliverables"])

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body {{ font-family: Helvetica, Arial, sans-serif; font-size: 11pt; color: #1f2937; line-height: 1.6; }}
h1 {{ font-size: 20pt; color: #173054; border-bottom: 2px solid #173054; padding-bottom: 4px; }}
h3 {{ font-size: 12pt; color: #334155; margin-top: 1em; }}
table {{ width: 100%; border-collapse: collapse; margin: 1em 0; }}
th {{ background: #173054; color: white; padding: 8px; text-align: left; font-size: 10pt; }}
td {{ padding: 6px 8px; border: 1px solid #d1d5db; font-size: 10pt; }}
.center {{ text-align: center; }}
.muted {{ color: #6b7280; font-size: 10pt; }}
</style></head>
<body>
<h1 class="center">Proposal: {eng['title']}</h1>
<p class="center muted">Confidential — For Client Review</p>
<table>
<tr><th>Client</th><td>{client_name or 'N/A'}</td></tr>
<tr><th>Engagement</th><td>{eng['title']}</td></tr>
<tr><th>Tester</th><td>{tester}</td></tr>
<tr><th>Date</th><td>{datetime.utcnow().strftime('%Y-%m-%d')}</td></tr>
<tr><th>Duration</th><td>{estimated_days} days</td></tr>
<tr><th>Day Rate</th><td>{currency} {day_rate:,}</td></tr>
<tr><th>Total Cost</th><td><strong>{currency} {total_cost:,}</strong></td></tr>
</table>

<h1>1. Scope</h1>
<p>The following targets are in scope:</p>
<ul>{targets_html}</ul>
<h3>Out of Scope</h3>
<p>Any systems not explicitly listed above are out of scope. Scope expansion requires written approval.</p>

<h1>2. Rules of Engagement</h1>
<p>{roe}</p>

<h1>3. Methodology</h1>
<ol>{phases_html}</ol>

<h1>4. Deliverables</h1>
<ul>{deliverables_html}</ul>

<h1>5. Pricing</h1>
<table>
<tr><th>Item</th><th>Rate</th><th>Total</th></tr>
<tr><td>Professional services ({estimated_days} days)</td><td>{currency} {day_rate:,}/day</td><td>{currency} {total_cost:,}</td></tr>
<tr><td><strong>Total</strong></td><td></td><td><strong>{currency} {total_cost:,}</strong></td></tr>
</table>
<p class="muted">50% upon signature, 50% upon delivery. Prices in {currency}. Valid 30 days.</p>

<h1>6. Acceptance</h1>
<p>By signing below, the client authorizes the penetration test as described above.</p>
<table>
<tr><td>Client Signature: _______________</td><td>{tester}: _______________</td></tr>
<tr><td>Date: _______________</td><td>Date: _______________</td></tr>
</table>

<p class="center muted">Generated by Chimeras v3.2 — {tester}<br>{datetime.utcnow().isoformat()}</p>
</body></html>"""

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc = HTML(string=html)
        doc.write_pdf(str(output_path))
        logger.info(f"Proposal PDF generated: {output_path.name}")
        return True
    except Exception as e:
        logger.error(f"Proposal PDF failed: {e}")
        raise