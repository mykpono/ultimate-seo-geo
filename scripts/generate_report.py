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

from fetch_page import fetch_page as fetch_url
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


def fetch_page(url: str, render: str = "never") -> str:
    """Fetch page HTML to a temp file, return path."""
    fetched = fetch_url(url, timeout=20, render=render)
    if fetched.get("error") or not fetched.get("content"):
        return ""
    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
    tmp.write(fetched["content"])
    tmp.close()
    return tmp.name


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
) -> dict:
    """Run all analysis scripts and collect results."""
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
    html_path = fetch_page(url, render=render)
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
        ("internal_links", "internal_links.py", [url, "--depth", "1", "--max-pages", "15"]),
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
            if crawl_deep and name in ("broken_links", "canonical")
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

    # Internal links score (penalize broken/soft-404/redirect pages)
    il = data["sections"].get("internal_links", {})
    il_issues = len(il.get("issues", []))
    il_broken_pages = len(il.get("broken_internal_pages", []))
    il_soft_404_pages = len(il.get("soft_404_pages", []))
    il_redirected_pages = len(il.get("redirected_pages", []))
    il_penalty = (il_issues * 10 + il_broken_pages * 15
                  + il_soft_404_pages * 10 + il_redirected_pages * 5)
    scores["internal_links"] = max(0, 100 - il_penalty)

    # Redirects score
    red = data["sections"].get("redirects", {})
    red_issues = len(red.get("issues", []))
    scores["redirects"] = max(0, 100 - red_issues * 25)

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
        issues_count = len(ent.get("issues", []))
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
}
# Structure checks report findings but carry no score: shown, never weighted.
DISPLAY_ONLY_CHECKS = ("page_types", "navigation", "architecture")
CONFIDENCE_LABELS = ("Confirmed", "Likely", "Hypothesis")


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
}

_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2, "pass": 3}
_SEVERITY_LABEL = {"critical": "Critical", "warning": "Warning", "info": "Info", "pass": "Pass"}
_SEVERITY_CHIP = {"critical": "sev-critical", "warning": "sev-warning", "info": "sev-info", "pass": "chip-ok"}
_STATUS_RANK = {"gap": 0, "flag": 1, "ok": 2, "deferred": 3, "na": 4}

# Scripts prefix string issues with status emoji. Severity is read from them
# first; they are then stripped, because the design system carries state in
# chips and markers and allows no emoji on any surface.
_EMOJI_PREFIX = re.compile("^\\s*(?:[\U0001F300-\U0001FAFF☀-➿ℹ⭐]️?\\s*)+")

_FONTS_URL = (
    "https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400..700;1,400..700"
    "&family=JetBrains+Mono:wght@400;500;700&display=swap"
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
    if status == "deferred":
        return f'<span class="mark m-deferred">⏸︎<small>{_esc(label)}</small></span>'
    kind = {"ok": "chip-ok", "flag": "chip-flag", "gap": "chip-gap"}.get(status, "chip-na")
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
        f'<div class="table-scroll"><table class="tbl"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def _notice(body_html: str, tone: str = "empty", lead: str = "") -> str:
    lead_html = f"<b>{_esc(lead)}</b> " if lead else ""
    return f'<p class="notice {tone}">{lead_html}{body_html}</p>'


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
    return '<dl class="meta">' + "".join(parts) + "</dl>"


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
                meta = _render_issue_metadata(_recommendation_metadata(issue, "section"))
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
    return issues


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
        if not isinstance(section, dict) or not section:
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
        sec_rows = [
            f"<tr><td class=\"url\">{_esc(sct.get('path', ''))}</td><td class=\"num\">{_esc(sct.get('url_count', 0))}</td>"
            f"<td>{_esc(sct.get('dominant_label', ''))}</td><td>{_yes_no(sct.get('in_nav'))}</td><td>{_yes_no((sct.get('hub') or {}).get('exists'))}</td>"
            f"<td class=\"num\">{_esc(sct.get('avg_depth') if sct.get('avg_depth') is not None else '—')}</td>"
            f"<td class=\"num\">{_esc(f"{sct['equity_share']:.0%}" if sct.get('equity_share') is not None else '—')}</td></tr>"
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

    return panels


_STEPPER = (
    '<span class="stepper"><button type="button" data-step="-1">Previous</button>'
    '<button type="button" data-step="1">Next</button></span>'
)


def _render_findings(issues: list) -> str:
    counts = {s: sum(1 for i in issues if i["severity"] == s) for s in ("critical", "warning", "info")}
    head = (
        '<div class="section-head"><h2 id="findings-h">Findings</h2>'
        f'<span class="mono note">{len(issues)} · {counts["critical"]} critical · '
        f'{counts["warning"]} warning · {counts["info"]} info</span>'
    )
    if not issues:
        return head + "</div>" + _notice("No findings. Every check came back without an issue.")

    filters = "".join(
        f'<button type="button" data-filter="{key}" aria-pressed="{"true" if key == "all" else "false"}">'
        f'{label} <span class="mono">{count}</span></button>'
        for key, label, count in (
            ("all", "All", len(issues)),
            ("critical", "Critical", counts["critical"]),
            ("warning", "Warning", counts["warning"]),
            ("info", "Info", counts["info"]),
        )
    )
    head += f'<div class="filter" id="finding-filter" role="group" aria-label="Filter by severity">{filters}</div></div>'

    rows, cards = [], []
    for issue in issues:
        fid = issue["id"]
        severity = issue["severity"]
        section = issue["section"]
        label = CHECK_LABELS.get(section, section.replace("_", " ").capitalize())
        headline = _headline(issue["finding"] or issue["text"])
        id_class = "id hi" if severity == "critical" else "id"
        rows.append(
            f'<tr data-key="{fid}" data-filter="{severity}" aria-selected="false">'
            f'<td class="{id_class}">{fid}</td>'
            f'<td><button type="button" class="row-title" aria-controls="finding-detail">{_esc(headline)}</button></td>'
            f"<td>{_severity_chip(severity)}</td>"
            f'<td class="small col-check">{_esc(label)}</td></tr>'
        )
        finding_field = ""
        if issue["finding"] and issue["finding"] != headline:
            finding_field = f'<div class="field"><p class="lbl">Finding</p><p>{_esc(issue["finding"])}</p></div>'
        fix_field = f'<div class="field"><p class="lbl">Fix</p><p>{_esc(issue["fix"])}</p></div>' if issue["fix"] else ""
        check_link = (
            f'<a class="mono" href="#check-{section}" data-open-check="{section}">Open the {_esc(label)} check</a>'
            if section in CHECK_LABELS else f'<span class="mono">{_esc(label)}</span>'
        )
        cards.append(
            f'<article class="card detail" data-key="{fid}" id="{fid}" aria-labelledby="{fid}-title">'
            '<div class="card-body">'
            f'<div class="card-top"><span class="id">{fid}</span>{_severity_chip(severity)}<span class="lbl">{_esc(label)}</span></div>'
            f'<h3 id="{fid}-title">{_esc(headline)}</h3>'
            f"{finding_field}{fix_field}{_render_issue_metadata(issue)}"
            "</div>"
            f'<div class="card-foot">{check_link}{_STEPPER}</div>'
            "</article>"
        )
    return (
        head
        + '<div class="ledger-grid"><div class="panel"><div class="table-scroll">'
        '<table class="ledger" aria-label="Findings"><thead><tr>'
        '<th class="lbl" scope="col" style="width:52px">ID</th>'
        '<th class="lbl" scope="col">Finding</th>'
        '<th class="lbl" scope="col" style="width:108px">Severity</th>'
        '<th class="lbl col-check" scope="col" style="width:170px">Check</th>'
        f'</tr></thead><tbody id="finding-rows">{"".join(rows)}</tbody></table></div>'
        '<p class="legend">Arrow keys move through the list.</p></div>'
        f'<aside class="detail-stack" id="finding-detail" aria-live="polite">{"".join(cards)}</aside></div>'
    )


def _render_checks(data: dict, scores: dict, issues: list) -> str:
    categories = scores.get("categories", {})
    weights = scores.get("weights", {})
    panels = _check_panels(data)
    finding_counts = {}
    for issue in issues:
        finding_counts[issue["section"]] = finding_counts.get(issue["section"], 0) + 1

    entries = []
    for key, label in CHECK_LABELS.items():
        section = _source_section(data["sections"], key)
        section = section if isinstance(section, dict) else {}
        status, status_label = _check_status(key, section, categories.get(key))
        entries.append((key, label, status, status_label, categories.get(key) or 0))
    entries.sort(key=lambda e: (_STATUS_RANK[e[2]], e[4]))

    rows, cards = [], []
    for key, label, status, status_label, score in entries:
        measured = status not in ("deferred", "na")
        scored = measured and key not in DISPLAY_ONLY_CHECKS  # structure checks have findings, not a score
        pct = max(0, min(100, int(score)))
        score_html = (
            f'<span class="score"><span class="mono">{pct}</span>'
            f'<span class="meter {status}"><span style="width:{pct}%"></span></span></span>'
            if scored else '<span class="mono muted">—</span>'
        )
        weight = weights.get(key)
        weight_html = _esc(weight) if weight and scored else "—"
        count = finding_counts.get(key, 0)
        chip = _status_chip(status, status_label)
        rows.append(
            f'<tr data-key="{key}" aria-selected="false">'
            f'<td><button type="button" class="row-title" aria-controls="check-detail">{_esc(label)}</button></td>'
            f"<td>{score_html}</td><td>{chip}</td>"
            f'<td class="num">{count}</td><td class="num col-weight">{weight_html}</td></tr>'
        )
        score_top = f'<span class="mono">{pct} / 100</span>' if scored else ""
        noun = "finding" if count == 1 else "findings"
        cards.append(
            f'<article class="card detail" data-key="{key}" id="check-{key}" aria-labelledby="check-{key}-title">'
            '<div class="card-body">'
            f'<div class="card-top"><span class="lbl">Check</span>{chip}{score_top}</div>'
            f'<h3 id="check-{key}-title">{_esc(label)}</h3>'
            f'<div class="panel-body">{panels.get(key, "")}</div>'
            "</div>"
            f'<div class="card-foot"><span class="mono">{count} {noun} · weight {weight_html}</span>{_STEPPER}</div>'
            "</article>"
        )
    return (
        '<div class="section-head"><h2 id="checks-h">Checks</h2>'
        '<p class="note">Sorted by status, weakest first. Scores run 0 to 100, and weight sets how much '
        "each check counts toward the overall score.</p></div>"
        '<div class="panel"><div class="table-scroll"><table class="ledger" aria-label="Checks"><thead><tr>'
        '<th class="lbl" scope="col">Check</th>'
        '<th class="lbl" scope="col" style="width:150px">Score</th>'
        '<th class="lbl" scope="col" style="width:150px">Status</th>'
        '<th class="lbl" scope="col" style="width:90px">Findings</th>'
        '<th class="lbl col-weight" scope="col" style="width:80px">Weight</th>'
        f'</tr></thead><tbody id="check-rows">{"".join(rows)}</tbody></table></div></div>'
        f'<div class="detail-stack check-detail" id="check-detail" aria-live="polite">{"".join(cards)}</div>'
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
        + (f'<p class="note">Also possible: {_esc(", ".join(alternatives))}</p>' if alternatives else "")
    )
    plan_title = "Fix plan" if platform == "Unknown" else f"Fix plan for {platform}"
    return (
        '<div class="section-head"><h2 id="platform-h">Platform</h2>'
        '<p class="note">Inferred from signals in the HTML source. Fixes are phrased for the detected platform.</p></div>'
        f'<div class="two-col"><div>{left}</div>'
        f'<div>{_subhead(plan_title)}{render_environment_fixes(data.get("environment_fixes", []))}</div></div>'
    )


def generate_html(data: dict, scores: dict) -> str:
    """Generate the HTML report: Tobto design system, Ledger layout."""
    domain = data["domain"]
    url = data["url"]
    timestamp = data["timestamp"]
    sections = data.get("sections", {})
    env = data.get("environment", {}) or {}
    overall = scores["overall"]
    categories = scores.get("categories", {})
    issues = _collect_issues(data)
    counts = {s: sum(1 for i in issues if i["severity"] == s) for s in ("critical", "warning", "info")}

    statuses = {}
    for key in CHECK_LABELS:
        section = _source_section(sections, key)
        statuses[key] = _check_status(key, section if isinstance(section, dict) else {}, categories.get(key))
    not_measured = sum(1 for status, _ in statuses.values() if status == "deferred")
    gaps = sorted((k for k, (status, _) in statuses.items() if status == "gap"),
                  key=lambda k: categories.get(k) or 0)[:3]
    ran = sum(1 for value in sections.values() if isinstance(value, dict) and not value.get("error"))

    try:
        generated = datetime.fromisoformat(timestamp)
        date_label = generated.strftime("%Y-%m-%d")
        stamp = generated.strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        date_label = stamp = str(timestamp)

    lede = (
        f"{len(issues)} findings: {counts['critical']} critical, {counts['warning']} warnings "
        f"and {counts['info']} informational."
    )
    if gaps:
        lede += " Weakest checks: " + _join_labels([CHECK_LABELS[k] for k in gaps]) + "."

    lead = next((i for i in issues if i["severity"] == "critical"), None) or next(
        (i for i in issues if i["severity"] == "warning"), None)
    if lead:
        lead_label = CHECK_LABELS.get(lead["section"], lead["section"])
        lead_fix = f'<p>{_esc(lead["fix"])}</p>' if lead["fix"] else ""
        callout = (
            '<div class="callout"><p class="lbl">Start here</p>'
            f'<p class="callout-title">{_esc(_headline(lead["finding"]))}</p>{lead_fix}'
            f'<p class="mono note"><a href="#{lead["id"]}" data-open-finding="{lead["id"]}">Open {lead["id"]}</a>'
            f" · {_esc(lead_label)}</p></div>"
        )
    else:
        callout = (
            '<div class="callout"><p class="lbl">Start here</p>'
            '<p class="callout-title">No critical or warning findings.</p>'
            "<p>Review the informational items and keep running regular reports.</p></div>"
        )

    strip = (
        f'<span class="count"><b>{overall}</b>/100 · grade {_grade(overall)}</span>'
        f'<span class="count"><b>{counts["critical"]}</b> critical</span>'
        f'<span class="count"><b>{counts["warning"]}</b> warning</span>'
        f'<span class="count"><b>{counts["info"]}</b> info</span>'
    )
    if not_measured:
        plural = "check" if not_measured == 1 else "checks"
        strip += f'<span class="mark m-deferred">⏸︎<small>{not_measured} {plural} not measured</small></span>'

    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"UTF-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>SEO report · {_esc(domain)}</title>\n"
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        f'<link rel="stylesheet" href="{_esc(_FONTS_URL)}">\n'
        f"<style>{_REPORT_CSS}</style>\n</head>\n<body>\n"
        '<div class="hero">\n'
        '<header class="site-header"><div class="wrap">'
        '<span class="brand">Ultimate SEO + GEO</span>'
        '<nav class="site-nav" aria-label="Report sections">'
        '<a href="#findings">Findings</a><a href="#checks">Checks</a>'
        '<a href="#platform">Platform</a><a href="#recommendations">Recommendations</a></nav>'
        '<button type="button" class="theme-toggle" id="theme-toggle">Theme: system</button>'
        "</div></header>\n"
        '<div class="wrap"><div class="intro">'
        '<div class="intro-main">'
        f'<p class="lbl">SEO + GEO report · {_esc(domain)}</p>'
        f"<h1>{_esc(domain)}</h1>"
        f'<p class="mono note">{_esc(date_label)} · {_esc(env.get("primary", "Unknown"))} · '
        f"{ran} of {len(sections)} checks ran</p>"
        f'<p class="lede">{_esc(lede)}</p>'
        f'<div class="strip" aria-label="Score and findings">{strip}</div>'
        "</div>"
        f'<div class="intro-side">{callout}'
        '<p class="scope"><span class="mark">◇</span><span><b>Automated checks.</b> Every finding '
        f"and score comes from scripts run against {_esc(url)}. Scores are a triage signal; confirm "
        "high-risk changes such as redirects, canonicals and robots.txt before acting.</span></p>"
        "</div></div></div>\n</div>\n"
        '<main class="wrap">\n'
        f'<section class="section band" id="findings" aria-labelledby="findings-h">{_render_findings(issues)}</section>\n'
        f'<section class="section" id="checks" aria-labelledby="checks-h">{_render_checks(data, scores, issues)}</section>\n'
        f'<section class="section" id="platform" aria-labelledby="platform-h">{_render_platform(data)}</section>\n'
        '<section class="section" id="recommendations" aria-labelledby="recommendations-h">'
        '<div class="section-head"><h2 id="recommendations-h">Recommendations</h2>'
        '<p class="note">Every recommendation the checks returned, grouped by check.</p></div>'
        f'<div class="rec-grid">{render_all_recommendations(data)}</div></section>\n'
        "</main>\n"
        '<footer class="site-footer"><div class="wrap">'
        f'<span class="mono">Generated by ultimate-seo-geo generate_report.py · {_esc(stamp)}</span>'
        f'<span>Findings and scores come from automated checks against <a href="{_esc(url)}">{_esc(url)}</a>.</span>'
        "</div></footer>\n"
        f"<script>{_REPORT_JS}</script>\n</body>\n</html>"
    )


_REPORT_CSS = """
:root{
  --font-sans:"Instrument Sans",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
  --font-mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --page:#ffffff;--card:#ffffff;--sunk:#f5f6f8;--band:#f5f6f8;--hover:#fafbfc;
  --text-strong:#0b0d10;--text-body:#16191e;--text-muted:#5b626d;--text-faint:#838a95;
  --link:#0057b7;--link-hover:#003c7f;--line:#d7dbe1;--line-strong:#b4bac3;
  --ring:rgba(11,13,16,.10);--focus:rgba(0,87,183,.35);
  --head-bg:#eef4fc;--head-text:#003c7f;
  --ok-text:#2f5e18;--ok-bg:#e8efe4;--ok-border:rgba(63,125,32,.35);
  --flag-text:#6e4c05;--flag-bg:#fdf6e3;--flag-border:rgba(153,106,8,.40);
  --danger-text:#a2213a;--danger-bg:#f8e7ea;--danger-border:rgba(194,51,79,.35);
  --info-text:#003c7f;--info-bg:#eef4fc;--info-border:rgba(0,87,183,.30);
  --warn-chip-text:#ffffff;--warn-chip-bg:#262a31;
  --st-deferred:#838a95;--accent:#b83f00;--observed:#0e7490;
  --hero-bg:#eef4fc;--hero-grid:rgba(0,87,183,.07);--hero-line:rgba(0,87,183,.18);--hero-code:#ffffff;
  --callout-bg:#ffffff;--callout-border:rgba(0,87,183,.22);
  --meter-ok:#3f7d20;--meter-flag:#996a08;--meter-gap:#c2334f;
  --code-bg:#f5f6f8;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    color-scheme:dark;
    --page:#0b0d10;--card:#16191e;--sunk:#1d2127;--band:#111418;--hover:rgba(255,255,255,.04);
    --text-strong:#ffffff;--text-body:#eaedf1;--text-muted:#838a95;--text-faint:#5b626d;
    --link:#7faae4;--link-hover:#b0ccf0;--line:rgba(255,255,255,.12);--line-strong:rgba(255,255,255,.24);
    --ring:rgba(255,255,255,.12);--focus:rgba(127,170,228,.45);
    --head-bg:#0d213b;--head-text:#7faae4;
    --ok-text:#8fce6e;--ok-bg:#16260f;--ok-border:rgba(63,125,32,.6);
    --flag-text:#e5c86a;--flag-bg:#2a200a;--flag-border:rgba(153,106,8,.6);
    --danger-text:#f08fa2;--danger-bg:#321219;--danger-border:rgba(194,51,79,.55);
    --info-text:#7faae4;--info-bg:#0d213b;--info-border:rgba(0,87,183,.55);
    --warn-chip-text:#0b0d10;--warn-chip-bg:#d7dbe1;
    --meter-ok:#8fce6e;--meter-flag:#e5c86a;--meter-gap:#f08fa2;
    --code-bg:rgba(255,255,255,.08);
  --hero-bg:#09192b;--hero-grid:rgba(255,255,255,.05);--hero-line:rgba(255,255,255,.12);--hero-code:rgba(255,255,255,.10);
  --callout-bg:#16191e;--callout-border:rgba(255,255,255,.14);--accent:#ff6a1a;--observed:#7fd4e8;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --page:#0b0d10;--card:#16191e;--sunk:#1d2127;--band:#111418;--hover:rgba(255,255,255,.04);
  --text-strong:#ffffff;--text-body:#eaedf1;--text-muted:#838a95;--text-faint:#5b626d;
  --link:#7faae4;--link-hover:#b0ccf0;--line:rgba(255,255,255,.12);--line-strong:rgba(255,255,255,.24);
  --ring:rgba(255,255,255,.12);--focus:rgba(127,170,228,.45);
  --head-bg:#0d213b;--head-text:#7faae4;
  --ok-text:#8fce6e;--ok-bg:#16260f;--ok-border:rgba(63,125,32,.6);
  --flag-text:#e5c86a;--flag-bg:#2a200a;--flag-border:rgba(153,106,8,.6);
  --danger-text:#f08fa2;--danger-bg:#321219;--danger-border:rgba(194,51,79,.55);
  --info-text:#7faae4;--info-bg:#0d213b;--info-border:rgba(0,87,183,.55);
  --warn-chip-text:#0b0d10;--warn-chip-bg:#d7dbe1;
  --meter-ok:#8fce6e;--meter-flag:#e5c86a;--meter-gap:#f08fa2;
  --code-bg:rgba(255,255,255,.08);
  --hero-bg:#09192b;--hero-grid:rgba(255,255,255,.05);--hero-line:rgba(255,255,255,.12);--hero-code:rgba(255,255,255,.10);
  --callout-bg:#16191e;--callout-border:rgba(255,255,255,.14);--accent:#ff6a1a;--observed:#7fd4e8;
}
*{box-sizing:border-box}
[hidden]{display:none!important}
body{margin:0;background:var(--page);color:var(--text-body);font-family:var(--font-sans);font-size:17px;line-height:1.7;-webkit-font-smoothing:antialiased;text-wrap:pretty}
h1,h2,h3,h4{margin:0;color:var(--text-strong);font-weight:600;letter-spacing:-0.02em;line-height:1.2;text-wrap:balance}
p{margin:0}
a{color:var(--link);text-underline-offset:.15em}
a:hover{color:var(--link-hover)}
code{font-family:var(--font-mono);font-size:.86em;background:var(--code-bg);border-radius:4px;padding:.1em .35em;overflow-wrap:anywhere}
button{font:inherit;color:inherit}
:focus-visible{outline:none;box-shadow:0 0 0 3px var(--focus);border-radius:6px}
.wrap{max-width:76rem;margin-inline:auto;padding-inline:24px}
.lbl{font-family:var(--font-mono);font-size:12px;line-height:1.4;text-transform:uppercase;letter-spacing:.12em;font-weight:500;color:var(--text-muted)}
.mono{font-family:var(--font-mono);font-variant-numeric:tabular-nums}
.muted{color:var(--text-muted)}
.note{font-size:14px;line-height:1.5;color:var(--text-muted)}
.subhead{font-size:15px;margin:20px 0 8px}

.hero{--line:var(--hero-line);--code-bg:var(--hero-code);--st-deferred:var(--text-muted);
  color:var(--text-body);background-color:var(--hero-bg);background-image:linear-gradient(var(--hero-grid) 1px,transparent 1px),linear-gradient(90deg,var(--hero-grid) 1px,transparent 1px);background-size:28px 28px;border-bottom:1px solid var(--line)}
.site-header{border-bottom:1px solid var(--line)}
.site-header .wrap{display:flex;flex-wrap:wrap;align-items:center;gap:8px 24px;padding-block:16px}
.brand{font-size:17px;font-weight:600;letter-spacing:-0.02em;color:var(--text-strong)}
.site-nav{display:flex;flex-wrap:wrap;gap:4px 20px;font-size:14px}
.site-nav a{color:var(--text-muted);text-decoration:none;transition:color 100ms cubic-bezier(.2,0,.2,1)}
.site-nav a:hover{color:var(--text-strong)}
.theme-toggle{display:none;margin-left:auto;height:32px;padding:0 12px;border-radius:8px;border:1px solid var(--line);background:transparent;color:var(--text-muted);font-family:var(--font-mono);font-size:12px;cursor:pointer}
.js .theme-toggle{display:inline-block}
.theme-toggle:hover{color:var(--text-strong)}
.intro{display:grid;grid-template-columns:minmax(0,7fr) minmax(0,5fr);gap:24px 48px;align-items:start;padding-block:48px 44px}
.intro-main{display:flex;flex-direction:column;gap:12px}
h1{font-size:36px;letter-spacing:-0.022em;line-height:1.15;overflow-wrap:anywhere}
.lede{font-size:18px;line-height:1.6;color:var(--text-muted);max-width:44rem}
.strip{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 28px;margin-top:12px;padding-top:16px;border-top:1px solid var(--line)}
.strip .count{font-family:var(--font-mono);font-size:14px;color:var(--text-body)}
.strip .count b{font-weight:700;color:var(--text-strong)}
.intro-side{display:flex;flex-direction:column;gap:12px}
.callout{border:1px solid var(--callout-border);border-radius:14px;padding:16px;display:flex;flex-direction:column;gap:8px;background:var(--callout-bg)}
.callout .lbl{color:var(--accent)}
.callout p{font-size:15px;line-height:1.6}
.callout .callout-title{font-size:17px;font-weight:600;color:var(--text-strong);line-height:1.4}
.scope{font-size:14px;line-height:1.5;color:var(--text-muted);display:flex;gap:10px;align-items:baseline}
.scope .mark{color:var(--observed)}
.scope b{font-weight:500;color:var(--text-strong)}

.notice{padding:12px 16px;border-radius:10px;border:1px solid var(--line);background:var(--sunk);font-size:14px;line-height:1.5;color:var(--text-muted);margin:0 0 12px}
.notice b{font-weight:500;color:var(--text-strong)}
.notice.info{background:var(--info-bg);border-color:var(--info-border)}
.notice.flag{background:var(--flag-bg);border-color:var(--flag-border)}

.section{margin-top:48px;border-top:1px solid var(--line);padding-top:32px}
.band{background:var(--band);box-shadow:0 0 0 100vmax var(--band);clip-path:inset(0 -100vmax)}
.band.section{border-top:0;margin-top:0;padding-block:40px 44px}
.section-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 16px;margin-bottom:20px}
.section-head h2{font-size:20px}
.section-head .note{flex-basis:100%}

.chip{display:inline-block;font-family:var(--font-mono);font-size:12px;line-height:18px;text-transform:uppercase;letter-spacing:.12em;font-weight:500;padding:1px 8px;border-radius:6px;border:1px solid;white-space:nowrap}
.sev-critical,.chip-gap{color:var(--danger-text);background:var(--danger-bg);border-color:var(--danger-border)}
.sev-warning{color:var(--warn-chip-text);background:var(--warn-chip-bg);border-color:var(--warn-chip-bg)}
.sev-info,.chip-na{color:var(--text-muted);background:transparent;border-color:var(--line)}
.chip-ok{color:var(--ok-text);background:var(--ok-bg);border-color:var(--ok-border)}
.chip-flag{color:var(--flag-text);background:var(--flag-bg);border-color:var(--flag-border)}
.chip-info{color:var(--info-text);background:var(--info-bg);border-color:var(--info-border)}
.mark{display:inline-flex;align-items:baseline;gap:8px;font-family:var(--font-mono);font-size:14px;font-weight:700;white-space:nowrap;font-variant-emoji:text}
.mark small{font-size:12px;text-transform:uppercase;letter-spacing:.12em;font-weight:500}
.m-deferred{color:var(--st-deferred)}
.yes{color:var(--ok-text);font-weight:600}
.no{color:var(--danger-text);font-weight:600}

.filter{display:none;flex-wrap:wrap;gap:8px;margin-left:auto}
.js .filter{display:flex}
.filter button{cursor:pointer;display:inline-flex;align-items:baseline;gap:6px;height:32px;padding:0 12px;border-radius:8px;border:1px solid var(--line);background:transparent;font-size:14px;line-height:30px;color:var(--text-muted)}
.filter button:hover{background:var(--hover);color:var(--text-strong)}
.filter button:active{transform:translateY(1px)}
.filter button[aria-pressed="true"]{background:var(--card);border-color:var(--line-strong);color:var(--text-strong);font-weight:500}
.filter .mono{font-size:12px;color:var(--text-faint)}

.panel{border-radius:14px;box-shadow:0 0 0 1px var(--ring);background:var(--card);padding:12px 16px 14px}
.ledger-grid{display:grid;grid-template-columns:minmax(0,7fr) minmax(0,5fr);gap:32px;align-items:start}
.table-scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
.ledger{font-size:15px;line-height:1.45}
.ledger th{padding:0 8px 10px;text-align:left;border-bottom:1px solid var(--line-strong);white-space:nowrap;color:var(--head-text)}
.ledger td{padding:0 8px;border-bottom:1px solid var(--line);vertical-align:baseline}
.ledger tbody tr:last-child td{border-bottom:0}
.js .ledger tbody tr{cursor:pointer}
.ledger tbody tr:hover{background:var(--hover)}
.ledger tbody tr[aria-selected="true"]{background:var(--sunk)}
.ledger tbody tr[aria-selected="true"] .row-title{font-weight:600}
.ledger td.id{font-family:var(--font-mono);font-size:13px;color:var(--text-muted);padding-block:12px}
.ledger td.id.hi{color:var(--danger-text)}
.row-title{all:unset;display:block;cursor:pointer;padding-block:12px;color:var(--text-strong);border-radius:6px;overflow-wrap:anywhere}
.row-title:focus-visible{box-shadow:0 0 0 3px var(--focus)}
.ledger td.small{font-size:14px;color:var(--text-muted)}
.legend{display:none;margin-top:12px;font-family:var(--font-mono);font-size:13px;color:var(--text-muted)}
.js .legend{display:block}
.score{display:inline-flex;align-items:center;gap:10px}
.meter{display:inline-block;width:64px;height:4px;border-radius:2px;background:var(--line);overflow:hidden}
.meter.wide{width:160px}
.meter>span{display:block;height:100%;background:var(--link)}
.meter.ok>span{background:var(--meter-ok)}
.meter.flag>span{background:var(--meter-flag)}
.meter.gap>span{background:var(--meter-gap)}

.detail-stack{display:flex;flex-direction:column;gap:16px}
.check-detail{margin-top:16px}
.card{border-radius:14px;box-shadow:0 0 0 1px var(--ring);background:var(--card);overflow:hidden}
.card-body{padding:16px;display:flex;flex-direction:column;gap:14px}
.card-top{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 12px}
.card-top .id{font-family:var(--font-mono);font-size:13px;color:var(--text-muted)}
.card h3{font-size:20px;line-height:1.25;overflow-wrap:anywhere}
.field{display:flex;flex-direction:column;gap:4px}
.field p{font-size:15px;line-height:1.6;overflow-wrap:anywhere}
.card-foot{border-top:1px solid var(--line);background:var(--sunk);padding:12px 16px;display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;font-size:13px}
.card-foot .mono{font-size:13px;color:var(--text-muted)}
.stepper{display:none;margin-left:auto;gap:8px}
.js .stepper{display:flex}
.stepper button{cursor:pointer;height:32px;padding:0 12px;border-radius:8px;border:1px solid var(--line-strong);background:var(--card);font-size:14px;color:var(--text-strong)}
.stepper button:hover{background:var(--hover)}
.stepper button:active{transform:translateY(1px)}
.stepper button:disabled{opacity:.5;pointer-events:none}

.kv{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:0;margin:0 0 12px;border-top:1px solid var(--line)}
.kv>div{padding:10px 12px 10px 0;border-bottom:1px solid var(--line)}
.kv dt{font-family:var(--font-mono);font-size:12px;text-transform:uppercase;letter-spacing:.12em;font-weight:500;color:var(--text-muted)}
.kv dd{margin:2px 0 0;font-family:var(--font-mono);font-size:15px;color:var(--text-strong);overflow-wrap:anywhere}
.tbl{font-size:14px;line-height:1.5;margin:0 0 12px}
.tbl th,.tbl td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
.tbl thead th{background:var(--head-bg);font-weight:600;color:var(--head-text)}
.tbl .num{text-align:right;font-family:var(--font-mono);font-size:13px;white-space:nowrap}
.url{font-family:var(--font-mono);font-size:13px;overflow-wrap:anywhere}
.issues{list-style:none;margin:0 0 12px;padding:0;border-top:1px solid var(--line)}
.issue{padding:12px 0;border-bottom:1px solid var(--line);display:flex;flex-direction:column;gap:6px}
.issue-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 12px}
.issue-head strong{font-weight:600;color:var(--text-strong);font-size:15px;line-height:1.45}
.issue-reason,.issue-fix{font-size:14px;line-height:1.55}
.issue-reason{color:var(--text-muted)}
.issue-fix .lbl{margin-right:6px}
.meta{margin:0;display:grid;gap:2px;font-size:13px;line-height:1.5;color:var(--text-muted)}
.meta>div{display:flex;flex-wrap:wrap;gap:0 6px}
.meta dt{font-weight:600;color:var(--text-body)}
.meta dd{margin:0}
.recs{margin:0 0 12px;padding-left:18px;display:flex;flex-direction:column;gap:6px;font-size:14px;line-height:1.55}

.two-col{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:40px;align-items:start}
.rec-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:8px 32px}
.site-footer{margin-top:64px;border-top:1px solid var(--line)}
.site-footer .wrap{padding-block:24px 48px;display:flex;flex-direction:column;gap:6px;font-size:14px;color:var(--text-muted)}

@media (max-width: 960px){
  .intro,.ledger-grid,.two-col{grid-template-columns:minmax(0,1fr)}
  .filter{margin-left:0}
}
@media (max-width: 640px){
  h1{font-size:28px}
  .col-check,.col-weight{display:none}
  .theme-toggle{margin-left:0}
}
@media (prefers-reduced-motion: reduce){
  *{transition:none!important;scroll-behavior:auto!important}
}
@media print{
  body{font-size:11pt;background:#ffffff}
  .hero{--text-strong:#0b0d10;--text-body:#16191e;--text-muted:#5b626d;--line:#d7dbe1;--link:#0057b7;background:none!important;color:#16191e}
  .callout{border-color:#d7dbe1;background:none}
  .band{box-shadow:none!important;background:none!important}
  .site-nav,.filter,.stepper,.theme-toggle,.legend{display:none!important}
  .detail[hidden]{display:block!important}
  .ledger-grid,.two-col,.intro{grid-template-columns:minmax(0,1fr)!important}
  .ledger tbody tr[aria-selected="true"]{background:transparent}
  .card{break-inside:avoid;box-shadow:none;border:1px solid #d7dbe1}
}
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

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  var stacked = window.matchMedia('(max-width: 960px)');

  function makeLedger(bodyId, detailId, filterId) {
    var body = document.getElementById(bodyId);
    var detail = document.getElementById(detailId);
    if (!body || !detail) return null;
    var rows = Array.prototype.slice.call(body.querySelectorAll('tr[data-key]'));
    var cards = Array.prototype.slice.call(detail.querySelectorAll('article[data-key]'));
    var selected = null;

    function visibleRows() { return rows.filter(function (r) { return !r.hidden; }); }
    function indexOfSelected(list) {
      for (var i = 0; i < list.length; i++) if (list[i].getAttribute('data-key') === selected) return i;
      return -1;
    }
    function syncStepper() {
      var list = visibleRows();
      var i = indexOfSelected(list);
      cards.forEach(function (card) {
        var prev = card.querySelector('[data-step="-1"]');
        var next = card.querySelector('[data-step="1"]');
        if (prev) prev.disabled = i <= 0;
        if (next) next.disabled = i < 0 || i >= list.length - 1;
      });
    }
    function select(key, opts) {
      opts = opts || {};
      var row = body.querySelector('tr[data-key="' + key + '"]');
      if (!row) return;
      if (row.hidden) setFilter('all');
      selected = key;
      rows.forEach(function (r) { r.setAttribute('aria-selected', r === row ? 'true' : 'false'); });
      cards.forEach(function (card) { card.hidden = card.getAttribute('data-key') !== key; });
      syncStepper();
      if (opts.focus) {
        var button = row.querySelector('.row-title');
        if (button) button.focus();
      }
      if (opts.reveal) {
        var target = stacked.matches ? detail : body.closest('section');
        if (target) target.scrollIntoView({ behavior: reduceMotion.matches ? 'auto' : 'smooth', block: 'start' });
      }
    }
    function setFilter(value) {
      rows.forEach(function (r) {
        r.hidden = !(value === 'all' || r.getAttribute('data-filter') === value);
      });
      if (filterId) {
        var buttons = document.querySelectorAll('#' + filterId + ' button[data-filter]');
        Array.prototype.forEach.call(buttons, function (b) {
          b.setAttribute('aria-pressed', b.getAttribute('data-filter') === value ? 'true' : 'false');
        });
      }
      var list = visibleRows();
      if (list.length && indexOfSelected(list) < 0) select(list[0].getAttribute('data-key'));
      else syncStepper();
    }
    function step(delta) {
      var list = visibleRows();
      var next = list[indexOfSelected(list) + delta];
      if (next) select(next.getAttribute('data-key'), { focus: true });
    }

    body.addEventListener('click', function (e) {
      var row = e.target.closest('tr[data-key]');
      if (row) select(row.getAttribute('data-key'), { reveal: stacked.matches });
    });
    body.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); step(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); step(-1); }
    });
    detail.addEventListener('click', function (e) {
      var button = e.target.closest('[data-step]');
      if (button) step(Number(button.getAttribute('data-step')));
    });
    if (filterId) {
      var filterEl = document.getElementById(filterId);
      if (filterEl) {
        filterEl.addEventListener('click', function (e) {
          var button = e.target.closest('button[data-filter]');
          if (button) setFilter(button.getAttribute('data-filter'));
        });
      }
    }
    if (rows.length) select(rows[0].getAttribute('data-key'));
    return {
      select: select,
      has: function (key) { return !!body.querySelector('tr[data-key="' + key + '"]'); }
    };
  }

  var findings = makeLedger('finding-rows', 'finding-detail', 'finding-filter');
  var checks = makeLedger('check-rows', 'check-detail', null);

  document.addEventListener('click', function (e) {
    var link = e.target.closest('[data-open-finding],[data-open-check]');
    if (!link) return;
    e.preventDefault();
    if (link.hasAttribute('data-open-finding') && findings) findings.select(link.getAttribute('data-open-finding'), { reveal: true });
    if (link.hasAttribute('data-open-check') && checks) checks.select(link.getAttribute('data-open-check'), { reveal: true });
  });

  var hash = decodeURIComponent((location.hash || '').slice(1));
  if (findings && findings.has(hash)) findings.select(hash, { reveal: true });
  else if (hash.indexOf('check-') === 0 && checks && checks.has(hash.slice(6))) checks.select(hash.slice(6), { reveal: true });
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

    args = parser.parse_args()
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
    )
    scores = calculate_overall_score(data)

    formats = [] if args.fmt == "none" else ["html", "xlsx"] if args.fmt == "all" else [args.fmt]

    html_cache = None
    for fmt in formats:
        if fmt == "html":
            html_cache = generate_html(data, scores)
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
                html_cache = generate_html(data, scores)
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

    summary = build_summary(data, scores)
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
