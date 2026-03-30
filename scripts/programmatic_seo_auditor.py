#!/usr/bin/env python3
"""
Programmatic SEO Auditor

Crawls a site, auto-detects URL pattern groups (template pages), and
audits each group for thin/duplicate content, boilerplate ratio, title
and meta description uniqueness, and internal linking health.

Flags scaled content abuse risks using the quality gates from
references/programmatic-seo.md.

Usage:
    python programmatic_seo_auditor.py https://example.com --json
    python programmatic_seo_auditor.py https://example.com --depth 3 --max-pages 200
"""

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 required. Install with: pip install beautifulsoup4")
    sys.exit(1)

USER_AGENT = "Mozilla/5.0 (compatible; SEOSkill-pSEOAudit/1.0)"
HEADERS = {"User-Agent": USER_AGENT}

THIN_WORD_COUNT = 300
BOILERPLATE_HIGH = 70  # >70% boilerplate = red flag
BOILERPLATE_WARN = 60
UNIQUENESS_HARD_STOP = 30  # <30% unique = scaled content abuse
UNIQUENESS_WARN = 40       # <40% unique = thin content risk
MIN_PATTERN_SIZE = 3       # need ≥3 pages to consider it a pattern group


# ---------------------------------------------------------------------------
# Fetch & extract
# ---------------------------------------------------------------------------

def _fetch(url: str, timeout: int = 12) -> tuple:
    """Fetch URL, return (html, final_url, status)."""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ct = resp.headers.get("Content-Type", "")
            if "text/html" not in ct:
                return None, resp.url, resp.status
            html = resp.read().decode("utf-8", errors="ignore")
            return html, resp.url, resp.status
    except Exception:
        return None, url, None


def _extract_meta(html: str, base_url: str) -> dict:
    """Extract SEO-relevant metadata from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    description = desc_tag.get("content", "").strip() if desc_tag else ""

    h1_tag = soup.find("h1")
    h1 = h1_tag.get_text(strip=True) if h1_tag else ""

    canon_tag = soup.find("link", rel="canonical")
    canonical = ""
    if canon_tag and canon_tag.get("href"):
        href = canon_tag["href"].strip()
        if not urlparse(href).scheme:
            href = urljoin(base_url, href)
        canonical = href

    robots_tag = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    robots = robots_tag.get("content", "").lower() if robots_tag else ""

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    body = soup.find("body")
    body_text = body.get_text(separator=" ", strip=True) if body else ""

    links = []
    base_domain = urlparse(base_url).netloc
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.netloc == base_domain and parsed.scheme in ("http", "https"):
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
            links.append(clean)

    return {
        "title": title,
        "description": description,
        "h1": h1,
        "canonical": canonical,
        "robots": robots,
        "body_text": body_text,
        "word_count": len(re.findall(r"\b\w+\b", body_text)),
        "internal_links": list(set(links)),
    }


# ---------------------------------------------------------------------------
# URL pattern detection
# ---------------------------------------------------------------------------

def _url_to_pattern(url: str) -> str:
    """
    Convert a URL to its pattern template.
    /retreats/mexico/oaxaca-healing-retreat  →  /retreats/*/  (depth-based)
    /brands/urb                              →  /brands/*
    /species/pluteus                         →  /species/*
    """
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) <= 1:
        return parsed.path.rstrip("/") or "/"

    pattern_parts = parts[:-1] + ["*"]
    return "/" + "/".join(pattern_parts)


def _detect_pattern_groups(urls: list) -> dict:
    """Group URLs by their template pattern. Returns {pattern: [urls]}."""
    groups = defaultdict(list)
    for url in urls:
        pattern = _url_to_pattern(url)
        groups[pattern].append(url)

    return {p: urls for p, urls in groups.items() if len(urls) >= MIN_PATTERN_SIZE}


# ---------------------------------------------------------------------------
# Content analysis
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list:
    return re.findall(r"\b[a-z]+\b", text.lower())


def _shingle(tokens: list, k: int = 5) -> set:
    if len(tokens) < k:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i:i + k]) for i in range(len(tokens) - k + 1)}


def _compute_boilerplate(pages_data: list) -> dict:
    """
    Compute boilerplate ratio across a set of template pages.
    Boilerplate = shingles that appear in >80% of pages in the group.
    Returns per-page boilerplate % and unique content %.
    """
    all_shingles = []
    for page in pages_data:
        tokens = _tokenize(page["body_text"])
        shingles = _shingle(tokens)
        all_shingles.append(shingles)

    if not all_shingles:
        return {}

    shingle_counts = Counter()
    for s_set in all_shingles:
        for s in s_set:
            shingle_counts[s] += 1

    threshold = max(2, len(pages_data) * 0.8)
    boilerplate_shingles = {s for s, c in shingle_counts.items() if c >= threshold}

    results = {}
    for i, page in enumerate(pages_data):
        total = len(all_shingles[i])
        if total == 0:
            results[page["url"]] = {"boilerplate_pct": 100.0, "unique_pct": 0.0}
            continue
        bp_count = len(all_shingles[i] & boilerplate_shingles)
        bp_pct = bp_count / total * 100
        results[page["url"]] = {
            "boilerplate_pct": round(bp_pct, 1),
            "unique_pct": round(100 - bp_pct, 1),
        }

    return results


def _check_title_uniqueness(pages_data: list) -> dict:
    """Check how unique titles are within a pattern group."""
    titles = [p["title"] for p in pages_data]
    title_counts = Counter(titles)
    total = len(titles)
    unique = len(title_counts)
    duplicated = {t: c for t, c in title_counts.items() if c > 1}
    return {
        "total": total,
        "unique": unique,
        "unique_pct": round(unique / max(1, total) * 100, 1),
        "duplicated": duplicated,
    }


def _check_description_uniqueness(pages_data: list) -> dict:
    """Check how unique meta descriptions are within a pattern group."""
    descs = [p["description"] for p in pages_data if p["description"]]
    missing = sum(1 for p in pages_data if not p["description"])
    desc_counts = Counter(descs)
    unique = len(desc_counts)
    duplicated = {d[:80] + "..." if len(d) > 80 else d: c
                  for d, c in desc_counts.items() if c > 1}
    return {
        "total": len(pages_data),
        "with_description": len(descs),
        "missing": missing,
        "unique": unique,
        "unique_pct": round(unique / max(1, len(descs)) * 100, 1),
        "duplicated": duplicated,
    }


def _check_h1_uniqueness(pages_data: list) -> dict:
    """Check H1 uniqueness across a pattern group."""
    h1s = [p["h1"] for p in pages_data]
    missing = sum(1 for h in h1s if not h)
    h1_counts = Counter(h for h in h1s if h)
    unique = len(h1_counts)
    duplicated = {h: c for h, c in h1_counts.items() if c > 1}
    return {
        "total": len(pages_data),
        "missing": missing,
        "unique": unique,
        "unique_pct": round(unique / max(1, len(h1s) - missing) * 100, 1),
        "duplicated": duplicated,
    }


# ---------------------------------------------------------------------------
# Crawl
# ---------------------------------------------------------------------------

def crawl_site(start_url: str, max_pages: int = 100, depth: int = 2) -> list:
    """BFS crawl; returns list of page data dicts."""
    visited = set()
    pages = []
    queue = [(start_url, 0)]
    seen = {start_url}
    base_domain = urlparse(start_url).netloc

    while queue and len(visited) < max_pages:
        url, d = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        time.sleep(0.3)
        html, final_url, status = _fetch(url)
        if not html or status != 200:
            continue

        meta = _extract_meta(html, final_url)
        meta["url"] = url
        meta["final_url"] = final_url
        meta["status"] = status
        pages.append(meta)

        if d < depth:
            for link in meta["internal_links"]:
                parsed = urlparse(link)
                if parsed.netloc == base_domain and link not in seen:
                    seen.add(link)
                    queue.append((link, d + 1))

    return pages


# ---------------------------------------------------------------------------
# Audit a pattern group
# ---------------------------------------------------------------------------

def audit_pattern_group(pattern: str, pages_data: list) -> dict:
    """Run all programmatic SEO checks on a pattern group."""
    result = {
        "pattern": pattern,
        "page_count": len(pages_data),
        "issues": [],
        "recommendations": [],
    }

    # 1. Word counts
    word_counts = [p["word_count"] for p in pages_data]
    avg_wc = sum(word_counts) / max(1, len(word_counts))
    thin_pages = [p["url"] for p in pages_data if p["word_count"] < THIN_WORD_COUNT]
    result["word_count"] = {
        "average": round(avg_wc),
        "min": min(word_counts),
        "max": max(word_counts),
        "thin_count": len(thin_pages),
        "thin_pages": thin_pages[:10],
    }

    if len(thin_pages) > 0:
        pct = len(thin_pages) / len(pages_data) * 100
        severity = "critical" if pct > 50 else "warning"
        result["issues"].append({
            "severity": severity,
            "finding": f"{len(thin_pages)}/{len(pages_data)} pages ({pct:.0f}%) have <{THIN_WORD_COUNT} words.",
            "fix": f"Expand content to ≥{THIN_WORD_COUNT} words of substantive, unique content per page, or noindex thin pages.",
        })

    # 2. Boilerplate / uniqueness
    bp_data = _compute_boilerplate(pages_data)
    if bp_data:
        avg_unique = sum(v["unique_pct"] for v in bp_data.values()) / len(bp_data)
        hard_stop_pages = [u for u, v in bp_data.items() if v["unique_pct"] < UNIQUENESS_HARD_STOP]
        warn_pages = [u for u, v in bp_data.items()
                      if UNIQUENESS_HARD_STOP <= v["unique_pct"] < UNIQUENESS_WARN]

        result["content_uniqueness"] = {
            "avg_unique_pct": round(avg_unique, 1),
            "avg_boilerplate_pct": round(100 - avg_unique, 1),
            "hard_stop_count": len(hard_stop_pages),
            "warning_count": len(warn_pages),
            "hard_stop_pages": hard_stop_pages[:10],
            "warning_pages": warn_pages[:10],
        }

        if hard_stop_pages:
            result["issues"].append({
                "severity": "critical",
                "finding": (
                    f"{len(hard_stop_pages)} page(s) have <{UNIQUENESS_HARD_STOP}% unique "
                    f"content — scaled content abuse territory."
                ),
                "fix": "Add genuinely unique per-page content (local data, specific facts, "
                       "unique analysis) or remove these pages.",
            })
        if warn_pages:
            result["issues"].append({
                "severity": "warning",
                "finding": (
                    f"{len(warn_pages)} page(s) have {UNIQUENESS_HARD_STOP}-{UNIQUENESS_WARN}% "
                    f"unique content — thin content risk."
                ),
                "fix": "Strengthen content differentiation. Each page needs ≥3 unique data "
                       "fields beyond simple variable substitution.",
            })

        if avg_unique < UNIQUENESS_WARN:
            result["recommendations"].append(
                f"Average uniqueness is only {avg_unique:.0f}% across this pattern group. "
                f"Consider adding page-specific data, local stats, unique descriptions, "
                f"or user-generated content to differentiate pages."
            )

    # 3. Title uniqueness
    title_data = _check_title_uniqueness(pages_data)
    result["titles"] = title_data

    if title_data["unique_pct"] < 100:
        dup_count = sum(c - 1 for c in title_data["duplicated"].values())
        result["issues"].append({
            "severity": "critical" if title_data["unique_pct"] < 80 else "warning",
            "finding": f"{dup_count} page(s) share duplicate titles. "
                       f"Only {title_data['unique_pct']}% of titles are unique.",
            "fix": "Every programmatic page must have a unique <title> tag. "
                   "Inject the primary variable (city, product, term) into the title.",
        })

    # 4. Meta description uniqueness
    desc_data = _check_description_uniqueness(pages_data)
    result["descriptions"] = desc_data

    if desc_data["missing"] > 0:
        result["issues"].append({
            "severity": "warning",
            "finding": f"{desc_data['missing']} page(s) missing meta description.",
            "fix": "Add unique meta descriptions to all programmatic pages.",
        })
    if desc_data["duplicated"]:
        dup_count = sum(c - 1 for c in desc_data["duplicated"].values())
        result["issues"].append({
            "severity": "warning",
            "finding": f"{dup_count} page(s) share duplicate meta descriptions.",
            "fix": "Generate unique meta descriptions per page using template variables.",
        })

    # 5. H1 uniqueness
    h1_data = _check_h1_uniqueness(pages_data)
    result["h1s"] = h1_data

    if h1_data["missing"] > 0:
        result["issues"].append({
            "severity": "warning",
            "finding": f"{h1_data['missing']} page(s) missing H1.",
            "fix": "Add a unique H1 to every programmatic page.",
        })
    if h1_data["unique_pct"] < 100 and h1_data["duplicated"]:
        result["issues"].append({
            "severity": "warning",
            "finding": f"Only {h1_data['unique_pct']}% of H1s are unique.",
            "fix": "Each page's H1 should include the primary differentiating variable.",
        })

    # 6. Canonical checks
    no_canonical = [p["url"] for p in pages_data if not p["canonical"]]
    noindex_pages = [p["url"] for p in pages_data if "noindex" in p["robots"]]
    non_self_canonical = [
        p["url"] for p in pages_data
        if p["canonical"] and p["canonical"].rstrip("/") != p["url"].rstrip("/")
    ]

    result["canonicals"] = {
        "missing": len(no_canonical),
        "noindex_count": len(noindex_pages),
        "non_self_canonical": len(non_self_canonical),
    }

    if no_canonical:
        result["issues"].append({
            "severity": "warning",
            "finding": f"{len(no_canonical)} programmatic page(s) missing canonical tag.",
            "fix": "Add self-referencing canonical to every indexable programmatic page.",
        })

    # 7. Internal linking between template pages
    template_urls = {p["url"] for p in pages_data}
    pages_with_cross_links = 0
    orphan_templates = []
    for p in pages_data:
        cross = [l for l in p["internal_links"] if l in template_urls and l != p["url"]]
        if cross:
            pages_with_cross_links += 1
        else:
            orphan_templates.append(p["url"])

    cross_pct = pages_with_cross_links / max(1, len(pages_data)) * 100
    result["internal_linking"] = {
        "cross_linked_pct": round(cross_pct, 1),
        "orphan_count": len(orphan_templates),
        "orphan_pages": orphan_templates[:10],
    }

    if len(orphan_templates) > len(pages_data) * 0.5:
        result["issues"].append({
            "severity": "warning",
            "finding": f"{len(orphan_templates)}/{len(pages_data)} template pages have no "
                       f"cross-links to other pages in the same pattern group.",
            "fix": "Add hub-spoke internal linking: a hub page linking to all spokes, "
                   "and 3-5 related spoke links per page.",
        })

    # Overall risk assessment
    critical_count = sum(1 for i in result["issues"] if i["severity"] == "critical")
    warning_count = sum(1 for i in result["issues"] if i["severity"] == "warning")

    if critical_count > 0:
        result["risk_level"] = "high"
        result["risk_label"] = "Scaled content abuse risk — fix critical issues before Google acts"
    elif warning_count > 2:
        result["risk_level"] = "medium"
        result["risk_label"] = "Multiple quality concerns — address warnings to avoid future penalties"
    else:
        result["risk_level"] = "low"
        result["risk_label"] = "Programmatic pages look healthy"

    return result


# ---------------------------------------------------------------------------
# Full audit
# ---------------------------------------------------------------------------

def run_audit(start_url: str, max_pages: int = 100, depth: int = 2) -> dict:
    """Crawl + detect patterns + audit each group."""
    pages = crawl_site(start_url, max_pages=max_pages, depth=depth)

    urls = [p["url"] for p in pages]
    pattern_groups = _detect_pattern_groups(urls)

    pages_by_url = {p["url"]: p for p in pages}

    group_audits = []
    pages_in_groups = set()

    for pattern, group_urls in sorted(pattern_groups.items(), key=lambda x: -len(x[1])):
        group_pages = [pages_by_url[u] for u in group_urls if u in pages_by_url]
        if len(group_pages) < MIN_PATTERN_SIZE:
            continue
        audit = audit_pattern_group(pattern, group_pages)
        group_audits.append(audit)
        pages_in_groups.update(group_urls)

    ungrouped = [u for u in urls if u not in pages_in_groups]

    total_critical = sum(
        sum(1 for i in g["issues"] if i["severity"] == "critical")
        for g in group_audits
    )
    total_warnings = sum(
        sum(1 for i in g["issues"] if i["severity"] == "warning")
        for g in group_audits
    )

    if total_critical > 0:
        overall_risk = "high"
    elif total_warnings > 3:
        overall_risk = "medium"
    else:
        overall_risk = "low"

    return {
        "url": start_url,
        "pages_crawled": len(pages),
        "pattern_groups_found": len(group_audits),
        "pages_in_patterns": len(pages_in_groups),
        "pages_ungrouped": len(ungrouped),
        "overall_risk": overall_risk,
        "total_critical_issues": total_critical,
        "total_warnings": total_warnings,
        "pattern_audits": group_audits,
        "ungrouped_urls": ungrouped[:20],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Programmatic SEO Auditor — detect template page quality issues at scale"
    )
    parser.add_argument("url", help="Start URL to crawl")
    parser.add_argument("--depth", type=int, default=2, help="Crawl depth (default: 2)")
    parser.add_argument("--max-pages", type=int, default=100,
                        help="Max pages to crawl (default: 100)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    print(f"Crawling {args.url} (depth={args.depth}, max={args.max_pages})...",
          file=sys.stderr)
    report = run_audit(args.url, max_pages=args.max_pages, depth=args.depth)
    print(f"Crawled {report['pages_crawled']} pages, found "
          f"{report['pattern_groups_found']} pattern groups.", file=sys.stderr)

    if args.json:
        print(json.dumps(report, indent=2))
        return

    print(f"\nProgrammatic SEO Audit Report")
    print("=" * 60)
    print(f"Site              : {report['url']}")
    print(f"Pages crawled     : {report['pages_crawled']}")
    print(f"Pattern groups    : {report['pattern_groups_found']}")
    print(f"Pages in patterns : {report['pages_in_patterns']}")
    print(f"Overall risk      : {report['overall_risk'].upper()}")
    print(f"Critical issues   : {report['total_critical_issues']}")
    print(f"Warnings          : {report['total_warnings']}")

    for g in report["pattern_audits"]:
        print(f"\n{'─' * 60}")
        risk_icon = {"high": "🔴", "medium": "⚠️", "low": "✅"}[g["risk_level"]]
        print(f"{risk_icon} Pattern: {g['pattern']} ({g['page_count']} pages)")
        print(f"   Risk: {g['risk_label']}")

        wc = g["word_count"]
        print(f"   Words: avg {wc['average']}, min {wc['min']}, max {wc['max']}"
              f" | Thin: {wc['thin_count']}")

        if "content_uniqueness" in g:
            cu = g["content_uniqueness"]
            print(f"   Uniqueness: {cu['avg_unique_pct']}% avg"
                  f" | Boilerplate: {cu['avg_boilerplate_pct']}%"
                  f" | Abuse risk: {cu['hard_stop_count']}"
                  f" | Thin risk: {cu['warning_count']}")

        t = g["titles"]
        print(f"   Titles: {t['unique_pct']}% unique ({t['unique']}/{t['total']})")

        d = g["descriptions"]
        print(f"   Descriptions: {d['unique_pct']}% unique, {d['missing']} missing")

        h = g["h1s"]
        print(f"   H1s: {h['unique_pct']}% unique, {h['missing']} missing")

        il = g["internal_linking"]
        print(f"   Cross-linking: {il['cross_linked_pct']}% of pages"
              f" | Orphans: {il['orphan_count']}")

        if g["issues"]:
            print(f"\n   Issues ({len(g['issues'])}):")
            for issue in g["issues"]:
                icon = "🔴" if issue["severity"] == "critical" else "⚠️"
                print(f"   {icon} {issue['finding']}")
                print(f"      Fix: {issue['fix']}")

        if g["recommendations"]:
            print(f"\n   Recommendations:")
            for r in g["recommendations"]:
                print(f"   💡 {r}")

    if not report["pattern_audits"]:
        print(f"\nNo programmatic URL patterns detected (need ≥{MIN_PATTERN_SIZE} "
              f"pages sharing the same URL structure).")
        print("This site may not use programmatic SEO, or the crawl didn't "
              "reach enough template pages. Try increasing --depth or --max-pages.")


if __name__ == "__main__":
    main()
