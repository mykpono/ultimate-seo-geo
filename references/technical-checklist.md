<!-- Updated: 2026-03-22 | Review: 2026-09-22 -->

# Technical SEO Checklist
## Updated: March 2026

**Contents:** Core Web Vitals Thresholds · How to Fix CWV · 9-Category Technical Audit · AI Crawler Configuration · Technical SEO Scoring · Detailed CWV Fix Steps · LCP Subparts · IndexNow · Critical Technical Issues · JavaScript SEO Clarifications

---

## Core Web Vitals Thresholds

**IMPORTANT: INP replaced FID on March 12, 2024. FID was fully removed from all Chrome tools on September 9, 2024. Never reference FID.**

| Metric | Good | Needs Improvement | Poor |
|---|---|---|---|
| **LCP** (Largest Contentful Paint) | < 2.5s | 2.5s – 4.0s | > 4.0s |
| **INP** (Interaction to Next Paint) | < 200ms | 200ms – 500ms | > 500ms |
| **CLS** (Cumulative Layout Shift) | < 0.1 | 0.1 – 0.25 | > 0.25 |

Measured at **75th percentile** of real user data. Use PageSpeed Insights (CrUX) or field data; lab data is directional only.

### AI Search & Page Speed Correlation
Pages with FCP (First Contentful Paint) < 0.4s average **6.7 AI citations**; slower pages average only **2.1 citations** (3× difference). Page speed is a GEO factor, not just a ranking factor.

---

## How to Fix Core Web Vitals

Each metric has distinct causes and fixes. Diagnose first, then apply the most impactful solutions.

### LCP (Largest Contentful Paint)
**What it is:** Time until the largest visible element (image, heading, block of text) renders. Measures initial page load perception.

**How to diagnose:**
- Use PageSpeed Insights → CrUX or field data (real users); check 75th percentile
- Chrome DevTools Lighthouse → Performance tab shows LCP element
- Check Network tab for which resource is rendering last as LCP

**3 most common fixes:**
1. **Optimize hero images**: Compress (use WebP), resize for viewport, add `rel="preload"` on critical images, use responsive srcset for different screen sizes
2. **Reduce server response time (TTFB)**: Use CDN, add caching headers (Cache-Control), optimize database queries, upgrade hosting if TTFB > 600ms
3. **Remove render-blocking resources**: Defer non-critical CSS/JavaScript in `<head>`, move scripts to end of `<body>` or use `async`/`defer` attributes

### INP (Interaction to Next Paint)
**What it is:** Time from user interaction (click, tap, keystroke) until the browser paints the response. Measures responsiveness during user actions.

**How to diagnose:**
- PageSpeed Insights → CrUX field data shows INP by user action
- Chrome DevTools → Interactions tab (DevTools recorder) shows which interactions are slow
- Look for "long tasks" in Performance tab (> 50ms JavaScript execution)

**3 most common fixes:**
1. **Break up long JavaScript tasks**: Split expensive computations into smaller chunks; use `requestIdleCallback()` or web workers for background processing
2. **Defer or lazy-load third-party scripts**: Move analytics, ads, chat widgets to load after interaction-critical code; use `loading="lazy"` for iframes
3. **Optimize event listeners**: Debounce input handlers (search, resize), avoid heavy operations in scroll/mousemove handlers, use event delegation for many elements

### CLS (Cumulative Layout Shift)
**What it is:** Sum of all unexpected layout shifts (without user input) during page load and interaction. Measures visual stability.

**How to diagnose:**
- PageSpeed Insights shows CLS score with list of shifting elements
- Chrome DevTools → Performance tab with "Layout Shift" events highlighted
- Look for which elements move after initial render

**3 most common fixes:**
1. **Reserve space for images and embeds**: Always include `width` and `height` attributes on images; use CSS aspect-ratio for videos/iframes; avoid width/height on dynamic content
2. **Font loading strategy**: Use `font-display: swap` (show fallback first, replace when font loads) instead of `font-display: block` (invisible text)
3. **Ads and dynamic content**: Reserve space with padding/min-height before ads/popups load; don't inject content above existing content without accounting for space

---

## 9-Category Technical Audit

### 1. Crawlability

**robots.txt**
- [ ] File exists at `/robots.txt`
- [ ] Does not block Googlebot, Bingbot, or key crawlers
- [ ] References XML sitemap(s)
- [ ] AI crawlers configured (see Section below)

**XML Sitemap**
- [ ] File exists at `/sitemap.xml`
- [ ] Referenced in robots.txt
- [ ] All key URLs included
- [ ] Only canonical URLs (no duplicates or noindex pages)
- [ ] Updated automatically (via CMS) or manually when publishing
- [ ] Submitted to Google Search Console and Bing Webmaster Tools

**Crawl Depth**
- [ ] All important pages reachable within 3 clicks of homepage
- [ ] No orphan pages (pages with zero internal links pointing to them)
- [ ] Internal linking connects related content

**JavaScript Rendering**
- [ ] Critical content visible in raw HTML (not JS-only)
- [ ] Check by fetching page source with JS disabled
- [ ] React/Vue/Angular SPAs: verify dynamic rendering or SSR setup

### 2. Indexability

**Canonical Tags**
- [ ] Every page has a self-referencing canonical
- [ ] No conflicts between canonical and noindex
- [ ] www and non-www redirect to single canonical domain
- [ ] HTTPS enforced (no canonical pointing to HTTP version)

**Duplicate Content**
- [ ] Pagination handled properly (noindex on paged archives, or proper canonical)
- [ ] URL parameters not creating duplicate pages
- [ ] Near-duplicate content addressed with canonical or consolidation

**Index Bloat**
- [ ] No unnecessary pages consuming crawl budget (thin tag pages, infinite scroll artifacts, faceted navigation pages)
- [ ] 404 errors addressed
- [ ] Soft 404s addressed — pages returning HTTP 200 status but showing "not found" or empty content (detect via Google Search Console Coverage report: "Crawled - currently not indexed")

**Hreflang** (multi-language/region sites)
- [ ] hreflang tags correct if site serves multiple languages/regions
- [ ] x-default hreflang specified

### 3. Security

- [ ] HTTPS enforced with valid SSL certificate
- [ ] No mixed content warnings (HTTP resources on HTTPS page)
- [ ] HSTS header present
- [ ] Security headers present:
  - Content-Security-Policy (CSP)
  - Strict-Transport-Security (HSTS)
  - X-Frame-Options (or CSP frame-ancestors)
  - X-Content-Type-Options: nosniff
  - Referrer-Policy
- [ ] No sensitive files exposed (/.env, /backup, /config)

### 4. URL Structure

- [ ] Clean, descriptive URLs (hyphens, lowercase, no special characters)
- [ ] Logical folder hierarchy reflecting site architecture
- [ ] No redirect chains (max 1 hop; 301 for permanent)
- [ ] No URL length > 100 characters
- [ ] Consistent trailing slash policy

### 5. Mobile Optimization

**Mobile-first indexing is 100% complete as of July 5, 2024.** Google now crawls ALL websites exclusively with the mobile Googlebot user-agent.

- [ ] Responsive design with viewport meta tag
- [ ] Touch targets ≥ 48×48px with 8px spacing
- [ ] Base font size ≥ 16px
- [ ] No horizontal scroll on mobile
- [ ] Content identical between desktop and mobile (Google indexes mobile version)
- [ ] Images sized for mobile (lazy-load, srcset)

### 6. Core Web Vitals

**Assessment approach:**
1. Run PageSpeed Insights (PSI) for real CrUX data (if available)
2. Check Chrome DevTools Lighthouse for lab baseline
3. Assess likely issues from code/content structure

**Common LCP issues:**
- Large unoptimized hero images
- Render-blocking resources (sync CSS/JS in `<head>`)
- Slow server response (TTFB > 600ms)
- Missing `rel="preload"` for above-the-fold images

**Common INP issues:**
- Heavy JavaScript execution on interaction
- Long tasks blocking main thread
- Third-party scripts (analytics, chat widgets, ads)

**Common CLS issues:**
- Images without `width` and `height` attributes
- Ads or embeds without reserved space
- Web fonts causing layout shift (use `font-display: swap` or `optional`)
- Dynamically injected content above existing content

### 7. Structured Data

See `schema-types.md` for full type reference. Technical checks:
- [ ] All JSON-LD in `<script type="application/ld+json">` tags
- [ ] Structured data in server-rendered HTML (not JS-injected) for time-sensitive types
- [ ] No deprecated types (HowTo, SpecialAnnouncement, etc.)
- [ ] Validate with Google Rich Results Test

### 8. JavaScript SEO (December 2025 Google guidance)

Critical clarifications for JS-heavy sites:

1. **Canonical conflicts**: If canonical in raw HTML differs from JS-injected canonical, Google may use EITHER. Keep them identical.
2. **noindex via JS**: If raw HTML has `noindex` but JS removes it, Google MAY still honor the raw HTML noindex. Serve correct robots directives in initial HTML.
3. **Non-200 pages**: Google does NOT render JavaScript on pages returning non-200 status codes. Error pages with JS-only content will be unseen.
4. **Structured data timing**: Product, Article schemas injected via JS may face delayed processing. Include in server-rendered HTML.

**Best practice:** Serve critical SEO elements (canonical, meta robots, structured data, title, meta description) in initial server-rendered HTML.

### 9. IndexNow Protocol

**Status (Jan 2026):** 80M+ websites using; supported by Bing, Yandex, Naver, Seznam, Yep. **Google does NOT support IndexNow.**

- [ ] Implement IndexNow for Bing and other non-Google engines if you publish content frequently. Google does not support it so it has no impact on Google indexation, but Bing indexation speed is meaningfully improved.
- [ ] Available via WordPress plugins (Yoast, Rank Math), Wix, Shopify natively, Cloudflare (paid)
- [ ] Priority for: time-sensitive content, e-commerce product pages, news sites
- [ ] Less critical for: static sites, long-form evergreen content

---

## AI Crawler Configuration (robots.txt)

As of 2025-2026, managing AI crawlers is a critical technical SEO consideration. Approximately 3-5% of websites now use AI-specific robots.txt rules.

| Crawler | Token | Purpose | Recommendation |
|---|---|---|---|
| GPTBot | `GPTBot` | OpenAI training | Allow for AI visibility |
| OAI-SearchBot | `OAI-SearchBot` | ChatGPT Search | Always allow |
| ChatGPT-User | `ChatGPT-User` | ChatGPT browsing | Always allow |
| ClaudeBot | `ClaudeBot` | Anthropic training | Allow |
| PerplexityBot | `PerplexityBot` | Perplexity index | Always allow |
| Google-Extended | `Google-Extended` | Gemini training ONLY | Optional block — does NOT affect Google Search |
| Bytespider | `Bytespider` | ByteDance/TikTok AI | Optional block |
| CCBot | `CCBot` | Common Crawl dataset | Optional block |

**Recommended robots.txt for AI visibility:**
```
User-agent: GPTBot
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: *
Allow: /
Sitemap: https://[domain]/sitemap.xml
```

---

## Technical SEO Scoring by Category

| Category | Good | Needs Work | Critical Issue |
|---|---|---|---|
| Crawlability | No blocked resources, sitemap present, AI crawlers configured | Minor blocks, incomplete sitemap | Googlebot blocked, no sitemap |
| Indexability | Clean canonicals, no duplicate issues | Some duplicate pages | Accidental noindex, canonical conflicts |
| Security | HTTPS, all security headers, no mixed content | HTTPS only, missing some headers | No HTTPS |
| URL Structure | Clean, short, consistent | Some long URLs, minor inconsistencies | Keyword-free URLs, redirect chains |
| Mobile | Fully responsive, fast on mobile | Some mobile issues | Not mobile-friendly |
| Core Web Vitals | All Good thresholds | Mixed or Needs Improvement | Poor for any metric |
| Structured Data | Active types only, validates | Missing opportunities | Deprecated types, validation errors |
| JS Rendering | SSR or no JS dependency for critical content | Some JS dependency | Critical content JS-only |
| IndexNow | Implemented | Not implemented | N/A (optional) |

---

## Detailed CWV Fix Steps

### Fixing LCP

The LCP element is usually the hero image or largest above-fold text block.

1. **Identify the LCP element** — PageSpeed Insights → Diagnostics shows exactly what it is.
2. **If LCP is an image:**
   - Add `fetchpriority="high"` to the `<img>` tag
   - Remove `loading="lazy"` if present — never lazy-load the LCP image
   - Serve in WebP format, sized to display dimensions
   - Self-host critical images where possible (avoids DNS overhead of third-party CDNs)
   - Add `<link rel="preload" as="image" href="hero.webp">` in `<head>`
3. **If LCP is a text element (H1, paragraph):**
   - Inline critical CSS; defer non-critical JS
   - Preload critical fonts: `<link rel="preload" as="font" href="font.woff2" crossorigin>`
   - If TTFB > 600ms → fix server response time first

### Fixing INP

INP measures the delay between user interaction and visual response.

1. **Identify slow interactions** — PageSpeed Insights → "Improve INP" lists culprits.
2. **Most common causes:**
   - Long JavaScript tasks on click/tap → break into smaller tasks using `setTimeout(fn, 0)` or `scheduler.postTask()`
   - Heavy third-party scripts on interaction → audit with Chrome DevTools → Performance → record a click
   - DOM size too large (>1,400 nodes) → reduce DOM depth; virtualize long lists
3. **Fastest win**: Defer/remove unused third-party scripts — chat widgets, tag manager, analytics payloads are the most common INP culprits.

### Fixing CLS

CLS measures unexpected layout shifts as the page loads.

1. **Identify shifting elements** — PageSpeed Insights → "Avoid large layout shifts."
2. **Common causes:**
   - **Images without dimensions** → add `width` and `height` to every `<img>` — most common CLS fix
   - **Ads/embeds without reserved space** → set `min-height` on the container
   - **Web fonts causing text reflow** → use `font-display: swap`; preload critical fonts
   - **Dynamic content inserted above fold** → insert below existing content or reserve space

## LCP Subparts Breakdown

Total LCP = sum of four diagnosable subparts (available in CrUX since February 2025):

| Subpart | What It Measures | Target |
|---|---|---|
| **TTFB** | Time to First Byte — server response | < 800ms |
| **Resource Load Delay** | Time from TTFB to resource request start | Minimize |
| **Resource Load Time** | Time to download the LCP resource | Depends on size |
| **Element Render Delay** | Time from resource loaded to rendered | Minimize |

Use PageSpeed Insights → Diagnostics to see which subpart is causing LCP failure. TTFB > 800ms = server/CDN problem. Large Resource Load Time = image too large or unoptimized.

## IndexNow

IndexNow notifies **Bing, Yandex, Naver, and Seznam** of URL updates — enabling faster indexing on non-Google engines. **Google does not use IndexNow.**

**When to add**: Sites that publish or update content frequently. E-commerce sites with price changes benefit most.

**Implementation**: Create an IndexNow key file at the root, then submit via API. Use `scripts/indexnow_checker.py` to validate.

**Note**: Siri, Alexa, and Cortana voice searches are powered by Bing — submit to Bing Webmaster Tools (separate from Google Search Console) for voice search visibility.

---

## Critical Technical Issues + Fix Directives

| Issue | How to Detect | Fix |
|---|---|---|
| CSS/JS blocked from Googlebot | robots.txt Disallow | Remove from Disallow |
| Dynamic content not in raw HTML | View source vs. DOM | Implement SSR or pre-rendering |
| No HTTPS / mixed content | Browser security indicator | Force HTTPS via 301; fix mixed assets |
| Missing canonical tags | Crawl or view source | Add `<link rel="canonical">` to every indexable page |
| Redirect chains (>1 hop) | Screaming Frog redirect report | Collapse to 1 hop |
| Orphan pages | Crawl + compare to sitemap | Add 1+ internal link from related indexed page |
| Soft 404s | GSC Coverage → "Crawled - currently not indexed" | Return real 404 or add genuine content |
| Missing OG / Twitter Card | View source: no `og:title` | Add to `<head>` on all shareable pages |
| Missing security headers | `curl -I` or DevTools Network | Add HSTS, X-Frame-Options, X-Content-Type-Options |

**Mobile-first indexing is 100% complete (July 5, 2024).** Google uses mobile Googlebot for ALL sites.

---

## JavaScript SEO — December 2025 Clarifications

1. **Canonical conflicts**: Raw HTML and JS injecting different canonicals → Google may use either. Serve identical canonicals in both.
2. **noindex in raw HTML**: If raw HTML has `noindex` and JS later removes it, Google may honor the raw HTML version. Never rely on JS to "fix" robots directives.
3. **Non-200 status pages**: Google does not render JS on non-200 pages.
4. **Structured data in JS**: Product/Article schema injected via JS may face delayed processing — include JSON-LD in the initial server-rendered HTML.

**Best practice**: Serve all critical SEO elements (canonical, meta robots, structured data, title, meta description, hreflang) in the **initial server-rendered HTML**.
