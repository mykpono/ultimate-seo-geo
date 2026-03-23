<!-- Updated: 2026-03-23 | Review: 2026-09-23 -->

# Site Migration SEO Checklist
## Updated: March 2026

A site migration is any change that risks altering how Google crawls, indexes, or ranks your pages. The biggest risk is losing organic traffic by forgetting a step.

**Migration types covered:**
- Domain change (example.com → newdomain.com)
- HTTP → HTTPS upgrade
- URL restructure (path changes without domain change)
- Platform migration (WordPress → Webflow, Squarespace → custom, etc.)
- Combining or splitting sites
- Subdomain ↔ subdirectory consolidation

---

## Pre-Migration: 6 Steps (Do Before Launch)

### Step 1: Full URL Crawl Baseline
Capture the full current URL inventory so you have a source of truth for every URL that needs a redirect.

**Tools:** Screaming Frog, Sitebulb, or `scripts/crawl_urls.py`

**What to capture:**
- All indexable URLs (HTTP 200, in sitemap, not noindex)
- URL → Title → H1 → Meta description mapping
- Inbound link counts per URL (from Google Search Console → Links report)
- Current organic traffic per URL (Google Analytics or Search Console → Performance → Pages)

**Save as:** `migration-baseline.csv`

> Never skip this step. Without a baseline, you can't verify that every high-traffic page has a redirect, and you can't diagnose post-migration traffic drops.

---

### Step 2: Build the Redirect Map

Map every old URL to its new URL. Prioritize by traffic and backlink equity.

**Priority tiers:**
| Tier | Criteria | Treatment |
|---|---|---|
| P1 | > 100 organic visits/month OR > 5 backlinks | Must have 301 redirect |
| P2 | < 100 visits/month, some backlinks | 301 redirect |
| P3 | No traffic, no backlinks | 301 redirect or allow to 404 |

**Rules:**
- Use 301 (permanent) for all content moves — never 302 for migrations
- Map to the most topically relevant new page, not always the homepage
- Avoid redirect chains: old → new (1 hop maximum); never old → intermediate → new
- If a page has no equivalent, map to the closest parent category

**Format:** Two-column CSV: `old_url, new_url`

---

### Step 3: Staging Environment Verification

Before launch, deploy to staging and check:

- [ ] All new URLs return HTTP 200
- [ ] All redirect mappings return 301 with correct destination
- [ ] Canonical tags point to the new domain/path
- [ ] Meta robots: no accidental `noindex` in staging that could leak to production
- [ ] XML sitemap updated with new URLs only (no old URLs, no staging URLs)
- [ ] robots.txt updated: staging should block all crawlers (`Disallow: /`); production should allow them
- [ ] Internal links updated throughout the site (no lingering references to old URLs)
- [ ] Schema markup updated: `@id`, `url`, `logo` properties point to new domain
- [ ] hreflang tags updated (if applicable)
- [ ] Google Analytics and Search Console tracking codes present

---

### Step 4: Pre-Migration Search Console Setup

- [ ] Verify ownership of the new domain in Google Search Console
- [ ] Submit new XML sitemap to new property
- [ ] For domain migrations: use the **Change of Address** tool (Settings → Change of Address) — this sends a strong signal to Google to re-crawl under the new domain
- [ ] Note: Change of Address only works for root domain changes (not subdirectory restructures)

---

### Step 5: Backlink Inventory

Pull all backlinks pointing to the old domain. These links are your most valuable equity — verify that critical backlinks will pass through the 301 redirect.

**Sources:**
- Google Search Console → Links → Top linking sites
- Ahrefs, Semrush, or CommonCrawl API (`https://index.commoncrawl.org/collinfo.json`)
- Moz Link Explorer

**Action:** For the top 20 referring domains, reach out post-migration to request direct link updates to the new URLs. 301s pass equity, but direct links are better.

---

### Step 6: Performance Baseline

Capture Core Web Vitals, page speed scores, and crawl budget estimates before the migration so you have a comparison point afterward.

- Run PageSpeed Insights on top 10 pages (or `scripts/pagespeed.py`)
- Export CrUX data from Search Console (Core Web Vitals report)
- Note current crawl rate from Search Console → Crawl Stats

---

## Migration Day: 5 Steps

### Step 1: Deploy and Verify Redirects Go Live
Immediately after launch, spot-check 10–20 redirect mappings:

```bash
curl -I https://olddomain.com/old-path/
# Expect: HTTP/1.1 301 Moved Permanently
# Location: https://newdomain.com/new-path/
```

Check redirect chains: `curl -L -I` should resolve in ≤ 2 hops.

### Step 2: Submit Updated Sitemap
- Submit new sitemap to Google Search Console
- Submit to Bing Webmaster Tools (separate property required)
- If using IndexNow: submit all new URLs via IndexNow API for faster Bing indexation

### Step 3: Request Indexing on Critical Pages
In Google Search Console → URL Inspection → Request Indexing, manually request indexing for the top 5–10 most important new URLs. This is not a guarantee but prioritizes those URLs in the crawl queue.

### Step 4: Verify robots.txt
Confirm production robots.txt:
- Does NOT have `Disallow: /` (a common migration mistake when copying staging config)
- References new sitemap URL
- Allows all major crawlers (Googlebot, Bingbot, OAI-SearchBot, PerplexityBot, ClaudeBot)

### Step 5: Monitor Real-Time Crawl
Watch Google Search Console → Coverage report for the first 24–48 hours. Look for sudden spikes in:
- 404 errors (redirect map gaps)
- Redirect errors (chains or loops)
- Noindex pages (accidental noindex directive)

---

## Post-Migration: Monitoring Schedule

| Timeline | What to Check | Tool |
|---|---|---|
| Day 1–3 | 404 errors, redirect errors, crawl rate | GSC Coverage, server logs |
| Day 1–7 | Impressions and clicks (expect dip, then recovery) | GSC Performance |
| Week 1–2 | Core Web Vitals field data appearing | GSC Core Web Vitals |
| Week 2–4 | Ranking positions for target keywords | GSC Performance → Queries |
| Month 1–3 | Organic traffic vs. pre-migration baseline | Google Analytics |
| Month 3–6 | Full traffic recovery expected for clean migrations | GA + GSC |
| Month 6+ | Remove old domain hosting (if full domain migration) | — |

**What's normal:**
- A 10–30% temporary traffic dip in weeks 1–3 is normal, especially for large sites
- Full recovery typically takes 3–6 months for domain migrations
- HTTPS-only migrations with no URL changes: usually minimal disruption
- Platform migrations with URL restructures: 3–6 months for full recovery

**Red flags (investigate immediately):**
- > 50% traffic drop in week 1 → likely redirect map gaps or accidental noindex
- Crawl rate drops to near zero → robots.txt likely blocking Googlebot
- New URLs not appearing in index after 4 weeks → canonical or noindex issue

---

## Common Migration Mistakes

| Mistake | Impact | Fix |
|---|---|---|
| Using 302 instead of 301 | Google may not transfer link equity | Change to 301 immediately |
| Redirect chains (A→B→C) | Equity loss, crawl budget waste | Flatten to single-hop (A→C) |
| Forgetting to update internal links | Wasted crawl budget on redirects | Run post-migration crawl; update links |
| Staging robots.txt deployed to production | Googlebot blocked entirely | Check robots.txt immediately |
| Forgetting to update schema `@id` and `url` | Entity confusion, broken rich results | Update all JSON-LD with new domain |
| Not submitting Change of Address | Slower re-crawl and re-indexation | Submit in Search Console → Settings |
| Mapping everything to homepage | Link equity dilution | Map to topically relevant page |
| Updating canonical tags but not redirect | Soft 404 signals | Both must point to new URL |
| Missing hreflang updates | Hreflang loop errors | Update all language variants simultaneously |
| Launching without baseline | Can't diagnose post-migration drops | Always baseline before launch |

---

## Platform-Specific Notes

### WordPress migrations
- Update WordPress Site URL in Settings → General (both Site Address and WordPress Address)
- Use Search & Replace in database to update all internal links and image paths
- Plugin: Better Search Replace or WP Migrate handles database URL updates

### Shopify / Wix / Webflow migrations
- Export-to-custom-domain: use platform's domain connection, not frame embedding
- Shopify: redirect app (e.g., Easy Redirects) handles 301s for product URL changes
- Platform-hosted to self-hosted: must manually redirect each old platform URL

### SPA / Next.js / React
- Ensure redirects are handled at server level (nginx, Vercel rewrites, Cloudflare) — not client-side only
- Client-side redirects (React Router) are invisible to Googlebot until JavaScript renders

---

## Redirect Map Validation Script

```python
# Quick redirect validation (run from command line)
# Usage: python validate_redirects.py migration-map.csv

import csv, requests, sys

with open(sys.argv[1]) as f:
    rows = list(csv.reader(f))

errors = []
for old_url, expected_new in rows[1:]:
    r = requests.get(old_url, allow_redirects=True, timeout=10)
    final = r.url.rstrip('/')
    expected = expected_new.rstrip('/')
    if final != expected:
        errors.append(f"FAIL: {old_url} → {final} (expected {expected})")

if errors:
    print('\n'.join(errors))
    sys.exit(1)
else:
    print(f"All {len(rows)-1} redirects validated.")
```
