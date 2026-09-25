#!/usr/bin/env python3
"""
Generate an interactive SEO report (HTML, XLSX, PDF, or combined).

Runs all analysis scripts and aggregates results into a single,
self-contained HTML file styled with the Tobto design system (Ledger layout).
Optionally exports to Excel (.xlsx) or PDF for offline sharing.

Usage:
    python generate_report.py https://example.com
    python generate_report.py https://example.com --output my-report.html
    python generate_report.py https://example.com --crawl-deep --crawl-max-pages 40
    python generate_report.py https://example.com --format xlsx --output report.xlsx
    python generate_report.py https://example.com --format pdf --output report.pdf
    python generate_report.py https://example.com --format all --output report

PDF requires optional WeasyPrint (see requirements.txt). Without it, use HTML + browser Print → Save as PDF.

`--crawl-deep` runs broken_links and canonical_checker in multi-page crawl mode (capped); slower and
more load on the target host than the default single-URL checks.
"""

import argparse
import html as html_lib
import json
import os
from typing import Optional
import re
import subprocess
import sys

import jsonld
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlparse

from fetch_page import fetch_page as fetch_url, render_fallback_warning
from gsc_insights import load_page_traffic
from robots_checker import AI_CRAWLER_ROLES, BLOCKING_STATUSES, SEARCH_ENGINE_CRAWLERS, crawler_status

# Maximum number of analysis scripts to run in parallel.
# Bounded to avoid overwhelming the target server with simultaneous crawls.
_MAX_PARALLEL_SCRIPTS = 8

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPT_TIMEOUT_DEFAULT = 120
_SCRIPT_TIMEOUT_CRAWL = 300


def _needs_raw_html_disclaimer(env: dict) -> bool:
    """True when the stack often injects title/meta/canonical client-side."""
    p = (env or {}).get("primary", "")
    r = str((env or {}).get("runtime", ""))
    return p in ("Next.js", "Nuxt") or "JavaScript" in r


def run_script(script_name: str, args: list, timeout: int = 120) -> dict:
    """Run an analysis script and capture JSON output."""
    script_path = os.path.join(SCRIPT_DIR, script_name)
    if not os.path.exists(script_path):
        return {"error": f"Script {script_name} not found"}

    cmd = [sys.executable, script_path] + args + ["--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        err_msg = result.stderr.strip() or f"Exit code {result.returncode}"
        return {"error": f"[{script_name}] {err_msg}"}
    except subprocess.TimeoutExpired:
        return {"error": f"Script timed out after {timeout}s"}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON output from script"}
    except Exception as e:
        return {"error": str(e)}


def fetch_page(url: str, render: str = "never") -> tuple[str, str]:
    """Fetch page HTML to a temp file. Returns (path, render_warning).

    With render="auto" a failed render still returns the static HTML, and
    render_warning says so; the page-level checks run on that content.
    """
    fetched = fetch_url(url, timeout=20, render=render)
    warning = render_fallback_warning(fetched["render_error"]) if fetched.get("render_error") else ""
    if fetched.get("error") or not fetched.get("content"):
        return "", warning
    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
    tmp.write(fetched["content"])
    tmp.close()
    return tmp.name, warning


def detect_environment(html_text: str, url: str) -> dict:
    """Infer site environment/CMS/framework from source signals."""
    lower = (html_text or "").lower()
    domain = urlparse(url).netloc.lower()
    scores = {}
    reasons = {}

    def hit(name: str, points: int, reason: str):
        scores[name] = scores.get(name, 0) + points
        reasons.setdefault(name, []).append(reason)

    # Managed CMS signals
    if any(s in lower for s in ("bloggerusercontent.com", "www.blogger.com", "data:blog.", "b:skin")):
        hit("Blogger", 6, "Blogger template/assets detected")
    if domain.endswith("blogspot.com"):
        hit("Blogger", 4, "Blogspot domain detected")

    if any(s in lower for s in ("wp-content/", "wp-includes/", "wp-json")):
        hit("WordPress", 6, "WordPress core paths detected")
    if re.search(r'generator[^>]+wordpress', lower):
        hit("WordPress", 3, "WordPress generator meta detected")

    if any(s in lower for s in ("cdn.shopify.com", "shopify.theme", "shopify-section")):
        hit("Shopify", 6, "Shopify assets/theme markers detected")

    if any(s in lower for s in ("wixstatic.com", "wix.com", "wixsite")):
        hit("Wix", 6, "Wix assets detected")

    if any(s in lower for s in ("webflow", "w-webflow")):
        hit("Webflow", 5, "Webflow markers detected")

    if any(s in lower for s in ("squarespace.com", "static1.squarespace")):
        hit("Squarespace", 6, "Squarespace assets detected")

    if re.search(r'generator[^>]+ghost', lower) or "ghost/" in lower:
        hit("Ghost", 5, "Ghost generator/assets detected")

    # Framework signals
    if any(s in lower for s in ("/_next/", "__next_data__")):
        hit("Next.js", 6, "Next.js runtime/build markers detected")
    if any(s in lower for s in ("/_nuxt/", "__nuxt")):
        hit("Nuxt", 6, "Nuxt runtime/build markers detected")

    if not scores:
        return {
            "primary": "Unknown",
            "runtime": "Unknown",
            "confidence": "low",
            "signals": ["No strong CMS/framework markers were found in HTML source."],
            "alternatives": [],
        }

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary, top_score = ranked[0]
    confidence = "high" if top_score >= 8 else "medium" if top_score >= 5 else "low"
    runtime_map = {
        "Blogger": "Managed CMS",
        "WordPress": "Managed CMS",
        "Shopify": "Managed CMS / Commerce",
        "Wix": "Managed CMS",
        "Webflow": "Managed CMS",
        "Squarespace": "Managed CMS",
        "Ghost": "Managed CMS",
        "Next.js": "JavaScript Framework",
        "Nuxt": "JavaScript Framework",
    }
    return {
        "primary": primary,
        "runtime": runtime_map.get(primary, "Unknown"),
        "confidence": confidence,
        "signals": reasons.get(primary, [])[:5],
        "alternatives": [name for name, _ in ranked[1:3]],
    }


def _platform_hint(primary: str, area: str) -> str:
    """Provide platform-specific implementation guidance."""
    blogger = {
        "metadata": "In Blogger, update Theme -> Edit HTML and add tags in the <head> section (title template, meta description, OG/Twitter tags).",
        "heading": "In Blogger templates, keep exactly one content H1 per page (post title on posts, site headline on homepage).",
        "headers": "Blogger cannot set most response headers directly. Add Cloudflare in front and configure Response Header Transform Rules.",
        "llms": "Blogger cannot natively serve arbitrary root files. Serve /llms.txt via Cloudflare Workers/Pages or reverse-proxy route.",
        "links": "Fix broken internal links in post content and navigation widgets; update outdated post URLs and labels.",
        "performance": "Optimize Blogger theme widgets/scripts, compress hero/media assets, and defer non-critical third-party scripts.",
    }
    wordpress = {
        "metadata": "Use your SEO plugin (Yoast/RankMath/AIOSEO) or theme templates to set title/meta and OG/Twitter tags.",
        "heading": "Ensure one H1 in theme templates and avoid duplicate H1 in builders/widgets.",
        "headers": "Set headers via server config (Nginx/Apache) or CDN edge rules.",
        "llms": "Create /llms.txt at web root or route it through your web server.",
        "links": "Fix links in menus, content blocks, and internal link plugin data.",
        "performance": "Use caching, image optimization, script deferral, and CWV-focused plugin settings.",
    }
    nextjs = {
        "metadata": "Use the Next.js Metadata API (`app/`) or `next/head` (`pages/`) for title/meta/OG/Twitter tags.",
        "heading": "Set a single semantic H1 in each route component.",
        "headers": "Set security headers in `next.config.js` `headers()` or at your edge/CDN.",
        "llms": "Serve `/llms.txt` from `/public/llms.txt`.",
        "links": "Fix links in route components and content source files; validate with link checks in CI.",
        "performance": "Use `next/image`, dynamic imports, script strategy controls, and reduce main-thread JS.",
    }
    fallback = {
        "metadata": "Update page templates to set complete title/meta/OG/Twitter tags.",
        "heading": "Ensure each page has exactly one descriptive H1 aligned to intent.",
        "headers": "Set missing security headers at web server or CDN layer.",
        "llms": "Add `/llms.txt` at site root with concise site description and key URLs.",
        "links": "Repair or remove broken internal links and refresh outdated navigation targets.",
        "performance": "Compress critical assets, reduce render-blocking scripts, and optimize CWV bottlenecks.",
    }

    platform_map = {
        "Blogger": blogger,
        "WordPress": wordpress,
        "Shopify": fallback,
        "Wix": fallback,
        "Webflow": fallback,
        "Squarespace": fallback,
        "Ghost": fallback,
        "Next.js": nextjs,
        "Nuxt": nextjs,
    }
    return platform_map.get(primary, fallback).get(area, fallback.get(area, ""))


def build_environment_fixes(data: dict) -> list:
    """Build actionable issue fixes tailored to detected environment."""
    env = data.get("environment", {})
    platform = env.get("primary", "Unknown")
    fixes = []

    def add(
        severity: str,
        title: str,
        reason: str,
        fix: str,
        dependency: str = "Confirm the affected page template or CMS setting before editing.",
        failure_check: str = "Rerun the same audit check; this finding should disappear or downgrade.",
        leading_indicator: str = "Critical/warning count for this section declines in the next report.",
    ):
        fixes.append({
            "severity": severity,
            "title": title,
            "reason": reason,
            "fix": fix,
            "dependency": dependency,
            "failure_check": failure_check,
            "leading_indicator": leading_indicator,
        })

    op = data["sections"].get("onpage", {})
    sec = data["sections"].get("security", {})
    soc = data["sections"].get("social", {})
    llm = data["sections"].get("llms_txt", {})
    bl = data["sections"].get("broken_links", {})
    rd = data["sections"].get("readability", {})
    psi = data["sections"].get("pagespeed", {})

    title = (op.get("title") or "").strip()
    meta = (op.get("meta_description") or "").strip()
    h1s = op.get("h1", []) if isinstance(op.get("h1"), list) else []

    if not h1s:
        add(
            "critical",
            "Missing H1 on page",
            "No primary content heading was detected, which weakens topical clarity.",
            _platform_hint(platform, "heading"),
        )

    if not meta or len(meta) < 110 or len(meta) > 170:
        add(
            "warning",
            "Meta description is missing or out of range",
            "This can reduce SERP CTR and snippet quality.",
            _platform_hint(platform, "metadata"),
        )

    if not title or len(title) < 30 or len(title) > 65:
        add(
            "warning",
            "Title tag needs optimization",
            "Title length/content is likely suboptimal for rankings and click-through.",
            _platform_hint(platform, "metadata"),
        )

    missing_headers = sec.get("headers_missing", {})
    if missing_headers:
        add(
            "critical" if len(missing_headers) >= 4 else "warning",
            f"{len(missing_headers)} security headers missing",
            "Missing headers reduce trust and can expose the site to browser/security risks.",
            _platform_hint(platform, "headers"),
        )

    if not llm.get("exists"):
        add(
            "info",
            "No llms.txt found (not a Google Search signal)",
            "Google confirmed in June 2026 that Search ignores llms.txt: it neither helps nor hurts "
            "visibility, including in AI Overviews and AI Mode. Absence costs nothing on Google. "
            "Some non-Google systems read the file, but no platform has confirmed it influences "
            "citation selection. Informational only — do not prioritise this over crawler access, "
            "indexation, citability, or entity signals.",
            _platform_hint(platform, "llms"),
            leading_indicator="Not applicable — llms.txt has no measurable Google Search effect. Track AI visibility through crawler access, indexation, entities, and citations instead.",
        )

    rob = data["sections"].get("robots", {})
    blocked_search = [
        crawler for crawler, state in (rob.get("ai_crawler_status") or {}).items()
        if state in BLOCKING_STATUSES and AI_CRAWLER_ROLES.get(crawler) == "search"
    ]
    if blocked_search:
        add(
            "warning",
            f"robots.txt blocks {len(blocked_search)} AI search crawler(s)",
            f"{', '.join(blocked_search)} cannot fetch the site. These crawlers build the indexes that "
            "ChatGPT search, Claude, Perplexity and other AI answer engines cite, so the site cannot be "
            "cited there. Blocking training crawlers such as GPTBot or ClaudeBot is a separate "
            "licensing choice and is not flagged.",
            "Remove the Disallow rules, or the `User-agent: *` block, that cover these crawlers. "
            "Training-crawler blocks can stay.",
            dependency="Confirm with the site owner that AI search visibility is wanted; some sites block these crawlers on purpose.",
            leading_indicator="robots_checker.py reports these crawlers as allowed, and citations from those engines can appear.",
        )

    # Preferred sources is a news/publisher lever (see references/ai-search-geo.md).
    # Raising it on a site that never appears in Top Stories is noise, so gate the
    # finding on a publisher signal rather than reporting it everywhere.
    ps = data["sections"].get("preferred_sources", {})
    # Flattened via jsonld.type_names: str() on a list @type produced
    # "['NewsArticle', 'Article']", which matches nothing below, so the
    # preferred-sources findings vanished on every multi-typed publisher page.
    schema_types = {
        name
        for s in (op.get("schema") or [])
        if isinstance(s, dict)
        for name in jsonld.type_names(s.get("@type"))
    }
    looks_like_publisher = bool(schema_types & {"NewsArticle", "NewsMediaOrganization", "LiveBlogPosting"})
    if ps and not ps.get("error") and looks_like_publisher:
        integ = ps.get("integration", {})
        if integ.get("button_element") and not integ.get("publisher_js"):
            add(
                "warning",
                "Preferred sources button present but publisher.js is not loaded",
                "The <div google-add-preferred-source-btn> placeholder renders nothing without the "
                "Google publisher script, so the opt-in is silently broken for every reader.",
                'Add <script async src="https://news.google.com/swg/js/v1/publisher.js"></script> before the button element.',
                leading_indicator="The button renders and readers can select the site as a preferred source.",
            )
        elif not ps.get("implemented"):
            add(
                "info",
                "No preferred sources opt-in found",
                "This site publishes news-style content but offers readers no way to mark it as a "
                "preferred source. Preferred sources drive the 'preferred' badge and more prominent "
                "Top Stories placement, and since July 17, 2026 can surface inside AI Overviews on "
                "developing-news queries — the only AI-answer lever the reader controls.",
                "Add the documented two-line button near existing reader intent (article footer or "
                'newsletter module): <script async src="https://news.google.com/swg/js/v1/publisher.js">'
                "</script> followed by <div google-add-preferred-source-btn></div>.",
                leading_indicator="Preferred-source selections rise; Top Stories placement carries the 'preferred' badge.",
            )

    broken_count = bl.get("summary", {}).get("broken", 0)
    soft_404_count = bl.get("summary", {}).get("soft_404s", 0)
    if broken_count > 0:
        add(
            "critical" if broken_count >= 5 else "warning",
            f"{broken_count} broken links detected",
            "Broken internal links hurt crawl flow and user trust.",
            _platform_hint(platform, "links"),
        )
    if soft_404_count > 0:
        add(
            "warning",
            f"{soft_404_count} soft 404(s) detected",
            "Pages returning 200 but showing 'not found' content waste crawl budget.",
            "Return a real 404/410 status code for pages that don't exist. Update internal links to remove references to these pages.",
        )

    sm = data["sections"].get("sitemap", {})
    sm_health = sm.get("url_health", {})
    sm_404s = len(sm_health.get("not_found_404", []))
    sm_soft = len(sm_health.get("soft_404s", []))
    sm_patterns = sm.get("url_patterns", {})
    sm_templates = len(sm_patterns.get("template_urls", []))
    sm_search = len(sm_patterns.get("search_urls", []))
    if sm_404s > 0:
        add(
            "critical",
            f"{sm_404s} sitemap URL(s) return 404",
            "Sitemap URLs returning 404 waste crawl budget and appear as errors in Google Search Console.",
            "Remove 404 URLs from sitemap. If content moved, add 301 redirects. Fix internal links pointing to dead pages.",
        )
    if sm_soft > 0:
        add(
            "warning",
            f"{sm_soft} sitemap URL(s) are soft 404s",
            "Pages in sitemap returning 200 but showing 'not found' content confuse search engines.",
            "Return real 404/410 status codes for dead pages, or restore genuine content.",
        )
    if sm_templates > 0 or sm_search > 0:
        add(
            "critical" if sm_templates > 0 else "warning",
            f"Problematic URLs in sitemap ({'template placeholders' if sm_templates else 'search result pages'})",
            "Search result and template URLs should never be in sitemaps — they waste crawl budget and dilute indexation.",
            "Remove search/template URLs from sitemap. Add noindex to search result pages. Block via robots.txt if needed.",
        )

    can = data["sections"].get("canonical", {})
    can_issues = can.get("issues", []) if isinstance(can.get("issues"), list) else []
    can_critical = sum(1 for i in can_issues if isinstance(i, dict) and i.get("severity") in ("critical", "high"))
    if can_critical > 0:
        add(
            "critical",
            f"{can_critical} canonical tag issue(s) detected",
            "Canonical tag problems cause 'Google chose different canonical' errors in Search Console.",
            "Ensure every page has a single, absolute, self-referencing canonical with consistent protocol (HTTPS) and domain (www vs non-www). Fix any canonical pointing to a redirect or 404.",
        )
    elif not can.get("canonical") and not can.get("error"):
        add(
            "warning",
            "Missing canonical tag",
            "Without a canonical tag, Google decides which URL to index — often choosing wrong.",
            "Add <link rel=\"canonical\" href=\"[absolute-self-url]\"> to every indexable page.",
        )

    il = data["sections"].get("internal_links", {})
    il_redirected = len(il.get("redirected_pages", []))
    if il_redirected > 0:
        add(
            "warning" if il_redirected < 5 else "critical",
            f"{il_redirected} internal link(s) point to redirect URLs",
            "GSC reports these as 'Page with redirect'. Stale links waste crawl budget and dilute link equity.",
            "Update all internal links to point to the final destination URL. Remove redirect URLs from sitemap.",
        )

    # Programmatic SEO issues
    pseo = data["sections"].get("programmatic_seo", {})
    if pseo and not pseo.get("error") and pseo.get("pattern_groups_found", 0) > 0:
        pseo_crit = pseo.get("total_critical_issues", 0)
        pseo_warn = pseo.get("total_warnings", 0)
        if pseo_crit > 0:
            add(
                "critical",
                f"{pseo_crit} critical programmatic SEO issue(s) detected",
                "Template pages have scaled content abuse risk (low uniqueness, duplicate titles, thin content).",
                "Add genuinely unique per-page content. Each page needs ≥40% unique content and unique title/H1/meta.",
            )
        elif pseo_warn > 2:
            add(
                "warning",
                f"{pseo_warn} programmatic SEO warnings",
                "Template pages have quality concerns that could trigger Google's Helpful Content system.",
                "Review template pages for content differentiation and internal linking.",
            )

    can_alt = can.get("summary", {}).get("alternate_pages", 0) if isinstance(can.get("summary"), dict) else 0
    if can_alt > 0:
        add(
            "warning" if can_alt < 10 else "critical",
            f"{can_alt} page(s) flagged as 'Alternate page with proper canonical'",
            "These pages have non-self-referencing canonicals — Google won't index them.",
            "If pages have unique content, change canonical to self-referencing. If true duplicates, consider 301 redirect to canonical target.",
        )

    il_broken = len(il.get("broken_internal_pages", []))
    il_soft = len(il.get("soft_404_pages", []))
    if il_broken > 0:
        add(
            "critical",
            f"{il_broken} internal page(s) return 404 during crawl",
            "Internal pages returning 404 break user journeys and waste link equity.",
            _platform_hint(platform, "links"),
        )
    if il_soft > 0:
        add(
            "warning",
            f"{il_soft} internal page(s) are soft 404s",
            "Soft 404 pages look broken to search engines despite returning HTTP 200.",
            "Return real 404/410 status codes or restore genuine content on these pages.",
        )

    og_missing = soc.get("og_missing", [])
    tw_missing = soc.get("twitter_missing", [])
    if og_missing or tw_missing:
        add(
            "warning",
            "Social meta tags are incomplete",
            "Missing OG/Twitter tags weakens social previews and share quality.",
            _platform_hint(platform, "metadata"),
        )

    if psi.get("error"):
        add(
            "info",
            "Performance measurement incomplete",
            "PageSpeed API returned an error, so CWV recommendations are less reliable.",
            "Rerun `pagespeed.py` with `--api-key` and then prioritize LCP/INP/CLS fixes from that output.",
        )

    if rd.get("flesch_reading_ease", 100) < 40 or rd.get("avg_sentence_length", 0) > 25:
        add(
            "warning",
            "Content readability is difficult",
            "Long, complex text can reduce engagement and comprehension.",
            "Rewrite key sections with shorter sentences (15-20 words), shorter paragraphs (2-4 sentences), and clearer subheadings.",
        )

    if not fixes:
        add(
            "pass",
            "No major implementation blockers detected",
            "Core checks look healthy for current scope.",
            "Continue monitoring with regular crawls and keep metadata/security/performance baselines in CI.",
        )

    return fixes


def _recommendation_metadata(issue: dict, section_name: str) -> dict:
    """Attach falsifiable recommendation metadata to structured findings."""
    dependency = (
        issue.get("dependency")
        or issue.get("depends_on")
        or "Verify the affected page, template, or data source before changing production output."
    )
    failure_check = (
        issue.get("failure_check")
        or issue.get("how_to_know_failed")
        or issue.get("validation")
        or f"Rerun the {section_name} check; this finding should disappear, downgrade, or show improved evidence."
    )
    leading_indicator = (
        issue.get("leading_indicator")
        or issue.get("metric")
        or f"Next audit shows fewer warnings in {section_name} and no new dependent regressions."
    )
    return {
        "dependency": dependency,
        "failure_check": failure_check,
        "leading_indicator": leading_indicator,
    }


# ---------------------------------------------------------------------------
# Traffic at stake: Search Console clicks joined to findings
# ---------------------------------------------------------------------------
# Severity says how wrong something is; clicks say how much it costs. A finding
# that names URLs is charged those URLs' Search Console clicks. One from a check
# that audits only the report's own page is charged that page. One from a
# site-level check (robots.txt, headers, sitemaps) touches every page and gets
# no per-page figure. Anything else gets none: a number is only printed when a
# URL ties it to the finding.
PAGE_SCOPED_CHECKS = frozenset({
    "onpage", "social", "schema_validation", "image_seo", "readability", "content_quality", "article",
    "citability", "hidden_instructions", "pagespeed", "redirects", "canonical", "hreflang",
})
SITE_WIDE_CHECKS = frozenset({
    "robots", "ai_search_access", "ai_bot_access", "security", "llms_txt", "sitemap", "entity",
    "indexnow_probe", "local_signals", "preferred_sources",
})
_TRAFFIC_URL_FIELDS = ("url", "page", "urls", "pages")


def traffic_key(url) -> str:
    """host/path with www., scheme, query, fragment and trailing slash dropped.

    Looser than gsc_insights.page_key on purpose: a report run on https://ex.com
    must still meet the https://www.ex.com/ rows of a URL-prefix property.
    """
    parsed = urlparse(str(url or "").strip())
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return f"{host}{parsed.path.rstrip('/') or '/'}" if host else ""


def traffic_from_pages(pages, source: str, window=None) -> dict:
    """The lookup attach_traffic reads: {"pages": {traffic_key: {clicks, impressions}}, ...}."""
    by_key = {}
    for row in pages or []:
        if not isinstance(row, dict):
            continue
        key = traffic_key(row.get("page"))
        if not key:
            continue
        slot = by_key.setdefault(key, {"clicks": 0, "impressions": 0})
        slot["clicks"] += int(row.get("clicks") or 0)
        slot["impressions"] += int(row.get("impressions") or 0)
    return {
        "source": source,
        "window": list(window) if window else None,
        "pages": by_key,
        "total_clicks": sum(v["clicks"] for v in by_key.values()),
        "total_impressions": sum(v["impressions"] for v in by_key.values()),
    }


def _named_site_urls(source: dict, text: str, site_host: str) -> list:
    """traffic_keys of the audited site's URLs a finding names, in order, deduplicated."""
    found = []
    for field in _TRAFFIC_URL_FIELDS:
        value = source.get(field)
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, dict):
                item = item.get("url") or item.get("page")
            if isinstance(item, str):
                found.append(item)
    found += _URL_RE.findall(text)
    keys = []
    for url in found:
        key = traffic_key(str(url).rstrip(".,;:"))
        if key and key.split("/", 1)[0] == site_host and key not in keys:
            keys.append(key)
    return keys


def attach_traffic(issue: dict, data: dict):
    """The finding's traffic at stake, or None when there is no Search Console data or no URL to tie it to."""
    traffic = data.get("gsc_traffic")
    if not traffic:
        return None
    source = issue.get("source_issue") or {}
    site_host = traffic_key(data.get("url")).split("/", 1)[0]
    text = " ".join(str(part or "") for part in (issue.get("finding"), source.get("evidence")))
    keys = _named_site_urls(source, text, site_host)
    basis = "URLs named in the finding"
    if not keys and issue["section"] in PAGE_SCOPED_CHECKS and data.get("url"):
        keys, basis = [traffic_key(data["url"])], "the audited page"
    base = {"source": traffic["source"], "window": traffic["window"]}
    if not keys:
        if issue["section"] in SITE_WIDE_CHECKS:
            return {"scope": "site", **base}
        return None
    matched = [traffic["pages"][k] for k in keys if k in traffic["pages"]]
    return {
        "scope": "pages",
        "clicks": sum(m["clicks"] for m in matched),
        "impressions": sum(m["impressions"] for m in matched),
        "urls_named": len(keys),
        "urls_matched": len(matched),
        "basis": basis,
        **base,
    }


def _traffic_rank(issue: dict) -> tuple:
    """Sort key inside one severity: site-wide first, then clicks at stake, then everything unjoined."""
    traffic = issue.get("traffic")
    if not traffic:
        return (2, 0)
    if traffic["scope"] == "site":
        return (0, 0)
    return (1, -traffic["clicks"]) if traffic["clicks"] else (2, 0)


def _traffic_window(traffic: dict) -> str:
    window = traffic.get("window")
    return f"{window[0]} to {window[1]}" if window and all(window) else traffic.get("source") or "Search Console"


def traffic_text(traffic) -> str:
    if not traffic:
        return ""
    if traffic["scope"] == "site":
        return "Site-wide: affects every page, so no per-page figure."
    named = traffic["urls_named"]
    if not traffic["urls_matched"]:
        return (f"No Search Console clicks for the {named} URL{'s' if named != 1 else ''} it names "
                f"({_traffic_window(traffic)}).")
    return (f"{traffic['clicks']:,} clicks · {traffic['impressions']:,} impressions on {traffic['urls_matched']} of "
            f"{named} URL{'s' if named != 1 else ''} ({traffic['basis']}; {_traffic_window(traffic)}).")


SITE_GRAPH_MAX_PAGES = 80
SITE_GRAPH_DEPTH = 2


def build_site_graph(url: str) -> str | None:
    """Run site_graph.py once and return the saved graph's path, or None.

    A failed graph never fails the report: the structure checkers then crawl
    for themselves (slower) and the sitemap check runs without --reconcile.
    """
    fd, path = tempfile.mkstemp(prefix="site_graph_", suffix=".json")
    os.close(fd)
    result = run_script(
        "site_graph.py",
        [url, "--max-pages", str(SITE_GRAPH_MAX_PAGES), "--depth", str(SITE_GRAPH_DEPTH), "--out", path],
        timeout=_SCRIPT_TIMEOUT_CRAWL,
    )
    if result.get("error") or not os.path.exists(path) or os.path.getsize(path) == 0:
        print(f"  ⚠️ site_graph.py: {result.get('error') or 'no graph written'} — structure checks will crawl individually")
        if os.path.exists(path):
            os.unlink(path)
        return None
    return path


def collect_data(
    url: str,
    *,
    crawl_deep: bool = False,
    crawl_max_pages: int = 30,
    crawl_depth: int = 2,
    render: str = "never",
    gsc_property: str | None = None,
) -> dict:
    """Run all analysis scripts and collect results.

    With gsc_property, gsc_insights.py runs in the same batch: its findings
    become the display-only search_performance check and its page totals are
    the traffic joined to every finding (see attach_traffic).
    """
    print(f"🔍 Analyzing {url}...")
    if crawl_deep:
        print(
            f"  📎 --crawl-deep: broken links + canonical checks use multi-page crawl "
            f"(depth={crawl_depth}, max_pages={crawl_max_pages}); slower and more server load."
        )
    data = {
        "url": url,
        "domain": urlparse(url).netloc,
        "timestamp": datetime.now().isoformat(),
        "sections": {},
        "crawl_deep": crawl_deep,
        "crawl_max_pages": crawl_max_pages,
        "crawl_depth": crawl_depth,
        "render_mode": render,
    }

    # Fetch page for parse_html and readability
    print("  ⏳ Fetching page HTML...")
    html_path, render_warning = fetch_page(url, render=render)
    if render_warning:
        print(f"  ⚠️  {render_warning}")
        data["render_warning"] = render_warning
    page_html = ""
    if html_path and os.path.exists(html_path):
        try:
            with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
                page_html = f.read()
        except OSError:
            page_html = ""
    data["environment"] = detect_environment(page_html, url)

    broken_args = [url, "--workers", "5", "--timeout", "8"]
    if crawl_deep:
        broken_args.extend(
            ["--crawl", "--depth", str(crawl_depth), "--max-pages", str(crawl_max_pages)]
        )

    canonical_args = [url]
    if crawl_deep:
        canonical_args.extend(
            ["--crawl", "--depth", str(crawl_depth), "--max-pages", str(crawl_max_pages)]
        )

    # One shared crawl for the site-structure checks (page types, navigation,
    # architecture, sitemap reconciliation). Built before the parallel batch,
    # like html_path; if it fails the three checkers crawl for themselves.
    print("  ⏳ Building site graph (one crawl, up to %d pages)..." % SITE_GRAPH_MAX_PAGES)
    graph_path = build_site_graph(url)
    sitemap_args = [url]
    if graph_path:
        sitemap_args += ["--lastmod", "--no-page-dates", "--structure", "--reconcile", graph_path]
        structure_args = [url, "--graph", graph_path]
    else:
        structure_args = [url]

    analyses = [
        ("robots", "robots_checker.py", [url]),
        ("ai_bot_access", "ai_bot_access.py", [url]),
        ("security", "security_headers.py", [url]),
        ("social", "social_meta.py", [url]),
        ("redirects", "redirect_checker.py", [url]),
        ("llms_txt", "llms_txt_checker.py", [url]),
        ("broken_links", "broken_links.py", broken_args),
        ("internal_links", "internal_links.py", [url, "--depth", "1", "--max-pages", "15"] + (["--graph", graph_path] if graph_path else [])),
        ("pagespeed", "pagespeed.py", [url, "--strategy", "mobile"]),
        # New analysis scripts (supplementary — failures don't block report)
        ("entity", "entity_checker.py", [url]),
        ("link_profile", "link_profile.py", [url, "--max-pages", "20"]),
        ("hreflang", "hreflang_checker.py", [url]),
        ("duplicate_content", "duplicate_content.py", [url]),
        ("content_quality", "content_quality.py", [url]),
        ("sitemap", "sitemap_checker.py", sitemap_args),
        # Site structure (display-only, never in CHECK_WEIGHTS)
        ("page_types", "page_type_classifier.py", structure_args),
        ("navigation", "navigation_checker.py", structure_args),
        ("architecture", "site_architecture.py", structure_args),
        ("canonical", "canonical_checker.py", canonical_args),
        ("programmatic_seo", "programmatic_seo_auditor.py", [url, "--max-pages", "80"]),
        ("local_signals", "local_signals_checker.py", [url]),
        ("preferred_sources", "preferred_sources_checker.py", [url]),
        ("indexnow_probe", "indexnow_checker.py", [url, "--probe"]),
    ]
    if gsc_property:
        analyses.append(("search_performance", "gsc_insights.py", [gsc_property, "--all"]))

    # Add parse_html and readability if page was fetched
    if html_path:
        analyses.append(("onpage", "parse_html.py", [html_path, "--url", url]))
        analyses.append(("readability", "readability.py", [html_path]))
        analyses.append(("article", "article_seo.py", [url]))

    # Merge HTML-file-based checks into the same parallel batch.
    # html_path is already written to disk at this point, so all tasks are
    # ready to run concurrently.
    if html_path and os.path.exists(html_path):
        analyses.append(("schema_validation", "validate_schema.py", [html_path]))
        analyses.append(("image_seo", "image_checker.py", [html_path, "--base-url", url]))
        analyses.append(("hidden_instructions", "hidden_instructions.py", [html_path]))
        analyses.append(("citability", "citability_checker.py", [html_path]))

    def _run_one(item: tuple) -> tuple:
        name, script, args = item
        start = time.time()
        timeout = (
            _SCRIPT_TIMEOUT_CRAWL
            if (crawl_deep and name in ("broken_links", "canonical")) or name == "search_performance"
            else _SCRIPT_TIMEOUT_DEFAULT
        )
        result = run_script(script, args, timeout=timeout)
        elapsed = round(time.time() - start, 1)
        return name, script, result, elapsed

    print(f"  ⏳ Running {len(analyses)} checks in parallel (max {_MAX_PARALLEL_SCRIPTS} workers)...")
    with ThreadPoolExecutor(max_workers=_MAX_PARALLEL_SCRIPTS) as pool:
        futures = {pool.submit(_run_one, item): item for item in analyses}
        for fut in as_completed(futures):
            name, script, result, elapsed = fut.result()
            data["sections"][name] = result
            status = "⚠️ error" if "error" in result and result.get("error") else "✅"
            print(f"  {status} {script} ({elapsed}s)")

    # Prefer canonical_checker URL when raw HTML had no <link rel="canonical">
    op = data["sections"].get("onpage", {})
    cansec = data["sections"].get("canonical", {})
    if isinstance(op, dict) and not op.get("error") and not (op.get("canonical") or "").strip():
        c = cansec.get("canonical") if isinstance(cansec, dict) else None
        if c:
            op = dict(op)
            op["canonical"] = c
            op["canonical_from_audit"] = True
            data["sections"]["onpage"] = op

    # Cleanup temp files
    if html_path and os.path.exists(html_path):
        os.unlink(html_path)
    if graph_path and os.path.exists(graph_path):
        os.unlink(graph_path)

    data["environment_fixes"] = build_environment_fixes(data)

    sp = data["sections"].get("search_performance")
    if isinstance(sp, dict) and isinstance(sp.get("pages"), list):
        data["gsc_traffic"] = traffic_from_pages(sp["pages"], "gsc_insights.py", (sp.get("windows") or {}).get("current"))

    return data


# Robots score lost for each web search engine (Googlebot, Bingbot) shut out of the site root.
ROBOTS_BLOCKED_ENGINE_PENALTY = 50


def _robots_score(rob: dict) -> int:
    """Score robots.txt crawl hygiene: a readable file, a declared sitemap, search engines let in.

    A missing robots.txt allows every crawler (RFC 9309 sec 2.3.1.3), so it
    scores like an empty file, not a failure. Whether AI search crawlers can
    reach the site is scored separately, as ai_search_access.
    """
    if rob.get("status") not in (200, 404):
        return 0
    score = 80 + (20 if rob.get("sitemaps") else 0)
    agents = rob.get("user_agents") or {}
    blocked = sum(1 for engine in SEARCH_ENGINE_CRAWLERS if crawler_status(agents, engine) in BLOCKING_STATUSES)
    return max(0, score - blocked * ROBOTS_BLOCKED_ENGINE_PENALTY)


def _ai_search_access_score(rob: dict) -> int:
    """Share of AI search crawlers robots.txt lets fetch the site root, 0-100.

    Search crawlers build the indexes AI answers cite (OAI-SearchBot for ChatGPT
    search, Claude-SearchBot, PerplexityBot, ...), so each one blocked takes the
    site out of that engine. Training crawlers are not counted: opting out of
    model training is a licensing choice. Explicit rules earn nothing on their
    own; only access counts.
    """
    if rob.get("status") not in (200, 404):
        return 0
    statuses = rob.get("ai_crawler_status") or {}
    search = [c for c, role in AI_CRAWLER_ROLES.items() if role == "search"]
    allowed = sum(1 for c in search if statuses.get(c, "not managed") not in BLOCKING_STATUSES)
    return round(100 * allowed / len(search))


# Checks scored from another check's data: they have no section of their own.
# Internal links: points per affected page, by what the page returns. A page that
# errors costs the same whether it is a 404 or a 5xx.
INTERNAL_LINK_PAGE_PENALTY = {
    "broken_internal_pages": 15, "server_error_pages": 15, "soft_404_pages": 10, "redirected_pages": 5,
}
INTERNAL_LINK_ISSUE_PENALTY = 10


def _internal_links_score(il: dict) -> int:
    """100 less a penalty per affected page, and a flat one per other link problem.

    internal_links.py summarises each non-empty page list in exactly one issue
    ("3 internal page(s) return 404/4xx"). Those are already charged per page, so
    only the rest (anchor text, nofollow, link counts) are charged per issue, and
    info-level notes (pages that refused the crawler) are not charged at all. The
    old sum charged a broken page twice, and a 5xx page once as a single issue,
    so a server error scored better than a 404.
    """
    per_page = sum(len(il.get(key) or []) * points for key, points in INTERNAL_LINK_PAGE_PENALTY.items())
    summarised = sum(1 for key in INTERNAL_LINK_PAGE_PENALTY if il.get(key))
    # An info note or open question (refused pages) is not a link problem and costs nothing.
    charged = [i for i in il.get("issues") or []
               if not (isinstance(i, dict) and _canonical_severity(i.get("severity")) in ("info", "low"))]
    other = max(0, len(charged) - summarised)
    return max(0, 100 - per_page - other * INTERNAL_LINK_ISSUE_PENALTY)


# Redirects: scored from the chain redirect_checker.py walked, not from how many
# lines it printed. One 302 per hop used to add one issue per hop, so two 302s
# scored 25 while a redirect loop, a page that never loads, scored 75.
REDIRECT_PENALTY = {"long_chain": 40, "two_hops": 15, "temporary": 15, "downgrade": 40}


def _redirects_score(red: dict) -> int:
    """0 when the chain never reaches a page; otherwise 100 less each problem, once.

    No final URL means a loop, too many hops, a redirect with no Location, or a
    hop the fetcher refused: the audited URL does not load, for a crawler either.
    """
    if not red.get("final_url"):
        return 0
    hops = red.get("total_hops") or 0
    penalty = 0
    if hops > 2:
        penalty += REDIRECT_PENALTY["long_chain"]
    elif hops == 2:
        penalty += REDIRECT_PENALTY["two_hops"]
    if any(hop.get("status") == 302 for hop in red.get("chain") or []):
        penalty += REDIRECT_PENALTY["temporary"]
    if red.get("has_downgrade"):
        penalty += REDIRECT_PENALTY["downgrade"]
    return max(0, 100 - penalty)


SCORE_SOURCE = {"ai_search_access": "robots"}


def _source_section(sections: dict, key: str):
    return sections.get(SCORE_SOURCE.get(key, key))


# The Health Score weights. They are the single source for the category weights
# documented in references/procedures/02-full-site-audit.md and AGENTS.md;
# tests/test_health_score_contract.py fails if the docs drift from them.
# llms.txt is deliberately absent: Google Search ignores it (June 2026), so
# it is shown in the report but never weighted.
CHECK_WEIGHTS = {
    "security": 8,
    "social": 5,
    "robots": 4,
    "ai_search_access": 8,
    "broken_links": 10,
    "internal_links": 8,
    "redirects": 3,
    "pagespeed": 13,
    "onpage": 10,
    "readability": 8,
    "entity": 5,
    "link_profile": 7,
    "hreflang": 5,
    "duplicate_content": 5,
    "content_quality": 6,
    "programmatic_seo": 4,
    "schema_validation": 5,
    "image_seo": 3,
    "canonical": 7,
    "sitemap": 3,
    "local_signals": 3,
    "indexnow_probe": 2,
}


def calculate_overall_score(data: dict) -> dict:
    """Calculate overall SEO score from all analyses."""
    scores = {}
    weights = dict(CHECK_WEIGHTS)

    # Security score
    sec = data["sections"].get("security", {})
    scores["security"] = sec.get("score", 0)

    # Social meta score
    soc = data["sections"].get("social", {})
    scores["social"] = soc.get("score", 0)

    # Robots score
    scores["robots"] = _robots_score(data["sections"].get("robots", {}))
    scores["ai_search_access"] = _ai_search_access_score(data["sections"].get("robots", {}))

    # Article score (informational, not weighted heavily)
    art = data["sections"].get("article", {})
    if art and not art.get("error"):
        art_score = 50
        if art.get("target_keyword"): art_score += 25
        if art.get("lsi_keywords"): art_score += 25
        scores["article"] = min(100, art_score)
    else:
        scores["article"] = 0

    # Broken links score (includes soft 404s)
    bl = data["sections"].get("broken_links", {})
    summary = bl.get("summary", {})
    total = summary.get("total", 1) or 1
    broken = summary.get("broken", 0)
    soft_404s = summary.get("soft_404s", 0)
    scores["broken_links"] = max(0, 100 - int(((broken + soft_404s) / total) * 300))

    scores["internal_links"] = _internal_links_score(data["sections"].get("internal_links", {}))
    scores["redirects"] = _redirects_score(data["sections"].get("redirects", {}))

    # AI bot access: displayed only, not in `weights`. The test sends a crawler's
    # user agent from the audit machine, which a firewall may treat differently
    # from the real crawler, so its result is suspected, not measured.
    scores["ai_bot_access"] = data["sections"].get("ai_bot_access", {}).get("score")

    # Hidden AI instructions: displayed only, not in `weights`. A hit is already a
    # Critical finding, and phrase matching can misfire, so it does not also move the score.
    scores["hidden_instructions"] = data["sections"].get("hidden_instructions", {}).get("score")

    # Citability and structure: displayed only, not in `weights`. Its proxies (lead,
    # prose walls, paragraph length, headings) are heuristics about page shape, and
    # it is "not applicable" on homepages and hubs; it earns a weight once it has
    # run on more audits without false positives.
    scores["citability"] = data["sections"].get("citability", {}).get("score")

    # llms.txt score: displayed only, not in `weights`
    llm = data["sections"].get("llms_txt", {})
    if llm.get("exists"):
        scores["llms_txt"] = llm.get("quality", {}).get("score", 0)
    else:
        scores["llms_txt"] = 0

    # PageSpeed score
    psi = data["sections"].get("pagespeed", {})
    scores["pagespeed"] = psi.get("performance_score", 0)

    # On-page score
    op = data["sections"].get("onpage", {})
    if op and not op.get("error"):
        op_score = 50
        if op.get("title"): op_score += 15
        if op.get("meta_description"): op_score += 15
        if op.get("h1"): op_score += 10
        if op.get("canonical"): op_score += 10
        scores["onpage"] = min(100, op_score)
    else:
        scores["onpage"] = 0

    # Readability score
    rd = data["sections"].get("readability", {})
    flesch = rd.get("flesch_reading_ease", 0)
    if flesch >= 60:
        scores["readability"] = 100
    elif flesch >= 30:
        scores["readability"] = 50 + int((flesch - 30) * (50 / 30))
    else:
        scores["readability"] = max(0, int(flesch * (50 / 30)))

    # Entity SEO score
    ent = data["sections"].get("entity", {})
    if ent and not ent.get("error"):
        sameas = ent.get("sameas_analysis", {})
        found = sameas.get("total_found", 0)
        missing = sameas.get("total_missing_critical", 4)
        has_wikidata = 1 if ent.get("wikidata", {}).get("found") else 0
        has_wikipedia = 1 if ent.get("wikipedia", {}).get("found") else 0
        ent_score = min(100, found * 15 + has_wikidata * 25 + has_wikipedia * 25)
        # Only defects cost score. Info notes and data gaps ("could not verify", "no
        # Wikipedia article") do not, so the number no longer depends on how a script
        # itemises what it saw.
        issues_count = sum(1 for i in ent.get("issues", []) or []
                           if not isinstance(i, dict) or _canonical_severity(i.get("severity")) not in ("info", "low"))
        ent_score = max(0, ent_score - issues_count * 10)
        scores["entity"] = ent_score
    else:
        scores["entity"] = 0

    # Link profile score
    lp = data["sections"].get("link_profile", {})
    if lp and not lp.get("error"):
        avg_links = lp.get("avg_internal_links_per_page", 0)
        orphans = lp.get("orphan_pages", {}).get("count", 0)
        dead_ends = lp.get("dead_end_pages", {}).get("count", 0)
        lp_score = 70
        if avg_links >= 5: lp_score += 15
        elif avg_links >= 3: lp_score += 5
        else: lp_score -= 15
        lp_score -= min(30, orphans * 5)
        lp_score -= min(20, dead_ends * 3)
        scores["link_profile"] = max(0, min(100, lp_score))
    else:
        scores["link_profile"] = 0

    # Hreflang score (skip weight if not applicable)
    hf = data["sections"].get("hreflang", {})
    if hf and not hf.get("error"):
        if hf.get("hreflang_tags_found", 0) > 0:
            summary = hf.get("summary", {})
            hf_score = 100 - summary.get("critical", 0) * 30 - summary.get("high", 0) * 15 - summary.get("medium", 0) * 5
            scores["hreflang"] = max(0, min(100, hf_score))
        else:
            # No hreflang = single language site, skip from weighting
            scores["hreflang"] = None
    else:
        scores["hreflang"] = None

    # Duplicate content score
    dc = data["sections"].get("duplicate_content", {})
    if dc and not dc.get("error"):
        dupes = len(dc.get("near_duplicates", []))
        thin = len(dc.get("thin_pages", []))
        dc_score = 100 - dupes * 20 - thin * 10
        scores["duplicate_content"] = max(0, min(100, dc_score))
    else:
        scores["duplicate_content"] = 0

    cq = data["sections"].get("content_quality", {})
    if cq and not cq.get("error"):
        scores["content_quality"] = int(cq.get("score", 0))
    else:
        scores["content_quality"] = 0

    # Programmatic SEO score
    pseo = data["sections"].get("programmatic_seo", {})
    if pseo and not pseo.get("error") and pseo.get("pattern_groups_found", 0) > 0:
        pseo_crit = pseo.get("total_critical_issues", 0)
        pseo_warn = pseo.get("total_warnings", 0)
        pseo_score = 100 - pseo_crit * 25 - pseo_warn * 8
        scores["programmatic_seo"] = max(0, min(100, pseo_score))
    else:
        scores["programmatic_seo"] = None

    # JSON-LD validation (validate_schema.py --json)
    sch = data["sections"].get("schema_validation", {})
    if sch and not sch.get("error"):
        scores["schema_validation"] = int(sch.get("score", 0))
    else:
        scores["schema_validation"] = 0

    # Image alt coverage
    img = data["sections"].get("image_seo", {})
    if img and not img.get("error"):
        scores["image_seo"] = int(img.get("score", 0))
    else:
        scores["image_seo"] = 0

    # Sitemap discovery
    sm = data["sections"].get("sitemap", {})
    if sm and not sm.get("error"):
        scores["sitemap"] = int(sm.get("score", 0))
    else:
        scores["sitemap"] = 0

    # Canonical
    can = data["sections"].get("canonical", {})
    if can and not can.get("error"):
        scores["canonical"] = int(can.get("score", 0))
    else:
        scores["canonical"] = 50

    loc = data["sections"].get("local_signals", {})
    if loc and not loc.get("error"):
        if loc.get("likely_local_business"):
            scores["local_signals"] = int(loc.get("score") or 0)
        else:
            scores["local_signals"] = None
            weights["local_signals"] = 0
    else:
        scores["local_signals"] = None
        weights["local_signals"] = 0

    # IndexNow probe (no API key)
    inx = data["sections"].get("indexnow_probe", {})
    if inx and not inx.get("error"):
        scores["indexnow_probe"] = int(inx.get("score", 50))
    else:
        scores["indexnow_probe"] = 0

    # A check that never ran or errored is unmeasured, not a 0 -- and not a 100:
    # a missing broken-links run used to score as "no broken links". Unmeasured
    # checks drop out of the weighting and are listed, so a rate-limited
    # PageSpeed call cannot move the overall score or trip a CI gate.
    unmeasured = []
    for key in weights:
        section = _source_section(data["sections"], key)
        if (not isinstance(section, dict) or not section or section.get("error")
                or (key == "pagespeed" and section.get("performance_score") is None)):
            scores[key] = None
            unmeasured.append(key)

    # Weighted average (only scored categories)
    total_weight = 0
    weighted_sum = 0
    measured = 0
    for k, w in weights.items():
        val = scores.get(k)
        if val is not None and w:
            total_weight += w
            weighted_sum += val * w
            measured += 1

    overall = round(weighted_sum / total_weight) if total_weight else 0
    raw_categories = dict(scores)

    # Coerce any None scores to 0 to prevent UI crashes
    for k in list(scores.keys()):
        if scores[k] is None:
            scores[k] = 0

    return {
        "overall": overall,
        "categories": scores,
        "weights": weights,
        "measured_categories": measured,
        "unmeasured": unmeasured,
        "raw_categories": raw_categories,
    }


# ---------------------------------------------------------------------------
# CI mode: a stable JSON summary and exit-code gates.
# ---------------------------------------------------------------------------

SUMMARY_SCHEMA_VERSION = 2
# A score built from fewer weighted checks than this is no basis for failing a build.
MIN_MEASURED_FOR_GATE = 5
EXIT_GATE_FAILED = 1
EXIT_GATE_INCONCLUSIVE = 3
_GATE_SEVERITIES = {"critical": ("critical",), "warning": ("critical", "warning")}

# The one severity scale every report uses, strongest first. Scripts speak two
# dialects: critical/high/medium/low/info and the older critical/warning/info.
# "warning" is read as medium, which keeps every finding in the same level
# (critical / warning / info) it has always had in the HTML view and CI gate.
SEVERITY_SCALE = ("critical", "high", "medium", "low", "info")
_CANONICAL_SEVERITY = {
    "critical": "critical", "high": "high",
    "warning": "medium", "medium": "medium",
    "low": "low", "info": "info",
}
_SEVERITY_LEVEL = {"critical": "critical", "high": "critical", "medium": "warning", "low": "info", "info": "info"}

# The nine report categories of references/procedures/02-full-site-audit.md.
# Every check belongs to exactly one; tests pin that no check is left out.
CHECK_GROUPS = {
    "content": "Content quality / E-E-A-T",
    "technical": "Technical SEO",
    "on_page": "On-page SEO",
    "links": "Link authority",
    "schema": "Schema / structured data",
    "performance": "Core Web Vitals",
    "geo": "AI search readiness (GEO)",
    "images": "Images",
    "local": "Local SEO",
}
CHECK_GROUP = {
    "onpage": "on_page", "social": "on_page",
    "schema_validation": "schema",
    "ai_search_access": "geo",
    "canonical": "technical", "robots": "technical", "sitemap": "technical", "security": "technical",
    "redirects": "technical", "broken_links": "technical", "hreflang": "technical",
    "indexnow_probe": "technical",
    "internal_links": "links", "link_profile": "links",
    "pagespeed": "performance",
    "image_seo": "images",
    "content_quality": "content", "readability": "content", "duplicate_content": "content",
    "article": "content", "programmatic_seo": "content",
    "entity": "geo", "llms_txt": "geo", "ai_bot_access": "geo", "hidden_instructions": "geo", "citability": "geo",
    "local_signals": "local",
    "page_types": "content", "navigation": "links", "architecture": "links",
    "search_performance": "on_page",
}
# Structure checks report findings but carry no score: shown, never weighted.
DISPLAY_ONLY_CHECKS = ("page_types", "navigation", "architecture", "search_performance")
CONFIDENCE_LABELS = ("Confirmed", "Likely", "Hypothesis")

# Who acts on a finding. The vocabulary is the recommendation register's
# (references/report-template/report-template.md § 5), so the automated report
# and the client report speak one language. "Auto" means no human judgement or
# authority is needed; whether an agent can reach the code is not known here.
LANES = ("Auto", "Assisted", "Human", "Decision")
LANE_TITLES = {
    "Auto": "AI can fix now",
    "Assisted": "AI drafts, you approve",
    "Human": "Needs a human",
    "Decision": "Needs a decision",
}
LANE_REASONS = {
    "Auto": "Safe change class: markup, metadata or copy an agent can change and re-check.",
    "Assisted": "High-risk change class: an agent drafts it; a person confirms before it ships.",
    "Human": "Needs a fact, an account or off-site work an agent does not have.",
    "Decision": "A page to create: the company decides whether to build it before anyone writes it.",
}
# Each check's usual lane, from the Safe / High-Risk table of
# references/procedures/02-full-site-audit.md (Mode 3). tests pin that every
# check has one.
CHECK_LANE = {
    "onpage": "Auto", "social": "Auto", "schema_validation": "Auto", "image_seo": "Auto",
    "internal_links": "Auto", "broken_links": "Auto", "navigation": "Auto", "readability": "Auto",
    "content_quality": "Auto", "article": "Auto", "citability": "Auto", "llms_txt": "Auto",
    "sitemap": "Auto", "indexnow_probe": "Auto", "local_signals": "Auto",
    "canonical": "Assisted", "robots": "Assisted", "ai_search_access": "Assisted", "ai_bot_access": "Assisted",
    "redirects": "Assisted", "hreflang": "Assisted", "security": "Assisted", "pagespeed": "Assisted",
    "duplicate_content": "Assisted", "programmatic_seo": "Assisted", "hidden_instructions": "Assisted",
    "architecture": "Assisted",
    "entity": "Human", "link_profile": "Human",
    "page_types": "Decision",
    "search_performance": "Auto",
}
# A finding's own words outrank its check's usual lane: a robots.txt edit raised
# by any check is still high-risk, and no check can create a Wikipedia article.
_HIGH_RISK_RE = re.compile(
    r"robots\.txt|\bcanonical|\bredirect|\bnoindex\b|\bhreflang\b|\b30[1278]\b|\.htaccess|\bfirewall\b|\bWAF\b", re.I)
_HUMAN_RE = re.compile(
    r"wikipedia|wikidata|linkedin|crunchbase|knowledge panel|press coverage|notability|backlink|referring domain"
    r"|google business profile|\bGBP\b|\b(?:customer|google|more|new) reviews\b|\bmanually\b|\bsameAs\b", re.I)
# Words that mean the check could not see, not that the site is wrong.
_DATA_GAP_RE = re.compile(
    r"\bnot (?:measured|assessed|verified|checked|available|fetched)\b|\bcould not (?:be )?(?:verif|fetch|measur|determin|assess|check)"
    r"|\bunable to\b|\bno data\b|\bnot enough (?:data|pages)\b|\bcrawl (?:stopped|incomplete)\b", re.I)
# What closes an unmeasured check, when there is something more useful to say
# than "run it again".
_UNMEASURED_HINTS = {
    "pagespeed": "Set PAGESPEED_API_KEY and re-run, or run `pagespeed.py` on its own; the public quota is rate-limited.",
    "link_profile": "Re-run `link_profile.py` with a larger crawl.",
    "duplicate_content": "Re-run `duplicate_content.py`; it needs at least two fetched pages.",
}


def _scale_value(value, scale):
    """value matched to a member of scale, case-insensitively, else None."""
    text = str(value or "").strip().lower()
    return next((item for item in scale if item.lower() == text), None)


def classify_finding(issue: dict) -> dict:
    """{"kind", "lane", "lane_reason"} for one collected issue.

    kind is defect, opportunity or data_gap. A data gap is the check saying it
    could not see, so it carries no lane: it belongs in Open questions, not in
    the plan. A script may state "kind", "lane" and "lane_reason" itself and is
    believed. Wording alone only moves an info-level finding to data_gap, so a
    real defect is never hidden by a phrase.
    """
    source = issue.get("source_issue") or {}
    tags = [str(t) for t in source.get("tags")] if isinstance(source.get("tags"), list) else []
    text = " ".join(str(part or "") for part in (issue.get("finding"), issue.get("fix")))

    kind = _scale_value(source.get("kind"), ("defect", "opportunity", "data_gap"))
    if not kind:
        if "opportunity" in tags:
            kind = "opportunity"
        elif "data_gap" in tags or (issue.get("severity") == "info" and _DATA_GAP_RE.search(text)):
            kind = "data_gap"
        else:
            kind = "defect"
    if kind == "data_gap":
        return {"kind": kind, "lane": None, "lane_reason": None}

    lane = _scale_value(source.get("lane"), LANES)
    reason = _supplied(source, "lane_reason")
    if not lane:
        if kind == "opportunity":
            lane = "Decision"
        elif _HUMAN_RE.search(text):
            lane = "Human"
        elif _HIGH_RISK_RE.search(text):
            lane = "Assisted"
        else:
            lane = CHECK_LANE.get(issue.get("section"), "Assisted")
    return {"kind": kind, "lane": lane, "lane_reason": reason or LANE_REASONS[lane]}


# A finding's identity across runs. IDs are renumbered every run and wording
# carries counts ("2 broken links" becomes "1 broken link"), so neither can say
# whether a finding is the same one as last time.
_CODE_SLUG_RE = re.compile(r"^[a-z][a-z0-9_.-]{2,63}$")
_URL_RE = re.compile(r"https?://[^\s'\"<>)\]]+", re.I)
_QUOTED_RE = re.compile(r"'([^']{2,80})'|\"([^\"]{2,80})\"|`([^`]{2,80})`")


def finding_code(section: str, issue: dict, finding: str) -> tuple:
    """(code, key) for one finding: its class, and this instance of it.

    code is the script's own "code" (or slug-shaped "type") when it gives one,
    else the wording with every number, URL and quoted name taken out, so a
    count that moves does not make a new finding. key adds the subject back (the
    script's "label" or "url", else the URLs and quoted names in the wording),
    so two pages with the same defect stay two findings.
    """
    text = str(finding or "")
    supplied = next((str(issue.get(k)).strip().lower() for k in ("code", "type")
                     if isinstance(issue.get(k), str) and _CODE_SLUG_RE.match(str(issue.get(k)).strip().lower())), None)
    subjects = [str(issue.get(k)).strip() for k in ("label", "url", "page") if isinstance(issue.get(k), str) and issue.get(k).strip()]
    if not subjects:
        subjects = _URL_RE.findall(text) + [next(g for g in m if g) for m in _QUOTED_RE.findall(text)]
    if supplied:
        code = supplied if supplied.startswith(f"{section}.") else f"{section}.{supplied}"
    else:
        # Only letters are read below, so every number drops out with the punctuation.
        bare = _QUOTED_RE.sub(" ", _URL_RE.sub(" ", text))
        head = bare.split(" — ")[0].split(": ")[0]
        # A short lead-in ("[info] Block 3:") names nothing: read the whole sentence.
        words = re.findall(r"[a-z]+", head.lower())
        if len(words) < 3:
            words = re.findall(r"[a-z]+", bare.lower())
        code = f"{section}." + ("-".join(words[:8]) or "finding")
    subject = "|".join(sorted(x.lower().rstrip("/") for x in subjects))
    return code, f"{code}#{subject}" if subject else code


def check_score_gains(scores: dict) -> dict:
    """Points of the overall score each weighted check would add back at 100."""
    raw = scores.get("raw_categories") or {}
    weights = scores.get("weights") or {}
    total = sum(w for k, w in weights.items() if w and raw.get(k) is not None)
    if not total:
        return {}
    return {k: round((100 - raw[k]) * w / total, 1)
            for k, w in weights.items() if w and raw.get(k) is not None and k not in DISPLAY_ONLY_CHECKS}


def build_action_plan(issues: list, scores: dict) -> dict:
    """Findings someone can act on, by lane, in the order to do them.

    Within a lane: severity first, then Search Console clicks at stake when the
    run has them (site-wide findings first, see _traffic_rank), then the score
    its check can recover. An
    info-level note with no fix is an observation, not an action, and a data gap
    is a question; both stay out.
    """
    gains = check_score_gains(scores)
    plan = {lane: [] for lane in LANES}
    for issue in issues:
        lane = issue.get("lane")
        if lane not in plan or (issue["severity"] == "info" and not issue.get("fix")):
            continue
        plan[lane].append(issue)
    for items in plan.values():
        items.sort(key=lambda i: (SEVERITY_SCALE.index(i["canonical_severity"]), *_traffic_rank(i),
                                  -gains.get(i["section"], 0), i["id"]))
    return plan


def build_open_questions(data: dict, scores: dict, issues: list) -> list:
    """What the run could not see: unmeasured checks, then data-gap findings.

    Each says what closes it. None of them is a defect, so none is counted in
    the severity tallies or placed in the action plan.
    """
    questions = []
    weights = scores.get("weights") or {}
    for key in scores.get("unmeasured") or []:
        section = _source_section(data["sections"], key)
        error = section.get("error") if isinstance(section, dict) else None
        label = CHECK_LABELS.get(key, key)
        questions.append({
            "id": f"Q-{key}",
            "check": key,
            "question": f"{label} was not measured.",
            "why": _clip(_plain(str(error)), 240) if error else "The check returned no result.",
            "close": _UNMEASURED_HINTS.get(key, f"Re-run the report; if it fails again, run the {label} check on its own to see the error."),
            "unlocks": (f"{weights[key]} points of weight in {CHECK_GROUPS.get(CHECK_GROUP.get(key), 'the score')}"
                        if weights.get(key) else None),
        })
    for issue in issues:
        if issue.get("kind") != "data_gap":
            continue
        source = issue.get("source_issue") or {}
        questions.append({
            "id": issue["id"],
            "check": issue["section"],
            "question": issue["finding"],
            "why": _supplied(source, "evidence"),
            "close": issue.get("fix") or None,
            "unlocks": None,
        })
    return questions


def _canonical_severity(value) -> str:
    return _CANONICAL_SEVERITY.get(str(value or "info").strip().lower(), "info")


def _supplied(issue: dict, *keys):
    """The first non-empty value a script supplied for any of keys, else None.

    The HTML view fills gaps with generic guidance; the summary does not, so a
    null tells a consumer the script had nothing to say.
    """
    for key in keys:
        value = issue.get(key)
        if isinstance(value, str):
            value = value.strip()
        if value:
            return value
    return None


def _confidence(issue: dict):
    value = _supplied(issue, "confidence")
    if not isinstance(value, str):
        return None
    return next((label for label in CONFIDENCE_LABELS if label.lower() == value.lower()), None)


def build_summary(data: dict, scores: dict) -> dict:
    """The machine-readable result of one report run (schema_version 2).

    Category scores are None when a check was unmeasured or does not apply;
    the HTML view shows those as a dash, never as 0. The contract is documented
    in references/procedures/21-script-toolbox.md.
    """
    issues = _collect_issues(data)
    raw = scores.get("raw_categories") or scores.get("categories", {})
    categories = {}
    for key, value in raw.items():
        section = _source_section(data["sections"], key)
        section = section if isinstance(section, dict) else {}
        categories[key] = {
            "label": CHECK_LABELS.get(key, key),
            "group": CHECK_GROUP.get(key),
            "score": value,
            "weight": scores.get("weights", {}).get(key) or None,
            "status": _check_status(key, section, value)[1],
        }
    counts = dict.fromkeys(SEVERITY_SCALE, 0)
    for issue in issues:
        counts[issue["canonical_severity"]] += 1
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "url": data.get("url"),
        "timestamp": data.get("timestamp"),
        "overall": scores.get("overall"),
        "grade": _grade(scores.get("overall") or 0),
        "severity_scale": list(SEVERITY_SCALE),
        "groups": dict(CHECK_GROUPS),
        "group_scores": {
            group: {k: v for k, v in entry.items() if not k.startswith("_")}
            for group, entry in group_scores(scores).items()
        },
        "measured_categories": scores.get("measured_categories"),
        "unmeasured": scores.get("unmeasured", []),
        "categories": categories,
        "counts": counts,
        "findings": [_summary_finding(i) for i in issues],
        "action_plan": {
            lane: [i["id"] for i in items] for lane, items in build_action_plan(issues, scores).items()
        },
        "open_questions": build_open_questions(data, scores, issues),
        "sections_run": sorted(name for name, value in data["sections"].items()
                               if isinstance(value, dict) and value and not value.get("error")),
        "render_warning": data.get("render_warning"),
        "search_console": {**{k: v for k, v in data["gsc_traffic"].items() if k != "pages"},
                           "pages": len(data["gsc_traffic"]["pages"])} if data.get("gsc_traffic") else None,
    }


def nominal_group_weights() -> dict:
    """Each report group's share of the Health Score, in percent, before any check drops out.

    This is the category weights table the docs print.
    """
    total = sum(CHECK_WEIGHTS.values())
    exact = {group: 100 * sum(w for k, w in CHECK_WEIGHTS.items() if CHECK_GROUP[k] == group) / total
             for group in CHECK_GROUPS}
    # Largest remainder, so the printed table sums to exactly 100.
    shares = {group: int(value) for group, value in exact.items()}
    for group in sorted(exact, key=lambda g: exact[g] - shares[g], reverse=True)[:100 - sum(shares.values())]:
        shares[group] += 1
    return shares


def group_scores(scores: dict) -> dict:
    """Roll measured check scores up into the nine report groups.

    A group's score is the weighted mean of its measured checks, and its share
    is its part of the measured weight, so the overall score is the share-weighted
    mean of the group scores (exactly before rounding, to within 1 point from the
    published one-decimal shares): one number, whichever way it is read.
    """
    raw = scores.get("raw_categories") or {}
    weights = scores.get("weights") or {}
    # A weighted check with no score either failed to run (listed in "unmeasured")
    # or does not apply to this site (hreflang on a one-language site). Only the
    # first is a gap in the audit.
    failed = set(scores.get("unmeasured") or [])
    measured_total = sum(w for k, w in weights.items() if w and raw.get(k) is not None)
    result = {}
    for group, label in CHECK_GROUPS.items():
        weighted = [k for k, w in weights.items() if w and CHECK_GROUP.get(k) == group]
        measured = [k for k in weighted if raw.get(k) is not None]
        weight = sum(weights[k] for k in measured)
        if weight:
            value = sum(raw[k] * weights[k] for k in measured) / weight
            score = round(value)
            status = "Strong" if score >= 80 else "Needs work" if score >= 50 else "Gap"
        else:
            value = score = None
            status = "Not measured" if failed.intersection(weighted) else "Not applicable"
        result[group] = {
            "label": label,
            "score": score,
            "share": round(100 * weight / measured_total, 1) if measured_total else 0.0,
            "status": status,
            "checks": weighted,
            "unmeasured": [k for k in weighted if k in failed],
            "_value": value,
            "_share": 100 * weight / measured_total if measured_total else 0.0,
        }
    return result


def _summary_finding(issue: dict) -> dict:
    source = issue.get("source_issue") or {}
    tags = source.get("tags")
    return {
        "id": issue["id"],
        "severity": issue["canonical_severity"],
        "level": issue["severity"],
        "section": issue["section"],
        "group": CHECK_GROUP.get(issue["section"]),
        "finding": issue["finding"],
        "evidence": _supplied(source, "evidence"),
        "impact": _supplied(source, "impact"),
        "fix": issue.get("fix", ""),
        "confidence": _confidence(source),
        "falsifiability": _supplied(source, "falsifiability", "failure_check", "how_to_know_failed", "validation"),
        "leading_indicator": _supplied(source, "leading_indicator", "metric"),
        "dependency": _supplied(source, "dependency", "depends_on"),
        "source": f"script:{issue['section']}",
        "tags": [str(t) for t in tags] if isinstance(tags, list) else [],
        "kind": issue.get("kind"),
        "lane": issue.get("lane"),
        "lane_reason": issue.get("lane_reason"),
        "code": issue.get("code"),
        "key": issue.get("key"),
        "status": None,
        "first_seen": None,
        "traffic_at_stake": issue.get("traffic"),
    }


def _finding_level(finding: dict) -> str:
    """The critical / warning / info level gates and annotations act on.

    Read from "level" when present, else derived from "severity", so a v1-shaped
    finding is judged exactly as before.
    """
    level = finding.get("level")
    if level in ("critical", "warning", "info"):
        return level
    return _SEVERITY_LEVEL[_canonical_severity(finding.get("severity"))]


def evaluate_gate(summary: dict, fail_under=None, fail_on=None) -> dict:
    """Decide a CI gate: {"result": pass | fail | inconclusive | not set, "reasons", "exit_code"}.

    Findings at or above --fail-on fail the build whatever the coverage. A score
    threshold is only judged when at least MIN_MEASURED_FOR_GATE weighted checks
    were measured; below that the gate is inconclusive (exit 3), because a
    network failure on the audit machine is not a regression on the site.
    """
    if fail_under is None and fail_on is None:
        return {"result": "not set", "reasons": [], "exit_code": 0}
    reasons, inconclusive = [], None
    if fail_on:
        hits = [f for f in summary["findings"] if _finding_level(f) in _GATE_SEVERITIES[fail_on]]
        if hits:
            listed = ", ".join(f"{f['id']} {f['finding'][:80]}" for f in hits[:5])
            reasons.append(f"{len(hits)} finding(s) at or above {fail_on}: {listed}")
    if fail_under is not None:
        measured = summary.get("measured_categories") or 0
        if measured < MIN_MEASURED_FOR_GATE:
            inconclusive = (
                f"only {measured} weighted check(s) were measured (need {MIN_MEASURED_FOR_GATE}); "
                f"unmeasured: {', '.join(summary.get('unmeasured') or []) or 'none'}"
            )
        elif summary["overall"] < fail_under:
            reasons.append(f"overall score {summary['overall']} is below --fail-under {fail_under}")
    if reasons:
        return {"result": "fail", "reasons": reasons, "exit_code": EXIT_GATE_FAILED}
    if inconclusive:
        return {"result": "inconclusive", "reasons": [inconclusive], "exit_code": EXIT_GATE_INCONCLUSIVE}
    return {"result": "pass", "reasons": [], "exit_code": 0}


def _escape_command_data(text) -> str:
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_command_property(text) -> str:
    return _escape_command_data(text).replace(":", "%3A").replace(",", "%2C")


def github_annotations(summary: dict) -> list:
    """GitHub Actions workflow commands for critical and warning findings.

    Finding text comes from the audited site, so newlines are escaped: an
    unescaped one would let a page start its own workflow command.
    """
    lines = []
    for finding in summary["findings"]:
        level = {"critical": "error", "warning": "warning"}.get(_finding_level(finding))
        if not level:
            continue
        title = _escape_command_property(f"SEO {finding['id']} ({finding['section']})")
        message = finding["finding"] + (f" Fix: {finding['fix']}" if finding.get("fix") else "")
        lines.append(f"::{level} title={title}::{_escape_command_data(message)}")
    return lines


# ---------------------------------------------------------------------------
# HTML report view: the Tobto design system in the Ledger layout.
#
# Everything the audited site controls (titles, anchors, URLs, tag values,
# script findings) is escaped with _esc before it reaches the page. Every
# finding card and check card is present in the markup; the inline script only
# hides the unselected ones, so print and WeasyPrint PDF export show them all.
# ---------------------------------------------------------------------------

CHECK_LABELS = {
    "onpage": "On-page SEO",
    "schema_validation": "JSON-LD schema",
    "canonical": "Canonical tags",
    "robots": "Robots.txt crawl rules",
    "ai_search_access": "AI search crawler access (robots.txt)",
    "ai_bot_access": "AI crawler access (firewall)",
    "hidden_instructions": "Hidden AI instructions",
    "citability": "Citability and structure",
    "sitemap": "Sitemaps",
    "security": "Security headers",
    "redirects": "Redirects",
    "broken_links": "Broken links",
    "internal_links": "Internal links",
    "link_profile": "Link profile",
    "pagespeed": "Performance (Core Web Vitals)",
    "image_seo": "Image SEO",
    "content_quality": "Content quality",
    "readability": "Readability",
    "duplicate_content": "Content uniqueness",
    "article": "Article and keywords",
    "entity": "Entity SEO",
    "llms_txt": "llms.txt",
    "social": "Social meta",
    "hreflang": "Hreflang",
    "programmatic_seo": "Programmatic SEO",
    "local_signals": "Local signals",
    "indexnow_probe": "IndexNow",
    "page_types": "Page-type coverage",
    "navigation": "Navigation and breadcrumbs",
    "architecture": "Site architecture",
    "search_performance": "Search performance (Search Console)",
}

_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2, "pass": 3}
_SEVERITY_LABEL = {"critical": "Critical", "warning": "Warning", "info": "Info", "pass": "Pass"}
_SEVERITY_CHIP = {"critical": "c", "warning": "h", "info": "o", "pass": "g"}
_STATUS_RANK = {"gap": 0, "flag": 1, "ok": 2, "deferred": 3, "na": 4}

# Scripts prefix string issues with status emoji. Severity is read from them
# first; they are then stripped, because the design system carries state in
# chips and markers and allows no emoji on any surface.
_EMOJI_PREFIX = re.compile("^\\s*(?:[\U0001F300-\U0001FAFF☀-➿ℹ⭐]️?\\s*)+")

_FONTS_URL = (
    "https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400..700;1,400..700"
    "&family=JetBrains+Mono:wght@400;500;700"
    "&display=swap"
)


def _esc(value) -> str:
    return html_lib.escape("" if value is None else str(value), quote=True)


def _plain(text) -> str:
    return _EMOJI_PREFIX.sub("", "" if text is None else str(text)).strip()


def _clip(value, limit: int) -> str:
    text = "" if value is None else str(value)
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return _esc(text)


def _headline(text: str, limit: int = 110) -> str:
    first = re.split(r"(?<=[.!?])\s+", text or "", maxsplit=1)[0]
    return first if len(first) <= limit else first[: limit - 1].rstrip() + "…"


def _join_labels(labels: list) -> str:
    if len(labels) <= 1:
        return "".join(labels)
    return ", ".join(labels[:-1]) + " and " + labels[-1]


def _stringify(item) -> str:
    if isinstance(item, dict):
        for key in ("title", "finding", "description", "message"):
            if item.get(key):
                extra = item.get("displayValue") or item.get("savings") or ""
                return f"{item[key]} ({extra})" if extra else str(item[key])
        return ", ".join(f"{k}: {v}" for k, v in item.items())
    return str(item)


def _grade(overall: int) -> str:
    for floor, letter in ((90, "A+"), (80, "A"), (70, "B"), (60, "C"), (50, "D")):
        if overall >= floor:
            return letter
    return "F"


def _chip(kind: str, label: str) -> str:
    return f'<span class="chip {kind}">{_esc(label)}</span>'


def _severity_chip(severity: str) -> str:
    return _chip(_SEVERITY_CHIP.get(severity, "sev-info"), _SEVERITY_LABEL.get(severity, severity.title()))


def _status_chip(status: str, label: str) -> str:
    kind = {"ok": "g", "flag": "h", "gap": "c"}.get(status, "o")
    return _chip(kind, label)


def _yes_no(flag, missing_is_bad: bool = True) -> str:
    if flag:
        return '<span class="yes">Yes</span>'
    return '<span class="no">No</span>' if missing_is_bad else '<span class="muted">No</span>'


def _kv(pairs: list) -> str:
    cells = "".join(f"<div><dt>{_esc(label)}</dt><dd>{value}</dd></div>" for label, value in pairs)
    return f'<dl class="kv">{cells}</dl>'


def _table(headers: list, rows: list) -> str:
    head = "".join(f'<th scope="col">{_esc(h)}</th>' for h in headers)
    return (
        f'<div class="tw"><table><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def _notice(body_html: str, tone: str = "empty", lead: str = "") -> str:
    """A callout in the report-set vocabulary: flag (default), info, good, or a plain note."""
    lead_html = f"<b>{_esc(lead)}</b> " if lead else ""
    css = {"flag": "callout", "info": "callout k", "good": "callout g"}.get(tone, "callout k")
    return f'<div class="{css}"><p>{lead_html}{body_html}</p></div>'


def _subhead(text: str) -> str:
    return f'<h4 class="subhead">{_esc(text)}</h4>'


def _check_status(key: str, section: dict, score) -> tuple:
    """Return (status, label) for one check.

    A check that errored or never ran is not a 0: it is unmeasured, and a check
    that does not apply to this site is not a gap.
    """
    if not section:
        return ("na", "Not run")
    if section.get("error"):
        return ("deferred", "Not measured")
    if key == "hreflang" and not section.get("hreflang_tags_found"):
        return ("na", "Not applicable")
    if key == "local_signals" and not section.get("likely_local_business"):
        return ("na", "Not applicable")
    if key == "programmatic_seo" and not section.get("pattern_groups_found"):
        return ("na", "Not applicable")
    if key == "pagespeed" and not section.get("performance_score"):
        return ("deferred", "Not measured")
    if key == "citability" and section.get("applicable") is False:
        return ("na", "Not applicable")
    if key == "ai_bot_access":
        if section.get("status") == "inconclusive" or section.get("score") is None:
            return ("deferred", "Not measured")
        if section.get("refused_search"):
            return ("flag", "Suspected block")
    if key in DISPLAY_ONLY_CHECKS:
        if key == "navigation" and section.get("status") == "not_measured":
            return ("deferred", "Not measured")
        levels = {_canonical_severity(i.get("severity")) for i in section.get("issues") or [] if isinstance(i, dict)}
        if levels & {"critical", "high"}:
            return ("gap", "Gap")
        if "medium" in levels:
            return ("flag", "Needs work")
        return ("ok", "Reviewed")
    value = score or 0
    if value >= 80:
        return ("ok", "Strong")
    if value >= 50:
        return ("flag", "Needs work")
    return ("gap", "Gap")


def _render_issue_metadata(issue: dict) -> str:
    parts = []
    for label, key in (
        ("Dependency:", "dependency"),
        ("Failure check:", "failure_check"),
        ("Leading indicator:", "leading_indicator"),
    ):
        value = issue.get(key, "")
        if value:
            parts.append(f"<div><dt>{label}</dt><dd>{_esc(value)}</dd></div>")
    if not parts:
        return ""
    return '<dl class="fmeta">' + "".join(parts) + "</dl>"


def render_environment_fixes(fixes: list) -> str:
    """Render environment-specific fixes for HTML output."""
    if not fixes:
        return _notice("No environment-specific fixes needed.")
    items = []
    for item in sorted(fixes, key=lambda x: _SEVERITY_ORDER.get(x.get("severity", "info"), 9)):
        severity = item.get("severity", "info")
        reason = item.get("reason", "")
        fix = item.get("fix", "")
        reason_html = f'<p class="issue-reason">{_esc(reason)}</p>' if reason else ""
        fix_html = f'<p class="issue-fix"><span class="lbl">Fix</span> {_esc(fix)}</p>' if fix else ""
        items.append(
            '<li class="issue">'
            f'<div class="issue-head">{_severity_chip(severity)}<strong>{_esc(_plain(item.get("title", "")))}</strong></div>'
            f"{reason_html}{fix_html}{_render_issue_metadata(item)}</li>"
        )
    return '<ul class="issues">' + "".join(items) + "</ul>"


def _section_recommendations(section_data: dict) -> list:
    recs = section_data.get("recommendations", section_data.get("suggestions", []))
    if isinstance(recs, dict):
        items = [f"{k}: {v}" for k, v in recs.items()]
    elif isinstance(recs, list):
        items = list(recs)
    else:
        items = []
    opps = section_data.get("opportunities", [])
    if isinstance(opps, list):
        items.extend(opps)
    return items


def render_recommendations(section_data: dict) -> str:
    """Render one check's structured issues and recommendations."""
    items = _section_recommendations(section_data)
    issue_rows = []
    issues = section_data.get("issues", [])
    if isinstance(issues, list):
        for issue in issues[:15]:
            if isinstance(issue, dict):
                severity = _SEVERITY_LEVEL[_canonical_severity(issue.get("severity"))]
                fix = issue.get("fix", "")
                fix_html = f'<p class="issue-fix"><span class="lbl">Fix</span> {_esc(fix)}</p>' if fix else ""
                # Only what the script said, like the finding cards: the stock wording here
                # read "Rerun the section check" under every issue of every check.
                meta = _render_issue_metadata({
                    "dependency": _supplied(issue, "dependency", "depends_on"),
                    "failure_check": _supplied(issue, "falsifiability", "failure_check", "how_to_know_failed", "validation"),
                    "leading_indicator": _supplied(issue, "leading_indicator", "metric"),
                })
                issue_rows.append(
                    '<li class="issue">'
                    f'<div class="issue-head">{_severity_chip(severity)}'
                    f'<strong>{_esc(_plain(issue.get("finding", "")))}</strong></div>'
                    f"{fix_html}{meta}</li>"
                )
            elif isinstance(issue, str):
                items.append(issue)

    html = ""
    if issue_rows:
        html += _subhead("Issues found") + '<ul class="issues">' + "".join(issue_rows) + "</ul>"
    if items:
        lis = "".join(f"<li>{_esc(_plain(_stringify(item)))}</li>" for item in items[:15])
        html += _subhead("Recommendations") + f'<ul class="recs">{lis}</ul>'
    return html


def render_readability_rewrites(readability_data: dict) -> str:
    """Render concrete sentence replacements for readability fixes."""
    rewrites = readability_data.get("sentence_rewrites", [])
    if not rewrites:
        return ""
    rows = []
    for item in rewrites[:5]:
        wc_raw = item.get("current_word_count", "")
        length = f"{wc_raw} words" if isinstance(wc_raw, (int, float)) else str(wc_raw)
        rows.append(
            f"<tr><td>{_esc(item.get('current', ''))}</td>"
            f"<td>{_esc(item.get('suggested', ''))}</td>"
            f'<td class="num">{_esc(length)}</td></tr>'
        )
    return _subhead("What to replace") + _table(["Current sentence", "Replace with", "Length"], rows)


def render_all_recommendations(data: dict) -> str:
    """Render every recommendation the checks returned, grouped by check."""
    groups = []
    env_items = [
        f"{_plain(item.get('title', ''))}: {item.get('fix', '')}"
        for item in data.get("environment_fixes", [])[:8]
        if item.get("severity") != "pass"
    ]
    if env_items:
        groups.append(("Platform fixes", env_items))
    for key, label in CHECK_LABELS.items():
        section = data["sections"].get(key, {})
        if not isinstance(section, dict):
            continue
        items = _section_recommendations(section)
        if key == "readability":
            for rewrite in section.get("sentence_rewrites", [])[:3]:
                current = str(rewrite.get("current", ""))[:180]
                suggested = str(rewrite.get("suggested", ""))[:180]
                items.append(f"Rewrite: {current} → {suggested}")
        if items:
            groups.append((label, items[:10]))
    if not groups:
        return _notice("No recommendations. Every check came back clean.")
    html = ""
    for label, items in groups:
        lis = "".join(f"<li>{_esc(_plain(_stringify(item)))}</li>" for item in items)
        html += f'<section class="rec-group">{_subhead(label)}<ul class="recs">{lis}</ul></section>'
    return html


def _collect_issues(data: dict) -> list:
    issues = []
    for section_name, section_data in data["sections"].items():
        if not isinstance(section_data, dict):
            continue
        for issue in section_data.get("issues", []) or []:
            if isinstance(issue, dict):
                canonical = _canonical_severity(issue.get("severity"))
                finding = _plain(issue.get("finding", "")) or _plain(str(issue))
                fix = str(issue.get("fix", "") or "")
                issues.append({
                    "text": f"{finding} — Fix: {fix}" if fix else finding,
                    "finding": finding,
                    "fix": fix,
                    "severity": _SEVERITY_LEVEL[canonical],
                    "canonical_severity": canonical,
                    "section": section_name,
                    "source_issue": issue,
                    **_recommendation_metadata(issue, section_name),
                })
            elif isinstance(issue, str):
                canonical = "critical" if "🔴" in issue else "medium" if "⚠" in issue else "info"
                text = _plain(issue)
                issues.append({"text": text, "finding": text, "fix": "", "severity": _SEVERITY_LEVEL[canonical],
                               "canonical_severity": canonical, "section": section_name})
    issues.sort(key=lambda x: SEVERITY_SCALE.index(x["canonical_severity"]))
    for number, issue in enumerate(issues, 1):
        issue["id"] = f"F{number:02d}"
        issue.update(classify_finding(issue))
        issue["code"], issue["key"] = finding_code(issue["section"], issue.get("source_issue") or {}, issue["finding"])
        # A data gap is a question, not work: it has nothing to put a cost on.
        issue["traffic"] = attach_traffic(issue, data) if issue["kind"] != "data_gap" else None
    return issues


def _anchor_audit_panel(audit) -> str:
    """The in-content anchor audit internal_links.py runs on the shared site graph."""
    if not isinstance(audit, dict) or not audit:
        return ""
    if audit.get("status") != "measured":
        return _subhead("Anchor audit") + _notice(_esc(audit.get("reason") or "Not measured."))
    excluded = audit.get("excluded") or {}
    vague_rows = [f'<tr><td>{_esc(v.get("anchor"))}</td><td class="url">{_clip(v.get("source", ""), 60)}</td>'
                  f'<td class="url">{_clip(v.get("target", ""), 60)}</td></tr>' for v in (audit.get("vague_links") or [])[:10]]
    return (
        _subhead("Anchor audit (in-content links)")
        + _kv([("Pages sampled", _esc(audit.get("pages_sampled"))),
               ("In-content links", _esc(audit.get("content_links"))),
               ("Chrome / repeating links left out", _esc(f'{excluded.get("chrome", 0)} / {excluded.get("boilerplate", 0)}')),
               ("Vague anchors", _esc(audit.get("vague_links_count")))])
        + (_table(["Anchor", "On page", "Links to"], vague_rows) if vague_rows else "")
    )


def _check_panels(data: dict) -> dict:
    """Build the detail body for every check, keyed like CHECK_LABELS."""
    sections = data["sections"]
    env = data.get("environment", {}) or {}

    def get(key: str) -> dict:
        value = sections.get(key)
        return value if isinstance(value, dict) else {}

    panels = {}

    op = get("onpage")
    title = op.get("title") or ""
    meta = op.get("meta_description") or ""
    h1_value = op.get("h1")
    if isinstance(h1_value, list):
        h1 = str(h1_value[0]) if h1_value else ""
    else:
        h1 = str(h1_value or "")
    canonical = op.get("canonical") or ""
    disclaimer = ""
    if _needs_raw_html_disclaimer(env):
        disclaimer = _notice(
            "Title, meta description, canonical and H1 are read from the initial response. On "
            f"{_esc(env.get('primary') or 'this stack')} and other JavaScript-heavy sites, tags may be "
            "injected client-side; confirm in DevTools or the Rich Results Test if this disagrees "
            "with the browser.",
            "info",
            "Raw HTML snapshot.",
        )
    meta_note = ' <span class="muted">(og:description fallback)</span>' if op.get("meta_description_source") == "og_fallback" else ""
    canonical_note = ' <span class="muted">(from canonical audit)</span>' if op.get("canonical_from_audit") else ""
    onpage_rows = [
        f'<tr><td>Title</td><td>{_clip(title, 90) or "—"}</td><td class="num">{len(title)}</td></tr>',
        f'<tr><td>Meta description</td><td>{_clip(meta, 170) or "—"}</td><td class="num">{len(meta)}{meta_note}</td></tr>',
        f'<tr><td>H1</td><td>{_clip(h1, 90) or "—"}</td><td class="num">{len(h1) if h1 else "—"}</td></tr>',
        f'<tr><td>Canonical</td><td class="url">{_clip(canonical, 110) or "—"}{canonical_note}</td><td class="num">—</td></tr>',
    ]
    panels["onpage"] = (
        disclaimer
        + _kv([("Title", _yes_no(title)), ("Meta description", _yes_no(meta)),
               ("H1", _yes_no(h1)), ("Canonical", _yes_no(canonical))])
        + _table(["Element", "Value", "Length"], onpage_rows)
        + render_recommendations(op)
    )

    sch = get("schema_validation")
    panels["schema_validation"] = (
        _kv([("JSON-LD blocks", _esc(sch.get("jsonld_blocks", 0))),
             ("Issues", _esc(sch.get("error_count", 0))),
             ("Critical", _esc(sch.get("critical_count", 0)))])
        + render_recommendations(sch)
    )

    can = get("canonical")
    self_ref = can.get("is_self_referencing")
    panels["canonical"] = (
        _kv([("Canonical", _yes_no(can.get("canonical"))),
             ("Self-referencing", "—" if self_ref is None else _yes_no(self_ref)),
             ("Target HTTP", _esc(can.get("canonical_status", "—"))),
             ("Score", _esc(can.get("score", "—")))])
        + render_recommendations(can)
    )

    rob = get("robots")
    crawler_rows = []
    for crawler, status in (rob.get("ai_crawler_status") or {}).items():
        status_text = str(status)
        role = AI_CRAWLER_ROLES.get(crawler, "")
        if "not managed" in status_text:
            chip = _chip("chip-na", "Unmanaged")
        elif "partially" in status_text:
            chip = _chip("chip-info", "Partial")
        elif "blocked" in status_text:
            # Blocking a training crawler is a licensing choice; blocking a
            # search or user crawler takes the site out of AI answers.
            chip = _chip("chip-info" if role == "training" else "chip-flag", "Blocked")
        else:
            chip = _chip("chip-ok", "Allowed")
        crawler_rows.append(
            f"<tr><td>{_esc(crawler)}</td><td>{_esc(role or '—')}</td>"
            f"<td>{chip}</td><td>{_esc(status_text)}</td></tr>"
        )
    engine_rows = [
        f"<tr><td>{_esc(engine)}</td><td>{_esc(state)}</td></tr>"
        for engine, state in (
            (e, crawler_status(rob.get("user_agents") or {}, e)) for e in SEARCH_ENGINE_CRAWLERS)
    ] if rob else []
    panels["robots"] = (
        _kv([("robots.txt", _esc(rob.get("status", "—"))),
             ("Sitemaps", _esc(len(rob.get("sitemaps") or []))),
             ("User-agents", _esc(len(rob.get("user_agents") or {})))])
        + (_subhead("Search engines") + _table(["Crawler", "Status"], engine_rows) if engine_rows else "")
    )
    panels["ai_search_access"] = (
        _notice("Scored from robots.txt: the share of AI search crawlers that can fetch the site root. "
                "Training crawlers are listed but not scored.")
        + (_subhead("AI crawler access") + _table(["Crawler", "Role", "Status", "Detail"], crawler_rows)
           if crawler_rows else "")
    )

    aba = get("ai_bot_access")
    access_rows = []
    for crawler, bot in (aba.get("bots") or {}).items():
        verdict = bot.get("verdict") or ""
        if verdict == "allowed":
            chip = _chip("chip-ok", "Served")
        elif verdict in ("blocked", "challenged"):
            label = "Challenged" if verdict == "challenged" else "Refused"
            chip = _chip("chip-flag" if bot.get("role") == "search" else "chip-info", label)
        else:
            chip = _chip("chip-na", verdict.title() or "—")
        detail = f"{bot['challenge_vendor']} challenge" if bot.get("challenge_vendor") else (bot.get("error") or "")
        access_rows.append(
            f"<tr><td>{_esc(crawler)}</td><td>{_esc(bot.get('role') or '—')}</td>"
            f'<td class="num">{_esc(bot.get("status") or "—")}</td><td>{chip}</td><td>{_esc(detail)}</td></tr>'
        )
    baseline = aba.get("baseline") or {}
    panels["ai_bot_access"] = (
        _kv([("Browser baseline", _esc(baseline.get("status") or "—")),
             ("Server", _esc(baseline.get("server") or "—")),
             ("Crawlers tested", _esc(len(aba.get("bots") or {})))])
        + (_notice(_esc(" ".join(aba["limits"])), "info", "Suspected, not proven.") if aba.get("limits") else "")
        + (_table(["Crawler", "Role", "HTTP", "Result", "Detail"], access_rows) if access_rows else "")
    )

    # Snippets are text the audited page hides from visitors; escape every one.
    hid = get("hidden_instructions")
    hidden_rows = [
        f"<tr><td>{_esc(item.get('context'))}</td><td>{_esc(item.get('where'))}</td>"
        f"<td>{_esc(item.get('snippet'))}</td></tr>"
        for item in (hid.get("hidden_instructions") or [])
    ] + [
        f"<tr><td>invisible Unicode</td><td>{_esc(item.get('kind'))}</td>"
        f"<td>{_esc(item.get('decoded') or str(item.get('length')) + ' characters')}</td></tr>"
        for item in (hid.get("invisible_unicode") or [])
    ]
    panels["hidden_instructions"] = (
        _kv([("Hidden instruction-like text", _esc(len(hid.get("hidden_instructions") or []))),
             ("Invisible Unicode runs", _esc(len(hid.get("invisible_unicode") or [])))])
        + (_notice(_esc(" ".join(hid["limits"])), "info", "Pattern-based.") if hid.get("limits") else "")
        + (_table(["Where", "Element", "Text"], hidden_rows) if hidden_rows else "")
    )

    cit = get("citability")
    if cit.get("applicable") is False:
        cit_body = _notice(_esc(cit.get("reason", "")), "info", "Not an article-style page.")
    else:
        comp = cit.get("components") or {}
        rows = [f"<tr><td>{_esc(name.replace('_', ' '))}</td><td class=\"num\">{_esc(c.get('score', '—'))}</td></tr>"
                for name, c in comp.items()]
        openings = cit.get("long_openings") or {}
        cit_body = (
            _kv([("Words", _esc(cit.get("words", "—"))), ("Sections", _esc(cit.get("sections", "—"))),
                 ("Question headings", _esc((cit.get("question_headings") or {}).get("count", "—"))),
                 ("Long section openings (not scored)", _esc(openings.get("count", "—")))])
            + (_table(["Component", "Score"], rows) if rows else "")
        )
    panels["citability"] = (
        _notice("Structural proxies for passages AI answers can quote: a lead paragraph, no prose walls, "
                "short paragraphs, a clean heading outline, specific figures. Shown, not weighted.", "info")
        + cit_body + render_recommendations(cit)
    ) if cit else ""

    sm = get("sitemap")
    health = sm.get("url_health") or {}
    health_html = ""
    if health.get("checked"):
        health_html = _subhead("URL health") + _kv([
            ("Checked", _esc(health.get("checked", 0))),
            ("Healthy", _esc(health.get("healthy", 0))),
            ("404", _esc(len(health.get("not_found_404") or []))),
            ("Soft 404", _esc(len(health.get("soft_404s") or []))),
            ("5xx", _esc(len(health.get("server_errors_5xx") or []))),
        ])
    panels["sitemap"] = (
        _kv([("Sitemaps listed", _esc(len(sm.get("sitemap_urls") or []))),
             ("Primary HTTP", _esc(sm.get("primary_status", "—"))),
             ("URLs in first sitemap", _esc(sm.get("url_count_estimate", "—")))])
        + health_html
        + render_recommendations(sm)
    )

    sec = get("security")
    present = sec.get("headers_present") or {}
    missing = sec.get("headers_missing") or {}
    header_rows = [
        f'<tr><td>{_esc(h)}</td><td>{_chip("chip-ok", "Present")}</td><td class="url">{_clip(v, 90)}</td></tr>'
        for h, v in present.items()
    ] + [
        f'<tr><td>{_esc(h)}</td><td>{_chip("chip-gap", "Missing")}</td><td>{_esc(d)}</td></tr>'
        for h, d in missing.items()
    ]
    panels["security"] = (
        _kv([("HTTPS", _yes_no(sec.get("https"))), ("Present", _esc(len(present))), ("Missing", _esc(len(missing)))])
        + (_table(["Header", "Status", "Value or description"], header_rows) if header_rows else "")
    )

    red = get("redirects")
    hop_rows = []
    for hop in red.get("chain") or []:
        status = hop.get("status", "?")
        if hop.get("final"):
            ok = isinstance(status, int) and 200 <= status < 300
            chip = _chip("chip-ok" if ok else "chip-gap", str(status))
            kind = "Final"
        else:
            chip = _chip("chip-flag", str(status))
            kind = hop.get("redirect_type", "")
        hop_rows.append(
            f'<tr><td class="num">{_esc(hop.get("step", ""))}</td><td>{chip}</td>'
            f'<td class="url">{_clip(hop.get("url", ""), 110)}</td>'
            f'<td class="num">{_esc(hop.get("time_ms", 0))} ms</td><td>{_esc(kind)}</td></tr>'
        )
    panels["redirects"] = (
        _kv([("Hops", _esc(red.get("total_hops", 0)))])
        + (_table(["Step", "Status", "URL", "Time", "Type"], hop_rows) if hop_rows
           else _notice("No redirect chain. The URL answers directly."))
    )

    bl = get("broken_links")
    bl_summary = bl.get("summary") or {}
    link_rows = []
    for link in (bl.get("broken") or [])[:20]:
        internal = link.get("is_internal")
        kind = _chip("chip-gap", "Internal") if internal else _chip("chip-flag", "External")
        link_rows.append(
            f'<tr><td>{kind}</td><td class="num">{_esc(link.get("status") or link.get("error", "?"))}</td>'
            f'<td class="url">{_clip(link.get("url", ""), 110)}</td><td>{_clip(link.get("anchor_text", ""), 60)}</td></tr>'
        )
    panels["broken_links"] = (
        _kv([("Links checked", _esc(bl_summary.get("total", 0))),
             ("Healthy", _esc(bl_summary.get("healthy", 0))),
             ("Broken", _esc(bl_summary.get("broken", 0))),
             ("Soft 404s", _esc(bl_summary.get("soft_404s", 0))),
             ("Redirected", _esc(bl_summary.get("redirected", 0))),
             ("Timeouts", _esc(bl_summary.get("timeout", 0)))])
        + (_table(["Type", "Status", "URL", "Anchor"], link_rows) if link_rows
           else _notice("No broken links found."))
    )

    il = get("internal_links")
    distribution = il.get("link_distribution") or {}
    anchors = list((il.get("anchor_texts") or {}).items())[:10]
    anchor_rows = []
    if anchors:
        top = max((count for _, count in anchors if isinstance(count, (int, float))), default=1) or 1
        for text, count in anchors:
            pct = round((count if isinstance(count, (int, float)) else 0) / top * 100)
            anchor_rows.append(
                f'<tr><td>{_clip(text, 50)}</td><td class="num">{_esc(count)}</td>'
                f'<td><span class="meter wide"><span style="width:{pct}%"></span></span></td></tr>'
            )
    panels["internal_links"] = (
        _kv([("Pages crawled", _esc(il.get("pages_crawled", 0))),
             ("Internal links", _esc(il.get("total_internal_links", 0))),
             ("Avg links per page", _esc(distribution.get("avg", 0))),
             ("Pages found", _esc(il.get("unique_pages_found", 0)))])
        + (_subhead("Top anchor texts") + _table(["Anchor text", "Links", "Share of top anchor"], anchor_rows) if anchor_rows else "")
        + _anchor_audit_panel(il.get("anchor_audit"))
    )

    lp = get("link_profile")
    orphans = lp.get("orphan_pages") or {}
    # A partial crawl cannot count orphans; "0" would read as a clean result.
    orphan_value = "—" if orphans.get("status") == "inconclusive" else _esc(orphans.get("count", 0))
    panels["link_profile"] = (
        _kv([("Pages crawled", _esc(lp.get("pages_crawled", "—"))),
             ("Avg links per page", _esc(lp.get("avg_internal_links_per_page", "—"))),
             ("Orphan pages", orphan_value),
             ("Dead ends", _esc((lp.get("dead_end_pages") or {}).get("count", 0)))])
        + render_recommendations(lp)
    )

    psi = get("pagespeed")
    metrics = psi.get("field_data") or psi.get("lab_data") or {}
    psi_note = ""
    if psi.get("error") or not psi.get("performance_score"):
        detail = f" ({_esc(psi.get('error'))})" if psi.get("error") else ""
        psi_note = _notice(
            f"Rerun <code>pagespeed.py --api-key YOUR_KEY</code> or check pagespeed.web.dev{detail}. "
            "Without that data this report states no LCP, INP or CLS figures.",
            "flag",
            "PageSpeed data unavailable.",
        )
    panels["pagespeed"] = (
        psi_note
        + _kv([("Performance", _esc(psi.get("performance_score") or "—")),
               ("LCP", _esc(metrics.get("LCP", "—"))),
               ("INP or TBT", _esc(metrics.get("INP", metrics.get("TBT", "—")))),
               ("CLS", _esc(metrics.get("CLS", "—")))])
        + render_recommendations(psi)
    )

    img = get("image_seo")
    missing_pct = img.get("missing_alt_pct")
    panels["image_seo"] = (
        _kv([("Images", _esc(img.get("total_images", "—"))),
             ("Missing alt", _esc(img.get("missing_alt", "—"))),
             ("Missing alt share", f"{_esc(missing_pct)}%" if missing_pct is not None else "—")])
        + render_recommendations(img)
    )

    cq = get("content_quality")
    panels["content_quality"] = (
        _kv([("Words", _esc(cq.get("word_count", "—"))),
             ("Filler phrases", _esc(len(cq.get("filler_phrases") or []))),
             ("Citation gap", _esc(cq.get("citation_gap", 0)))])
        + render_recommendations(cq)
    )

    rd = get("readability")
    panels["readability"] = (
        _kv([("Flesch reading ease", _esc(rd.get("flesch_reading_ease", "—"))),
             ("Grade level", _esc(rd.get("flesch_kincaid_grade", "—"))),
             ("Words", _esc(rd.get("word_count", "—"))),
             ("Reading time", f'{_esc(rd.get("estimated_reading_time_min", "—"))} min')])
        + render_recommendations(rd)
        + render_readability_rewrites(rd)
    )

    dc = get("duplicate_content")
    panels["duplicate_content"] = (
        _kv([("Pages analyzed", _esc(dc.get("pages_analyzed", "—"))),
             ("Near duplicates", _esc(len(dc.get("near_duplicates") or []))),
             ("Thin pages", _esc(len(dc.get("thin_pages") or [])))])
        + render_recommendations(dc)
    )

    art = get("article")
    headings = art.get("headings") if isinstance(art.get("headings"), dict) else {}
    related = art.get("lsi_keywords") or []
    keyword_row = (
        f'<tr><td>{_esc(art.get("target_keyword") or "—")}</td>'
        f'<td>{_esc(", ".join(str(k) for k in related) if related else "—")}</td></tr>'
    )
    panels["article"] = (
        _kv([("Words", _esc(art.get("word_count", "—"))),
             ("H2 headings", _esc(len(headings.get("h2") or []))),
             ("Images", _esc(len(art.get("images") or [])))])
        + _table(["Target keyword", "Related keywords"], [keyword_row])
        + render_recommendations(art)
    )

    ent = get("entity")
    panels["entity"] = (
        _kv([("Wikidata", _yes_no((ent.get("wikidata") or {}).get("found"))),
             ("Wikipedia", _yes_no((ent.get("wikipedia") or {}).get("found"))),
             ("sameAs links", _esc((ent.get("sameas_analysis") or {}).get("total_found", 0))),
             ("Issues", _esc(len(ent.get("issues") or [])))])
        + render_recommendations(ent)
    )

    llm = get("llms_txt")
    quality = llm.get("quality") or {}
    tips = "".join(f"<li>{_esc(_plain(tip))}</li>" for tip in quality.get("suggestions") or [])
    panels["llms_txt"] = (
        _notice("Google Search ignores llms.txt; its absence costs nothing there.", "empty")
        + _kv([("llms.txt", _yes_no(llm.get("exists"), False)),
               ("llms-full.txt", _yes_no(llm.get("full_exists"), False)),
               ("Quality score", _esc(quality.get("score", 0)))])
        + (_subhead("Suggestions") + f'<ul class="recs">{tips}</ul>' if tips else "")
    )

    soc = get("social")
    og = soc.get("og_tags") or {}
    tw = soc.get("twitter_tags") or {}
    social_rows = []
    for tag in ("og:title", "og:description", "og:image", "og:url", "og:type", "og:site_name"):
        value = og.get(tag, "")
        status = _chip("chip-ok", "Present") if value else _chip("chip-gap", "Missing")
        social_rows.append(f'<tr><td class="mono">{tag}</td><td>{status}</td><td class="url">{_clip(value, 90) or "—"}</td></tr>')
    for tag in ("twitter:card", "twitter:title", "twitter:description", "twitter:image", "twitter:site"):
        value = tw.get(tag, "")
        status = _chip("chip-ok", "Present") if value else _chip("chip-flag", "Missing")
        social_rows.append(f'<tr><td class="mono">{tag}</td><td>{status}</td><td class="url">{_clip(value, 90) or "—"}</td></tr>')
    panels["social"] = _table(["Tag", "Status", "Value"], social_rows)

    hf = get("hreflang")
    tags_found = hf.get("hreflang_tags_found", 0)
    panels["hreflang"] = (
        _kv([("Method", _esc(hf.get("implementation_method", "none"))), ("Tags found", _esc(tags_found))])
        + (render_recommendations(hf) if tags_found
           else _notice("No hreflang tags. That is expected for a single-language site."))
    )

    ps = get("programmatic_seo")
    panels["programmatic_seo"] = (
        _kv([("Pattern groups", _esc(ps.get("pattern_groups_found", 0))),
             ("Critical issues", _esc(ps.get("total_critical_issues", 0))),
             ("Warnings", _esc(ps.get("total_warnings", 0)))])
        + render_recommendations(ps)
    )

    loc = get("local_signals")
    panels["local_signals"] = (
        _kv([("LocalBusiness schema", _yes_no(loc.get("localbusiness_jsonld"), False)),
             ("tel: links", _esc(loc.get("tel_links", "—"))),
             ("Address markup", _yes_no(loc.get("structured_address_signals"), False))])
        + render_recommendations(loc)
    )

    inx = get("indexnow_probe")
    panels["indexnow_probe"] = (
        _kv([("Meta tag", _yes_no(inx.get("meta_indexnow_present"), False)),
             ("robots.txt hint", _yes_no(inx.get("robots_mentions_indexnow"), False)),
             ("Sitemap in robots.txt", _yes_no(inx.get("robots_has_sitemap")))])
        + render_recommendations(inx)
    )

    for key in CHECK_LABELS:
        section = _source_section(sections, key)
        if key == "search_performance" and not section:
            prefix = _notice("Runs only when the report is given a Search Console property "
                             "(<code>--gsc-property sc-domain:example.com</code>, Tier 1 credentials). "
                             "<code>--gsc-pages</code> with a Pages export adds traffic at stake to the findings without it.")
        elif not isinstance(section, dict) or not section:
            prefix = _notice("This check did not run, usually because the page could not be fetched.")
        elif section.get("error") and key != "pagespeed":
            prefix = _notice(_esc(section.get("error")), "flag", "Check did not complete.")
        else:
            prefix = ""
        panels[key] = prefix + panels.get(key, "")
    pt = get("page_types")
    if pt:
        matrix = pt.get("matrix") or {}
        rows = [
            f"<tr><td>{_esc(label.replace('_', ' '))}</td><td class=\"num\">{_esc(m.get('count', 0))}</td>"
            f"<td class=\"num\">{_esc(round(100 * (m.get('share') or 0)))}%</td><td>{_esc(m.get('intent', ''))}</td>"
            f"<td class=\"url\">{_clip(', '.join('/' + (f or '') for f in (m.get('families') or [])[:3]), 80)}</td></tr>"
            for label, m in matrix.items() if m.get("count")
        ]
        src = pt.get("source") or {}
        expected = pt.get("expected") or []
        missing = [l for l in expected if not (matrix.get(l) or {}).get("count")]
        panels["page_types"] = (
            _notice("Every sitemap and crawled URL labelled by content type; expected types come from the industry template. "
                    "Shown, not weighted; absence findings are only made from a complete sitemap or crawl.", "info")
            + _kv([("Site type", _esc(pt.get("site_type", "—"))), ("URLs classified", _esc(pt.get("urls_classified", "—"))),
                   ("Inventory", _esc(src.get("status", "—"))),
                   ("Expected types missing", _esc(", ".join(missing) if missing else ("none" if expected else "—")))])
            + (_table(["Page type", "URLs", "Share", "Intent", "Sections"], rows) if rows else "")
            + render_recommendations(pt)
        )

    nv = get("navigation")
    if nv:
        prim = (nv.get("primary_nav") or {}).get("links") or []
        nav_rows = [f"<tr><td>{_esc(l.get('anchor') or '(empty)')}</td><td class=\"url\">{_clip(l.get('href', ''), 90)}</td></tr>" for l in prim[:25]]
        bc = nv.get("breadcrumbs") or {}
        panels["navigation"] = (
            _notice("Global navigation, footer and breadcrumbs read from the page chrome (links repeating on 80% of sampled pages). "
                    "A JavaScript-only navigation is reported as not measured, never as absent. Shown, not weighted.", "info")
            + _kv([("Status", _esc(nv.get("status", "—"))), ("Pages sampled", _esc(nv.get("sampled_pages", "—"))),
                   ("Primary nav links", _esc((nv.get("primary_nav") or {}).get("count", "—"))),
                   ("Footer links", _esc((nv.get("footer_nav") or {}).get("count", "—"))),
                   ("Breadcrumbs (visible / JSON-LD)", _esc(f"{bc.get('with_visible', 0)} / {bc.get('with_jsonld', 0)}"))])
            + (_subhead("Primary navigation") + _table(["Anchor", "URL"], nav_rows) if nav_rows else "")
            + render_recommendations(nv)
        )

    ar = get("architecture")
    if ar:
        def _equity_cell(sct):
            share = sct.get("equity_share")
            return "—" if share is None else f"{share:.0%}"

        sec_rows = [
            f"<tr><td class=\"url\">{_esc(sct.get('path', ''))}</td><td class=\"num\">{_esc(sct.get('url_count', 0))}</td>"
            f"<td>{_esc(sct.get('dominant_label', ''))}</td><td>{_yes_no(sct.get('in_nav'))}</td><td>{_yes_no((sct.get('hub') or {}).get('exists'))}</td>"
            f"<td class=\"num\">{_esc(sct.get('avg_depth') if sct.get('avg_depth') is not None else '—')}</td>"
            f"<td class=\"num\">{_esc(_equity_cell(sct))}</td></tr>"
            for sct in (ar.get("sections") or [])[:20] if not sct.get("parent")
        ]
        eq = ar.get("equity") or {}
        inv = ar.get("inventory") or {}
        panels["architecture"] = (
            _notice("Sections by first directory: size, dominant page type, whether the navigation reaches them, hub page, click depth, "
                    "and the share of internal link equity (PageRank, chrome links x0.25) — equity only on a complete crawl. Shown, not weighted.", "info")
            + _kv([("URLs in inventory", _esc(inv.get("total", "—"))), ("Inventory", "complete" if inv.get("complete") else "incomplete"),
                   ("Equity", _esc(eq.get("status", "—")))])
            + (_table(["Section", "URLs", "Type", "In nav", "Hub", "Depth", "Equity"], sec_rows) if sec_rows else "")
            + (f"<pre class=\"mono\">{_esc(ar.get('mermaid', ''))}</pre>" if ar.get("mermaid") else "")
            + render_recommendations(ar)
        )

    sp = get("search_performance")
    if sp:
        window = (sp.get("windows") or {}).get("current") or ["—", "—"]
        curve = sp.get("ctr_curve") or {}

        def pct(value):
            return f"{value or 0:.1%}"

        def cells(values, url_at=None, text_at=(0,)):
            """Table cells: the URL column clipped, text columns left, figures right-aligned."""
            return "".join(
                f'<td class="url">{_clip(v, 70)}</td>' if i == url_at else
                f"<td>{_esc(v)}</td>" if i in text_at else
                f'<td class="num">{_esc(f"{v:,}" if isinstance(v, int) else v)}</td>'
                for i, v in enumerate(values)
            )

        curve_rows = [f"<tr>{cells([pos, pct(v.get('median_ctr')), v.get('rows', 0)], text_at=())}</tr>" for pos, v in curve.items()]
        sd_rows = [f"<tr>{cells([i.get('query', ''), i.get('page', ''), i.get('position'), i.get('impressions', 0), i.get('upside_clicks_at_position_3')], 1)}</tr>"
                   for i in ((sp.get("striking_distance") or {}).get("items") or [])[:10]]
        lc_rows = [f"<tr>{cells([i.get('query', ''), i.get('page', ''), i.get('position'), pct(i.get('ctr')), pct(i.get('expected_ctr'))], 1)}</tr>"
                   for i in ((sp.get("low_ctr") or {}).get("items") or [])[:10]]
        dc_rows = []
        for i in ((sp.get("decay") or {}).get("items") or [])[:10]:
            clicks = i.get("clicks") or {}
            trail = " / ".join(str(clicks.get(k, 0)) for k in ("before_previous", "previous", "current"))
            pattern = {True: "seasonal", False: "trend"}.get(i.get("seasonal"), "no last-year data")
            dc_rows.append(f"<tr>{cells([i.get('page', ''), trail, pattern], 0, (2,))}</tr>")
        panels["search_performance"] = (
            _notice("Query and page performance from the Search Console API: striking-distance queries, low CTR against this "
                    "property's own CTR by position, queries split across URLs, and pages down two windows in a row. "
                    "Every figure is from the API; shown, not weighted. Its page clicks also fill the "
                    "&ldquo;Traffic at stake&rdquo; line of every finding that names a page.", "info")
            + _kv([("Window", _esc(f"{window[0]} to {window[1]}")),
                   ("Query x page rows", _esc(sp.get("query_page_rows", "—"))),
                   ("Row cap reached", _esc(", ".join(sp.get("truncated") or []) or "no"))])
            + (_subhead("Striking distance (position 8-15)") + _table(["Query", "Page", "Position", "Impressions", "Upside at position 3"], sd_rows) if sd_rows else "")
            + (_subhead("Low CTR for the position") + _table(["Query", "Page", "Position", "CTR", "Site median"], lc_rows) if lc_rows else "")
            + (_subhead("Decaying pages (clicks per window)") + _table(["Page", "Clicks, oldest to latest", "Pattern"], dc_rows) if dc_rows else "")
            + (_subhead("This property's CTR by position") + _table(["Position", "Median CTR", "Rows"], curve_rows) if curve_rows else "")
            + render_recommendations(sp)
            + "".join(f'<p class="small">{_esc(line)}</p>' for line in sp.get("limits") or [])
        )

    return panels


def _finding_key(finding: dict, from_wording: bool = False) -> str:
    """A summary finding's identity across runs.

    from_wording ignores a stored key and derives one from the text alone. A
    summary written before keys existed can only be read that way, and then
    both sides must be, or a finding whose script supplies a "type" would
    look resolved and new at once.
    """
    if not from_wording and finding.get("key"):
        return finding["key"]
    return finding_code(finding.get("section") or "", {}, finding.get("finding") or "")[1]


def _brief(finding: dict, **extra) -> dict:
    return {"id": finding.get("id"), "section": finding.get("section"), "finding": finding.get("finding"),
            "code": finding.get("code") or _finding_key(finding).split("#")[0], "lane": finding.get("lane"), **extra}


def compare_with_previous(summary: dict, previous: dict) -> dict:
    """What changed since an earlier ``--json`` summary of the same site.

    Findings are matched by key (finding_code), not by ID or wording: IDs are
    renumbered on every run and wording carries counts. An earlier finding whose
    check did not run this time is "not_rechecked", never "resolved": silence
    from a check that was rate-limited is not a fix. Returned as plain data so
    the JSON summary can carry it too.
    """
    before = [f for f in previous.get("findings") or [] if isinstance(f, dict)]
    legacy = any(not f.get("key") for f in before)
    current = {_finding_key(f, legacy): f for f in summary.get("findings") or [] if isinstance(f, dict)}
    earlier = {_finding_key(f, legacy): f for f in before}
    ran = summary.get("sections_run")
    ran = set(ran) if isinstance(ran, list) else None
    unmeasured = set(summary.get("unmeasured") or [])

    def rechecked(finding: dict) -> bool:
        section = finding.get("section")
        return section not in unmeasured and (ran is None or section in ran)

    resolved, not_rechecked, persisting = [], [], []
    for k, f in earlier.items():
        if k in current:
            now = current[k]
            changed = {}
            if now.get("severity") != f.get("severity") and f.get("severity"):
                changed["severity_was"] = f.get("severity")
            if now.get("finding") != f.get("finding"):
                changed["finding_was"] = f.get("finding")
            persisting.append(_brief(now, first_seen=f.get("first_seen") or previous.get("timestamp"), **changed))
        elif rechecked(f):
            resolved.append(_brief(f))
        else:
            not_rechecked.append(_brief(f))
    new = [_brief(f) for k, f in current.items() if k not in earlier]
    changes = []
    earlier_categories = previous.get("categories") or {}
    for check, category in (summary.get("categories") or {}).items():
        before = earlier_categories.get(check) or {}
        if before and before.get("status") != category.get("status"):
            changes.append({"check": check, "label": category.get("label") or CHECK_LABELS.get(check, check),
                            "from": before.get("status"), "to": category.get("status")})
    now, then = summary.get("overall"), previous.get("overall")
    delta = now - then if isinstance(now, int) and isinstance(then, int) else None
    return {
        "timestamp": previous.get("timestamp"),
        "overall": then,
        "score_delta": delta,
        "resolved": resolved,
        "new": new,
        "persisting": persisting,
        "not_rechecked": not_rechecked,
        "status_changes": changes,
    }


def apply_previous(summary: dict, previous: dict) -> dict:
    """Attach the comparison to summary and stamp each finding with status and first_seen.

    first_seen carries forward from run to run, so a chain of --previous runs
    knows how long a finding has been open.
    """
    delta = compare_with_previous(summary, previous)
    seen = {item["id"]: item.get("first_seen") for item in delta["persisting"]}
    for finding in summary.get("findings") or []:
        if finding.get("id") in seen:
            finding["status"], finding["first_seen"] = "persisting", seen[finding["id"]]
        else:
            finding["status"], finding["first_seen"] = "new", summary.get("timestamp")
    summary["previous"] = delta
    return delta


def _coverage_counts(statuses: dict, weights: dict) -> dict:
    counts = {"weighted": 0, "display": 0, "deferred": 0, "na": 0}
    for key, (status, _label) in statuses.items():
        if status in ("ok", "flag", "gap"):
            if key in DISPLAY_ONLY_CHECKS or not weights.get(key):
                counts["display"] += 1
            else:
                counts["weighted"] += 1
        elif status == "deferred":
            counts["deferred"] += 1
        else:
            counts["na"] += 1
    return counts


def _inventory(data: dict) -> dict:
    """Inventory and completeness from the structure checks, when they ran."""
    sections = data.get("sections", {})
    ar = _source_section(sections, "architecture")
    pt = _source_section(sections, "page_types")
    inv = (ar.get("inventory") or {}) if isinstance(ar, dict) else {}
    src = (pt.get("source") or {}) if isinstance(pt, dict) else {}
    complete = inv.get("complete") if inv else (src.get("status") == "complete" if src else None)
    site_type = (pt.get("site_type") if isinstance(pt, dict) else None) or (ar.get("site_type") if isinstance(ar, dict) else None)
    return {
        "total": inv.get("total"),
        "fetched": inv.get("fetched"),
        "sitemap_urls": inv.get("sitemap_urls"),
        "complete": complete,
        "site_type": site_type,
        "measured": bool(inv or src),
    }


def _short_date(timestamp) -> str:
    try:
        return datetime.fromisoformat(str(timestamp)).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return str(timestamp or "")


def _finding_kind(issue: dict) -> str:
    return issue.get("kind") or classify_finding(issue)["kind"]


def _finding_card(issue: dict) -> str:
    fid = issue["id"]
    severity = issue["severity"]
    section = issue["section"]
    label = CHECK_LABELS.get(section, section.replace("_", " ").capitalize())
    headline = _headline(issue["finding"] or issue["text"])
    source = issue.get("source_issue") or {}
    kind = _finding_kind(issue)
    rows = []
    if issue["finding"] and issue["finding"] != headline:
        rows.append(("Finding", _esc(issue["finding"])))
    for field_label, keys in (
        ("Evidence", ("evidence",)),
        ("Impact", ("impact",)),
    ):
        value = _supplied(source, *keys)
        if value:
            rows.append((field_label, _esc(value)))
    confidence = _confidence(source)
    falsifiability = _supplied(source, "falsifiability", "failure_check", "how_to_know_failed", "validation")
    if confidence or falsifiability:
        text = _esc(confidence) if confidence else ""
        if falsifiability:
            text += (". " if text else "") + "Wrong if: " + _esc(falsifiability)
        rows.append(("Confidence", text))
    if issue.get("traffic"):
        rows.append(("Traffic at stake", _esc(traffic_text(issue["traffic"]))))
    if issue["fix"]:
        rows.append(("Fix", _esc(issue["fix"])))
    if issue.get("lane"):
        rows.append(("Who", f'{_lane_chip(issue["lane"])} {_esc(issue.get("lane_reason") or "")}'))
    watch = _supplied(source, "leading_indicator", "metric")
    if watch:
        rows.append(("Watch", _esc(watch)))
    dependency = _supplied(source, "dependency", "depends_on")
    if dependency:
        rows.append(("Depends on", _esc(dependency)))
    check_link = (
        f'<a href="#check-{section}">Open the {_esc(label)} check</a>'
        if section in CHECK_LABELS else _esc(label)
    )
    rows.append(("Source", f'<span class="mono">script:{_esc(section)}</span> · {check_link}'))
    dl = "".join(f"<dt>{_esc(k)}</dt><dd>{v}</dd>" for k, v in rows)
    kind_chip = _chip("g", "Opportunity") if kind == "opportunity" else _severity_chip(severity)
    css = "opp" if kind == "opportunity" else _SEVERITY_CHIP.get(severity, "o")
    return (
        f'<article class="find {css}" data-key="{fid}" data-filter="{severity}" id="{fid}" aria-labelledby="{fid}-title">'
        f'<div class="find-top"><span class="pid">{fid}</span>{kind_chip}'
        f'<h3 id="{fid}-title">{_esc(headline)}</h3><span class="chip o">{_esc(label)}</span></div>'
        f"<dl>{dl}</dl></article>"
    )


def _render_findings(issues: list) -> str:
    defects = [i for i in issues if _finding_kind(i) == "defect"]
    opportunities = [i for i in issues if _finding_kind(i) == "opportunity"]
    counts = {s: sum(1 for i in defects if i["severity"] == s) for s in ("critical", "warning", "info")}
    tally = (f'{len(defects)} · {counts["critical"]} critical · {counts["warning"]} warning · {counts["info"]} info')
    if opportunities:
        tally += f' · {len(opportunities)} {"opportunity" if len(opportunities) == 1 else "opportunities"}'
    questions = sum(1 for i in issues if _finding_kind(i) == "data_gap")
    if questions:
        tally += f' · {questions} moved to open questions'
    head = (
        '<div class="sec-head"><span class="sec-n">07</span><h2 id="findings-h">Findings</h2>'
        f'<span class="small mono">{tally}</span></div>'
    )
    if not defects and not opportunities:
        return head + _notice("No findings. Every check came back without an issue.", "good")

    filters = "".join(
        f'<button type="button" data-filter="{key}" aria-pressed="{"true" if key == "all" else "false"}">'
        f"{label} <b>{count}</b></button>"
        for key, label, count in (
            ("all", "All", len(defects)),
            ("critical", "Critical", sum(1 for i in defects if i["severity"] == "critical")),
            ("warning", "Warning", sum(1 for i in defects if i["severity"] == "warning")),
            ("info", "Info", sum(1 for i in defects if i["severity"] == "info")),
        )
    )
    intro = (
        '<p class="prose">The evidence register behind the <a href="#plan">action plan</a>, ordered by severity, '
        "then by the check that raised them. Every card names its evidence when the check supplied it, the fix, "
        "who can act on it, and the check to open for detail. Opportunities (pages to create) are listed separately "
        "and never count against the score; things a check could not see are under "
        '<a href="#questions">open questions</a>.</p>'
        f'<div class="filters" id="finding-filter" role="group" aria-label="Filter by severity">{filters}</div>'
    )

    rows = []
    for issue in defects:
        fid = issue["id"]
        label = CHECK_LABELS.get(issue["section"], issue["section"].replace("_", " ").capitalize())
        rows.append(
            f'<tr data-key="{fid}" data-filter="{issue["severity"]}">'
            f'<td class="q"><a href="#{fid}">{fid}</a></td>'
            f'<td>{_esc(_headline(issue["finding"] or issue["text"]))}</td>'
            f"<td>{_severity_chip(issue['severity'])}</td>"
            f'<td class="small">{_esc(label)}</td></tr>'
        )
    index = (
        '<div class="tw"><table aria-label="Findings index"><thead><tr>'
        '<th scope="col">ID</th><th scope="col">Finding</th><th scope="col">Severity</th><th scope="col">Check</th>'
        f'</tr></thead><tbody id="finding-rows">{"".join(rows)}</tbody></table></div>'
        if rows else ""
    )
    cards = "".join(_finding_card(i) for i in defects)
    opp_html = ""
    if opportunities:
        opp_html = (
            '<h3 class="block-h" id="opportunities">Opportunities</h3>'
            '<p class="small prose">Pages to create, not defects to fix. Raised by the page-type check from a '
            "complete inventory; they never enter the severity list.</p>"
            + "".join(_finding_card(i) for i in opportunities)
        )
    return head + intro + index + f'<div id="finding-cards">{cards}</div>' + opp_html


def _lane_chip(lane) -> str:
    return f'<span class="chip lane-{_esc(lane)}">{_esc(LANE_TITLES.get(lane, lane))}</span>' if lane else ""


def build_fix_prompt(data: dict, items: list) -> str:
    """The request that hands the Auto lane back to an agent, as plain text."""
    lines = [
        f"Using the ultimate-seo-geo skill in Mode 3 (Execute), fix these findings from the "
        f"{_short_date(data.get('timestamp'))} report for {data.get('url')}.",
        "All are in the Safe change class. Show each change before applying it, skip any that turns out "
        "to need a robots.txt, canonical, redirect, noindex or hreflang edit, and afterwards re-run "
        "generate_report.py with --previous pointing at this run's JSON summary to confirm they are gone.",
        "",
    ]
    for issue in items:
        line = f"- {issue['id']} [{issue['section']}] {issue['finding']}"
        if issue.get("fix"):
            line += f" Fix: {issue['fix']}"
        lines.append(line)
    return "\n".join(lines)


def _plan_row(issue: dict, gains: dict, since: dict = None) -> str:
    label = CHECK_LABELS.get(issue["section"], issue["section"].replace("_", " ").capitalize())
    fix = f'<p class="plan-fix">{_esc(issue["fix"])}</p>' if issue.get("fix") else (
        '<p class="plan-fix muted">The check named no fix; open the finding for its evidence.</p>')
    gain = gains.get(issue["section"])
    gain_html = (f'<span class="small mono" title="What the whole {_esc(label)} check adds back at 100">'
                 f"check: up to +{gain:g} pts</span>") if gain else ""
    age = ""
    if since is not None:
        first = since.get(issue["id"])
        age = (_chip("o", f"Open since {_short_date(first)}") if first else _chip("m", "New"))
    dependency = _supplied(issue.get("source_issue") or {}, "dependency", "depends_on")
    dep_html = f'<p class="small"><b>Depends on</b> {_esc(dependency)}</p>' if dependency else ""
    traffic = issue.get("traffic") or {}
    if traffic.get("scope") == "pages" and traffic.get("clicks"):
        gain_html = (f'<span class="small mono" title="{_esc(traffic_text(traffic))}">'
                     f'{traffic["clicks"]:,} clicks at stake</span>') + gain_html
    elif traffic.get("scope") == "site":
        gain_html = '<span class="small mono">site-wide</span>' + gain_html
    return (
        f'<li class="plan-item" data-key="{issue["id"]}">'
        f'<div class="plan-top"><a class="pid" href="#{issue["id"]}">{issue["id"]}</a>{_severity_chip(issue["severity"])}{age}'
        f'<strong>{_esc(_headline(issue["finding"]))}</strong></div>'
        f'{fix}{dep_html}<p class="plan-meta"><span class="chip o">{_esc(label)}</span>{gain_html}</p></li>'
    )


def _render_fixed(delta: dict) -> str:
    """What the last run found and this run no longer does: the verify step of the loop."""
    if not delta:
        return ""
    resolved = delta.get("resolved") or []
    skipped = delta.get("not_rechecked") or []
    if not resolved and not skipped:
        return ""
    then = _short_date(delta.get("timestamp"))
    html = ""
    if resolved:
        rows = []
        for item in resolved:
            was = f" · was: {LANE_TITLES[item['lane']]}" if item.get("lane") in LANE_TITLES else ""
            label = CHECK_LABELS.get(item.get("section"), item.get("section") or "")
            rows.append(f'<li class="ok"><span class="mk">✓</span><div>{_esc(_headline(item.get("finding") or ""))}'
                        f"<small>{_esc(label + was)}</small></div></li>")
        html += (
            '<section class="lane" id="fixed" aria-labelledby="fixed-h"><div class="lane-head">'
            f'<h3 id="fixed-h">Fixed since the {_esc(then)} run</h3><span class="chip g">{len(resolved)}</span></div>'
            '<p class="small prose">Found last time, re-checked this time, gone. Matched by finding code, so a count '
            f'that only moved is not listed here.</p><ul class="qc">{"".join(rows)}</ul></section>'
        )
    if skipped:
        names = _join_labels(sorted({CHECK_LABELS.get(i.get("section"), i.get("section") or "") for i in skipped}))
        html += _notice(f"{len(skipped)} earlier {'finding was' if len(skipped) == 1 else 'findings were'} not re-checked, because "
                        f"{_esc(names)} did not run this time. They are not counted as fixed.", "empty", "Not re-checked")
    return html


def _render_action_plan(data: dict, scores: dict, issues: list, delta: dict = None) -> str:
    plan = build_action_plan(issues, scores)
    since = None
    if delta:
        since = {item["id"]: item.get("first_seen") for item in delta.get("persisting") or []}
    gains = check_score_gains(scores)
    total = sum(len(items) for items in plan.values())
    tally = " · ".join(f"{len(plan[lane])} {LANE_TITLES[lane].lower()}" for lane in LANES if plan[lane])
    head = (
        '<div class="sec-head"><span class="sec-n">02</span><h2 id="plan-h">Action plan</h2>'
        f'<span class="small mono">{_esc(tally or "nothing to do")}</span></div>'
    )
    if not total:
        return head + _render_fixed(delta) + _notice("Nothing to act on. No finding in this run names work to do.", "good")
    intro = (
        '<p class="prose">Every finding that names work, sorted by who can do it. Work an agent can finish on its '
        "own comes first; inside each lane the order is severity, then the score the check can recover. "
        "&ldquo;AI can fix now&rdquo; means the change needs no human judgement or sign-off; it still needs an agent "
        "with access to the site&rsquo;s code or CMS. Evidence for every item is in the "
        '<a href="#findings">findings register</a>.</p>'
    )
    if data.get("gsc_traffic"):
        intro += (f'<p class="small prose">Search Console clicks ({_esc(_traffic_window(data["gsc_traffic"]))}) break ties '
                  "inside each severity: site-wide findings first, then the findings whose pages earn the most clicks.</p>")
    notes = sum(1 for i in issues if i.get("lane") and i["severity"] == "info" and not i.get("fix"))
    if notes:
        intro += (f'<p class="small prose">{notes} informational {"note names" if notes == 1 else "notes name"} no fix and '
                  "stay in the findings register only.</p>")
    blocks = []
    for lane in LANES:
        items = plan[lane]
        if not items:
            continue
        rows = "".join(_plan_row(i, gains, since) for i in items)
        prompt_html = ""
        if lane == "Auto":
            prompt_html = (
                '<details class="fix-prompt" open><summary>Hand this lane to an agent</summary>'
                '<p class="small">Paste this into Claude Code, Cursor or any agent that has the skill and the site&rsquo;s code.</p>'
                f'<pre class="mono" id="fix-prompt-text">{_esc(build_fix_prompt(data, items))}</pre>'
                '<button type="button" class="copy-btn" id="fix-prompt-copy" data-copy="fix-prompt-text">Copy fix prompt</button>'
                "</details>"
            )
        blocks.append(
            f'<section class="lane" id="lane-{lane.lower()}" aria-labelledby="lane-{lane.lower()}-h">'
            f'<div class="lane-head"><h3 id="lane-{lane.lower()}-h">{_esc(LANE_TITLES[lane])}</h3>'
            f'<span class="chip lane-{lane}">{len(items)}</span></div>'
            f'<p class="small prose">{_esc(LANE_REASONS[lane])}</p>'
            f'<ol class="plan">{rows}</ol>{prompt_html}</section>'
        )
    return head + intro + _render_fixed(delta) + "".join(blocks)


def _render_open_questions(questions: list) -> str:
    head = (
        '<div class="sec-head"><span class="sec-n">03</span><h2 id="questions-h">Open questions</h2>'
        f'<span class="small mono">{len(questions)} open</span></div>'
    )
    if not questions:
        return head + _notice("Nothing open. Every check ran and none reported a blind spot.", "good")
    intro = (
        '<p class="prose">What this run could not see. These are not defects and are not in the plan or the '
        "severity counts: each one is information to get before the matching part of the audit can be trusted.</p>"
    )
    rows = []
    for q in questions:
        label = CHECK_LABELS.get(q["check"], q["check"])
        why = f'<small>{_esc(q["why"])}</small>' if q.get("why") else ""
        unlocks = f'<small>Unlocks: {_esc(q["unlocks"])}</small>' if q.get("unlocks") else ""
        rows.append(
            f'<tr data-key="{_esc(q["id"])}" id="{_esc(q["id"])}"><td class="q">{_esc(q["id"])}</td>'
            f'<td>{_esc(q["question"])}{why}</td>'
            f'<td>{_esc(q.get("close") or "No next step named by the check.")}{unlocks}</td>'
            f'<td class="small"><a href="#check-{_esc(q["check"])}">{_esc(label)}</a></td></tr>'
        )
    return head + intro + (
        '<div class="tw"><table class="questions" aria-label="Open questions"><thead><tr>'
        '<th scope="col">ID</th><th scope="col">What is not known</th><th scope="col">What closes it</th>'
        f'<th scope="col">Check</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def _check_entries(data: dict, scores: dict) -> list:
    categories = scores.get("categories", {})
    entries = []
    for key, label in CHECK_LABELS.items():
        section = _source_section(data["sections"], key)
        section = section if isinstance(section, dict) else {}
        status, status_label = _check_status(key, section, categories.get(key))
        entries.append((key, label, status, status_label, categories.get(key) or 0))
    entries.sort(key=lambda e: (_STATUS_RANK[e[2]], e[4]))
    return entries


def _render_checks_table(data: dict, scores: dict, issues: list, entries: list) -> str:
    weights = scores.get("weights", {})
    finding_counts = {}
    for issue in issues:
        finding_counts[issue["section"]] = finding_counts.get(issue["section"], 0) + 1
    rows = []
    for key, label, status, status_label, score in entries:
        measured = status not in ("deferred", "na")
        scored = measured and key not in DISPLAY_ONLY_CHECKS and bool(weights.get(key))
        pct = max(0, min(100, int(score)))
        if scored:
            counts_as = "weighted"
        elif measured:
            counts_as = "shown, not weighted"
        elif status == "deferred":
            counts_as = "not measured"
        else:
            counts_as = status_label.lower()
        score_html = f'<span class="mono">{pct}</span>' if scored else '<span class="muted">—</span>'
        weight_html = _esc(weights.get(key)) if scored else "—"
        rows.append(
            f'<tr data-key="{key}">'
            f'<td><a href="#check-{key}">{_esc(label)}</a></td>'
            f'<td class="small">{_esc(CHECK_GROUP.get(key, ""))}</td>'
            f"<td>{_status_chip(status, status_label)}</td>"
            f'<td class="n">{score_html}</td><td class="n">{weight_html}</td>'
            f'<td class="n">{finding_counts.get(key, 0)}</td>'
            f'<td class="small">{_esc(counts_as)}</td></tr>'
        )
    return (
        '<div class="tw"><table aria-label="Checks"><thead><tr>'
        '<th scope="col">Check</th><th scope="col">Group</th><th scope="col">Status</th>'
        '<th scope="col" class="n">Score</th><th scope="col" class="n">Weight</th>'
        '<th scope="col" class="n">Findings</th><th scope="col">Counts toward score</th>'
        f'</tr></thead><tbody id="check-rows">{"".join(rows)}</tbody></table></div>'
    )


def _render_check_details(data: dict, scores: dict, issues: list, entries: list) -> str:
    weights = scores.get("weights", {})
    panels = _check_panels(data)
    finding_counts = {}
    for issue in issues:
        finding_counts[issue["section"]] = finding_counts.get(issue["section"], 0) + 1
    cards = []
    for key, label, status, status_label, score in entries:
        measured = status not in ("deferred", "na")
        scored = measured and key not in DISPLAY_ONLY_CHECKS and bool(weights.get(key))
        pct = max(0, min(100, int(score)))
        score_top = f'<span class="mono">{pct} / 100 · weight {_esc(weights.get(key))}</span>' if scored else ""
        count = finding_counts.get(key, 0)
        noun = "finding" if count == 1 else "findings"
        cards.append(
            f'<article class="card detail" data-key="{key}" id="check-{key}" aria-labelledby="check-{key}-title">'
            f'<div class="card-top"><span class="label">Check</span>{_status_chip(status, status_label)}{score_top}'
            f'<span class="small">{count} {noun}</span></div>'
            f'<h3 id="check-{key}-title">{_esc(label)}</h3>'
            f'<div class="panel-body">{panels.get(key, "")}</div>'
            "</article>"
        )
    return "".join(cards)


def _measured_count(scores: dict) -> int:
    """How many weighted checks produced a score (the number the CI gate reads)."""
    value = scores.get("measured_categories")
    if isinstance(value, int):
        return value
    if isinstance(value, (list, tuple, set)):
        return len(value)
    weights = scores.get("weights") or {}
    raw = scores.get("raw_categories") or {}
    return sum(1 for k, w in weights.items() if w and raw.get(k) is not None)


def _render_score(data: dict, scores: dict, stamp: str, statuses: dict) -> str:
    overall = scores["overall"]
    measured = _measured_count(scores)
    weights = scores.get("weights") or {}
    # "Not measured" is a weighted check that ran and failed; a check that never
    # ran is counted, not listed, so the source line stays readable.
    unmeasured = [k for k, (status, _label) in statuses.items() if status == "deferred" and weights.get(k)]
    not_run = sum(1 for k, (status, label) in statuses.items() if label == "Not run" and weights.get(k))
    groups = group_scores(scores)
    bars = []
    for group, info in groups.items():
        score = info.get("score")
        n_checks = len(info.get("checks") or [])
        n_unmeasured = len(info.get("unmeasured") or [])
        sub = f"{n_checks} {'check' if n_checks == 1 else 'checks'}"
        if n_unmeasured:
            sub += f" · {n_unmeasured} not measured"
        if info.get("share"):
            sub += f" · {info['share']}% of score"
        status = info.get("status", "")
        chip = _chip({"Strong": "g", "Needs work": "h", "Gap": "c"}.get(status, "o"), status)
        if score is None:
            track = '<div class="track nm"></div><div class="val nm">—</div>'
        else:
            track = f'<div class="track"><i style="width:{max(0, min(100, int(score)))}%"></i></div><div class="val">{int(score)}</div>'
        bars.append(f'<div class="lbl">{_esc(info.get("label", group))} <small>{_esc(sub)}</small></div>{track}{chip}')
    if measured < MIN_MEASURED_FOR_GATE:
        number = f'<div class="score-n ns">Inconclusive</div>'
        source = (f"Only {measured} weighted {'check' if measured == 1 else 'checks'} measured; the Health Score needs "
                  f"at least {MIN_MEASURED_FOR_GATE}. Computed value {overall}/100 is not a valid score.")
    else:
        number = f'<div class="score-n">{overall}<small>/100 · {_esc(_grade(overall))}</small></div>'
        source = f"{measured} weighted checks measured"
        if unmeasured:
            source += " · not measured: " + _esc(_join_labels([CHECK_LABELS.get(k, k) for k in unmeasured]))
        if not_run:
            source += f" · {not_run} weighted {'check' if not_run == 1 else 'checks'} did not run"
        source += ". Shown unmodified; display-only checks carry no weight."
    return (
        '<div class="sec-head"><span class="sec-n">04</span><h2 id="score-h">Health Score</h2></div>'
        f'<div class="score">{number}<p class="score-src">Source: generate_report.py · {_esc(stamp)}<br>{source}</p>'
        f'<div class="bars" role="img" aria-label="Score by category">{"".join(bars)}</div></div>'
        '<p class="small prose">Category shares are the weights of the checks that ran, renormalised. A category with '
        "a hatched track was not measured or does not apply; it never reads as a low score.</p>"
    )


def _render_delta(delta: dict) -> str:
    if not delta:
        return ""
    then = _short_date(delta.get("timestamp"))
    change = delta.get("score_delta")
    if change is None:
        score_html = '<b>—</b><span>Health Score comparison not available</span>'
    else:
        sign = "+" if change > 0 else ""
        css = "up" if change > 0 else "dn" if change < 0 else ""
        score_html = (f'<b class="{css}">{sign}{change}</b>'
                      f'<span>Health Score since the {_esc(then)} run ({_esc(delta.get("overall"))} → now)</span>')

    def ids(items: list) -> str:
        return "".join(f'<span class="pid">{_esc(i.get("id"))}</span>' for i in items[:6] if i.get("id"))

    resolved = delta.get("resolved") or []
    new = delta.get("new") or []
    changes = delta.get("status_changes") or []
    skipped = len(delta.get("not_rechecked") or [])
    skipped_note = f" · {skipped} not re-checked" if skipped else ""
    # The "Fixed since" block exists only when something cleared.
    fixed_link = '<span class="small"><a href="#fixed">See what cleared</a></span>' if resolved else ""
    change_text = " · ".join(f'{_esc(c.get("label"))} {_esc(c.get("from"))} → {_esc(c.get("to"))}' for c in changes[:4])
    return (
        f'<div class="delta" aria-label="Change since the previous run">'
        f"<div>{score_html}</div>"
        f'<div><b class="{"up" if resolved else ""}">{len(resolved)}</b><span>Findings fixed{skipped_note}</span>'
        f'{fixed_link}</div>'
        f'<div><b class="{"dn" if new else ""}">{len(new)}</b><span>New findings</span><span class="ids">{ids(new)}</span></div>'
        f'<div><b>{len(changes)}</b><span>Checks that changed status</span><span class="small">{change_text}</span></div>'
        "</div>"
    )


def _render_coverage(data: dict, scores: dict, issues: list, entries: list, counts: dict, inventory: dict) -> str:
    sections = data["sections"]
    ran = sum(1 for value in sections.values() if isinstance(value, dict) and not value.get("error"))
    tiles = []
    if inventory["measured"]:
        tiles.append((inventory.get("sitemap_urls") if inventory.get("sitemap_urls") is not None else "—",
                      "sitemap URLs · " + ("complete" if inventory.get("complete") else "incomplete")))
        tiles.append((inventory.get("fetched") if inventory.get("fetched") is not None else "—", "pages fetched by the site graph"))
    tiles.append((f"{ran} of {len(sections)}", "checks ran"))
    tiles.append((counts["weighted"], "weighted checks in the score"))
    if len(tiles) < 4:
        tiles.append((len(issues), "findings"))
    tiles_html = "".join(f"<div><b>{_esc(v)}</b><span>{_esc(l)}</span></div>" for v, l in tiles[:4])
    if inventory["measured"] and inventory.get("complete"):
        claim = _notice("Inventory complete: findings about missing page types, hubs and orphans are allowed.", "good")
    elif inventory["measured"]:
        claim = _notice("Inventory incomplete: absence claims (missing page types, hubs, orphans, equity share) are withheld.", "flag")
    else:
        claim = _notice("No site graph: the structure checks did not run, so absence claims are withheld.", "flag")
    return (
        '<div class="sec-head"><span class="sec-n">05</span><h2 id="coverage-h">Scope and coverage</h2></div>'
        f'<div class="cov" aria-label="Inventory and completeness">{tiles_html}</div>{claim}'
        '<p class="small prose">Every check with its status, sorted weakest first. Weighted checks score 0 to 100 and '
        "carry a weight; display-only checks are reviewed but never move the score; a check that failed to run is "
        "not measured, and one that does not apply to this site is not a gap.</p>"
        + _render_checks_table(data, scores, issues, entries)
    )


def _render_site_shape(data: dict) -> str:
    sections = data["sections"]
    pt = _source_section(sections, "page_types")
    nv = _source_section(sections, "navigation")
    ar = _source_section(sections, "architecture")
    sm = _source_section(sections, "sitemap")
    pt = pt if isinstance(pt, dict) and not pt.get("error") else {}
    nv = nv if isinstance(nv, dict) and not nv.get("error") else {}
    ar = ar if isinstance(ar, dict) and not ar.get("error") else {}
    sm = sm if isinstance(sm, dict) else {}
    if not (pt or nv or ar):
        return ""
    parts = ['<div class="sec-head"><span class="sec-n">06</span><h2 id="shape-h">Site shape</h2></div>',
             '<p class="prose">Measured by the structure checks on the shared crawl. Shown, not weighted.</p>']

    by_intent = pt.get("by_intent") or {}
    if by_intent:
        order = ("TOFU", "MOFU", "BOFU", "support", "trust", "meta")
        cells = []
        for stage in order:
            info = by_intent.get(stage) or {}
            count = info.get("count", 0) or 0
            share = info.get("share")
            share_text = f"{round(100 * share)}% of URLs" if isinstance(share, (int, float)) else ""
            cells.append(f'<div class="{"gap" if not count else ""}"><span>{_esc(stage)}</span><b>{count}</b><small>{_esc(share_text)}</small></div>')
        parts.append(f'<div class="funnel" aria-label="Pages by funnel stage">{"".join(cells)}</div>')

    tree_html = ""
    top = [s for s in (ar.get("sections") or []) if isinstance(s, dict) and not s.get("parent")]
    if top:
        children = {}
        for s in ar.get("sections") or []:
            if isinstance(s, dict) and s.get("parent"):
                children.setdefault(s["parent"], []).append(s)

        def node(s: dict) -> str:
            tags = []
            if s.get("in_nav"):
                tags.append("in nav")
            hub = s.get("hub") or {}
            if hub.get("exists"):
                tags.append("hub")
            share = s.get("equity_share")
            if isinstance(share, (int, float)):
                tags.append(f"{share:.0%} equity")
            flags = []
            if not hub.get("exists"):
                flags.append("no hub")
            if not s.get("in_nav"):
                flags.append("not in nav")
            html = (f'<li><span class="path">{_esc(s.get("path", ""))}</span>'
                    f'<span class="cnt">{_esc(s.get("url_count", 0))}</span>')
            if s.get("dominant_label"):
                html += f'<span class="tag">{_esc(str(s["dominant_label"]).replace("_", " "))}</span>'
            if tags:
                html += f'<span class="tag">{_esc(" · ".join(tags))}</span>'
            if flags:
                html += f'<span class="chip c">{_esc(" · ".join(flags))}</span>'
            kids = children.get(s.get("path"))
            if kids:
                html += "<ul>" + "".join(node(k) for k in kids[:8]) + "</ul>"
            return html + "</li>"

        top.sort(key=lambda s: -(s.get("url_count") or 0))
        inventory = ar.get("inventory") or {}
        root = f'<li><span class="path">/</span><span class="cnt">{_esc(inventory.get("total", ""))} URLs</span><ul>'
        tree_html = (f"<h3>Section tree</h3><ul class=\"tree\">{root}{''.join(node(s) for s in top[:12])}</ul></li></ul>")

    rows = []
    if nv:
        prim = nv.get("primary_nav") or {}
        foot = nv.get("footer_nav") or {}
        bc = nv.get("breadcrumbs") or {}
        if nv.get("status") == "not_measured":
            rows.append(("Global navigation", "—", _status_chip("deferred", "Not measured")))
        else:
            rows.append(("Primary navigation links", _esc(prim.get("count", "—")), _status_chip("ok", "Measured")))
            rows.append(("Footer links", _esc(foot.get("count", "—")), _status_chip("ok", "Measured")))
            visible, jsonld = bc.get("with_visible", 0) or 0, bc.get("with_jsonld", 0) or 0
            bc_status = _status_chip("ok", "Match") if visible == jsonld else _status_chip("flag", "Mismatch")
            rows.append(("Breadcrumbs visible / BreadcrumbList", f"{visible} / {jsonld}", bc_status))
    reconcile = sm.get("reconcile") or {}
    if reconcile:
        unlisted = (reconcile.get("crawled_not_in_sitemap") or {}).get("count", 0) or 0
        rows.append(("Indexable pages not in the sitemap", _esc(unlisted),
                     _status_chip("gap" if unlisted > 50 else "flag" if unlisted else "ok", "Gap" if unlisted > 50 else "Needs work" if unlisted else "Strong")))
    if ar:
        eq = ar.get("equity") or {}
        eq_status = "measured" if eq.get("by_section") else "deferred"
        rows.append(("Link equity by section", _esc(eq.get("status", "—")),
                     _status_chip("ok" if eq_status == "measured" else "deferred", "Measured" if eq_status == "measured" else "Withheld")))
    if pt:
        matrix = pt.get("matrix") or {}
        expected = pt.get("expected") or []
        missing = [l for l in expected if not (matrix.get(l) or {}).get("count")]
        src = pt.get("source") or {}
        if expected:
            if src.get("status") != "complete":
                rows.append(("Expected page types missing", "inventory incomplete", _status_chip("deferred", "Withheld")))
            else:
                rows.append(("Expected page types missing", _esc(", ".join(l.replace("_", " ") for l in missing) or "none"),
                             _status_chip("flag" if missing else "ok", "Gap" if missing else "Strong")))
    table_html = ""
    if rows:
        body = "".join(f"<tr><td>{_esc(k)}</td><td class=\"n\">{v}</td><td>{chip}</td></tr>" for k, v, chip in rows)
        table_html = ('<h3>Navigation and sitemap</h3><div class="tw"><table style="min-width:0" aria-label="Navigation and sitemap">'
                      f"<tbody>{body}</tbody></table></div>")
    if tree_html or table_html:
        parts.append(f'<div class="shape-grid"><div>{tree_html}</div><div>{table_html}</div></div>')
    parts.append('<p class="small prose">Full page-type matrix, navigation links and the section table are in the '
                 'appendix under <a href="#check-page_types">Page-type coverage</a>, '
                 '<a href="#check-navigation">Navigation and breadcrumbs</a> and '
                 '<a href="#check-architecture">Site architecture</a>.</p>')
    return "".join(parts)


_GEO_QUICK = (
    ("ai_search_access", "AI search crawlers allowed in robots.txt"),
    ("ai_bot_access", "AI crawlers not refused by the firewall"),
    ("hidden_instructions", "No hidden instructions aimed at AI agents"),
    ("citability", "Answer-first, self-contained passages an assistant can cite"),
    ("entity", "Entity resolvable off-site (Wikidata, sameAs, consistent name)"),
    ("llms_txt", "llms.txt present and consistent (never weighted; Google ignores it)"),
)


def _render_geo(statuses: dict) -> str:
    items = []
    for key, question in _GEO_QUICK:
        status, label = statuses.get(key, ("na", "Not run"))
        css = "ok" if status == "ok" else "no" if status in ("flag", "gap") else "nm"
        mark = "✓" if css == "ok" else "✗" if css == "no" else "–"
        items.append(f'<li class="{css}"><span class="mk">{mark}</span><div>{_esc(question)}'
                     f'<small>{_esc(CHECK_LABELS.get(key, key))} · {_esc(label)} · <a href="#check-{key}">detail</a></small></div></li>')
    return (
        '<div class="sec-head"><span class="sec-n">08</span><h2 id="geo-h">GEO readiness</h2></div>'
        '<p class="prose">Whether AI assistants can reach, read and cite this site. Each line is the status of one check.</p>'
        f'<ul class="qc">{"".join(items)}</ul>'
    )


def _render_platform(data: dict) -> str:
    env = data.get("environment", {}) or {}
    platform = env.get("primary", "Unknown")
    signals = env.get("signals", []) or []
    alternatives = env.get("alternatives", []) or []
    signal_list = "".join(f"<li>{_esc(sig)}</li>" for sig in signals)
    left = (
        _kv([("Platform", _esc(platform)),
             ("Runtime", _esc(env.get("runtime", "Unknown"))),
             ("Confidence", _esc(str(env.get("confidence", "low")).capitalize())),
             ("Signals matched", _esc(len(signals)))])
        + (_subhead("Detection signals") + f'<ul class="recs">{signal_list}</ul>' if signal_list else "")
        + (f'<p class="small">Also possible: {_esc(", ".join(alternatives))}</p>' if alternatives else "")
    )
    plan_title = "Fix plan" if platform == "Unknown" else f"Fix plan for {platform}"
    return (
        '<div class="sec-head"><span class="sec-n">09</span><h2 id="platform-h">Platform</h2></div>'
        '<p class="prose">Inferred from signals in the HTML source. Fixes are phrased for the detected platform.</p>'
        f'<div class="two-col"><div>{left}</div>'
        f'<div>{_subhead(plan_title)}{render_environment_fixes(data.get("environment_fixes", []))}</div></div>'
    )


_ACCENT_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _report_options(options) -> dict:
    options = dict(options or {})
    accent = options.get("accent")
    if accent and not _ACCENT_RE.match(str(accent)):
        raise ValueError(f"accent must be a six-digit hex colour like #0057B7, got {accent!r}")
    return {
        "prepared_for": options.get("prepared_for") or "",
        "prepared_by": options.get("prepared_by") or "ultimate-seo-geo · generate_report.py",
        "accent": accent or "",
    }


def _load_template_asset(name: str, fallback: str) -> str:
    """Read a design-system file from references/report-template/, beside scripts/.

    The plugin bundle ships references/ next to scripts/, so the same relative
    path works installed and in the repo. A missing file is reported and the
    report falls back to the embedded minimum so a run never fails on CSS.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "report-template", name)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        print(f"  ⚠️ {name} not found beside scripts/ ({exc}); using the embedded fallback stylesheet", file=sys.stderr)
        return fallback


def generate_html(data: dict, scores: dict, options=None, previous_summary=None) -> str:
    """Generate the HTML report: the report-set design system, one page, the spine.

    Masthead with coverage bar → verdict and figures → delta since the previous
    run → action plan by lane (who can act) → open questions (what the run could
    not see) → Health Score by category → scope and coverage → site shape →
    findings by kind → GEO readiness → platform → appendix of check details. Every section is in the markup; JavaScript only filters and
    scroll-spies, so print and PDF show everything.
    """
    opts = _report_options(options)
    domain = data["domain"]
    url = data["url"]
    timestamp = data["timestamp"]
    sections = data.get("sections", {})
    env = data.get("environment", {}) or {}
    overall = scores["overall"]
    weights = scores.get("weights", {}) or {}
    issues = _collect_issues(data)
    defects = [i for i in issues if _finding_kind(i) == "defect"]
    counts = {s: sum(1 for i in defects if i["severity"] == s) for s in ("critical", "warning", "info")}
    entries = _check_entries(data, scores)
    statuses = {key: (status, label) for key, label_, status, label, _score in
                ((e[0], e[1], e[2], e[3], e[4]) for e in entries)}
    coverage = _coverage_counts(statuses, weights)
    inventory = _inventory(data)
    gaps = sorted((k for k, (status, _) in statuses.items() if status == "gap"),
                  key=lambda k: (scores.get("categories") or {}).get(k) or 0)[:3]
    ran = sum(1 for value in sections.values() if isinstance(value, dict) and not value.get("error"))

    try:
        generated = datetime.fromisoformat(timestamp)
        date_label = generated.strftime("%Y-%m-%d")
        stamp = generated.strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        date_label = stamp = str(timestamp)

    delta = None
    if previous_summary:
        delta = compare_with_previous(build_summary(data, scores), previous_summary)

    plan = build_action_plan(issues, scores)
    questions = build_open_questions(data, scores, issues)
    lede = (
        f"{len(defects)} findings: {counts['critical']} critical, {counts['warning']} warnings "
        f"and {counts['info']} informational."
    )
    if plan["Auto"]:
        lede += f" An agent can fix {len(plan['Auto'])} of them without sign-off."
    if questions:
        lede += f" {len(questions)} open {'question' if len(questions) == 1 else 'questions'} about what the run could not see."
    if gaps:
        lede += " Weakest checks: " + _join_labels([CHECK_LABELS[k] for k in gaps]) + "."
    if inventory.get("site_type"):
        lede += f" Detected site type: {inventory['site_type']}."

    lead = next((i for i in defects if i["severity"] == "critical"), None) or next(
        (i for i in defects if i["severity"] == "warning"), None)
    # Work an agent can finish alone goes first; the most severe finding is
    # still named when it is someone else's to do.
    first = next((i for i in plan["Auto"] if i["severity"] in ("critical", "warning")), None) or lead
    if first:
        first_label = CHECK_LABELS.get(first["section"], first["section"])
        first_fix = f'<p>{_esc(first["fix"])}</p>' if first["fix"] else ""
        also = ""
        if lead and lead is not first:
            also = (f'<p class="small">Most severe, and not an agent&rsquo;s to fix alone: '
                    f'<span class="ids"><a href="#{lead["id"]}">{lead["id"]}</a></span>'
                    f'{_esc(_headline(lead["finding"], 80))}</p>')
        start = (
            f'<div class="start{" auto" if first.get("lane") == "Auto" else ""}"><span class="label">Start here</span>'
            f'{_lane_chip(first.get("lane"))}'
            f'<h3>{_esc(_headline(first["finding"]))}</h3>{first_fix}'
            f'<p><span class="ids"><a href="#{first["id"]}">{first["id"]}</a>'
            f'<a href="#check-{first["section"]}">{_esc(first_label)}</a></span></p>{also}</div>'
        )
    else:
        start = (
            '<div class="start ok"><span class="label">Start here</span>'
            "<h3>No critical or warning findings.</h3>"
            "<p>Review the informational items and keep running regular reports.</p></div>"
        )

    measured = _measured_count(scores)
    if measured >= MIN_MEASURED_FOR_GATE:
        score_fig = f'<div class="fig nu">{overall}<small>/100</small></div><span class="label">Health Score · grade {_esc(_grade(overall))}</span>'
    else:
        score_fig = '<div class="fig nu">—</div><span class="label">Health Score inconclusive</span>'
    figs = (
        f'<div class="figs" aria-label="Headline figures"><div>{score_fig}</div>'
        f'<div><div class="fig {"dn" if counts["critical"] else ""}">{counts["critical"]}</div><span class="label">Critical findings</span></div>'
        f'<div><div class="fig {"dn" if counts["warning"] else ""}">{counts["warning"]}</div><span class="label">Warning findings</span></div>'
        f'<div><div class="fig">{counts["info"]}</div><span class="label">Informational findings</span></div></div>'
    )

    need_you = len(plan["Human"]) + len(plan["Decision"])
    lane_figs = (
        '<div class="figs lanes" aria-label="Who acts">'
        f'<div><div class="fig {"up" if plan["Auto"] else ""}">{len(plan["Auto"])}</div><a class="label" href="#{"lane-auto" if plan["Auto"] else "plan"}">AI can fix now</a></div>'
        f'<div><div class="fig">{len(plan["Assisted"])}</div><a class="label" href="#{"lane-assisted" if plan["Assisted"] else "plan"}">AI drafts, you approve</a></div>'
        f'<div><div class="fig">{need_you}</div><a class="label" href="#plan">Need a person or a decision</a></div>'
        f'<div><div class="fig">{len(questions)}</div><a class="label" href="#questions">Open questions</a></div></div>'
    )

    meta_rows = []
    if opts["prepared_for"]:
        meta_rows.append(("Prepared for", opts["prepared_for"]))
    meta_rows.append(("Prepared by", opts["prepared_by"]))
    meta_rows.append(("Date", date_label))
    meta_rows.append(("Platform", env.get("primary", "Unknown")))
    meta_rows.append(("Mode", "Internal · automated checks"))
    meta_rows.append(("Site type", inventory.get("site_type") or "not classified"))
    meta_rows.append(("Checks", f"{ran} of {len(sections)} ran"))
    meta_html = "".join(f"<div><dt>{_esc(k)}</dt><dd>{_esc(v)}</dd></div>" for k, v in meta_rows)

    if inventory["measured"] and inventory.get("complete"):
        claim_chip = '<span class="seg ok">Inventory complete · absence claims allowed</span>'
    else:
        claim_chip = '<span class="seg warn">Inventory incomplete · absence claims withheld</span>'
    covbar = (
        '<div class="covbar" aria-label="Coverage summary">'
        f'<span class="seg"><i class="dot w"></i><b>{coverage["weighted"]}</b> checks weighted</span>'
        f'<span class="seg"><i class="dot d"></i><b>{coverage["display"]}</b> shown, not weighted</span>'
        f'<span class="seg"><i class="dot n"></i><b>{coverage["deferred"]}</b> not measured</span>'
        f'<span class="seg"><i class="dot x"></i><b>{coverage["na"]}</b> not applicable or not run</span>'
        f"{claim_chip}</div>"
    )

    accent_css = f":root{{--accent:{opts['accent']}}}" if opts["accent"] else ""
    css = _load_template_asset("report.css", _FALLBACK_CSS) + _REPORT_EXTRA_CSS + accent_css
    print_css = _load_template_asset("print.css", "")

    nav_items = [("verdict", "Verdict"), ("plan", "Action plan"), ("questions", "Open questions"),
                 ("score", "Score"), ("coverage", "Coverage")]
    shape_html = _render_site_shape(data)
    if shape_html:
        nav_items.append(("shape", "Site shape"))
    nav_items += [("findings", "Findings"), ("geo", "GEO readiness"), ("platform", "Platform"), ("appendix", "Appendix")]
    nav_html = "".join(
        f'<a href="#{key}" class="active">{label}</a>' if i == 0 else f'<a href="#{key}">{label}</a>'
        for i, (key, label) in enumerate(nav_items)
    )

    shape_section = f'<section id="shape" aria-labelledby="shape-h">{shape_html}</section>' if shape_html else ""

    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"UTF-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>SEO + GEO report · {_esc(domain)}</title>\n"
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        f'<link rel="stylesheet" href="{_esc(_FONTS_URL)}">\n'
        f"<style>{css}\n{print_css}</style>\n</head>\n<body>\n"
        '<header class="top"><div class="top-in">'
        '<div class="top-row"><p class="eyebrow">SEO + GEO report · automated checks</p>'
        '<button type="button" class="theme-toggle" id="theme-toggle">Theme: system</button></div>'
        f"<h1>{_esc(domain)}</h1>"
        f'<p class="sub">{_esc(lede)}</p>'
        f'<dl class="meta">{meta_html}</dl>{covbar}'
        "</div></header>\n"
        f'<nav class="toc" aria-label="Sections"><div class="toc-in">{nav_html}</div></nav>\n'
        '<main class="shell">\n'
        '<section id="verdict" aria-labelledby="verdict-h">'
        '<div class="sec-head"><span class="sec-n">01</span><h2 id="verdict-h">Verdict</h2></div>'
        f"{figs}{lane_figs}"
        '<div class="two"><div class="verdict">'
        f'<p class="lead">{_esc(lede)}</p>'
        f"<p>Every finding and score on this page comes from scripts run against {_esc(url)}. "
        "Scores are a triage signal; confirm high-risk changes such as redirects, canonicals and robots.txt before acting.</p>"
        f"</div>{start}</div>{_render_delta(delta)}</section>\n"
        f'<section id="plan" aria-labelledby="plan-h">{_render_action_plan(data, scores, issues, delta)}</section>\n'
        f'<section id="questions" aria-labelledby="questions-h">{_render_open_questions(questions)}</section>\n'
        f'<section id="score" aria-labelledby="score-h">{_render_score(data, scores, stamp, statuses)}</section>\n'
        f'<section id="coverage" aria-labelledby="coverage-h">{_render_coverage(data, scores, issues, entries, coverage, inventory)}</section>\n'
        f"{shape_section}\n"
        f'<section id="findings" aria-labelledby="findings-h">{_render_findings(issues)}</section>\n'
        f'<section id="geo" aria-labelledby="geo-h">{_render_geo(statuses)}</section>\n'
        f'<section id="platform" aria-labelledby="platform-h">{_render_platform(data)}</section>\n'
        '<section id="appendix" aria-labelledby="appendix-h">'
        '<div class="sec-head"><span class="sec-n">A</span><h2 id="appendix-h">Appendix · check details</h2></div>'
        '<p class="prose">What each check measured, in full, with every recommendation it returned. '
        'Sorted weakest first, like the coverage table.</p>'
        f'<div class="check-details" id="check-detail">{_render_check_details(data, scores, issues, entries)}</div>'
        "</section>\n"
        "</main>\n"
        f'<footer class="shell"><span class="mono">Generated by ultimate-seo-geo generate_report.py · {_esc(stamp)}</span>'
        f' · Findings and scores come from automated checks against <a href="{_esc(url)}">{_esc(url)}</a>.'
        ' If the links inside this report go nowhere, you are reading it in a preview that blocks scripts: '
        'open the file in a web browser.'
        "</footer>\n"
        f"<script>{_REPORT_JS}</script>\n</body>\n</html>"
    )


# The minimum a report needs when references/report-template/report.css is not
# beside scripts/. Tokens match report.css so the extra CSS below still resolves.
_FALLBACK_CSS = """
:root{--paper:#FFFFFF;--surface:#FFFFFF;--surface-2:#F5F6F8;--ink:#0B0D10;--ink-2:#16191E;--muted:#5B626D;--faint:#838A95;--line:#D7DBE1;--line-strong:#B4BAC3;--accent:#0057B7;--accent-soft:#EEF4FC;--accent-ink:#003C7F;--critical:#A2213A;--critical-soft:#F9E9ED;--warn:#6E4C05;--warn-soft:#FDF6E3;--good:#2F5E18;--good-soft:#E9F1E3;--opp:#FF6A1A;--shadow:none;--r-card:14px;--r-chip:6px;--sans:"Instrument Sans",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Arial,sans-serif;--serif:var(--sans);--mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#0B0D10;--surface:#16191E;--surface-2:#262A31;--ink:#FFFFFF;--ink-2:#EAEDF1;--muted:#838A95;--faint:#5B626D;--line:rgba(255,255,255,.12);--line-strong:rgba(255,255,255,.24);--accent:#7FAAE4;--accent-soft:#0D1B34;--accent-ink:#B0CCF0;--critical:#F08FA2;--critical-soft:#2F141C;--warn:#E5C86A;--warn-soft:#2F2612;--good:#8FCE6E;--good-soft:#182614;--shadow:none;}}
:root[data-theme="dark"]{--paper:#0B0D10;--surface:#16191E;--surface-2:#262A31;--ink:#FFFFFF;--ink-2:#EAEDF1;--muted:#838A95;--faint:#5B626D;--line:rgba(255,255,255,.12);--line-strong:rgba(255,255,255,.24);--accent:#7FAAE4;--accent-soft:#0D1B34;--accent-ink:#B0CCF0;--critical:#F08FA2;--critical-soft:#2F141C;--warn:#E5C86A;--warn-soft:#2F2612;--good:#8FCE6E;--good-soft:#182614;--shadow:none;}
*{box-sizing:border-box}[hidden]{display:none!important}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--serif);font-size:17px;line-height:1.6}
.shell{max-width:1080px;margin:0 auto;padding-inline:20px;padding-block:0 96px}.top-in{max-width:1080px;margin:0 auto;padding-inline:20px;padding-block:40px 30px}
h1,h2,h3,h4,.label,th,.fig,.chip,nav,button,dt{font-family:var(--sans)}
.eyebrow{font-family:var(--mono);color:var(--muted)}
.chip{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;font-weight:600;padding:3px 8px;border-radius:var(--r-chip);display:inline-block}
.chip.c{background:var(--critical-soft);color:var(--critical)}.chip.h{background:var(--warn-soft);color:var(--warn)}.chip.g{background:var(--good-soft);color:var(--good)}.chip.o{background:var(--surface-2);color:var(--muted);border:1px solid var(--line)}
table{border-collapse:collapse;width:100%;font-family:var(--sans);font-size:13.5px}th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:var(--r-card);background:var(--surface);margin:20px 0}
.find{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--muted);border-radius:var(--r-card);padding:18px 20px;margin:0 0 14px}
.find.c{border-left-color:var(--critical)}.find.h{border-left-color:var(--warn)}
.find dl{margin:0;display:grid;grid-template-columns:96px 1fr;gap:5px 16px;font-size:15px}.find dt{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--faint)}.find dd{margin:0}
"""

# Components the generator adds on top of report.css: the coverage bar, the
# score block, the delta strip, the start-here card, filters, site shape, the
# GEO list, check-panel primitives, and the theme toggle.
_REPORT_EXTRA_CSS = """
.top-row{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.top-row .eyebrow{margin:0}
.theme-toggle{display:none;height:30px;padding:0 10px;border-radius:var(--r-chip);border:1px solid var(--line-strong);background:transparent;color:var(--muted);font-family:var(--mono);font-size:12px;cursor:pointer}
.js .theme-toggle{display:inline-block}
.theme-toggle:hover{color:var(--ink)}
section[id]{scroll-margin-top:56px}
.block-h{margin-top:34px}
.covbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:18px 0 0;font-family:var(--sans);font-size:13px;color:var(--muted)}
.covbar .seg{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border:1px solid var(--line);border-radius:var(--r-chip);background:var(--surface)}
.covbar .seg b{font-family:var(--mono);font-weight:500;color:var(--ink);font-variant-numeric:tabular-nums}
.covbar .seg.ok{border-color:var(--good);color:var(--good)}
.covbar .seg.warn{border-color:var(--warn);color:var(--warn)}
.covbar .dot{width:8px;height:8px;border-radius:1px;display:inline-block}
.dot.w{background:var(--accent)} .dot.d{background:var(--accent);opacity:.35} .dot.n{background:transparent;border:1px dashed var(--muted)} .dot.x{background:var(--line-strong)}
.two{display:grid;grid-template-columns:1.4fr 1fr;gap:16px;align-items:start;margin-bottom:22px}
.start{border:1px solid var(--line-strong);border-left:4px solid var(--critical);background:var(--surface);border-radius:var(--r-card);padding:18px 22px;box-shadow:var(--shadow)}
.start.ok{border-left-color:var(--good)}
.start .label{margin-bottom:6px;display:block}
.start h3{margin:0 0 6px}
.start p{margin:0 0 6px;font-size:15.5px;color:var(--ink-2)}
.start p:last-child{margin-bottom:0}
.fig small{font-size:16px;color:var(--muted)}
.start.auto{border-left-color:var(--good)}
.start .chip{margin-bottom:8px}
.figs.lanes{margin-top:-10px}
.figs.lanes a.label{text-decoration:none}
.figs.lanes a.label:hover{color:var(--ink)}
.lane{margin:0 0 26px}
.lane-head{display:flex;align-items:center;gap:10px;margin:22px 0 2px}
.lane-head h3{margin:0}
.plan{list-style:none;padding:0;margin:10px 0 0;display:grid;gap:8px;counter-reset:plan}
.plan-item{border:1px solid var(--line);border-radius:var(--r-card);background:var(--surface);padding:12px 16px;font-family:var(--sans)}
.plan-top{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.plan-top strong{flex:1 1 320px;font-size:15.5px}
.plan-fix{margin:6px 0 0;font-size:14.5px;color:var(--ink-2)}
.plan-item .small{margin:4px 0 0}
.plan-meta{margin:8px 0 0;display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.fix-prompt{margin:14px 0 0;border:1px solid var(--line);border-radius:var(--r-card);background:var(--surface);padding:12px 16px}
.fix-prompt summary{font-family:var(--sans);font-weight:600;font-size:14.5px;cursor:pointer}
.fix-prompt pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:10px 0}
.copy-btn{display:none;font:inherit;font-family:var(--sans);font-size:12.5px;font-weight:500;padding:6px 12px;border:1px solid var(--accent);border-radius:var(--r-chip);background:var(--accent-soft);color:var(--accent-ink);cursor:pointer}
.js .copy-btn{display:inline-block}
table.questions small{display:block;color:var(--muted);margin-top:3px}
.score{display:grid;grid-template-columns:220px 1fr;gap:20px 28px;border:1px solid var(--line);border-radius:var(--r-card);background:var(--surface);padding:24px 26px;margin:0 0 22px}
.score-n{font-family:var(--sans);font-size:64px;line-height:1;font-weight:700;letter-spacing:-.04em;font-variant-numeric:tabular-nums}
.score-n small{font-size:22px;color:var(--muted);font-weight:500;letter-spacing:0}
.score-n.ns{font-size:30px;line-height:1.1;color:var(--muted);letter-spacing:-.02em}
.score-src{font-family:var(--mono);font-size:12px;color:var(--muted);margin:0;line-height:1.5;grid-column:1}
.bars{display:grid;grid-template-columns:200px 1fr 46px 110px;gap:6px 14px;align-items:center;font-family:var(--sans);font-size:13.5px;grid-column:2;grid-row:1/3}
.bars .lbl{color:var(--ink-2)}
.bars .lbl small{display:block;font-family:var(--mono);font-size:11px;color:var(--faint)}
.bars .track{height:10px;background:var(--surface-2);border-radius:var(--r-chip);position:relative;overflow:hidden}
.bars .track.nm{background:repeating-linear-gradient(135deg,transparent 0 4px,var(--line) 4px 6px);border:1px dashed var(--line-strong)}
.bars .track i{position:absolute;inset:0 auto 0 0;background:var(--accent);border-radius:2px 4px 4px 2px;display:block}
.bars .val{font-family:var(--mono);font-size:12.5px;text-align:right;font-variant-numeric:tabular-nums;color:var(--ink)}
.bars .val.nm{color:var(--faint)}
.delta{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);border-radius:var(--r-card);background:var(--surface);margin:0 0 22px;overflow:hidden}
.delta>div{padding:14px 18px;border-right:1px solid var(--line)}
.delta>div:last-child{border-right:0}
.delta b{display:block;font-family:var(--sans);font-size:22px;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.delta span{display:block;font-family:var(--sans);font-size:12.5px;color:var(--muted);margin-top:2px}
.delta .ids{margin-top:6px}
.filters{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 16px;font-family:var(--sans)}
.filters button{font:inherit;font-size:12.5px;font-weight:500;padding:5px 11px;border:1px solid var(--line-strong);border-radius:var(--r-chip);background:var(--surface);color:var(--ink-2);cursor:pointer}
.filters button[aria-pressed="true"]{background:var(--accent-soft);border-color:var(--accent);color:var(--accent-ink)}
.filters button b{font-family:var(--mono);font-weight:500;margin-left:4px;color:var(--muted)}
.funnel{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin:14px 0 20px}
.funnel>div{border:1px solid var(--line);border-radius:var(--r-card);background:var(--surface);padding:12px 14px}
.funnel b{display:block;font-family:var(--sans);font-size:22px;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.funnel span{display:block;font-family:var(--sans);font-size:11.5px;color:var(--muted);letter-spacing:.08em;text-transform:uppercase;font-weight:600;margin-bottom:4px}
.funnel small{display:block;font-family:var(--sans);font-size:12px;color:var(--muted)}
.funnel .gap b{color:var(--critical)}
.shape-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.tree .chip{font-size:9.5px}
.qc{list-style:none;padding:0;margin:14px 0;display:grid;gap:8px;font-family:var(--sans);font-size:14.5px}
.qc li{display:grid;grid-template-columns:22px 1fr;gap:12px;align-items:start;padding:10px 14px;border:1px solid var(--line);border-radius:var(--r-card);background:var(--surface)}
.qc .mk{font-family:var(--mono);font-size:13px;font-weight:600;text-align:center}
.qc .ok .mk{color:var(--good)} .qc .no .mk{color:var(--critical)} .qc .nm .mk{color:var(--faint)}
.qc small{display:block;color:var(--muted);margin-top:2px}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.kv{margin:0 0 14px;display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px 18px;font-family:var(--sans);font-size:14px}
.kv div{border-top:1px solid var(--line);padding-top:6px}
.kv dt{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--faint);font-weight:600}
.kv dd{margin:2px 0 0;color:var(--ink-2);overflow-wrap:anywhere}
.callout{margin:14px 0}
.callout b{font-family:var(--sans)}
.subhead{font-size:14px;margin:18px 0 6px}
.issues,.recs{padding-left:20px;margin:0 0 12px;font-family:var(--sans);font-size:14.5px}
.issues{list-style:none;padding-left:0}
.issue{border:1px solid var(--line);border-radius:var(--r-card);background:var(--surface);padding:10px 14px;margin:0 0 8px}
.issue-head{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.issue-fix,.issue-reason{margin:4px 0 0;font-size:14px;color:var(--ink-2)}
.issue-fix .lbl{font-family:var(--sans);font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--faint);font-weight:600;margin-right:6px}
.fmeta{margin:6px 0 0;display:grid;gap:2px;font-size:13px;line-height:1.5;color:var(--muted);font-family:var(--sans)}
.fmeta>div{display:flex;flex-wrap:wrap;gap:0 6px}
.fmeta dt{font-weight:600;color:var(--ink-2)}
.fmeta dd{margin:0}
.rec-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.rec-group{border:1px solid var(--line);border-radius:var(--r-card);background:var(--surface);padding:12px 16px}
.rec-group .subhead{margin-top:0}
.check-details{display:grid;gap:14px}
.card.detail{border:1px solid var(--line);border-radius:var(--r-card);background:var(--surface);padding:18px 22px}
.card-top{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:6px;font-family:var(--sans);font-size:13px;color:var(--muted)}
.panel-body{font-size:15px}
.panel-body .tw{margin:12px 0}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;font-family:var(--mono);font-size:12.5px;white-space:nowrap}
td.url{font-family:var(--mono);font-size:12.5px;overflow-wrap:anywhere}
.yes{color:var(--good);font-weight:600}.no{color:var(--critical);font-weight:600}.muted{color:var(--muted)}
.meter{display:inline-block;height:8px;width:120px;background:var(--surface-2);border-radius:var(--r-chip);vertical-align:middle;overflow:hidden;margin-left:8px}
.meter span{display:block;height:100%;background:var(--accent)}
.meter.wide{width:220px}
footer.shell{margin-top:60px;padding-top:22px;padding-bottom:40px;border-top:1px solid var(--line-strong);font-size:13px;color:var(--faint);font-family:var(--sans)}
@media (max-width:820px){
  .score{grid-template-columns:1fr}
  .score-src,.bars{grid-column:auto;grid-row:auto}
  .bars{grid-template-columns:1fr 60px}
  .bars .lbl{grid-column:1/-1}
  .bars .chip{display:none}
  .two,.shape-grid,.two-col,.rec-grid{grid-template-columns:1fr}
  .funnel{grid-template-columns:repeat(3,1fr)}
  .delta{grid-template-columns:1fr 1fr}
  .delta>div{border-bottom:1px solid var(--line)}
  .delta>div:nth-child(2n){border-right:0}
}
@media print{.theme-toggle,.filters,.copy-btn{display:none}}
"""

_REPORT_JS = """
(function () {
  var root = document.documentElement;
  root.classList.add('js');

  var THEME_KEY = 'ultimate-seo-geo-report-theme';
  var toggle = document.getElementById('theme-toggle');
  function applyTheme(theme) {
    if (theme === 'light' || theme === 'dark') root.setAttribute('data-theme', theme);
    else root.removeAttribute('data-theme');
    if (toggle) toggle.textContent = 'Theme: ' + (theme || 'system');
  }
  var saved = null;
  try { saved = localStorage.getItem(THEME_KEY); } catch (e) { saved = null; }
  applyTheme(saved);
  if (toggle) {
    toggle.addEventListener('click', function () {
      var current = root.getAttribute('data-theme');
      var next = current === null ? 'light' : current === 'light' ? 'dark' : null;
      try {
        if (next) localStorage.setItem(THEME_KEY, next);
        else localStorage.removeItem(THEME_KEY);
      } catch (e) { /* storage unavailable: the choice lasts for this page view */ }
      applyTheme(next);
    });
  }

  var filterEl = document.getElementById('finding-filter');
  var applyFilter = null;
  if (filterEl) {
    var buttons = Array.prototype.slice.call(filterEl.querySelectorAll('button[data-filter]'));
    var targets = Array.prototype.slice.call(document.querySelectorAll('#finding-rows tr[data-filter], #finding-cards article[data-filter]'));
    applyFilter = function (value) {
      buttons.forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-filter') === value ? 'true' : 'false'); });
      targets.forEach(function (t) { t.hidden = !(value === 'all' || t.getAttribute('data-filter') === value); });
    };
    filterEl.addEventListener('click', function (e) {
      var button = e.target.closest('button[data-filter]');
      if (button) applyFilter(button.getAttribute('data-filter'));
    });
  }

  var copyBtn = document.getElementById('fix-prompt-copy');
  if (copyBtn && navigator.clipboard) {
    copyBtn.addEventListener('click', function () {
      var source = document.getElementById(copyBtn.getAttribute('data-copy'));
      if (!source) return;
      navigator.clipboard.writeText(source.textContent).then(function () {
        copyBtn.textContent = 'Copied';
        setTimeout(function () { copyBtn.textContent = 'Copy fix prompt'; }, 1800);
      }, function () { copyBtn.textContent = 'Copy failed: select the text above'; });
    });
  } else if (copyBtn) {
    copyBtn.hidden = true;
  }

  // In-page links scroll by script. File previews in chat and IDE apps embed
  // the report as an iframe srcdoc, whose base URL is the host page's: a plain
  // fragment link there resolves to the host's URL and navigates the frame away.
  // Where the host also blocks scripts nothing on the page can help; the footer
  // says to open the file in a browser.
  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest('a[href^="#"]');
    if (!a) return;
    var id = decodeURIComponent(a.getAttribute('href').slice(1));
    var target = id && document.getElementById(id);
    if (!target) return;
    e.preventDefault();
    // A finding the severity filter hid has no box to scroll to: show all first.
    if (applyFilter && target.closest('[hidden]')) applyFilter('all');
    target.scrollIntoView({ block: 'start' });
    if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
    target.focus({ preventScroll: true });
    try { history.replaceState(null, '', '#' + id); } catch (err) { /* srcdoc or sandboxed frame: no history entry */ }
  });

  var links = Array.prototype.slice.call(document.querySelectorAll('nav.toc a'));
  var sections = links.map(function (a) { return document.querySelector(a.getAttribute('href')); }).filter(Boolean);
  if ('IntersectionObserver' in window && sections.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        links.forEach(function (a) { a.classList.toggle('active', a.getAttribute('href') === '#' + entry.target.id); });
      });
    }, { rootMargin: '-40% 0px -55% 0px' });
    sections.forEach(function (s) { io.observe(s); });
  }
})();
"""


def export_xlsx(data: dict, scores: dict, output_path: str) -> str:
    """Export report data to an Excel workbook. Returns the output path."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        print("⚠️  openpyxl not installed. Install with: pip install openpyxl>=3.1.0",
              file=sys.stderr)
        return ""

    wb = Workbook()
    header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        bottom=Side(style="thin", color="D0D5DD"),
    )

    def _write_header(ws, headers: list):
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

    def _auto_width(ws):
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                val = str(cell.value or "")
                max_len = max(max_len, min(len(val), 60))
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # --- Sheet 1: Summary ---
    ws = wb.active
    ws.title = "Summary"
    _write_header(ws, ["Metric", "Value"])
    summary_rows = [
        ("URL", data.get("url", "")),
        ("Domain", data.get("domain", "")),
        ("Report Date", data.get("timestamp", "")),
        ("Overall Score", f"{scores['overall']}/100"),
        ("Platform Detected", data.get("environment", {}).get("primary", "Unknown")),
        ("Runtime", data.get("environment", {}).get("runtime", "Unknown")),
        ("", ""),
        ("— Category Scores —", ""),
    ]
    category_labels = {
        "security": "Security Headers", "social": "Social Meta",
        "robots": "Robots.txt crawl rules", "ai_search_access": "AI Search Crawler Access",
        "broken_links": "Broken Links",
        "internal_links": "Internal Links", "redirects": "Redirects",
        "llms_txt": "AI Search (llms.txt)", "pagespeed": "Performance (CWV)",
        "onpage": "On-Page SEO", "readability": "Readability",
        "entity": "Entity SEO", "link_profile": "Link Profile",
        "hreflang": "Hreflang", "duplicate_content": "Content Uniqueness",
        "schema_validation": "JSON-LD", "image_seo": "Image SEO",
        "sitemap": "Sitemaps", "canonical": "Canonical Tags",
        "local_signals": "Local Signals", "indexnow_probe": "IndexNow",
    }
    for key, label in category_labels.items():
        val = scores["categories"].get(key, 0)
        weight = scores["weights"].get(key, 0)
        summary_rows.append((label, f"{val}/100 (weight: {weight}%)"))

    for r, (metric, value) in enumerate(summary_rows, 2):
        ws.cell(row=r, column=1, value=metric).border = thin_border
        ws.cell(row=r, column=2, value=str(value)).border = thin_border
    _auto_width(ws)

    # --- Sheet 2: Issues ---
    ws2 = wb.create_sheet("Issues")
    _write_header(ws2, ["Severity", "Section", "Finding", "Fix"])
    row = 2
    for section_name, section_data in data["sections"].items():
        for issue in section_data.get("issues", []):
            if isinstance(issue, dict):
                ws2.cell(row=row, column=1, value=issue.get("severity", "info").upper()).border = thin_border
                ws2.cell(row=row, column=2, value=section_name).border = thin_border
                ws2.cell(row=row, column=3, value=issue.get("finding", "")).border = thin_border
                ws2.cell(row=row, column=4, value=issue.get("fix", "")).border = thin_border
                row += 1
            elif isinstance(issue, str):
                ws2.cell(row=row, column=1, value="INFO").border = thin_border
                ws2.cell(row=row, column=2, value=section_name).border = thin_border
                ws2.cell(row=row, column=3, value=issue).border = thin_border
                row += 1
    for fix_item in data.get("environment_fixes", []):
        ws2.cell(row=row, column=1, value=fix_item.get("severity", "info").upper()).border = thin_border
        ws2.cell(row=row, column=2, value="environment").border = thin_border
        ws2.cell(row=row, column=3, value=fix_item.get("title", "")).border = thin_border
        ws2.cell(row=row, column=4, value=fix_item.get("fix", "")).border = thin_border
        row += 1
    _auto_width(ws2)

    # --- Sheet: Action plan (who acts, in order) and open questions ---
    collected = _collect_issues(data)
    ws_plan = wb.create_sheet("Action plan", 1)
    _write_header(ws_plan, ["Order", "Lane", "ID", "Severity", "Check", "Finding", "Fix", "Why this lane"])
    row = 2
    for lane, items in build_action_plan(collected, scores).items():
        for issue in items:
            values = [row - 1, LANE_TITLES[lane], issue["id"], issue["canonical_severity"].upper(),
                      CHECK_LABELS.get(issue["section"], issue["section"]), issue["finding"], issue.get("fix", ""),
                      issue.get("lane_reason", "")]
            for col, value in enumerate(values, 1):
                ws_plan.cell(row=row, column=col, value=value).border = thin_border
            row += 1
    _auto_width(ws_plan)

    ws_q = wb.create_sheet("Open questions", 2)
    _write_header(ws_q, ["ID", "Check", "What is not known", "Why", "What closes it", "Unlocks"])
    for row, q in enumerate(build_open_questions(data, scores, collected), 2):
        values = [q["id"], CHECK_LABELS.get(q["check"], q["check"]), q["question"], q.get("why") or "",
                  q.get("close") or "", q.get("unlocks") or ""]
        for col, value in enumerate(values, 1):
            ws_q.cell(row=row, column=col, value=value).border = thin_border
    _auto_width(ws_q)

    # --- Sheet 3: Links ---
    ws3 = wb.create_sheet("Links")
    _write_header(ws3, ["Type", "Status", "URL", "Anchor Text", "Internal?"])
    row = 2
    bl = data["sections"].get("broken_links", {})
    for link in bl.get("broken", []):
        ws3.cell(row=row, column=1, value="Broken").border = thin_border
        ws3.cell(row=row, column=2, value=str(link.get("status", link.get("error", "?")))).border = thin_border
        ws3.cell(row=row, column=3, value=link.get("url", "")).border = thin_border
        ws3.cell(row=row, column=4, value=link.get("anchor_text", "")).border = thin_border
        ws3.cell(row=row, column=5, value="Yes" if link.get("is_internal") else "No").border = thin_border
        row += 1
    _auto_width(ws3)

    # --- Sheet 4: Technical ---
    ws4 = wb.create_sheet("Technical")
    _write_header(ws4, ["Check", "Status", "Detail"])
    row = 2
    sec = data["sections"].get("security", {})
    for header, value in sec.get("headers_present", {}).items():
        ws4.cell(row=row, column=1, value=header).border = thin_border
        ws4.cell(row=row, column=2, value="Present").border = thin_border
        ws4.cell(row=row, column=3, value=str(value)[:200]).border = thin_border
        row += 1
    for header, desc in sec.get("headers_missing", {}).items():
        ws4.cell(row=row, column=1, value=header).border = thin_border
        ws4.cell(row=row, column=2, value="Missing").border = thin_border
        ws4.cell(row=row, column=3, value=desc).border = thin_border
        row += 1
    rob = data["sections"].get("robots", {})
    for crawler, status in rob.get("ai_crawler_status", {}).items():
        ws4.cell(row=row, column=1, value=f"AI Crawler: {crawler}").border = thin_border
        ws4.cell(row=row, column=2, value="Blocked" if "blocked" in status else "Managed" if "not managed" not in status else "Unmanaged").border = thin_border
        ws4.cell(row=row, column=3, value=status).border = thin_border
        row += 1
    psi = data["sections"].get("pagespeed", {})
    if psi and not psi.get("error"):
        for metric in ["LCP", "INP", "CLS", "TBT", "FCP", "SI"]:
            val = psi.get("field_data", psi.get("lab_data", {})).get(metric)
            if val is not None:
                ws4.cell(row=row, column=1, value=f"CWV: {metric}").border = thin_border
                ws4.cell(row=row, column=2, value="Measured").border = thin_border
                ws4.cell(row=row, column=3, value=str(val)).border = thin_border
                row += 1
    _auto_width(ws4)

    if not output_path.endswith(".xlsx"):
        output_path += ".xlsx"
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    wb.save(output_path)
    return output_path


def export_pdf(html: str, output_path: str) -> Optional[str]:
    """Render HTML report to PDF using WeasyPrint (optional dependency)."""
    try:
        from weasyprint import HTML
    except ImportError:
        print(
            "\n❌ PDF export requires WeasyPrint:\n"
            "     pip install weasyprint\n"
            "   System libraries: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation\n"
            "   Or use --format html and Print → Save as PDF in your browser.\n",
            file=sys.stderr,
        )
        return None

    if not output_path.endswith(".pdf"):
        output_path += ".pdf"
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    try:
        HTML(string=html, base_url=os.getcwd()).write_pdf(output_path)
    except Exception as e:
        print(
            f"\n❌ WeasyPrint could not build PDF ({e}).\n"
            "   Try --format html and use the browser Print dialog → Save as PDF.\n",
            file=sys.stderr,
        )
        return None
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Generate interactive SEO report (HTML/XLSX/PDF)")
    parser.add_argument("url", help="Website URL to analyze")
    parser.add_argument("--output", "-o", help="Output filename (default: seo-report-<domain>.<ext>)")
    parser.add_argument(
        "--format", "-f", dest="fmt", default="html",
        choices=["html", "xlsx", "pdf", "all", "none"],
        help="Output format: html (default), xlsx (Excel), pdf (WeasyPrint), all (HTML + XLSX), "
             "none (no report file; use with --json in CI)",
    )
    parser.add_argument(
        "--crawl-deep",
        action="store_true",
        help="Multi-page crawl for broken_links + canonical_checker (capped; slower, more server load)",
    )
    parser.add_argument(
        "--crawl-max-pages",
        type=int,
        default=30,
        metavar="N",
        help="With --crawl-deep: max pages per crawl (default: 30)",
    )
    parser.add_argument(
        "--crawl-depth",
        type=int,
        default=2,
        metavar="D",
        help="With --crawl-deep: BFS depth (default: 2)",
    )
    parser.add_argument(
        "--render",
        choices=["never", "auto", "always"],
        default="never",
        help="Render the main page HTML with Playwright before page-level checks",
    )
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="Write a machine-readable summary (schema_version 2) to PATH; - writes it to stdout "
             "and sends progress to stderr",
    )
    parser.add_argument(
        "--fail-under",
        type=int,
        metavar="N",
        help="Exit 1 when the overall score is below N (0-100). Exit 3 when fewer than "
             f"{MIN_MEASURED_FOR_GATE} weighted checks were measured",
    )
    parser.add_argument(
        "--fail-on",
        choices=["critical", "warning"],
        help="Exit 1 when any finding is at or above this severity",
    )
    parser.add_argument(
        "--github-annotations",
        action="store_true",
        help="Print GitHub Actions ::error / ::warning annotations for critical and warning findings",
    )
    parser.add_argument(
        "--previous",
        metavar="PATH",
        help="An earlier --json summary of the same site; the report opens with what changed since it "
             "and the JSON summary carries the comparison under \"previous\"",
    )
    parser.add_argument(
        "--gsc-property",
        metavar="PROPERTY",
        help='Search Console property ("sc-domain:example.com" or "https://example.com/"). Runs gsc_insights.py '
             "as a display-only check and joins its page clicks to every finding (needs Tier 1 credentials)",
    )
    parser.add_argument(
        "--gsc-pages",
        metavar="PATH",
        help="Page clicks to join to findings without API access: a Search Console Pages CSV export, "
             "gsc_insights.py --json or --save-rows output, or gsc_query.py --dimension page --json output",
    )
    parser.add_argument("--prepared-for", metavar="NAME", help="Shown in the report masthead")
    parser.add_argument("--prepared-by", metavar="NAME", help="Shown in the report masthead (default: the skill)")
    parser.add_argument("--accent", metavar="#RRGGBB", help="Accent colour for the report (white-label); default teal")

    args = parser.parse_args()
    if args.accent and not _ACCENT_RE.match(args.accent):
        parser.error("--accent must be a six-digit hex colour like #0057B7")
    previous_summary = None
    if args.previous:
        try:
            with open(args.previous, "r", encoding="utf-8") as fh:
                previous_summary = json.load(fh)
        except (OSError, ValueError) as exc:
            parser.error(f"--previous: cannot read {args.previous}: {exc}")
        if not isinstance(previous_summary, dict) or "findings" not in previous_summary:
            parser.error(f"--previous: {args.previous} is not a generate_report.py --json summary")
    page_traffic = None
    if args.gsc_pages:
        try:
            page_traffic = load_page_traffic(args.gsc_pages)
        except (OSError, ValueError) as exc:
            parser.error(f"--gsc-pages: cannot read {args.gsc_pages}: {exc}")
        if not page_traffic["pages"]:
            parser.error(f"--gsc-pages: {args.gsc_pages} has no page rows")
    report_options = {"prepared_for": args.prepared_for, "prepared_by": args.prepared_by, "accent": args.accent}
    if args.fail_under is not None and not 0 <= args.fail_under <= 100:
        parser.error("--fail-under must be between 0 and 100")
    if args.json == "-" and args.github_annotations:
        parser.error("--json - and --github-annotations both write to stdout; write the JSON to a file")
    domain = urlparse(args.url).netloc.replace(".", "_")
    real_stdout = sys.stdout
    if args.json == "-":
        sys.stdout = sys.stderr

    data = collect_data(
        args.url,
        crawl_deep=args.crawl_deep,
        crawl_max_pages=max(1, args.crawl_max_pages),
        crawl_depth=max(1, args.crawl_depth),
        render=args.render,
        gsc_property=args.gsc_property,
    )
    if page_traffic:
        # An explicit file wins over the property's own page totals.
        data["gsc_traffic"] = traffic_from_pages(page_traffic["pages"], page_traffic["source"], page_traffic["window"])
    scores = calculate_overall_score(data)
    summary = build_summary(data, scores)
    if previous_summary:
        apply_previous(summary, previous_summary)

    formats = [] if args.fmt == "none" else ["html", "xlsx"] if args.fmt == "all" else [args.fmt]

    html_cache = None
    for fmt in formats:
        if fmt == "html":
            html_cache = generate_html(data, scores, report_options, previous_summary)
            if args.output and args.fmt != "all":
                out = args.output
            elif args.output and args.fmt == "all":
                out = f"{args.output}.html"
            else:
                out = f"seo-report-{domain}.html"
            out_dir = os.path.dirname(out)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                f.write(html_cache)
            print(f"\n✅ HTML report saved to: {os.path.abspath(out)}")

        elif fmt == "xlsx":
            if args.output and args.fmt != "all":
                out = args.output
            elif args.output and args.fmt == "all":
                out = f"{args.output}.xlsx"
            else:
                out = f"seo-report-{domain}.xlsx"
            result = export_xlsx(data, scores, out)
            if result:
                print(f"✅ Excel report saved to: {os.path.abspath(result)}")

        elif fmt == "pdf":
            if html_cache is None:
                html_cache = generate_html(data, scores, report_options, previous_summary)
            if args.output:
                out = args.output
            else:
                out = f"seo-report-{domain}.pdf"
            result = export_pdf(html_cache, out)
            if result:
                print(f"✅ PDF report saved to: {os.path.abspath(result)}")

    print(f"   Overall Score: {scores['overall']}/100")
    if scores.get("unmeasured"):
        print(f"   Unmeasured (left out of the score): {', '.join(scores['unmeasured'])}")

    gate = evaluate_gate(summary, args.fail_under, args.fail_on)
    summary["gate"] = {"fail_under": args.fail_under, "fail_on": args.fail_on, **gate}
    if gate["result"] != "not set":
        print(f"   Gate: {gate['result']}")
        for reason in gate["reasons"]:
            print(f"     - {reason}")

    sys.stdout = real_stdout
    if args.json:
        text = json.dumps(summary, indent=2, ensure_ascii=False)
        if args.json == "-":
            print(text)
        else:
            out_dir = os.path.dirname(args.json)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            with open(args.json, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            print(f"✅ JSON summary saved to: {os.path.abspath(args.json)}")
    if args.github_annotations:
        for line in github_annotations(summary):
            print(line)
    if gate["exit_code"]:
        sys.exit(gate["exit_code"])


if __name__ == "__main__":
    main()
