#!/usr/bin/env python3
"""Professional A4 PDF report template with charts, cover page, and TOC.

Generates HTML optimized for WeasyPrint PDF rendering.  The HTML also
renders acceptably in a browser for fallback use (Print → Save as PDF).

Usage (as a library — imported by generate_report.py):

    from pdf_template import render_pdf_html
    html_str = render_pdf_html(report_data)
"""

from __future__ import annotations

import html as html_lib
from datetime import datetime
from typing import Any

from pdf_charts import category_radar, cwv_bars, health_score_gauge, severity_donut

_CSS = r"""
@page {
    size: A4;
    margin: 2cm;
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9pt;
        color: #7f8c8d;
        font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    }
    @top-right {
        content: "SEO Audit Report";
        font-size: 8pt;
        color: #bdc3c7;
        font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    }
}

@page :first {
    @bottom-center { content: none; }
    @top-right { content: none; }
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    font-size: 11pt;
    line-height: 1.55;
    color: #2c3e50;
    background: #fff;
}

h1 { font-size: 28pt; font-weight: 700; margin-bottom: 0.3em; color: #2c3e50; }
h2 { font-size: 18pt; font-weight: 700; margin: 1em 0 0.4em; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 4pt; }
h3 { font-size: 13pt; font-weight: 600; margin: 0.8em 0 0.3em; color: #34495e; }

p { margin-bottom: 0.6em; }
a { color: #3498db; text-decoration: none; }

table { width: 100%; border-collapse: collapse; margin: 0.6em 0 1em; font-size: 10pt; }
th, td { padding: 6pt 10pt; text-align: left; border-bottom: 1px solid #ecf0f1; }
th { background: #f8f9fa; font-weight: 600; color: #2c3e50; }
tr:nth-child(even) td { background: #fdfdfe; }

.cover { page-break-after: always; text-align: center; padding-top: 25%; }
.cover h1 { font-size: 36pt; color: #2c3e50; }
.cover .subtitle { font-size: 14pt; color: #7f8c8d; margin-top: 0.5em; }
.cover .score-big { font-size: 72pt; font-weight: 800; margin: 0.4em 0 0.1em; }
.cover .score-label { font-size: 14pt; color: #7f8c8d; }
.cover .meta { font-size: 11pt; color: #95a5a6; margin-top: 2em; }
.cover .meta span { display: inline-block; margin: 0 12pt; }

.toc { page-break-after: always; }
.toc ul { list-style: none; padding: 0; }
.toc li { padding: 4pt 0; border-bottom: 1px dotted #ecf0f1; font-size: 11pt; }
.toc li a { color: #2c3e50; }

.section { page-break-before: always; }

.finding { margin-bottom: 1.2em; padding: 10pt 14pt; border-left: 4px solid #bdc3c7; background: #fafafa; border-radius: 0 4pt 4pt 0; page-break-inside: avoid; }
.finding.critical { border-left-color: #e74c3c; background: #fdf0ef; }
.finding.high { border-left-color: #f39c12; background: #fef9ed; }
.finding.medium { border-left-color: #f1c40f; background: #fefce8; }
.finding.low { border-left-color: #3498db; background: #eef6fc; }

.finding .severity-tag { display: inline-block; font-size: 9pt; font-weight: 700; text-transform: uppercase; padding: 2pt 6pt; border-radius: 3pt; color: #fff; margin-right: 8pt; vertical-align: middle; }
.finding .severity-tag.critical { background: #e74c3c; }
.finding .severity-tag.high { background: #f39c12; }
.finding .severity-tag.medium { background: #f1c40f; color: #2c3e50; }
.finding .severity-tag.low { background: #3498db; }

.finding dt { font-weight: 600; font-size: 10pt; color: #7f8c8d; margin-top: 4pt; }
.finding dd { margin-left: 0; margin-bottom: 4pt; }

.chart-row { display: flex; gap: 20pt; flex-wrap: wrap; justify-content: center; margin: 1em 0; }
.chart-row > div { flex: 0 1 auto; }

.badge { display: inline-block; padding: 2pt 8pt; border-radius: 3pt; font-size: 9pt; font-weight: 600; }
.badge-green { background: #d4efdf; color: #1e8449; }
.badge-orange { background: #fdebd0; color: #b9770e; }
.badge-red { background: #fadbd8; color: #922b21; }

.appendix-table th { font-size: 9pt; }
.appendix-table td { font-size: 9pt; }
"""


def _e(text: Any) -> str:
    """HTML-escape helper."""
    return html_lib.escape(str(text)) if text else ""


def _score_class(score: int) -> str:
    if score >= 80:
        return "badge-green"
    if score >= 50:
        return "badge-orange"
    return "badge-red"


def _score_color_hex(score: int) -> str:
    if score >= 80:
        return "#27ae60"
    if score >= 50:
        return "#f39c12"
    return "#e74c3c"


def _render_cover(data: dict) -> str:
    url = _e(data.get("url", ""))
    score = data.get("health_score", 0)
    biz_type = _e(data.get("business_type", "Unknown"))
    confidence = _e(data.get("confidence", "Medium"))
    date = _e(data.get("date", datetime.now().strftime("%Y-%m-%d")))
    pages = data.get("audited_pages", "N/A")

    return (
        '<div class="cover">\n'
        '  <h1>SEO Audit Report</h1>\n'
        f'  <p class="subtitle">{url}</p>\n'
        f'  <div class="score-big" style="color: {_score_color_hex(score)}">{score}</div>\n'
        '  <p class="score-label">SEO Health Score / 100</p>\n'
        '  <div class="meta">\n'
        f'    <span>Date: {date}</span>\n'
        f'    <span>Type: {biz_type}</span>\n'
        f'    <span>Pages: {pages}</span>\n'
        f'    <span>Confidence: {confidence}</span>\n'
        '  </div>\n'
        '</div>\n'
    )


def _render_toc(sections: list[tuple[str, str]]) -> str:
    items = "".join(
        f'  <li><a href="#{sid}">{_e(title)}</a></li>\n'
        for sid, title in sections
    )
    return (
        '<div class="toc">\n'
        '  <h2>Table of Contents</h2>\n'
        f'  <ul>\n{items}  </ul>\n'
        '</div>\n'
    )


def _render_executive_summary(data: dict) -> str:
    score = data.get("health_score", 0)
    findings = data.get("findings", [])
    critical = sum(1 for f in findings if f.get("severity") == "critical")
    high = sum(1 for f in findings if f.get("severity") == "high")
    medium = sum(1 for f in findings if f.get("severity") == "medium")
    low = sum(1 for f in findings if f.get("severity") == "low")

    cats = data.get("category_scores", {})
    cat_rows = ""
    for name, val in cats.items():
        badge_cls = _score_class(val)
        cat_rows += (
            f'<tr><td>{_e(name)}</td>'
            f'<td><span class="badge {badge_cls}">{val}/100</span></td></tr>\n'
        )

    gauge_svg = health_score_gauge(score)
    donut_svg = severity_donut(critical, high, medium, low)

    return (
        f'<div class="section" id="executive-summary">\n'
        '  <h2>Executive Summary</h2>\n'
        '  <div class="chart-row">\n'
        f'    <div>{gauge_svg}</div>\n'
        f'    <div>{donut_svg}</div>\n'
        '  </div>\n'
        '  <table>\n'
        '    <tr><th>Metric</th><th>Value</th></tr>\n'
        f'    <tr><td>Total Findings</td><td>{critical + high + medium + low}</td></tr>\n'
        f'    <tr><td>Critical</td><td>{critical}</td></tr>\n'
        f'    <tr><td>High</td><td>{high}</td></tr>\n'
        f'    <tr><td>Medium</td><td>{medium}</td></tr>\n'
        f'    <tr><td>Low / Info</td><td>{low}</td></tr>\n'
        '  </table>\n'
        + (f'  <h3>Category Scores</h3>\n  <table>\n    <tr><th>Category</th><th>Score</th></tr>\n{cat_rows}  </table>\n' if cat_rows else '')
        + '</div>\n'
    )


def _render_category_charts(data: dict) -> str:
    cats = data.get("category_scores", {})
    if len(cats) < 3:
        return ""

    radar_svg = category_radar(cats)
    cwv = data.get("cwv", {})
    cwv_section = ""
    if cwv.get("lcp") is not None and cwv.get("inp") is not None and cwv.get("cls") is not None:
        bars_svg = cwv_bars(cwv["lcp"], cwv["inp"], cwv["cls"])
        cwv_section = f'    <div>{bars_svg}</div>\n'

    return (
        '<div class="section" id="visualizations">\n'
        '  <h2>Score Visualizations</h2>\n'
        '  <div class="chart-row">\n'
        f'    <div>{radar_svg}</div>\n'
        f'{cwv_section}'
        '  </div>\n'
        '</div>\n'
    )


def _render_finding(finding: dict) -> str:
    sev = finding.get("severity", "medium")
    return (
        f'<div class="finding {sev}">\n'
        f'  <p><span class="severity-tag {sev}">{_e(sev)}</span> '
        f'<strong>{_e(finding.get("finding", ""))}</strong></p>\n'
        '  <dl>\n'
        f'    <dt>Evidence</dt><dd>{_e(finding.get("evidence", "—"))}</dd>\n'
        f'    <dt>Impact</dt><dd>{_e(finding.get("impact", "—"))}</dd>\n'
        f'    <dt>Fix</dt><dd>{_e(finding.get("fix", "—"))}</dd>\n'
        f'    <dt>Confidence</dt><dd>{_e(finding.get("confidence", "—"))}</dd>\n'
        '  </dl>\n'
        '</div>\n'
    )


def _render_findings_section(findings: list[dict], severity: str, title: str, section_id: str) -> str:
    filtered = [f for f in findings if f.get("severity") == severity]
    if not filtered:
        return ""
    body = "".join(_render_finding(f) for f in filtered)
    return (
        f'<div class="section" id="{section_id}">\n'
        f'  <h2>{_e(title)}</h2>\n'
        f'{body}'
        '</div>\n'
    )


def _render_appendix(data: dict) -> str:
    scripts = data.get("scripts_run", [])
    if not scripts:
        return ""

    rows = ""
    for s in scripts:
        name = _e(s.get("name", ""))
        status = _e(s.get("status", ""))
        duration = s.get("duration", "")
        rows += f"    <tr><td>{name}</td><td>{status}</td><td>{_e(duration)}</td></tr>\n"

    return (
        '<div class="section" id="appendix">\n'
        '  <h2>Appendix — Scripts Summary</h2>\n'
        '  <table class="appendix-table">\n'
        '    <tr><th>Script</th><th>Status</th><th>Duration</th></tr>\n'
        f'{rows}'
        '  </table>\n'
        '</div>\n'
    )


def render_pdf_html(report_data: dict) -> str:
    """Render a complete HTML document suitable for WeasyPrint PDF conversion.

    Args:
        report_data: dict with keys like ``url``, ``health_score``,
            ``business_type``, ``confidence``, ``date``, ``audited_pages``,
            ``category_scores`` (dict), ``cwv`` (dict with lcp/inp/cls),
            ``findings`` (list of finding dicts), ``scripts_run`` (list).

    Returns:
        Full HTML string with inline CSS, SVG charts, cover page, TOC,
        and all findings sections.
    """
    findings = report_data.get("findings", [])

    toc_items: list[tuple[str, str]] = [
        ("executive-summary", "Executive Summary"),
    ]

    cats = report_data.get("category_scores", {})
    if len(cats) >= 3:
        toc_items.append(("visualizations", "Score Visualizations"))

    severity_sections = [
        ("critical", "Critical Issues", "critical-issues"),
        ("high", "High Priority", "high-priority"),
        ("medium", "Medium Priority", "medium-priority"),
        ("low", "Low Priority / Info", "low-priority"),
    ]
    for sev, title, sid in severity_sections:
        if any(f.get("severity") == sev for f in findings):
            toc_items.append((sid, title))

    if report_data.get("scripts_run"):
        toc_items.append(("appendix", "Appendix — Scripts Summary"))

    cover = _render_cover(report_data)
    toc = _render_toc(toc_items)
    summary = _render_executive_summary(report_data)
    charts = _render_category_charts(report_data)

    finding_sections = ""
    for sev, title, sid in severity_sections:
        finding_sections += _render_findings_section(findings, sev, title, sid)

    appendix = _render_appendix(report_data)

    return (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '  <meta charset="utf-8">\n'
        f'  <title>SEO Audit — {_e(report_data.get("url", ""))}</title>\n'
        f'  <style>{_CSS}</style>\n'
        '</head>\n'
        '<body>\n'
        f'{cover}'
        f'{toc}'
        f'{summary}'
        f'{charts}'
        f'{finding_sections}'
        f'{appendix}'
        '</body>\n'
        '</html>\n'
    )
