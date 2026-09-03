"""
Chimeras v3.1 — PDF Report Exporter

Renders the structured pentest report to PDF using WeasyPrint.
Takes the same data as core/report_template.py and produces a
client-ready PDF with Cyberian Defenses branding, CVSS color-coded
finding tables, and professional typography.

Integration:
    Bookkeeper calls export_pdf() at report time alongside
    structured_report.md and findings.sarif.
    Output: pentest_report.pdf in the engagement report directory.
"""

import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    HTML = None
    CSS = None

# ─── Severity color mapping (CVSS-aware) ──────────────────────────────

_SEVERITY_COLORS = {
    "critical": {"bg": "#7f1d1d", "text": "#ffffff", "border": "#991b1b"},
    "high":     {"bg": "#dc2626", "text": "#ffffff", "border": "#b91c1c"},
    "medium":   {"bg": "#f59e0b", "text": "#000000", "border": "#d97706"},
    "low":      {"bg": "#3b82f6", "text": "#ffffff", "border": "#2563eb"},
    "info":     {"bg": "#6b7280", "text": "#ffffff", "border": "#4b5563"},
}

_DEFAULT_SEVERITY = {"bg": "#6b7280", "text": "#ffffff", "border": "#4b5563"}


def _severity_style(severity: str) -> Dict[str, str]:
    """Return color dict for a severity level."""
    return _SEVERITY_COLORS.get((severity or "").lower(), _DEFAULT_SEVERITY)


def _escape_html(text: str) -> str:
    """Escape HTML special characters in text content."""
    if not text:
        return ""
    text = str(text)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def _md_inline_to_html(text: str) -> str:
    """Convert minimal markdown inline formatting to HTML.

    Handles: **bold**, *italic*, `code`, [links](url).
    Everything else is escaped.
    """
    if not text:
        return ""
    text = _escape_html(text)

    # Bold: **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic: *text* (but not ** which is bold)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    # Inline code: `text`
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    # Links: [text](url)
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)

    return text


def _md_block_to_html(md: str) -> str:
    """Convert a markdown text block to simplified HTML for PDF rendering.

    Handles headings (##, ###), bullet lists (-), numbered lists (1.),
    code blocks (```), tables (|), and paragraphs.
    """
    if not md:
        return ""
    lines = md.strip().split("\n")
    html_parts: List[str] = []
    in_code_block = False
    in_table = False
    in_list = False
    list_type = "ul"
    table_header_done = False

    for line in lines:
        stripped = line.strip()

        # Code block fences
        if stripped.startswith("```"):
            if in_code_block:
                html_parts.append("</code></pre>")
                in_code_block = False
            else:
                lang = stripped[3:].strip()
                html_parts.append(f"<pre><code>")
                in_code_block = True
            continue

        if in_code_block:
            html_parts.append(_escape_html(line))
            continue

        # Table detection
        if stripped.startswith("|") and stripped.endswith("|"):
            if not in_table:
                in_table = True
                table_header_done = False
                html_parts.append("<table class='md-table'>")
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            # Skip separator rows (|---|---|)
            if all(re.match(r'^[-:]+$', c) for c in cells):
                table_header_done = True
                continue
            if not table_header_done:
                html_parts.append("<tr>" + "".join(f"<th>{_md_inline_to_html(c)}</th>" for c in cells) + "</tr>")
                table_header_done = True
            else:
                html_parts.append("<tr>" + "".join(f"<td>{_md_inline_to_html(c)}</td>" for c in cells) + "</tr>")
            continue
        elif in_table:
            html_parts.append("</table>")
            in_table = False

        # Headings
        if stripped.startswith("### "):
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            html_parts.append(f"<h3>{_md_inline_to_html(stripped[4:])}</h3>")
            continue
        if stripped.startswith("## "):
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            html_parts.append(f"<h2>{_md_inline_to_html(stripped[3:])}</h2>")
            continue
        if stripped.startswith("# "):
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            html_parts.append(f"<h1>{_md_inline_to_html(stripped[2:])}</h1>")
            continue

        # Horizontal rule
        if stripped in ("---", "***", "___"):
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            html_parts.append("<hr/>")
            continue

        # Bullet list
        if re.match(r'^[-*]\s+', stripped):
            if not in_list or list_type != "ul":
                if in_list:
                    html_parts.append(f"</{list_type}>")
                html_parts.append("<ul>")
                in_list = True
                list_type = "ul"
            content = re.sub(r'^[-*]\s+', '', stripped)
            html_parts.append(f"<li>{_md_inline_to_html(content)}</li>")
            continue

        # Numbered list
        if re.match(r'^\d+\.\s+', stripped):
            if not in_list or list_type != "ol":
                if in_list:
                    html_parts.append(f"</{list_type}>")
                html_parts.append("<ol>")
                in_list = True
                list_type = "ol"
            content = re.sub(r'^\d+\.\s+', '', stripped)
            html_parts.append(f"<li>{_md_inline_to_html(content)}</li>")
            continue

        # Empty line
        if not stripped:
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            html_parts.append("")
            continue

        # Regular paragraph
        if in_list:
            html_parts.append(f"</{list_type}>")
            in_list = False
        html_parts.append(f"<p>{_md_inline_to_html(stripped)}</p>")

    if in_code_block:
        html_parts.append("</code></pre>")
    if in_table:
        html_parts.append("</table>")
    if in_list:
        html_parts.append(f"</{list_type}>")

    return "\n".join(html_parts)


# ─── HTML report template ─────────────────────────────────────────────

_PDF_CSS = """
@page {
    size: A4;
    margin: 2cm 1.8cm 2.5cm 1.8cm;
    @bottom-center {
        content: "Chimeras Autonomous AI Pentest Swarm — Cyberian Defenses";
        font-size: 8pt;
        color: #6b7280;
    }
    @bottom-right {
        content: counter(page) " / " counter(pages);
        font-size: 8pt;
        color: #6b7280;
    }
}

@page :first {
    margin-top: 0;
    @bottom-center { content: ""; }
    @bottom-right { content: ""; }
}

body {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.5;
    color: #1f2937;
}

/* ─── Cover page ─── */
.cover {
    page-break-after: always;
    text-align: center;
    padding-top: 6cm;
    background: #0f172a;
    color: #f8fafc;
    margin: -2cm -1.8cm 0 -1.8cm;
    padding-left: 1.8cm;
    padding-right: 1.8cm;
    padding-bottom: 2cm;
    min-height: 100vh;
}
.cover h1 {
    font-size: 28pt;
    color: #f8fafc;
    margin-bottom: 0.5cm;
    border: none;
}
.cover .subtitle {
    font-size: 14pt;
    color: #94a3b8;
    margin-bottom: 3cm;
}
.cover .meta {
    font-size: 11pt;
    color: #cbd5e1;
    text-align: left;
    margin: 0 2cm;
    line-height: 2;
}
.cover .meta strong {
    color: #f8fafc;
    display: inline-block;
    width: 4cm;
}
.cover .branding {
    margin-top: 4cm;
    font-size: 10pt;
    color: #64748b;
}

/* ─── Headings ─── */
h1 {
    font-size: 18pt;
    color: #0f172a;
    border-bottom: 2px solid #0f172a;
    padding-bottom: 4px;
    margin-top: 1.5em;
    page-break-after: avoid;
}
h2 {
    font-size: 14pt;
    color: #1e3a5f;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 3px;
    margin-top: 1.2em;
    page-break-after: avoid;
}
h3 {
    font-size: 12pt;
    color: #334155;
    margin-top: 1em;
    page-break-after: avoid;
}

/* ─── Tables ─── */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.8em 0;
    font-size: 9pt;
    page-break-inside: auto;
}
th {
    background: #1e3a5f;
    color: #ffffff;
    text-align: left;
    padding: 6px 8px;
    border: 1px solid #1e3a5f;
    font-weight: 600;
}
td {
    padding: 5px 8px;
    border: 1px solid #d1d5db;
    vertical-align: top;
}
tr:nth-child(even) td {
    background: #f8fafc;
}
tr {
    page-break-inside: avoid;
}
table.md-table th {
    background: #475569;
}
.severity-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 3px;
    font-weight: 600;
    font-size: 8.5pt;
    text-transform: uppercase;
}

/* ─── Finding cards ─── */
.finding-card {
    page-break-inside: avoid;
    margin: 1em 0;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
    overflow: hidden;
}
.finding-header {
    padding: 8px 12px;
    color: #ffffff;
    font-weight: 600;
    font-size: 11pt;
    display: flex;
    justify-content: space-between;
}
.finding-body {
    padding: 10px 14px;
}
.finding-body h3 {
    margin-top: 0.5em;
    color: #475569;
    font-size: 10pt;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.finding-body pre {
    background: #f1f5f9;
    padding: 8px;
    border-radius: 3px;
    font-size: 8.5pt;
    overflow-x: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
}
code {
    background: #f1f5f9;
    padding: 1px 3px;
    border-radius: 2px;
    font-size: 9pt;
}
pre code {
    background: none;
    padding: 0;
}

/* ─── Misc ─── */
hr {
    border: none;
    border-top: 1px solid #e5e7eb;
    margin: 1.5em 0;
}
p { margin: 0.4em 0; }
ul, ol { margin: 0.4em 0 0.4em 1.2em; }
li { margin: 0.2em 0; }
a { color: #2563eb; text-decoration: none; }

.warning {
    background: #fef3c7;
    border-left: 4px solid #f59e0b;
    padding: 8px 12px;
    margin: 0.8em 0;
    font-size: 9.5pt;
}

.toc {
    page-break-after: always;
}
.toc h2 {
    border-bottom: 2px solid #0f172a;
}
.toc-entry {
    display: flex;
    justify-content: space-between;
    border-bottom: 1px dotted #d1d5db;
    padding: 3px 0;
    font-size: 10pt;
}
.toc-entry .section {
    color: #1e3a5f;
}
"""


def _build_finding_card(finding: Dict[str, Any], index: int) -> str:
    """Build an HTML finding card for a single finding."""
    severity = (finding.get("severity") or "info").lower()
    colors = _severity_style(severity)
    fid = finding.get("id", f"FILL-{index:03d}")
    title = _escape_html(finding.get("title", "Untitled Finding"))
    cvss = finding.get("cvss", "N/A")
    status = _escape_html(finding.get("status", "Confirmed"))

    # Evidence hash (if present)
    evidence_hash = finding.get("evidence_hash")
    evidence_section = ""
    if evidence_hash:
        evidence_section = (
            f'<h3>Evidence Hash (SHA-256)</h3>'
            f'<pre><code>{_escape_html(evidence_hash)}</code></pre>'
        )

    # Compliance mappings (if present)
    compliance = finding.get("compliance", {})
    compliance_section = ""
    compliance_mappings = compliance.get("compliance", {}) if compliance else {}
    if compliance_mappings:
        compliance_lines = []
        for fw_name, controls in compliance_mappings.items():
            for ctrl in controls:
                compliance_lines.append(
                    f"<tr>"
                    f"<td><strong>{_escape_html(fw_name)}</strong></td>"
                    f"<td>{_escape_html(ctrl['control_id'])}</td>"
                    f"<td>{_escape_html(ctrl['control_name'])}</td>"
                    f"</tr>"
                )
        compliance_section = (
            f'<h3>Compliance Mapping</h3>'
            f'<table class="md-table">'
            f'<tr><th>Framework</th><th>Control ID</th><th>Control Name</th></tr>'
            f"{''.join(compliance_lines)}"
            f'</table>'
        )

    card = f"""
    <div class="finding-card">
      <div class="finding-header" style="background:{colors['bg']};">
        <span>{fid}: {title}</span>
        <span>CVSS {cvss} | {status}</span>
      </div>
      <div class="finding-body">
        <h3>Description</h3>
        <p>{_md_inline_to_html(finding.get("description", "N/A"))}</p>

        <h3>Risks</h3>
        <p>{_md_inline_to_html(finding.get("risks", "N/A"))}</p>

        <h3>Attack Vectors</h3>
        {_md_block_to_html(finding.get("attack_vectors", "N/A"))}

        <h3>Proof of Concept</h3>
        {_md_block_to_html(finding.get("poc", "N/A"))}

        <h3>Proof of Existence</h3>
        <pre><code>{_escape_html(finding.get("proof_of_existence", "N/A"))}</code></pre>

        {evidence_section}

        {compliance_section}

        <h3>Remediation</h3>
        <p>{_md_inline_to_html(finding.get("remediation", "N/A"))}</p>
      </div>
    </div>
    """
    return card


def _build_findings_table(findings: List[Dict[str, Any]]) -> str:
    """Build the findings summary table HTML."""
    if not findings:
        return "<p><em>No findings recorded.</em></p>"

    rows = []
    for i, f in enumerate(findings):
        severity = (f.get("severity") or "info").lower()
        colors = _severity_style(severity)
        badge = (
            f'<span class="severity-badge" '
            f'style="background:{colors["bg"]};color:{colors["text"]};">'
            f'{_escape_html(f.get("severity", "N/A"))}</span>'
        )
        fid = f.get("id", f"FILL-{i:03d}")
        rows.append(
            f"<tr>"
            f"<td><strong>{_escape_html(fid)}</strong></td>"
            f"<td>{_escape_html(f.get('title', ''))}</td>"
            f"<td>{badge}</td>"
            f"<td>{_escape_html(str(f.get('cvss', 'N/A')))}</td>"
            f"<td>{_escape_html(f.get('status', ''))}</td>"
            f"</tr>"
        )

    return f"""
    <table>
      <thead>
        <tr>
          <th style="width:8%;">ID</th>
          <th style="width:45%;">Finding</th>
          <th style="width:15%;">Severity</th>
          <th style="width:12%;">CVSS</th>
          <th style="width:20%;">Status</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
    """


def _build_cover_page(
    engagement_name: str,
    client_name: str,
    report_date: str,
    targets: List[str],
    finding_count: int,
    critical_count: int,
) -> str:
    """Build the cover page HTML."""
    target_list = ", ".join(targets) if targets else "N/A"
    risk_summary = (
        f"{critical_count} critical, "
        f"{finding_count} total findings"
    )

    return f"""
    <div class="cover">
      <h1>Penetration Test Report</h1>
      <div class="subtitle">Confidential — Authorized Security Assessment</div>
      <div class="meta">
        <p><strong>Engagement:</strong> {_escape_html(engagement_name)}</p>
        <p><strong>Client:</strong> {_escape_html(client_name or "N/A")}</p>
        <p><strong>Date:</strong> {_escape_html(report_date)}</p>
        <p><strong>Targets:</strong> {_escape_html(target_list)}</p>
        <p><strong>Findings:</strong> {_escape_html(risk_summary)}</p>
        <p><strong>Tester:</strong> Chimeras Autonomous AI Pentest Swarm</p>
      </div>
      <div class="branding">
        Generated by Chimeras v3.1 — Cyberian Defenses<br/>
        {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
      </div>
    </div>
    """


def _build_toc(findings: List[Dict[str, Any]]) -> str:
    """Build a table of contents for the findings section."""
    if not findings:
        return ""

    entries = []
    for i, f in enumerate(findings):
        fid = f.get("id", f"FILL-{i:03d}")
        title = f.get("title", "Untitled")
        severity = (f.get("severity") or "info").lower()
        colors = _severity_style(severity)
        badge = (
            f'<span class="severity-badge" '
            f'style="background:{colors["bg"]};color:{colors["text"]};">'
            f'{_escape_html(f.get("severity", "N/A"))}</span>'
        )
        entries.append(
            f'<div class="toc-entry">'
            f'<span class="section">{_escape_html(fid)}: {_escape_html(title)}</span>'
            f'<span>{badge}</span>'
            f'</div>'
        )

    return f"""
    <div class="toc">
      <h2>Table of Contents</h2>
      {''.join(entries)}
    </div>
    """


def export_pdf(
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
) -> bool:
    """Export a professional pentest report to PDF.

    Uses the same data structure as core/report_template.py:render_report.
    Falls back gracefully if WeasyPrint is not installed (returns False).

    Args:
        output_path: Where to write the PDF file.
        See render_report() for other args.

    Returns:
        True if PDF was written, False if WeasyPrint unavailable.
    """
    if not WEASYPRINT_AVAILABLE:
        logger.warning("WeasyPrint not installed — PDF export skipped")
        return False

    targets = targets or []
    findings = findings or []
    critical_findings = critical_findings or []

    report_date = datetime.utcnow().strftime("%Y-%m-%d")

    # Count critical findings
    critical_count = sum(
        1 for f in findings
        if (f.get("severity", "") or "").lower() == "critical"
    )

    # Build the full HTML document
    html_parts = [
        "<html><head><meta charset='utf-8'></head><body>",
        # Cover page
        _build_cover_page(
            engagement_name, client_name, report_date,
            targets, len(findings), critical_count,
        ),
        # Table of contents
        _build_toc(findings),
        # Executive Summary
        "<h1>1. Executive Summary</h1>",
        _md_block_to_html(executive_summary or "N/A"),
        # Scope
        "<h1>2. Scope</h1>",
        f"<p><strong>Mission Scope:</strong> {_md_inline_to_html(mission_scope or 'N/A')}</p>",
        f"<p><strong>Internal Scope:</strong> {_md_inline_to_html(internal_scope or 'N/A')}</p>",
        f"<p><strong>Rules of Engagement:</strong> {_md_inline_to_html(roe or 'N/A')}</p>",
        "<h3>Targets Tested</h3>" if targets else "",
        "<ul>" + "".join(f"<li>{_escape_html(t)}</li>" for t in targets) + "</ul>" if targets else "<p><em>No targets listed.</em></p>",
        # Findings Summary Table
        "<h1>3. Findings Summary</h1>",
        _build_findings_table(findings),
        # Detailed Findings
        "<h1>4. Detailed Findings</h1>",
    ]

    for i, f in enumerate(findings):
        html_parts.append(_build_finding_card(f, i))

    if not findings:
        html_parts.append("<p><em>No detailed findings recorded.</em></p>")

    # Engagement Flow
    html_parts.append("<h1>5. Engagement Flow</h1>")
    html_parts.append(_md_block_to_html(engagement_flow or "N/A"))

    # Critical Findings
    html_parts.append("<h1>6. Critical Findings</h1>")
    if critical_findings:
        items = []
        for cf in critical_findings:
            bot = _escape_html(cf.get("bot", "").upper())
            cvss = _escape_html(str(cf.get("cvss", "")))
            target = _escape_html(cf.get("target", ""))
            finding = _escape_html(cf.get("finding", ""))
            items.append(f"<li><strong>[{bot}]</strong> CVSS {cvss} on {target}: {finding}</li>")
        html_parts.append(f"<ul>{''.join(items)}</ul>")
    else:
        html_parts.append("<p><em>No critical findings (CVSS >= 7.0) recorded.</em></p>")

    # Decision Audit Trail
    html_parts.append("<h1>7. Decision Audit Trail</h1>")
    html_parts.append(_md_block_to_html(decision_audit or "N/A"))

    # Cleanup Status
    html_parts.append("<h1>8. Cleanup Status</h1>")
    html_parts.append(_md_block_to_html(cleanup_status))

    # Mission Outcome
    html_parts.append("<h1>9. Mission Outcome</h1>")
    html_parts.append(_md_block_to_html(mission_outcome or "N/A"))

    # Footer
    html_parts.append(
        f"<hr/><p style='font-size:8pt;color:#6b7280;text-align:center;'>"
        f"Report generated by Chimeras v3.1 — Cyberian Defenses<br/>"
        f"{datetime.utcnow().isoformat()}</p>"
    )

    html_parts.append("</body></html>")
    full_html = "\n".join(html_parts)

    try:
        doc = HTML(string=full_html)
        css = CSS(string=_PDF_CSS)
        doc.write_pdf(str(output_path), stylesheets=[css])
        logger.info(f"PDF exported: {len(findings)} findings → {output_path.name}")
        return True
    except Exception as e:
        logger.error(f"PDF export failed: {e}")
        raise


def is_pdf_available() -> bool:
    """Check if PDF export is available (WeasyPrint installed)."""
    return WEASYPRINT_AVAILABLE