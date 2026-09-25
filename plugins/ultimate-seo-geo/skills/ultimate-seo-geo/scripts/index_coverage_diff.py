#!/usr/bin/env python3
"""
Compare two Search Console "Page indexing" exports and say what moved and why.

The Page indexing report is not available through the Search Console API (see
gsc_export.py), so this script reads the files the report's Export button
writes: the zip, the folder it unzips to, or one of its CSVs. Run it weekly
with last week's export and this week's:

    python scripts/index_coverage_diff.py last-week.zip this-week.zip
    python scripts/index_coverage_diff.py last-week/ this-week/ --shipped shipped.txt --json

It reads every "Reason, Source, Validation, Pages" table in each export
(Critical issues.csv, Non-critical issues.csv) and Chart.csv (daily Indexed /
Not indexed totals), then:

  * reports only reasons that moved: at least --min-delta URLs (default 50), or
    at least --min-pct (default 5%) on a change of at least --min-floor URLs
    (default 10), so 2 -> 3 pages is not a "50% rise";
  * classifies each reason: technical (the site stops Google: robots.txt,
    noindex, 4xx/5xx, redirect errors), quality (Google crawled and declined:
    "Crawled - currently not indexed", duplicates), discovery ("Discovered -
    currently not indexed": not crawled yet) or expected (redirects and
    alternates with a proper canonical, usually intended);
  * ties each move to --shipped notes (one change per line) where a note names
    the thing that moves that reason, and says so when nothing does;
  * names ONE reason to investigate.

A rise in "Crawled - currently not indexed" is a quality signal: resubmitting
those URLs does nothing. The output says so every time it appears.

Example URLs: each reason's drill-down export (Table.csv, capped at 1,000 rows
by Search Console) can be compared with --examples OLD NEW; --sitemap marks
which newly listed URLs are in the sitemap, i.e. submitted pages Google now
declines. A capped list is a sample, and the output says so.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import zipfile
from urllib.parse import urlparse

MIN_DELTA = 50
MIN_PCT = 0.05
MIN_FLOOR = 10
EXAMPLE_CAP = 1000   # Search Console lists at most 1,000 example URLs per reason
LIST_LIMIT = 50      # URLs printed per list

# reason (lower case) -> class, meaning, cause of a rise, action on a rise, words in shipped notes that explain it
REASONS = {
    "server error (5xx)": ("technical", "Googlebot got a 5xx response.",
                           "Server errors or timeouts while Googlebot crawled: an outage, a slow deploy, or rate limiting.",
                           "Check server logs for 5xx on the listed URLs, fix the cause, then Validate Fix.",
                           ("outage", "downtime", "5xx", "server", "deploy", "hosting", "cdn", "firewall", "rate limit")),
    "redirect error": ("technical", "A redirect chain that is too long, loops, or leads to a bad URL.",
                       "New redirects that chain or loop.",
                       "Run redirect_checker.py on the listed URLs; point every redirect straight at its final 200 URL.",
                       ("redirect", "301", "302", "migration", "migrate", "moved")),
    "url blocked by robots.txt": ("technical", "robots.txt disallows the URL.",
                                  "A robots.txt change, or new URLs under a disallowed path.",
                                  "Diff robots.txt against last week (robots_checker.py); allow any URL that must be indexed.",
                                  ("robots",)),
    "url marked 'noindex'": ("technical", "The page carries a noindex directive.",
                             "noindex added to a template, often left over from staging.",
                             "Find the template that emits noindex on the listed URLs and remove it where the pages must be indexed.",
                             ("noindex", "staging", "template")),
    "soft 404": ("technical", "The page looks like 'not found' but returns 200.",
                 "Empty or near-empty pages: out-of-stock products, empty categories, thin search pages.",
                 "Return a real 404/410 for pages that are gone, or give the pages real content.",
                 ("remov", "delet", "out of stock", "unpublish", "retire", "empty")),
    "blocked due to unauthorized request (401)": ("technical", "Googlebot got 401.",
                                                  "Pages put behind a login, or a staging password on production.",
                                                  "Remove the auth requirement from pages that must be indexed.",
                                                  ("auth", "login", "password", "staging", "sso")),
    "not found (404)": ("technical", "Googlebot got 404.",
                        "Deleted or moved pages that are still linked or listed in the sitemap. Harmless when the pages were removed on purpose.",
                        "If the pages were removed on purpose, take them out of the sitemap and internal links; otherwise restore them or 301 them.",
                        ("remov", "delet", "unpublish", "retire", "migration", "migrate", "moved", "redirect")),
    "blocked due to access forbidden (403)": ("technical", "Googlebot got 403.",
                                              "A firewall, bot-protection or WAF rule refusing Googlebot.",
                                              "Check the WAF/bot rules for Googlebot (verify by reverse DNS, not user agent) and allow it.",
                                              ("firewall", "waf", "cloudflare", "bot", "403", "security")),
    "url blocked due to other 4xx issue": ("technical", "Googlebot got another 4xx.",
                                           "An unusual client error from the server (410, 429, 451...).",
                                           "Fetch the listed URLs as Googlebot and fix the status code.",
                                           ("rate limit", "429", "410", "firewall")),
    "blocked by page removal tool": ("technical", "A removal request in Search Console hides the URL.",
                                     "Someone filed removal requests.",
                                     "Review Removals in Search Console; cancel requests for pages that should appear.",
                                     ("removal",)),
    "crawled - currently not indexed": ("quality", "Google crawled the page and chose not to index it.",
                                        "Google judged the pages not worth indexing: thin, near-duplicate or low-value content. It is not a technical fault.",
                                        "Improve or consolidate the pages (duplicate_content.py, content_quality.py). Resubmitting them does nothing.",
                                        ("launch", "new pages", "published", "added", "programmatic", "template", "generated")),
    "discovered - currently not indexed": ("discovery", "Google knows the URL but has not crawled it yet.",
                                           "Many new URLs at once, weak internal linking, or a slow server limiting crawl rate.",
                                           "Link the pages from crawled pages (internal_links.py) and keep them in the sitemap; wait 2-4 weeks before acting further.",
                                           ("launch", "new pages", "published", "added", "sitemap", "programmatic", "generated")),
    "duplicate without user-selected canonical": ("quality", "A duplicate with no canonical; Google picked another URL.",
                                                  "New parameter, filter or print URLs that duplicate existing pages.",
                                                  "Add a self-referencing canonical to the preferred URL and point duplicates at it (canonical_checker.py).",
                                                  ("canonical", "parameter", "filter", "faceted", "pagination")),
    "duplicate, google chose different canonical": ("quality", "Google overrode the declared canonical.",
                                                    "Pages marked canonical that Google sees as copies of another page.",
                                                    "Make the declared canonical the strongest version (content, internal links, sitemap) or change the canonical to Google's choice.",
                                                    ("canonical", "duplicate", "merge", "consolidat")),
    "alternate page with proper canonical tag": ("expected", "An alternate URL correctly canonicalised to another page.",
                                                 "More alternates (parameters, AMP, language variants). Usually intended.",
                                                 "None if the canonicals are intended; spot-check five URLs.",
                                                 ("canonical", "parameter", "amp", "hreflang", "variant")),
    "page with redirect": ("expected", "The URL redirects; Google indexes the target instead.",
                           "Redirects added (a migration or URL change). Old URLs leave the index as intended.",
                           "None for intended redirects; take redirected URLs out of the sitemap and update internal links (internal_links.py).",
                           ("redirect", "301", "migration", "migrate", "moved", "url change", "restructur")),
}
# Older or regional wordings, matched by substring when the exact name is unknown.
_FALLBACK = (
    ("robots", "url blocked by robots.txt"), ("noindex", "url marked 'noindex'"), ("soft 404", "soft 404"),
    ("5xx", "server error (5xx)"), ("server error", "server error (5xx)"), ("redirect error", "redirect error"),
    ("404", "not found (404)"), ("not found", "not found (404)"), ("401", "blocked due to unauthorized request (401)"),
    ("403", "blocked due to access forbidden (403)"), ("crawled", "crawled - currently not indexed"),
    ("discovered", "discovered - currently not indexed"), ("chose different canonical", "duplicate, google chose different canonical"),
    ("duplicate", "duplicate without user-selected canonical"), ("alternate page", "alternate page with proper canonical tag"),
    ("redirect", "page with redirect"),
)
CLASS_ORDER = {"technical": 0, "quality": 1, "discovery": 2, "expected": 3, "unclassified": 4}
QUALITY_NOTE = ("'Crawled - currently not indexed' is a quality signal, not a technical fault: Google fetched the pages "
                "and declined them. Resubmitting or requesting indexing does not change that; better or fewer pages do.")


def canonical_reason(name: str) -> str | None:
    # Search Console writes "URL marked \u2018noindex\u2019" with curly quotes.
    key = " ".join(str(name or "").strip().lower().replace("\u2018", "'").replace("\u2019", "'").split())
    if key in REASONS:
        return key
    return next((target for needle, target in _FALLBACK if needle in key), None)


# ---------------------------------------------------------------------------
# Reading exports
# ---------------------------------------------------------------------------

def _number(value) -> int:
    text = str(value if value is not None else "").strip().replace(",", "").replace(" ", "")
    if text in ("", "-", "~"):
        return 0  # Search Console writes ~ and - for "no data"; its own docs treat them as zero
    return int(float(text))


def _read_csv_text(text: str) -> tuple[list[str], list[dict]]:
    text = text.lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]
    return [f.strip() for f in reader.fieldnames or []], rows


def _files(path: str) -> list[tuple[str, str]]:
    """[(name, text)] for every CSV in a zip, a folder, or a single CSV file."""
    if os.path.isdir(path):
        out = []
        for name in sorted(os.listdir(path)):
            if name.lower().endswith(".csv"):
                with open(os.path.join(path, name), encoding="utf-8-sig") as fh:
                    out.append((name, fh.read()))
        return out
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            return [(os.path.basename(n), zf.read(n).decode("utf-8-sig"))
                    for n in sorted(zf.namelist()) if n.lower().endswith(".csv")]
    with open(path, encoding="utf-8-sig") as fh:
        return [(os.path.basename(path), fh.read())]


def _col(fields: list[str], *names) -> str | None:
    lower = {f.lower(): f for f in fields}
    return next((lower[n] for n in names if n in lower), None)


def load_export(path: str) -> dict:
    """{"reasons": {canonical_or_raw: {...}}, "chart": {...} | None, "files": [...]} from one export.

    Raises ValueError when the export holds no reason table and no chart, so a
    wrong file (a Performance export, a drill-down Table.csv) fails loudly.
    """
    reasons, chart, used = {}, None, []
    for name, text in _files(path):
        fields, rows = _read_csv_text(text)
        reason_col, pages_col = _col(fields, "reason"), _col(fields, "pages")
        if reason_col and pages_col:
            source_col, validation_col = _col(fields, "source"), _col(fields, "validation")
            for row in rows:
                raw = row.get(reason_col, "")
                if not raw:
                    continue
                key = canonical_reason(raw) or raw.strip().lower()
                slot = reasons.setdefault(key, {"reason": raw.strip(), "pages": 0, "source": None, "validation": None, "file": name})
                slot["pages"] += _number(row.get(pages_col))
                slot["source"] = slot["source"] or (row.get(source_col) if source_col else None)
                slot["validation"] = slot["validation"] or (row.get(validation_col) if validation_col else None)
            used.append(name)
            continue
        date_col, indexed_col = _col(fields, "date"), _col(fields, "indexed")
        if date_col and indexed_col:
            not_col = _col(fields, "not indexed")
            series = sorted((r[date_col], _number(r.get(indexed_col)), _number(r.get(not_col)) if not_col else None)
                            for r in rows if r.get(date_col))
            if series:
                chart = {"series": series, "as_of": series[-1][0]}
                used.append(name)
    if not reasons and not chart:
        raise ValueError(f"{path}: no Page indexing table (Reason, Pages) or chart (Date, Indexed) found")
    return {"path": path, "reasons": reasons, "chart": chart, "files": used}


def load_url_list(path: str) -> list[str]:
    """URLs from a drill-down export (Table.csv, zip or folder): the column named URL."""
    urls = []
    for _, text in _files(path):
        fields, rows = _read_csv_text(text)
        url_col = _col(fields, "url", "urls", "page", "address")
        if url_col:
            urls += [r[url_col] for r in rows if r.get(url_col, "").startswith(("http://", "https://"))]
    if not urls:
        raise ValueError(f"{path}: no URL column found (expected a drill-down Table.csv)")
    return urls


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

def moved(before: int, after: int, min_delta=MIN_DELTA, min_pct=MIN_PCT, min_floor=MIN_FLOOR) -> bool:
    delta = after - before
    if abs(delta) >= min_delta:
        return True
    if abs(delta) < min_floor:
        return False
    return before == 0 or abs(delta) / before >= min_pct


def match_shipped(key: str, notes: list[str]) -> list[str]:
    words = REASONS[key][4] if key in REASONS else ()
    return [n for n in notes if any(w in n.lower() for w in words)]


def diff_reasons(old: dict, new: dict, notes: list[str], thresholds: dict) -> list[dict]:
    rows = []
    for key in sorted(set(old["reasons"]) | set(new["reasons"])):
        a = old["reasons"].get(key, {})
        b = new["reasons"].get(key, {})
        before, after = a.get("pages", 0), b.get("pages", 0)
        delta = after - before
        spec = REASONS.get(key)
        klass = spec[0] if spec else "unclassified"
        shipped = match_shipped(key, notes) if delta else []
        if delta > 0:
            cause = (f"Shipped this period: {'; '.join(shipped[:2])}" if shipped
                     else (spec[2] if spec else "Unknown reason; open it in Search Console.")
                     + (" No shipped note names a matching change." if notes else ""))
            action = spec[3] if spec else "Open the reason in Search Console and inspect five example URLs."
        elif delta < 0:
            cause = f"Shipped this period: {'; '.join(shipped[:2])}" if shipped else "Fewer URLs in this state."
            action = "None: fewer URLs in this state. Confirm they moved to Indexed, not to another reason."
        else:
            cause, action = "No change.", "None."
        rows.append({
            "reason": (b or a).get("reason", key),
            "class": klass,
            "source": (b or a).get("source"),
            "validation": b.get("validation"),
            "before": before,
            "after": after,
            "delta": delta,
            "pct": round(delta / before, 3) if before else None,
            "moved": moved(before, after, **thresholds),
            "direction": "worse" if delta > 0 else "better" if delta < 0 else "flat",
            "meaning": spec[1] if spec else None,
            "likely_cause": cause,
            "cause_confidence": "Likely" if shipped else "Hypothesis",
            "shipped_matches": shipped,
            "action": action,
        })
    rows.sort(key=lambda r: (not r["moved"], r["direction"] != "worse", CLASS_ORDER[r["class"]], -abs(r["delta"])))
    return rows


def totals(old: dict, new: dict, thresholds: dict) -> list[dict]:
    """Indexed / Not indexed on each export's last chart day."""
    out = []
    if not (old.get("chart") and new.get("chart")):
        return out
    a, b = old["chart"]["series"][-1], new["chart"]["series"][-1]
    for i, state in ((1, "Indexed"), (2, "Not indexed")):
        if a[i] is None or b[i] is None:
            continue
        delta = b[i] - a[i]
        out.append({"state": state, "before": a[i], "after": b[i], "delta": delta,
                    "pct": round(delta / a[i], 3) if a[i] else None, "moved": moved(a[i], b[i], **thresholds),
                    "direction": ("worse" if delta < 0 else "better" if delta > 0 else "flat") if state == "Indexed"
                    else ("worse" if delta > 0 else "better" if delta < 0 else "flat")})
    return out


def pick_investigation(rows: list[dict], total_rows: list[dict]) -> dict | None:
    """The one move to look at first.

    Technical rises first (the site is stopping Google), then a fall in Indexed,
    then quality and discovery rises; an expected rise that shipped notes explain
    comes last. Largest move wins inside a tier.
    """
    worse = [r for r in rows if r["moved"] and r["direction"] == "worse"]

    def tier(r):
        if r["class"] == "technical":
            return 0
        if r["class"] == "expected":
            return 5 if r["shipped_matches"] else 4
        return {"quality": 2, "discovery": 3}.get(r["class"], 3)

    indexed_drop = next((t for t in total_rows if t["state"] == "Indexed" and t["moved"] and t["direction"] == "worse"), None)
    candidates = [(tier(r), -r["delta"], r) for r in worse]
    if indexed_drop:
        candidates.append((1, indexed_drop["delta"], {"reason": "Indexed", **indexed_drop}))
    if not candidates:
        return None
    _, _, top = min(candidates, key=lambda c: (c[0], c[1]))
    why = {
        "technical": "a technical block: the site is stopping Google from indexing these URLs",
        "quality": "Google crawled these pages and declined them",
        "discovery": "Google has not crawled these URLs yet",
        "expected": "usually intended; confirm it matches what shipped",
    }.get(top.get("class"), "the indexed page count fell")
    return {"reason": top["reason"], "delta": top["delta"], "why": why}


def diff_examples(old_urls: list[str], new_urls: list[str], sitemap_urls=None) -> dict:
    def key(u):
        p = urlparse(u.strip())
        return f"{p.netloc.lower()}{p.path.rstrip('/') or '/'}"
    old_keys = {key(u) for u in old_urls}
    new_map = {key(u): u for u in new_urls}
    added = [u for k, u in new_map.items() if k not in old_keys]
    removed_keys = old_keys - set(new_map)
    removed = [u for u in old_urls if key(u) in removed_keys]
    capped = len(old_urls) >= EXAMPLE_CAP or len(new_urls) >= EXAMPLE_CAP
    out = {
        "before": len(old_urls), "after": len(new_urls),
        "added": len(added), "removed": len(removed),
        "added_urls": added[:LIST_LIMIT], "removed_urls": removed[:LIST_LIMIT],
        "sample": capped,
        "note": ("Search Console lists at most 1,000 example URLs per reason: these lists are a sample, "
                 "so 'added' and 'removed' are URLs that entered or left the sample.") if capped else None,
    }
    if sitemap_urls is not None:
        in_sitemap = {key(u) for u in sitemap_urls}
        submitted = [u for u in added if key(u) in in_sitemap]
        out["added_in_sitemap"] = len(submitted)
        out["added_in_sitemap_urls"] = submitted[:LIST_LIMIT]
    return out


def load_sitemap_urls(arg: str) -> tuple[list[str], bool]:
    """(urls, complete) from a site or sitemap URL, a local sitemap XML, or a text file of URLs."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    if arg.startswith(("http://", "https://")):
        import site_graph  # lazy: only --sitemap with a URL needs requests and bs4
        found = site_graph.discover_sitemap(arg)
        return list(found.get("urls") or {}), bool(found.get("complete"))
    with open(arg, encoding="utf-8-sig") as fh:
        text = fh.read()
    if "<urlset" in text or "<sitemapindex" in text:
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text)
        return locs, "<sitemapindex" not in text  # an index file lists child sitemaps, not pages
    return [line.strip() for line in text.splitlines() if line.strip().startswith(("http://", "https://"))], True


# ---------------------------------------------------------------------------
# Findings and output
# ---------------------------------------------------------------------------

def build_issues(rows: list[dict], total_rows: list[dict], investigate, period: str) -> list[dict]:
    issues = []
    for t in total_rows:
        if t["state"] == "Indexed" and t["moved"] and t["direction"] == "worse":
            issues.append({
                "code": "indexed_drop", "severity": "high", "kind": "defect", "lane": "Assisted",
                "finding": f"Indexed pages fell from {t['before']:,} to {t['after']:,} ({t['delta']:+,}) {period}.",
                "evidence": "Chart.csv, last day of each export.",
                "impact": "Pages that leave the index cannot rank or be cited.",
                "fix": "Read the reasons that rose in the same period (below); the drop is usually one of them.",
                "confidence": "Confirmed",
                "falsifiability": "Wrong if the drop is URLs removed on purpose (a migration or pruning) now reported as redirects or 404s.",
                "leading_indicator": "Indexed count in next week's export.",
            })
    for r in rows:
        if not (r["moved"] and r["direction"] == "worse"):
            continue
        severity = {"technical": "high", "quality": "medium", "discovery": "medium"}.get(r["class"], "low")
        if r["class"] == "technical" and r["reason"].lower().startswith("not found") and r["shipped_matches"]:
            severity = "low"  # 404s for pages removed on purpose are expected
        pct = f", {r['pct']:+.0%}" if r["pct"] is not None else ""
        issue = {
            "code": f"coverage.{re.sub(r'[^a-z0-9]+', '-', r['reason'].lower()).strip('-')}",
            "severity": severity, "kind": "defect",
            "lane": "Assisted" if r["class"] in ("technical", "expected") else "Human",
            "finding": f"'{r['reason']}' rose from {r['before']:,} to {r['after']:,} pages ({r['delta']:+,}{pct}) {period}.",
            "evidence": f"Page indexing export; reason class: {r['class']}.",
            "impact": r["meaning"] or "Pages in this state are not indexed.",
            "fix": r["action"],
            "confidence": "Confirmed",  # the count is measured; the cause carries its own confidence
            "cause_confidence": r["cause_confidence"],
            "falsifiability": "Wrong if the URLs listed under this reason were meant to leave the index; check five examples.",
            "leading_indicator": f"'{r['reason']}' count in next week's export.",
            "likely_cause": r["likely_cause"],
        }
        if r["reason"].lower().startswith("crawled - currently not indexed"):
            issue["impact"] += " " + QUALITY_NOTE
        issues.append(issue)
    if investigate:
        for issue in issues:
            if issue["finding"].startswith(f"'{investigate['reason']}'") or (
                    investigate["reason"] == "Indexed" and issue["code"] == "indexed_drop"):
                issue["tags"] = ["investigate_first"]
                break
    return issues


def compare(old_path: str, new_path: str, notes=None, thresholds=None, examples=None, sitemap=None) -> dict:
    thresholds = thresholds or {}
    notes = [n.strip() for n in (notes or []) if n.strip()]
    old, new = load_export(old_path), load_export(new_path)
    rows = diff_reasons(old, new, notes, thresholds)
    total_rows = totals(old, new, thresholds)
    investigate = pick_investigation(rows, total_rows)
    a_date = (old.get("chart") or {}).get("as_of")
    b_date = (new.get("chart") or {}).get("as_of")
    period = f"between {a_date} and {b_date}" if a_date and b_date else "between the two exports"
    result = {
        "before": {"path": old_path, "as_of": a_date, "files": old["files"]},
        "after": {"path": new_path, "as_of": b_date, "files": new["files"]},
        "thresholds": {"min_delta": thresholds.get("min_delta", MIN_DELTA), "min_pct": thresholds.get("min_pct", MIN_PCT),
                       "min_floor": thresholds.get("min_floor", MIN_FLOOR)},
        "totals": total_rows,
        "reasons": rows,
        "movers": [r for r in rows if r["moved"]],
        "investigate": investigate,
        "limits": [
            "The Page indexing report is not in the Search Console API; these figures are the exports' own.",
            "Counts lag: Search Console updates this report every few days, so a change shipped this week may show next week.",
        ],
    }
    if not total_rows:
        result["limits"].append("No Chart.csv in one or both exports: Indexed / Not indexed totals are not compared.")
    if any(r["reason"].lower().startswith("crawled - currently not indexed") and r["moved"] for r in rows):
        result["notes"] = [QUALITY_NOTE]
    if examples:
        sm_urls, sm_complete = (load_sitemap_urls(sitemap) if sitemap else (None, None))
        result["examples"] = diff_examples(load_url_list(examples[0]), load_url_list(examples[1]), sm_urls)
        if sitemap:
            result["examples"]["sitemap_complete"] = sm_complete
            if not sm_complete:
                result["limits"].append("The sitemap was not read completely: added_in_sitemap is a lower bound.")
    result["issues"] = build_issues(rows, total_rows, investigate, period)
    return result


def print_human(result: dict) -> None:
    b, a = result["before"], result["after"]
    print(f"Page indexing: {b.get('as_of') or b['path']}  ->  {a.get('as_of') or a['path']}")
    print("=" * 78)
    for t in result["totals"]:
        mark = "*" if t["moved"] else " "
        print(f"{mark} {t['state']:<14} {t['before']:>9,} -> {t['after']:>9,}  {t['delta']:+,}")
    movers = result["movers"]
    print(f"\nReasons that moved ({len(movers)} of {len(result['reasons'])}):")
    if not movers:
        print("  none above the thresholds")
    for r in movers:
        pct = f"{r['pct']:+.0%}" if r["pct"] is not None else "new"
        print(f"  [{r['class']:<11}] {r['reason'][:48]:<48} {r['before']:>7,} -> {r['after']:>7,}  {r['delta']:+,} ({pct})")
        print(f"      cause ({r['cause_confidence']}): {r['likely_cause']}")
        print(f"      action: {r['action']}")
    inv = result.get("investigate")
    print(f"\nInvestigate first: {inv['reason']} ({inv['delta']:+,}): {inv['why']}." if inv else "\nNothing to investigate.")
    for note in result.get("notes", []):
        print(f"\nNote: {note}")
    ex = result.get("examples")
    if ex:
        print(f"\nExample URLs: {ex['before']} -> {ex['after']}; {ex['added']} added, {ex['removed']} removed")
        if "added_in_sitemap" in ex:
            print(f"  {ex['added_in_sitemap']} of the added URLs are in the sitemap (submitted pages Google now declines)")
        for url in ex["added_urls"][:15]:
            print(f"  + {url}")
        if ex.get("note"):
            print(f"  {ex['note']}")
    for line in result["limits"]:
        print(f"Limit: {line}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two Search Console Page indexing exports")
    parser.add_argument("before", help="Earlier export: the zip, its unzipped folder, or its Critical issues CSV")
    parser.add_argument("after", help="Later export, same forms")
    parser.add_argument("--shipped", metavar="PATH", help="Text file of changes shipped in the period, one per line")
    parser.add_argument("--examples", nargs=2, metavar=("OLD", "NEW"),
                        help="Drill-down exports (Table.csv) of one reason from each period, to list URLs that entered or left it")
    parser.add_argument("--sitemap", metavar="URL_OR_FILE",
                        help="With --examples: site URL, sitemap URL, sitemap XML or URL list; marks added URLs that are submitted")
    parser.add_argument("--min-delta", type=int, default=MIN_DELTA, help=f"A move of this many URLs always counts (default {MIN_DELTA})")
    parser.add_argument("--min-pct", type=float, default=MIN_PCT, help=f"Relative move that counts (default {MIN_PCT})")
    parser.add_argument("--min-floor", type=int, default=MIN_FLOOR, help=f"Smallest move the relative rule applies to (default {MIN_FLOOR})")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()
    if args.sitemap and not args.examples:
        parser.error("--sitemap needs --examples")
    if args.min_delta < 1 or args.min_floor < 0 or not 0 <= args.min_pct <= 1:
        parser.error("--min-delta must be >= 1, --min-floor >= 0, --min-pct between 0 and 1")

    notes = []
    if args.shipped:
        try:
            with open(args.shipped, encoding="utf-8") as fh:
                notes = fh.read().splitlines()
        except OSError as exc:
            parser.error(f"--shipped: cannot read {args.shipped}: {exc}")
    try:
        result = compare(args.before, args.after, notes,
                         {"min_delta": args.min_delta, "min_pct": args.min_pct, "min_floor": args.min_floor},
                         args.examples, args.sitemap)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"error": str(exc)}) if args.json else f"Error: {exc}")
        return 1
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_human(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
