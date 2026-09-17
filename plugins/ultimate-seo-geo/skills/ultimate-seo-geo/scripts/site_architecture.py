#!/usr/bin/env python3
"""
Site architecture audit: the site as a tree of sections, and how link
equity, navigation and depth are distributed across it.

references/industry-templates.md prescribes an ideal tree per business type;
nothing measured the real one. This script reads the site graph
(scripts/site_graph.py), the page labels (page_type_classifier.py) and the
global navigation (navigation_checker.py) and reports:

  * SECTIONS by first directory (split one level further when a section
    holds most of the site): URL count and share, dominant page type,
    whether a hub page exists at the section root, whether the primary
    navigation or footer links into it, click depth and word count of the
    fetched pages, and which sitemap file lists it;
  * LINK EQUITY by section — PageRank (d = 0.85) over the fetched pages,
    in-content links weighted 1.0 and chrome links (nav, header, footer,
    breadcrumb) 0.25, summed per section. Only on a COMPLETE crawl: a
    partial graph misattributes equity, so anything less is reported as
    "not measured";
  * FINDINGS, display-only: a money section starved of equity while an
    informational one hoards it, a large section the navigation never
    links into, a section with no hub page, money sections buried deep,
    and URL hygiene (deep paths, mixed case, slash inconsistency, dated
    evergreen URLs, query strings in the sitemap);
  * a Mermaid tree of the top sections for the report.

Usage:
    python site_architecture.py https://example.com
    python site_architecture.py https://example.com --graph site_graph.json --json
    python site_architecture.py https://example.com --site-type ecommerce
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from urllib.parse import urlparse

import navigation_checker as navc
import page_type_classifier as ptc
import site_graph

DAMPING = 0.85
ITERATIONS = 50
CHROME_WEIGHT = 0.25           # nav / header / footer / breadcrumb links vs 1.0 for in-content links
CHROME_REGIONS = frozenset({"nav", "header", "footer", "breadcrumb"})
SPLIT_SHARE = 0.40             # a section holding more than this is split by its second directory
SPLIT_MIN_URLS = 50
BIG_SECTION_SHARE = 0.05       # sections at least this big must be in the navigation
BIG_SECTION_MIN_URLS = 5
HUB_MIN_URLS = 5               # a section this big should have a hub page at its root
EQUITY_STARVED = 0.05          # a money section under this share of equity ...
EQUITY_HOARD = 0.60            # ... while one informational section holds more than this
DEEP_MONEY_DEPTH = 3.0         # average click depth beyond which a money section is buried
DEEP_PATH = 4                  # path segments beyond which a URL is "deep"
DEEP_PATH_SHARE = 0.20
MONEY_INTENTS = frozenset({"BOFU", "MOFU"})
INFO_INTENTS = frozenset({"TOFU", "support"})
STRUCTURE_INTENTS = frozenset({"TOFU", "MOFU", "BOFU", "support", "trust"})
EVERGREEN_TYPES = frozenset({"product_feature", "pricing", "docs_help", "solution_use_case", "ecom_category", "ecom_product", "location_service"})
EQUITY_MIN_PAGES = 10          # equity over fewer fetched pages says nothing about the site
EQUITY_MIN_SITEMAP_COVERAGE = 0.8  # ...and the crawl must have reached most of what the sitemap lists
_YEAR = re.compile(r"^(19|20)\d{2}$")


# ---------------------------------------------------------------------------
# Inventory and sections
# ---------------------------------------------------------------------------

def inventory(graph: dict) -> dict[str, dict]:
    """Every known URL keyed like the graph: {key: {url, fetched, sitemap_source, lastmod}}."""
    inv: dict[str, dict] = {}
    for key, page in graph.get("pages", {}).items():
        inv[key] = {"url": page["url"], "fetched": True, "status": page.get("status"), "sitemap_source": None, "lastmod": None}
    for url, meta in graph.get("sitemap", {}).get("urls", {}).items():
        key = site_graph.page_key(url)
        row = inv.setdefault(key, {"url": url, "fetched": False, "status": None, "sitemap_source": None, "lastmod": None})
        row["sitemap_source"] = meta.get("source")
        row["lastmod"] = meta.get("lastmod")
    return inv


def section_of(url: str) -> tuple[str | None, str | None]:
    """(dir_1, dir_2) with a locale prefix skipped, as the classifier does."""
    parts = site_graph.url_parts(url)
    dirs = parts["dirs"]
    if dirs and ptc._LOCALE_SEGMENT.match(f"/{dirs[0]}/"):
        dirs = dirs[1:]
    return (dirs[0] if dirs else None, dirs[1] if len(dirs) > 1 else None)


def build_sections(inv: dict[str, dict], labels: dict[str, str], pages: dict[str, dict]) -> list[dict]:
    total = len(inv) or 1
    rows: dict[tuple, dict] = {}

    def _row(path, parent=None):
        return rows.setdefault(path, {
            "path": path, "parent": parent, "url_count": 0, "keys": [], "labels": Counter(),
            "fetched": 0, "depths": [], "words": [], "sources": Counter(), "hub_key": None,
        })

    for key, row in inv.items():
        d1, d2 = section_of(row["url"])
        path = f"/{d1}/" if d1 else "/"
        sec = _row(path)
        sec["url_count"] += 1
        sec["keys"].append(key)
        sec["labels"][labels.get(key, "generic")] += 1
        if row["sitemap_source"]:
            sec["sources"][row["sitemap_source"]] += 1
        page = pages.get(key)
        if page:
            sec["fetched"] += 1
            if page.get("depth") is not None:
                sec["depths"].append(page["depth"])
            if page.get("word_count") is not None:
                sec["words"].append(page["word_count"])
        parts = site_graph.url_parts(row["url"])
        if d1 and parts["depth"] == 1 or (d1 and parts["depth"] == 2 and ptc._LOCALE_SEGMENT.match(f"/{parts['dirs'][0]}/")):
            sec["hub_key"] = key  # the section root itself is a known page

    # Split dominant sections one level down.
    for path, sec in list(rows.items()):
        if path == "/" or sec["url_count"] < SPLIT_MIN_URLS or sec["url_count"] / total <= SPLIT_SHARE:
            continue
        for key in sec["keys"]:
            d1, d2 = section_of(inv[key]["url"])
            if not d2:
                continue
            sub = _row(f"{path}{d2}/", parent=path)
            sub["url_count"] += 1
            sub["keys"].append(key)
            sub["labels"][labels.get(key, "generic")] += 1
            page = pages.get(key)
            if page:
                sub["fetched"] += 1
                if page.get("depth") is not None:
                    sub["depths"].append(page["depth"])
                if page.get("word_count") is not None:
                    sub["words"].append(page["word_count"])
            if site_graph.url_parts(inv[key]["url"])["depth"] == 2:
                sub["hub_key"] = key
        # Keep only meaningful subsections.
        for sub_path in [p for p, r in rows.items() if r["parent"] == path and r["url_count"] < HUB_MIN_URLS]:
            del rows[sub_path]

    out = []
    for path, sec in rows.items():
        dominant, dom_n = (sec["labels"].most_common(1)[0] if sec["labels"] else ("generic", 0))
        intent = ptc._BY_LABEL.get(dominant, {}).get("intent", "meta")
        hub_page = pages.get(sec["hub_key"]) if sec["hub_key"] else None
        out.append({
            "path": path,
            "parent": sec["parent"],
            "url_count": sec["url_count"],
            "share": round(sec["url_count"] / total, 3),
            "dominant_label": dominant,
            "dominant_share": round(dom_n / sec["url_count"], 2) if sec["url_count"] else 0,
            "intent": intent,
            "labels": dict(sec["labels"].most_common(5)),
            "fetched": sec["fetched"],
            "hub": {"exists": sec["hub_key"] is not None, "key": sec["hub_key"],
                    "status": hub_page.get("status") if hub_page else ("in sitemap" if sec["hub_key"] else None)},
            "avg_depth": round(sum(sec["depths"]) / len(sec["depths"]), 1) if sec["depths"] else None,
            "max_depth": max(sec["depths"]) if sec["depths"] else None,
            "avg_word_count": round(sum(sec["words"]) / len(sec["words"])) if sec["words"] else None,
            "sitemap_source": sec["sources"].most_common(1)[0][0] if sec["sources"] else None,
            "keys": sec["keys"],
        })
    out.sort(key=lambda s: (s["parent"] or "", -s["url_count"], s["path"]))
    return out


# ---------------------------------------------------------------------------
# Link equity
# ---------------------------------------------------------------------------

def pagerank(pages: dict[str, dict], damping: float = DAMPING, iterations: int = ITERATIONS, chrome_weight: float = CHROME_WEIGHT) -> dict[str, float]:
    """Weighted PageRank over the fetched pages' followable internal links.

    In-content links (main, aside, other) weigh 1.0; chrome links (nav,
    header, footer, breadcrumb) weigh ``chrome_weight`` — a documented
    reasonable-surfer choice, not a claim about Google's weights. Links to
    pages outside ``pages``, nofollow links and self-links are dropped.
    Dangling pages spread their score uniformly. Scores sum to 1.
    """
    keys = list(pages)
    n = len(keys)
    if n == 0:
        return {}
    index = {k: i for i, k in enumerate(keys)}
    out_w: list[dict[int, float]] = [dict() for _ in keys]
    for k, page in pages.items():
        i = index[k]
        for link in page.get("out_links", []):
            if not link.get("internal") or not link.get("key") or link["key"] == k:
                continue
            if "nofollow" in (link.get("rel") or []):
                continue
            j = index.get(link["key"])
            if j is None:
                continue
            w = chrome_weight if link.get("region") in CHROME_REGIONS else 1.0
            out_w[i][j] = out_w[i].get(j, 0.0) + w
    totals = [sum(d.values()) for d in out_w]
    score = [1.0 / n] * n
    for _ in range(iterations):
        dangling = sum(score[i] for i in range(n) if totals[i] == 0)
        new = [(1 - damping) / n + damping * dangling / n] * n
        for i in range(n):
            if totals[i] == 0:
                continue
            share = damping * score[i] / totals[i]
            for j, w in out_w[i].items():
                new[j] += share * w
        score = new
    s = sum(score) or 1.0
    return {k: score[index[k]] / s for k in keys}


def normalise_log(scores: dict[str, float]) -> dict[str, int]:
    """0-100 on a log scale (crawlobserver's presentation): 100 for the top page."""
    if not scores:
        return {}
    lo, hi = min(scores.values()), max(scores.values())
    if lo <= 0 or hi <= lo:
        return {k: 100 for k in scores}
    span = math.log(hi) - math.log(lo)
    return {k: int(round(100 * (math.log(v) - math.log(lo)) / span)) for k, v in scores.items()}


def equity_gate(graph: dict) -> str | None:
    """Why equity cannot be measured on this graph, or None when it can.

    A crawl is "complete" when every linked page was fetched — which is
    trivially true for a JavaScript homepage with no links in raw HTML
    (lab.mykpono.com: 1 page fetched, 23 in the sitemap, "complete"). Equity
    over that graph is the homepage at 100% and nonsense. So: the crawl must
    be complete, cover at least EQUITY_MIN_PAGES pages, and reach most of
    what the sitemap lists.
    """
    crawl = graph.get("crawl", {})
    pages = graph.get("pages", {})
    sitemap = graph.get("sitemap", {})
    if not crawl.get("complete"):
        return "equity needs a complete crawl: " + "; ".join(crawl.get("reasons") or ["crawl incomplete"])
    if len(pages) < EQUITY_MIN_PAGES:
        return f"only {len(pages)} page(s) fetched; equity needs at least {EQUITY_MIN_PAGES}"
    sm_keys = {site_graph.page_key(u) for u in sitemap.get("urls", {})}
    if sm_keys:
        covered = sum(1 for k in sm_keys if k in pages)
        if covered < EQUITY_MIN_SITEMAP_COVERAGE * len(sm_keys):
            return f"crawl reached {covered} of {len(sm_keys)} sitemap URLs ({covered / len(sm_keys):.0%}); equity needs {EQUITY_MIN_SITEMAP_COVERAGE:.0%}"
    return None


def equity_by_section(graph: dict, sections: list[dict]) -> dict:
    pages = graph.get("pages", {})
    reason = equity_gate(graph)
    if reason:
        return {"status": "not measured", "reason": reason, "by_section": {}, "top_pages": []}
    pr = pagerank(pages)
    norm = normalise_log(pr)
    by_section: dict[str, float] = {}
    for sec in sections:
        by_section[sec["path"]] = round(sum(pr.get(k, 0.0) for k in sec["keys"]), 4)
    top = sorted(pr.items(), key=lambda kv: -kv[1])[:10]
    return {
        "status": "measured",
        "method": f"PageRank d={DAMPING}, {ITERATIONS} iterations, chrome links x{CHROME_WEIGHT}, {len(pages)} fetched pages",
        "by_section": by_section,
        "top_pages": [{"url": pages[k]["url"], "score": norm[k], "share": round(v, 4)} for k, v in top],
    }


# ---------------------------------------------------------------------------
# Hygiene
# ---------------------------------------------------------------------------

def url_hygiene(inv: dict[str, dict], labels: dict[str, str], sitemap_found: bool) -> dict:
    total = len(inv) or 1
    deep, mixed, dated_evergreen, query_in_sitemap, numeric = [], [], [], [], []
    slash_forms: dict[str, set] = defaultdict(set)
    for key, row in inv.items():
        p = site_graph.url_parts(row["url"])
        if p["depth"] > DEEP_PATH:
            deep.append(row["url"])
        if p["mixed_case"]:
            mixed.append(row["url"])
        if p["has_date"] and labels.get(key) in EVERGREEN_TYPES:
            dated_evergreen.append(row["url"])
        if p["has_query"] and row["sitemap_source"]:
            query_in_sitemap.append(row["url"])
        if p["has_numeric_id"]:
            numeric.append(row["url"])
        if p["depth"] >= 1 and row["sitemap_source"]:
            d1, _ = section_of(row["url"])
            slash_forms[d1 or "/"].add(p["trailing_slash"])
    inconsistent = sorted(s for s, forms in slash_forms.items() if len(forms) > 1)
    return {
        "deep_paths": {"count": len(deep), "share": round(len(deep) / total, 3), "examples": deep[:5]},
        "mixed_case": {"count": len(mixed), "examples": mixed[:5]},
        "dated_evergreen": {"count": len(dated_evergreen), "examples": dated_evergreen[:5]},
        "query_in_sitemap": {"count": len(query_in_sitemap), "examples": query_in_sitemap[:5]},
        "numeric_ids": {"count": len(numeric), "share": round(len(numeric) / total, 3)},
        "trailing_slash_inconsistent_sections": inconsistent[:10],
        "sitemap_found": sitemap_found,
    }


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def mermaid_tree(site: str, sections: list[dict], limit: int = 14) -> str:
    host = urlparse(site).netloc or site
    lines = ["graph TD", f'  root["{host}"]']
    top = [s for s in sections if s["parent"] is None and s["path"] != "/"][:limit]
    ids = {}
    for i, s in enumerate(top):
        ids[s["path"]] = f"s{i}"
        lines.append(f'  root --> s{i}["{s["path"]} ({s["url_count"]:,} · {s["dominant_label"]})"]')
    for j, s in enumerate(sec for sec in sections if sec["parent"] in ids):
        lines.append(f'  {ids[s["parent"]]} --> t{j}["{s["path"]} ({s["url_count"]:,} · {s["dominant_label"]})"]')
    return "\n".join(lines)


def analyze(graph: dict, site_type: str = "auto") -> dict:
    pages = graph.get("pages", {})
    inv = inventory(graph)
    types = ptc.classify_site(graph, site_type=site_type)
    labels = {k: v["label"] for k, v in types["pages"].items()}
    chosen = types["site_type"]
    complete = bool(graph.get("sitemap", {}).get("complete")) or bool(graph.get("crawl", {}).get("complete"))

    sections = build_sections(inv, labels, pages)
    nav = navc.analyze(graph, site_type=site_type)
    nav_measured = nav["status"] == "measured"
    nav_keys = {s["key"] for s in nav["primary_nav"]["links"] + nav["footer_nav"]["links"] + nav["repeating_unlabelled"]["links"] if s.get("key")}
    for sec in sections:
        linked = [k for k in sec["keys"] if k in nav_keys]
        sec["in_nav"] = bool(linked)
        sec["nav_targets"] = linked[:3]

    equity = equity_by_section(graph, sections)
    for sec in sections:
        sec["equity_share"] = equity["by_section"].get(sec["path"]) if equity["status"] == "measured" else None

    hygiene = url_hygiene(inv, labels, bool(graph.get("sitemap", {}).get("found")))
    issues = _findings(sections, equity, hygiene, chosen, complete, nav_measured, len(inv))

    slim = [{k: v for k, v in s.items() if k != "keys"} for s in sections]
    return {
        "site": graph.get("site"),
        "site_type": chosen,
        "inventory": {"total": len(inv), "fetched": len(pages), "sitemap_urls": len(graph.get("sitemap", {}).get("urls", {})), "complete": complete,
                      "reasons": (graph.get("sitemap", {}).get("reasons") or []) + (graph.get("crawl", {}).get("reasons") or []) if not complete else []},
        "navigation": {"status": nav["status"], "sections": nav["taxonomy"]["sections"]},
        "sections": slim[:80],
        "equity": equity,
        "hygiene": hygiene,
        "mermaid": mermaid_tree(graph.get("site") or "", sections),
        "issues": issues,
    }


def _findings(sections, equity, hygiene, site_type, complete, nav_measured, total) -> list[dict]:
    issues: list[dict] = []
    top_level = [s for s in sections if s["parent"] is None and s["path"] != "/"]

    # Equity distribution.
    if equity["status"] == "measured":
        starved = [s for s in top_level if s["intent"] in MONEY_INTENTS and s["url_count"] >= BIG_SECTION_MIN_URLS and (s["equity_share"] or 0) < EQUITY_STARVED]
        hoarding = [s for s in top_level if s["intent"] in INFO_INTENTS and (s["equity_share"] or 0) > EQUITY_HOARD]
        if starved and hoarding:
            h = hoarding[0]
            issues.append({
                "type": "section_equity_mismatch",
                "severity": "Medium",
                "finding": f"{h['path']} holds {h['equity_share']:.0%} of internal link equity while {', '.join(s['path'] for s in starved[:3])} get under {EQUITY_STARVED:.0%} each.",
                "evidence": f"{equity['method']}. " + "; ".join(f"{s['path']} {s['dominant_label']} {s['url_count']} URLs -> {(s['equity_share'] or 0):.1%}" for s in [h] + starved[:3]),
                "impact": "The pages that convert are the ones the internal link graph values least; rankings follow equity.",
                "fix": f"Link from the top {h['path']} pages into the {starved[0]['path']} hub and its key pages (in-content, descriptive anchors), and add the hub to the primary navigation.",
                "confidence": "Likely",
                "sections": [s["path"] for s in starved[:5]],
            })
    else:
        issues.append({
            "type": "equity_not_measured",
            "severity": "Info",
            "finding": "Link equity by section was not measured.",
            "evidence": equity.get("reason", "incomplete crawl"),
            "impact": "Cannot say which sections the internal link graph favours.",
            "fix": "Re-run `site_graph.py` with `--max-pages` above the site's page count (and `--depth` high enough) so the crawl completes.",
            "confidence": "Confirmed",
        })

    # Big sections the navigation never links into.
    for s in top_level:
        if s["in_nav"] or s["intent"] not in STRUCTURE_INTENTS:
            continue
        if s["url_count"] < BIG_SECTION_MIN_URLS or s["share"] < BIG_SECTION_SHARE:
            continue
        if _YEAR.match(s["path"].strip("/")):
            continue
        issues.append({
            "type": "section_not_in_nav",
            "severity": "Medium" if nav_measured else "Info",
            "finding": f"{s['path']} is {s['share']:.0%} of the site's URLs but nothing in it is linked from the global navigation or footer.",
            "evidence": f"{s['url_count']} URLs, mostly {s['dominant_label']}; hub page {'exists' if s['hub']['exists'] else 'not found'}" + ("" if nav_measured else " (navigation not measured from raw HTML)"),
            "impact": "A whole section reachable only through in-content links sits deeper in the crawl and gets equity only when individual pages happen to link to it.",
            "fix": f"Add {s['path']} (its hub page) to the primary navigation or the footer.",
            "confidence": "Likely" if nav_measured else "Hypothesis",
            "section": s["path"],
        })

    # Children without a hub.
    for s in top_level:
        if s["hub"]["exists"] or s["url_count"] < HUB_MIN_URLS or s["intent"] not in STRUCTURE_INTENTS:
            continue
        if _YEAR.match(s["path"].strip("/")):
            continue
        issues.append({
            "type": "children_without_hub",
            "severity": "Medium" if complete else "Info",
            "finding": f"{s['path']} has {s['url_count']} pages but no hub page at its root.",
            "evidence": f"{s['path'].rstrip('/') or '/'} is not in the sitemap and was not reached by the crawl; the section is mostly {s['dominant_label']}." + ("" if complete else " Inventory incomplete."),
            "impact": "Without a hub, the section's pages have no parent to consolidate internal links, breadcrumbs point nowhere, and the category-level query has no landing page.",
            "fix": f"Publish {s['path']} as a hub that lists and links every page in the section, add it to the navigation, and point the pages' breadcrumbs at it.",
            "confidence": "Likely" if complete else "Hypothesis",
            "tags": ["opportunity"],
            "section": s["path"],
        })

    # Money sections buried deep.
    for s in top_level:
        if s["intent"] in MONEY_INTENTS and s["avg_depth"] is not None and s["fetched"] >= 3 and s["avg_depth"] > DEEP_MONEY_DEPTH:
            issues.append({
                "type": "deep_section",
                "severity": "Low",
                "finding": f"{s['path']} pages sit {s['avg_depth']} clicks from the homepage on average.",
                "evidence": f"{s['fetched']} fetched pages, max depth {s['max_depth']}, mostly {s['dominant_label']}.",
                "impact": "Crawlers and users reach conversion pages last; depth correlates with lower crawl frequency and equity.",
                "fix": "Link the section hub from the navigation and its top pages from the homepage or hub.",
                "confidence": "Likely",
                "section": s["path"],
            })

    # URL hygiene.
    h = hygiene
    if h["deep_paths"]["share"] > DEEP_PATH_SHARE and h["deep_paths"]["count"] >= 10:
        issues.append({"type": "url_deep_paths", "severity": "Low",
                       "finding": f"{h['deep_paths']['share']:.0%} of URLs are more than {DEEP_PATH} directories deep.",
                       "evidence": f"{h['deep_paths']['count']} of {total} URLs, e.g. {', '.join(h['deep_paths']['examples'][:2])}",
                       "impact": "Deep paths usually mean deep click paths and diluted section signals in the URL.",
                       "fix": "Flatten the hierarchy where directories carry no meaning; keep redirects for moved URLs.", "confidence": "Confirmed"})
    if h["mixed_case"]["count"]:
        issues.append({"type": "url_mixed_case", "severity": "Low",
                       "finding": f"{h['mixed_case']['count']} URL(s) contain upper-case path characters.",
                       "evidence": ", ".join(h["mixed_case"]["examples"][:3]),
                       "impact": "Case variants are distinct URLs to crawlers: duplicate content and split equity when both resolve.",
                       "fix": "Lower-case all paths and 301 the upper-case variants.", "confidence": "Confirmed"})
    if h["trailing_slash_inconsistent_sections"]:
        issues.append({"type": "url_trailing_slash_inconsistent", "severity": "Low",
                       "finding": f"Trailing-slash usage is inconsistent inside {len(h['trailing_slash_inconsistent_sections'])} section(s) of the sitemap.",
                       "evidence": "sections: " + ", ".join(h["trailing_slash_inconsistent_sections"][:5]),
                       "impact": "Two URL forms per page invite duplicate indexing and redirect hops from internal links.",
                       "fix": "Pick one form site-wide, redirect the other, and list only the canonical form in the sitemap.", "confidence": "Confirmed"})
    if h["dated_evergreen"]["count"]:
        issues.append({"type": "url_dated_evergreen", "severity": "Low",
                       "finding": f"{h['dated_evergreen']['count']} evergreen page(s) carry a date in the URL.",
                       "evidence": ", ".join(h["dated_evergreen"]["examples"][:3]),
                       "impact": "A dated URL on a product, pricing or docs page signals staleness and blocks refreshing the page without a redirect.",
                       "fix": "Move evergreen pages to undated URLs with 301s.", "confidence": "Likely"})
    if h["query_in_sitemap"]["count"]:
        issues.append({"type": "url_query_in_sitemap", "severity": "Low",
                       "finding": f"{h['query_in_sitemap']['count']} sitemap URL(s) carry a query string.",
                       "evidence": ", ".join(h["query_in_sitemap"]["examples"][:3]),
                       "impact": "Parameterised URLs in the sitemap are usually filtered or tracking variants that should not be indexed.",
                       "fix": "List canonical URLs only; canonicalise or noindex the parameter variants.", "confidence": "Likely"})

    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
    issues.sort(key=lambda i: order.get(i["severity"], 9))
    return issues


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(r: dict) -> None:
    inv = r["inventory"]
    print(f"\n🏗️  Site architecture: {r['site']}  ({r['site_type']})")
    print(f"   Inventory: {inv['total']} URLs ({inv['sitemap_urls']} from sitemap, {inv['fetched']} fetched), {'complete' if inv['complete'] else 'incomplete'}")
    print(f"   Navigation: {r['navigation']['status']}; sections in nav: {', '.join('/' + s + '/' for s in r['navigation']['sections'][:10]) or 'none'}")
    print(f"   Equity: {r['equity']['status']}" + (f" — {r['equity']['method']}" if r["equity"]["status"] == "measured" else ""))
    print("\n   Sections:")
    print(f"     {'path':<28}{'urls':>7}{'share':>7}  {'type':<20}{'nav':<5}{'hub':<5}{'depth':>6}{'equity':>8}")
    for s in r["sections"][:25]:
        eq = f"{s['equity_share']:.1%}" if s["equity_share"] is not None else "-"
        print(f"     {s['path'][:27]:<28}{s['url_count']:>7}{s['share']:>7.1%}  {s['dominant_label'][:19]:<20}{'yes' if s['in_nav'] else 'no':<5}{'yes' if s['hub']['exists'] else 'no':<5}{(s['avg_depth'] if s['avg_depth'] is not None else '-'):>6}{eq:>8}")
    if r["issues"]:
        print("\n   Findings:")
        for i in r["issues"]:
            print(f"     [{i['severity']}] {i['finding']}")
            print(f"        fix: {i['fix']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the site's section structure, link equity distribution and URL hygiene")
    parser.add_argument("url", help="Site URL (homepage)")
    parser.add_argument("--graph", help="site_graph.py output to read instead of crawling")
    parser.add_argument("--site-type", choices=ptc.SITE_TYPES, default="auto", help="Business type (default auto)")
    parser.add_argument("--max-pages", type=int, default=80, help="Pages to crawl when no --graph is given (default 80)")
    parser.add_argument("--depth", type=int, default=2, help="Crawl depth when no --graph is given (default 2)")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.graph:
        graph = site_graph.load_graph(args.graph)
    else:
        graph = site_graph.build_graph(args.url, max_pages=max(1, args.max_pages), max_depth=max(0, args.depth))
    result = analyze(graph, site_type=args.site_type)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_summary(result)


if __name__ == "__main__":
    main()
