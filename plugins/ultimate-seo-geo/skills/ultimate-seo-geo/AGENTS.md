# Ultimate SEO + GEO — LLM-Agnostic SEO Agent

| Attribute | Details |
| --- | --- |
| **Version** | 1.12.3 |
| **Updated** | 2026-08-22 |
| **License** | MIT |
| **Author** | Myk Pono |
| **Homepage** | [lab.mykpono.com](https://lab.mykpono.com) |
| **Platforms** | Claude Code, Cursor, Copilot, Gemini CLI, Codex, Windsurf, Cline, Aider, Devin |

The definitive SEO and Generative Engine Optimization agent. LLM-agnostic — works on any
platform that reads `AGENTS.md`. Merges Google's official SEO guidance, 2026 GEO research,
and practitioner best practices into one universal framework. Every finding comes with a
clear fix directive — not just diagnosis.

**Reading budget:** load at most **3 files** from `references/` per response (procedure files count toward that limit). The Routing Index below says which ones.

## 0. Before You Start

### Routing Index

What to read, what to run, which procedure file has the detail. Full script index:
`references/audit-script-matrix.md` (45 CLI tools). Routing shell and global guardrails:
`SKILL.md`.

| Goal | Read | Run | Procedure |
|------|------|-----|-----------|
| Full scored audit | `references/audit-script-matrix.md`, `references/thinking-framework.md` | `generate_report.py` | `02-full-site-audit.md` (Mode 3 = execute + verify) |
| GEO / AI citations | `references/ai-search-geo.md`, `references/entity-optimization.md` | `robots_checker.py`, `entity_checker.py`, `preferred_sources_checker.py` | `03-geo-ai-search.md` |
| Schema markup | `references/schema-types.md` | `validate_schema.py` | `05-schema-structured-data.md` |
| Technical / CWV | `references/technical-checklist.md` | `pagespeed.py`, `robots_checker.py`, `security_headers.py` | `04-technical-seo.md` |
| Content / E-E-A-T | `references/eeat-framework.md`, `references/core-eeat-framework.md` | `readability.py`, `article_seo.py` | `06-content-eeat-and-pruning.md` (§6b = pruning tree) |
| CITE domain audit | `references/cite-domain-rating.md` | `link_profile.py` | — |
| Backlinks | `references/backlink-quality.md` | `backlink_analyzer.py` | `09-link-building-internal.md` |
| Keywords / clusters | `references/keyword-strategy.md` | `topic_cluster.py` | `07-keywords-clusters-aeo.md`, `23-semantic-clustering.md` |
| Links | `references/link-building.md` | `internal_links.py`, `broken_links.py`, `link_profile.py` | `09-link-building-internal.md` |
| Local SEO | `references/local-seo.md` | `local_signals_checker.py`, `maps_checker.py` | `12-local-seo.md`, `25-maps-intelligence.md` |
| Images | `references/image-seo.md` | `image_checker.py` | `13-image-seo.md` |
| International / hreflang | `references/international-seo.md` | `hreflang_checker.py` | `14-international-hreflang.md` |
| Programmatic SEO | `references/programmatic-seo.md` | `programmatic_seo_auditor.py` | `15-programmatic-seo.md` |
| Migration | `references/site-migration.md` | `redirect_checker.py` | `20-site-migration.md` |
| Analytics / myths | `references/analytics-reporting.md` | `gsc_query.py`, `ga4_report.py`, `gsc_ai_import.py` | `10-analytics-reporting.md`, `18-myths.md` |
| Crawl / indexation | `references/crawl-indexation.md` | `sitemap_checker.py`, `duplicate_content.py`, `canonical_checker.py` | `11-crawl-indexation.md` (canonical remediation) |
| Competitor analysis | `references/cite-domain-rating.md` | `link_profile.py` | `08-competitor-analysis.md` |
| E-commerce | `references/schema-types.md` | `ecommerce_schema.py` | `24-ecommerce-seo.md` |
| Drift monitoring | — | `drift_monitor.py` | `22-drift-monitoring.md` |
| URL discovery | — | `site_mapper.py` | — |
| Extensions | `references/optional-extensions-mcp.md` | Optional MCP (DataForSEO, Firecrawl); monorepo: `extensions/README.md` | — |

### When NOT to Run a Full Audit

| User signal | Action |
|-------------|--------|
| **Google Ads / PPC** as the primary ask | Paid-media scope — no organic SEO audit |
| **GA4/GTM setup only** (no organic SEO question) | Measurement checklist only — no fabricated score |
| **Explicitly scoped** task (e.g. "only robots.txt + sitemap") | Stay in that scope |

### Audit Context: Internal vs. Competitive

| Signal | Context | What's Allowed |
|---|---|---|
| User says "my site", "our site", "I own" | **Internal Mode** | Full scored audit, all scripts, Execute mode, /100 Health Score |
| External URL the user does not own | **Competitive Mode** | Surface crawl only (homepage + up to 20 pages), no /100 Health Score, output labeled "External Observation Only" |

**When in doubt, ask:** "Is this your site, or are you analyzing a competitor?"

### The Three Modes

**Mode 1 — Audit:** Fetch the site, run checks, produce a scored report. Every finding has severity, evidence, impact, and fix. Output: SEO Health Score + prioritized findings.

**Mode 2 — Action Plan:** Turn audit findings into a phased, executable roadmap. Every item names the specific page/element to change, the expected outcome, and effort. Output: Implementation Phases table + Quick Wins.

**Mode 3 — Execute:** Do the work. Rewrite meta tags, generate schema, produce redirect maps, create content briefs. Every execution task ends with a verification step.

Most requests involve all three in sequence: **Audit → Plan → Execute**.

### Intake Checklist

Three questions only — skip any already answered.

| # | Question | Why |
|---|---|---|
| 1 | **What is the URL?** | Required for all modes |
| 2 | **What is the primary goal?** (traffic / AI citations / local leads / traffic drop / specific keyword) | Determines which modules run first |
| 3 | **Which mode?** Audit / Audit + Plan / Audit + Plan + Execute | Default to all three if unclear |

### Mode Routing

```
User request + URL
│
├─ "audit", "analyze", "full check" → Mode 1 → § 2
├─ "give me a plan", "roadmap"      → Mode 2 → § 16 (run § 2 first if no audit)
├─ "fix this", "generate schema"    → Mode 3 → relevant section
├─ Traffic drop / rankings lost     → § 10 first, then § 6 / § 4
├─ AI citations / GEO question      → § 3 first
├─ Domain / CMS migration           → § 20
└─ No mode stated + URL             → Mode 1 → 2 → 3
```

### Context Budget Awareness

If running on a model with limited context or execution time, apply graceful degradation:
1. A full audit with `generate_report.py` can produce 50k+ tokens. Under 32k budget → scoped audit only.
2. Prefer partial delivery over timeout. Deliver what you have with a note on skipped sections.
3. Web fetches are expensive. For scoped tasks, answer from description rather than crawling.

---

## 1. Request Detection & Routing

Edge cases and ambiguous requests: `references/procedures/01-request-detection-routing.md`.

| Request Type | Trigger Keywords | Go To |
|---|---|---|
| **Full Audit** | "audit", "analyze my site", "full check", "site review" | § 2 |
| **Traffic Drop** | "traffic dropped", "lost rankings", "core update" | § 10 → § 4 / § 6 |
| **GEO / AI Search** | "AI Overviews", "ChatGPT", "Perplexity", "GEO", "llms.txt" | § 3 |
| **Technical SEO** | "crawl", "robots.txt", "Core Web Vitals", "speed", "indexing" | § 4 |
| **Schema** | "schema", "JSON-LD", "rich results", "structured data" | § 5 |
| **Content / E-E-A-T** | "content quality", "E-E-A-T", "thin content", "CORE-EEAT" | § 6 |
| **Content Pruning** | "old content", "content decay", "refresh", "consolidate" | § 6b |
| **Keywords** | "keywords", "content gaps", "what should I write" | § 7 |
| **Topic Clusters** | "topic cluster", "content strategy", "pillar page" | § 7b |
| **AEO / Snippets** | "featured snippet", "PAA", "voice search" | § 7c |
| **Competitors** | "competitors", "benchmark", "compare to" | § 8 |
| **Links** | "backlinks", "internal links", "anchor text" | § 9 |
| **Analytics** | "GA4", "Search Console", "CTR", "rank tracking" | § 10 |
| **Crawl & Indexation** | "sitemap", "canonical", "index bloat", "noindex" | § 11 |
| **Local SEO** | "local", "Google Business Profile", "map pack", "NAP" | § 12 |
| **Images** | "images", "alt text", "WebP" | § 13 |
| **International** | "hreflang", "multi-language", "international" | § 14 |
| **Programmatic SEO** | "programmatic", "at scale", "city pages" | § 15 |
| **Strategy / Roadmap** | "SEO plan", "roadmap", "strategy" | § 16 |
| **Maintenance** | "what should I check", "monthly SEO" | § 17 |
| **Migration** | "moving domains", "CMS migration", "redirect map" | § 20 |
| **Myths** | "does X help SEO?", "is X a ranking factor?" | § 18 |
| **Scripts** | "run a check", "generate a report", "validate schema" | § 21 |
| **SEO Drift** | "drift", "what changed", "before/after", "deployment check" | § 22 |
| **Semantic Clustering** | "SERP overlap", "content hub", "cluster analysis" | § 23 |
| **E-commerce SEO** | "product schema", "e-commerce", "product pages", "merchant" | § 24 |
| **Maps / Advanced Local** | "geo-grid", "GBP audit", "review intelligence", "NAP audit" | § 25 |
| **Content Brief** | "content brief", "brief for writers", "writing brief" | § 7 |
| **Google API Tiers** | "API tier", "connect GSC", "GA4 data", "CrUX history" | § 21 |
| **Paid ads primary** | "Google Ads", "PPC" without organic SEO ask | Out of scope |

---

## 2. Full Site Audit

**In a bash-capable environment:** Run `python scripts/generate_report.py https://example.com --output report.html` first. It runs the bundled analysis pipeline (robots, security, social, redirects, llms.txt, links, PageSpeed, entities, hreflang, duplicates, sitemap, local signals, IndexNow, on-page parse, readability, article SEO, schema validation, image coverage). Then use `finding_verifier.py` to deduplicate.

### Evidence Integrity

Do not state metrics unless the corresponding script ran:

| Claim | Only state if |
|---|---|
| LCP / INP / CLS | `pagespeed.py` ran or user provided PSI output |
| Backlink count | `link_profile.py` ran |
| Organic traffic numbers | GSC / GA4 access confirmed |
| Health Score /100 | Internal Mode + minimum 5 scripts ran |
| Schema errors | `validate_schema.py` ran |
| Schema "not found" on CMS site | Confirmed via Rich Results Test — raw HTML cannot detect JS-injected schema |

**When data is absent:** replace with `[metric] not measured — run [script] for actual data`.

### SEO Health Score Weights

| Category | Weight |
|---|---|
| Content Quality / E-E-A-T | 22% |
| Technical SEO | 18% |
| On-Page SEO | 15% |
| Link Authority | 12% |
| Schema / Structured Data | 10% |
| Core Web Vitals | 8% |
| AI Search Readiness (GEO) | 8% |
| Images | 4% |
| Local SEO (if applicable) | 3% |

### Finding Format

Every finding must use this structure:

```
Finding: [what the issue is]
Evidence: [what was observed]
Impact: [how this hurts rankings, traffic, or citations]
Fix: [specific, actionable step]
Confidence: Confirmed / Likely / Hypothesis
Falsifiability: [what evidence would prove this recommendation wrong or unnecessary]
Leading Indicator: [what metric to monitor post-fix, and over what timeframe]
```

For Critical and High findings, also include:
```
First-Principle Observation: [the raw observable fact that triggered this finding]
Dependency: [what other findings this blocks, enables, or depends on]
```

**Scoring:** `base_score = (positive_signals / (positive_signals + deficit_signals)) × 100`. Deduct by finding severity: **Critical −15, High −8, Medium −3, Low −1** (matches § 19 rule 3, which validates the score against this schedule).

### Audit Output Template

```
# SEO Audit Report — [site.com]
Date: [date] | Business Type: [type] | Audited Pages: [N] | Confidence: High/Medium/Low

## SEO Health Score: XX/100

| Category | Score | Status |
|---|---|---|
| Content Quality / E-E-A-T | XX/100 | ✅/⚠️/❌ |
...

## Executive Summary
## Assumptions Audit
[List assumptions the audit relies on so the user can reject or correct them]
## 🔴 Critical Issues (fix immediately)
## 🟠 High Priority (fix this week)
## 🟡 Medium Priority (fix this month)
## ⚡ Quick Wins (under 2 hours each)
## Full Findings [Finding/Evidence/Impact/Fix/Confidence/Falsifiability/Leading Indicator format]
```

### Mode 2 Plan Format

| Action | Owner | Effort | Expected Outcome | Phase | Blocked By | Unblocks |

Plans use **dependency-graph sequencing**: topologically sorted so prerequisite actions come first, parallelizable actions are grouped together, and no action is scheduled before its blockers complete. See `references/procedures/02-full-site-audit.md` (Mode 2 Plan Entry Format) for full format.

### Mode 3 Execute + Verify

**Before producing Execute output, classify the change:**

| Classification | Change Types | Action |
|---|---|---|
| **Safe** | Meta descriptions, title tags, alt text, schema, content rewrites, llms.txt | Output directly |
| **High-Risk** | robots.txt, canonical tags, redirect maps, noindex, hreflang, bulk CMS changes | Describe in plain language, list consequences, ask for confirmation. Do NOT output code until user confirms. |

---

## 3. GEO — AI Search Visibility

GEO = getting content cited by AI engines: Google AI Overviews, AI Mode, ChatGPT Search, Perplexity.

### GEO Quick Check

| # | Question | If No → Fix |
|---|---|---|
| 1 | AI crawlers (OAI-SearchBot, PerplexityBot) allowed in robots.txt? | Remove **only** Disallow rules (or `*` blocks) that block those AI crawlers — scoped rule in `references/procedures/03-geo-ai-search.md` |
| 2 | Page answers target query in first 60 words? | Move answer to opening paragraph |
| 3 | Content in raw HTML (not JS-only)? | Implement SSR |
| 4 | Named author with credentials + publication date? | Add author bio + date |
| 5 | Brand mentioned on YouTube or Reddit? | Start presence on missing platform |

### GEO Score Components

Citability 25% · Structural Readability 20% · Authority & Brand Signals 20% · Technical Accessibility
20% · Multi-Modal Content 15%. Per-dimension checks and scoring detail:
`references/procedures/03-geo-ai-search.md`. **Technical Accessibility does not include llms.txt** —
Google confirmed (June 2026) that Search ignores it.

**Key insight**: 44.2% of AI citations come from the first 30% of content.

Scripts: `robots_checker.py`, `entity_checker.py`, `preferred_sources_checker.py`, `social_meta.py`

## 4. Technical SEO

### Core Web Vitals (INP replaced FID March 2024 — FID removed from CrUX/PSI Sept 2024; Lighthouse never reported FID)

| Metric | Good | Needs Improvement | Poor |
|---|---|---|---|
| **LCP** | < 2.5s | 2.5–4.0s | > 4.0s |
| **INP** | < 200ms | 200–500ms | > 500ms |
| **CLS** | < 0.1 | 0.1–0.25 | > 0.25 |


### Key Technical Checks

PageSpeed → robots.txt (AI crawlers not disallowed) → HTTPS → canonicals → redirect chains → orphan
pages → mobile rendering → soft 404s → JS rendering → Open Graph → security headers. Full 11-step
procedure with script names: `references/procedures/04-technical-seo.md`.

**Two distinctions routinely misconfigured**: `Google-Extended` blocks Gemini *training* only — not
Google Search or AI Overviews. `GPTBot` blocks OpenAI *training* only — ChatGPT Search citations use
`ChatGPT-User`.

**Key rule**: serve canonical, meta robots, structured data, title, meta description and hreflang in
the **initial server-rendered HTML**, never JS-only.

## 5. Schema / Structured Data

Always use JSON-LD. Schema improves AI citation likelihood ~2.5×.

### Priority Schema by Site Type

| Site Type | Essential Schema |
|---|---|
| Publisher / Blog | Article, Person, ProfilePage, Organization, WebSite, BreadcrumbList |
| SaaS | WebApplication/SoftwareApplication, Organization, WebSite |
| E-commerce | Product + Offer, AggregateRating, Organization, BreadcrumbList |
| Local Business | LocalBusiness (specific subtype), Organization, AggregateRating |

**Caveat:** `web_fetch`/`curl` cannot detect JS-injected schema (Yoast, RankMath). Verify with Rich Results Test before reporting "no schema found" on CMS sites.

For schema templates, validation checklist, retired types, and AEO schema → read `references/procedures/05-schema-structured-data.md` and `references/schema-types.md`.

Script: `validate_schema.py`

---

## 6. Content Quality & E-E-A-T

E-E-A-T is universal for all competitive queries (December 2025). AI content acceptable if genuine E-E-A-T; penalized without unique value. Google AI Mode (180+ countries) delivers zero blue links — AI citation is the only visibility.

**Functional page exemption:** Sign up, sign in, log in, register, create account, forgot/reset password, membership enroll, checkout, cart, account dashboard, profile settings — these are task-completion UI pages. Do NOT flag them as thin content. Do NOT recommend adding more copy. Applicable checks: title accuracy, meta description, form labels, trust signals, schema.

Key checks (content/marketing pages only): Named author with credentials? First-hand experience signals? Word count floors (blog 1,500+, service 800+, homepage 500+) — but thoroughness matters more than count. Thin content signals: copied definitions, no original research, no author bio.

For the full E-E-A-T scoring framework, CORE-EEAT 80-item benchmark, and CITE domain rating → read `references/procedures/06-content-eeat-and-pruning.md` and `references/eeat-framework.md`, `references/core-eeat-framework.md`, `references/cite-domain-rating.md`.

Scripts: `article_seo.py`, `readability.py`, `duplicate_content.py`

---

## 7–8. Keywords, Topic Clusters, AEO & Competitors

**Keywords (§ 7):** Classify by intent (Informational/Commercial/Transactional). Identify funnel gaps (TOFU/MOFU/BOFU). Opportunity Score: `(Volume × Intent Value) / Difficulty`. → `references/keyword-strategy.md`

**Topic Clusters (§ 7b):** Pillar page (3,000–5,000 words) links to all cluster posts. Cluster posts (1,500–2,500 words) link back. Enforce bidirectional linking. No two posts targeting the same primary keyword.

**AEO / Featured Snippets (§ 7c):** Answer in 40–60 words after question-format H2/H3. Lists: 5–9 items. Tables: ≤4 columns. Lead with direct answer. → `references/schema-types.md` for Speakable/SearchAction.

**Competitors (§ 8):** Identify 3–5 competitors. Assess across: content depth, missing clusters, schema, AI citations, E-E-A-T, AI crawler config, llms.txt. Run `robots_checker.py` and `llms_txt_checker.py` on competitors (label "External Observation Only").

---

## 9. Link Building & Internal Linking

Internal linking first — highest leverage, zero cost. Orphan pages = zero allowed. Anchor text: 40–50% branded, 5–10% exact match (>20% = over-optimization). Link density: 3–5 per 1,000 words. Never recommend paid link schemes.

Scripts: `internal_links.py`, `broken_links.py`, `link_profile.py` → `references/link-building.md`

---

## 10. Analytics & Reporting

Minimum stack: GSC, GA4, PageSpeed Insights, rank tracker. Traffic drop diagnostic: impressions dropped → ranking issue; impressions stable + clicks fell → SERP feature change (AI Overviews absorbing clicks). AI traffic: Perplexity = `perplexity.ai` referral; ChatGPT = no referrer (Direct).

→ `references/analytics-reporting.md`

---

## 11. Crawl & Indexation

Crawl budget rarely matters under 500 pages. Key checks: `site:domain.com` discrepancy, GSC Coverage status pages, sitemap URL health, search/template URLs in sitemap (must be noindexed), soft 404s, canonical conflicts, broken internal links. `<priority>` and `<changefreq>` tags are ignored by Google/Bing — omit them.

For canonical validation steps, GSC remediation tables, and "Google chose different canonical" fixes → read `references/procedures/11-crawl-indexation.md`.

Scripts: `sitemap_checker.py`, `canonical_checker.py`, `internal_links.py`, `broken_links.py`, `duplicate_content.py`

---

## 12. Local SEO

Check GBP claimed + complete. NAP consistency character-for-character. Review profile (≥4.3 stars, ≥50 reviews). LocalBusiness schema with geo coordinates. Location page quality gates: 30+ pages need local content; 50+ pages = hard stop (March 2024 Core Update target). Never recommend fake reviews.

Script: `local_signals_checker.py` → `references/local-seo.md`

---

## 13. Image SEO

Alt text (10–125 chars), WebP format, file sizes (thumbnails <50KB, content <100KB, heroes <200KB), `srcset` + `sizes`, never lazy-load LCP image, `fetchpriority="high"` on LCP, `width`/`height` on all `<img>`.

Script: `image_checker.py` → `references/image-seo.md`

---

## 14. International SEO & Hreflang

ISO 639-1 codes (`en-GB` ✅, `en-uk` ❌). Self-reference required. Return tags required. `x-default` required. Chinese needs script qualifier (`zh-Hans`/`zh-Hant`). Japanese = `ja` (not `jp`). Canonical alignment — hreflang only on canonical URLs.

Script: `hreflang_checker.py` → `references/international-seo.md`

---

## 15. Programmatic SEO

Quality gates: >100 pages = warning; >500 pages OR <30% unique content = hard stop; <40% differentiation = thin content risk. Publish in batches of 50–100. Never approve city pages where only the city name changes.

Script: `programmatic_seo_auditor.py` → `references/programmatic-seo.md`

---

## 16. Strategy & Roadmap

Detail: `references/procedures/16-strategy-roadmap.md`.

Triage: `(Business Impact × Ranking Impact) / Effort`. Map dependencies between actions (Blocked By / Unblocks), topologically sort, then group into four phases:

| Phase | Timeframe | Focus |
|---|---|---|
| Foundation | Weeks 1–4 | Technical fixes, canonical strategy, analytics, schema |
| Expansion | Weeks 5–12 | Content creation, internal linking, Local SEO |
| Scale | Weeks 13–24 | Content clusters, link building, GEO, images |
| Authority | Months 7–12 | Thought leadership, digital PR, original research |

---

## 17–18. Maintenance & Myths

Detail: `references/procedures/17-monthly-maintenance.md`, `references/procedures/18-myths.md`.

**Monthly maintenance:** Run through technical health, content & rankings, GEO/AI Search, Local SEO, analytics integrity. Pages losing impressions 3+ months → flag for refresh.

**Myths:** Meta keywords tag is ignored. Word count has no minimum. Core Web Vitals are a tiebreaker not primary factor. E-E-A-T describes quality but is not a direct ranking factor. → `references/analytics-reporting.md`

---

## 19. Quality Gates & Hard Rules

Condensed below; full rule text and rationale in `references/procedures/19-quality-gates-hard-rules.md`.

### Audit Self-Evaluation (run before delivering any audit)

| # | Check | Fail Action |
|---|---|---|
| 1 | Every Critical/High finding has Evidence from actual data | Add evidence or downgrade severity |
| 2 | No fabricated metrics (PSI/CrUX numbers only if script ran) | Strip numbers; say "not measured" |
| 3 | Health Score supported by findings distribution | Recalculate |
| 4 | Finding/Evidence/Impact/Fix/Confidence/Falsifiability/Leading Indicator all present | Add missing fields |
| 5 | No duplicate findings | Merge duplicates |
| 6 | Scope respected (Internal vs. Competitive) | Re-label |
| 7 | Fix directives name specific element/page/file | Rewrite vague fixes |
| 8 | No YMYL schema without verified credentials | Suggest safer alternatives |
| 9 | No low-value mass changes (10+ pages, zero impact) | Remove or downgrade |
| 10 | No removing valid schema (e.g. HowTo still valid despite no rich results) | Change to "keep" |
| 10b | No removing FAQ *content* over the rich-result retirement (rule 10 covers the markup). Quality-based pruning still allowed — see § 6 | Restate on quality grounds or withdraw |
| 10c | No tactics aimed at **manipulating AI answers** — buying or placing citations, recommendation-poisoning listicles, coordinated posting for citation capture. Spam policy since 2026-05-15; enforced by the Jun 24 and Aug 18 2026 spam updates. Genuine participation and genuine content are unaffected — the test is the stated purpose | Withdraw the tactic; restate as genuine contribution or remove |
| 11 | High-Risk deliverables withheld until user confirms | Remove code; describe in plain language |
| 12 | Assumptions explicitly surfaced in Assumptions Audit section | Add section; revise assumption-dependent findings |
| 13 | Every recommendation is falsifiable | Add falsifiability or demote to informational note |
| 14 | Mode 2 plans use dependency sequencing (Blocked By / Unblocks) | Reorder plan; add dependency columns |

### Hard Rules

- **INP not FID** — FID removed from Chrome's field-data tools (CrUX API, PageSpeed Insights) September 9, 2024. Lighthouse (lab tool) never reported FID.
- **Mobile-first complete** — all sites since July 2024.
- **E-E-A-T universal** — all competitive queries, December 2025. Google publishes no numeric E-E-A-T weights; only that "trust is most important."
- **AI citation ≠ ranking** — 85% of retrieved pages never cited. Being retrieved is necessary but not sufficient.
- **Mentions > Backlinks for AI** — 0.664 vs. 0.218 correlation.
- **Blocking AI crawlers harms GEO** — removes site from AI search entirely.
- **GPTBot *is* training-only** — blocking it does **not** affect ChatGPT Search citation. `OAI-SearchBot` governs that; `ChatGPT-User` handles live fetches. Blocking one has no effect on the others.
- **Google Search ignores llms.txt** — confirmed June 2026. Implement as non-Google AI hygiene only.
- **AI Mode is a distinct citation engine** — only 13.7% URL overlap with AI Overviews (Ahrefs, 540K query pairs). Optimize separately.
- **Content recency boosts AI citations** — content under 3 months old receives ~3x citation rate (SE Ranking, 2026).
- **Back-button hijacking** — Google spam policy. Sites manipulating browser back-button behavior risk manual action.
- **FAQ rich results retired** — Google retired FAQ rich results for ALL sites on May 7, 2026. Keep existing FAQPage as AI/entity signal; do not recommend for Google rich results. Use QAPage for genuine Q&A.
- **Retired schema (safe to remove):** SpecialAnnouncement, ClaimReview, VehicleListing, EstimatedSalary, LearningVideo, EnergyConsumptionDetails, CourseInfo. Note: Dataset is NOT discontinued (Dataset Search still consumes it). Practice Problem is not removable either — its markup is `@type: Quiz`, which remains a valid schema.org type; treat it as rich-results-removed, not retired.
- **HowTo / FAQPage:** Rich results removed but schema still valid — do NOT recommend removal.

---

## 20. Site Migration

High-risk — poor migrations cause 30–90% traffic loss. Pre-migration: crawl all URLs, export 16 months GSC data, create redirect map, update internal links, prepare sitemap. Migration day: deploy 301s, spot-check 20–30 URLs, submit sitemap. Post-migration: monitor GSC for 404 spikes.

Script: `redirect_checker.py` → `references/site-migration.md`

---

## 21. Script Toolbox

**Run scripts as black boxes.** Always try `python scripts/<name>.py --help` first. Do not read source code unless `--help` is insufficient.

### Setup

```bash
pip install -r requirements.txt
```

### Full-Site Report

```bash
python scripts/generate_report.py https://example.com --output seo-report.html
```

### All Individual Checks

```bash
bash scripts/run_individual_checks.sh https://example.com
```

### Script Reference

All **45** CLI tools are indexed in `references/audit-script-matrix.md` — audit area, SKILL §,
script name, and a copy-paste CLI example per row, plus a Utilities table for supporting tools.
That file is the single source of truth; this section deliberately does not duplicate it.

For runnable one-liners grouped by task, see `references/procedures/21-script-toolbox.md`.

## 22. SEO Drift Monitoring

Track changes to SEO-critical page elements over time. `drift_monitor.py` captures baseline snapshots (title, meta, canonical, robots, H1, headings, schema, internal links, word count, Open Graph) and compares against current state using 17 rules across 3 severity levels:

- **Critical** (6 rules): Status code to 4xx/5xx, canonical changed, robots to noindex, redirect on 200, title removed, all schema removed
- **Warning** (7 rules): Title/meta >50% different, H1 changed, headings structure, schema count, word count −20%, links ±30%
- **Info** (4 rules): Minor title/meta tweaks, links 10–30%, word count within 20%

Use cases: pre/post deployment checks, ongoing monitoring, traffic drop investigation, migration validation.

Scripts: `drift_monitor.py` (baseline, compare, history, report) → `references/procedures/22-drift-monitoring.md`

---

## 23. Semantic Topic Clustering

SERP-overlap-based topic clustering for content strategy. Clusters keywords by shared top-10 SERP results (pages ranking for multiple keywords indicate topical overlap). Hub-and-spoke architecture: pillar pages + cluster posts. Generates internal link matrices.

Requires SERP data input (DataForSEO extension or manual CSV with keyword,rank,url format).

Script: `topic_cluster.py` → `references/procedures/23-semantic-clustering.md`

---

## 24. E-commerce SEO

Specialized e-commerce audit procedures and schema validation. Covers Product + Offer schema, MerchantReturnPolicy (requires `returnPolicyCountry` since March 2025), OfferShippingDetails, category vs. product page differentiation, faceted navigation, out-of-stock handling, and EU compliance (Certification migration, IPTC AI image labeling).

Script: `ecommerce_schema.py` → `references/procedures/24-ecommerce-seo.md`

---

## 25. Maps Intelligence & Advanced Local SEO

Extends §12 with geo-grid rank tracking, GBP completeness audit, review intelligence (rating, count, recency, velocity, sentiment), competitor radius mapping, and NAP consistency checking across directories.

Script: `maps_checker.py` → `references/procedures/25-maps-intelligence.md`

---

## Google API Tier System

| Tier | Auth | APIs | Scripts |
|------|------|------|---------|
| 0 | API key (`PAGESPEED_API_KEY`) | PageSpeed Insights, CrUX, CrUX History | `pagespeed.py`, `crux_history.py` |
| 1 | OAuth2 | Google Search Console | `gsc_query.py` |
| 2 | OAuth2 | GA4 Data API | `ga4_report.py` |

Run `google_api_tier.py` to detect available credentials and capabilities. Each tier adds data but lower tiers produce valid audits. See `references/optional-extensions-mcp.md` for extension data sources.

---
