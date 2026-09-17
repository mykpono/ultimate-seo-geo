#!/usr/bin/env python3
"""
Site graph: crawl a site once and persist a reusable structural model.

Discovers the sitemap (robots.txt, then the usual paths, expanding sitemap
indexes and recording <lastmod>), BFS-crawls internal links from the homepage,
and records for every fetched page its title, H1, canonical, robots meta,
JSON-LD types, word count, a hash of the main content, and every outbound
link together with the page REGION the link sits in (header, nav, footer,
breadcrumb, aside, main, other).

Region attribution is the new capability: every other checker in this repo
strips <nav>, <header> and <footer> as noise, so global navigation has been
invisible to the audit. Checkers that need the structure read the saved graph
(``--out site_graph.json``) instead of crawling again.

Completeness is recorded, never assumed. ``crawl.complete`` is true only when
no fetch failed, no cap truncated the crawl, and every internal page any
crawled page links to was itself fetched — the rule tests/test_orphan_detection.py
established: a claim that something is ABSENT site-wide needs a provably
complete crawl. ``sitemap.complete`` is true only when a sitemap was found and
every child sitemap was read without a cap cutting it short.

Usage:
    python site_graph.py https://example.com
    python site_graph.py https://example.com --max-pages 100 --depth 3 --out site_graph.json
    python site_graph.py https://example.com --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:
    print("Error: requests required. Install with: pip install requests")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 required. Install with: pip install beautifulsoup4")
    sys.exit(1)

import jsonld
from url_safety import validate_url

GRAPH_SCHEMA_VERSION = 1
USER_AGENT = "Mozilla/5.0 (compatible; UltimateSEO-SiteGraph/1.15; +https://github.com/mykpono/ultimate-seo-geo)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

SITEMAP_GUESSES = ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml", "/wp-sitemap.xml")
MAX_SITEMAPS = 50
MAX_SITEMAP_URLS = 50_000

# Link targets that are files, not pages. They are never crawled and a crawl
# is not incomplete for having skipped them (same list as link_profile.py).
NON_PAGE_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".avif", ".ico",
    ".zip", ".gz", ".mp3", ".mp4", ".webm", ".css", ".js", ".json", ".xml",
    ".txt", ".csv", ".xlsx", ".docx", ".pptx",
)

REGIONS = ("breadcrumb", "nav", "header", "footer", "aside", "main", "other")

# Path shapes that carry a date: /2026/09/, /2026-09-17-slug, /20260917/
_DATE_SEGMENT = re.compile(r"^(19|20)\d{2}(?:[-/]?(0[1-9]|1[0-2])(?:[-/]?(0[1-9]|[12]\d|3[01]))?)?(?:-|$)")
_NUMERIC_ID = re.compile(r"^\d{3,}$|-\d{3,}$|^[a-f0-9]{16,}$|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_PAGINATION = re.compile(r"(?:^|/)page/\d+/?$|(?:^|/)p/\d+/?$", re.I)
_PAGINATION_QUERY = {"page", "p", "pg", "paged", "offset", "start"}


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def page_key(url: str) -> str:
    """Identity of a page: scheme, lowercase host, path without trailing slash.

    A sitemap <loc> of /guide/ and an href of /guide are the same page, and so
    are EX.com and ex.com (same rule as link_profile.page_key). The fragment
    and the query string are not part of the identity.
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"


def is_page_url(url: str) -> bool:
    return not urlparse(url).path.lower().endswith(NON_PAGE_EXTENSIONS)


def same_site(host: str, site_host: str) -> bool:
    """True for the site's own host, with and without a leading www."""
    a = host.lower().split(":")[0]
    b = site_host.lower().split(":")[0]
    return a == b or a == f"www.{b}" or b == f"www.{a}"


def url_parts(url: str) -> dict:
    """Decompose a URL into the columns a structure audit reads.

    Modelled on advertools' url_to_df: ``dirs`` is the list of path segments,
    ``dir_1``..``dir_3`` are the first three (or None), ``last_dir`` is the
    final segment, ``depth`` is the segment count. Flags cover the shapes that
    matter for taxonomy and hygiene checks: dates in the path, numeric ids,
    pagination, an extension, a trailing slash, mixed case, query keys.
    """
    parsed = urlparse(url)
    raw_path = parsed.path or "/"
    segments = [s for s in raw_path.split("/") if s]
    last = segments[-1] if segments else ""
    extension = ""
    if "." in last:
        candidate = last.rsplit(".", 1)[1].lower()
        if 1 <= len(candidate) <= 5 and candidate.isalnum():
            extension = candidate
    query_keys = []
    if parsed.query:
        for pair in parsed.query.split("&"):
            key = pair.split("=", 1)[0]
            if key and key not in query_keys:
                query_keys.append(key)
    has_date = any(_DATE_SEGMENT.match(s) for s in segments)
    if not has_date and len(segments) >= 2:
        # /2026/09/slug: year and month as separate segments
        has_date = any(
            re.fullmatch(r"(19|20)\d{2}", a) and re.fullmatch(r"0[1-9]|1[0-2]", b)
            for a, b in zip(segments, segments[1:])
        )
    has_numeric_id = any(_NUMERIC_ID.search(s) for s in segments)
    is_paginated = bool(_PAGINATION.search(raw_path)) or any(k.lower() in _PAGINATION_QUERY for k in query_keys)
    return {
        "scheme": parsed.scheme.lower(),
        "host": parsed.netloc.lower(),
        "path": raw_path,
        "dirs": segments,
        "dir_1": segments[0] if len(segments) > 0 else None,
        "dir_2": segments[1] if len(segments) > 1 else None,
        "dir_3": segments[2] if len(segments) > 2 else None,
        "last_dir": last or None,
        "depth": len(segments),
        "extension": extension or None,
        "query_keys": query_keys,
        "has_query": bool(parsed.query),
        "has_date": has_date,
        "has_numeric_id": has_numeric_id,
        "is_paginated": is_paginated,
        "trailing_slash": len(raw_path) > 1 and raw_path.endswith("/"),
        "mixed_case": raw_path != raw_path.lower(),
    }


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_url(url: str, timeout: int = 10) -> dict:
    """Fetch one URL. Returns {status, final_url, html, headers, error}.

    Goes through validate_url so a sitemap <loc> of file:///etc/passwd or a
    link into a private network is refused rather than read. Never raises:
    the caller records the error and the crawl is marked incomplete.
    """
    result = {"status": None, "final_url": url, "html": "", "headers": {}, "error": None}
    safe = validate_url(url)
    if not safe.ok:
        result["error"] = f"URL safety check failed: {safe.reason}"
        return result
    try:
        resp = requests.get(safe.normalized_url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        result["status"] = resp.status_code
        result["final_url"] = resp.url
        result["headers"] = {k.lower(): v for k, v in resp.headers.items()}
        ctype = result["headers"].get("content-type", "")
        if resp.status_code == 200 and ("html" in ctype or "xml" in ctype or not ctype):
            result["html"] = resp.text
        elif resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
        else:
            result["error"] = f"non-HTML content-type: {ctype[:60]}"
    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except requests.exceptions.RequestException as exc:
        result["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    return result


# ---------------------------------------------------------------------------
# Sitemap discovery
# ---------------------------------------------------------------------------

_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)
_URL_BLOCK_RE = re.compile(r"<url>(.*?)</url>", re.I | re.S)
_SITEMAP_BLOCK_RE = re.compile(r"<sitemap>(.*?)</sitemap>", re.I | re.S)
_LASTMOD_RE = re.compile(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", re.I)


def parse_sitemap(xml: str) -> tuple[list[dict], list[str], bool]:
    """Return (entries, child_sitemaps, is_index).

    Each entry is {"url", "lastmod"}. A sitemap index yields child sitemap
    URLs and no entries. Malformed XML is parsed leniently with regexes: the
    audit needs the URLs, not a validation verdict.
    """
    is_index = "<sitemapindex" in xml[:2000].lower()
    if is_index:
        children = []
        for block in _SITEMAP_BLOCK_RE.findall(xml):
            m = _LOC_RE.search(block)
            if m:
                children.append(m.group(1))
        if not children:
            children = _LOC_RE.findall(xml)
        return [], children, True
    entries = []
    blocks = _URL_BLOCK_RE.findall(xml)
    if blocks:
        for block in blocks:
            m = _LOC_RE.search(block)
            if not m:
                continue
            lm = _LASTMOD_RE.search(block)
            entries.append({"url": m.group(1).strip(), "lastmod": lm.group(1).strip() if lm else None})
    else:
        entries = [{"url": u, "lastmod": None} for u in _LOC_RE.findall(xml)]
    return entries, [], False


def discover_sitemap(site_url: str, timeout: int = 12, max_sitemaps: int = MAX_SITEMAPS, max_urls: int = MAX_SITEMAP_URLS) -> dict:
    """Find and read the site's sitemaps. Records completeness and lastmod per URL."""
    parsed = urlparse(site_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    out = {
        "found": False,
        "complete": False,
        "reasons": [],
        "sources": [],
        "urls": {},
    }
    queue: deque[str] = deque()
    robots = fetch_url(f"{base}/robots.txt", timeout=timeout)
    if robots["status"] == 200 and robots["html"]:
        for line in robots["html"].splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("sitemap:"):
                sm = stripped.split(":", 1)[1].strip()
                if sm:
                    queue.append(sm)
    declared_in_robots = len(queue) > 0
    for guess in SITEMAP_GUESSES:
        queue.append(base + guess)

    seen: set[str] = set()
    truncated = False
    while queue:
        sm_url = queue.popleft()
        if sm_url in seen:
            continue
        if len(seen) >= max_sitemaps:
            truncated = True
            out["reasons"].append(f"stopped after {max_sitemaps} sitemap files")
            break
        seen.add(sm_url)
        # Once one sitemap has been found, the remaining guesses are only
        # tried when nothing was declared in robots.txt.
        if out["found"] and declared_in_robots and sm_url in {base + g for g in SITEMAP_GUESSES}:
            continue
        res = fetch_url(sm_url, timeout=timeout)
        body = res["html"]
        if res["status"] != 200 or not body or "<" not in body[:300]:
            if out["found"] or sm_url in {base + g for g in SITEMAP_GUESSES}:
                # A missing guess is not an error. A missing child sitemap is.
                if out["found"] and sm_url not in {base + g for g in SITEMAP_GUESSES}:
                    out["sources"].append({"url": sm_url, "status": res["status"], "url_count": 0, "is_index": False, "error": res["error"]})
                    out["reasons"].append(f"child sitemap unreadable: {sm_url} ({res['error']})")
            continue
        entries, children, is_index = parse_sitemap(body)
        out["found"] = True
        out["sources"].append({"url": sm_url, "status": 200, "url_count": len(entries), "is_index": is_index, "error": None})
        for child in children:
            if child.startswith("/"):
                child = urljoin(base + "/", child.lstrip("/"))
            if child not in seen:
                queue.append(child)
        for entry in entries:
            if len(out["urls"]) >= max_urls:
                truncated = True
                out["reasons"].append(f"stopped after {max_urls} sitemap URLs")
                break
            out["urls"].setdefault(entry["url"], {"lastmod": entry["lastmod"], "source": sm_url})
        if truncated:
            break

    if not out["found"]:
        out["reasons"].append("no sitemap found in robots.txt or at the usual paths")
    unreadable = any(s["status"] != 200 for s in out["sources"])
    out["complete"] = out["found"] and not truncated and not unreadable
    return out


# ---------------------------------------------------------------------------
# Page extraction
# ---------------------------------------------------------------------------

def _classes(tag) -> str:
    cls = tag.get("class") or []
    if isinstance(cls, str):
        cls = [cls]
    return " ".join(cls).lower()


def _is_breadcrumb(tag) -> bool:
    if tag.name not in ("nav", "ol", "ul", "div", "span", "section"):
        return False
    aria = (tag.get("aria-label") or "").lower()
    itemtype = (tag.get("itemtype") or "").lower()
    ident = (tag.get("id") or "").lower()
    return (
        "breadcrumb" in aria
        or "breadcrumb" in _classes(tag)
        or "breadcrumblist" in itemtype
        or "breadcrumb" in ident
    )


def link_region(a_tag) -> str:
    """The page region an <a> sits in: the nearest qualifying ancestor wins.

    Breadcrumb is tested before nav on each ancestor because a breadcrumb
    trail is usually ``<nav aria-label="breadcrumb">`` — one element that
    is both, and the more specific answer is the useful one.
    """
    for parent in a_tag.parents:
        if parent is None or parent.name is None:
            continue
        name = parent.name.lower()
        role = (parent.get("role") or "").lower()
        if _is_breadcrumb(parent):
            return "breadcrumb"
        if name == "nav" or role == "navigation":
            return "nav"
        if name == "header" or role == "banner":
            return "header"
        if name == "footer" or role == "contentinfo":
            return "footer"
        if name == "aside" or role == "complementary":
            return "aside"
        if name == "main" or role == "main" or name == "article":
            return "main"
    return "other"


def _jsonld_types(soup) -> list[str]:
    types: list[str] = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", raw))
            except json.JSONDecodeError:
                continue
        for node in jsonld.nodes(data):
            items = node.get("@graph") if isinstance(node.get("@graph"), list) else [node]
            for item in items:
                if isinstance(item, dict):
                    for t in jsonld.type_names(item.get("@type")):
                        if t not in types:
                            types.append(t)
    return types


def _main_text(soup) -> str:
    """Visible text of the page's own content: <main>, else <article>, else
    body minus the chrome. Used for the word count and the template hash."""
    root = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.find("article")
    if root is None:
        root = soup.body or soup
        for el in root(["script", "style", "noscript", "template", "svg", "nav", "header", "footer", "aside", "form"]):
            el.decompose()
    else:
        for el in root(["script", "style", "noscript", "template", "svg"]):
            el.decompose()
    return root.get_text(separator=" ", strip=True)


def extract_page(html: str, url: str, site_host: str) -> dict:
    """Structural facts about one fetched page, links annotated by region."""
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    h1_tag = soup.find("h1")
    canonical_tag = soup.find("link", rel=lambda v: v and "canonical" in [x.lower() for x in (v if isinstance(v, list) else [v])])
    robots_tag = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    html_tag = soup.find("html")

    out_links = []
    region_counts = {r: 0 for r in REGIONS}
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue
        full = urljoin(url, href)
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https"):
            continue
        full = full.split("#", 1)[0]
        internal = same_site(parsed.netloc, site_host)
        rel = a.get("rel") or []
        if isinstance(rel, str):
            rel = rel.split()
        region = link_region(a)
        region_counts[region] += 1
        out_links.append({
            "href": full,
            "key": page_key(full) if internal else None,
            "anchor": a.get_text(" ", strip=True)[:120],
            "rel": [r.lower() for r in rel],
            "region": region,
            "internal": internal,
        })

    jsonld_types = _jsonld_types(soup)
    text = _main_text(soup)
    words = re.findall(r"\b\w+\b", text)
    return {
        "url": url,
        "key": page_key(url),
        "title": title_tag.get_text(strip=True)[:300] if title_tag else None,
        "h1": h1_tag.get_text(" ", strip=True)[:300] if h1_tag else None,
        "h1_count": len(soup.find_all("h1")),
        "canonical": urljoin(url, canonical_tag["href"].strip()) if canonical_tag and canonical_tag.get("href") else None,
        "robots_meta": (robots_tag.get("content") or "").strip().lower() if robots_tag else None,
        "lang": (html_tag.get("lang") or "").strip().lower() if html_tag and html_tag.get("lang") else None,
        "jsonld_types": jsonld_types,
        "word_count": len(words),
        "main_text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16] if text else None,
        "out_links": out_links,
        "internal_out": sum(1 for l in out_links if l["internal"]),
        "external_out": sum(1 for l in out_links if not l["internal"]),
        "region_counts": region_counts,
    }


# ---------------------------------------------------------------------------
# Crawl
# ---------------------------------------------------------------------------

def crawl(site_url: str, max_pages: int = 100, max_depth: int = 3, timeout: int = 10, workers: int = 5, delay: float = 0.0) -> dict:
    """BFS crawl of internal links from ``site_url``.

    Returns {"pages": {key: page}, "complete", "reasons", "fetched", "failed",
    "truncated", "max_pages", "max_depth"}. Non-page URLs (files) are neither
    fetched nor counted against completeness.
    """
    parsed = urlparse(site_url)
    if not parsed.scheme:
        site_url = f"https://{site_url}"
        parsed = urlparse(site_url)
    site_host = parsed.netloc

    pages: dict[str, dict] = {}
    failed: list[dict] = []
    reasons: list[str] = []
    seen: set[str] = {page_key(site_url)}
    depth_of: dict[str, int] = {page_key(site_url): 0}
    queue: deque[tuple[str, int]] = deque([(site_url, 0)])
    truncated = False
    skipped_depth = 0

    def _fetch_one(item):
        url, depth = item
        if delay:
            time.sleep(delay)
        return url, depth, fetch_url(url, timeout=timeout)

    while queue:
        if len(pages) + len(failed) >= max_pages:
            truncated = True
            break
        room = max_pages - len(pages) - len(failed)
        batch = []
        while queue and len(batch) < min(workers, room):
            batch.append(queue.popleft())
        with ThreadPoolExecutor(max_workers=max(1, len(batch))) as pool:
            futures = [pool.submit(_fetch_one, item) for item in batch]
            results = [f.result() for f in as_completed(futures)]
        # Keep BFS order deterministic for the tests and the reader.
        results.sort(key=lambda r: (r[1], r[0]))
        for url, depth, res in results:
            key = page_key(url)
            if res["error"] or not res["html"]:
                failed.append({"url": url, "status": res["status"], "error": res["error"] or "empty body", "depth": depth})
                continue
            page = extract_page(res["html"], url, site_host)
            page["status"] = res["status"]
            page["final_url"] = res["final_url"]
            page["redirected"] = page_key(res["final_url"]) != key
            page["depth"] = depth
            page["content_type"] = res["headers"].get("content-type")
            page["last_modified_header"] = res["headers"].get("last-modified")
            pages[key] = page
            for link in page["out_links"]:
                if not link["internal"] or not is_page_url(link["href"]):
                    continue
                lk = link["key"]
                if lk in seen:
                    continue
                seen.add(lk)
                if depth + 1 > max_depth:
                    skipped_depth += 1
                    continue
                depth_of[lk] = depth + 1
                queue.append((link["href"], depth + 1))

    if queue:
        truncated = True
    if truncated:
        reasons.append(f"crawl stopped at max_pages={max_pages}: {len(queue)} discovered URL(s) not fetched")
    if skipped_depth:
        reasons.append(f"{skipped_depth} URL(s) beyond max_depth={max_depth} not fetched")
    if failed:
        reasons.append(f"{len(failed)} fetch(es) failed")

    # Every internal page target must be fetched for the crawl to be complete.
    unfetched_targets = 0
    for page in pages.values():
        for link in page["out_links"]:
            if link["internal"] and is_page_url(link["href"]) and link["key"] not in pages:
                unfetched_targets += 1
    if unfetched_targets and not truncated and not skipped_depth and not failed:
        reasons.append(f"{unfetched_targets} linked internal page(s) were not fetched")

    return {
        "site_host": site_host,
        "pages": pages,
        "complete": not truncated and not skipped_depth and not failed and unfetched_targets == 0,
        "reasons": reasons,
        "fetched": len(pages),
        "failed": failed,
        "truncated": truncated,
        "max_pages": max_pages,
        "max_depth": max_depth,
    }


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_graph(site_url: str, max_pages: int = 100, max_depth: int = 3, timeout: int = 10, workers: int = 5, delay: float = 0.0, with_sitemap: bool = True) -> dict:
    parsed = urlparse(site_url)
    if not parsed.scheme:
        site_url = f"https://{site_url}"
        parsed = urlparse(site_url)
    site_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"

    sitemap = discover_sitemap(site_url, timeout=timeout) if with_sitemap else {
        "found": False, "complete": False, "reasons": ["sitemap discovery disabled"], "sources": [], "urls": {}
    }
    crawled = crawl(site_url, max_pages=max_pages, max_depth=max_depth, timeout=timeout, workers=workers, delay=delay)

    pages = crawled["pages"]
    # Inbound counts by region, for every known page key.
    inbound: dict[str, dict] = {}
    for page in pages.values():
        for link in page["out_links"]:
            if not link["internal"]:
                continue
            if link["key"] == page["key"]:
                continue  # a page's link to itself (logo, breadcrumb) is not inbound
            slot = inbound.setdefault(link["key"], {r: 0 for r in REGIONS})
            slot[link["region"]] += 1
    for key, page in pages.items():
        counts = inbound.get(key, {r: 0 for r in REGIONS})
        page["inbound_by_region"] = counts
        page["inbound_total"] = sum(counts.values())
        page["in_sitemap"] = any(page_key(u) == key for u in sitemap["urls"]) if sitemap["urls"] else None
        page["parts"] = url_parts(page["url"])

    sitemap_keys = {page_key(u) for u in sitemap["urls"]}
    crawled_keys = set(pages)
    summary = {
        "pages_fetched": len(pages),
        "pages_failed": len(crawled["failed"]),
        "sitemap_urls": len(sitemap["urls"]),
        "sitemap_urls_with_lastmod": sum(1 for v in sitemap["urls"].values() if v["lastmod"]),
        "crawled_not_in_sitemap": len(crawled_keys - sitemap_keys) if sitemap["found"] else None,
        "sitemap_not_crawled": len(sitemap_keys - crawled_keys) if sitemap["found"] else None,
        "internal_links": sum(p["internal_out"] for p in pages.values()),
        "external_links": sum(p["external_out"] for p in pages.values()),
        "links_by_region": {r: sum(p["region_counts"][r] for p in pages.values()) for r in REGIONS},
        "max_depth_seen": max((p["depth"] for p in pages.values()), default=0),
    }
    return {
        "schema_version": GRAPH_SCHEMA_VERSION,
        "site": site_url,
        "domain": parsed.netloc,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sitemap": sitemap,
        "crawl": {k: v for k, v in crawled.items() if k != "pages"},
        "pages": pages,
        "summary": summary,
    }


def load_graph(path: str) -> dict:
    """Read a graph written by ``--out``. Raises on a missing or foreign file."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or "pages" not in data or "crawl" not in data:
        raise ValueError(f"{path} is not a site_graph.py output")
    version = data.get("schema_version")
    if version != GRAPH_SCHEMA_VERSION:
        raise ValueError(f"{path}: schema_version {version!r}, expected {GRAPH_SCHEMA_VERSION}")
    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(graph: dict) -> None:
    s = graph["summary"]
    c = graph["crawl"]
    sm = graph["sitemap"]
    print(f"\n🕸️  Site graph: {graph['site']}")
    print(f"   Pages fetched: {s['pages_fetched']}  failed: {s['pages_failed']}  max depth seen: {s['max_depth_seen']}")
    print(f"   Crawl complete: {'yes' if c['complete'] else 'no'}")
    for r in c["reasons"]:
        print(f"     - {r}")
    if sm["found"]:
        print(f"   Sitemap: {len(sm['sources'])} file(s), {s['sitemap_urls']} URL(s), {s['sitemap_urls_with_lastmod']} with lastmod, complete: {'yes' if sm['complete'] else 'no'}")
        print(f"     crawled but not in sitemap: {s['crawled_not_in_sitemap']}   in sitemap but not crawled: {s['sitemap_not_crawled']}")
    else:
        print("   Sitemap: not found")
    for r in sm["reasons"]:
        print(f"     - {r}")
    print(f"   Internal links: {s['internal_links']}  external: {s['external_links']}")
    print("   Links by region: " + ", ".join(f"{k}={v}" for k, v in s["links_by_region"].items() if v))


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl a site once and save a reusable structural graph")
    parser.add_argument("url", help="Site URL (homepage)")
    parser.add_argument("--max-pages", type=int, default=100, help="Maximum pages to fetch (default 100)")
    parser.add_argument("--depth", type=int, default=3, help="Maximum click depth from the homepage (default 3)")
    parser.add_argument("--timeout", type=int, default=10, help="Per-request timeout in seconds")
    parser.add_argument("--workers", type=int, default=5, help="Parallel fetches (default 5)")
    parser.add_argument("--delay", type=float, default=0.0, help="Seconds to wait before each fetch (politeness)")
    parser.add_argument("--no-sitemap", action="store_true", help="Skip sitemap discovery")
    parser.add_argument("--out", "-o", help="Write the graph JSON to this file")
    parser.add_argument("--json", "-j", action="store_true", help="Print the graph JSON to stdout")
    args = parser.parse_args()

    graph = build_graph(
        args.url,
        max_pages=max(1, args.max_pages),
        max_depth=max(0, args.depth),
        timeout=args.timeout,
        workers=max(1, args.workers),
        delay=max(0.0, args.delay),
        with_sitemap=not args.no_sitemap,
    )
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(graph, fh, indent=2)
    if args.json:
        print(json.dumps(graph, indent=2))
    else:
        _print_summary(graph)
        if args.out:
            print(f"   Saved: {args.out}")


if __name__ == "__main__":
    main()
