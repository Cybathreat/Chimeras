"""
Chimeras v3.2 — Static Client Portal

Generates a self-contained, single-file HTML portal from engagement findings.
No server, no cloud, no dependencies. Client opens it in a browser — interactive
findings table, severity filters, evidence viewer, compliance matrix, remediation
status. Consultant zips it and sends. Replaces Strix's run viewer without infrastructure.

Sovereign procurement compliant: data never leaves the client's infrastructure.

Integration:
    Bookkeeper calls export_portal() at report time.
    Output: report/client_portal.html (single file, ~50-200KB)
"""

import json
import logging
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

_PORTAL_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Segoe UI', 'Inter', 'Helvetica Neue', sans-serif;
    background: #0f172a; color: #e2e8f0; line-height: 1.6;
}
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }
.header {
    background: linear-gradient(135deg, #173054, #1e3a5f);
    padding: 30px 40px; border-radius: 8px; margin-bottom: 24px;
    border: 1px solid #225777;
}
.header h1 { font-size: 24px; color: #f8fafc; margin-bottom: 8px; }
.header .meta { font-size: 13px; color: #94a3b8; }
.header .meta span { margin-right: 20px; }
.tabs {
    display: flex; gap: 4px; margin-bottom: 20px;
    border-bottom: 2px solid #1e3a5f;
}
.tab {
    padding: 10px 20px; cursor: pointer; border-radius: 6px 6px 0 0;
    background: #1e293b; color: #94a3b8; font-size: 13px; font-weight: 600;
    border: none; transition: all 0.2s;
}
.tab:hover { background: #334155; color: #e2e8f0; }
.tab.active { background: #173054; color: #f8fafc; border-bottom: 2px solid #10b981; }
.tab-content { display: none; }
.tab-content.active { display: block; }

/* Filters */
.filters { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.filter-group { display: flex; gap: 6px; align-items: center; }
.filter-label { font-size: 12px; color: #64748b; font-weight: 600; text-transform: uppercase; }
.filter-btn {
    padding: 4px 12px; border-radius: 4px; border: 1px solid #334155;
    background: #1e293b; color: #94a3b8; font-size: 12px; cursor: pointer;
    transition: all 0.15s;
}
.filter-btn:hover { border-color: #475569; color: #e2e8f0; }
.filter-btn.active { border-color: #10b981; color: #10b981; background: rgba(16,185,129,0.1); }

/* Findings table */
.findings-table { width: 100%; border-collapse: collapse; }
.findings-table th {
    background: #1e293b; padding: 10px 12px; text-align: left;
    font-size: 12px; font-weight: 600; color: #94a3b8;
    border-bottom: 2px solid #334155; text-transform: uppercase; letter-spacing: 0.5px;
}
.findings-table td {
    padding: 10px 12px; border-bottom: 1px solid #1e293b; font-size: 13px;
}
.findings-table tr:hover { background: #1e293b; }
.findings-table tr { cursor: pointer; transition: background 0.1s; }
.severity-badge {
    display: inline-block; padding: 2px 10px; border-radius: 3px;
    font-size: 11px; font-weight: 700; text-transform: uppercase;
}
.sev-critical { background: #7f1d1d; color: #fef2f2; }
.sev-high { background: #dc2626; color: #fef2f2; }
.sev-medium { background: #f59e0b; color: #1c1917; }
.sev-low { background: #3b82f6; color: #eff6ff; }
.sev-info { background: #6b7280; color: #f9fafb; }

/* Finding detail panel */
.detail-overlay {
    display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.7); z-index: 100; justify-content: center; align-items: center;
}
.detail-overlay.show { display: flex; }
.detail-panel {
    background: #1e293b; border: 1px solid #334155; border-radius: 8px;
    width: 90%; max-width: 700px; max-height: 85vh; overflow-y: auto; padding: 24px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}
.detail-panel h2 { color: #f8fafc; margin-bottom: 12px; font-size: 18px; }
.detail-section { margin-bottom: 16px; }
.detail-section h3 {
    font-size: 12px; color: #10b981; text-transform: uppercase;
    letter-spacing: 1px; margin-bottom: 6px;
}
.detail-section p { font-size: 13px; color: #cbd5e1; }
.detail-section pre {
    background: #0f172a; padding: 12px; border-radius: 4px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 12px; color: #94a3b8; overflow-x: auto; white-space: pre-wrap;
}
.close-btn {
    float: right; background: #334155; border: none; color: #94a3b8;
    padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 13px;
}
.close-btn:hover { background: #475569; color: #e2e8f0; }

/* Summary cards */
.summary-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 24px; }
.card {
    background: #1e293b; padding: 16px; border-radius: 6px;
    border: 1px solid #334155; text-align: center;
}
.card .count { font-size: 28px; font-weight: 700; }
.card .label { font-size: 12px; color: #64748b; text-transform: uppercase; }
.card.critical .count { color: #ef4444; }
.card.high .count { color: #f87171; }
.card.medium .count { color: #fbbf24; }
.card.low .count { color: #60a5fa; }
.card.info .count { color: #9ca3af; }
.card.total .count { color: #10b981; }

/* Compliance table */
.compliance-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.compliance-table th {
    background: #1e293b; padding: 8px 12px; text-align: left; font-size: 12px;
    color: #94a3b8; border-bottom: 1px solid #334155;
}
.compliance-table td { padding: 8px 12px; border-bottom: 1px solid #1e293b; font-size: 13px; }

/* Evidence */
.evidence-section { margin-top: 12px; }
.evidence-hash {
    font-family: monospace; font-size: 11px; color: #64748b;
    background: #0f172a; padding: 2px 6px; border-radius: 3px;
}

.footer {
    margin-top: 30px; padding: 16px; text-align: center;
    font-size: 11px; color: #475569; border-top: 1px solid #1e293b;
}
"""


def _sev_class(severity: str) -> str:
    return f"sev-{(severity or 'info').lower()}"


def export_portal(
    output_path: Path,
    engagement_name: str = "N/A",
    client_name: str = "",
    findings: Optional[List[Dict[str, Any]]] = None,
    compliance_data: Optional[Dict[str, Any]] = None,
    evidence_summary: Optional[Dict[str, Any]] = None,
    coverage_summary: Optional[Dict[str, Any]] = None,
    narrative_md: str = "",
) -> bool:
    """Export a self-contained HTML client portal.

    Single file, no external dependencies, no server. Client opens in browser.
    Interactive findings table with severity filters, finding detail panel,
    compliance matrix, evidence hashes, coverage summary.

    Args:
        output_path: Where to write the HTML file.
        findings: List of finding dicts (from FindingsStore).
        compliance_data: Compliance mapping summary (from ComplianceMapper).
        evidence_summary: Evidence locker summary (from EvidenceLocker.summary()).
        coverage_summary: Coverage tracker summary (from CoverageTracker.summary()).
        narrative_md: LLM narrative markdown (for the overview tab).

    Returns:
        True if portal was written.
    """
    findings = findings or []
    compliance_data = compliance_data or {}
    evidence_summary = evidence_summary or {}
    coverage_summary = coverage_summary or {}

    # Severity counts
    sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        s = (f.get("severity") or "info").lower()
        sev_counts[s] = sev_counts.get(s, 0) + 1
    total = len(findings)

    # Build findings JSON for embedding
    findings_json = json.dumps(findings, indent=2)

    # Build compliance rows
    comp_rows = ""
    per_finding = compliance_data.get("per_finding", {})
    for fid, controls in sorted(per_finding.items()):
        for c in controls:
            parts = c.split(": ", 1)
            fw = parts[0] if len(parts) > 0 else ""
            ctrl_detail = parts[1] if len(parts) > 1 else c
            comp_rows += f'<tr><td><strong>{fid}</strong></td><td>{fw}</td><td>{ctrl_detail}</td></tr>'

    # Summary cards HTML
    cards = ""
    for sev, count in sev_counts.items():
        cards += f'<div class="card {sev}"><div class="count">{count}</div><div class="label">{sev}</div></div>'
    cards += f'<div class="card total"><div class="count">{total}</div><div class="label">Total</div></div>'

    # Evidence section
    evidence_html = ""
    if evidence_summary:
        evidence_html = f"""
        <h3>Evidence Chain Summary</h3>
        <p><strong>Artifacts:</strong> {evidence_summary.get('total', 0)} |
        <strong>Linked:</strong> {evidence_summary.get('linked', 0)} |
        <strong>Verified:</strong> {'✅' if evidence_summary.get('verified') else '❌'} |
        <strong>Manifest hash:</strong> <code>{evidence_summary.get('manifest_hash', 'N/A')}</code></p>
        """

    # Coverage section
    coverage_html = ""
    if coverage_summary and coverage_summary.get("total_checks", 0) > 0:
        coverage_html = f"""
        <h3>Coverage Summary</h3>
        <p><strong>Checks performed:</strong> {coverage_summary.get('total_checks', 0)} |
        <strong>Targets tested:</strong> {coverage_summary.get('unique_targets', 0)} |
        <strong>Tools used:</strong> {coverage_summary.get('unique_tools', 0)}</p>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pentest Portal — {engagement_name}</title>
<style>{_PORTAL_CSS}</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Penetration Test Portal</h1>
        <div class="meta">
            <span>📋 <strong>Engagement:</strong> {engagement_name}</span>
            <span>🏢 <strong>Client:</strong> {client_name or 'N/A'}</span>
            <span>📅 <strong>Date:</strong> {datetime.utcnow().strftime('%Y-%m-%d')}</span>
            <span>🔍 <strong>Tester:</strong> Chimeras AI Pentest Swarm</span>
        </div>
    </div>

    <div class="tabs">
        <button class="tab active" onclick="showTab('findings')">Findings</button>
        <button class="tab" onclick="showTab('compliance')">Compliance</button>
        <button class="tab" onclick="showTab('evidence')">Evidence & Coverage</button>
        <button class="tab" onclick="showTab('overview')">Overview</button>
    </div>

    <!-- Findings Tab -->
    <div id="tab-findings" class="tab-content active">
        <div class="summary-cards">{cards}</div>

        <div class="filters">
            <div class="filter-group">
                <span class="filter-label">Severity:</span>
                <button class="filter-btn active" onclick="filterFindings('all', this)">All</button>
                <button class="filter-btn" onclick="filterFindings('critical', this)">Critical</button>
                <button class="filter-btn" onclick="filterFindings('high', this)">High</button>
                <button class="filter-btn" onclick="filterFindings('medium', this)">Medium</button>
                <button class="filter-btn" onclick="filterFindings('low', this)">Low</button>
                <button class="filter-btn" onclick="filterFindings('info', this)">Info</button>
            </div>
        </div>

        <table class="findings-table" id="findings-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Finding</th>
                    <th>Severity</th>
                    <th>CVSS</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody id="findings-body"></tbody>
        </table>
    </div>

    <!-- Compliance Tab -->
    <div id="tab-compliance" class="tab-content">
        <h2 style="color:#f8fafc;margin-bottom:12px;">Compliance Mapping</h2>
        <p style="color:#94a3b8;margin-bottom:16px;">Findings mapped to OWASP ASVS 4.0, PCI DSS 4.0, ISO 27001:2022, NIST 800-53 Rev 5</p>
        <table class="compliance-table">
            <thead><tr><th>Finding</th><th>Framework</th><th>Control</th></tr></thead>
            <tbody>{comp_rows if comp_rows else '<tr><td colspan="3" style="color:#64748b;text-align:center;padding:20px;">No compliance mappings available</td></tr>'}</tbody>
        </table>
    </div>

    <!-- Evidence & Coverage Tab -->
    <div id="tab-evidence" class="tab-content">
        <h2 style="color:#f8fafc;margin-bottom:12px;">Evidence Chain & Coverage</h2>
        {evidence_html}
        {coverage_html}
        <div style="margin-top:20px;padding:16px;background:#1e293b;border-radius:6px;border:1px solid #334155;">
            <h3 style="color:#10b981;margin-bottom:8px;">Tamper Detection</h3>
            <p style="color:#94a3b8;font-size:13px;">All evidence artifacts are SHA-256 hashed. The manifest is itself hashed to detect post-engagement tampering. Run <code style="background:#0f172a;padding:2px 6px;border-radius:3px;">chimeras verify</code> to validate evidence integrity.</p>
        </div>
    </div>

    <!-- Overview Tab -->
    <div id="tab-overview" class="tab-content">
        <h2 style="color:#f8fafc;margin-bottom:12px;">Engagement Overview</h2>
        <div style="background:#1e293b;padding:20px;border-radius:6px;border:1px solid #334155;">
            <pre style="color:#cbd5e1;font-size:13px;white-space:pre-wrap;">{narrative_md[:5000] if narrative_md else 'No narrative available.'}</pre>
        </div>
    </div>

    <div class="footer">
        Generated by Chimeras v3.2 — Cyberian Defenses<br>
        {datetime.utcnow().isoformat()} | Self-contained portal — no server, no cloud, zero data egress
    </div>
</div>

<!-- Finding Detail Overlay -->
<div class="detail-overlay" id="detail-overlay" onclick="closeDetail(event)">
    <div class="detail-panel" id="detail-panel" onclick="event.stopPropagation()">
        <button class="close-btn" onclick="closeDetail()">✕ Close</button>
        <div id="detail-content"></div>
    </div>
</div>

<script>
const findings = {findings_json};

function showTab(tabName) {{
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + tabName).classList.add('active');
    event.target.classList.add('active');
}}

function filterFindings(severity, btn) {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderFindings(severity);
}}

function renderFindings(filter = 'all') {{
    const tbody = document.getElementById('findings-body');
    tbody.innerHTML = '';
    findings.forEach((f, i) => {{
        const sev = (f.severity || 'info').toLowerCase();
        if (filter !== 'all' && sev !== filter) return;
        const row = document.createElement('tr');
        row.onclick = () => showDetail(i);
        row.innerHTML = `
            <td><strong>${{f.id || ''}}</strong></td>
            <td>${{f.title || ''}}</td>
            <td><span class="severity-badge {_sev_class('${{sev}}')}" style="padding:2px 10px;border-radius:3px;font-size:11px;font-weight:700;text-transform:uppercase;">${{sev}}</span></td>
            <td>${{f.cvss || 'N/A'}}</td>
            <td>${{f.status || ''}}</td>
        `;
        // Apply severity badge class dynamically
        const badge = row.querySelector('.severity-badge');
        if (badge) {{
            const classes = {{'critical':'sev-critical','high':'sev-high','medium':'sev-medium','low':'sev-low','info':'sev-info'}};
            badge.className = 'severity-badge ' + (classes[sev] || 'sev-info');
        }}
        tbody.appendChild(row);
    }});
}}

function showDetail(index) {{
    const f = findings[index];
    let html = `<h2>${{f.id || ''}}: ${{f.title || 'Untitled'}}</h2>`;
    html += `<p style="color:#94a3b8;margin-bottom:16px;"><strong>Severity:</strong> ${{f.severity || 'N/A'}} | <strong>CVSS:</strong> ${{f.cvss || 'N/A'}} | <strong>Status:</strong> ${{f.status || 'N/A'}}</p>`;

    const sections = [
        ['Description', f.description],
        ['Risks', f.risks],
        ['Attack Vectors', f.attack_vectors],
        ['Proof of Concept', f.poc],
        ['Proof of Existence', f.proof_of_existence],
        ['Remediation', f.remediation],
    ];

    sections.forEach(([title, content]) => {{
        if (content && content !== 'N/A') {{
            const isPre = title === 'Proof of Existence' || title === 'Proof of Concept' || title === 'Attack Vectors';
            html += `<div class="detail-section"><h3>${{title}}</h3>`;
            if (isPre) {{
                html += `<pre>${{content}}</pre>`;
            }} else {{
                html += `<p>${{content}}</p>`;
            }}
            html += `</div>`;
        }}
    }});

    // Evidence hash
    if (f.evidence_hash) {{
        html += `<div class="detail-section"><h3>Evidence Hash (SHA-256)</h3><p><code class="evidence-hash">${{f.evidence_hash}}</code></p></div>`;
    }}

    // Compliance
    const comp = f.compliance || {{}};
    const compMap = comp.compliance || {{}};
    if (Object.keys(compMap).length > 0) {{
        html += `<div class="detail-section"><h3>Compliance Mapping</h3><table class="compliance-table"><tr><th>Framework</th><th>Control ID</th><th>Name</th></tr>`;
        Object.entries(compMap).forEach(([fw, controls]) => {{
            controls.forEach(c => {{
                html += `<tr><td><strong>${{fw}}</strong></td><td>${{c.control_id}}</td><td>${{c.control_name}}</td></tr>`;
            }});
        }});
        html += `</table></div>`;
    }}

    document.getElementById('detail-content').innerHTML = html;
    document.getElementById('detail-overlay').classList.add('show');
}}

function closeDetail(event) {{
    if (event && event.target.id !== 'detail-overlay' && event.type !== 'click') return;
    document.getElementById('detail-overlay').classList.remove('show');
}}

// Initialize
renderFindings();
</script>
</body>
</html>"""

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info(f"Client portal exported: {len(findings)} findings → {output_path.name}")
        return True
    except Exception as e:
        logger.error(f"Portal export failed: {e}")
        raise