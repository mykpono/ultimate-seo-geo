#!/usr/bin/env python3
"""
Render the client report from a report source.

The source (JSON, schema_version 1) holds the narrative, findings, recommendations,
coverage, prompts, page cards, validity review and glossary of one engagement. It
extends the generate_report.py summary: pass --summary to fold the machine checks
into the coverage section and the appendix, --graph to fill the inventory and
completeness verdict from site_graph.py, and --structure to render the measured
site shape from page_type_classifier.py, navigation_checker.py, site_architecture.py
and sitemap_checker.py --reconcile outputs.

Output: report.html, one self-contained document (CSS inlined from
references/report-template/) in five parts: Summary, Audit, Strategy, Plan and a
folded Appendix. The design contract is report-template.md.

The source is linted first (report_data_lint.py); errors stop the render unless
--force is given.

Usage:
    python scripts/render_report.py source.json --out reports/
    python scripts/render_report.py source.json --out reports/ --summary summary.json --graph site_graph.json
    python scripts/render_report.py source.json --out reports/ --structure structure/   # page_types.json, navigation.json, architecture.json, sitemap.json
"""

import argparse
import html as html_lib
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report_data_lint  # noqa: E402

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "references", "report-template"))

REPORT_FILE = "report.html"

SEV_CLASS = {"critical": "c", "high": "h", "medium": "m", "low": "l", "info": "i"}
SEV_LABEL = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low", "info": "Info"}
EVIDENCE_LABEL = {"weighted": "Measured · weighted", "display_only": "Measured · shown, not weighted", "measured": "Measured", "sampled": "Sampled",
                  "internal": "Internal records", "inferred": "Inferred", "not_measured": "Not measured"}
EVIDENCE_CLASS = {"weighted": "g", "display_only": "m", "measured": "g", "sampled": "m", "internal": "o", "inferred": "h", "not_measured": "o"}
VALIDITY_CLASS = {"Confirmed": "g", "Revised": "m", "Added": "h", "Dropped": "c"}
TIER_CLASS = {"Free": "g", "Review": "m", "Gated": "h", "Legal": "c", "Never": "c"}
HORIZON_LABEL = {"now": "Now — this week", "weeks_1_4": "Weeks 1–4", "weeks_3_12": "Weeks 3–12", "later": "Later — gated on tests or the baseline"}
HORIZON_ORDER = ["now", "weeks_1_4", "weeks_3_12", "later"]
STATUS_CLASS = {"Strong": "g", "Reviewed": "g", "Needs work": "h", "Gap": "c", "Not measured": "o", "Not applicable": "o",
                "Suspected block": "h"}

ID_LINK = re.compile(r"(?<![\w/#.-])((?:F|D)\d{1,3}|[TMGCP]\d{1,3}[a-z]?)(?![\w-]|\.\d)")


# --- text -----------------------------------------------------------------------

def esc(value) -> str:
    return html_lib.escape("" if value is None else str(value), quote=True)


class Ctx:
    """Rendering context: the source and which IDs exist. Every ID resolves on the one page."""

    def __init__(self, src: dict, doc: str = "report"):
        self.src = src
        self.doc = doc
        self.finding_ids = {f["id"] for f in src.get("findings", []) if f.get("id")}
        self.rec_ids = {r["id"] for r in src.get("recommendations", []) if r.get("id")}
        self.decision_ids = {d["id"] for d in src.get("decisions", []) if d.get("id")}

    def href(self, ident: str):
        if ident in self.finding_ids or ident in self.rec_ids or ident in self.decision_ids:
            return "#" + ident
        if ident + "a" in self.rec_ids:
            return "#" + ident + "a"                        # "G7" resolves to the first of G7a, G7b
        return None

    def inline(self, text) -> str:
        """Escape, then apply `code`, **bold** and ID links."""
        if text is None:
            return ""
        out = esc(text)
        out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
        out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)

        def link(m):
            ident = m.group(1)
            href = self.href(ident)
            return f'<a href="{href}">{ident}</a>' if href else ident

        # do not link inside <code>
        parts = re.split(r"(<code>.*?</code>)", out)
        return "".join(p if p.startswith("<code>") else ID_LINK.sub(link, p) for p in parts)

    def ids(self, ids) -> str:
        if not ids:
            return "—"
        out = []
        for ident in ids:
            href = self.href(ident)
            out.append(f'<a href="{href}">{esc(ident)}</a>' if href else f'<span class="pid">{esc(ident)}</span>')
        return '<span class="ids">' + "".join(out) + "</span>"


def chip(label, cls="o", title=None) -> str:
    t = f' title="{esc(title)}"' if title else ""
    return f'<span class="chip {cls}"{t}>{esc(label)}</span>'


def table(heads, rows, classes=None) -> str:
    classes = classes or [""] * len(heads)
    th = "".join(f'<th class="{esc(c)}">{esc(h)}</th>' if c else f"<th>{esc(h)}</th>" for h, c in zip(heads, classes))
    body = []
    for row in rows:
        row_cls = ""
        cells = row
        if isinstance(row, dict):
            row_cls = row.get("class", "")
            cells = row["cells"]
        tds = []
        for i, cell in enumerate(cells):
            c = classes[i] if i < len(classes) else ""
            tds.append(f'<td class="{esc(c)}">{cell}</td>' if c else f"<td>{cell}</td>")
        body.append(f'<tr class="{esc(row_cls)}">' + "".join(tds) + "</tr>" if row_cls else "<tr>" + "".join(tds) + "</tr>")
    return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def render_blocks(ctx: Ctx, blocks) -> str:
    """Narrative blocks: p, lead, h3, h4, ul, ol, table, callout, figs, ba, note."""
    out = []
    for b in blocks or []:
        if isinstance(b, str):
            out.append(f"<p>{ctx.inline(b)}</p>")
            continue
        t = b.get("type", "p")
        if t == "p":
            out.append(f"<p>{ctx.inline(b.get('text'))}</p>")
        elif t == "lead":
            out.append(f'<div class="verdict"><p class="lead">{ctx.inline(b.get("text"))}</p></div>')
        elif t in ("h3", "h4"):
            out.append(f"<{t}>{ctx.inline(b.get('text'))}</{t}>")
        elif t in ("ul", "ol"):
            items = "".join(f"<li>{ctx.inline(i)}</li>" for i in b.get("items", []))
            out.append(f'<{t} class="tight">{items}</{t}>')
        elif t == "table":
            rows = [[ctx.inline(c) for c in r] for r in b.get("rows", [])]
            out.append(table(b.get("heads", []), rows, b.get("classes")))
        elif t == "callout":
            out.append(f'<div class="callout {esc(b.get("tone", ""))}"><p>{ctx.inline(b.get("text"))}</p></div>')
        elif t == "figs":
            out.append(render_figs(b.get("items", [])))
        elif t == "ba":
            out.append('<div class="ba"><div class="now"><span class="label">' + esc(b.get("now_label", "Today")) + "</span><p>"
                       + ctx.inline(b.get("now")) + '</p></div><div class="fix"><span class="label">' + esc(b.get("fix_label", "Answer-first"))
                       + "</span><p>" + ctx.inline(b.get("fix")) + "</p></div></div>")
        elif t == "note":
            out.append(f'<p class="small">{ctx.inline(b.get("text"))}</p>')
    return "".join(out)


def render_figs(items) -> str:
    cells = []
    for it in items[:4]:
        tone = {"down": "dn", "up": "up", "neutral": "nu"}.get(it.get("tone", "neutral"), "nu")
        cells.append(f'<div><div class="fig {tone}">{esc(it.get("value"))}</div><span class="label">{esc(it.get("label"))}</span></div>')
    return f'<div class="figs">{"".join(cells)}</div>' if cells else ""


# --- page frame -----------------------------------------------------------------

def load_css() -> str:
    css = []
    for name in ("report.css", "print.css"):
        path = os.path.join(TEMPLATE_DIR, name)
        with open(path, encoding="utf-8") as fh:
            css.append(fh.read())
    return "\n".join(css)


NAV_JS = """(function(){var nav=document.querySelector('nav.toc');if(!nav)return;var links=[].slice.call(nav.querySelectorAll('a[href^="#"]'));
var secs=links.map(function(a){return document.getElementById(a.getAttribute('href').slice(1));}).filter(Boolean);
function mark(){var pos=window.pageYOffset+nav.offsetHeight+20,cur=secs[0];secs.forEach(function(s){if(s.offsetTop<=pos)cur=s;});
links.forEach(function(a){a.classList.toggle('active',!!cur&&a.getAttribute('href')==='#'+cur.id);});}
window.addEventListener('scroll',mark,{passive:true});mark();})();
/* In-page links scroll by script. File previews in chat and IDE apps embed the report as an iframe srcdoc,
   whose base URL is the host page's: a plain fragment link there navigates the frame away.
   A target inside a folded appendix section is unfolded first. */
document.addEventListener('click',function(e){if(e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
var a=e.target.closest('a[href^="#"]');if(!a)return;var id=decodeURIComponent(a.getAttribute('href').slice(1));
var t=id&&document.getElementById(id);if(!t)return;e.preventDefault();
for(var p=t;p;p=p.parentElement){if(p.tagName==='DETAILS')p.open=true;}
var d=t.querySelector(':scope>details');if(d)d.open=true;
t.scrollIntoView({block:'start'});
if(!t.hasAttribute('tabindex'))t.setAttribute('tabindex','-1');t.focus({preventScroll:true});
try{history.replaceState(null,'','#'+id);}catch(err){}});
/* Print every folded section, then restore what the reader had open. */
(function(){var shut=[];window.addEventListener('beforeprint',function(){shut=[].slice.call(document.querySelectorAll('details:not([open])'));
shut.forEach(function(d){d.open=true;});});window.addEventListener('afterprint',function(){shut.forEach(function(d){d.open=false;});shut=[];});})();"""


def section_html(sid, number, heading, inner, fold=False) -> str:
    head = f'<span class="sec-n">{esc(number)}</span><h2>{esc(heading)}</h2>'
    if fold:
        return f'<section id="{esc(sid)}" class="fold"><details class="fold"><summary class="sec-head">{head}</summary>{inner}</details></section>'
    return f'<section id="{esc(sid)}"><div class="sec-head">{head}</div>{inner}</section>'


def page(src: dict, title: str, sub: str, parts, css: str, extra_meta=None) -> str:
    """parts: list of (id, label, intro html, sections, fold); sections: list of (id, nav label, heading, body html).

    The sticky nav lists the parts; each part opens with its own contents line. A report of one
    part (the component catalogue) lists its sections in the nav instead. `fold` renders every
    section of the part as a closed <details> that the link handler and printing open.
    """
    meta = src.get("meta", {})
    meta_items = [("Prepared for", meta.get("prepared_for")), ("Prepared by", meta.get("prepared_by")), ("Date", meta.get("date")),
                  ("Data window", meta.get("data_window")), ("Site type", meta.get("site_type")), ("Version", meta.get("version"))]
    meta_items += extra_meta or []
    meta_html = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in meta_items if v)
    if len(parts) == 1:
        toc = "".join(f'<a href="#{esc(sid)}">{esc(label)}</a>' for sid, label, _, _ in parts[0][3])
    else:
        toc = "".join(f'<a href="#{esc(pid)}">{esc(label)}</a>' for pid, label, _, _, _ in parts)
    body = []
    for n, (pid, label, intro, sections, fold) in enumerate(parts, 1):
        secs = []
        contents = []
        for i, (sid, nav, heading, inner) in enumerate(sections, 1):
            number = f"{n}.{i}" if len(parts) > 1 else f"{i:02d}"
            secs.append(section_html(sid, number, heading, inner, fold))
            contents.append(f'<li><a href="#{esc(sid)}"><span class="n">{esc(number)}</span>{esc(nav)}</a></li>')
        if len(parts) == 1:
            body.append("".join(secs))
            continue
        toc_html = f'<ol class="part-toc">{"".join(contents)}</ol>' if contents else ""
        body.append(f'<div class="part" id="{esc(pid)}"><div class="part-head"><span class="part-n">Part {n}</span><h2>{esc(label)}</h2></div>'
                    f'{toc_html}{intro}{"".join(secs)}</div>')
    eyebrow = f"{esc(meta.get('client', ''))} · SEO &amp; GEO"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400..700;1,400..700&family=JetBrains+Mono:wght@400;500;700&display=swap">
<style>
{css}
</style>
</head>
<body>
<header class="top"><div class="top-in">
<div class="eyebrow">{eyebrow}</div>
<h1>{esc(title)}</h1>
<p class="sub">{esc(sub)}</p>
<dl class="meta">{meta_html}</dl>
</div></header>
<nav class="toc" aria-label="Parts"><div class="toc-in">{toc}</div></nav>
<div class="shell">
{"".join(body)}
<footer>{esc(title)} · {esc(meta.get('date', ''))} · Prepared by {esc(meta.get('prepared_by', ''))} · Generated {esc(src.get('generated', date.today().isoformat()))} by render_report.py from source v{esc(meta.get('version', ''))}. If a link does nothing in a preview pane, open the file in a web browser.</footer>
</div>
<script>{NAV_JS}</script>
</body>
</html>
"""


# --- coverage ---------------------------------------------------------------------

def coverage_html(ctx: Ctx, full=True) -> str:
    src = ctx.src
    cov = src.get("coverage", {})
    out = []
    graph = cov.get("graph")
    if graph:
        sm, cr, s = graph.get("sitemap", {}), graph.get("crawl", {}), graph.get("summary", {})
        complete = bool(sm.get("complete")) or bool(cr.get("complete"))
        sitemap_urls = f"{s.get('sitemap_urls') or 0:,}"
        pages_fetched = f"{s.get('pages_fetched') or 0:,}"
        out.append('<div class="cov">'
                   f'<div><b>{esc(sitemap_urls)}</b><span>sitemap URLs · {"complete" if sm.get("complete") else "incomplete"}</span></div>'
                   f'<div><b>{esc(pages_fetched)}</b><span>pages fetched · crawl {"complete" if cr.get("complete") else "incomplete"}</span></div>'
                   f'<div><b>{esc(s.get("max_depth_seen", "—"))}</b><span>max click depth seen</span></div>'
                   f'<div><b>{esc(src.get("meta", {}).get("site_type", "—"))}</b><span>site type</span></div></div>')
        if complete:
            out.append('<div class="cov-claim ok">Inventory complete: absence claims (missing page types, hubs, orphans, equity share) are allowed.</div>')
        else:
            reasons = "; ".join((sm.get("reasons") or []) + (cr.get("reasons") or []))
            out.append(f'<div class="cov-claim no">Inventory incomplete: absence claims about site structure are withheld{(" — " + esc(reasons)) if reasons else ""}.</div>')
        out.append(f'<p class="small">Site graph generated {esc(graph.get("generated_at", "—"))} by site_graph.py.</p>')
    checks = cov.get("checks") or []
    if checks and full:
        rows = []
        for c in checks:
            status = c.get("status") or ("Not measured" if c.get("score") is None else "")
            weighted = c.get("weight") is not None and c.get("score") is not None
            score = esc(c.get("score")) if weighted else "—"
            weight = esc(c.get("weight")) if weighted else "—"
            kind = "weighted" if c.get("weight") else ("shown, not weighted" if c.get("score") is not None or status in ("Reviewed", "Needs work", "Gap") else "—")
            rows.append([esc(c.get("label")), esc(c.get("group") or ""), chip(status, STATUS_CLASS.get(status, "o")), score, weight, esc(kind)])
        out.append("<h3>Checks run</h3>" + table(["Check", "Group", "Status", "Score", "Weight", "Counts toward the score"], rows, ["", "", "", "n", "n", ""]))
        if src.get("health_score", {}).get("overall") is not None:
            hs = src["health_score"]
            out.append(f'<p class="small">Health Score {esc(hs["overall"])}/100 · Source: {esc(hs.get("source"))}.</p>')
        else:
            out.append('<p class="small">Health Score: not scored — ' + esc(src.get("health_score", {}).get("reason", "no generate_report.py run is part of this source")) + ".</p>")
    sources = cov.get("sources") or []
    if sources:
        rows = [[esc(s.get("name")), chip(EVIDENCE_LABEL.get(s.get("status"), s.get("status")), EVIDENCE_CLASS.get(s.get("status"), "o")),
                 ctx.inline(s.get("basis")), esc(s.get("window") or "—"), esc(s.get("date") or "—")] for s in sources]
        out.append("<h3>Data sources</h3>" + table(["Dimension", "Status", "Basis", "Window", "As of"], rows))
    if not full:
        return "".join(out)
    ne = cov.get("not_examined") or []
    if ne:
        out.append("<h3>Not examined</h3>" + table(["What", "Why", "Enabled by"], [[esc(n.get("name")), ctx.inline(n.get("reason")), ctx.ids(n.get("enabled_by") or [])] for n in ne]))
    oos = cov.get("out_of_scope") or []
    if oos:
        out.append("<h3>Out of scope</h3><ul class=\"tight\">" + "".join(f"<li><strong>{esc(o.get('name'))}</strong> — {ctx.inline(o.get('reason'))}</li>" for o in oos) + "</ul>")
    ass = cov.get("assumptions") or []
    if ass:
        out.append("<h3>Assumptions you can reject</h3><ul class=\"tight\">" + "".join(f"<li>{ctx.inline(a)}</li>" for a in ass) + "</ul>")
    caveats = cov.get("caveats") or []
    if caveats:
        out.append(render_blocks(ctx, caveats))
    return "".join(out)


# --- site shape (measured) ----------------------------------------------------------

def site_shape_html(ctx: Ctx) -> str:
    st = ctx.src.get("structure") or {}
    out = []
    pt = st.get("page_types")
    if pt:
        matrix = pt.get("matrix") or {}
        rows = []
        for label, m in sorted(matrix.items(), key=lambda kv: -(kv[1].get("count") or 0)):
            if not m.get("count"):
                continue
            fams = ", ".join("/" + (f or "") for f in (m.get("families") or [])[:3])
            rows.append([esc(label.replace("_", " ")), esc(f"{m['count']:,}"), esc(f"{round(100 * (m.get('share') or 0))}%"), esc(m.get("intent", "")), esc(fams)])
        expected = pt.get("expected") or []
        missing = [l for l in expected if not (matrix.get(l) or {}).get("count")]
        src_status = (pt.get("source") or {}).get("status", "—")
        classified = f"{pt.get('urls_classified') or 0:,}"
        out.append("<h3>Page types</h3>"
                   f'<p class="small">Site type <strong>{esc(pt.get("site_type"))}</strong> · {esc(classified)} URLs classified · inventory {esc(src_status)} · '
                   f'expected types missing: {esc(", ".join(missing) if missing else ("none" if expected else "—"))}. Shown, not weighted.</p>'
                   + table(["Page type", "URLs", "Share", "Intent", "Sections"], rows, ["", "n", "n", "", ""]))
        bi = pt.get("by_intent") or {}
        if bi:
            out.append(table(["Funnel stage", "URLs"], [[esc(k), esc(f"{v.get('count', 0):,}")] for k, v in bi.items() if v.get("count")], ["", "n"]))
    nv = st.get("navigation")
    if nv:
        bc = nv.get("breadcrumbs") or {}
        kv = [("Status", nv.get("status")), ("Pages sampled", nv.get("sampled_pages")),
              ("Primary nav links", (nv.get("primary_nav") or {}).get("count")), ("Footer links", (nv.get("footer_nav") or {}).get("count")),
              ("Breadcrumbs visible / JSON-LD", f"{bc.get('with_visible', 0)} / {bc.get('with_jsonld', 0)}")]
        out.append("<h3>Navigation and breadcrumbs</h3>" + table(["Measure", "Value"], [[esc(k), esc(v)] for k, v in kv]))
        prim = (nv.get("primary_nav") or {}).get("links") or []
        if prim:
            out.append(table(["Primary navigation anchor", "URL"], [[esc(l.get("anchor") or "(empty)"), f'<span class="mono">{esc(l.get("href", ""))}</span>'] for l in prim[:25]]))
        if nv.get("status") == "not_measured":
            out.append('<div class="callout">Navigation was not measured from raw HTML (fewer than three landmark links). This is not a missing navigation; confirm with a rendered fetch.</div>')
    ar = st.get("architecture")
    if ar:
        sections = ar.get("sections") or []
        inv, eq = ar.get("inventory") or {}, ar.get("equity") or {}
        inv_total = f"{inv.get('total') or 0:,}"
        out.append("<h3>Sections</h3>"
                   f'<p class="small">{esc(inv_total)} URLs in inventory ({"complete" if inv.get("complete") else "incomplete"}) · link equity {esc(eq.get("status", "—"))}'
                   + (f' ({esc(eq.get("reason"))})' if eq.get("reason") else "") + ". Shown, not weighted.</p>")
        top = [s for s in sections if not s.get("parent")]
        rows = []
        for s in top[:25]:
            share = s.get("equity_share")
            rows.append([f'<span class="mono">{esc(s.get("path"))}</span>', esc(f"{s.get('url_count', 0):,}"), esc(s.get("dominant_label", "")),
                         "yes" if s.get("in_nav") else "no", "yes" if (s.get("hub") or {}).get("exists") else "no",
                         esc(s.get("avg_depth") if s.get("avg_depth") is not None else "—"), esc("—" if share is None else f"{share:.0%}")])
        out.append(table(["Section", "URLs", "Dominant type", "In nav", "Hub", "Depth", "Equity"], rows, ["", "n", "", "", "", "n", "n"]))
        out.append(tree_html(sections))
    smp = st.get("sitemap")
    if smp:
        rec = smp.get("reconcile") or {}
        if rec:
            rows = []
            for key, val in rec.items():
                if isinstance(val, dict) and "count" in val:
                    rows.append([esc(key.replace("_", " ")), esc(val.get("count")), esc(val.get("status") or "—")])
                elif isinstance(val, list):
                    rows.append([esc(key.replace("_", " ")), esc(len(val)), "—"])
                elif isinstance(val, int) and not isinstance(val, bool):
                    rows.append([esc(key.replace("_", " ")), esc(val), "—"])
            if rows:
                out.append("<h3>Sitemap vs crawl</h3>" + table(["Bucket", "URLs", "Status"], rows, ["", "n", ""]))
        lm = smp.get("lastmod") or {}
        if lm:
            kv = [(k.replace("_", " "), v) for k, v in lm.items() if isinstance(v, (int, float, str, bool))]
            if kv:
                out.append("<h3>Sitemap lastmod</h3>" + table(["Measure", "Value"], [[esc(k), esc(v)] for k, v in kv[:12]]))
    return "".join(out)


def tree_html(sections) -> str:
    """The section tree as a static nested list (no Mermaid at run time)."""
    if not sections:
        return ""
    by_parent = {}
    for s in sections:
        by_parent.setdefault(s.get("parent"), []).append(s)

    def node(s):
        tag = f' <span class="tag">{esc(s.get("dominant_label", ""))}{" · in nav" if s.get("in_nav") else ""}</span>'
        kids = by_parent.get(s.get("path"), [])
        inner = "<ul>" + "".join(node(k) for k in kids) + "</ul>" if kids else ""
        count = f"{s.get('url_count') or 0:,}"
        return f'<li><span class="path">{esc(s.get("path"))}</span><span class="cnt">{esc(count)}</span>{tag}{inner}</li>'

    top = [s for s in by_parent.get(None, []) if s.get("path") != "/"]
    return '<ul class="tree">' + "".join(node(s) for s in top[:40]) + "</ul>"


# --- findings -------------------------------------------------------------------------

def finding_card(ctx: Ctx, f: dict) -> str:
    kind = f.get("kind", "defect")
    sev = f.get("severity", "info")
    cls = "keep" if kind == "keep" else ("opp" if kind == "opportunity" else SEV_CLASS.get(sev, "i"))
    chips = []
    if kind == "keep":
        chips.append(chip("Working well", "g"))
    else:
        chips.append(chip(SEV_LABEL.get(sev, sev), SEV_CLASS.get(sev, "i")))
        if kind != "defect":
            chips.append(chip(kind, "k"))
    chips.append(chip(EVIDENCE_LABEL.get(f.get("evidence_status"), f.get("evidence_status")), EVIDENCE_CLASS.get(f.get("evidence_status"), "o")))
    if f.get("machine_source"):
        chips.append(chip("script: " + f["machine_source"].split(":")[0], "o", f["machine_source"]))
    rows = [("Observation", ctx.inline(f.get("observation"))), ("Evidence", ctx.inline(f.get("evidence")))]
    if f.get("impact"):
        rows.append(("Impact", ctx.inline(f["impact"])))
    rows.append(("Confidence", f"<strong>{esc(f.get('confidence'))}</strong> · would be wrong if: {ctx.inline(f.get('falsifiability'))}"))
    if kind != "keep":
        rows.append(("Fix", ctx.ids(f.get("fixes"))))
    if f.get("watch"):
        rows.append(("Watch", ctx.inline(f["watch"])))
    if f.get("depends_on") or f.get("blocks"):
        rows.append(("Depends on", (ctx.ids(f.get("depends_on")) if f.get("depends_on") else "—") + " · blocks " + (ctx.ids(f.get("blocks")) if f.get("blocks") else "—")))
    dl = "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in rows)
    return (f'<div class="find {cls}" id="{esc(f["id"])}"><div class="find-top">{"".join(chips)}'
            f'<h3>{esc(f["id"])} · {ctx.inline(f.get("title"))}</h3></div><dl>{dl}</dl></div>')


def findings_html(ctx: Ctx) -> str:
    findings = sorted(ctx.src.get("findings", []), key=lambda f: (f.get("order", 999), f.get("id", "")))
    main = [f for f in findings if f.get("kind") in ("defect", "risk")]
    return "".join(finding_card(ctx, f) for f in main)


# --- recommendations -----------------------------------------------------------------

def rec_cells(ctx: Ctx, r: dict, cols, anchor=False, today=frozenset()) -> list:
    """anchor: this row is the one element that owns the recommendation's id.
    Only the full register sets it; every other view links to that row.
    today: IDs an agent can start now, marked in the action cell."""
    cells = []
    for c in cols:
        if c == "id":
            if anchor:
                cells.append(f'<a id="{esc(r["id"])}" href="#{esc(r["id"])}" class="mono">{esc(r["id"])}</a>')
            else:
                cells.append(f'<a href="{esc(ctx.href(r["id"]) or "#" + r["id"])}" class="mono">{esc(r["id"])}</a>')
        elif c == "action":
            sup = r.get("supersedes")
            extra = ""
            if sup:
                extra = f'<p class="small">Overrides {esc(sup.get("check"))} finding {esc(sup.get("finding_id", ""))}: {ctx.inline(sup.get("reason"))}</p>'
            mark = chip("Start today", "g") + " " if r.get("id") in today else ""
            cells.append(mark + ctx.inline(r.get("action")) + extra)
        elif c == "fixes":
            cells.append(ctx.ids(r.get("fixes")))
        elif c == "basis":
            cells.append(chip(r.get("basis"), {"Documented": "g", "Data-backed": "m", "Test first": "h"}.get(r.get("basis"), "o")))
        elif c == "validity":
            cells.append(chip(r["validity"], VALIDITY_CLASS.get(r["validity"], "o")) if r.get("validity") else "—")
        elif c == "tier":
            cells.append(chip(r.get("tier"), TIER_CLASS.get(r.get("tier"), "o")))
        elif c == "owner":
            cells.append(esc(r.get("owner_role")))
        elif c == "lane":
            cells.append(f'<span class="chip lane-{esc(r.get("lane"))}">{esc(r.get("lane"))}</span>')
        elif c == "effort":
            cells.append(esc(r.get("effort")))
        elif c == "effect":
            cells.append(ctx.inline(r.get("effect") or "—"))
        elif c == "deps":
            b = ctx.ids(r.get("blocked_by")) if r.get("blocked_by") else "—"
            u = ctx.ids(r.get("unblocks")) if r.get("unblocks") else "—"
            cells.append(f'<span class="deps">blocked by</span> {b}<br><span class="deps">unblocks</span> {u}')
        elif c == "done":
            cells.append(ctx.inline(r.get("done_when")))
        elif c == "horizon":
            cells.append(esc(HORIZON_LABEL.get(r.get("horizon"), r.get("horizon"))))
        elif c == "track":
            cells.append(esc(r.get("track") or "—"))
        elif c == "status":
            cells.append(esc(r.get("status") or "planned"))
        elif c == "decision":
            cells.append(ctx.ids([r["decision"]]) if r.get("decision") else "—")
    return cells


REGISTER_COLS = [("id", "ID", "q"), ("action", "Action", ""), ("fixes", "Fixes", ""), ("basis", "Basis", ""), ("validity", "Validity", ""),
                 ("tier", "Tier", ""), ("owner", "Owner", ""), ("lane", "Lane", ""), ("effort", "Effort", "n"), ("effect", "Expected effect", ""),
                 ("deps", "Dependencies", ""), ("done", "Done when", ""), ("status", "Status", "")]


def register_table(ctx: Ctx, recs, cols=REGISTER_COLS, anchor=False, today=frozenset()) -> str:
    rows = []
    for r in recs:
        row = {"cells": rec_cells(ctx, r, [c for c, _, _ in cols], anchor, today)}
        if r.get("status") == "dropped":
            row["class"] = "dropped"
        rows.append(row)
    return table([h for _, h, _ in cols], rows, [c for _, _, c in cols])


def active_recs(src):
    return [r for r in src.get("recommendations", []) if r.get("status") != "dropped"]


def blockers_open(src, r) -> list:
    """Recommendation IDs and decisions that still block r."""
    by_id = {x["id"]: x for x in src.get("recommendations", [])}
    open_ = []
    for b in r.get("blocked_by") or []:
        other = by_id.get(b)
        if other and other.get("status") not in ("shipped", "read", "dropped"):
            open_.append(b)
    if r.get("lane") == "Decision":
        open_.append(r.get("decision") or "decision")
    return open_


def start_today(src) -> list:
    """Auto or Assisted recommendations with nothing left to wait for.

    Any open blocker counts, whatever its lane: a test that has not read is as
    blocking as a redirect nobody has approved.
    """
    out = []
    for r in active_recs(src):
        if r.get("lane") not in ("Auto", "Assisted"):
            continue
        if r.get("status") in ("shipped", "read"):
            continue
        if not blockers_open(src, r):
            out.append(r)
    return out


# --- parts -------------------------------------------------------------------------------
#
# One report, five parts. Each thing renders once: the verdict and decisions in the Summary,
# coverage and findings in the Audit, prompts and page cards in the Strategy, the register in
# the Plan, method and machine checks in the Appendix. Every other mention links by ID.

def lead(ctx: Ctx, text) -> str:
    return f'<div class="verdict"><p class="lead">{ctx.inline(text)}</p></div>' if text else ""


def decisions_table(ctx: Ctx) -> str:
    """The one place each decision ID is anchored."""
    decisions = ctx.src.get("decisions", [])
    if not decisions:
        return "<p>None.</p>"
    recs = ctx.src.get("recommendations", [])
    rows = [[f'<a id="{esc(x["id"])}" href="#{esc(x["id"])}" class="mono">{esc(x["id"])}</a>', ctx.inline(x.get("question")), esc(x.get("owner_role")),
             ctx.inline(x.get("needed_by") or "—"), esc(x.get("status") or "open"), ctx.ids([r["id"] for r in recs if r.get("decision") == x["id"]])] for x in decisions]
    return table(["ID", "Decision", "Owner", "Needed by", "Status", "Unblocks"], rows, ["q", "", "", "", "", ""])


def part_summary(ctx: Ctx, used: set):
    """Leadership reads this part and can stop. Falls back to the audit's verdict and figures
    when the source has no brief, and records what it borrowed so the Audit does not repeat it."""
    src = ctx.src
    docs = src.get("docs", {})
    b, a = docs.get("brief", {}), docs.get("audit", {})
    verdict = b.get("verdict")
    if not verdict and a.get("verdict"):
        verdict = a["verdict"]
        used.add("audit.verdict")
    figures = b.get("figures")
    if not figures and a.get("figures"):
        figures = a["figures"]
        used.add("audit.figures")
    sections = [("summary-verdict", "Verdict", "Verdict", lead(ctx, verdict) + render_figs(figures or []) + render_blocks(ctx, b.get("blocks", [])))]
    sections.append(("summary-decisions", "Decisions", "Decisions needed", decisions_table(ctx)))
    top = [r for r in active_recs(src) if r.get("brief")] or [r for r in active_recs(src) if r.get("horizon") == "now"][:6]
    actions = table(["ID", "Action", "Owner", "Lane", "Done when"], [rec_cells(ctx, r, ["id", "action", "owner", "lane", "done"]) for r in top], ["q", "", "", "", ""]) if top else "<p>Nothing is scheduled for this week.</p>"
    sections.append(("summary-actions", "This week", "This week",
                     actions + f'<p class="small">All {len(active_recs(src))} recommendations, in order, with dependencies and tiers: <a href="#plan-register">the register</a>.</p>'))
    ne = src.get("coverage", {}).get("not_examined", [])
    if ne:
        unknown = '<ul class="tight">' + "".join(f"<li><strong>{esc(n.get('name'))}</strong> — {ctx.inline(n.get('reason'))}</li>" for n in ne) + "</ul>"
        sections.append(("summary-unknown", "Not known", "What is not known yet",
                         unknown + '<p class="small">What would close each gap, and what was measured: <a href="#audit-coverage">Scope and coverage</a>.</p>'))
    how = docs.get("index", {}).get("blocks")
    if how:
        sections.append(("summary-how", "How to read", "How to read this report", render_blocks(ctx, how)))
    return ("summary", "Summary", "", sections, False)


def part_audit(ctx: Ctx, used: set):
    src = ctx.src
    d = src.get("docs", {}).get("audit", {})
    intro = ("" if "audit.verdict" in used else lead(ctx, d.get("verdict"))) + render_blocks(ctx, d.get("summary", [])) \
        + ("" if "audit.figures" in used else render_figs(d.get("figures", [])))
    sections = [("audit-coverage", "Coverage", "Scope and coverage", coverage_html(ctx))]
    for s in d.get("sections", []):
        sections.append(("audit-" + s["id"], s.get("nav", s["title"]), s["title"], render_blocks(ctx, s.get("blocks", []))))
    shape = site_shape_html(ctx) + render_blocks(ctx, d.get("site_shape", []))
    if shape:
        sections.append(("audit-shape", "Site shape", "Site shape", shape))
    sections.append(("audit-findings", "Findings", "Findings", render_blocks(ctx, d.get("findings_intro", [])) + findings_html(ctx)))
    keeps = [f for f in src.get("findings", []) if f.get("kind") == "keep"]
    if keeps:
        sections.append(("audit-strengths", "Strengths", "Strengths to protect", "".join(finding_card(ctx, f) for f in keeps)))
    opps = [f for f in src.get("findings", []) if f.get("kind") == "opportunity"]
    if opps:
        sections.append(("audit-opportunities", "Opportunities", "Opportunity signals",
                         '<p class="small">Pages or assets to create rather than defects to fix. They carry a severity for sizing but never sit in the findings list, and a missing page type is only claimed from a complete inventory.</p>'
                         + "".join(finding_card(ctx, f) for f in opps)))
    if d.get("geo"):
        sections.append(("audit-geo", "GEO / AEO", d.get("geo_title", "GEO / AEO: being the source AI assistants cite"), render_blocks(ctx, d["geo"])))
    if d.get("questions"):
        sections.append(("audit-questions", "Key questions", "Answers to the key questions", render_blocks(ctx, d["questions"])))
    return ("audit", "Audit", intro, sections, False)


def pages_html(ctx: Ctx, d: dict) -> str:
    """Page cards grouped by wave; each wave folds, since only the content team works through them."""
    out = [render_blocks(ctx, d.get("pages_intro", []))]
    waves = {}
    for p in ctx.src.get("pages", []):
        waves.setdefault(p.get("wave", ""), []).append(p)
    for wave, items in waves.items():
        cards = [render_blocks(ctx, items[0].get("wave_intro", []))]
        for p in items:
            cls = {"Consolidate": "con", "Rebuild": "reb", "Add block": "add", "New": "new", "Differentiate": "reb"}.get(p.get("type"), "")
            rows = [("Owns", " ".join(f'<span class="pid">{esc(x)}</span>' for x in p.get("prompts", [])))]
            if p.get("page_type"):
                rows.append(("Page type", esc(p["page_type"])))
            for k in ("Today", "Data", "Change", "Test"):
                if p.get("fields", {}).get(k):
                    cls_dd = {"Today": "state", "Data": "state", "Test": "test"}.get(k, "")
                    rows.append((k, f'<span class="{cls_dd}">' + ctx.inline(p["fields"][k]) + "</span>"))
            for k, v in p.get("fields", {}).items():
                if k not in ("Owns", "Today", "Data", "Change", "Test"):
                    rows.append((k, ctx.inline(v)))
            if p.get("recs"):
                rows.append(("Recs", ctx.ids(p["recs"])))
            dl = "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in rows)
            cards.append(f'<div class="pg {cls}"><div class="pg-top">{chip(p.get("type"), {"con": "c", "reb": "h", "add": "m", "new": "g"}.get(cls, "o"))}<span class="pg-url">{ctx.inline(p.get("url"))}</span></div><dl>{dl}</dl></div>')
        n = len(items)
        out.append(f'<details class="fold wave"><summary><h3>{esc(wave)}</h3><span class="small">{n} page{"s" if n != 1 else ""}</span></summary>{"".join(cards)}</details>')
    return "".join(out)


def part_strategy(ctx: Ctx):
    src = ctx.src
    d = src.get("docs", {}).get("strategy", {})
    intro = lead(ctx, d.get("verdict")) + render_blocks(ctx, d.get("summary", [])) + render_figs(d.get("figures", [])) + render_blocks(ctx, d.get("coverage_note", []))
    sections = [("strategy-" + s["id"], s.get("nav", s["title"]), s["title"], render_blocks(ctx, s.get("blocks", []))) for s in d.get("sections", [])]
    prompts = src.get("prompts", {})
    if prompts.get("tiers"):
        tiers = []
        for t in prompts["tiers"]:
            rows = "".join(f'<div class="prow" id="{esc(r.get("id", ""))}"><q>{ctx.inline(r.get("prompt"))}</q><div class="own"><b>{esc(r.get("id", ""))} · {ctx.inline(r.get("owner"))}</b>{ctx.inline(r.get("note"))}</div></div>' for r in t.get("rows", []))
            tiers.append(f'<div class="ptier"><div class="ptier-h"><strong>{ctx.inline(t.get("tier"))}</strong><span>{ctx.inline(t.get("note"))}</span></div>{rows}</div>')
        sections.append(("strategy-prompts", "Prompt roster", "The AI prompt roster", render_blocks(ctx, prompts.get("intro", [])) + "".join(tiers)))
    if src.get("pages"):
        sections.append(("strategy-pages", "Page cards", "Page-to-prompt map", pages_html(ctx, d)))
    if not (intro or sections):
        return None
    return ("strategy", "Strategy", intro, sections, False)


def part_plan(ctx: Ctx):
    src = ctx.src
    d = src.get("docs", {}).get("plan", {})
    live = active_recs(src)
    intro = lead(ctx, d.get("verdict")) + render_blocks(ctx, d.get("summary", []))
    sections = []
    if d.get("guardrails"):
        sections.append(("plan-guardrails", "Guardrails", "Guardrails", render_blocks(ctx, d["guardrails"])))
    rule = d.get("prioritisation") or [
        {"type": "ol", "items": ["**Measurement prerequisites** — exports with expiry dates, the site graph, the prompt baseline.",
                                 "**Stop-loss and public-fact fixes** — wrong claims, broken redirects, corrupted assets.",
                                 "**Confirmed defects** with a documented fix and no measurement dependency (Track A).",
                                 "**Tested changes** (Track B), one test per page set, ordered by value at stake × confidence ÷ effort.",
                                 "**Bets** (Track C), including page-type opportunities, gated on a test read or the baseline."]},
        {"type": "p", "text": "Within a level, ties break by value at stake × confidence ÷ effort. The risk tier is a gate, not a score input. Every row shows what blocks it and what it unblocks."}]
    sections.append(("plan-rule", "Priority rule", "How the order was decided", render_blocks(ctx, rule)))
    today = {r["id"] for r in start_today(src)}
    timeline = ['<p class="small">' + (f'{chip("Start today", "g")} marks the {len(today)} Auto or Assisted item{"s" if len(today) != 1 else ""} with nothing left to wait for: an agent can begin now. '
                                        if today else "No item is unblocked for an agent yet. ")
                + "Auto items ship under the Free tier with automated checks; Assisted items are drafted by the agent and merged by a human.</p>"]
    cols = [c for c in REGISTER_COLS if c[0] in ("id", "action", "fixes", "tier", "owner", "lane", "effort", "deps", "done", "status")]
    for h in HORIZON_ORDER:
        items = [r for r in live if r.get("horizon") == h]
        if items:
            timeline.append(f'<div class="plan-h"><h3>{esc(HORIZON_LABEL[h])}</h3><p class="small">{len(items)} items</p></div>' + register_table(ctx, items, cols, today=today))
    sections.append(("plan-timeline", "Timeline", "Timeline", "".join(timeline)))
    if d.get("owners"):
        sections.append(("plan-owners", "Owners", "Owners", render_blocks(ctx, d["owners"])))
    sections.append(("plan-register", "Register", "The full register",
                     '<p class="small">Every recommendation, including dropped ones (struck through). IDs: T technical · M measurement · G GEO and public facts · C commercial and content · P portfolio. '
                     'Decisions are listed in the <a href="#summary-decisions">Summary</a>.</p>' + register_table(ctx, src.get("recommendations", []), anchor=True)))
    for key, nav, title in (("monitoring", "Monitoring", "Monitoring"), ("standards", "Standards", "Standards to build"), ("loop", "Monthly loop", "Monthly loop"), ("needed", "Still needed", "Still needed")):
        if d.get(key):
            sections.append(("plan-" + key, nav, title, render_blocks(ctx, d[key])))
    return ("plan", "Plan", intro, sections, False)


def part_appendix(ctx: Ctx):
    """Reviewers' material, folded: the page stays readable, and links and printing unfold it."""
    src = ctx.src
    d = src.get("docs", {}).get("appendix", {})
    v = src.get("validity", {})
    sections = []
    recs = src.get("recommendations", [])
    if any(r.get("validity") for r in recs) or v.get("summary") or v.get("method"):
        counts = {k: sum(1 for r in recs if r.get("validity") == k) for k in ("Confirmed", "Revised", "Dropped", "Added")}
        figs = render_figs([{"value": counts["Confirmed"], "label": "Confirmed as written", "tone": "up"}, {"value": counts["Revised"], "label": "Revised — kept, with changes", "tone": "neutral"},
                            {"value": counts["Dropped"], "label": "Dropped", "tone": "down"}, {"value": counts["Added"], "label": "Added", "tone": "up"}])
        val_rows = []
        for r in recs:
            if not r.get("validity"):
                continue
            val_rows.append({"cells": [f'<a href="{ctx.href(r["id"])}" class="mono">{esc(r["id"])}</a>', ctx.inline(r.get("validity_original") or r.get("action")), chip(r["validity"], VALIDITY_CLASS.get(r["validity"], "o")),
                                       ctx.inline(r.get("validity_reason") or "—"), ctx.inline(r.get("validity_now") or r.get("action"))], "class": "dropped" if r.get("status") == "dropped" else ""})
        validity = (render_blocks(ctx, v.get("summary", [])) + figs + ("<h3>Method</h3>" + render_blocks(ctx, v["method"]) if v.get("method") else "")
                    + "<h3>Verdicts</h3>" + table(["ID", "Recommendation as first stated", "Verdict", "Why", "Now stands as"], val_rows, ["q", "", "", "", ""]))
        sections.append(("appendix-validity", "Validity review", "Recommendation validity review", validity))
    if v.get("corrections"):
        sections.append(("appendix-corrections", "Corrections", "Corrected findings and figures", render_blocks(ctx, v["corrections"])))
    if v.get("evidence_levels"):
        sections.append(("appendix-evidence", "Evidence levels", "Evidence levels for the GEO tactics", render_blocks(ctx, v["evidence_levels"])))
    tests = src.get("tests", [])
    if tests:
        sections.append(("appendix-tests", "Open tests", "Open tests", render_blocks(ctx, d.get("tests_intro", [])) + table(["Claim", "Would be disproved by", "Design"], [[ctx.inline(t.get("claim")), ctx.inline(t.get("disproved_by")), ctx.inline(t.get("design"))] for t in tests]) + render_blocks(ctx, d.get("tests_outro", []))))
    machine = src.get("machine") or {}
    if machine.get("findings") or machine.get("categories"):
        cats = machine.get("categories") or {}
        rows = [[esc(c.get("label")), esc(c.get("group") or ""), chip(c.get("status") or "—", STATUS_CLASS.get(c.get("status"), "o")), esc(c.get("score") if c.get("weight") and c.get("score") is not None else "—"), esc(c.get("weight") or "—")] for c in cats.values()] if isinstance(cats, dict) else []
        mf = []
        for f in machine.get("findings") or []:
            sev = str(f.get("severity", "info")).lower()
            mf.append(f'<div class="find {SEV_CLASS.get(sev, "i")}"><div class="find-top">{chip(SEV_LABEL.get(sev, sev), SEV_CLASS.get(sev, "i"))}{chip("script: " + str(f.get("section", "")), "o")}<h3>{ctx.inline(f.get("finding"))}</h3></div>'
                      f'<dl><dt>Evidence</dt><dd>{ctx.inline(f.get("evidence") or "—")}</dd><dt>Impact</dt><dd>{ctx.inline(f.get("impact") or "—")}</dd><dt>Fix</dt><dd>{ctx.inline(f.get("fix") or "—")}</dd><dt>Confidence</dt><dd>{esc(f.get("confidence") or "—")}</dd></dl></div>')
        intro = f'<p class="small">Output of generate_report.py on {esc(machine.get("url", ""))} at {esc(machine.get("timestamp", ""))} (summary schema {esc(machine.get("schema_version", ""))}). '
        if machine.get("overall") is not None:
            intro += f'Health Score {esc(machine["overall"])}/100 from {esc(machine.get("measured_categories", "?"))} weighted checks.'
        else:
            intro += "Not scored."
        intro += " Structure checks are shown, never weighted.</p>"
        sections.append(("appendix-machine", "Machine checks", "Machine checks", intro + (table(["Check", "Group", "Status", "Score", "Weight"], rows, ["", "", "", "n", "n"]) if rows else "") + "".join(mf)))
    ar = (src.get("structure") or {}).get("architecture") or {}
    if ar.get("mermaid"):
        sections.append(("appendix-mermaid", "Section tree", "Section tree (Mermaid source)", f'<pre class="mono">{esc(ar["mermaid"])}</pre>'))
    gl = src.get("glossary", [])
    if gl:
        sections.append(("appendix-glossary", "Glossary", "Glossary", '<dl class="gloss">' + "".join(f"<div><dt>{esc(g.get('term'))}</dt><dd>{ctx.inline(g.get('definition'))}</dd></div>" for g in gl) + "</dl>"))
    if not sections:
        return None
    intro = render_blocks(ctx, d.get("intro", [])) or '<p class="small">Method and evidence for reviewers. Each section opens on click, and all of them open when the page is printed.</p>'
    return ("appendix", "Appendix", intro, sections, True)


def render(src: dict, css=None) -> str:
    """The whole report as one self-contained HTML page."""
    css = load_css() if css is None else css
    src.setdefault("generated", date.today().isoformat())
    ctx = Ctx(src)
    used = set()
    parts = [part_summary(ctx, used), part_audit(ctx, used), part_strategy(ctx), part_plan(ctx), part_appendix(ctx)]
    meta = src.get("meta", {})
    title = meta.get("title") or f"{meta.get('client', '')} SEO & GEO report".strip()
    sub = meta.get("purpose") or src.get("docs", {}).get("brief", {}).get("sub", "The verdict, the audit, the strategy and the plan in one document.")
    return page(src, title, sub, [p for p in parts if p], css)


# --- assembly ------------------------------------------------------------------------------

def merge_summary(src: dict, summary: dict) -> dict:
    """Fold a generate_report.py summary (schema 2) into the source."""
    cov = src.setdefault("coverage", {})
    cats = summary.get("categories") or {}
    checks = []
    for key, c in cats.items():
        checks.append({"key": key, "label": c.get("label", key), "group": c.get("group"), "score": c.get("score"), "weight": c.get("weight"), "status": c.get("status")})
    cov["checks"] = checks
    if summary.get("overall") is not None:
        src["health_score"] = {"overall": summary["overall"], "source": f"generate_report.py — {summary.get('measured_categories', '?')} weighted checks measured", "grade": summary.get("grade")}
    src["machine"] = {"url": summary.get("url"), "timestamp": summary.get("timestamp"), "schema_version": summary.get("schema_version"), "overall": summary.get("overall"),
                      "measured_categories": summary.get("measured_categories"), "categories": cats, "findings": summary.get("findings") or []}
    return src


def merge_graph(src: dict, graph: dict) -> dict:
    cov = src.setdefault("coverage", {})
    cov["graph"] = {"sitemap": {k: v for k, v in (graph.get("sitemap") or {}).items() if k != "urls"}, "crawl": graph.get("crawl") or {},
                    "summary": graph.get("summary") or {}, "generated_at": graph.get("generated_at"), "site": graph.get("site")}
    return src


def merge_structure(src: dict, folder: str) -> dict:
    st = src.setdefault("structure", {})
    for key, name in (("page_types", "page_types.json"), ("navigation", "navigation.json"), ("architecture", "architecture.json"), ("sitemap", "sitemap.json")):
        path = os.path.join(folder, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and not data.get("error"):
                if key == "architecture" and "sections" in data:
                    data = dict(data)
                    data["sections"] = [{k: v for k, v in s.items() if k not in ("keys",)} for s in data["sections"]]
                st[key] = data
            elif isinstance(data, dict) and data.get("error"):
                print(f"  ⚠️ {name}: {data['error']} — skipped")
    return src


def sample_source() -> dict:
    """A small complete source used for the component catalogue and smoke tests."""
    return {
        "schema_version": 1,
        "meta": {"client": "Example", "site": "https://example.com", "prepared_for": "Example marketing team", "prepared_by": "The audit team",
                 "date": "2026-09-17", "data_window": "Aug 2026", "site_type": "saas", "version": "sample", "purpose": "Component catalogue."},
        "docs": {
            "brief": {"verdict": "The verdict card: one paragraph that answers the question, before any evidence.", "figures": [
                {"value": "−28%", "label": "Brand clicks, year over year", "tone": "down"}, {"value": "2.40%", "label": "Homepage demo rate", "tone": "up"},
                {"value": "0.35%", "label": "Share of clicks to commercial URLs", "tone": "neutral"}, {"value": "91", "label": "Demo requests from AI referrals", "tone": "up"}]},
            "audit": {"verdict": "Every document opens with a verdict.", "summary": [
                {"type": "p", "text": "Prose with `code`, **bold** and linked IDs: F1 is fixed by T1, which needs decision D1."},
                {"type": "callout", "tone": "k", "text": "A callout for a caveat the reader must not miss."},
                {"type": "ba", "now_label": "Today", "now": "The page opens with a breadcrumb and a marketing sentence.", "fix_label": "Answer-first", "fix": "The page opens with the definition and one specific number."},
                {"type": "table", "heads": ["Metric", "Aug 2025", "Aug 2026", "Change"], "classes": ["", "n", "n", "n"], "rows": [["Clicks", "1,004", "719", "−28%"]]}],
                "sections": []},
            "strategy": {"verdict": "Strategy verdict."}, "plan": {"verdict": "Plan verdict."},
        },
        "coverage": {
            "graph": {"sitemap": {"found": True, "complete": True}, "crawl": {"complete": False, "reasons": ["crawl stopped at max_pages"]},
                      "summary": {"sitemap_urls": 3021, "pages_fetched": 3298, "max_depth_seen": 3}, "generated_at": "2026-09-17T20:04:56+00:00"},
            "checks": [{"key": "robots", "label": "Robots & AI crawlers", "group": "technical", "score": 100, "weight": 5, "status": "Strong"},
                       {"key": "page_types", "label": "Page-type coverage", "group": "content", "score": None, "weight": None, "status": "Reviewed"},
                       {"key": "pagespeed", "label": "Core Web Vitals", "group": "performance", "score": None, "weight": 8, "status": "Not measured"}],
            "sources": [{"key": "gsc", "name": "Search Console", "kind": "api", "status": "measured", "basis": "Daily property series", "window": "Jun 2025–Sep 2026", "date": "2026-09-15"},
                        {"key": "prompts", "name": "AI-assistant citations", "kind": "sample", "status": "not_measured", "basis": "No prompt baseline yet"}],
            "not_examined": [{"name": "Backlinks", "reason": "No Links export yet", "enabled_by": ["M1"]}],
            "out_of_scope": [{"name": "Paid search", "reason": "Not a search surface"}],
            "assumptions": ["The homepage represents brand demand."],
        },
        "health_score": {"overall": 84, "source": "generate_report.py — 19 weighted checks measured"},
        "findings": [
            {"id": "F1", "kind": "defect", "severity": "critical", "order": 1, "title": "Brand demand is falling", "observation": "Clicks on the exact brand query fell 28%.",
             "evidence": "1,004 → 719 per 28 days, Search Console.", "evidence_status": "measured", "impact": "The homepage produces 44% of organic demo requests.",
             "confidence": "Confirmed", "falsifiability": "Brand clicks recover without a paid change.", "fixes": ["T1"], "watch": "Brand clicks per 28 days, read at 8 weeks.", "depends_on": ["F2"]},
            {"id": "F2", "kind": "risk", "severity": "high", "order": 2, "title": "Pipeline figures are not CRM-reconciled", "observation": "GA4 and CRM disagree.",
             "evidence": "GA4 demo requests only.", "evidence_status": "inferred", "impact": "Every pipeline figure carries this uncertainty.", "confidence": "Likely",
             "falsifiability": "CRM shows the same series.", "fixes": ["M1"], "watch": "GA4 vs CRM within 10%."},
            {"id": "F3", "kind": "opportunity", "severity": "medium", "order": 3, "title": "No comparison page in the navigation", "observation": "163 comparison URLs, none linked globally.",
             "evidence": "navigation_checker.py, 40 pages sampled.", "evidence_status": "display_only", "machine_source": "navigation:money_page_not_in_nav", "impact": "The most-cited page type is buried.",
             "confidence": "Confirmed", "falsifiability": "Contextual links exist.", "fixes": ["C1"], "watch": "Comparison prompt citations."},
            {"id": "F4", "kind": "keep", "severity": "info", "order": 4, "title": "AI crawlers are allowed and pages render server-side", "observation": "Nine allow groups; content readable without JavaScript.",
             "evidence": "robots.txt and raw-HTML crawl.", "evidence_status": "measured", "confidence": "Confirmed", "falsifiability": "A rendering change."},
        ],
        "recommendations": [
            {"id": "T1", "action": "Redirect `www` to the identical apex path in one hop", "fixes": ["F1"], "basis": "Documented", "validity": "Confirmed", "tier": "Gated",
             "owner_role": "Engineering", "lane": "Human", "effort": "S", "effect": "Deep links pass value to the right page", "blocked_by": [], "unblocks": ["C1"],
             "done_when": "20 sampled paths return one 301", "horizon": "now", "track": "A", "status": "planned", "decision": None},
            {"id": "M1", "action": "Reconcile GA4 demo requests with the CRM monthly", "fixes": ["F2"], "basis": "Data-backed", "validity": "Revised", "validity_reason": "The step is organic-specific.",
             "tier": "Free", "owner_role": "Analytics", "lane": "Auto", "effort": "S", "effect": "Trustworthy pipeline figures", "blocked_by": [], "unblocks": [], "done_when": "Agreement within 10% for 3 months",
             "horizon": "now", "track": "A", "status": "planned"},
            {"id": "C1", "action": "Link the comparison pages from `/pricing` and the footer", "fixes": ["F3"], "basis": "Test first", "validity": "Added", "tier": "Review", "owner_role": "Content",
             "lane": "Assisted", "effort": "M", "effect": "Comparison citations", "blocked_by": ["T1"], "unblocks": [], "done_when": "Linked; citations read at 8 weeks", "horizon": "weeks_3_12", "track": "B",
             "status": "planned", "supersedes": {"check": "navigation", "finding_id": "money_page_not_in_nav", "reason": "Global navigation stays as is; links are tested cluster by cluster first."}},
            {"id": "C2", "action": "Publish the pricing model", "fixes": ["F1"], "basis": "Data-backed", "validity": "Dropped", "tier": "Legal", "owner_role": "Leadership", "lane": "Decision",
             "decision": "D1", "effort": "S", "done_when": "—", "horizon": "later", "status": "dropped"},
        ],
        "decisions": [{"id": "D1", "question": "Publish the pricing model on `/pricing`?", "owner_role": "Leadership", "needed_by": "Week 6", "status": "open"}],
        "prompts": {"tiers": [{"tier": "Tier 1 · Category selection", "note": "Improvado must appear as a named candidate.", "rows": [
            {"id": "T1.1", "prompt": "What platform should a 2,000-person retailer use to unify marketing data?", "owner": "/products, /reporting", "note": "Needs an enterprise-scale qualifier"}]}]},
        "pages": [{"wave": "Wave 1 · Structure", "wave_intro": [{"type": "p", "text": "Nothing else is worth writing until these resolve."}], "type": "Consolidate", "url": "/products/marketing-attribution",
                   "prompts": ["T1.1"], "page_type": "product_feature", "recs": ["T1"],
                   "fields": {"Today": "551 words · duplicate at `/use-cases/marketing-attribution`", "Data": "52 impressions / 0 clicks", "Change": "301 the duplicate (T1)", "Test": "One URL ranks for 4 weeks"}}],
        "validity": {"summary": [{"type": "lead", "text": "The direction held; the specifics did not."}], "corrections": [{"type": "table", "heads": ["Claim", "Corrected", "Effect"], "rows": [["0.67% homepage rate", "2.40%", "Brand reliance stronger"]]}]},
        "tests": [{"claim": "Answer-first openings improve citations", "disproved_by": "No difference vs control", "design": "Matched pairs, 100–200 posts, 8–12 weeks"}],
        "glossary": [{"term": "GEO", "definition": "Generative engine optimization."}],
        "structure": {"architecture": {"sections": [{"path": "/blog/", "parent": None, "url_count": 890, "dominant_label": "blog_article", "in_nav": True, "hub": {"exists": True}, "avg_depth": 2.0, "equity_share": None},
                                                    {"path": "/blog/ai/", "parent": "/blog/", "url_count": 82, "dominant_label": "blog_article", "in_nav": False, "hub": {"exists": False}, "avg_depth": 3.0}],
                                       "inventory": {"total": 4345, "complete": True}, "equity": {"status": "not measured", "reason": "needs a complete crawl"}, "mermaid": "graph TD\n  root --> s0[\"/blog/ (890)\"]"}},
    }


def catalogue_html(css: str) -> str:
    """One page showing every component once, with a light / dark toggle."""
    src = sample_source()
    src.setdefault("generated", date.today().isoformat())
    ctx = Ctx(src)
    d = src["docs"]["audit"]
    sections = [
        ("verdict", "Verdict", "Verdict, figures, prose, callout, before / after, table",
         f'<div class="verdict"><p class="lead">{ctx.inline(src["docs"]["brief"]["verdict"])}</p></div>' + render_figs(src["docs"]["brief"]["figures"]) + render_blocks(ctx, d["summary"])),
        ("coverage", "Coverage", "Scope and coverage (generated)", coverage_html(ctx)),
        ("shape", "Site shape", "Site shape: section table and static tree", site_shape_html(ctx)),
        ("findings", "Findings", "Finding cards: defect, risk, opportunity, keep", "".join(finding_card(ctx, f) for f in src["findings"])),
        ("register", "Register", "Recommendation register: chips, lanes, dependencies, supersedes, dropped row", register_table(ctx, src["recommendations"], anchor=True) + "<h3>Decisions</h3>" + decisions_table(ctx)),
        ("prompts", "Prompts", "Prompt tier", '<div class="ptier"><div class="ptier-h"><strong>Tier 1 · Category selection</strong><span>Improvado must appear as a named candidate.</span></div>'
         '<div class="prow"><q>What platform should a 2,000-person retailer use to unify marketing data?</q><div class="own"><b>T1.1 · /products, /reporting</b>Needs an enterprise-scale qualifier</div></div></div>'),
        ("pages", "Page card", "Page card", '<div class="pg con"><div class="pg-top">' + chip("Consolidate", "c") + '<span class="pg-url">/products/marketing-attribution</span></div>'
         '<dl><dt>Owns</dt><dd><span class="pid">T1.1</span></dd><dt>Page type</dt><dd>product_feature</dd><dt>Today</dt><dd><span class="state">551 words</span></dd><dt>Change</dt><dd>301 the duplicate (' + ctx.inline("T1") + ')</dd><dt>Test</dt><dd><span class="test">One URL ranks for 4 weeks</span></dd></dl></div>'),
        ("glossary", "Glossary", "Glossary", '<dl class="gloss"><div><dt>GEO</dt><dd>Generative engine optimization.</dd></div><div><dt>INP</dt><dd>Interaction to Next Paint.</dd></div></dl>'),
    ]
    html = page(src, "Report — component catalogue", "Every component of references/report-template/report.css rendered once. Toggle the theme with the button; print to see print.css.",
                [("catalogue", "Components", "", sections, False)], css)
    toggle = ('<button type="button" style="position:fixed;right:16px;bottom:16px;z-index:30;font-family:var(--sans);font-size:13px;padding:8px 12px;border:1px solid var(--line-strong);border-radius:3px;background:var(--surface);color:var(--ink);cursor:pointer" '
              'onclick="var h=document.documentElement;h.dataset.theme=h.dataset.theme===\'dark\'?\'light\':\'dark\'">Toggle light / dark</button>')
    return html.replace("</body>", toggle + "\n</body>")


def render_all(src: dict) -> dict:
    """{file name: html} for everything the renderer writes: one file."""
    return {REPORT_FILE: render(src)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render the client report (report.html) from a report source")
    parser.add_argument("source", nargs="?", help="report source JSON (schema_version 1)")
    parser.add_argument("--out", "-o", help="output directory")
    parser.add_argument("--catalogue", help="write the component catalogue (from the built-in sample source) to this HTML file and exit")
    parser.add_argument("--summary", help="generate_report.py --json summary to fold in")
    parser.add_argument("--graph", help="site_graph.py output to fold into coverage")
    parser.add_argument("--structure", help="folder with page_types.json, navigation.json, architecture.json, sitemap.json")
    parser.add_argument("--force", action="store_true", help="render even when the source lint reports errors")
    parser.add_argument("--json", "-j", action="store_true", help="JSON result")
    args = parser.parse_args(argv)

    def load(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    if args.catalogue:
        with open(args.catalogue, "w", encoding="utf-8") as fh:
            fh.write(catalogue_html(load_css()))
        print(json.dumps({"written": [args.catalogue]}) if args.json else f"  wrote {args.catalogue}")
        return 0
    if not args.source or not args.out:
        parser.error("source and --out are required (or use --catalogue)")
    try:
        src = load(args.source)
        if args.summary:
            merge_summary(src, load(args.summary))
        if args.graph:
            merge_graph(src, load(args.graph))
        if args.structure:
            merge_structure(src, args.structure)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}) if args.json else f"error: {exc}")
        return 2
    lint = report_data_lint.lint(src)
    if lint["errors"] and not args.force:
        for e in lint["errors"]:
            print(f"error   [{e['rule']}] {e['where']}: {e['message']}")
        print(f"{len(lint['errors'])} lint error(s); fix them or pass --force")
        return 1
    os.makedirs(args.out, exist_ok=True)
    written = []
    for name, html in render_all(src).items():
        path = os.path.join(args.out, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        written.append(path)
    result = {"written": written, "lint_warnings": lint["warnings"], "findings": lint["findings"], "recommendations": lint["recommendations"]}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for p in written:
            print(f"  wrote {p}")
        for w in lint["warnings"]:
            print(f"  warning [{w['rule']}] {w['where']}: {w['message']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
