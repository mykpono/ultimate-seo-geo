#!/usr/bin/env python3
"""
Navigation checker: what the site's global navigation, footer and
breadcrumbs actually link to, and what they leave out.

Every other checker in this repo removes <nav>, <header> and <footer> as
noise, so "pricing is not in the navigation" has never been a finding the
scripts could make. This one reads the site graph (scripts/site_graph.py)
and:

  * extracts the PRIMARY navigation (header and nav landmarks outside the
    footer), the FOOTER navigation, and the breadcrumb trail per page;
  * treats a link as GLOBAL when it appears in the same place on at least
    80% of the sampled pages (ui-discovery's boilerplate heuristic), and
    also finds REPEATING links outside any landmark — the footer built from
    plain <div>s that landmark-only attribution cannot see;
  * checks that money pages (pricing, features, solutions, categories,
    contact) are reachable from the global navigation, that global links
    are not broken or redirected, that the footer is not a link dump, that
    nav anchors carry meaning, and that the visible breadcrumb agrees with
    the BreadcrumbList JSON-LD;
  * reports the top-level taxonomy the navigation defines, for the
    site-architecture audit.

Findings are display-only (not weighted in the Health Score). A raw-HTML
navigation with fewer than three links is reported as NOT MEASURED, never as
"no navigation": JavaScript-rendered chrome is invisible to a plain fetch.

Usage:
    python navigation_checker.py https://example.com
    python navigation_checker.py https://example.com --graph site_graph.json --json
    python navigation_checker.py https://example.com --sample 20 --site-type saas
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from urllib.parse import urlparse

import page_type_classifier as ptc
import site_graph

GLOBAL_SHARE = 0.80            # a link is global when it is on >= 80% of sampled pages
MIN_PAGES_FOR_GLOBAL = 3       # below this, the homepage's chrome stands in for "global"
MIN_RAW_NAV_LINKS = 3          # fewer landmark links than this in raw HTML => not measured
FOOTER_DUMP_ABS = 100          # footer links beyond which it is a link dump
FOOTER_DUMP_RATIO = 3.0        # ...or more than this many times the primary nav (and > 40)
FOOTER_DUMP_MIN = 40
GENERIC_ANCHORS = frozenset({"learn more", "click here", "read more", "here", "more", "link", "this", "see more", "view", "go"})

# Page types that should be one click from the global navigation, with the
# severity when they exist on the site but no instance is linked from it.
NAV_EXPECTED = {
    "saas": {"pricing": "High", "product_feature": "High", "solution_use_case": "Medium", "contact": "Medium",
             "docs_help": "Low", "comparison": "Low", "case_study": "Low", "integration": "Low"},
    "ecommerce": {"ecom_category": "High", "contact": "Medium", "about_company": "Low", "faq": "Low"},
    "local": {"location_service": "High", "contact": "High", "about_company": "Medium"},
    "publisher": {"tag_archive": "Medium", "about_company": "Low", "author": "Low"},
    "docs": {"docs_help": "Medium"},
    "generic": {"pricing": "Medium", "product_feature": "Medium", "contact": "Low", "about_company": "Low"},
}


# ---------------------------------------------------------------------------
# Sampling and boilerplate
# ---------------------------------------------------------------------------

def sample_pages(graph: dict, sample: int) -> list[dict]:
    """Homepage first, then a spread across first directories and depths."""
    pages = list(graph.get("pages", {}).values())
    if not pages:
        return []
    pages.sort(key=lambda p: (p.get("depth", 9), p["url"]))
    home = [p for p in pages if p.get("depth") == 0][:1]
    rest = [p for p in pages if p not in home]
    picked, seen_dirs = list(home), set()
    for p in rest:  # one per first directory first, so the sample spans sections
        d = (p.get("parts") or site_graph.url_parts(p["url"]))["dir_1"]
        if d not in seen_dirs:
            picked.append(p)
            seen_dirs.add(d)
        if len(picked) >= sample:
            break
    for p in rest:
        if len(picked) >= sample:
            break
        if p not in picked:
            picked.append(p)
    return picked[:sample]


def _placement(link: dict) -> str | None:
    """Which global set a link belongs to, by region and container."""
    region, container = link.get("region"), link.get("container", "other")
    if region == "breadcrumb":
        return None
    if container == "footer" or region == "footer":
        return "footer"
    if region in ("nav", "header") or container == "header":
        return "primary"
    if region in ("main", "other", "aside"):
        return "unlabelled"
    return None


def global_links(pages: list[dict]) -> dict:
    """Links that repeat across the sample, per placement.

    Returns {"primary": [...], "footer": [...], "repeating_unlabelled": [...],
    "threshold_pages": n, "method": str}. Each entry: key, href, anchor, pages
    (count), share, region, internal.
    """
    n = len(pages)
    per_place: dict[str, dict[str, dict]] = {"primary": {}, "footer": {}, "unlabelled": {}}
    for page in pages:
        seen_here: set[tuple[str, str]] = set()
        for link in page.get("out_links", []):
            place = _placement(link)
            if not place:
                continue
            ident = link["key"] or link["href"]
            if (place, ident) in seen_here:
                continue
            seen_here.add((place, ident))
            slot = per_place[place].setdefault(ident, {
                "key": link["key"], "href": link["href"], "anchor": link["anchor"], "anchors": Counter(),
                "pages": 0, "region": link["region"], "internal": link["internal"],
            })
            slot["pages"] += 1
            slot["anchors"][link["anchor"].strip().lower()] += 1

    if n >= MIN_PAGES_FOR_GLOBAL:
        threshold = max(2, int(-(-GLOBAL_SHARE * n // 1)))  # ceil
        method = f"links present on >= {threshold} of {n} sampled pages ({GLOBAL_SHARE:.0%})"
    else:
        threshold = 1
        method = f"only {n} page(s) sampled: the homepage's chrome stands in for the global set"

    def pick(place):
        out = []
        for slot in per_place[place].values():
            if slot["pages"] >= threshold:
                s = dict(slot)
                s["anchor"] = slot["anchors"].most_common(1)[0][0] if slot["anchors"] else slot["anchor"]
                s["share"] = round(slot["pages"] / n, 2)
                del s["anchors"]
                out.append(s)
        out.sort(key=lambda s: (-s["pages"], s["href"]))
        return out

    primary, footer = pick("primary"), pick("footer")
    labelled = {s["key"] or s["href"] for s in primary + footer}
    unlabelled = [s for s in pick("unlabelled") if (s["key"] or s["href"]) not in labelled]
    # A page's link to itself (logo) is chrome, not navigation, but keep it out of the counts.
    return {"primary": primary, "footer": footer, "repeating_unlabelled": unlabelled, "threshold_pages": threshold, "method": method}


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def breadcrumb_checks(pages: list[dict]) -> dict:
    """Visible breadcrumb vs BreadcrumbList JSON-LD, and where breadcrumbs are missing."""
    deep = [p for p in pages if (p.get("depth") or 0) >= 1 and (p.get("parts") or site_graph.url_parts(p["url"]))["depth"] >= 2]
    with_visible = [p for p in pages if p.get("breadcrumb_visible")]
    with_schema = [p for p in pages if p.get("breadcrumb_jsonld")]
    mismatches, schema_only, visible_only = [], [], []
    for p in pages:
        vis = [_norm(a) for a in p.get("breadcrumb_visible") or []]
        sch = [_norm(a) for a in p.get("breadcrumb_jsonld") or []]
        if vis and sch:
            # Every visible crumb must appear in the schema list, in order.
            it = iter(sch)
            ok = all(any(v == s for s in it) for v in vis)
            if not ok:
                mismatches.append({"url": p["url"], "visible": p["breadcrumb_visible"][:6], "jsonld": p["breadcrumb_jsonld"][:6]})
        elif sch and not vis:
            schema_only.append(p["url"])
        elif vis and not sch:
            visible_only.append(p["url"])
    uses = len(with_visible) + len(with_schema) > 0
    missing_deep = [p["url"] for p in deep if not p.get("breadcrumb_visible") and not p.get("breadcrumb_jsonld")] if uses else []
    return {
        "pages_sampled": len(pages),
        "deep_pages": len(deep),
        "with_visible": len(with_visible),
        "with_jsonld": len(with_schema),
        "mismatches": mismatches,
        "jsonld_only": schema_only[:10],
        "visible_only": visible_only[:10],
        "missing_on_deep_pages": missing_deep[:10],
        "missing_on_deep_pages_count": len(missing_deep),
    }


def analyze(graph: dict, site_type: str = "auto", sample: int = 40) -> dict:
    pages_all = graph.get("pages", {})
    pages = sample_pages(graph, sample)
    home = next((p for p in pages if p.get("depth") == 0), pages[0] if pages else None)
    issues: list[dict] = []

    # Page types, for the money-page and taxonomy checks.
    types = ptc.classify_site(graph, site_type=site_type)
    labels = {k: v["label"] for k, v in types["pages"].items()}
    chosen_type = types["site_type"]

    glob = global_links(pages)
    primary, footer, repeating = glob["primary"], glob["footer"], glob["repeating_unlabelled"]

    # Raw-HTML navigation present at all?
    home_landmark_links = 0
    if home:
        home_landmark_links = sum(1 for l in home.get("out_links", []) if l.get("region") in ("nav", "header") or l.get("container") == "header")
    measured = home_landmark_links >= MIN_RAW_NAV_LINKS or len(primary) >= MIN_RAW_NAV_LINKS
    if not measured:
        rep_note = f"; {len(repeating)} link(s) repeat outside landmarks and were used instead" if repeating else ""
        issues.append({
            "type": "nav_not_measured",
            "severity": "Info",
            "finding": "Global navigation could not be measured from raw HTML.",
            "evidence": f"Homepage has {home_landmark_links} link(s) inside header/nav landmarks (threshold {MIN_RAW_NAV_LINKS}){rep_note}.",
            "impact": "If the navigation is rendered by JavaScript, crawlers that do not execute it (most AI crawlers) see no site structure; if it uses plain <div>s, assistive tech and this audit cannot tell it apart from content.",
            "fix": "Confirm with `render_page.py` or the Rich Results Test whether the nav exists in rendered HTML; if it is JS-only, server-render it; if it is <div>-based, wrap it in <header><nav>.",
            "confidence": "Confirmed",
        })

    nav_targets = {s["key"] for s in primary if s["key"]}
    footer_targets = {s["key"] for s in footer if s["key"]}
    repeating_targets = {s["key"] for s in repeating if s["key"]}
    reachable = nav_targets | footer_targets | repeating_targets

    # Money pages not reachable from the global chrome.
    expected = NAV_EXPECTED.get(chosen_type, NAV_EXPECTED["generic"])
    by_label: dict[str, list[str]] = defaultdict(list)
    for key, label in labels.items():
        by_label[label].append(key)
    for label, severity in expected.items():
        keys = by_label.get(label, [])
        if not keys:
            continue  # absence is page_type_classifier's finding, not this one
        linked = [k for k in keys if k in reachable]
        if linked:
            continue
        if not measured:
            severity = "Info"
        elif len(keys) < 3 and severity in ("High", "Medium"):
            severity = "Low"  # one or two such pages: a thin signal that the type exists at all
        example = sorted(keys)[:3]
        issues.append({
            "type": "money_page_not_in_nav",
            "severity": severity,
            "finding": f"No {label.replace('_', ' ')} page is linked from the global navigation or footer in raw HTML.",
            "evidence": f"{len(keys)} {label} page(s) exist (e.g. {', '.join(example)}); none of them is among the {len(nav_targets)} primary-nav or {len(footer_targets)} footer targets{' or the ' + str(len(repeating_targets)) + ' repeating unlabelled links' if repeating_targets else ''}.",
            "impact": "Pages outside the global navigation get link equity only from in-content links and sit deeper in the crawl; buyers and AI crawlers landing anywhere on the site cannot reach them in one click.",
            "fix": f"Add the {label.replace('_', ' ')} hub (or the top page of that type) to the primary navigation; at minimum link it from the footer.",
            "confidence": "Likely" if measured else "Hypothesis",
            "label": label,
            "pages": example,
        })

    # Broken or redirected global links.
    failed = {f["url"]: f for f in graph.get("crawl", {}).get("failed", [])}
    failed_keys = {site_graph.page_key(u): f for u, f in failed.items()}
    broken, redirected = [], []
    for s in primary + footer:
        if not s["internal"] or not s["key"]:
            continue
        page = pages_all.get(s["key"])
        if page is None:
            f = failed_keys.get(s["key"])
            if f and (f.get("status") or 0) >= 400:
                broken.append({"href": s["href"], "anchor": s["anchor"], "status": f.get("status")})
            continue
        if page.get("redirected"):
            redirected.append({"href": s["href"], "anchor": s["anchor"], "final_url": page.get("final_url")})
    if broken:
        issues.append({
            "type": "nav_link_broken",
            "severity": "High",
            "finding": f"{len(broken)} global navigation link(s) return an error on every page.",
            "evidence": "; ".join(f"{b['anchor'] or b['href']} -> HTTP {b['status']}" for b in broken[:5]),
            "impact": "A broken link in the chrome is broken site-wide: every page passes equity to a dead URL and every visitor can hit it.",
            "fix": "Fix or remove the target; re-run `broken_links.py` to confirm.",
            "confidence": "Confirmed",
            "links": broken[:10],
        })
    if redirected:
        issues.append({
            "type": "nav_link_redirect",
            "severity": "Medium",
            "finding": f"{len(redirected)} global navigation link(s) point at a redirect.",
            "evidence": "; ".join(f"{r['href']} -> {r['final_url']}" for r in redirected[:5]),
            "impact": "Site-wide redirect hops waste crawl budget and dilute the equity the navigation passes.",
            "fix": "Point the navigation at the final URL.",
            "confidence": "Confirmed",
            "links": redirected[:10],
        })

    # Footer link dump: internal links only — a corporate footer full of links to
    # the parent company's domain dilutes nothing on this site.
    footer_internal = [s for s in footer if s["internal"]]
    primary_internal = [s for s in primary if s["internal"]]
    if footer_internal and (len(footer_internal) > FOOTER_DUMP_ABS or (len(footer_internal) > FOOTER_DUMP_MIN and primary_internal and len(footer_internal) > FOOTER_DUMP_RATIO * len(primary_internal))):
        issues.append({
            "type": "footer_link_dump",
            "severity": "Low",
            "finding": f"The footer carries {len(footer_internal)} global internal links.",
            "evidence": f"{len(footer_internal)} internal footer links vs {len(primary_internal)} internal primary-nav links on {glob['threshold_pages']}+ of {len(pages)} sampled pages.",
            "impact": "Hundreds of site-wide footer links flatten the internal link graph: every page passes a sliver of equity everywhere and the hubs that matter get no more than the legal pages.",
            "fix": "Keep the footer to the sections, trust pages and legal links; move deep links to hub pages that the footer links to.",
            "confidence": "Likely",
        })

    # Generic anchors and one anchor pointing at several URLs.
    generic = [s for s in primary if _norm(s["anchor"]) in GENERIC_ANCHORS or not _norm(s["anchor"])]
    anchor_targets: dict[str, set] = defaultdict(set)
    for s in primary:
        if s["key"]:
            anchor_targets[_norm(s["anchor"])].add(s["key"])
    ambiguous = {a: sorted(t) for a, t in anchor_targets.items() if a and len(t) > 1}
    if generic or ambiguous:
        ev = []
        if generic:
            ev.append("empty or generic anchors: " + ", ".join(f"'{s['anchor'] or '(empty)'}' -> {s['href']}" for s in generic[:4]))
        if ambiguous:
            ev.append("same anchor, different targets: " + "; ".join(f"'{a}' -> {len(t)} URLs" for a, t in list(ambiguous.items())[:3]))
        issues.append({
            "type": "nav_generic_anchor",
            "severity": "Low",
            "finding": f"{len(generic)} generic and {len(ambiguous)} ambiguous anchor(s) in the primary navigation.",
            "evidence": "; ".join(ev),
            "impact": "Nav anchors are the strongest site-wide relevance signal a page gets; 'Learn more' and empty icon links pass none.",
            "fix": "Use the page's topic as the anchor (add visually-hidden text to icon links).",
            "confidence": "Confirmed",
        })

    # Breadcrumbs.
    bc = breadcrumb_checks(pages)
    if bc["mismatches"]:
        m = bc["mismatches"][0]
        issues.append({
            "type": "breadcrumb_schema_mismatch",
            "severity": "Medium",
            "finding": f"Visible breadcrumb and BreadcrumbList JSON-LD disagree on {len(bc['mismatches'])} sampled page(s).",
            "evidence": f"{m['url']}: visible {m['visible']} vs JSON-LD {m['jsonld']}",
            "impact": "Google requires structured data to match visible content; a mismatch forfeits the breadcrumb rich result and, repeated site-wide, reads as misleading markup.",
            "fix": "Generate BreadcrumbList from the same data as the rendered trail (same names, same order; the current page may be the last item).",
            "confidence": "Confirmed",
            "pages": [x["url"] for x in bc["mismatches"][:10]],
        })
    if bc["missing_on_deep_pages_count"]:
        issues.append({
            "type": "breadcrumb_missing",
            "severity": "Low",
            "finding": f"{bc['missing_on_deep_pages_count']} of {bc['deep_pages']} sampled deep page(s) have no breadcrumb although the site uses them.",
            "evidence": f"e.g. {', '.join(bc['missing_on_deep_pages'][:3])}",
            "impact": "Inconsistent breadcrumbs give crawlers and users an incomplete map of the hierarchy and lose a cheap internal link to each parent hub.",
            "fix": "Render the breadcrumb (and BreadcrumbList) on every page below the first level.",
            "confidence": "Likely",
            "pages": bc["missing_on_deep_pages"],
        })
    elif bc["deep_pages"] >= 3 and not bc["with_visible"] and not bc["with_jsonld"] and chosen_type in ("ecommerce", "docs", "publisher"):
        issues.append({
            "type": "breadcrumb_absent",
            "severity": "Low",
            "finding": "No breadcrumbs on any sampled page.",
            "evidence": f"{bc['deep_pages']} sampled pages are two or more levels deep; none has a breadcrumb trail or BreadcrumbList JSON-LD.",
            "impact": f"On a {chosen_type} site the hierarchy is the navigation; without breadcrumbs each deep page links up to nothing and the SERP shows a raw URL instead of a path.",
            "fix": "Add a visible breadcrumb inside <nav aria-label=\"breadcrumb\"> plus matching BreadcrumbList JSON-LD.",
            "confidence": "Likely",
        })
    if bc["jsonld_only"] and not bc["with_visible"]:
        issues.append({
            "type": "breadcrumb_jsonld_only",
            "severity": "Low",
            "finding": f"BreadcrumbList JSON-LD without a visible breadcrumb on {len(bc['jsonld_only'])} sampled page(s).",
            "evidence": f"e.g. {', '.join(bc['jsonld_only'][:3])}",
            "impact": "Structured data must reflect visible content; invisible breadcrumbs are markup without the user benefit and may be ignored.",
            "fix": "Render the trail the markup describes.",
            "confidence": "Likely",
        })

    # Taxonomy the navigation defines.
    taxonomy = []
    for s in primary:
        if not s["internal"] or not s["key"]:
            continue
        parts = site_graph.url_parts(s["href"])
        taxonomy.append({"anchor": s["anchor"], "href": s["href"], "dir_1": parts["dir_1"], "label": labels.get(s["key"], ptc.classify_url(s["href"])["label"]), "share": s["share"]})
    sections = sorted({t["dir_1"] for t in taxonomy if t["dir_1"]})

    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
    issues.sort(key=lambda i: order.get(i["severity"], 9))
    for i in issues:
        if not measured and i["type"] not in ("nav_not_measured",) and i["severity"] in ("High", "Medium"):
            i["severity"] = "Info"
            i["confidence"] = "Hypothesis"
            i["evidence"] += " (navigation not measured from raw HTML; see nav_not_measured)"
    issues.sort(key=lambda i: order.get(i["severity"], 9))

    return {
        "site": graph.get("site"),
        "site_type": chosen_type,
        "status": "measured" if measured else "not_measured",
        "sampled_pages": len(pages),
        "method": glob["method"],
        "primary_nav": {"count": len(primary), "internal": sum(1 for s in primary if s["internal"]), "links": primary[:150]},
        "footer_nav": {"count": len(footer), "internal": sum(1 for s in footer if s["internal"]), "links": footer[:200]},
        "repeating_unlabelled": {"count": len(repeating), "links": repeating[:60]},
        "taxonomy": {"sections": sections, "nav_links": taxonomy[:80]},
        "breadcrumbs": bc,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(r: dict) -> None:
    print(f"\n🧭 Navigation: {r['site']}  ({r['site_type']}, {r['status']})")
    print(f"   Sampled {r['sampled_pages']} page(s); {r['method']}")
    print(f"   Primary nav: {r['primary_nav']['count']} global links ({r['primary_nav']['internal']} internal)")
    for t in r["taxonomy"]["nav_links"][:20]:
        print(f"     - {t['anchor'][:40]:<40} {t['href']}  [{t['label']}]")
    print(f"   Footer: {r['footer_nav']['count']} global links ({r['footer_nav']['internal']} internal)")
    if r["repeating_unlabelled"]["count"]:
        print(f"   Repeating links outside landmarks: {r['repeating_unlabelled']['count']} (a <div>-built header/footer?)")
    bc = r["breadcrumbs"]
    print(f"   Breadcrumbs: visible on {bc['with_visible']}, JSON-LD on {bc['with_jsonld']}, mismatches {len(bc['mismatches'])}, missing on {bc['missing_on_deep_pages_count']} deep page(s)")
    if r["issues"]:
        print("\n   Findings:")
        for i in r["issues"]:
            print(f"     [{i['severity']}] {i['finding']}")
            print(f"        fix: {i['fix']}")
    else:
        print("\n   No navigation findings.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit global navigation, footer and breadcrumbs from a site graph")
    parser.add_argument("url", help="Site URL (homepage)")
    parser.add_argument("--graph", help="site_graph.py output to read instead of crawling")
    parser.add_argument("--sample", type=int, default=40, help="Pages to use for the boilerplate analysis (default 40)")
    parser.add_argument("--site-type", choices=ptc.SITE_TYPES, default="auto", help="Business type for the money-page check (default auto)")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.graph:
        graph = site_graph.load_graph(args.graph)
    else:
        graph = site_graph.build_graph(args.url, max_pages=max(2, args.sample), max_depth=1)
    result = analyze(graph, site_type=args.site_type, sample=max(1, args.sample))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_summary(result)


if __name__ == "__main__":
    main()
