---
name: ultimate-seo-geo
description: Universal SEO + GEO skill for scored full-site audits, technical SEO, CORE-EEAT and CITE scoring, Schema.org JSON-LD, entity optimization, and GEO for AI Overviews, ChatGPT, and Perplexity. Use when the user mentions SEO, GEO, audit, schema, rankings, traffic drop, AI citations, backlinks, sitemap, crawl, robots, migration, hreflang, or content strategy.
---

# Ultimate SEO + GEO — Universal Search Optimization Skill

| Attribute | Details |
| --- | --- |
| **Version** | 1.4.0 |
| **Updated** | 2026-03-26 |
| **License** | MIT |
| **Author** | Myk Pono |
| **Lab** | [lab.mykpono.com](https://lab.mykpono.com) |
| **Homepage** | [mykpono.com](https://mykpono.com) |
| **LinkedIn** | [Profile](https://www.linkedin.com/in/mykolaponomarenko/) |

The definitive SEO and Generative Engine Optimization skill. Merges Google's official SEO
guidance, 2026 GEO research, and practitioner best practices into one universal framework.
Every finding comes with a clear fix directive — not just diagnosis.

## 0. Before You Start

### Routing index (read only what you need)

| Goal | Start here |
|------|------------|
| Full scored audit | § 2, § 21, `references/audit-script-matrix.md` |
| AI citations / GEO | § 3, `llms_txt_checker.py`, `entity_checker.py` |
| Schema only | § 5, `validate_schema.py` |
| Local | § 12, `local_signals_checker.py` |
| Crawl / index / performance | § 4, matrix scripts (`robots_checker`, `sitemap_checker`, `pagespeed.py` if API works) |
| Migration | § 20, `redirect_checker.py` |
| Keywords / roadmap (no URL yet) | § 7, § 16 — **do not** invent a live-site `/100` score |

### When *not* to run Mode 1 (full audit)

| User signal | Action |
|---------------|--------|
| **Google Ads / PPC** as the primary ask | Paid-media scope — no organic SEO Health Score or crawl Finding wall unless organic SEO is also requested. |
| Employer branding only, **pure** press/PR distribution, **email-only** marketing | Narrow guidance; no implied full technical + content audit. |
| **GA4/GTM setup only** (no organic SEO question) | § 10 measurement checklist — **no** fabricated domain-wide numeric score. |
| **Social** community management only | Out of scope unless tied to organic discovery (e.g. `sameAs`, entity signals). |
| **Explicitly scoped** task (e.g. “only robots.txt + sitemap”) | Stay in that scope — no domain-wide E-E-A-T essay or `/100` score unless the user asks. |

### Audit Context: Internal vs. Competitive Mode

Before routing, determine which audit context applies. This controls what outputs are valid.

| Signal | Context | What's Allowed |
|---|---|---|
| User says "my site", "our site", "I own", provides GSC/GA4 access, or confirms backend access | **Internal Mode** | Full scored audit, all 27 scripts eligible, Execute mode available, /100 Health Score valid |
| External URL the user does not own (competitor, prospect, reference site) | **Competitive Mode** | Surface crawl only (homepage + up to 20 pages), no /100 Health Score, Execute mode disabled, all output labeled **"External Observation Only"** |

**When in doubt, ask:** "Is this your site, or are you analyzing a competitor?"

This skill operates in three modes. Identify which mode applies before touching anything else.

### The Three Modes

**Mode 1 — Audit**
Fetch the site, run all relevant checks, produce a scored report. Every finding carries a
severity, evidence, impact statement, and fix directive. Output: SEO Health Score + prioritised
findings in the standard format (§ 2).

**Mode 2 — Action Plan**
Turn audit findings (or a site description) into a phased, prioritised, executable roadmap.
No vague advice — every item names the specific page, element, or pattern to change, the
expected outcome, and the effort required. Output: Implementation Phases table (§ 16) + Quick Wins.

**Mode 3 — Execute**
Do the work. Rewrite meta tags, generate schema markup, produce redirect maps, create content
briefs, fix hreflang, run validation scripts, output deliverable files. Every execution task
ends with a verification step.

Most requests involve all three in sequence: **Audit → Plan → Execute**. Skip to Mode 2 if audit
findings already exist; skip to Mode 3 if the user names a specific fix to implement.

### Intake Checklist

Three questions only — skip any already answered in the user's message.

| # | Question | Why It Matters |
|---|---|---|
| 1 | **What is the URL?** | Required for all three modes |
| 2 | **What is the primary goal?** (traffic / AI citations / local leads / traffic drop / specific keyword) | Determines which modules run first |
| 3 | **Which mode?** Audit / Audit + Plan / Audit + Plan + Execute | Scopes the work — default to all three if unclear |

Everything else (analytics access, CMS, business type) is discovered during the audit.

### Mode Routing

| Signal in the Request | Mode | Start At |
|---|---|---|
| "audit my site", "analyze", "full check", "what's wrong" | 1 → Audit | § 2 |
| "give me a plan", "roadmap", "what to fix first" | 2 → Plan | § 16 (after § 2 if no audit exists) |
| "fix this", "generate schema for", "rewrite my titles", "run the scripts" | 3 → Execute | § 21 for scripts; relevant section for task |
| "audit + fix everything" / no mode stated + URL | 1 → 2 → 3 | § 2, then § 16, then execute top findings |
| Traffic drop with URL | 1 → focused | § 10 first, then § 6 / § 4 |
| AI citations question | 1 → focused | § 3 first |
| Domain/CMS migration | 1 → focused | § 20 |

### What "Done" Looks Like per Mode

**Audit complete** when: SEO Health Score delivered, all Critical and High findings documented in
Finding/Evidence/Impact/Fix/Confidence format, no section skipped without reason stated.

**Plan complete** when: findings grouped into four implementation phases (Foundation / Expansion /
Scale / Authority), each item has an owner action, expected outcome, and effort estimate.

**Execute complete** when: every fix implemented AND verified — run the relevant validation script,
review the output, confirm it resolves the original finding.

---

## 1. Request Detection & Routing

If the request matches **§ 0 “When not to run Mode 1”**, route to a **narrow** answer or decline the SEO-audit template — even if generic “marketing” vocabulary appears.

| Request Type | Trigger Keywords | Go To |
|---|---|---|
| **Full Audit** | "audit", "analyze my site", "full check", "site review" | § 2 |
| **GEO / AI Search** | "AI Overviews", "ChatGPT", "Perplexity", "AI citations", "GEO", "AI Mode" | § 3 |
| **Technical SEO** | "crawl", "robots.txt", "Core Web Vitals", "speed", "indexing", "JS rendering" | § 4 |
| **Schema / Structured Data** | "schema", "JSON-LD", "rich results", "structured data" | § 5 |
| **Content / E-E-A-T** | "content quality", "E-E-A-T", "thin content", "helpful content", "CORE-EEAT" | § 6 |
| **Content Scoring** | "CORE-EEAT audit", "content score", "CITE audit", "domain authority score", "GEO score" | § 6 |
| **Entity Optimization** | "entity", "knowledge graph", "knowledge panel", "Wikidata", "brand entity" | § 3 |
| **Content Pruning / Refresh** | "old content", "content decay", "delete pages", "refresh", "consolidate" | § 6b |
| **Keyword Research** | "keywords", "ranking opportunities", "content gaps", "what should I write" | § 7 |
| **Topic Clusters** | "topic cluster", "content strategy", "pillar page" | § 7b |
| **AEO / Featured Snippets** | "featured snippet", "PAA", "voice search", "knowledge panel", "speakable" | § 7c |
| **Competitor Analysis** | "competitors", "benchmark", "compare to", "X vs Y page", "alternatives page" | § 8 |
| **Link Building** | "backlinks", "internal links", "anchor text", "referring domains" | § 9 |
| **Analytics / Reporting** | "GA4", "Search Console", "traffic drop", "CTR", "rank tracking" | § 10 |
| **Crawl & Indexation** | "crawl budget", "sitemap", "canonical", "index bloat", "noindex" | § 11 |
| **Local SEO** | "local", "Google Business Profile", "GBP", "map pack", "NAP" | § 12 |
| **Image SEO** | "images", "alt text", "WebP", "image size" | § 13 |
| **International SEO** | "hreflang", "multi-language", "international", "geo-targeting" | § 14 |
| **Programmatic SEO** | "programmatic", "at scale", "templates", "city pages", "glossary pages" | § 15 |
| **Strategy / Roadmap** | "SEO plan", "roadmap", "strategy", "what should I focus on" | § 16 |
| **Monthly Maintenance** | "what should I check", "monthly SEO", "ongoing", "monitor" | § 17 |
| **Site Migration** | "moving domains", "new URL structure", "CMS migration", "redirect map" | § 20 |
| **Myths / Misconceptions** | "does X help SEO?", "is X a ranking factor?" | § 18 |
| **Script Toolbox** | "run a check", "generate a report", "validate schema", "automated audit" | § 21 |
| **Paid ads primary** | "Google Ads", "PPC campaign", "ad spend" without organic SEO ask | § 0 — paid scope, not Mode 1 |
| **Scoped technical only** | "only robots.txt", "just the sitemap", "don’t audit content" | § 0 + § 4 / § 11 — stay in scope |

---

## 2. Full Site Audit

### Process

**In a bash-capable environment**: Run `python scripts/generate_report.py https://example.com --output report.html` first — it runs the **bundled analysis pipeline** in `generate_report.py` (robots, security, social, redirects, llms.txt, links, PageSpeed, entities, hreflang, duplicates, sitemap discovery, local signals, IndexNow probe, on-page parse, readability, article SEO, JSON-LD validation, image alt coverage, etc.). Then use `finding_verifier.py` to deduplicate at the end. For any single dimension, run the matching script from **`references/audit-script-matrix.md`** or **§21**.

**Evidence Integrity — do not state the following unless the corresponding data source ran or was provided:**

| Claim | Only state if |
|---|---|
| LCP / INP / CLS / performance score | `pagespeed.py` ran successfully, or user pasted PageSpeed Insights / CrUX output |
| Backlink count or referring domains | `link_profile.py` ran and returned data |
| Organic traffic or impression numbers | GSC / GA4 access confirmed and data retrieved |
| Health Score /100 | Internal Mode + minimum 5 scripts ran with data |
| Thin content finding | `readability.py` + `duplicate_content.py` both ran |
| Schema errors or validation status | `validate_schema.py` ran against the page |

**When data is absent:** replace the claim with `[metric] not measured — run [script] for actual data` or ask the user to provide it. If `pagespeed.py` failed, lacks an API key, or the environment blocks googleapis.com, say **performance data unavailable** and give checklist-level guidance (§ 4, `references/technical-checklist.md`) or ask the user to run PSI / WebPageTest manually.

1. **Fetch the site** — homepage + 5–10 representative pages (pillar pages, top posts, key landing pages).
2. **Detect business type** from page signals:
   - *SaaS/B2B*: pricing page, /features, "free trial"
   - *E-commerce*: /products, Product schema, "add to cart"
   - *Local service*: phone/address, service area, maps embed
   - *Publisher/Blog*: article-heavy, bylines, /category structure
   - *Agency/Portfolio*: /case-studies, client logos
   - Load `references/industry-templates.md` for business-type-specific architecture and schema priorities.

**Industry preset (what to prioritize first)**

| Detected type | Emphasize | Run early (when shell + network available) |
|-----------------|-----------|---------------------------------------------|
| **SaaS / B2B** | § 7 keywords, § 5 SoftwareApplication / Product, § 4 tech | `generate_report.py`, `validate_schema.py`, `meta_lengths_checker.py` |
| **E-commerce** | § 11 indexation, § 5 Product + `BreadcrumbList`, § 9 internal links | `generate_report.py`, `duplicate_content.py`, `sitemap_checker.py` |
| **Local service** | § 12, § 5 `LocalBusiness`, NAP | `local_signals_checker.py`, `robots_checker.py` |
| **Publisher / blog** | § 6 E-E-A-T, § 13 images, Article / `NewsArticle` | `readability.py`, `article_seo.py`, `duplicate_content.py` |
| **Agency / portfolio** | § 8 competitors, § 9 authority | `link_profile.py` + full report |

3. **Run all audit modules** in sequence: On-Page SEO · Content/E-E-A-T (§ 6) · Technical (§ 4) · Schema (§ 5) · Core Web Vitals (§ 4) · GEO/AI Search (§ 3) · Links (§ 9) · Images (§ 13) · Crawl & Indexation (§ 11) · Keyword Gaps (§ 7) · Local SEO if applicable (§ 12) · Analytics setup (§ 10).
4. **Score** — SEO Health Score using weights below.
5. **Assign confidence level**: High (8+ pages fetched + analytics access) / Medium (4–7 pages, no analytics) / Low (1–3 pages).
6. **Prioritize findings** — Critical → High → Medium → Quick Wins.

### SEO Health Score Weights

| Category | Weight |
|---|---|
| Content Quality / E-E-A-T | 22% |
| Technical SEO | 18% |
| On-Page SEO (titles, meta, URLs) | 15% |
| Link Authority | 12% |
| Schema / Structured Data | 10% |
| Core Web Vitals | 8% |
| AI Search Readiness (GEO) | 8% |
| Images | 4% |
| Local SEO (if applicable) | 3% |

### On-Page SEO Checklist

| Element | Standard | Fix If Missing |
|---|---|---|
| Title tag | Unique, ≤60 chars, primary keyword present | Rewrite: `[Primary Keyword] — [Brand]` |
| Meta description | Unique, 150–160 chars, no quotes | Write value-first: answer "why should I click?" |
| H1 | One per page, matches title topic | Add single H1 matching the page's main intent |
| URL | Lowercase, hyphens, descriptive, ≤100 chars | Redirect old URL → new clean URL + canonical |
| Canonical | Self-referencing on every indexable page | Add `<link rel="canonical" href="[absolute-url]">` |

**First check for any new site:** `site:yourdomain.com` in Google. Zero results = indexation problem → go to § 4 immediately.

### Finding Format

Every audit finding must use this structure:

```
Finding: [what the issue is]
Evidence: [what was observed / what data shows this]
Impact: [how this hurts rankings, traffic, or citations]
Fix: [specific, actionable step]
Confidence: Confirmed / Likely / Hypothesis
```

**Confidence labels:**
- **Confirmed**: Direct evidence in fetched source/data
- **Likely**: Strong inference from partial data (2–3 signals)
- **Hypothesis**: Pattern-based assumption; limited page access

**Scoring formula:** `base_score = (positive_signals / (positive_signals + deficit_signals)) × 100`. Deduct: Critical −15 pts, Warning −5 pts.

### Audit Output Format

Use this exact template:

```
# SEO Audit Report — [site.com]
Date: [date] | Business Type: [type] | Audited Pages: [N] | Confidence: High/Medium/Low

## SEO Health Score: XX/100
[chain-of-thought: positive_signals=N, deficit_signals=N, base=XX, Critical −15×N, Warning −5×N = final]

| Category | Score | Status |
|---|---|---|
| Content Quality / E-E-A-T | XX/100 | ✅/⚠️/❌ |
...

## Executive Summary
[2–3 sentences: biggest strength, biggest gap, single highest-impact action]

## 🔴 Critical Issues (fix immediately)
## 🟠 High Priority (fix this week)
## 🟡 Medium Priority (fix this month)
## ⚡ Quick Wins (under 2 hours each)
## 💡 Opportunity Signals
## Full Findings [per-category, each in Finding/Evidence/Impact/Fix/Confidence format]
```

### Mode 1 Audit Example (3-finding excerpt)

```
# SEO Audit Report — greenleaf.io
Date: 2026-03-15 | Business Type: SaaS | Audited Pages: 8 | Confidence: Medium

## SEO Health Score: 61/100
positive_signals=14, deficit_signals=9, base=61, Critical −15×0, Warning −5×2 = 51 → adjusted 61

## 🟠 High Priority

Finding: No Organization or SoftwareApplication schema on any page
Evidence: 0 JSON-LD blocks found across 8 pages; competitors average 3 schema types
Impact: Missing rich results; 0% AI citation eligibility — schema increases citation ~2.5×
Fix: Add Organization schema to homepage, SoftwareApplication + AggregateRating to /pricing
Confidence: Confirmed | Severity: 🟠 High

Finding: LCP 4.8s on homepage — hero image is 1.2MB unoptimized PNG
Evidence: PageSpeed Insights mobile score 38; LCP element: <img src="/hero-dashboard.png">
Impact: Poor CWV = deprioritized in mobile rankings; FCP > 0.4s reduces AI citations by 3×
Fix: Convert to WebP (target <200KB), add fetchpriority="high", preload via <link>
Confidence: Confirmed | Severity: 🟠 High

## ⚡ Quick Wins

Finding: Title tags use "Home | Greenleaf" pattern — keyword absent
Evidence: Homepage title "Home | Greenleaf" instead of primary keyword
Impact: ~15% CTR loss vs. keyword-leading titles at same position
Fix: Rewrite to "Project Management for Remote Teams | Greenleaf"
Confidence: Confirmed | Severity: 🟡 Medium
```

### Mode 2 Plan Entry Format

When converting audit findings into a roadmap (§ 16), use this format per item:

```
| Fix schema on all product pages | Dev | 2 hr | Star ratings in SERPs (+15–30% CTR) | Phase 1 |
```
Columns: Action | Owner | Effort | Expected Outcome | Phase

### Mode 3 Execute + Verify Loop

**Before producing any Execute output, classify the change:**

| Classification | Change Types | Action |
|---|---|---|
| **Safe** | Meta descriptions, title tags, alt text, FAQ/Article/Organization schema, content rewrites, llms.txt, internal links | Output directly |
| **High-Risk** | robots.txt, canonical tags, redirect maps, noindex directives, hreflang tags, bulk CMS template changes | State the proposed change and ask for explicit confirmation before outputting — one bad change here can deindex the site |

When implementing a specific fix:

```
1. Classify: Safe or High-Risk?
2. If High-Risk: state the change and confirm with the user before proceeding
3. State the finding being addressed
4. Produce the fix artifact (code, rewrite, JSON-LD, redirect map)
5. Verify: run scripts/validate_schema.py [file] OR review output directly
6. Confirm: "Fix resolves [Finding] — [evidence of resolution]"
```

**Example:**
```
Addressing: Missing FAQPage schema on /guides/psilocybin-therapy
Fix: [generated JSON-LD below]
Verify: python scripts/validate_schema.py therapy_page.html → 0 errors
Confirmed: FAQPage with 4 Q&A pairs valid; eligible for AI Overview extraction.
```

---

## 3. GEO — AI Search Visibility

GEO = getting content cited by AI engines: Google AI Overviews, AI Mode, ChatGPT Search, Perplexity.

### GEO Quick Check (run first — 5 yes/no questions)

| # | Question | If No → Action |
|---|---|---|
| 1 | Are AI crawlers (OAI-SearchBot, PerplexityBot) allowed in robots.txt? | Remove Disallow rules immediately |
| 2 | Does the page answer its target query in the first 60 words? | Move key answer to opening paragraph |
| 3 | Is page content present in raw HTML (not JS-rendered only)? | Implement SSR or pre-rendering |
| 4 | Does the page have a named author with credentials and a publication date? | Add author bio + date to every key page |
| 5 | Is the brand mentioned on YouTube or Reddit? | Start a presence on the missing platform |

Any "No" = fix before deeper analysis. All "Yes" → proceed to full GEO Score.

### 2026 AI Search Landscape

| Platform | Reach | Traffic Signal |
|---|---|---|
| **Google AI Overviews** | 1.5B users/month | 38% citations from top-10 pages; 47% from below position 5 |
| **Google AI Mode** | 180+ countries (May 2025) | Zero blue links — citation is the ONLY visibility |
| **ChatGPT Search** | 900M weekly active users | Appears as Direct in GA4 (no referral header) |
| **Perplexity** | 500M+ queries/month | Trackable `perplexity.ai` referral in GA4 |

Only 11–13.7% of domains are cited by both ChatGPT and AI Overviews — platform-specific optimization matters. For full platform data, brand correlation stats, and Wikipedia/Wikidata setup, see `references/ai-search-geo.md`.

### GEO Audit — Step by Step

1. **Check AI crawler access** — Fetch `/robots.txt`. Confirm OAI-SearchBot, PerplexityBot, ClaudeBot are not Disallowed.
2. **Check llms.txt** — Fetch `/llms.txt`. Missing → generate from template below. Low-cost hygiene step.
3. **Score citability** — For each key page: does the first 40–60 words answer the target query? Self-contained 134–167 word answer blocks? Question-format headings? Pages already optimized for Featured Snippets (§ 7c) have a structural head-start on AI citation.
4. **Check JavaScript rendering** — Fetch raw page source. Key content absent from raw HTML = invisible to AI bots.
5. **Audit brand signals** — Search brand on YouTube, Reddit, Wikipedia. Missing platforms = highest-priority targets. See `references/ai-search-geo.md` for correlation data and Wikipedia/Wikidata setup.
6. **Test AI citation presence** — Search 3–5 target keywords in ChatGPT and Perplexity. Note where competitors appear and the site doesn't.
7. **Output GEO Score** using component weights below.

### GEO Score Components

| Dimension | Weight | Key Checks |
|---|---|---|
| **Citability** | 25% | Answer in first 40–60 words; 134–167 word self-contained blocks; specific stats |
| **Structural Readability** | 20% | H1→H2→H3 hierarchy; question-based headings; tables |
| **Authority & Brand Signals** | 20% | Author bio + credentials; publication date; Wikipedia/Reddit/YouTube presence |
| **Technical Accessibility** | 20% | AI crawlers allowed; SSR; llms.txt present |
| **Multi-Modal Content** | 15% | Text + images + video = 78% of cited sources |

**Key insight**: 44.2% of AI citations come from the *first 30%* of content. Restructuring alone can 2× citation rate.

### Building Brand Signals — Tactical Playbook

Brand signals (Reddit, YouTube, Wikipedia mentions) account for 20% of the GEO Score. Use when step 5 identifies any missing platform.

**Quora**
1. Search Quora for questions your content directly answers.
2. Write a genuine 2–3 paragraph answer — do not copy-paste the article.
3. Include one link to the relevant page at the end, not the top.
4. Upvoted Quora answers index in Google and are scraped by Perplexity. Genuine answers accumulate passive impressions for months.
5. Target 3–5 Quora answers per piece of published content.

**Reddit**
1. Find the subreddit where the target audience discusses this topic.
2. Write 2–3 sentences of genuine context explaining why the content is relevant — do not paste the link alone. Context-free links are removed or downvoted. Upvoted Reddit threads are heavily indexed and cited by Perplexity.
3. Engage with follow-up comments within 24 hours.

**Influencer and Newsletter Outreach**
1. Build a list of 10–30 relevant influencers per topic cluster.
2. Email one sentence on why their audience benefits + pre-written tweet or LinkedIn post they can share as-is. Make sharing zero-effort.
3. Identify 5–10 industry newsletters. Pitch strong content with a one-line summary — newsletter editors need good content; you are doing them a favour.
4. Each share → brand mention → strengthens entity signals and AI citation rate.

### Google AI Mode — Specific Optimization

AI Mode (launched May 2025) has no blue links at all — zero visibility if not cited. It follows up with clarifying questions, so content that answers follow-on queries wins. Add a "Related Questions" section (3–5 logical follow-ups) at the end of key pages. Explicit publication + last-updated dates are stronger freshness signals here than in standard search.

### AI Crawler Access

| Crawler | Owner | Action |
|---|---|---|
| OAI-SearchBot, ChatGPT-User | OpenAI Search | **Always allow** |
| GPTBot | OpenAI Training | Allow — blocking also removes site from ChatGPT Search |
| PerplexityBot | Perplexity | **Always allow** |
| ClaudeBot, anthropic-ai | Anthropic | Allow |
| Google-Extended | Google Gemini training | Optional block — does NOT affect Google Search or AI Overviews |

### llms.txt Quick Template

```
# [Site Name]
> [One-line description]

## Key Pages
- [Page Title](url): [What it covers]

## Best Content
- [Article Title](url): [What it answers]
```

### GEO Finding Example

```
Finding: Key answer buried below fold — target query not answered in first 30% of content
Evidence: "How does [product] work" answered in paragraph 6, ~800 words in.
           44.2% of AI citations come from first 30% of content — this page fails.
Impact: Low AI Overview and Perplexity citation rate for the site's core query.
Fix: Move the direct answer to the opening paragraph. Keep detail further down.
Confidence: Confirmed | Severity: 🟠 High
```

→ `references/ai-search-geo.md` (full platform data, brand correlation, Wikipedia/Wikidata setup, Passage Indexing, Princeton GEO research techniques, content type citation share, AI monitoring tools, platform source selection factors) | `references/entity-optimization.md` (47-signal entity checklist, AI Entity Resolution Test, Knowledge Graph guide) | `scripts/robots_checker.py` `scripts/entity_checker.py` `scripts/llms_txt_checker.py` `scripts/social_meta.py`

---

## 4. Technical SEO

### Core Web Vitals (INP replaced FID March 2024 — never reference FID)

| Metric | Good | Needs Improvement | Poor |
|---|---|---|---|
| **LCP** | < 2.5s | 2.5–4.0s | > 4.0s |
| **INP** | < 200ms | 200–500ms | > 500ms |
| **CLS** | < 0.1 | 0.1–0.25 | > 0.25 |

Measured at 75th percentile (CrUX/PageSpeed Insights). Speed is also a GEO factor: FCP < 0.4s pages average 6.7 AI citations vs. 2.1 for slower pages.

### Technical Audit — Step by Step

1. **Run PageSpeed Insights** on homepage + top 3 pages. Record LCP, INP, CLS. For detailed CWV fix steps (LCP subparts, INP long task debugging, CLS prevention patterns), see `references/technical-checklist.md`.
2. **Check robots.txt** — CSS, JS, and key pages not blocked. AI crawlers not disallowed.
3. **Check HTTPS** — Entire site over HTTPS. Mixed-content assets → force HTTPS via 301.
4. **Check canonical tags** — Every indexable page has `<link rel="canonical" href="[absolute-url]">`.
5. **Check redirect chains** — Chain >1 hop → collapse to direct redirect.
6. **Check orphan pages** — Any indexed page with zero internal links. Flag here; fix in § 9.
7. **Check mobile rendering** — GSC Mobile Usability. Touch targets ≥48×48px, font ≥16px.
8. **Check soft 404s** — Page returns 200 but shows "not found". Fix: return real 404 or add genuine content.
9. **Check JavaScript rendering** — Compare raw source to rendered DOM. Key content JS-only = invisible to AI bots.
10. **Check Open Graph + Twitter Card** — `og:title`, `og:description`, `og:image`, `twitter:card` on all shareable pages.
11. **Check security headers** — HSTS, X-Frame-Options, X-Content-Type-Options. ✅ Pass: `Strict-Transport-Security: max-age=31536000; includeSubDomains`. ❌ Fail: header absent or `max-age=0`.

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

→ `references/technical-checklist.md` (detailed CWV fix steps, LCP subparts, IndexNow setup) | `scripts/pagespeed.py` `scripts/robots_checker.py` `scripts/redirect_checker.py` `scripts/security_headers.py` `scripts/indexnow_checker.py`

> **Script note**: `pagespeed.py` calls googleapis.com. In proxy-restricted environments it will fail — fallback: ask user to run pagespeed.web.dev and share results, or use the manual CWV checklist in `references/technical-checklist.md`.

---

## 5. Schema / Structured Data

Always use **JSON-LD** (`<script type="application/ld+json">`). Schema improves AI citation likelihood ~2.5× (Google/Microsoft, March 2025).

### Schema Audit — Step by Step

1. **Check existing schema** — Fetch page source, search `application/ld+json`.
2. **Validate** — Test at search.google.com/test/rich-results. Fix errors before adding new schema.
3. **Identify missing schema** — Compare to Essential Schema table below.
4. **Generate missing schema** — Use JSON-LD templates in `references/schema-types.md`.
5. **Check deprecated types** — See § 19. Remove deprecated schema immediately.
6. **Add FAQPage to key pages** — Google restricts FAQ rich results to gov/healthcare, but FAQPage is still extracted by ChatGPT, Perplexity, and AI Overviews.

### Priority Schema by Site Type

| Site Type | Essential Schema |
|---|---|
| **Publisher / Blog** | Article/BlogPosting, Person, ProfilePage (author pages), Organization, WebSite, BreadcrumbList |
| **Forum / Community** | DiscussionForumPosting, Person, Organization |
| **SaaS** | WebApplication/SoftwareApplication, Organization, WebSite, FAQPage |
| **E-commerce** | Product + Offer, AggregateRating, Organization, BreadcrumbList, ProductGroup (variants), OfferShippingDetails |
| **Local Business** | LocalBusiness (most specific subtype), Organization, AggregateRating |
| **Personal Site** | Person, ProfilePage, WebSite, Article |

### Validation Checklist

1. `@context` = `"https://schema.org"` (https, not http)
2. `@type` is valid and not deprecated (§ 19)
3. All required properties present
4. All URLs are absolute (not relative)
5. Dates in ISO 8601 (`YYYY-MM-DD`)
6. No placeholder text — all values are real, accurate data

For e-commerce schema additions (ProductGroup, Certification, OfferShippingDetails), recent schema types (2024–2026), and AEO schema (Sitelinks Searchbox, Speakable, Knowledge Panel sameAs), see `references/schema-types.md`.

→ `references/schema-types.md` | `scripts/validate_schema.py`

---

## 6. Content Quality & E-E-A-T

### Key Policy Updates

| Update | Date | Impact |
|---|---|---|
| **E-E-A-T universal** | December 2025 | Applies to ALL competitive queries — not just YMYL |
| **AI content quality** | September 2025 QRG | AI content acceptable if genuine E-E-A-T; penalized without unique value |
| **Helpful Content System merged** | March 2024 | Merged into core algorithm — helpfulness weighted continuously |

### Content Audit — Step by Step

1. **Read the page in full.** Comprehensive coverage? Named author with credentials?
2. **Score each E-E-A-T factor** — see `references/eeat-framework.md` for the full scoring framework and factor weights.
3. **Identify the weakest factor** — this is the highest-leverage fix.
4. **Check word count**: Blog post 1,500+, Service page 800+, Homepage 500+, Product page 300+. These are floors — cover the topic fully.
5. **Check for thin content signals**: copied definitions, no original research, no first-hand examples, no author bio.
6. **Recommend specific additions** — not "add experience signals," but "add a section with real test results showing [specific outcome] from [specific test]."

**Key insight**: AI can mimic expertise but not fabricate genuine Experience. First-hand signals are the #1 E-E-A-T differentiator post-Dec 2025.

**Don't**: Recommend increasing word count as a standalone fix. Padding is a negative signal.

For the E-E-A-T scoring framework with factor weights, content quality minimums table, readability grade targets, and 2025 spam categories (expired domain abuse, site reputation abuse, scaled content abuse), see `references/eeat-framework.md` and `references/content-eeat.md`.

For the full **80-item CORE-EEAT content audit** (8 dimensions, Pass/Partial/Fail scoring, content-type weight tables, 3 veto items, GEO Score vs. SEO Score), see `references/core-eeat-framework.md`. Use this for deep content quality assessments.

For the **40-item CITE domain authority audit** (Citation/Identity/Trust/Eminence, domain-type weights, veto items that cap score at 39, Diagnosis Matrix for CITE × CORE-EEAT strategy), see `references/cite-domain-rating.md`. Use this for domain-level authority assessments.

→ `references/eeat-framework.md` `references/content-eeat.md` `references/core-eeat-framework.md` `references/cite-domain-rating.md` | `scripts/article_seo.py` `scripts/readability.py` `scripts/duplicate_content.py`

---

## 6b. Content Pruning & Refresh

For sites older than 2 years, content decay is often higher leverage than creating new content.

### Step by Step

1. **Export all URLs from GSC** → Performance → Last 16 months → Download CSV. Sort by impressions descending.
2. **Categorize every page** into one of four buckets:

| Bucket | Criteria | Action |
|---|---|---|
| **Refresh** | Had impressions 12–16 months ago, traffic declined, topic still relevant | Update content, improve E-E-A-T, add question headings, update lastModified |
| **Prune** | < 10 impressions in 12 months, no backlinks, outdated | 301 redirect to most relevant page, then delete |
| **Consolidate** | Multiple pages covering the same topic | Merge into one strong page; redirect all others |
| **Keep** | Stable or growing traffic, strong E-E-A-T | Monitor monthly |

3. **For each Prune**: zero backlinks → 301 redirect then delete. Has backlinks → consolidate first.
4. **For each Consolidate**: pick strongest page, incorporate best content, 301 redirect weaker pages, update all internal links.

**Don't**: Prune pages with external backlinks without redirecting. Losing backlink equity from an unredirected prune is worse than keeping mediocre content.

For freshness thresholds by content type, see `references/content-eeat.md`.

→ `references/content-eeat.md`

---

## 7. Keyword Research & Content Gaps

### Step by Step

1. **Establish seed keywords** — What are the 3–5 core topics this site covers?
2. **Classify existing content by intent** — Informational / Commercial / Transactional / Navigational.
3. **Identify funnel gaps** — Which stages (TOFU / MOFU / BOFU) have no content?
4. **Prioritize missing content** — For each gap: target keyword, intent, format, difficulty.
5. **Output a prioritized content plan** — Up to 10 recommended pages by Opportunity Score: `(Volume × Intent Value) / Difficulty` — see `references/keyword-strategy.md` for the full formula with intent-weighted values and priority scoring matrix.

### Keyword Selection: Good vs. Bad

| ✅ Good Target | ❌ Poor Target | Why |
|---|---|---|
| "project management software for remote teams" | "project management" | Too broad — DA 80+ players dominate |
| "best CRM for small business 2026" | "CRM software" | Specific + high commercial intent |
| "Salesforce alternatives for nonprofits" | "Salesforce" | Navigational — won't convert |
| "email marketing open rate benchmarks" | "email marketing" | Data opportunity vs. unreachable head term |

### Intent + Funnel Gap Detection

| Intent | Pattern | Content Format |
|---|---|---|
| **Informational (TOFU)** | "what is X", "how to X" | Pillar guide, how-to — create definitional anchor if missing |
| **Commercial (MOFU/BOFU)** | "best X", "X vs Y", "X alternatives" | Comparison, roundup — high commercial intent, often faster to rank |
| **Transactional (BOFU)** | "buy X", "X pricing", "free trial" | Landing page, pricing |

→ `references/keyword-strategy.md`

---

## 7b. Topic Cluster Building

### Step by Step

1. **Identify pillar topic** — Broad term with high volume. Pillar page: 3,000–5,000 words, covers the topic broadly, links to every cluster post.
2. **Map cluster posts** — Find subtopics via PAA boxes, GSC queries. Pattern: "what is [topic]", "how to [topic]", "best [topic] tools", "[topic] vs [alternative]".
3. **Assign funnel intent** — TOFU / MOFU / BOFU. Aim for a mix.
4. **Build pillar first**, then cluster posts (1,500–2,500 words each).
5. **Enforce bidirectional linking** — Pillar → all cluster posts. All cluster posts → pillar.

### Example Structure

**Pillar**: "Project Management Software" (3,500 words)
- TOFU: "What is project management?", "Agile vs. Waterfall"
- MOFU: "How to choose PM software", "Project management templates"
- BOFU: "Best PM software for small teams", "Asana vs. Monday vs. Trello"

### Cluster Health Check

| Check | Status |
|---|---|
| Pillar receives most internal links from cluster? | ✅ Required |
| All cluster posts indexed? | ✅ Required |
| No two posts targeting the same primary keyword? | ✅ Required (cannibalization) |

---

## 7c. AEO — Answer Engine Optimization

AEO covers zero-click SERP features: Featured Snippets, PAA, Knowledge Panel, voice/speakable. Winning these directly feeds AI Overview and AI Mode citations.

### Featured Snippet Optimization

1. **Identify candidates** — Pages ranking 2–10 for informational queries (high impressions in GSC).
2. **Identify the snippet format** — Search the query. Paragraph, list, or table?
3. **Structure the answer:**
   - **Paragraph**: 40–60 words immediately after a question-format H2/H3. Never exceed 60 words.
   - **List**: 5–9 items, each < 15 words. Lists >9 items get truncated.
   - **Table**: ≤4 columns, labeled headers.
4. **Never defer the answer** — "It depends" before the answer loses the snippet to a competitor who answers directly.

### PAA Optimization

1. Find PAA questions for the target keyword.
2. Add a dedicated H2/H3 using the exact question wording.
3. Answer immediately in **40–60 words** — direct, no preamble.
4. Aim for 3–5 PAA answers per page (each answer surfaces more questions).

### Content Format Pattern

```
## What is [Topic]?
[Topic] is [definition in 1 sentence]. It works by [mechanism in 1 sentence].
[1–2 sentences context. Total: 40–60 words.]

## How does [Topic] work?
[Direct answer in 40–60 words starting with the subject.]
```

For Knowledge Panel (sameAs schema), Sitelinks Searchbox (SearchAction code), Speakable schema, and voice search platform breakdown (Siri/Alexa use Bing, not Google), see `references/schema-types.md` → "AEO Schema" section.

---

## 8. Competitor Analysis

### Step by Step

1. **Identify 3–5 direct competitors** — Search the site's primary keyword and note positions 1–5.
2. **Fetch competitor homepage + top-ranking pages**. Also fetch `[competitor-url]/robots.txt` and `[competitor-url]/llms.txt` for GEO stance assessment. For topic coverage: run `sitemap_checker.py [competitor-url]` to confirm sitemap URL and reachability, then fetch the raw sitemap XML directly and read `<loc>` URL path patterns — folder-level segments absent from the audited site are direct content gap candidates.
3. **Assess across five dimensions** below.
4. **Identify 3 biggest gaps to close** and 3 biggest advantages to exploit.
5. **Test shared keywords in AI search** — ChatGPT and Perplexity. Note who gets cited.

### Competitor Assessment Dimensions

| Dimension | Opportunity Signal |
|---|---|
| Content depth gaps | Create the definitive resource on under-covered topics |
| Missing topic clusters | Map cluster and execute content plan |
| Schema advantages | Add missing schema immediately; reinforce where you have it |
| AI citation presence | If they're cited and you're not → audit GEO signals (§ 3) |
| E-E-A-T gaps | Leverage credentials where competitors use anonymous bylines |
| AI crawler configuration | If competitor blocks OAI-SearchBot or PerplexityBot in robots.txt → immediate GEO first-mover advantage. Run `robots_checker.py [competitor-url]`. Output labeled "External Observation Only." |
| llms.txt presence | If competitor lacks llms.txt → your llms.txt gives AI systems clearer indexing signal. Run `llms_txt_checker.py [competitor-url]`. Output labeled "External Observation Only." |
| Topic coverage gap (sitemap) | Fetch competitor's raw sitemap XML; `<loc>` URL path patterns absent from your site → direct content calendar input. Confirm sitemap reachability via `sitemap_checker.py [competitor-url]`, then read raw `<loc>` entries. Output labeled "External Observation Only." |

### Output Format

```
## Competitive Landscape
| Dimension | [Your Site] | [Competitor 1] | [Competitor 2] |

## Top 3 Gaps to Close
## Top 3 Advantages to Exploit
## AI Citation Gap (if applicable)
## Recommended Comparison Pages to Create
```

For "X vs Y" and "Alternatives to X" page content requirements, the 4-type comparison page playbook (title formulas, fairness guidelines, CTA placement rules), feature matrix structure, and nominative fair use guidance, see `references/link-building.md` → "Comparison & Alternatives Page Playbook" section.

---

## 9. Link Building & Internal Linking

**Internal linking first** — highest leverage, zero cost. Always audit before recommending external acquisition.

### Internal Link Audit — Step by Step

1. **Identify pillar pages** — Verify they receive the most internal links from cluster posts.
2. **Find orphan pages** — Zero internal links pointing to them. Fix: add 1+ contextual link from a related page.
3. **Audit anchor text** — Replace "click here"/"read more" with descriptive, keyword-rich anchors.
4. **Check crawl depth** — Key pages within 3 clicks from homepage.

### Standards

| Rule | Standard |
|---|---|
| Orphan pages | Zero allowed — every indexed page needs 1+ internal link |
| Anchor text distribution | 40–50% branded, 15–20% naked URL, 5–10% exact match. >20% exact match = over-optimization |
| Internal nofollow | Remove — nofollow on internal links blocks PageRank flow |
| Link density | 3–5 contextual internal links per 1,000 words |

### External Link Quality Hierarchy

1. Editorial links from authoritative publications
2. Digital PR / original research
3. Partner/supplier/testimonial links
4. Broken link building, resource page outreach
5. Industry directories (supplementary)

**Don't**: Recommend paid link schemes — violates Google's spam policy.

→ `references/link-building.md` (CommonCrawl backlink API, comparison page requirements) | `scripts/internal_links.py` `scripts/broken_links.py` `scripts/link_profile.py`

---

## 10. Analytics & Reporting

### Setup — Step by Step

1. **Confirm GA4** — `gtag.js` in page source. Missing → install and configure organic reporting.
2. **Confirm Search Console verified** — If not → verify and submit sitemap.
3. **Confirm rank tracking** — Weekly position tracking for primary keywords (mobile + desktop separately).
4. **Run PageSpeed Insights** on homepage + 2 key pages.

### Minimum Stack

| Tool | Purpose |
|---|---|
| **Google Search Console** | Indexation, Performance, Core Web Vitals (field data) |
| **GA4** | Organic sessions, engagement, conversions |
| **PageSpeed Insights** | CWV field + lab data |
| **Rank tracker** | Weekly position tracking |

### Traffic Drop Diagnostic

1. **GSC impressions dropped** → Ranking issue. Check algorithm update calendar. Identify pages + dates.
2. **Impressions stable, clicks fell** → SERP feature change (AI Overview absorbing clicks). Optimize for AI citation (§ 3) and featured snippet (§ 7c).
3. **Segment by page type** → Isolate which category is affected.

### CTR Benchmarks

| Position | Expected CTR | Action |
|---|---|---|
| 1 | 27–39% | Rewrite title; test question format |
| 3 | 10–14% | Improve meta description; add rich result schema |
| 5 | 5–7% | Rewrite title + meta; optimize for featured snippet |
| 10 | 2–3% | Major content upgrade to push to top 5 |

**AI traffic**: Perplexity = `perplexity.ai` referral in GA4. ChatGPT = no referrer, appears as Direct.

→ `references/analytics-reporting.md`

---

## 11. Crawl & Indexation

**Rule of thumb**: Crawl budget rarely matters for sites under 500 pages. Focus on content quality first.

### Indexation Audit — Step by Step

1. `site:domain.com` in Google. Large discrepancy = investigation needed.
2. **GSC Coverage** — "Crawled - currently not indexed" (thin content) and "Submitted URL not indexed."
3. **Sitemap health** — Only canonical, 200-status, indexable URLs. No noindex pages in sitemap.
4. **Canonical conflicts** — No page with both `noindex` and a canonical tag.
5. **URL parameter handling** — Parameter variants must canonical to master page.

### Key Canonical Rules

| Scenario | Fix |
|---|---|
| www vs. non-www | 301 redirect one to the other + canonical |
| HTTP vs. HTTPS | 301 redirect HTTP → HTTPS |
| URL parameters | Canonical → master page |
| noindex + canonical conflict | Use one or the other — never both |

**Sitemap health**: submitted/indexed ratio >90% = healthy; <70% = investigate content quality or canonicalization.

→ `references/crawl-indexation.md`

---

## 12. Local SEO

Apply whenever the site is a local business, service area business, or has physical locations.

### Audit — Step by Step

1. **Check GBP** — Not claimed → claim and verify immediately.
2. **Audit GBP completeness** — Primary category (most specific), all hours, services, photos (min 10), weekly posts.
3. **Check NAP consistency** — Character-for-character identical across GBP, website, all citations.
4. **Check review profile** — Count, average rating, recency.
5. **Verify LocalBusiness schema** — name, address, phone, geo coordinates, openingHours.

### Review Benchmarks

| Metric | Healthy | Action |
|---|---|---|
| Star rating | ≥ 4.3 | Address negative patterns; request reviews proactively |
| Review count | ≥ 50 | Create review request at highest satisfaction moment |
| Review recency | ≤ 30 days | Automate review request post-service |

**Citation priority**: GBP → Apple Maps → Bing Places → Yelp → Facebook → BBB → industry directories

### Location Page Quality Gates

| Threshold | Action |
|---|---|
| 30+ location pages | ⚠️ WARNING — each needs: local address, team, reviews, locally relevant content |
| 50+ location pages | 🛑 HARD STOP — city-name-only swap targeted by March 2024 Core Update |

**Don't**: Recommend fake reviews — GBP suspension risk.

→ `references/local-seo.md`

---

## 13. Image SEO

### Audit — Step by Step

1. **Check each `<img>`** — alt text? Declared width/height? WebP format?
2. **Identify LCP image** — Confirm `fetchpriority="high"` and NOT lazy-loaded.
3. **Check file sizes** — DevTools Network, actual KB per image.
4. **Fix missing alt text** — Descriptive, 10–125 chars.
5. **Check responsive images** — `srcset` and `sizes` on content images.

### Checklist + Fix Directives

| Element | Standard | Fix |
|---|---|---|
| Alt text | Descriptive, 10–125 chars | "[what + context]" e.g. "White ceramic mug on wooden desk" |
| Format | WebP preferred | Convert to WebP; AVIF for cutting-edge |
| File size | Thumbnails <50KB; content <100KB; heroes <200KB | Squoosh/Cloudinary; CDN compression |
| Responsive | `srcset` and `sizes` | Add multi-resolution srcset |
| Lazy loading | Below-fold only | Never lazy-load LCP image |
| Dimensions | `width` and `height` on all `<img>` | Prevents CLS |
| LCP image | `fetchpriority="high"` | `<img fetchpriority="high" src="hero.webp">` |

**Progressive enhancement:**
```html
<picture>
  <source srcset="image.avif" type="image/avif">
  <source srcset="image.webp" type="image/webp">
  <img src="image.jpg" alt="Descriptive alt text" width="800" height="600"
       loading="lazy" decoding="async">
</picture>
```

**Don't**: Add `loading="lazy"` to the LCP image.

→ `references/image-seo.md`

---

## 14. International SEO & Hreflang

### Audit — Step by Step

1. **Check existing hreflang** — View source, search `rel="alternate"`.
2. **Validate language codes** — ISO 639-1 format: `en-GB` ✅ `en-uk` ❌ (region uppercase).
3. **Check self-references** — Every page must hreflang to itself.
4. **Check return tags** — A links to B; B must link back to A.
5. **Check x-default** — `<link rel="alternate" hreflang="x-default" href="[fallback-url]">`.
6. **Check canonical alignment** — Hreflang only on canonical URLs.

### Critical Rules

| Rule | Fix |
|---|---|
| Self-reference required | Add `hreflang="[lang]"` to own page |
| Return tags required | Audit all alternate pages |
| `x-default` required | Add fallback URL tag |
| Chinese requires script qualifier | `zh-Hans` / `zh-Hant` ✅ — bare `zh` ❌ |
| Japanese code | `ja` ✅ — `jp` is a country code ❌ |

→ `references/international-seo.md` | `scripts/hreflang_checker.py`

---

## 15. Programmatic SEO

### Step by Step

1. **Assess data source** — Each record must have ≥3 distinct data points beyond the variable name.
2. **Design template** — Unique injection: title, H1, meta description, ≥30% of body content.
3. **Apply quality gates** — Hard stops below.
4. **Build internal linking** — Programmatic pages must link to pillar and cluster pages.
5. **noindex thin records** from day one.
6. **Human review** — 5–10% sample before publishing >100 pages.

### Quality Gates (Non-Negotiable)

| Threshold | Action |
|---|---|
| >100 pages | ⚠️ WARNING — review content differentiation |
| >500 pages OR <30% unique content | 🛑 HARD STOP |
| <40% differentiation | Flag as thin content risk |

**Don't**: Approve city pages where only the city name changes — March 2024 Core Update target (60–80% traffic declines seen).

→ `references/programmatic-seo.md` (12 playbooks taxonomy, data-asset-to-playbook decision matrix, data defensibility hierarchy, Scaled Content Abuse enforcement timeline with dates, uniqueness calculation formula, progressive rollout strategy)

---

## 16. SEO Strategy & Roadmap

### Step by Step

1. **Triage findings**: (Business Impact × Ranking Impact) / Effort. Highest = do first.
2. **Group into four phases** below.
3. **State the #1 action for this week** — concrete task + expected outcome.
4. **Set milestones** — what does success look like at 30/60/90 days?

### Implementation Phases

| Phase | Timeframe | Focus |
|---|---|---|
| **Foundation** | Weeks 1–4 | Technical fixes, canonical strategy, analytics, essential schema |
| **Expansion** | Weeks 5–12 | Content creation (TOFU/MOFU/BOFU gaps), internal linking, Local SEO |
| **Scale** | Weeks 13–24 | Content clusters, link building, GEO optimization, image SEO |
| **Authority** | Months 7–12 | Thought leadership, digital PR, original research, Wikipedia entity |

### Quick Win Prioritization

- Canonicalization errors → 1–2 weeks to crawl improvement
- Missing schema on existing pages → template once, apply everywhere
- Title tag rewrites for positions 4–15 → CTR improvement in 2–4 weeks
- Internal links from high-authority pages → immediate crawl benefit
- Unblocking AI crawlers → GEO improvement within weeks
- Question-format headings on ranking pages → featured snippet capture in 2–6 weeks

---

## 17. Monthly Maintenance Checklist

Run through the full monthly maintenance checklist (5 categories: Technical Health, Content & Rankings, GEO/AI Search, Local SEO, Analytics Integrity) in `references/analytics-reporting.md` → "Monthly Maintenance Checklist" section. Key trigger: any page losing impressions for 3+ months → flag for content refresh (§ 6b).

→ `references/analytics-reporting.md`

---

## 18. Google's Official Stance — Myths & Misconceptions

14 common SEO myths with Google's official positions are documented in `references/analytics-reporting.md` → "Myths & Misconceptions" section. Load when a user asks "does X help SEO?" or "is X a ranking factor?" Key myths to know without loading: meta keywords tag is ignored, word count has no minimum/maximum, CWV are a tiebreaker not primary factor, E-E-A-T describes quality but is not a direct ranking factor.

→ `references/analytics-reporting.md`

---

## 19. Quality Gates & Hard Rules

Global rules — apply across all sections.

**Deprecated schema** — never recommend: HowTo (Sept 2023), SpecialAnnouncement (July 2025), ClaimReview (June 2025), Dataset (late 2025), VehicleListing (June 2025), Practice Problem (late 2025), EstimatedSalary (June 2025), LearningVideo (June 2025), EnergyConsumptionDetails (replaced by Certification, April 2025), CourseInfo (June 2025).

**INP not FID** — FID removed September 9, 2024.

**Mobile-first is complete** — Mobile Googlebot for ALL sites since July 5, 2024.

**E-E-A-T is universal** — All competitive queries, December 2025.

**AI citation ≠ ranking** — 85% of pages ChatGPT retrieves are never cited.

**Mentions > Backlinks for AI** — 0.664 vs. 0.218 correlation.

**No paid links** — violates Google's spam policy.

**No fake reviews** — GBP suspension risk.

**Programmatic guardrails** — Warn at 100+ pages; hard stop at 500+ or <30% unique content.

**Blocking AI crawlers harms GEO** — Blocking OAI-SearchBot/PerplexityBot removes site from AI search.

**GPTBot ≠ training only** — Blocking it also limits ChatGPT Search citation.

---

## 20. Site Migration SEO

Site migration = any change to URL structure, domain, protocol, or CMS. High-risk — poor migrations cause 30–90% traffic loss.

### Migration Risk Assessment

| Migration Type | Risk Level |
|---|---|
| HTTP → HTTPS | Low |
| Subdomain → subdirectory | Medium |
| URL restructure (same domain) | Medium-High |
| Domain change | High |
| CMS platform change | High |
| Domain + URL structure change | Very High — never do both at once |

### Migration Process (Summary)

**Pre-migration**: Crawl current site (all URLs + canonicals); export 16 months of GSC data; create complete old URL → new URL redirect map; update all internal links; prepare new sitemap; add + verify new GSC property.

**Migration day**: Deploy all redirects as **301** (not 302); spot-check 20–30 URLs; submit new sitemap immediately; run GSC URL Inspection on key pages.

**Post-migration**: Monitor GSC Coverage for 404 spikes (Day 1–3); check impressions (Day 3–7); check key rankings (Week 2); benchmark at Day 30.

For the complete step-by-step checklists, common mistakes, and post-migration monitoring schedule, see `references/site-migration.md`.

→ `references/site-migration.md` | `scripts/redirect_checker.py`

---

## 21. Script Toolbox — Automated Checks

There are **24** Python **diagnostic** scripts for URL/HTML checks, plus **`requirements-check.py`** (dependency preflight) and **`score_eval_transcript.py`** (regression scoring for `evals/evals.json`). **`check-plugin-sync.py`** is maintainers/CI only and is **not** copied into the plugin bundle. **Every major audit step maps to a script** — see `references/audit-script-matrix.md`. **Merge duplicate findings** with `finding_verifier.py` using `references/finding-verifier-example.json` as the JSON shape reference (optional `references/finding-verifier-context-example.json` for context).

They are **not** invoked via subagents in this skill file: the default path is **one shell process** — either `generate_report.py` (bundled pipeline, runs the URL + HTML checks below) or targeted `python scripts/... --json` calls. **Optional:** In clients that expose a Task/subagent tool, you may delegate **independent** script runs in parallel **only when** you are **not** already running `generate_report.py` for the same URL (avoid duplicate work). Merge subagent outputs in the main thread before scoring.

**Run all individual URL checks in sequence (bash):** `bash scripts/run_individual_checks.sh https://example.com` (prints JSON from each tool; for a single HTML dashboard use `generate_report.py` instead).

### Environment Note

> Scripts require outbound network access. In sandboxed or proxy-restricted environments:
> - `pagespeed.py` will fail (calls googleapis.com) → fallback: pagespeed.web.dev manually
> - All other scripts only access the target site directly and should work normally
> - If any script fails with `ProxyError`, use the manual checklist in the corresponding reference file

**Evidence integrity:** If `pagespeed.py` did not return JSON scores, **do not** invent PSI/CrUX/LCP/CLS/INP numbers in the narrative (same rule as § 2).

### Setup (one-time)

```bash
pip install -r requirements.txt
```

### Full-Site Report — Start Here

```bash
python scripts/generate_report.py https://example.com --output seo-report.html
```

Runs the bundled analysis pipeline (see §2): URL-based scripts, homepage HTML for `validate_schema` + `image_checker`, plus dashboard sections for schema, images, sitemaps, local signals, and IndexNow probe. Use at the start of any Mode 1 full audit.

### Script Quick Reference

| Script | Purpose | Audit Section |
|---|---|---|
| `generate_report.py` | Interactive HTML dashboard — full bundled pipeline | § 2 Full Audit |
| `pagespeed.py` | Core Web Vitals via PSI API ⚠️ requires external access | § 4 Technical |
| `robots_checker.py` | robots.txt rules + AI crawler allow/block status | § 3 GEO, § 4 |
| `security_headers.py` | HSTS, CSP, X-Frame-Options — weighted score | § 4 Technical |
| `redirect_checker.py` | Full redirect chain — loops and mixed HTTP/HTTPS | § 4, § 20 |
| `validate_schema.py` | JSON-LD validation (`--json` for tools) | § 5 Schema |
| `hreflang_checker.py` | All 8 hreflang rules + bidirectional return tags | § 14 International |
| `llms_txt_checker.py` | llms.txt presence + format validation | § 3 GEO |
| `indexnow_checker.py` | IndexNow with `--key`; keyless `--probe` for reports | § 4 Technical |
| `sitemap_checker.py` | Sitemap URLs from robots + first sitemap sanity | § 11 Crawl |
| `local_signals_checker.py` | LocalBusiness JSON-LD, tel:, address signals | § 12 Local |
| `image_checker.py` | Alt coverage on saved HTML (`--base-url`) | § 13 Images |
| `entity_checker.py` | Wikidata, Wikipedia, sameAs — entity signals | § 3 GEO |
| `broken_links.py` | 4xx/5xx broken links + 3xx redirect counts | § 9 Links |
| `internal_links.py` | Link graph, orphan pages, anchor text, crawl depth | § 9 Links |
| `link_profile.py` | Deeper link graph, equity distribution | § 9 Links |
| `social_meta.py` | Open Graph + Twitter Card validation | § 4 Technical |
| `parse_html.py` | Extracts titles, H1s, meta, canonical, schema | § 2, § 4 |
| `article_seo.py` | CMS-aware article SEO — content structure, keywords | § 6 Content |
| `readability.py` | Flesch-Kincaid grade + sentence stats | § 6 Content |
| `duplicate_content.py` | Near-duplicate detection | § 6 Content |
| `meta_lengths_checker.py` | Title / meta description / H1 length & presence | § 2 On-page |
| `fetch_page.py` | Fetch and save raw HTML | General |
| `finding_verifier.py` | Deduplicates findings across a full audit | § 2 Full Audit |
| `requirements-check.py` | Verify `requests` + `beautifulsoup4` | Preflight |
| `score_eval_transcript.py` | Score a saved reply vs `evals/evals.json` | QA / regression |

### Targeted Usage

```bash
# Validate schema after generating it (machine-readable)
python scripts/validate_schema.py page.html --json

# Check AI crawler access
python scripts/robots_checker.py https://example.com

# Full redirect chain analysis
python scripts/redirect_checker.py https://example.com/old-page

# Internal link graph + orphan detection
python scripts/internal_links.py https://example.com --json

# Check llms.txt
python scripts/llms_txt_checker.py https://example.com

# Title + meta description lengths
python scripts/meta_lengths_checker.py --url https://example.com --json

# Regression: score a transcript against an eval id
python scripts/score_eval_transcript.py --eval-id 1 --text-file my-transcript.txt
python scripts/score_eval_transcript.py --all-fixtures   # bundled golden fixtures
```

---

### Attribution

Frameworks and sources this skill builds on:

| Source | Credit |
| --- | --- |
| [Agentic-SEO-Skill](https://github.com/Bhanunamikaze/Agentic-SEO-Skill) | Bhanunamikaze — SEO toolkit architecture, specialist agents, technical SEO audit framework |
| [claude-seo](https://github.com/AgriciDaniel/claude-seo) | AgriciDaniel — GEO / DataForSEO patterns, AI crawler tables, subagent delegation |
| [core-eeat-content-benchmark](https://github.com/aaron-he-zhu/core-eeat-content-benchmark) | aaron-he-zhu — CORE-EEAT 80-item framework, weights, GEO-first mapping |
| [cite-domain-rating](https://github.com/aaron-he-zhu/cite-domain-rating) | aaron-he-zhu — CITE 40-item domain authority, weights, diagnosis matrix |
| Entity Optimizer | aaron-he-zhu — entity checklist, AI entity resolution, Knowledge Graph guide |
| AI SEO / GEO Content Optimizer | aaron-he-zhu — Princeton GEO data, engine preference mapping, citation-share data |
