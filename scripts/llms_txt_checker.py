#!/usr/bin/env python3
"""
Check for llms.txt file and validate its format.

llms.txt is a proposed standard for providing LLM-friendly site information.
See: https://llmstxt.org/

NOT a Google Search signal. Google confirmed in June 2026 that Search ignores
llms.txt entirely -- it neither helps nor hurts visibility, including in AI
Overviews and AI Mode. This checker reports presence and format quality for the
benefit of non-Google systems that read the file. A missing or low-scoring
llms.txt is informational: it must never be scored as a Google SEO or Google AI
citation defect. See references/ai-search-geo.md, "llms.txt Standard".

Usage:
    python llms_txt_checker.py https://example.com
    python llms_txt_checker.py https://example.com --json
    python llms_txt_checker.py https://example.com --check-sitemap --json
"""

import argparse
import gzip
import html
import json
import re
import sys
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

from url_safety import validate_url

USER_AGENT = "Mozilla/5.0 (compatible; UltimateSEO/1.8)"
MAX_SITEMAP_FILES = 20
MAX_SITEMAP_URLS = 50000
MAX_LINK_CHECKS = 20
DEAD_STATUSES = {404, 410}
LLMS_FILE_NAMES = {"llms.txt", "llms-full.txt"}
LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)


def check_llms_txt(url: str, timeout: int = 15) -> dict:
    """
    Fetch and validate llms.txt from a domain.

    Args:
        url: Website URL or domain
        timeout: Request timeout in seconds

    Returns:
        Dictionary with validation results
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)

    base = f"{parsed.scheme}://{parsed.netloc}"

    result = {
        "url": f"{base}/llms.txt",
        "full_url": f"{base}/llms-full.txt",
        "exists": False,
        "full_exists": False,
        "status": None,
        "full_status": None,
        "content": None,
        "parsed": {
            "title": None,
            "description": None,
            "sections": [],
            "links": [],
        },
        "quality": {
            "score": 0,
            "issues": [],
            "suggestions": [],
        },
        "error": None,
    }

    headers = {"User-Agent": "Mozilla/5.0 (compatible; UltimateSEO/1.8)"}

    # Check llms.txt
    try:
        resp = requests.get(f"{base}/llms.txt", timeout=timeout, headers=headers)
        result["status"] = resp.status_code

        if resp.status_code == 200:
            result["exists"] = True
            result["content"] = resp.text
            _parse_llms_txt(resp.text, result)
            _score_quality(result)
        elif resp.status_code == 404:
            result["quality"]["issues"].append(
                "➖ No llms.txt found — informational; Google Search ignores llms.txt"
            )
            result["quality"]["suggestions"].append(
                "Create /llms.txt with site name, description, and key page links"
            )
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)

    # Check llms-full.txt (optional extended version)
    try:
        resp = requests.get(f"{base}/llms-full.txt", timeout=timeout, headers=headers)
        result["full_status"] = resp.status_code
        result["full_exists"] = resp.status_code == 200
    except requests.exceptions.RequestException:
        pass

    return result


def _parse_llms_txt(content: str, result: dict):
    """Parse llms.txt content into structured data."""
    lines = content.strip().splitlines()

    if not lines:
        result["quality"]["issues"].append("⚠️ llms.txt is empty")
        return

    # First line should be the title (# Title)
    first_line = lines[0].strip()
    if first_line.startswith("# "):
        result["parsed"]["title"] = first_line[2:].strip()
    else:
        result["quality"]["issues"].append("⚠️ First line should be a title (# Site Name)")

    # Look for description (> blockquote)
    current_section = None

    for line in lines[1:]:
        line = line.strip()

        if not line:
            continue

        if line.startswith("> "):
            desc = line[2:].strip()
            if not result["parsed"]["description"]:
                result["parsed"]["description"] = desc
            else:
                result["parsed"]["description"] += " " + desc

        elif line.startswith("## "):
            current_section = line[3:].strip()
            result["parsed"]["sections"].append({
                "name": current_section,
                "links": [],
            })

        elif line.startswith("- ["):
            # Parse markdown links: - [Title](URL): Description
            match = re.match(r'-\s*\[([^\]]+)\]\(([^)]+)\)(?::\s*(.*))?', line)
            if match:
                link = {
                    "title": match.group(1),
                    "url": match.group(2),
                    "description": match.group(3) or "",
                }
                result["parsed"]["links"].append(link)
                if result["parsed"]["sections"]:
                    result["parsed"]["sections"][-1]["links"].append(link)


def _score_quality(result: dict):
    """Score the quality of llms.txt content."""
    score = 0
    parsed = result["parsed"]
    quality = result["quality"]

    # Title present (+20)
    if parsed["title"]:
        score += 20
    else:
        quality["issues"].append("⚠️ Missing title")

    # Description present (+20)
    if parsed["description"]:
        score += 20
        if len(parsed["description"]) < 20:
            quality["issues"].append("⚠️ Description too short")
        elif len(parsed["description"]) > 50:
            score += 5  # Bonus for good description
    else:
        quality["issues"].append("⚠️ Missing description (> blockquote)")
        quality["suggestions"].append("Add a description: > Brief site description")

    # Sections present (+15)
    if parsed["sections"]:
        score += 15
        if len(parsed["sections"]) >= 3:
            score += 5  # Bonus for good organization
    else:
        quality["suggestions"].append("Add sections (## Section Name) to organize content")

    # Links present (+20)
    if parsed["links"]:
        score += 20
        if len(parsed["links"]) >= 5:
            score += 5  # Bonus for comprehensive links
        if len(parsed["links"]) >= 10:
            score += 5
    else:
        quality["issues"].append("⚠️ No links found")
        quality["suggestions"].append("Add key page links: - [Page Title](URL): Description")

    # Content length (+5)
    content_len = len(result["content"] or "")
    if content_len > 200:
        score += 5

    quality["score"] = min(score, 100)


# ---------------------------------------------------------------------------
# llms.txt vs sitemap: stale and dead links. Informational, like everything
# about llms.txt -- Google Search ignores the file.
# ---------------------------------------------------------------------------


def _get(url: str, timeout: int = 15, max_redirects: int = 5):
    """GET with the URL-safety check on every hop.

    Returns (status, text, content, final_url, error). Links in llms.txt are
    third-party input, so no hop is fetched before it passes validate_url.
    """
    current = url
    try:
        for _ in range(max_redirects + 1):
            safe = validate_url(current)
            if not safe.ok:
                return None, "", b"", current, f"URL safety check failed: {safe.reason}"
            resp = requests.get(safe.normalized_url, timeout=timeout,
                                headers={"User-Agent": USER_AGENT}, allow_redirects=False)
            location = resp.headers.get("Location")
            if resp.is_redirect and location:
                current = urljoin(safe.normalized_url, location)
                continue
            return resp.status_code, resp.text or "", resp.content or b"", safe.normalized_url, None
        return None, "", b"", current, f"too many redirects (max {max_redirects})"
    except requests.exceptions.RequestException as exc:
        return None, "", b"", current, str(exc)


def page_key(url: str, base: str) -> tuple:
    """(host, path) identifying the page a URL stands for.

    llms.txt commonly links the markdown twin of a page (/docs/page.md or
    /docs/page.html.md), so .md, index.html, www. and trailing slashes do not
    count as differences. Scheme, query and fragment are ignored.
    """
    parsed = urlparse(urljoin(base.rstrip("/") + "/", (url or "").strip()))
    host = (parsed.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    path = parsed.path or "/"
    if path.endswith(".md"):
        path = path[:-3]
    if path.endswith("/index.html"):
        path = path[: -len("index.html")]
    elif path.endswith("/index"):
        path = path[: -len("index")]
    if len(path) > 1:
        path = path.rstrip("/") or "/"
    return host, path


def _sitemap_locations(base: str, timeout: int) -> list:
    status, text, _, _, _ = _get(f"{base}/robots.txt", timeout)
    found = []
    if status == 200:
        for line in text.splitlines():
            name, _, value = line.strip().partition(":")
            if name.strip().lower() == "sitemap" and value.strip():
                found.append(value.strip())
    return found or [f"{base}/sitemap.xml"]


def read_sitemap_urls(base: str, timeout: int = 15) -> dict:
    """Every <loc> page URL reachable from the site's sitemaps, and whether all were read."""
    queue = _sitemap_locations(base, timeout)
    seen, files, urls, errors = set(), [], [], []
    complete = True
    while queue:
        sitemap = urljoin(base + "/", queue.pop(0))
        if sitemap in seen:
            continue
        if len(files) >= MAX_SITEMAP_FILES:
            complete = False
            errors.append(f"stopped after {MAX_SITEMAP_FILES} sitemap files")
            break
        seen.add(sitemap)
        status, text, content, _, error = _get(sitemap, timeout)
        if status != 200:
            complete = False
            errors.append(f"{sitemap}: {error or f'HTTP {status}'}")
            continue
        if sitemap.endswith(".gz"):
            try:
                text = gzip.decompress(content).decode("utf-8", "replace")
            except (OSError, EOFError):
                pass  # served already decompressed; keep the text body
        files.append(sitemap)
        locs = [html.unescape(loc) for loc in LOC.findall(text)]
        if re.search(r"<sitemapindex", text, re.I):
            queue.extend(locs)
            continue
        urls.extend(locs)
        if len(urls) >= MAX_SITEMAP_URLS:
            urls = urls[:MAX_SITEMAP_URLS]
            complete = False
            errors.append(f"stopped after {MAX_SITEMAP_URLS} URLs")
            break
    return {"urls": urls, "files": files, "complete": complete, "errors": errors}


def compare_with_sitemap(result: dict, base: str, timeout: int = 15, max_link_checks: int = MAX_LINK_CHECKS) -> dict:
    """Find llms.txt links the sitemap no longer lists, and which of those are dead."""
    comparison = {
        "status": None,
        "sitemap_files": [],
        "sitemap_url_count": 0,
        "same_site_links": 0,
        "external_links": 0,
        "llms_file_links": 0,
        "missing_from_sitemap": [],
        "links_checked": 0,
        "dead_links": [],
        "link_check_errors": [],
        "errors": [],
    }
    result["sitemap_comparison"] = comparison
    issues = result["quality"]["issues"]
    if not result.get("exists"):
        comparison["status"] = "no llms.txt"
        return comparison

    sitemap = read_sitemap_urls(base, timeout)
    comparison.update(sitemap_files=sitemap["files"], sitemap_url_count=len(sitemap["urls"]), errors=sitemap["errors"])
    if not sitemap["files"]:
        comparison["status"] = "no sitemap"
        issues.append("ℹ️ No sitemap could be read, so llms.txt links were not compared against one")
        return comparison

    listed = {page_key(u, base) for u in sitemap["urls"]}
    # The site is every host its sitemap lists, not just the one typed: docs
    # that moved to a new domain redirect robots.txt and the sitemap there.
    site_hosts = {page_key(base, base)[0]} | {host for host, _ in listed}
    missing = {}
    for link in result["parsed"]["links"]:
        key = page_key(link["url"], base)
        if key[0] not in site_hosts:
            comparison["external_links"] += 1
            continue
        # Nested llms.txt files (one per product or section) are files for
        # machines, never sitemap pages.
        if key[1].rsplit("/", 1)[-1] in LLMS_FILE_NAMES:
            comparison["llms_file_links"] += 1
            continue
        comparison["same_site_links"] += 1
        if key not in listed:
            missing.setdefault(urljoin(base + "/", link["url"].strip()), None)
    comparison["missing_from_sitemap"] = list(missing)
    comparison["status"] = "complete" if sitemap["complete"] else "partial"

    for url in comparison["missing_from_sitemap"][:max_link_checks]:
        status, _, _, _, error = _get(url, timeout)
        comparison["links_checked"] += 1
        if status in DEAD_STATUSES:
            comparison["dead_links"].append({"url": url, "status": status})
        elif error:
            comparison["link_check_errors"].append({"url": url, "error": error})

    if comparison["missing_from_sitemap"]:
        where = "the sitemap" if sitemap["complete"] else "the sitemap files that could be read"
        shown = ", ".join(comparison["missing_from_sitemap"][:5])
        more = " …" if len(comparison["missing_from_sitemap"]) > 5 else ""
        issues.append(
            f"ℹ️ {len(comparison['missing_from_sitemap'])} llms.txt link(s) are not in {where}: {shown}{more}. "
            "They may be stale; confirm each still belongs in llms.txt"
        )
    if comparison["dead_links"]:
        shown = ", ".join(f"{d['url']} (HTTP {d['status']})" for d in comparison["dead_links"][:5])
        unchecked = len(comparison["missing_from_sitemap"]) - comparison["links_checked"]
        note = f"; {unchecked} more not checked" if unchecked > 0 else ""
        issues.append(f"ℹ️ {len(comparison['dead_links'])} llms.txt link(s) are dead: {shown}{note}. Remove or update them")
    return comparison


def main():
    parser = argparse.ArgumentParser(description="Check llms.txt for AI search optimization")
    parser.add_argument("url", help="Website URL or domain")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--check-sitemap",
        action="store_true",
        help="Compare llms.txt links with the sitemap and check links missing from it for 404/410 "
             "(informational; Google Search ignores llms.txt)",
    )

    args = parser.parse_args()
    result = check_llms_txt(args.url)
    if args.check_sitemap and not result["error"]:
        compare_with_sitemap(result, result["url"].rsplit("/llms.txt", 1)[0])

    if args.json:
        output = {k: v for k, v in result.items() if k != "content"}
        output["google_search_signal"] = False
        output["note"] = (
            "Google Search ignores llms.txt (confirmed June 2026): it neither helps nor "
            "hurts visibility, including AI Overviews and AI Mode. Report absence as "
            "informational only, never as a Google SEO or Google AI citation defect."
        )
        print(json.dumps(output, indent=2))
        return

    if result["error"]:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"llms.txt Check — {result['url']}")
    print("=" * 50)

    if result["exists"]:
        print(f"Status: ✅ Found (HTTP {result['status']})")
        print(f"Title: {result['parsed']['title'] or 'None'}")
        print(f"Description: {result['parsed']['description'] or 'None'}")
        print(f"Sections: {len(result['parsed']['sections'])}")
        print(f"Links: {len(result['parsed']['links'])}")
        print(f"Quality Score: {result['quality']['score']}/100")
    else:
        print(f"Status: ➖ Not found (HTTP {result['status']}) — not a Google Search defect")

    if result["full_exists"]:
        print(f"\nllms-full.txt: ✅ Found")
    else:
        print(f"\nllms-full.txt: ❌ Not found")

    comparison = result.get("sitemap_comparison")
    if comparison:
        print(f"\nSitemap comparison: {comparison['status']}")
        if comparison["sitemap_files"]:
            print(f"  Sitemap URLs read: {comparison['sitemap_url_count']} from {len(comparison['sitemap_files'])} file(s)")
            print(f"  llms.txt links on this site: {comparison['same_site_links']} (external: {comparison['external_links']})")
            print(f"  Not in sitemap: {len(comparison['missing_from_sitemap'])}; dead (404/410): {len(comparison['dead_links'])}")

    if result["quality"]["issues"]:
        print(f"\nIssues:")
        for issue in result["quality"]["issues"]:
            print(f"  {issue}")

    print(
        "\nNote: Google Search ignores llms.txt (confirmed June 2026) — it neither helps"
        "\nnor hurts visibility, including in AI Overviews and AI Mode. These results are"
        "\ninformational, for non-Google systems that read the file. Do not score them as"
        "\na Google SEO or Google AI citation defect."
    )

    if result["quality"]["suggestions"]:
        print(f"\nSuggestions:")
        for sug in result["quality"]["suggestions"]:
            print(f"  💡 {sug}")


if __name__ == "__main__":
    main()
