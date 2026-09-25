#!/usr/bin/env python3
"""
Check redirect chains for a URL.

Follows the full redirect chain, reports each hop (status + destination),
detects mixed HTTP/HTTPS, redirect loops, and chain length issues.

With --graph (a site_graph.py output) it audits the site's own links
instead: every internal link whose written URL is not where its page ends up
is followed hop by hop, and the redirects are ranked by how many pages link to
them, so the ones to fix first come first. A link that sits in the header,
nav or footer is flagged: it is on every page, and one template edit fixes it.

Usage:
    python redirect_checker.py https://example.com
    python redirect_checker.py https://example.com http://example.com --json
    python redirect_checker.py --graph site_graph.json --json
"""

import argparse
import json
import sys
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)


from url_safety import validate_url

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; UltimateSEO/1.8)"}


def check_redirects(url: str, max_redirects: int = 10, timeout: int = 10) -> dict:
    """
    Follow and analyze the redirect chain for a URL.

    Args:
        url: URL to check
        max_redirects: Maximum redirects to follow
        timeout: Request timeout in seconds

    Returns:
        Dictionary with redirect chain analysis
    """
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"

    result = {
        "url": url,
        "final_url": None,
        "chain": [],
        "total_hops": 0,
        "total_time_ms": 0,
        "has_loop": False,
        "has_mixed_protocol": False,
        "has_downgrade": False,
        "issues": [],
        "error": None,
    }

    seen = set()
    current = url

    try:
        for i in range(max_redirects + 1):
            if current in seen:
                result["has_loop"] = True
                result["issues"].append(f"🔴 Redirect loop detected at: {current}")
                break
            seen.add(current)

            # Re-validate EVERY hop, not just the seed. `current` is taken from
            # the previous response's Location header below, so an audited host
            # can steer this loop wherever it likes: one
            # `302 Location: http://169.254.169.254/latest/meta-data/` reaches
            # cloud metadata, and each hop's status and timing is recorded in
            # result["chain"]. This mirrors the per-hop check fetch_page.py does.
            safe = validate_url(current)
            if not safe.ok:
                result["issues"].append(
                    f"🔴 Refused to follow step {i+1}: {safe.reason} ({current})"
                )
                # Same key shape as a normal hop; downstream readers index
                # status/time_ms directly.
                result["chain"].append({
                    "step": i + 1,
                    "url": current,
                    "status": None,
                    "time_ms": 0,
                    "blocked": safe.reason,
                })
                break

            resp = requests.head(safe.normalized_url, timeout=timeout,
                                 headers=HEADERS, allow_redirects=False)

            hop = {
                "step": i + 1,
                "url": current,
                "status": resp.status_code,
                "time_ms": round(resp.elapsed.total_seconds() * 1000),
            }

            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location", "")
                if not location:
                    hop["error"] = "Redirect with no Location header"
                    result["chain"].append(hop)
                    result["issues"].append(f"🔴 Redirect at step {i+1} has no Location header")
                    break

                # Resolve relative URLs
                if not urlparse(location).scheme:
                    from urllib.parse import urljoin
                    location = urljoin(current, location)

                hop["redirect_to"] = location
                hop["redirect_type"] = {
                    301: "permanent (301)",
                    302: "temporary (302)",
                    303: "see other (303)",
                    307: "temporary (307)",
                    308: "permanent (308)",
                }.get(resp.status_code, f"unknown ({resp.status_code})")

                result["chain"].append(hop)
                result["total_time_ms"] += hop["time_ms"]
                current = location
            else:
                # Final destination
                hop["final"] = True
                result["chain"].append(hop)
                result["final_url"] = current
                result["total_time_ms"] += hop["time_ms"]
                break
        else:
            result["issues"].append(f"🔴 Too many redirects (>{max_redirects})")

    except requests.exceptions.RequestException as e:
        result["error"] = str(e)

    result["total_hops"] = max(0, len(result["chain"]) - 1)

    # Mixed protocol is normal when the chain upgrades http:// to https://, which
    # is the redirect every site should have. Only a step from https back down to
    # http is a defect: it drops the page off TLS and hands Google an insecure URL.
    schemes = [urlparse(hop["url"]).scheme for hop in result["chain"]]
    result["has_mixed_protocol"] = "http" in schemes and "https" in schemes
    downgrade = next((i for i in range(1, len(schemes)) if schemes[i - 1] == "https" and schemes[i] == "http"), None)
    result["has_downgrade"] = downgrade is not None
    if downgrade is not None:
        result["issues"].append(
            f"🔴 Redirect downgrades HTTPS to HTTP at step {downgrade} — keep every hop on https"
        )

    # Check chain length
    if result["total_hops"] > 2:
        result["issues"].append(
            f"🔴 Long redirect chain ({result['total_hops']} hops) — degrades crawl efficiency"
        )
    elif result["total_hops"] > 1:
        result["issues"].append(
            f"⚠️ Redirect chain has {result['total_hops']} hops — aim for max 1"
        )

    # Check for 302 where 301 should be used
    for hop in result["chain"]:
        if hop["status"] == 302:
            result["issues"].append(
                f"⚠️ Temporary redirect (302) at step {hop['step']} — "
                f"use 301 for permanent moves to preserve link equity"
            )

    return result


# ---------------------------------------------------------------------------
# Site-wide: the site's own links that redirect (--graph)
# ---------------------------------------------------------------------------

CHROME_REGIONS = frozenset({"nav", "header", "footer", "breadcrumb"})
DEFAULT_MAX_CHECKS = 100
TEMPORARY = (302, 303, 307)
LIST_LIMIT = 25


def _strip_fragment(url: str) -> str:
    return (url or "").split("#", 1)[0]


def _strip_query(url: str) -> str:
    return _strip_fragment(url).split("?", 1)[0]


def redirecting_links(graph: dict) -> dict:
    """{href: {"sources": set, "chrome": bool, "content": bool, "final": str}} for internal links that redirect.

    A link redirects when its href, as written (fragment dropped), differs from
    the final URL of the page it points to. Compared as written, not by page
    key, so /gallery -> /gallery/ counts: it is a real hop the site's own link
    makes. Query strings are ignored in the comparison: the graph keys pages
    without them, so ?utm_content=... variants (moz.com) are not evidence of a
    redirect. The result is a list of suspects; audit_site_redirects walks each
    one, and only the walk says whether it redirects. Links to pages the crawl
    did not fetch are counted apart, unjudged.
    """
    pages = graph.get("pages") or {}
    found, unfetched = {}, set()
    for page in pages.values():
        source = page.get("url")
        for link in page.get("out_links") or []:
            if not link.get("internal") or not link.get("key") or link["key"] == page.get("key"):
                continue
            target = pages.get(link["key"])
            href = _strip_fragment(link.get("href"))
            if target is None:
                unfetched.add(href)
                continue
            final = _strip_fragment(target.get("final_url") or target.get("url"))
            if not final or _strip_query(href) == _strip_query(final):
                continue
            slot = found.setdefault(href, {"sources": set(), "chrome": False, "content": False, "final": final})
            slot["sources"].add(source)
            if link.get("region") in CHROME_REGIONS or link.get("container") in ("header", "footer"):
                slot["chrome"] = True
            else:
                slot["content"] = True
    return {"links": found, "unfetched_targets": len(unfetched)}


def audit_site_redirects(graph: dict, max_checks: int = DEFAULT_MAX_CHECKS, check=None) -> dict:
    """Follow every redirecting internal link and rank them by the pages that carry them."""
    check = check or check_redirects
    found = redirecting_links(graph)
    ranked = sorted(found["links"].items(), key=lambda kv: (-len(kv[1]["sources"]), kv[0]))
    rows = []
    for href, info in ranked[:max_checks]:
        walked = check(href)
        chain = walked.get("chain") or []
        statuses = [hop.get("status") for hop in chain]
        final_status = statuses[-1] if statuses else None
        rows.append({
            "href": href,
            "linking_pages": len(info["sources"]),
            "sources": sorted(info["sources"])[:5],
            "in_navigation": info["chrome"],
            "in_content": info["content"],
            "hops": walked.get("total_hops", 0),
            "statuses": statuses,
            "final_url": walked.get("final_url") or info["final"],
            "final_status": final_status,
            "loop": bool(walked.get("has_loop")),
            "temporary": any(s in TEMPORARY for s in statuses[:-1]),
            "downgrade": bool(walked.get("has_downgrade")),
            "error": walked.get("error"),
        })
    chains = [r for r in rows if r["hops"] >= 2 or r["loop"]]
    broken = [r for r in rows if not r["loop"] and r["final_status"] is not None and r["final_status"] >= 400]
    single = [r for r in rows if r["hops"] == 1 and not r["loop"] and r not in broken]
    # A suspect the walk answers directly (0 hops) is not a redirect: the site serves both spellings, e.g.
    # /category/x and /category/x/ both 200 on smashingmagazine.com, and the crawl fetched the other one.
    resolved = [r for r in rows if r["hops"] == 0 and not r["loop"] and (r["final_status"] or 0) < 400]
    result = {
        "pages_in_graph": len(graph.get("pages") or {}),
        "suspects": len(found["links"]),
        "redirecting_links": len(rows) - len(resolved) + max(0, len(found["links"]) - max_checks),
        "checked": len(rows),
        "not_checked": max(0, len(found["links"]) - max_checks),
        "unfetched_targets": found["unfetched_targets"],
        "counts": {"single_hop": len(single), "chains": len(chains), "loops": sum(r["loop"] for r in rows),
                   "ends_in_error": len(broken), "temporary": sum(r["temporary"] for r in rows),
                   "serves_directly": len(resolved)},
        "redirects": [r for r in rows if r not in resolved][:LIST_LIMIT],
        "method": ("internal links whose written URL differs from the final URL of the page they point to, "
                   "followed hop by hop and ranked by linking pages"),
    }
    result["issues"] = site_redirect_issues(result, rows, chains, broken, single)
    return result


def site_redirect_issues(result, rows, chains, broken, single) -> list:
    issues = []
    nav_note = lambda group: (f" {sum(r['in_navigation'] for r in group)} of them sit in the header, nav or footer: "  # noqa: E731
                              "fix those once in the template." if any(r["in_navigation"] for r in group) else "")
    if chains or broken:
        worst = (chains + broken)[0]
        issues.append({
            "severity": "medium",
            "code": "redirects.site_chains",
            "lane": "Assisted",
            "finding": (f"{len(chains)} internal link target(s) redirect through 2+ hops or loop, and {len(broken)} "
                        f"redirect to an error page."),
            "evidence": "; ".join(f"{r['href']} -> {' -> '.join(str(s) for s in r['statuses'])} "
                                  f"(linked from {r['linking_pages']} page(s))" for r in (chains + broken)[:3]),
            "impact": "Every extra hop costs crawl budget and delays the page; a chain that ends in an error drops the link entirely.",
            "fix": ("Point each first redirect straight at the final URL (one hop), and give the error ones a live "
                    "destination. Redirect rules are high-risk: confirm before shipping." + nav_note(chains + broken)),
            "confidence": "Confirmed",
            "falsifiability": "Wrong if the chain differs for Googlebot; check one in Search Console's URL Inspection.",
            "leading_indicator": "Chains and errors in the next --graph run; 'Page with redirect' in Search Console's Page indexing.",
            "urls": [worst["href"]] + [r["href"] for r in (chains + broken)[1:10]],
        })
    if single:
        issues.append({
            "severity": "low",
            "code": "redirects.links_to_redirects",
            "lane": "Auto",
            "finding": (f"{len(single)} internal link target(s) redirect once; "
                        f"{sum(r['linking_pages'] for r in single)} page link(s) point at them."),
            "evidence": "; ".join(f"{r['href']} -> {r['final_url']} (from {r['linking_pages']} page(s))" for r in single[:3]),
            "impact": "Each link through a redirect costs a hop on every crawl and is reported as 'Page with redirect'.",
            "fix": ("Change each link to its final URL. The redirects stay for outside links." + nav_note(single)
                    + (f" {sum(r['temporary'] for r in single)} use a temporary redirect (302/303/307); if the move is "
                       "permanent, make it a 301." if any(r["temporary"] for r in single) else "")),
            "confidence": "Confirmed",
            "falsifiability": "Wrong if the final URL is not the canonical page (check its rel=canonical).",
            "leading_indicator": "redirecting_links in the next --graph run.",
            "urls": [r["href"] for r in single[:10]],
        })
    return issues


def print_site(result: dict) -> None:
    c = result["counts"]
    print(f"Site redirects — {result['suspects']} suspect link target(s) on {result['pages_in_graph']} pages; "
          f"{result['checked']} walked, {result['not_checked']} not walked; {result['redirecting_links']} redirect")
    print(f"  single hop {c['single_hop']} | chains {c['chains']} | loops {c['loops']} | end in error {c['ends_in_error']} | "
          f"temporary {c['temporary']} | serves directly (not a redirect) {c['serves_directly']}")
    print("=" * 78)
    for r in result["redirects"]:
        where = "nav" if r["in_navigation"] else "content"
        print(f"  {r['linking_pages']:>4} pages [{where}] {r['href']}")
        print(f"        {' -> '.join(str(s) for s in r['statuses'])}  {r['final_url']}"
              + ("  LOOP" if r["loop"] else "") + (f"  error: {r['error']}" if r["error"] else ""))
    for issue in result["issues"]:
        print(f"\n{issue['finding']}\n  Fix: {issue['fix']}")


def main():
    parser = argparse.ArgumentParser(description="Check redirect chains")
    parser.add_argument("urls", nargs="*", help="URL(s) to check")
    parser.add_argument("--graph", metavar="PATH",
                        help="site_graph.py output: audit every internal link that redirects, ranked by linking pages")
    parser.add_argument("--max-checks", type=int, default=DEFAULT_MAX_CHECKS,
                        help=f"With --graph: redirecting links to follow (default {DEFAULT_MAX_CHECKS})")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    if args.graph:
        import site_graph  # lazy: the plain URL check needs no site-structure modules
        try:
            graph = site_graph.load_graph(args.graph)
        except (OSError, ValueError) as exc:
            parser.error(f"--graph: {exc}")
        if args.max_checks < 1:
            parser.error("--max-checks must be positive")
        result = audit_site_redirects(graph, args.max_checks)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print_site(result)
        return
    if not args.urls:
        parser.error("give URL(s) to check, or --graph")

    results = []
    for url in args.urls:
        results.append(check_redirects(url))

    if args.json:
        output = results if len(results) > 1 else results[0]
        print(json.dumps(output, indent=2))
        return

    for result in results:
        if result["error"]:
            print(f"Error checking {result['url']}: {result['error']}")
            continue

        print(f"Redirect Chain — {result['url']}")
        print("=" * 50)

        if not result["chain"]:
            print("  No response received")
            continue

        for hop in result["chain"]:
            status = hop["status"]
            time_ms = hop["time_ms"]

            if hop.get("final"):
                icon = "✅" if 200 <= status < 300 else "🔴"
                print(f"  {icon} [{status}] {hop['url']} ({time_ms}ms) — FINAL")
            else:
                redirect_type = hop.get("redirect_type", "")
                print(f"  ↪️ [{status}] {hop['url']} ({time_ms}ms)")
                print(f"       → {hop.get('redirect_to', '?')} ({redirect_type})")

        print(f"\nTotal hops: {result['total_hops']} | Total time: {result['total_time_ms']}ms")

        if result["issues"]:
            print(f"\nIssues:")
            for issue in result["issues"]:
                print(f"  {issue}")
        print()


if __name__ == "__main__":
    main()
