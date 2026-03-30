<!-- Updated: 2026-03-22 | Review: 2026-09-22 -->

# Crawl Budget, Indexation & Canonicalization
## Updated: March 2026

---


**Contents:** Updated: March 2026 · Why Crawl Management Matters · Crawl Budget Components · Crawl Budget Waste — What to Fix · XML Sitemap Strategy · Canonicalization · Log File Analysis · Indexation Health Checks · International SEO: hreflang · Crawl & Indexation Scoring

## Why Crawl Management Matters

Googlebot has a finite crawl budget per site — it determines how many pages are crawled and how often. Wasting crawl budget on low-value pages means important pages get crawled less frequently. This is especially critical for:
- Large sites (10,000+ URLs)
- E-commerce sites with faceted navigation
- Sites with frequent content updates (news, product inventory)
- Sites recovering from indexation drops

**Small sites (< 500 pages)**: Crawl budget is rarely the issue. Focus on content quality and canonical strategy instead.

---

## Crawl Budget Components

### 1. Crawl Rate Limit
How fast Googlebot crawls without overloading your server. Controlled by:
- Server health and response time (TTFB < 200ms = healthy)
- `Crawl-delay` in robots.txt (use sparingly — can slow legitimate crawling)
- GSC Crawl Stats report → "Crawl rate" setting (legacy; Google mostly ignores this now)

### 2. Crawl Demand
How often Google wants to crawl a URL based on:
- **Popularity**: More-linked-to pages get crawled more often
- **Freshness**: Frequently-updated pages get crawled more often
- **Crawl history**: Pages that changed often historically get revisited sooner

### Google's Crawl Priority Order (2026)
1. Sitemaps + ping
2. Internal links from high-authority pages
3. External links pointing to the page
4. Historical crawl signals
5. Low-priority: orphan pages, deep crawl depth, URL parameters

---

## Crawl Budget Waste — What to Fix

### High-Priority Crawl Waste

| Issue | Detection | Fix |
|---|---|---|
| Faceted navigation URLs | Crawl site, count `/color=red&size=M` style URLs | `noindex` or canonical → master category |
| Paginated archive pages | Pages like `/blog/page/47` | Noindex paginated pages OR canonical all to page 1 (if content is largely duplicate) |
| Session IDs / tracking parameters | URLs with `?utm_source=`, `?sessionid=` | Canonical to canonical URL; configure URL parameters in GSC (legacy tool, still available) |
| Thin tag / category pages | `/tag/red/`, `/category/all/` pages with < 300 words and no unique value | Noindex or consolidate |
| Infinite scroll artifacts | Dynamic `?page=2`, `?offset=100` URLs | Proper pagination with `rel=next`/`prev` is deprecated — use view-all + canonical instead |
| Duplicate HTTP/HTTPS or www/non-www | Four versions of homepage | 301 redirect all to single canonical; set preferred domain in GSC |
| Staging site crawlable | Staging URLs in search results | Block with robots.txt on staging; add noindex meta; do NOT rely on robots.txt alone |

### Medium-Priority Crawl Waste

| Issue | Detection | Fix |
|---|---|---|
| Printer-friendly / PDF versions | Duplicate content with `?print=1` | Canonical → original page |
| Sort order variants | `/products?sort=price_asc` | Canonical → canonical product listing |
| Near-duplicate location pages | 50 city pages with < 10% unique content | Unique local content or consolidate with geo-targeting |
| Old subdomain content | `old.site.com` still crawlable | 301 redirect or block |
| Dev/API endpoints crawlable | `/api/v2/products.json` in index | `noindex` or robots.txt block |

---

## XML Sitemap Strategy

### Sitemap Best Practices

- **Maximum 50,000 URLs or 50MB per sitemap file** (uncompressed) — use sitemap index files for large sites
- **Only canonical URLs**: Never include noindex pages, redirect chains, or 4xx pages in sitemap
- **Include**: all indexable pages you want crawled — key content, product pages, articles
- **Exclude**: paginated archives, filtered/faceted URLs, thin pages, admin pages

### Sitemap Index Structure (large sites)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://site.com/sitemap-pages.xml</loc>
    <lastmod>2026-03-01</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://site.com/sitemap-posts.xml</loc>
    <lastmod>2026-03-21</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://site.com/sitemap-products.xml</loc>
    <lastmod>2026-03-21</lastmod>
  </sitemap>
</sitemapindex>
```

### Sitemap URL Entry Best Practice

```xml
<url>
  <loc>https://site.com/article-slug/</loc>
  <lastmod>2026-02-15</lastmod>
  <changefreq>monthly</changefreq>  <!-- Google largely ignores this -->
  <priority>0.8</priority>          <!-- Google largely ignores this -->
</url>
```

**Note**: Google has confirmed it ignores `changefreq` and `priority` in most cases. Keep them for completeness but do not rely on them.

### Sitemap Submission

1. Add to `robots.txt`: `Sitemap: https://site.com/sitemap.xml`
2. Submit in Google Search Console: Sitemaps report → Enter sitemap URL → Submit
3. Submit in Bing Webmaster Tools (separate from GSC)
4. Resubmit sitemap after major structural changes

---

## Canonicalization

### The Canonical Tag

```html
<link rel="canonical" href="https://site.com/the-canonical-url/" />
```

**Rules:**
- Every indexable page should have a self-referencing canonical
- Canonical must be an absolute URL (including protocol and domain)
- Canonical should always use HTTPS
- Canonical must match exactly (trailing slash consistency matters)

### Canonical Decision Tree

```
Is this the primary URL for this content?
├── YES → Self-referencing canonical
└── NO → What is the primary URL?
    ├── Known → Canonical points to primary URL
    └── Unknown → Fix URL structure first, then set canonical
```

### Duplicate Content Scenarios & Fixes

| Scenario | Problem URL | Canonical Fix |
|---|---|---|
| www vs. non-www | `http://www.site.com/page` | Canonical → `https://site.com/page` + 301 redirect |
| HTTP vs. HTTPS | `http://site.com/page` | 301 redirect to HTTPS + canonical on HTTPS page |
| Trailing slash variants | `/page` and `/page/` | Pick one, 301 the other, canonical = chosen version |
| Faceted navigation | `/shoes?color=red&size=8` | Canonical → `/shoes/` (master category) |
| Syndicated content | Your article on third-party site | Third-party page should canonical → your original |
| Paginated series | `/blog/page/2` | Options: (a) Noindex + canonical → page 1; (b) Noindex paginated, keep page 1 indexed |
| URL parameters | `/page?ref=newsletter` | Canonical → clean URL; configure in GSC params tool |

### Canonical Conflicts to Avoid

- **Noindex + Canonical conflict**: If a page has `noindex` AND a canonical pointing to another page — Google may still not index the target. Fix: use canonical only, remove noindex.
- **Redirect chain canonicals**: Canonical pointing to a URL that 301 redirects elsewhere — Google follows the chain but it wastes budget. Canonical should point to the final destination.
- **JS-injected vs. HTML canonical mismatch**: If raw HTML canonical ≠ JS-injected canonical, Google may use either. Always match them (see technical-checklist.md for full JS guidance).
- **Canonical chain (A → B → C)**: Page A canonicalizes to B, but B canonicalizes to C. Google follows the chain and may choose C, overriding your intent. Always have canonical targets use self-referencing canonicals.

### "Google Chose Different Canonical" — Diagnosis & Fix

When GSC reports "Duplicate, Google chose different canonical than user" (Page Indexing report):

**Automated detection**: Run `scripts/canonical_checker.py URL` for the affected page, or `--crawl` for site-wide audit.

**Step 1: Check the affected URL**
- Fetch the page and inspect its `<link rel="canonical">` tag
- Check if the canonical URL actually resolves to 200 (not 404, not redirect)
- Check if the canonical target's own canonical is self-referencing

**Step 2: Check common causes**

| Cause | How to Detect | Fix |
|---|---|---|
| www and non-www both accessible | Access both `www.site.com/page` and `site.com/page` — both return 200 | 301 redirect one to the other; update canonical to match |
| HTTP and HTTPS both accessible | Access both `http://` and `https://` — both return 200 | 301 redirect HTTP → HTTPS; add HSTS |
| Trailing slash variant exists | Both `/page` and `/page/` return 200 with same content | Pick one, 301 redirect the other |
| Canonical URL redirects | HEAD request on canonical URL shows 3xx | Update canonical to the final destination |
| Canonical URL returns 404 | HEAD request on canonical URL shows 404 | Fix the target page or update canonical |
| Near-duplicate page exists | Run `duplicate_content.py` — high similarity pair found | Differentiate content or use canonical + 301 redirect |
| Multiple canonical tags | View source — two or more `<link rel="canonical">` | Remove duplicates, keep one |
| Internal links favor different URL | Most internal links point to a different URL than the canonical | Align internal links with the canonical URL |

**Step 3: Validate the fix**
- After fixing, use GSC URL Inspection → "Request Indexing" on the affected URL
- Click "Validate Fix" in the GSC Page Indexing report
- Monitor for 7-28 days until validation completes

---

## Log File Analysis

### Why Log Analysis Matters

Server logs reveal what Googlebot *actually* crawled — not what you think it crawled. Essential for diagnosing:
- Which pages are never crawled despite being in sitemap
- Which pages waste crawl budget (e.g., 404 pages being retried)
- Crawl frequency patterns by page type
- Whether Googlebot uses mobile or desktop user agent (should be mobile since July 2024)

### Log Analysis Setup

**Tools**: Screaming Frog Log File Analyser, Botify, Semrush Log File Analyser, Ahrefs (limited), custom Python/Pandas

**What to look for in logs:**

```python
# Filter for Googlebot requests only
# Googlebot user-agent: "Googlebot/2.1 (+http://www.google.com/bot.html)"
# Googlebot mobile: "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X...) Googlebot/2.1"

# Key columns: datetime, url, status_code, user_agent, response_time
```

### Log Analysis Report Framework

| Report | What to Extract |
|---|---|
| **Crawl frequency** | Which pages get crawled daily vs. weekly vs. monthly? |
| **Status code distribution** | % 200, % 301, % 404, % 5xx from Googlebot |
| **Crawl waste** | URLs with 4xx/5xx being repeatedly retried → add to robots.txt or fix |
| **Uncrawled pages** | URLs in sitemap that don't appear in logs → internal linking problem |
| **Crawl depth correlation** | Pages at depth 4+ often appear rarely in logs → restructure navigation |
| **Bot type ratio** | Smartphone Googlebot vs. Desktop Googlebot (should be predominantly smartphone since July 2024) |

### Sample Log Insights → Actions

| Log Finding | Likely Cause | Fix |
|---|---|---|
| 40% of crawl on 404 pages | Broken internal links / old URLs | Fix internal links; 301 redirect old URLs |
| High-value pages crawled < weekly | Low internal PageRank | Add internal links from high-authority pages |
| Bot crawling `/wp-admin` | robots.txt not blocking admin | Add `Disallow: /wp-admin/` to robots.txt |
| Only desktop Googlebot seen | Possible verification issue | Investigate; confirm mobile-first indexing in GSC |
| Crawl rate spikes then drops | Server throttling | Optimize server response time (TTFB) |

---

## Indexation Health Checks

### Monthly Indexation Audit

1. **Site command check**: `site:yourdomain.com` in Google — gives rough estimate (not precise)
2. **GSC Coverage report**: Track Valid, Errors, Warnings, Excluded counts month-over-month
3. **GSC "Not found (404)" report**: Check Page Indexing → "Not found (404)" for pages Google tried to index but got 404. Cross-reference with sitemap — any 404 URL in sitemap is a critical fix.
4. **Sitemap URL health check**: Run `scripts/sitemap_checker.py --sample 50` (or `--check-all` for smaller sites). Validates that sitemap URLs actually return HTTP 200. Catches 404s, soft 404s, 5xx errors, and redirects before they appear in GSC.
5. **GSC "Page with redirect"**: Run `scripts/internal_links.py` to find internal links that point to URLs returning 3xx. These stale links waste crawl budget. Fix: update all internal links to point to the final destination URL and remove redirect URLs from sitemap.
6. **GSC "Alternate page with proper canonical"**: Run `scripts/canonical_checker.py --crawl` to find pages where the canonical tag points to a different URL. Google treats these as duplicates. If the page has unique content, change canonical to self-referencing. If truly duplicate, 301 redirect.
7. **Sitemap submitted vs. indexed ratio**: > 20% gap between submitted and indexed = quality issue
6. **"Crawled - not indexed" cluster**: Group by page type — if blog posts dominate, content quality audit needed
7. **Search/template URL hygiene**: Check sitemap for search result URLs (`?q=`, `?search=`, `{search_term_string}`) and faceted/filtered URLs. These must be removed from sitemap and marked noindex.

### Indexation Ratio Benchmarks

| Sitemap Submitted / Indexed Ratio | Interpretation |
|---|---|
| > 90% | Healthy |
| 70-90% | Acceptable; investigate excluded pages |
| 50-70% | Content quality or technical issue |
| < 50% | Significant indexation problem — prioritize |

### GSC "Not Found (404)" Remediation Playbook

When Google Search Console reports pages as "Not found (404)" under Page Indexing:

**Step 1: Categorize each 404 URL**

| URL Pattern | Category | Example |
|---|---|---|
| Product/content page | Deleted or moved content | `/brands/some-brand`, `/buy/product-name` |
| Location/directory page | Removed listing | `/churches/state/church-name` |
| Search result URL | Indexation hygiene issue | `/search?q={search_term_string}` |
| Parameter URL | Faceted/filtered page | `/products?color=red&size=M` |
| Unknown/typo URL | External link with wrong URL | `/misspelled-page-name` |

**Step 2: Apply the correct fix per category**

| Category | Fix | Priority |
|---|---|---|
| **Content moved** | 301 redirect to new URL; update sitemap; fix internal links | Critical |
| **Content deleted** | Return 404 or 410; remove from sitemap; remove all internal links to it | High |
| **Search/template URL** | Remove from sitemap; add `<meta name="robots" content="noindex">` to all search result pages; add `Disallow: /search` to robots.txt | Critical |
| **Faceted URL** | Remove from sitemap; canonical → master category; consider noindex | High |
| **External link typo** | If high-authority link, 301 redirect to correct page; otherwise let 404 stand | Medium |
| **Page should exist** | Fix the application bug; restore the page; ensure 200 response | Critical |

**Step 3: Validate the fix**
- Use URL Inspection tool in GSC to request re-crawl of fixed URLs
- After fixing, click "Validate Fix" in GSC → Page Indexing → "Not found (404)"
- Monitor: validation takes 7-28 days; re-check after validation completes

### GSC "Page with redirect" Remediation Playbook

When GSC reports pages as "Page with redirect" under Page Indexing, these URLs return 3xx when crawled. Google won't index them.

**Automated detection:** `scripts/internal_links.py` finds internal links to redirect URLs during crawl, with source-page tracing. `scripts/sitemap_checker.py --sample 50` catches redirect URLs in the sitemap.

**Step 1: Identify sources of stale links**
- Internal links still pointing to old URLs that now redirect
- Sitemap entries listing redirect URLs instead of final destinations
- Hard-coded URLs in navigation, footer, or content that haven't been updated

**Step 2: Apply fixes**

| Cause | Fix | Priority |
|---|---|---|
| **Internal links to old URL** | Update href to the final destination URL site-wide | Critical |
| **Sitemap contains redirect URL** | Replace with final destination URL in sitemap | Critical |
| **URL structure migration** | Ensure redirects are 301 (permanent); update all internal links to new structure | High |
| **HTTP → HTTPS redirect** | Change all internal links to `https://`; update sitemap | High |
| **Non-www → www redirect (or vice versa)** | Standardize all internal links to the preferred domain version | High |

**Step 3: Validate**
- Request re-crawl via URL Inspection in GSC
- Click "Validate Fix" in GSC → Page Indexing → "Page with redirect"
- Monitor: 7-28 days for validation to complete

### GSC "Alternate page with proper canonical tag" Remediation Playbook

When GSC reports pages as "Alternate page with proper canonical tag" under Page Indexing, these pages have a canonical tag pointing to a different URL. Google recognizes the canonical and doesn't index the alternate.

**Automated detection:** `scripts/canonical_checker.py --crawl` finds all non-self-referencing canonicals with aggregate statistics. `scripts/duplicate_content.py` identifies near-duplicate content with canonical cross-referencing.

**Step 1: Determine if the alternate status is intentional**

| Scenario | Expected? | Action |
|---|---|---|
| Paginated series (`/blog/page/2` → `/blog`) | Yes | Normal behavior — no fix |
| AMP page canonicalizing to desktop | Yes | Normal behavior — no fix |
| Parameter variant (`?ref=source` → base) | Usually yes | Verify canonical target has best content |
| Unique content page misconfigured | No | Fix canonical to self-referencing |
| CMS defaulting all pages to homepage canonical | No | Fix CMS canonical logic — each page should self-canonical |
| Near-duplicate pages both should exist | Depends | Differentiate content or consolidate into one page |

**Step 2: Apply fixes for unintentional alternates**
- Change canonical to self-referencing on pages with unique content
- Differentiate content if pages are too similar (>85% similarity)
- Fix CMS/theme canonical configuration if mass-misconfigured
- If page is truly duplicate: 301 redirect to canonical target (stronger signal)

**Step 3: Validate**
- Request re-crawl via URL Inspection in GSC
- Click "Validate Fix" in GSC → Page Indexing → "Alternate page with proper canonical tag"
- Monitor: 14-28 days — canonical changes take longer to process than redirect fixes

### Recovery Playbook: Sudden Indexation Drop

1. **Check GSC for manual action** (Security & Manual Actions → Manual Actions)
2. **Check algorithm update calendar** — did Google release an update in the 7 days prior?
3. **Check server logs** — did crawl rate drop? Server errors spike?
4. **Check for mass noindex or robots.txt change** — deployment accident?
5. **Check canonicalization** — mass canonical changes can trigger de-indexation
6. **Check for site migration or SSL change** — redirecting to HTTP accidentally?

---

## International SEO: hreflang

For sites serving multiple languages or regions.

### hreflang Tag Syntax

```html
<!-- In <head> of each language variant -->
<link rel="alternate" hreflang="en" href="https://site.com/en/page/" />
<link rel="alternate" hreflang="en-GB" href="https://site.com/en-gb/page/" />
<link rel="alternate" hreflang="fr" href="https://site.com/fr/page/" />
<link rel="alternate" hreflang="x-default" href="https://site.com/page/" />
```

**Rules:**
- Always include `x-default` hreflang for the default/fallback version
- Every page in the cluster must reference all other pages (reciprocal)
- Use ISO 639-1 language codes (en, fr, de) and optionally ISO 3166-1 region codes (en-GB, fr-CA)
- Can also implement via XML sitemap or HTTP headers

### hreflang Implementation Options

| Method | Best For | Complexity |
|---|---|---|
| HTML `<head>` tags | Most sites | Low |
| XML Sitemap | Large sites, JS-heavy | Medium |
| HTTP headers | PDFs, non-HTML resources | High |

### Common hreflang Errors

- Missing reciprocal tags (page A references B but B doesn't reference A) → Google ignores the tag
- Wrong language code (`en-UK` instead of `en-GB`) → tag ignored
- hreflang pointing to redirected or 404 URL → crawl waste
- hreflang on noindex page → avoid (noindex signals not to follow)

---

## Crawl & Indexation Scoring

| Dimension | Excellent | Good | Needs Work |
|---|---|---|---|
| Sitemap quality | 100% canonical URLs, auto-updated | Mostly clean, manual updates | Includes noindex / redirect URLs |
| Canonical implementation | All pages self-canonical, no conflicts | Mostly correct | Missing canonicals or conflicts |
| Crawl waste | < 5% of crawl budget on non-200 | 5-15% | > 15% |
| Index ratio | > 90% submitted = indexed | 70-90% | < 70% |
| Pagination handling | Clean noindex or canonical strategy | Partial | Duplicate paginated pages indexed |
| Hreflang (if multi-lang) | Reciprocal, validated, x-default | Partially implemented | Errors or missing |
