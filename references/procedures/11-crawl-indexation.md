> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

## 11. Crawl & Indexation

**Rule of thumb**: Crawl budget rarely matters for sites under 500 pages. Focus on content quality first.

### Indexation Audit — Step by Step

1. `site:domain.com` in Google. Large discrepancy = investigation needed.
2. **GSC Coverage** — "Crawled - currently not indexed" (thin content) and "Submitted URL not indexed." Check "Not found (404)" for pages Google tried to index but got 404. **Week over week:** export Page indexing each week (the report is not in the API) and run `python scripts/index_coverage_diff.py last-week.zip this-week.zip --shipped shipped.txt`. It reports only reasons that moved (≥50 URLs, or ≥5% on ≥10 URLs), sorts them into technical (robots.txt, noindex, 4xx/5xx: the site blocks Google), quality ("Crawled - currently not indexed", duplicates: Google declined; resubmitting does nothing), discovery ("Discovered - currently not indexed") and expected (redirects, alternates), ties each move to the shipped notes, and names one reason to investigate: technical rises first, then a fall in Indexed. `--examples OLD.csv NEW.csv --sitemap URL` lists the example URLs that entered a reason and which of them are submitted in the sitemap; Search Console caps those lists at 1,000, so treat them as a sample.
3. **Sitemap URL health** — Run `scripts/sitemap_checker.py` with URL sampling. Every sitemap URL must return 200. Flag: 404s, 5xx errors, soft 404s, redirects in sitemap. Note: `<priority>` and `<changefreq>` tags are ignored by Google and Bing — omit them from new sitemaps; they add size without benefit.
4. **Search/template URL indexation** — Check sitemap for search result URLs (`?q=`, `?search=`, `{search_term_string}`) and faceted URLs (`?sort=`, `?filter=`). These must never appear in sitemaps. Fix: remove from sitemap, add `<meta name="robots" content="noindex">`, block in robots.txt.
5. **Soft 404 detection** — Run `scripts/broken_links.py` to detect pages returning HTTP 200 but showing "not found" content. Fix: return real 404/410 or restore genuine content.
6. **Site-wide broken internal links** — Run `scripts/broken_links.py --crawl` or `scripts/internal_links.py` to find internal pages returning 404/5xx. Each broken internal link wastes crawl budget and breaks link equity.
7. **Pages with redirect** — Run `scripts/internal_links.py` to find internal links pointing to URLs that redirect. GSC reports these as "Page with redirect." Fix: update all internal links to point to the final destination URL. Remove redirect URLs from the sitemap.
8. **Alternate page detection** — Run `scripts/canonical_checker.py --crawl` to find pages with non-self-referencing canonicals. GSC reports these as "Alternate page with proper canonical tag." If these pages have unique content that should be indexed, change their canonical to self-referencing. If they are true duplicates, 301 redirect to the canonical target.
9. **Canonical conflicts** — No page with both `noindex` and a canonical tag.
10. **URL parameter handling** — Parameter variants must canonical to master page.

### GSC "Not Found (404)" Remediation

When GSC reports pages as "Not found (404)", apply this decision tree per URL:

| Scenario | Action |
|---|---|
| Content moved to new URL | Add 301 redirect old → new; update sitemap and internal links |
| Content permanently deleted | Return 404 or 410; remove from sitemap; remove internal links |
| Content should exist but is broken | Fix the page; ensure it returns 200 |
| Search/template URL (e.g. `?q={search_term_string}`) | Remove from sitemap; add noindex to search pages; block crawling via robots.txt |
| URL was never valid (typo, outdated) | Let 404 stand; remove from sitemap; fix any internal links pointing to it |

### GSC "Page with redirect" Remediation

When GSC reports pages as "Page with redirect" — these URLs redirect (301/302) when crawled, so Google won't index them.

| Root Cause | Detection | Fix |
|---|---|---|
| URL was moved, old URL redirects | `scripts/internal_links.py` detects redirect pages during crawl | Update all internal links to point to the final destination URL |
| Sitemap contains redirect URLs | `scripts/sitemap_checker.py --sample 50` flags redirected URLs | Remove redirect URLs from sitemap; add only final destination URLs |
| URL structure changed | Redirect chain from old → new path pattern | Update internal links site-wide; redirect map stays as safety net |
| HTTP → HTTPS redirect | HTTP version still linked internally | Update all internal links to HTTPS |

### GSC "Alternate page with proper canonical tag" Remediation

When GSC reports pages as "Alternate page with proper canonical tag" — these pages have a canonical tag pointing to a different URL. Google treats them as duplicates and doesn't index them.

| Root Cause | Detection | Fix |
|---|---|---|
| Intentional duplicate (correct) | Page is a true duplicate of the canonical target | No fix needed — or 301 redirect to canonical target for a cleaner signal |
| Unintentional duplicate (wrong canonical) | Page has unique content but canonical points elsewhere | Change canonical to self-referencing; differentiate content from similar pages |
| CMS/theme auto-canonical misconfiguration | Many pages all canonicalize to homepage or a single URL | Fix CMS canonical settings; ensure each page canonicalizes to itself |
| Parameter variants auto-canonicalized | `/page?ref=source` canonicalizes to `/page` | Expected behavior — verify the canonical target has the best content |
| Near-duplicate content | `scripts/duplicate_content.py` finds > 85% similarity | Differentiate content significantly or consolidate pages |

### Canonical Validation — Step by Step

1. **Run canonical check** — `scripts/canonical_checker.py URL` for single page, `--crawl` for site-wide.
2. **Self-referencing check** — Every indexable page should have a self-referencing canonical. Non-self canonical = intentional duplicate declaration.
3. **Absolute URL check** — Canonical must be absolute (include protocol + domain). Relative URLs are unreliable.
4. **Protocol consistency** — Canonical must match the page's protocol (HTTPS canonical on HTTPS page).
5. **www/non-www consistency** — Canonical domain must match the page domain. Mismatch = #1 cause of "Google chose different canonical."
6. **Trailing slash consistency** — Page URL and canonical must agree on trailing slash convention.
7. **Canonical target resolves** — The canonical URL must return HTTP 200. Canonical → 404 or redirect = Google ignores it.
8. **No canonical chains** — The canonical target's own canonical should be self-referencing. If A → B → C, Google picks C and ignores your preference.
9. **No noindex + canonical conflict** — Never combine `<meta name="robots" content="noindex">` with a non-self canonical. Use one or the other.
10. **Single canonical tag** — Only one `<link rel="canonical">` per page. Multiple tags = unpredictable behavior.

### GSC "Google Chose Different Canonical" Remediation

When GSC reports "Duplicate, Google chose different canonical than user":

| Root Cause | Detection | Fix |
|---|---|---|
| www vs. non-www both accessible | `canonical_checker.py --crawl` detects www mismatch | 301 redirect one variant to the other site-wide |
| Trailing slash variant | Same path with/without trailing slash both return 200 | Pick one, 301 redirect the other, canonical = chosen |
| HTTP + HTTPS both accessible | Both `http://` and `https://` return 200 | Force HTTPS via 301; HSTS header |
| Near-duplicate content | `duplicate_content.py` detects > 85% similarity | Differentiate content or consolidate with canonical + 301 |
| Canonical points to redirect | `canonical_checker.py` detects this | Update canonical to final destination URL |
| Canonical points to 404 | `canonical_checker.py` detects this | Fix the target URL or update canonical |
| Multiple canonical tags | `canonical_checker.py` detects this | Remove duplicates; keep only one |
| Canonical chain (A → B → C) | `canonical_checker.py` detects target's canonical | Update A's canonical to C directly |

### Key Canonical Rules

| Scenario | Fix |
|---|---|
| www vs. non-www | 301 redirect one to the other + canonical |
| HTTP vs. HTTPS | 301 redirect HTTP → HTTPS |
| URL parameters | Canonical → master page |
| noindex + canonical conflict | Use one or the other — never both |

**Sitemap health**: submitted/indexed ratio >90% = healthy; <70% = investigate content quality or canonicalization.

→ See `references/crawl-indexation.md` | Run `scripts/sitemap_checker.py --sample 50` Run `scripts/canonical_checker.py --crawl` Run `scripts/internal_links.py` Run `scripts/broken_links.py --crawl`
