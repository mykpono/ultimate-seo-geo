#!/usr/bin/env python3
"""
Sitemap discovery, validation, and URL health checking.

Discovers sitemaps from robots.txt, validates format, and samples
sitemap URLs to verify they return HTTP 200 (catches GSC "Not found 404"
and soft 404 issues before they appear in Search Console).

Optional, additive analyses (the default output and score are unchanged):
    --lastmod              <lastmod> coverage, invalid/future values, one-date-everywhere,
                           and a 20-page sample compared with the pages' own modified dates
    --structure            sitemap index layout: files, sizes, per-section children,
                           duplicates, foreign hosts, http entries
    --reconcile GRAPH.json sitemap vs a site_graph.py crawl (six buckets)

Usage:
  python sitemap_checker.py https://example.com
  python sitemap_checker.py https://example.com --json
  python sitemap_checker.py https://example.com --sample 50
  python sitemap_checker.py https://example.com --check-all
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:
    print(json.dumps({"error": "requests required: pip install requests"}))
    sys.exit(1)

USER_AGENT = "Mozilla/5.0 (compatible; UltimateSEO-Sitemap/1.8)"

SEARCH_URL_PATTERNS = re.compile(
    r"[?&](q|query|search|s|search_term_string|keyword|term)=", re.I
)
FACETED_URL_PATTERNS = re.compile(
    r"[?&](sort|order|filter|page|offset|limit|color|size|brand|category|tag)=", re.I
)
TEMPLATE_PLACEHOLDER = re.compile(r"\{[^}]+\}")


def _fetch(url: str, timeout: int = 12) -> tuple[int | None, str]:
    try:
        r = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        )
        return r.status_code, r.text or ""
    except Exception as e:
        return None, str(e)


def _head_check(url: str, timeout: int = 10) -> dict:
    """HEAD request with GET fallback; returns status info."""
    result = {"url": url, "status": None, "error": None, "redirect": None, "soft_404": False}
    try:
        resp = requests.head(
            url, timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True, verify=False,
        )
        if resp.status_code == 405:
            resp = requests.get(
                url, timeout=timeout,
                headers={"User-Agent": USER_AGENT},
                allow_redirects=True, verify=False, stream=True,
            )
        result["status"] = resp.status_code
        if resp.history:
            result["redirect"] = {
                "from": url, "to": resp.url,
                "hops": len(resp.history),
            }
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("text/html"):
            body = ""
            try:
                body = resp.text[:5000] if hasattr(resp, "text") else ""
            except Exception:
                pass
            if body:
                lower = body.lower()
                soft_404_signals = [
                    "page not found", "404", "not found",
                    "no longer available", "does not exist",
                    "page doesn't exist", "page has been removed",
                ]
                for signal in soft_404_signals:
                    if signal in lower:
                        title_match = re.search(r"<title[^>]*>(.*?)</title>", lower)
                        if title_match and signal in title_match.group(1):
                            result["soft_404"] = True
                            break
    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except requests.exceptions.ConnectionError:
        result["error"] = "connection_failed"
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)[:100]
    return result


def _analyze_url_patterns(urls: list[str]) -> dict:
    """Detect problematic URL patterns that shouldn't be in sitemaps."""
    findings = {
        "search_urls": [],
        "faceted_urls": [],
        "template_urls": [],
        "parameter_urls": [],
    }
    for url in urls:
        if TEMPLATE_PLACEHOLDER.search(url):
            findings["template_urls"].append(url)
        elif SEARCH_URL_PATTERNS.search(url):
            findings["search_urls"].append(url)
        elif FACETED_URL_PATTERNS.search(url):
            findings["faceted_urls"].append(url)
        elif "?" in url:
            findings["parameter_urls"].append(url)
    return findings


def _resolve_sitemap_index(xml: str, base: str, timeout: int = 12) -> list[str]:
    """If xml is a sitemap index, fetch child sitemaps and collect all <loc> URLs."""
    child_sitemaps = re.findall(r"<sitemap>\s*<loc>\s*([^<\s]+)\s*</loc>", xml, re.I)
    all_locs = []
    for sm_url in child_sitemaps[:20]:
        if sm_url.startswith("/"):
            sm_url = urljoin(base + "/", sm_url.lstrip("/"))
        sc, body = _fetch(sm_url, timeout)
        if sc == 200:
            all_locs.extend(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body, re.I))
    return all_locs


# ---------------------------------------------------------------------------
# Optional analyses: --lastmod, --structure, --reconcile (additive; the default
# output and the score are unchanged when none is requested)
# ---------------------------------------------------------------------------

_URL_BLOCK_RE = re.compile(r"<url>(.*?)</url>", re.I | re.S)
_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)
_LASTMOD_RE = re.compile(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", re.I)
_SITEMAP_BLOCK_RE = re.compile(r"<sitemap>(.*?)</sitemap>", re.I | re.S)
_W3C_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$")

SINGLE_FILE_WARN = 10_000          # one file this big should be split by section
FILE_LIMIT = 50_000                # sitemaps.org hard limit per file
LASTMOD_IDENTICAL_SHARE = 0.90     # share of URLs sharing one lastmod value that reads as generated, not tracked
LASTMOD_MIN_URLS = 20
LASTMOD_SAMPLE = 20
STALE_DAYS = 7                     # page says it changed this much later than lastmod claims
FUTURE_GRACE_DAYS = 1


def _parse_entries(xml: str) -> tuple[list[dict], list[str], bool]:
    """(entries, child_sitemaps, is_index); entries are {url, lastmod}."""
    is_index = "<sitemapindex" in xml[:2000].lower()
    if is_index:
        children = []
        for block in _SITEMAP_BLOCK_RE.findall(xml):
            m = _LOC_RE.search(block)
            if m:
                children.append(m.group(1).strip())
        if not children:
            children = [u.strip() for u in _LOC_RE.findall(xml)]
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
        entries = [{"url": u.strip(), "lastmod": None} for u in _LOC_RE.findall(xml)]
    return entries, [], False


def _collect_entries(primary_url: str, xml: str, base: str, timeout: int = 12, max_children: int = 50) -> dict:
    """Every entry of the primary sitemap and its children, with the file each came from."""
    entries, children, is_index = _parse_entries(xml)
    files = [{"url": primary_url, "status": 200, "url_count": len(entries), "is_index": is_index, "bytes": len(xml.encode("utf-8", errors="ignore"))}]
    for e in entries:
        e["source"] = primary_url
    truncated = False
    for child in children[:max_children]:
        if child.startswith("/"):
            child = urljoin(base + "/", child.lstrip("/"))
        sc, body = _fetch(child, timeout)
        if sc != 200 or not body:
            files.append({"url": child, "status": sc, "url_count": 0, "is_index": False, "bytes": 0})
            continue
        c_entries, c_children, c_index = _parse_entries(body)
        files.append({"url": child, "status": 200, "url_count": len(c_entries), "is_index": c_index, "bytes": len(body.encode("utf-8", errors="ignore"))})
        for e in c_entries:
            e["source"] = child
        entries.extend(c_entries)
    if len(children) > max_children:
        truncated = True
    return {"entries": entries, "files": files, "is_index": is_index, "truncated": truncated}


def _parse_w3c(value: str):
    """A sitemap <lastmod> as an aware datetime, or None when malformed."""
    from datetime import datetime, timedelta, timezone
    m = _W3C_DATE_RE.match(value or "")
    if not m:
        return None
    y, mo, d, hh, mm, ss, tz = m.groups()
    try:
        dt = datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), int(ss or 0))
    except ValueError:
        return None
    if tz and tz != "Z":
        sign = 1 if tz[0] == "+" else -1
        digits = tz[1:].replace(":", "")
        offset = timedelta(hours=int(digits[:2]), minutes=int(digits[2:4]))
        return dt.replace(tzinfo=timezone(sign * offset))
    return dt.replace(tzinfo=timezone.utc)


def _page_modified_date(url: str, timeout: int = 10):
    """The date a page itself claims it changed: article:modified_time, JSON-LD
    dateModified, or the Last-Modified header. None when it says nothing."""
    from datetime import datetime, timezone
    from email.utils import parsedate_to_datetime
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, allow_redirects=True)
    except requests.exceptions.RequestException:
        return None, None
    html = resp.text if resp.status_code == 200 else ""
    m = re.search(r'property=["\']article:modified_time["\']\s+content=["\']([^"\']+)', html, re.I) or \
        re.search(r'content=["\']([^"\']+)["\']\s+property=["\']article:modified_time["\']', html, re.I)
    if m:
        dt = _parse_w3c(m.group(1).strip())
        if dt:
            return dt, "article:modified_time"
    m = re.search(r'"dateModified"\s*:\s*"([^"]+)"', html)
    if m:
        dt = _parse_w3c(m.group(1).strip())
        if dt:
            return dt, "dateModified"
    lm = resp.headers.get("Last-Modified")
    if lm:
        try:
            return parsedate_to_datetime(lm), "Last-Modified"
        except (TypeError, ValueError):
            pass
    return None, None


def analyze_lastmod(entries: list[dict], sample: int = LASTMOD_SAMPLE, check_pages: bool = True, now=None) -> tuple[dict, list[dict]]:
    """lastmod coverage, plausibility, and (sampled) agreement with the pages."""
    from collections import Counter
    from datetime import datetime, timedelta, timezone
    now = now or datetime.now(timezone.utc)
    total = len(entries)
    with_lm = [e for e in entries if e.get("lastmod")]
    invalid, future, parsed = [], [], []
    for e in with_lm:
        dt = _parse_w3c(e["lastmod"])
        if dt is None:
            invalid.append(e["url"])
            continue
        parsed.append((e, dt))
        if dt > now + timedelta(days=FUTURE_GRACE_DAYS):
            future.append(f"{e['url']} ({e['lastmod']})")
    values = Counter(e["lastmod"][:10] for e in with_lm)
    top_value, top_n = (values.most_common(1)[0] if values else (None, 0))
    identical_share = round(top_n / len(with_lm), 3) if with_lm else 0.0
    recent_24h = sum(1 for _, dt in parsed if now - dt < timedelta(hours=24))

    result = {
        "urls": total,
        "with_lastmod": len(with_lm),
        "coverage": round(len(with_lm) / total, 3) if total else 0.0,
        "invalid": invalid[:10],
        "invalid_count": len(invalid),
        "future": future[:10],
        "future_count": len(future),
        "most_common_value": top_value,
        "most_common_share": identical_share,
        "within_24h": recent_24h,
        "page_check": {"checked": 0, "compared": 0, "stale": [], "ahead": [], "agree": 0, "no_signal": 0},
    }
    issues: list[dict] = []
    if total and not with_lm:
        issues.append({"severity": "info", "finding": f"None of the {total} sitemap URLs carries <lastmod>.",
                       "fix": "Add <lastmod> with the real last-significant-change date; Google uses it for crawl scheduling only when it is consistently accurate."})
    if invalid:
        issues.append({"severity": "warning", "finding": f"{len(invalid)} <lastmod> value(s) are not W3C datetimes (e.g. {', '.join(invalid[:2])}).",
                       "fix": "Use YYYY-MM-DD or full ISO 8601 with a timezone."})
    if future:
        issues.append({"severity": "high", "finding": f"{len(future)} <lastmod> value(s) are in the future (e.g. {future[0]}).",
                       "fix": "Generate lastmod from the content's actual modification time, in UTC; future dates are ignored and discredit the rest."})
    if len(with_lm) >= LASTMOD_MIN_URLS and identical_share >= LASTMOD_IDENTICAL_SHARE:
        issues.append({"severity": "warning", "finding": f"{identical_share:.0%} of {len(with_lm)} <lastmod> values are the same date ({top_value}).",
                       "fix": "A single date across the site means lastmod is the build time, not the change time; Google stops trusting it. Emit each page's real modification date or drop the tag."})
    elif len(with_lm) >= LASTMOD_MIN_URLS and recent_24h == len(with_lm):
        issues.append({"severity": "info", "finding": f"All {len(with_lm)} <lastmod> values are within the last 24 hours.",
                       "fix": "If the site was not just republished wholesale, lastmod is being regenerated on every build; emit real change dates."})

    if check_pages and parsed and sample > 0:
        pick = parsed[:sample] if len(parsed) <= sample else random.sample(parsed, sample)
        pc = result["page_check"]
        for e, dt in pick:
            pc["checked"] += 1
            page_dt, source = _page_modified_date(e["url"])
            if page_dt is None:
                pc["no_signal"] += 1
                continue
            pc["compared"] += 1
            delta_days = (page_dt - dt).total_seconds() / 86400
            if delta_days > STALE_DAYS:
                pc["stale"].append({"url": e["url"], "lastmod": e["lastmod"], "page": page_dt.isoformat(), "source": source})
            elif delta_days < -30:
                pc["ahead"].append({"url": e["url"], "lastmod": e["lastmod"], "page": page_dt.isoformat(), "source": source})
            else:
                pc["agree"] += 1
        if pc["stale"]:
            issues.append({"severity": "warning", "finding": f"{len(pc['stale'])} of {pc['compared']} compared page(s) changed after their <lastmod> (e.g. {pc['stale'][0]['url']}: page {pc['stale'][0]['page'][:10]}, lastmod {pc['stale'][0]['lastmod'][:10]}).",
                           "fix": "Regenerate the sitemap when content changes, or drive lastmod from the same field as article:modified_time / dateModified."})
        if pc["ahead"] and pc["ahead"] and len(pc["ahead"]) >= max(2, pc["compared"] // 4):
            issues.append({"severity": "info", "finding": f"{len(pc['ahead'])} of {pc['compared']} compared page(s) have a <lastmod> more than 30 days after the date the page itself declares.",
                           "fix": "lastmod ahead of the page's own modified date reads as manufactured freshness; align the two."})
    return result, issues


def analyze_structure(files: list[dict], entries: list[dict], site_host: str, is_index: bool, truncated: bool = False) -> tuple[dict, list[dict]]:
    """How the sitemap is organised: files, sizes, section coverage, duplicates, hosts."""
    from collections import Counter, defaultdict
    total = len(entries)
    issues: list[dict] = []
    by_file_sections: dict[str, Counter] = defaultdict(Counter)
    hosts = Counter()
    schemes = Counter()
    seen = Counter()
    for e in entries:
        pr = urlparse(e["url"])
        hosts[pr.netloc.lower()] += 1
        schemes[pr.scheme.lower()] += 1
        seen[e["url"]] += 1
        segs = [x for x in pr.path.split("/") if x]
        by_file_sections[e["source"]][f"/{segs[0]}/" if segs else "/"] += 1
    duplicates = [u for u, n in seen.items() if n > 1]
    site_host = site_host.lower()
    other_hosts = {h: n for h, n in hosts.items() if h != site_host and h != f"www.{site_host}" and site_host != f"www.{h}"}
    children = [f for f in files if f["url"] != files[0]["url"]]
    empty = [f["url"] for f in children if f["status"] == 200 and f["url_count"] == 0 and not f["is_index"]]
    unreadable = [f"{f['url']} (HTTP {f['status']})" for f in children if f["status"] != 200]
    oversized = [f for f in files if f["url_count"] > FILE_LIMIT]
    section_files = []
    for f in files:
        if f["is_index"] or not f["url_count"]:
            continue
        secs = by_file_sections.get(f["url"], Counter())
        top, n = (secs.most_common(1)[0] if secs else ("/", 0))
        section_files.append({"file": f["url"], "urls": f["url_count"], "top_section": top, "top_section_share": round(n / f["url_count"], 2) if f["url_count"] else 0, "sections": len(secs)})
    organised = bool(children) and all(sf["top_section_share"] >= 0.8 for sf in section_files) if section_files else False

    result = {
        "is_index": is_index,
        "files": len(files),
        "children": len(children),
        "children_truncated": truncated,
        "largest_file_urls": max((f["url_count"] for f in files), default=0),
        "by_section": organised,
        "section_files": section_files[:30],
        "duplicates": duplicates[:10],
        "duplicate_count": len(duplicates),
        "other_hosts": other_hosts,
        "http_entries": schemes.get("http", 0),
        "empty_children": empty[:10],
        "unreadable_children": unreadable[:10],
    }
    if not is_index and total > SINGLE_FILE_WARN:
        issues.append({"severity": "warning", "finding": f"A single sitemap file lists {total:,} URLs.",
                       "fix": "Split into a sitemap index with one child per section (blog, docs, products…): Search Console then reports coverage per section and a broken section is obvious."})
    if oversized:
        issues.append({"severity": "critical", "finding": f"{len(oversized)} sitemap file(s) exceed the {FILE_LIMIT:,}-URL limit (e.g. {oversized[0]['url']}: {oversized[0]['url_count']:,}).",
                       "fix": "Search engines ignore entries beyond the limit; split the file."})
    if unreadable:
        issues.append({"severity": "high", "finding": f"{len(unreadable)} child sitemap(s) are unreadable: {', '.join(unreadable[:3])}.",
                       "fix": "Fix or remove the child from the index; every URL in it is currently unsubmitted."})
    if empty:
        issues.append({"severity": "warning", "finding": f"{len(empty)} child sitemap(s) list no URLs: {', '.join(empty[:3])}.",
                       "fix": "Remove empty children from the index or fix the generator that produces them."})
    if duplicates:
        issues.append({"severity": "warning", "finding": f"{len(duplicates)} URL(s) appear more than once across the sitemap files (e.g. {duplicates[0]}).",
                       "fix": "List each canonical URL once; duplicates usually mean two generators cover the same section."})
    if other_hosts:
        h, n = max(other_hosts.items(), key=lambda kv: kv[1])
        issues.append({"severity": "warning", "finding": f"{sum(other_hosts.values())} sitemap URL(s) are on other hosts (e.g. {n} on {h}).",
                       "fix": "A sitemap may only list URLs on the host that serves it (or one verified in Search Console); move those entries to that host's own sitemap."})
    if result["http_entries"] and schemes.get("https"):
        issues.append({"severity": "warning", "finding": f"{result['http_entries']} sitemap URL(s) use http:// on an https site.",
                       "fix": "List the https canonical URLs only."})
    if is_index and children and not organised and len(children) > 1:
        issues.append({"severity": "info", "finding": f"The sitemap index has {len(children)} child files but they are not organised by section (each file mixes sections).",
                       "fix": "Optional: one child per section makes Search Console coverage reports diagnosable per section."})
    return result, issues


def reconcile_with_graph(entries: list[dict], graph: dict) -> tuple[dict, list[dict]]:
    """Sitemap vs crawl: what is crawled but unlisted, and what is listed but
    non-200, redirected, noindex, canonicalised elsewhere, or (only after a
    complete crawl) never reached by a link."""
    import site_graph  # local import: keeps the default path free of bs4
    pages = graph.get("pages", {})
    crawl = graph.get("crawl", {})
    sm_keys = {site_graph.page_key(e["url"]): e["url"] for e in entries}
    failed = {site_graph.page_key(f["url"]): f for f in crawl.get("failed", [])}

    crawled_not_listed, redirected, noindex, canonical_elsewhere, non_200, unreached = [], [], [], [], [], []
    for key, page in pages.items():
        listed = key in sm_keys
        robots = (page.get("robots_meta") or "").lower()
        canon = page.get("canonical")
        canon_key = site_graph.page_key(canon) if canon else None
        if not listed:
            if page.get("status") == 200 and not page.get("redirected") and "noindex" not in robots and (canon_key is None or canon_key == key):
                crawled_not_listed.append(page["url"])
            continue
        if page.get("redirected"):
            redirected.append({"url": sm_keys[key], "final_url": page.get("final_url")})
        if "noindex" in robots:
            noindex.append(sm_keys[key])
        if canon_key and canon_key != key:
            canonical_elsewhere.append({"url": sm_keys[key], "canonical": canon})
    for key, f in failed.items():
        if key in sm_keys and (f.get("status") or 0) >= 400:
            non_200.append({"url": sm_keys[key], "status": f.get("status")})
    if crawl.get("complete"):
        unreached = [u for k, u in sm_keys.items() if k not in pages and k not in failed and site_graph.is_page_url(u)]

    result = {
        "graph_site": graph.get("site"),
        "crawl_complete": bool(crawl.get("complete")),
        "sitemap_urls": len(sm_keys),
        "crawled_pages": len(pages),
        "crawled_not_in_sitemap": {"count": len(crawled_not_listed), "examples": sorted(crawled_not_listed)[:10]},
        "sitemap_redirect": {"count": len(redirected), "examples": redirected[:10]},
        "sitemap_noindex": {"count": len(noindex), "examples": noindex[:10]},
        "sitemap_canonicalised_elsewhere": {"count": len(canonical_elsewhere), "examples": canonical_elsewhere[:10]},
        "sitemap_non_200": {"count": len(non_200), "examples": non_200[:10]},
        "sitemap_unreached_by_crawl": {"count": len(unreached), "examples": sorted(unreached)[:10], "status": "complete" if crawl.get("complete") else "inconclusive"},
        "not_crawled": sum(1 for k in sm_keys if k not in pages),
    }
    issues: list[dict] = []
    if crawled_not_listed:
        issues.append({"severity": "warning", "finding": f"{len(crawled_not_listed)} crawled, indexable page(s) are not in the sitemap (e.g. {', '.join(sorted(crawled_not_listed)[:3])}).",
                       "fix": "Add them, or confirm they are meant to be unlisted; Search Console reports 'Indexed, not submitted in sitemap' for these."})
    if noindex:
        issues.append({"severity": "high", "finding": f"{len(noindex)} sitemap URL(s) carry a noindex robots meta (e.g. {noindex[0]}).",
                       "fix": "A sitemap is a list of pages to index; remove noindex pages from it (or drop the noindex)."})
    if canonical_elsewhere:
        issues.append({"severity": "warning", "finding": f"{len(canonical_elsewhere)} sitemap URL(s) canonicalise to another URL (e.g. {canonical_elsewhere[0]['url']} -> {canonical_elsewhere[0]['canonical']}).",
                       "fix": "List the canonical URL instead; Search Console reports these as 'Duplicate, submitted URL not selected as canonical'."})
    if redirected:
        issues.append({"severity": "warning", "finding": f"{len(redirected)} sitemap URL(s) redirect (e.g. {redirected[0]['url']} -> {redirected[0]['final_url']}).",
                       "fix": "List final URLs only."})
    if non_200:
        issues.append({"severity": "high", "finding": f"{len(non_200)} sitemap URL(s) returned an error during the crawl (e.g. {non_200[0]['url']}: HTTP {non_200[0]['status']}).",
                       "fix": "Remove dead URLs or restore the pages; 404s in the sitemap are reported as errors in Search Console."})
    if crawl.get("complete") and unreached:
        issues.append({"severity": "warning", "finding": f"{len(unreached)} sitemap URL(s) were not reached by a complete crawl of the site's links (e.g. {', '.join(sorted(unreached)[:3])}).",
                       "fix": "These pages are submitted but orphaned: nothing links to them. Link each from its section hub or remove it from the sitemap."})
    return result, issues


def check_sitemaps(
    site_url: str,
    sample_size: int = 30,
    check_all: bool = False,
    max_workers: int = 8,
    lastmod: bool = False,
    structure: bool = False,
    reconcile_graph: str | None = None,
    lastmod_pages: bool = True,
) -> dict:
    parsed = urlparse(site_url)
    if not parsed.scheme:
        site_url = f"https://{site_url}"
        parsed = urlparse(site_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{base}/robots.txt"

    out: dict = {
        "url": site_url,
        "robots_url": robots_url,
        "sitemap_urls": [],
        "primary_sitemap_url": None,
        "primary_status": None,
        "url_count_estimate": 0,
        "url_health": {
            "checked": 0,
            "healthy": 0,
            "not_found_404": [],
            "server_errors_5xx": [],
            "redirected": [],
            "soft_404s": [],
            "timeouts": [],
            "errors": [],
        },
        "url_patterns": {
            "search_urls": [],
            "faceted_urls": [],
            "template_urls": [],
            "parameter_urls": [],
        },
        "issues": [],
        "recommendations": [],
    }

    robots_code, body = _fetch(robots_url)
    if robots_code != 200:
        out["issues"].append(
            {
                "severity": "warning",
                "finding": f"robots.txt not reachable (HTTP {robots_code}).",
                "fix": "Publish robots.txt with Sitemap: directives.",
            }
        )
        guess = f"{base}/sitemap.xml"
        guess_code, _ = _fetch(guess)
        if guess_code == 200:
            out["sitemap_urls"].append(guess)
    else:
        for line in body.splitlines():
            line = line.strip()
            if line.lower().startswith("sitemap:"):
                sm = line.split(":", 1)[1].strip()
                if sm:
                    out["sitemap_urls"].append(sm)

    if not out["sitemap_urls"]:
        out["issues"].append(
            {
                "severity": "high",
                "finding": "No Sitemap: lines in robots.txt and no fallback sitemap.xml.",
                "fix": "Add `Sitemap: https://example.com/sitemap.xml` to robots.txt.",
            }
        )
        out["recommendations"].append("Submit XML sitemaps in Google Search Console.")
        return out

    primary = out["sitemap_urls"][0]
    out["primary_sitemap_url"] = primary
    if primary.startswith("/"):
        primary = urljoin(base + "/", primary.lstrip("/"))

    sc, xml = _fetch(primary)
    out["primary_status"] = sc
    if sc != 200:
        out["issues"].append(
            {
                "severity": "critical",
                "finding": f"Primary sitemap returned HTTP {sc}: {primary}",
                "fix": "Fix sitemap URL or server response.",
            }
        )
        return out

    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml, re.I)

    is_index = "<sitemap>" in xml.lower() and "<sitemapindex" in xml.lower()
    if is_index:
        child_locs = _resolve_sitemap_index(xml, base)
        locs = child_locs if child_locs else locs

    out["url_count_estimate"] = len(locs)

    if len(locs) == 0 and "<url>" not in xml.lower() and "<sitemap>" not in xml.lower():
        out["issues"].append(
            {
                "severity": "warning",
                "finding": "Sitemap response does not look like XML sitemap (no <loc> entries).",
                "fix": "Validate sitemap format (XML sitemap index or urlset).",
            }
        )

    # --- URL pattern analysis ---
    if locs:
        out["url_patterns"] = _analyze_url_patterns(locs)
        patterns = out["url_patterns"]

        if patterns["template_urls"]:
            out["issues"].append({
                "severity": "critical",
                "finding": (
                    f"{len(patterns['template_urls'])} URL(s) in sitemap contain template "
                    f"placeholders (e.g. {{search_term_string}}): "
                    f"{', '.join(patterns['template_urls'][:3])}"
                ),
                "fix": (
                    "Remove template/placeholder URLs from sitemap immediately. "
                    "These are not real pages and waste crawl budget."
                ),
            })

        if patterns["search_urls"]:
            out["issues"].append({
                "severity": "high",
                "finding": (
                    f"{len(patterns['search_urls'])} search result URL(s) found in sitemap: "
                    f"{', '.join(patterns['search_urls'][:3])}"
                ),
                "fix": (
                    "Remove search result pages from sitemap. Add <meta name=\"robots\" "
                    "content=\"noindex\"> to search result pages to prevent indexation. "
                    "Block via robots.txt: Disallow: /search"
                ),
            })

        if patterns["faceted_urls"]:
            faceted_count = len(patterns["faceted_urls"])
            if faceted_count > 5:
                out["issues"].append({
                    "severity": "warning",
                    "finding": f"{faceted_count} faceted/filtered URLs in sitemap (sort, filter, page params).",
                    "fix": (
                        "Remove faceted URLs from sitemap. Use canonical tags pointing "
                        "to the master category page. Consider noindex on filtered views."
                    ),
                })

    # --- Sample URL health checks ---
    if locs and (sample_size > 0 or check_all):
        urls_to_check = list(locs)
        if not check_all and len(urls_to_check) > sample_size:
            urls_to_check = random.sample(urls_to_check, sample_size)

        health = out["url_health"]
        health["checked"] = len(urls_to_check)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_head_check, url): url for url in urls_to_check}
            for future in as_completed(futures):
                r = future.result()
                status = r["status"]
                if r["error"]:
                    if r["error"] == "timeout":
                        health["timeouts"].append(r["url"])
                    else:
                        health["errors"].append({"url": r["url"], "error": r["error"]})
                elif status and 400 <= status < 500:
                    health["not_found_404"].append({"url": r["url"], "status": status})
                elif status and status >= 500:
                    health["server_errors_5xx"].append({"url": r["url"], "status": status})
                elif r.get("soft_404"):
                    health["soft_404s"].append(r["url"])
                elif r.get("redirect"):
                    health["redirected"].append({
                        "url": r["url"],
                        "redirect_to": r["redirect"]["to"],
                        "hops": r["redirect"]["hops"],
                    })
                else:
                    health["healthy"] += 1

        n404 = len(health["not_found_404"])
        n5xx = len(health["server_errors_5xx"])
        nsoft = len(health["soft_404s"])
        nred = len(health["redirected"])

        if n404:
            out["issues"].append({
                "severity": "critical",
                "finding": (
                    f"{n404} sitemap URL(s) return 404 Not Found "
                    f"(checked {health['checked']}/{out['url_count_estimate']}): "
                    + ", ".join(e["url"] for e in health["not_found_404"][:5])
                ),
                "fix": (
                    "For each 404 URL: (1) If content was moved, add a 301 redirect to "
                    "the new URL. (2) If content was deleted, remove the URL from the "
                    "sitemap and let the 404 stand (or 410 for permanent removal). "
                    "(3) Fix any internal links still pointing to these URLs."
                ),
            })

        if n5xx:
            out["issues"].append({
                "severity": "critical",
                "finding": (
                    f"{n5xx} sitemap URL(s) return 5xx server errors: "
                    + ", ".join(e["url"] for e in health["server_errors_5xx"][:5])
                ),
                "fix": "Investigate server errors. Fix application bugs or resource limits causing 5xx responses.",
            })

        if nsoft:
            out["issues"].append({
                "severity": "high",
                "finding": (
                    f"{nsoft} sitemap URL(s) are soft 404s (return 200 but show 'not found' content): "
                    + ", ".join(health["soft_404s"][:5])
                ),
                "fix": (
                    "Return a real 404/410 status code instead of 200 for pages that don't "
                    "exist. Soft 404s waste crawl budget and confuse search engines."
                ),
            })

        if nred > 3:
            out["issues"].append({
                "severity": "warning",
                "finding": f"{nred} sitemap URLs redirect to different URLs.",
                "fix": (
                    "Update sitemap to use final destination URLs. Sitemaps should only "
                    "contain canonical, non-redirecting URLs."
                ),
            })

    if out["url_count_estimate"] > 0:
        out["recommendations"].append(
            f"Primary sitemap lists ~{out['url_count_estimate']} URLs — monitor Coverage in GSC."
        )

    # --- Optional analyses (additive; never touch the score) ---
    if lastmod or structure or reconcile_graph:
        collected = _collect_entries(primary, xml, base)
        entries = collected["entries"]
        if lastmod:
            out["lastmod"], extra = analyze_lastmod(entries, check_pages=lastmod_pages)
            out["issues"].extend(extra)
        if structure:
            out["structure"], extra = analyze_structure(collected["files"], entries, parsed.netloc, collected["is_index"], collected["truncated"])
            out["issues"].extend(extra)
        if reconcile_graph:
            import site_graph  # local import: the default path must not need bs4
            graph = site_graph.load_graph(reconcile_graph)
            out["reconcile"], extra = reconcile_with_graph(entries, graph)
            out["issues"].extend(extra)

    # --- Score ---
    score = 30
    if robots_code == 200 and out["sitemap_urls"]:
        score += 20
    if sc == 200:
        score += 15
    if out["url_count_estimate"] > 0:
        score += 10

    health = out["url_health"]
    if health["checked"] > 0:
        healthy_pct = health["healthy"] / health["checked"]
        if healthy_pct >= 0.95:
            score += 25
        elif healthy_pct >= 0.80:
            score += 15
        elif healthy_pct >= 0.60:
            score += 5
        else:
            score -= 10

    n_pattern_issues = (
        len(out["url_patterns"]["template_urls"])
        + len(out["url_patterns"]["search_urls"])
    )
    if n_pattern_issues > 0:
        score -= min(20, n_pattern_issues * 10)

    out["score"] = max(0, min(100, score))
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Sitemap discovery, validation, and URL health checking")
    p.add_argument("url", help="Site URL")
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--sample", type=int, default=30,
        help="Number of sitemap URLs to sample-check (default: 30; 0 to skip)",
    )
    p.add_argument(
        "--check-all", action="store_true",
        help="Check ALL sitemap URLs instead of sampling (slow for large sitemaps)",
    )
    p.add_argument(
        "--workers", "-w", type=int, default=8,
        help="Concurrent workers for URL checks (default: 8)",
    )
    p.add_argument("--lastmod", action="store_true", help="Check <lastmod> coverage and plausibility, and compare a sample against the pages' own modified dates")
    p.add_argument("--no-page-dates", action="store_true", help="With --lastmod: skip fetching sample pages (no extra requests)")
    p.add_argument("--structure", action="store_true", help="Report how the sitemap is organised: files, sizes, per-section children, duplicates, foreign hosts")
    p.add_argument("--reconcile", metavar="SITE_GRAPH_JSON", help="Compare the sitemap against a site_graph.py crawl: unlisted pages, listed noindex/redirect/canonicalised/404 URLs, orphans after a complete crawl")
    args = p.parse_args()
    data = check_sitemaps(
        args.url,
        sample_size=args.sample,
        check_all=args.check_all,
        max_workers=args.workers,
        lastmod=args.lastmod,
        structure=args.structure,
        reconcile_graph=args.reconcile,
        lastmod_pages=not args.no_page_dates,
    )
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
