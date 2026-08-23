> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

## 4. Technical SEO

### Core Web Vitals (INP replaced FID March 2024 — FID removed from CrUX/PSI Sept 2024; Lighthouse never reported FID)

| Metric | Good | Needs Improvement | Poor |
|---|---|---|---|
| **LCP** | < 2.5s | 2.5–4.0s | > 4.0s |
| **INP** | < 200ms | 200–500ms | > 500ms |
| **CLS** | < 0.1 | 0.1–0.25 | > 0.25 |

Measured at 75th percentile (CrUX/PageSpeed Insights). Speed is also a GEO factor: FCP < 0.4s pages average 6.7 AI citations vs. 2.1 for slower pages.

### Technical Audit — Step by Step

1. **Run PageSpeed Insights** on homepage + top 3 pages. Record LCP, INP, CLS. For detailed CWV fix steps (LCP subparts, INP long task debugging, CLS prevention patterns), see `references/technical-checklist.md`.
2. **Check robots.txt** — CSS, JS, and key pages not blocked. AI crawlers not disallowed. Two critical distinctions often misconfigured: (a) `Google-Extended` blocks Gemini training only — it does **not** affect Google Search indexing or AI Overviews (those use Googlebot); (b) `GPTBot` blocks OpenAI training only — it does **not** block ChatGPT Search citations, which uses `ChatGPT-User`. Blocking GPTBot expecting only a training opt-out silently removes the site from ChatGPT live search results if `ChatGPT-User` is also blocked.
3. **Check HTTPS** — Entire site over HTTPS. Mixed-content assets → force HTTPS via 301.
4. **Check canonical tags** — Run `scripts/canonical_checker.py URL` for single-page validation or `--crawl` for site-wide. Every indexable page needs `<link rel="canonical" href="[absolute-url]">`. Check for www/non-www mismatch, trailing slash inconsistency, and canonical chains.
5. **Check redirect chains** — Chain >1 hop → collapse to direct redirect.
6. **Check orphan pages** — Any indexed page with zero internal links. Flag here; fix in § 9.
7. **Check mobile rendering** — GSC Mobile Usability. Touch targets ≥48×48px, font ≥16px.
8. **Check soft 404s** — Run `scripts/broken_links.py` on key pages; it detects pages returning 200 but showing "not found" in `<title>`. Also check `scripts/sitemap_checker.py` output for soft 404s in sitemap. Fix: return real 404/410 or add genuine content.
9. **Check for broken internal pages** — Run `scripts/internal_links.py` (now reports 404/5xx pages found during crawl) or `scripts/broken_links.py --crawl` for site-wide broken link scan.
10. **Check JavaScript rendering** — Compare raw source to rendered DOM. Key content JS-only = invisible to AI bots.
11. **Check Open Graph + Twitter Card** — `og:title`, `og:description`, `og:image`, `twitter:card` on all shareable pages.
12. **Check security headers** — HSTS, X-Frame-Options, X-Content-Type-Options. ✅ Pass: `Strict-Transport-Security: max-age=31536000; includeSubDomains`. ❌ Fail: header absent or `max-age=0`.

For the full Critical Technical Issues + Fix Directives table (9 issues with detection methods and fixes), JavaScript SEO December 2025 clarifications (canonical conflicts, noindex behavior, JS-rendered structured data), and the mobile-first indexing note, see `references/technical-checklist.md`.

**Key rule**: Serve all critical SEO elements (canonical, meta robots, structured data, title, meta description, hreflang) in the **initial server-rendered HTML** — not JS-only.

### Technical Finding Example

```
Finding: Redirect Chain Detected
Severity: 🟠 High | Confidence: Confirmed

Issue: /old-page → /temp-redirect → /final-destination (2-hop chain)
Every extra hop adds latency and dilutes link equity.

Fix: Update all internal links and any external links you control to point directly to
/final-destination. The redirect map remains as a safety net.
Expected impact: Faster crawl, full link equity preservation.
```

→ See `references/technical-checklist.md` (detailed CWV fix steps, LCP subparts, IndexNow setup) | Run `scripts/pagespeed.py` Run `scripts/robots_checker.py` Run `scripts/redirect_checker.py` Run `scripts/security_headers.py` Run `scripts/indexnow_checker.py` Run `scripts/broken_links.py --crawl` Run `scripts/sitemap_checker.py --sample 50`

> **Script note**: `pagespeed.py` calls googleapis.com. In proxy-restricted environments it will fail — fallback: ask user to run pagespeed.web.dev and share results, or use the manual CWV checklist in `references/technical-checklist.md`.

