#!/usr/bin/env python3
"""
Link Profile Analyzer

Crawls a site to build an internal/external link graph, identifies orphan
pages, calculates internal link equity distribution, and analyzes anchor
text patterns.

For backlink data from external sources, integrates with GSC API
(if credentials available) or outputs instructions for manual enrichment.

Usage:
    python link_profile.py https://example.com --json
    python link_profile.py https://example.com --max-pages 100 --json
    python link_profile.py https://example.com --gsc-credentials creds.json
"""

import argparse
import json
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from urllib.parse import urlparse, urljoin

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 required. Install with: pip install beautifulsoup4",
          file=sys.stderr)
    sys.exit(1)

from url_safety import validate_url


USER_AGENT = "Mozilla/5.0 (compatible; UltimateSEO-LinkProfile/1.8)"

# Link targets that are files, not pages. None of them can be an orphan page,
# and a crawl is not incomplete for having skipped them.
NON_PAGE_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".avif", ".ico",
    ".zip", ".gz", ".mp3", ".mp4", ".webm", ".css", ".js", ".json", ".xml",
    ".txt", ".csv", ".xlsx", ".docx", ".pptx",
)


def page_key(url: str) -> str:
    """Identity of a page for inbound-link counting.

    A sitemap <loc> of /guide/ and an href of /guide are the same page, and so
    are EX.com and ex.com. Comparing raw strings reported pages as orphans
    purely because the sitemap and the navigation spelled them differently.
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"


def is_page_url(url: str) -> bool:
    return not urlparse(url).path.lower().endswith(NON_PAGE_EXTENSIONS)


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def fetch_page(url: str, timeout: int = 10) -> tuple:
    """Return (final_url, html) or (url, '').

    Most URLs reaching this function come from the audited site itself: the
    <loc> entries of its sitemap and the hrefs of its pages. urlopen serves
    file:// and ftp:// as happily as http://, so without a scheme check a
    sitemap entry of <loc>file:///etc/passwd</loc> is read straight into the
    report. validate_url is the guard this repo already ships for that.
    """
    safe = validate_url(url)
    if not safe.ok:
        return url, ""
    try:
        req = urllib.request.Request(
            safe.normalized_url, headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.url, resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return url, ""


def get_sitemap_urls(site_url: str, limit: int = 200) -> list:
    """Extract URLs from sitemap.xml."""
    parsed = urlparse(site_url)
    sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    _, body = fetch_page(sitemap_url)
    if not body:
        return []
    urls = re.findall(r"<loc>([^<]+)</loc>", body)
    # Expand sitemap index
    if any("sitemap" in u.lower() and u.endswith(".xml") for u in urls[:5]):
        expanded = []
        for sub in urls[:10]:
            time.sleep(0.3)
            _, sub_body = fetch_page(sub)
            if sub_body:
                expanded.extend(re.findall(r"<loc>([^<]+)</loc>", sub_body))
        urls = expanded
    return urls[:limit]


# ---------------------------------------------------------------------------
# Link extraction
# ---------------------------------------------------------------------------

def extract_links(html: str, page_url: str, base_domain: str) -> dict:
    """Extract internal and external links from a page."""
    soup = BeautifulSoup(html, "html.parser")
    internal = []
    external = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        full_url = urljoin(page_url, href)
        parsed = urlparse(full_url)
        anchor_text = a.get_text(strip=True)[:100]
        nofollow = "nofollow" in (a.get("rel") or [])

        link_data = {
            "url": f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
            "anchor": anchor_text,
            "nofollow": nofollow,
        }

        if parsed.netloc == base_domain or parsed.netloc.endswith(f".{base_domain}"):
            internal.append(link_data)
        else:
            external.append(link_data)

    return {"internal": internal, "external": external}


# ---------------------------------------------------------------------------
# Crawl & build graph
# ---------------------------------------------------------------------------

def crawl_site(site_url: str, max_pages: int = 50) -> dict:
    """Crawl site and build link graph."""
    parsed = urlparse(site_url)
    base_domain = parsed.netloc

    # Seed URLs from sitemap + homepage. Ask for one more URL than we will
    # fetch, so a sitemap that does not fit is known to have been cut short.
    seed_urls = get_sitemap_urls(site_url, limit=max_pages + 1)
    if page_key(site_url) not in {page_key(u) for u in seed_urls}:
        seed_urls.insert(0, site_url)
    seed_truncated = len(seed_urls) > max_pages
    seed_urls = seed_urls[:max_pages]

    # Link graph
    graph = {
        "pages": {},          # url -> {internal_links, external_links, inbound_count}
        "all_internal_targets": Counter(),  # url -> inbound link count
        "all_external_targets": Counter(),
        "anchor_texts": defaultdict(list),   # url -> [anchor_texts pointing to it]
        # Orphan detection (see analyze_link_profile) works on page_key()s.
        "entry_keys": {page_key(site_url)},  # the audited entry page, never an orphan
        "page_keys": {},                     # fetched url -> keys of its url and final url
        "inbound_keys": Counter(),           # key -> links from OTHER fetched pages
        "link_target_keys": set(),           # key of every page an internal link points to
        "failed_urls": [],
        "seed_truncated": seed_truncated,
    }

    crawled = set()
    crawled_keys = set()
    for url in seed_urls:
        key = page_key(url)
        if key in crawled_keys:
            continue
        crawled.add(url)
        crawled_keys.add(key)

        time.sleep(0.3)
        final_url, html = fetch_page(url)
        if not html:
            graph["failed_urls"].append(url)
            continue

        own_keys = {key, page_key(final_url)}
        graph["page_keys"][url] = own_keys
        if key in graph["entry_keys"]:
            graph["entry_keys"] |= own_keys

        links = extract_links(html, final_url, base_domain)

        for link in links["internal"]:
            if not is_page_url(link["url"]):
                continue
            target = page_key(link["url"])
            graph["link_target_keys"].add(target)
            # A page's link to itself (nav, logo, breadcrumb) is not inbound.
            if target not in own_keys:
                graph["inbound_keys"][target] += 1

        graph["pages"][url] = {
            "internal_out": len(links["internal"]),
            "external_out": len(links["external"]),
            "internal_links": [l["url"] for l in links["internal"][:20]],
        }

        for link in links["internal"]:
            graph["all_internal_targets"][link["url"]] += 1
            if link["anchor"]:
                graph["anchor_texts"][link["url"]].append(link["anchor"])

        for link in links["external"]:
            graph["all_external_targets"][link["url"]] += 1

    return graph, crawled, base_domain


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_link_profile(graph: dict, crawled: set, base_domain: str) -> dict:
    """Produce analysis from the crawled link graph."""
    pages = graph["pages"]
    internal_targets = graph["all_internal_targets"]

    # Orphan pages: fetched pages no other fetched page links to. Zero inbound
    # links is only evidence when the crawl saw every page that could hold the
    # link. A 20-URL sample of a 3,000-URL sitemap cannot see the hub that
    # links to a case study, so on a partial crawl the check reports that it
    # was not assessed instead of calling the case study an orphan.
    fetched_keys = set().union(*graph["page_keys"].values())
    unfetched_targets = graph["link_target_keys"] - fetched_keys
    incomplete_reasons = []
    if graph["seed_truncated"]:
        incomplete_reasons.append("the sitemap lists more URLs than --max-pages")
    if graph["failed_urls"]:
        incomplete_reasons.append(f"{len(graph['failed_urls'])} page(s) could not be fetched")
    if unfetched_targets:
        incomplete_reasons.append(f"{len(unfetched_targets)} linked page(s) were never fetched")

    orphan_pages = []
    if not incomplete_reasons:
        for url, keys in graph["page_keys"].items():
            if keys & graph["entry_keys"]:
                continue
            if not any(graph["inbound_keys"].get(k, 0) for k in keys):
                orphan_pages.append(url)
        orphan_pages.sort()

    # Top linked pages (highest inbound internal links)
    top_linked = internal_targets.most_common(20)

    # Pages with no outbound internal links (dead ends)
    dead_ends = [url for url, data in pages.items() if data["internal_out"] == 0]

    # External link distribution
    external_domains = Counter()
    for url in graph["all_external_targets"]:
        domain = urlparse(url).netloc
        external_domains[domain] += 1

    # Anchor text analysis
    anchor_diversity = {}
    for url, anchors in graph["anchor_texts"].items():
        unique = len(set(a.lower() for a in anchors))
        total = len(anchors)
        anchor_diversity[url] = {
            "total_anchors": total,
            "unique_anchors": unique,
            "diversity_ratio": round(unique / max(total, 1), 2),
        }

    # Internal link equity (simplified PageRank-like distribution)
    total_pages = len(pages)
    avg_internal_links = (
        sum(d["internal_out"] for d in pages.values()) / max(total_pages, 1)
    )

    # Issues
    issues = []
    if orphan_pages:
        issues.append({
            "type": "orphan_pages",
            "severity": "High",
            "count": len(orphan_pages),
            "finding": f"{len(orphan_pages)} orphan page(s) with zero inbound internal links.",
            "pages": orphan_pages[:10],
            "fix": "Add internal links from relevant content pages to these orphan pages.",
        })
    elif incomplete_reasons:
        issues.append({
            "type": "orphan_check_inconclusive",
            "severity": "Info",
            "finding": (
                f"Orphan pages not assessed: {len(pages)} page(s) fetched, and inbound links "
                f"from pages outside this crawl cannot be ruled out ({'; '.join(incomplete_reasons)})."
            ),
            "fix": "Compare a full-site crawl against the sitemap before reporting any page as an orphan.",
        })

    if dead_ends:
        issues.append({
            "type": "dead_end_pages",
            "severity": "Medium",
            "count": len(dead_ends),
            "finding": f"{len(dead_ends)} page(s) with no outbound internal links (dead ends).",
            "pages": dead_ends[:10],
            "fix": "Add contextual internal links to related content from these pages.",
        })

    if avg_internal_links < 3:
        issues.append({
            "type": "low_internal_linking",
            "severity": "High",
            "finding": f"Average internal links per page is only {avg_internal_links:.1f} (target: 5-10).",
            "fix": "Increase internal linking by adding contextual links within content.",
        })

    return {
        "pages_crawled": total_pages,
        "total_internal_links": sum(d["internal_out"] for d in pages.values()),
        "total_external_links": sum(d["external_out"] for d in pages.values()),
        "unique_internal_targets": len(internal_targets),
        "unique_external_domains": len(external_domains),
        "avg_internal_links_per_page": round(avg_internal_links, 1),
        "orphan_pages": {
            "status": "inconclusive" if incomplete_reasons else "complete",
            "count": len(orphan_pages),
            "urls": orphan_pages[:15],
            "reasons": incomplete_reasons,
        },
        "dead_end_pages": {
            "count": len(dead_ends),
            "urls": dead_ends[:15],
        },
        "top_linked_pages": [
            {"url": url, "inbound_links": count}
            for url, count in top_linked
        ],
        "top_external_domains": [
            {"domain": domain, "links": count}
            for domain, count in external_domains.most_common(15)
        ],
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# GSC backlink integration (optional)
# ---------------------------------------------------------------------------

def get_gsc_backlinks(credentials_path: str, site_url: str) -> dict:
    """Pull external links from Google Search Console (if available)."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        scopes = ["https://www.googleapis.com/auth/webmasters.readonly"]
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=scopes
        )
        service = build("searchconsole", "v1", credentials=creds)

        resp = service.links().list(siteUrl=site_url).execute()
        return {
            "available": True,
            "external_links": resp.get("externalLinks", [])[:20],
            "internal_links_sample": resp.get("internalLinks", [])[:10],
        }
    except ImportError:
        return {"available": False, "reason": "google-api-python-client not installed."}
    except Exception as exc:
        return {"available": False, "reason": str(exc)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Link Profile Analyzer — crawls site, builds link graph, identifies issues"
    )
    parser.add_argument("url", help="Site URL to analyze")
    parser.add_argument("--max-pages", type=int, default=50,
                        help="Max pages to crawl (default: 50)")
    parser.add_argument("--gsc-credentials", default="",
                        help="Path to GSC service account credentials (optional)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    print(f"Crawling {args.url}...", file=sys.stderr)
    graph, crawled, base_domain = crawl_site(args.url, max_pages=args.max_pages)

    print("Analyzing link profile...", file=sys.stderr)
    report = analyze_link_profile(graph, crawled, base_domain)
    report["site_url"] = args.url

    # Optional GSC backlinks
    if args.gsc_credentials:
        print("Fetching GSC backlinks...", file=sys.stderr)
        report["gsc_backlinks"] = get_gsc_backlinks(args.gsc_credentials, args.url)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return

    print(f"\nLink Profile Analysis — {args.url}")
    print("=" * 60)
    print(f"Pages crawled            : {report['pages_crawled']}")
    print(f"Total internal links     : {report['total_internal_links']}")
    print(f"Total external links     : {report['total_external_links']}")
    print(f"Unique internal targets  : {report['unique_internal_targets']}")
    print(f"Unique external domains  : {report['unique_external_domains']}")
    print(f"Avg internal links/page  : {report['avg_internal_links_per_page']}")

    orph = report["orphan_pages"]
    if orph["status"] == "inconclusive":
        print(f"\nOrphan pages: not assessed ({'; '.join(orph['reasons'])})")
    elif orph["count"]:
        print(f"\n🔴 Orphan Pages ({orph['count']}):")
        for u in orph["urls"][:5]:
            print(f"  - {u}")

    dead = report["dead_end_pages"]
    if dead["count"]:
        print(f"\n⚠️  Dead-End Pages ({dead['count']}):")
        for u in dead["urls"][:5]:
            print(f"  - {u}")

    if report["top_linked_pages"]:
        print(f"\nTop Linked Pages:")
        for p in report["top_linked_pages"][:10]:
            print(f"  [{p['inbound_links']:>3}] {p['url']}")

    if report["issues"]:
        print(f"\nIssues ({len(report['issues'])}):")
        for issue in report["issues"]:
            icon = "🔴" if issue["severity"] == "High" else "⚠️"
            print(f"  {icon} [{issue['type']}] {issue['finding']}")
            print(f"     Fix: {issue['fix']}")


if __name__ == "__main__":
    main()
