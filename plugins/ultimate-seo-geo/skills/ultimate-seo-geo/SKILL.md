---
name: ultimate-seo-geo
description: Audits and optimizes websites for search engine visibility (SEO) and AI search citation (GEO), covering technical health, E-E-A-T content scoring, domain authority, structured data, rich results, and entity signals. Use when running SEO audits, diagnosing traffic drops or ranking losses, generating Schema.org JSON-LD, checking Core Web Vitals, crawlability, robots.txt, sitemaps, hreflang, backlinks, planning content strategy or site migrations, fixing indexing issues, or optimizing for AI Overviews, ChatGPT, and Perplexity. NOT for paid ads (PPC/SEM), social media strategy, email marketing, or general web development unrelated to search.
version: 1.8.1
---

# Ultimate SEO + GEO — LLM-Agnostic SEO Agent

| Attribute | Details |
| --- | --- |
| **Version** | 1.8.1 |
| **Updated** | 2026-04-01 |
| **License** | MIT |
| **Author** | Myk Pono |
| **Lab** | [lab.mykpono.com](https://lab.mykpono.com) |
| **Homepage** | [lab.mykpono.com](https://lab.mykpono.com) |
| **LinkedIn** | [Profile](https://www.linkedin.com/in/mykolaponomarenko/) |
| **Platforms** | Claude Code, Cursor, Copilot, Gemini CLI, Codex, Windsurf, Cline, Aider, Devin |

The definitive SEO and Generative Engine Optimization agent. LLM-agnostic — works on any
platform that reads `AGENTS.md`. Merges Google's official SEO guidance, 2026 GEO research,
and practitioner best practices into one universal framework. Every finding comes with a
clear fix directive — not just diagnosis.

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

### Reference Reading Guide

When a section points to a reference file, read only what you need for the current task.

**Progressive Disclosure rule:** Load at most **3 reference files** per response — unless running a Mode 1 full audit with `generate_report.py`, which implicitly covers all dimensions. For single-topic Mode 2 or Mode 3 tasks (e.g., "fix my schema", "write an llms.txt"), the routing table below identifies exactly 1–2 files to load. Loading all 22 reference files for a narrow task wastes context and adds latency with no quality gain. This pattern follows Anthropic's [Skills progressive disclosure architecture](https://github.com/anthropics/claude-cookbooks/tree/main/skills).

| Task | Read | Run |
|------|------|-----|
| Full audit (any type) | `references/audit-script-matrix.md` | `generate_report.py` |
| GEO / AI citations | `references/ai-search-geo.md`, `references/entity-optimization.md` | `robots_checker.py`, `entity_checker.py`, `llms_txt_checker.py` |
| Schema markup | `references/schema-types.md` | `validate_schema.py` |
| Technical / CWV | `references/technical-checklist.md` | `pagespeed.py`, `robots_checker.py`, `security_headers.py` |
| Content / E-E-A-T | `references/eeat-framework.md`, `references/core-eeat-framework.md` | `readability.py`, `article_seo.py` |
| CITE domain audit | `references/cite-domain-rating.md` | `link_profile.py` |
| Keywords / clusters | `references/keyword-strategy.md` | — |
| Links | `references/link-building.md` | `internal_links.py`, `broken_links.py`, `link_profile.py` |
| Local SEO | `references/local-seo.md` | `local_signals_checker.py` |
| Images | `references/image-seo.md` | `image_checker.py` |
| International / hreflang | `references/international-seo.md` | `hreflang_checker.py` |
| Programmatic SEO | `references/programmatic-seo.md` | `programmatic_seo_auditor.py` |
| Migration | `references/site-migration.md` | `redirect_checker.py` |
| Analytics / myths | `references/analytics-reporting.md` | — |
| Crawl / indexation | `references/crawl-indexation.md` | `sitemap_checker.py`, `duplicate_content.py`, `canonical_checker.py`, `broken_links.py`, `internal_links.py` |

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

```
User request + URL
│
├─ "audit", "analyze", "full check", "what's wrong"
│   └─ Mode 1 → § 2
│
├─ "give me a plan", "roadmap", "what to fix first"
│   └─ Mode 2 → § 16 (run § 2 first if no audit exists)
│
├─ "fix this", "generate schema", "rewrite my titles", "run the scripts"
│   └─ Mode 3 → § 21 for scripts; relevant section for task
│
├─ Traffic drop / rankings lost
│   └─ Mode 1 focused → § 10 first, then § 6 / § 4
│
├─ AI citations / GEO question
│   └─ Mode 1 focused → § 3 first
│
├─ Domain / CMS migration
│   └─ Mode 1 focused → § 20
│
└─ No mode stated + URL / "audit + fix everything"
    └─ Mode 1 → 2 → 3 (§ 2, then § 16, then execute top findings)
```

### What "Done" Looks Like per Mode

**Audit complete** when: SEO Health Score delivered, all Critical and High findings documented in
Finding/Evidence/Impact/Fix/Confidence format, no section skipped without reason stated.

**Plan complete** when: findings grouped into four implementation phases (Foundation / Expansion /
Scale / Authority), each item has an owner action, expected outcome, and effort estimate.

**Execute complete** when: every fix implemented AND verified — run the relevant validation script,
review the output, confirm it resolves the original finding.

### Context Budget Awareness

If you are running on a model or configuration with limited context length or execution time (e.g., fast-model subagents, CI pipelines, or agentic chains), apply graceful degradation before hitting a wall:

1. **Estimate before executing.** A full Mode 1 audit with `generate_report.py` and all scripts can produce 50k+ tokens of output. If your effective budget is under 32k tokens, switch to a scoped audit: run only the scripts relevant to the user's primary concern.
2. **Prefer partial delivery over timeout.** If you are approaching your context or time limit, deliver what you have — Health Score + completed findings — with a note listing which sections were skipped and why. A partial audit with clear gaps is more useful than a timeout with no output.
3. **Web fetches are expensive.** Each site fetch adds latency and tokens. For scoped tasks (schema only, robots.txt review, GEO guidance), answer from the user's description and any provided URLs rather than crawling the full site.
4. **Compaction fallback.** If context fills mid-audit, follow § 21 (Context Management) — compress completed sections into summary bullets and continue with remaining sections.

This is a **fallback**, not a default. When context budget allows, always prefer the full audit pipeline.

---

## 1. Request Detection & Routing

If the request matches **§ 0 “When not to run Mode 1”**, route to a **narrow** answer or decline the SEO-audit template — even if generic “marketing” vocabulary appears.

**Disambiguation:** When multiple rows match, prefer the most specific. If equally specific, use the first match. If nothing matches, fall back to § 0 Intake Checklist.

This table routes by **topic**. For mode selection (Audit vs. Plan vs. Execute), see **§ 0 Mode Routing**.

| Request Type | Trigger Keywords | Go To |
|---|---|---|
| **Full Audit** | “audit”, “analyze my site”, “full check”, “site review” | § 2 Full Audit |
| **Traffic Drop / Rankings Lost** | “traffic dropped”, “lost rankings”, “rankings fell”, “why did traffic drop”, “core update”, “algorithm update”, “rankings dropped” | § 10 Analytics first, then § 4 Technical / § 6 Content |
| **GEO / AI Search** | “AI Overviews”, “ChatGPT”, “Perplexity”, “AI citations”, “GEO”, “AI Mode”, “SearchGPT”, “Gemini”, “llms.txt”, “AI search” | § 3 GEO |
| **Technical SEO** | “crawl”, “robots.txt”, “Core Web Vitals”, “speed”, “indexing”, “JS rendering”, “mobile”, “mobile-friendly”, “HTTPS”, “security headers”, “redirect chain” | § 4 Technical |
| **Schema / Structured Data** | “schema”, “JSON-LD”, “rich results”, “structured data” | § 5 Schema |
| **Content / E-E-A-T** | “content quality”, “E-E-A-T”, “thin content”, “helpful content”, “CORE-EEAT” | § 6 Content |
| **Content Scoring** | “CORE-EEAT audit”, “content score”, “CITE audit”, “domain authority score”, “GEO score” | § 6 Content |
| **Entity Optimization** | “entity”, “knowledge graph”, “knowledge panel”, “Wikidata”, “brand entity” | § 3 GEO |
| **Content Pruning / Refresh** | “old content”, “content decay”, “delete pages”, “refresh”, “consolidate” | § 6b Pruning |
| **Keyword Research** | “keywords”, “ranking opportunities”, “content gaps”, “what should I write” | § 7 Keywords |
| **Topic Clusters** | “topic cluster”, “content strategy”, “pillar page” | § 7b Clusters |
| **AEO / Featured Snippets** | “featured snippet”, “PAA”, “voice search”, “knowledge panel”, “speakable” | § 7c AEO |
| **Competitor Analysis** | “competitors”, “benchmark”, “compare to”, “X vs Y page”, “alternatives page” | § 8 Competitors |
| **Link Building** | “backlinks”, “internal links”, “anchor text”, “referring domains” | § 9 Links |
| **Analytics / Reporting** | “GA4”, “Search Console”, “CTR”, “rank tracking”, “penalty”, “manual action” | § 10 Analytics |
| **Crawl & Indexation** | “crawl budget”, “sitemap”, “canonical”, “index bloat”, “noindex”, “duplicate content”, “content cannibalization” | § 11 Crawl |
| **Local SEO** | “local”, “Google Business Profile”, “GBP”, “map pack”, “NAP” | § 12 Local |
| **Image SEO** | “images”, “alt text”, “WebP”, “image size” | § 13 Images |
| **International SEO** | “hreflang”, “multi-language”, “international”, “geo-targeting” | § 14 International |
| **Programmatic SEO** | “programmatic”, “at scale”, “templates”, “city pages”, “glossary pages” | § 15 Programmatic |
| **Strategy / Roadmap** | “SEO plan”, “roadmap”, “strategy”, “what should I focus on” | § 16 Strategy |
| **Monthly Maintenance** | “what should I check”, “monthly SEO”, “ongoing”, “monitor” | § 17 Maintenance |
| **Site Migration** | “moving domains”, “new URL structure”, “CMS migration”, “redirect map” | § 20 Migration |
| **Myths / Misconceptions** | “does X help SEO?”, “is X a ranking factor?” | § 18 Myths |
| **Script Toolbox** | “run a check”, “generate a report”, “validate schema”, “automated audit” | § 21 Scripts |
| **No clear match** | Query doesn’t match any row above | § 0 Intake Checklist |
| **Paid ads primary** | “Google Ads”, “PPC campaign”, “ad spend” without organic SEO ask | § 0 — paid scope, not Mode 1 |
| **Scoped technical only** | “only robots.txt”, “just the sitemap”, “don’t audit content” | § 0 + § 4 / § 11 — stay in scope |

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
| Schema "not found" on a CMS site | Confirmed via Rich Results Test or browser JS console — `web_fetch`/`curl`/raw HTML cannot detect JS-injected schema (Yoast, RankMath, AIOSEO inject via client-side JS) |

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

For the on-page element checklist (title tags, meta descriptions, H1, URLs, canonicals), see `references/technical-checklist.md`.

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

For a 3-finding excerpt showing the output format, see `references/audit-output-example.md`.

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
| **High-Risk** | robots.txt, canonical tags, redirect maps, noindex directives, hreflang tags, bulk CMS template changes | **Do not output the actual file or code.** Describe the change in plain language, list the specific consequences, and ask "Do you want me to proceed?" Only produce the deliverable after the user explicitly confirms. Showing the directive even as illustration defeats the safety gate — the user can copy-paste it before reading the warning. |

When implementing a specific fix:

```
1. Classify: Safe or High-Risk?
2. If High-Risk: describe the change in plain language + list consequences + ask for confirmation
   — do NOT include the actual file, code block, or directive until the user says yes
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

For 2026 platform reach and traffic signal data, see `references/ai-search-geo.md`.

### GEO Audit — Step by Step

1. **Check AI crawler access** — Fetch `/robots.txt`. Confirm OAI-SearchBot, PerplexityBot, ClaudeBot are not Disallowed.
2. **Check llms.txt** — Fetch `/llms.txt`. Missing → generate from template below. Low-cost hygiene step. Also check for **RSL 1.0 (Really Simple Licensing)** — December 2025 standard backed by Reddit, Yahoo, Medium, Quora, Cloudflare, Akamai, and Creative Commons. Check for a `/rsl.txt` file or RSL `<meta>` tag on key pages. Absence is not a penalty but early adoption signals AI-friendly intent.
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

For the Quora, Reddit, influencer, and newsletter outreach playbooks, see `references/ai-search-geo.md` → Tactical Playbooks per Channel.

For Google AI Mode–specific optimization (zero blue links, follow-up queries, Related Questions sections), see `references/ai-search-geo.md` → Platform-Specific Optimization.

For the AI crawler allow/block table (OAI-SearchBot, PerplexityBot, ClaudeBot, GPTBot, Google-Extended) and the llms.txt quick template, see `references/ai-search-geo.md`.

### GEO Finding Example

```
Finding: Key answer buried below fold — target query not answered in first 30% of content
Evidence: "How does [product] work" answered in paragraph 6, ~800 words in.
           44.2% of AI citations come from first 30% of content — this page fails.
Impact: Low AI Overview and Perplexity citation rate for the site's core query.
Fix: Move the direct answer to the opening paragraph. Keep detail further down.
Confidence: Confirmed | Severity: 🟠 High
```

### Citation Demonstration (Evaluator-Optimizer Pattern)

When auditing a page's citation potential, always produce a **before/after citation demonstration** — not just a score. Show the user what an AI-quotable passage from their content would look like:

```
CURRENT (not citable — 340 words, no direct answer in first 30%)
  "Psilocybin has been the subject of considerable scientific investigation in recent
  years, with researchers from leading institutions exploring its..."

REWRITTEN (citable — 148 words, direct answer in first sentence, source attributed)
  "Psilocybin produces psychedelic effects by binding to serotonin 5-HT2A receptors
  in the brain, temporarily altering perception and cognition (Johns Hopkins Center
  for Psychedelic Research, 2024). Effects last 4–6 hours at typical doses of
  10–30 mg. A 2023 JAMA Psychiatry meta-analysis of 11 RCTs found response rates
  of 57–80% for treatment-resistant depression."

WHY IT'S CITABLE: Self-contained (148 words, within 134–167 target), direct answer
first, specific numeric stat, dated institutional source — exactly what AI systems
prefer for citation inclusion.
```

This concrete demonstration is more actionable than a score alone. Adapted from Anthropic's [Citations cookbook](https://github.com/anthropics/claude-cookbooks/blob/main/misc/using_citations.ipynb) pattern of showing source attribution in structured output.

→ See `references/ai-search-geo.md` (full platform data, brand correlation, Wikipedia/Wikidata setup, Passage Indexing, Princeton GEO research techniques, content type citation share, AI monitoring tools, platform source selection factors) | See `references/entity-optimization.md` (47-signal entity checklist, AI Entity Resolution Test, Knowledge Graph guide) | Run `scripts/robots_checker.py` Run `scripts/entity_checker.py` Run `scripts/llms_txt_checker.py` Run `scripts/social_meta.py`

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
2. **Check robots.txt** — CSS, JS, and key pages not blocked. AI crawlers not disallowed. Two critical distinctions often misconfigured: (a) `Google-Extended` blocks Gemini training only — it does **not** affect Google Search indexing or AI Overviews (those use Googlebot); (b) `GPTBot` blocks OpenAI training only — it does **not** block ChatGPT Search citations, which uses `ChatGPT-User`. Blocking GPTBot expecting only a training opt-out silently removes the site from ChatGPT live search results if `ChatGPT-User` is also blocked.
3. **Check HTTPS** — Entire site over HTTPS. Mixed-content assets → force HTTPS via 301.
4. **Check canonical tags** — Run `scripts/canonical_checker.py URL` for single-page validation or `--crawl` for site-wide. Every indexable page needs `<link rel="canonical" href="[absolute-url]">`. Check for www/non-www mismatch, trailing slash inconsistency, and canonical chains.
5. **Check redirect chains** — Chain >1 hop → collapse to direct redirect.
6. **Check orphan pages** — Any indexed page with zero internal links. Flag here; fix in § 9.
7. **Check mobile rendering** — GSC Mobile Usability. Touch targets ≥48×48px, font ≥16px.
8. **Check soft 404s** — Run `scripts/broken_links.py` on key pages; it detects pages returning 200 but showing "not found" in `<title>`. Also check `scripts/sitemap_checker.py` output for soft 404s in sitemap. Fix: return real 404/410 or add genuine content.
9. **Check for broken internal pages** — Run `scripts/internal_links.py` (now reports 404/5xx pages found during crawl) or `scripts/broken_links.py --crawl` for site-wide broken link scan.
10. **Check JavaScript rendering** — Compare raw source to rendered DOM. Key content JS-only = invisible to AI bots.
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

→ See `references/technical-checklist.md` (detailed CWV fix steps, LCP subparts, IndexNow setup) | Run `scripts/pagespeed.py` Run `scripts/robots_checker.py` Run `scripts/redirect_checker.py` Run `scripts/security_headers.py` Run `scripts/indexnow_checker.py` Run `scripts/broken_links.py --crawl` Run `scripts/sitemap_checker.py --sample 50`

> **Script note**: `pagespeed.py` calls googleapis.com. In proxy-restricted environments it will fail — fallback: ask user to run pagespeed.web.dev and share results, or use the manual CWV checklist in `references/technical-checklist.md`.

---

## 5. Schema / Structured Data

Always use **JSON-LD** (`<script type="application/ld+json">`). Schema improves AI citation likelihood ~2.5× (Google/Microsoft, March 2025).

### Schema Audit — Step by Step

1. **Check existing schema** — Fetch page source, search `application/ld+json`. **Caveat:** `web_fetch`, `curl`, and raw HTML cannot reliably detect schema on CMS sites — many plugins (Yoast, RankMath, AIOSEO) inject JSON-LD via client-side JavaScript that won't appear in static source. If raw HTML shows no schema on a CMS site, verify with Rich Results Test (renders JS) or browser console (`document.querySelectorAll('script[type="application/ld+json"]')`) before reporting "no schema found."
2. **Validate** — Test at search.google.com/test/rich-results. Fix errors before adding new schema.
3. **Identify missing schema** — Compare to Essential Schema table below.
4. **Generate missing schema** — Use JSON-LD templates in `references/schema-types.md`.
5. **Check retired types** — See § 19. Remove truly retired schema (SpecialAnnouncement, ClaimReview, etc.). Do NOT remove HowTo — rich results removed but schema still valid for Bing and AI systems.
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
2. `@type` is valid and not retired (§ 19)
3. All required properties present
4. All URLs are absolute (not relative)
5. Dates in ISO 8601 (`YYYY-MM-DD`)
6. No placeholder text — all values are real, accurate data

For e-commerce schema additions (ProductGroup, Certification, OfferShippingDetails), recent schema types (2024–2026), and AEO schema (Sitelinks Searchbox, Speakable, Knowledge Panel sameAs), see `references/schema-types.md`.

→ See `references/schema-types.md` | Run `scripts/validate_schema.py`

---

## 6. Content Quality & E-E-A-T

### Key Policy Updates

| Update | Date | Impact |
|---|---|---|
| **E-E-A-T universal** | December 2025 | Applies to ALL competitive queries — not just YMYL |
| **AI content quality** | September 2025 QRG | AI content acceptable if genuine E-E-A-T; penalized without unique value |
| **Helpful Content System merged** | March 2024 | Merged into core algorithm — helpfulness weighted continuously |
| **Google AI Mode** | May 2025 | Available in 180+ countries; delivers **zero blue links** — AI citation is the only visibility mechanism; traditional rankings do not appear |

### Functional Page Exemption (check before auditing content)

**Before applying any content-quality or thin-content checks, classify the page type.** Functional pages have a task-completion purpose — minimal copy is correct design, not a content problem.

| Page type | Examples | Content audit rule |
|---|---|---|
| **Functional / task UI** | Sign up, Sign in, Log in, Register, Create account, Forgot password, Reset password, Join, Membership enroll, Checkout, Cart, Account dashboard, Profile settings | **Skip word-count checks entirely. Do NOT flag as thin content. Do NOT recommend adding more copy.** |
| **Landing / marketing** | Pricing, Features, About, Blog, Service pages | Apply full content audit below |
| **Content** | Blog posts, guides, case studies | Apply full content audit below |

**For functional pages, relevant checks are:** page title accuracy, meta description clarity, form label quality, error message usability, trust signals (SSL badge, privacy link), and schema (`WebPage`, `BreadcrumbList`). Never flag low word count.

---

### Content Audit — Step by Step

1. **Read the page in full.** Comprehensive coverage? Named author with credentials?
2. **Score each E-E-A-T factor** — see `references/eeat-framework.md` for the full scoring framework and factor weights.
3. **Identify the weakest factor** — this is the highest-leverage fix.
4. **Check word count**: Blog post 1,500+, Service page 800+, Homepage 500+, Product page 300+. These are topical coverage floors, not targets — Google has confirmed word count is NOT a direct ranking factor. A focused 500-word page that thoroughly answers the query outranks a padded 2,000-word page. Cover the topic fully, then stop.
5. **Check for thin content signals**: copied definitions, no original research, no first-hand examples, no author bio.
6. **Recommend specific additions** — not "add experience signals," but "add a section with real test results showing [specific outcome] from [specific test]."

**Key insight**: AI can mimic expertise but not fabricate genuine Experience. First-hand signals are the #1 E-E-A-T differentiator post-Dec 2025.

**Don't**: Recommend increasing word count as a standalone fix. Padding is a negative signal.

For the E-E-A-T scoring framework with factor weights, content quality minimums table, readability grade targets, and 2025 spam categories (expired domain abuse, site reputation abuse, scaled content abuse), see `references/eeat-framework.md` and `references/content-eeat.md`.

For the full **80-item CORE-EEAT content audit** (8 dimensions, Pass/Partial/Fail scoring, content-type weight tables, 3 veto items, GEO Score vs. SEO Score), see `references/core-eeat-framework.md`. Use this for deep content quality assessments.

For the **40-item CITE domain authority audit** (Citation/Identity/Trust/Eminence, domain-type weights, veto items that cap score at 39, Diagnosis Matrix for CITE × CORE-EEAT strategy), see `references/cite-domain-rating.md`. Use this for domain-level authority assessments.

→ See `references/eeat-framework.md` `references/content-eeat.md` `references/core-eeat-framework.md` `references/cite-domain-rating.md` | Run `scripts/article_seo.py` Run `scripts/readability.py` Run `scripts/duplicate_content.py`

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

→ See `references/content-eeat.md`

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

→ See `references/keyword-strategy.md`

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
   - **Paragraph**: 40–60 words immediately after a question-format H2/H3. Google truncates paragraph snippets beyond ~60 words, so staying under preserves the complete answer.
   - **List**: 5–9 items, each < 15 words. Lists >9 items get truncated.
   - **Table**: ≤4 columns, labeled headers.
4. **Lead with the direct answer** — "It depends" before the actual answer loses the snippet to a competitor who answers directly. Google selects the most concise, self-contained response.

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

**Comparison page title formulas** (use these for new pages targeting competitive intent):
- X vs Y: `[A] vs [B]: [Key Differentiator] ([Year])`
- Alternatives: `[N] Best [A] Alternatives in [Year] (Free & Paid)`
- Roundup: `[N] Best [Category] Tools in [Year] — Compared & Ranked`

For roundup pages, add `ItemList` schema alongside `Article` — it signals a structured list to AI systems and improves citation probability. For "X vs Y" and "Alternatives to X" page content requirements, the 4-type comparison page playbook (fairness guidelines, CTA placement rules), feature matrix structure, and nominative fair use guidance, see `references/link-building.md` → "Comparison & Alternatives Page Playbook" section.

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

→ See `references/link-building.md` (CommonCrawl backlink API, comparison page requirements) | Run `scripts/internal_links.py` Run `scripts/broken_links.py` Run `scripts/link_profile.py`

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
| **PageSpeed Insights** | Core Web Vitals field + lab data |
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

→ See `references/analytics-reporting.md`

---

## 11. Crawl & Indexation

**Rule of thumb**: Crawl budget rarely matters for sites under 500 pages. Focus on content quality first.

### Indexation Audit — Step by Step

1. `site:domain.com` in Google. Large discrepancy = investigation needed.
2. **GSC Coverage** — "Crawled - currently not indexed" (thin content) and "Submitted URL not indexed." Check "Not found (404)" for pages Google tried to index but got 404.
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

---

## 12. Local SEO

Apply whenever the site is a local business, service area business, or has physical locations.

### Audit — Step by Step

1. **Check GBP** — Not claimed → claim and verify immediately.
2. **Audit GBP completeness** — Primary category (most specific), all hours, services, photos (min 10), weekly posts.
3. **Check NAP consistency** — Character-for-character identical across GBP, website, all citations.
4. **Check review profile** — Count, average rating, recency.
5. **Verify LocalBusiness schema** — name, address, phone, geo coordinates, openingHours.

For review benchmarks (≥ 4.3 stars, ≥ 50 reviews, ≤ 30 days recency) and citation priority order, see `references/local-seo.md`.

### Location Page Quality Gates

| Threshold | Action |
|---|---|
| 30+ location pages | ⚠️ WARNING — each needs: local address, team, reviews, locally relevant content |
| 50+ location pages | 🛑 HARD STOP — city-name-only swap targeted by March 2024 Core Update |

**Don't**: Recommend fake reviews — GBP suspension risk.

→ See `references/local-seo.md`

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
| Non-LCP images | `decoding="async"` | Prevents image decoding from blocking the main thread |

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

**JPEG XL** — Chrome reversed its 2022 removal decision in November 2025, implementing via a Rust-based decoder. Not yet in Chrome stable as of March 2026. Offers ~20% lossless savings over JPEG with zero quality loss. Monitor for 2026/2027 adoption; not yet practical for production deployment.

→ See `references/image-seo.md`

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

### Implementation Methods

Choose based on site scale:

| Method | Best For | Pros | Cons |
|---|---|---|---|
| **HTML `<link>` tags** | < 50 language variants | Easy to implement, visible in source | Bloats `<head>`, hard to maintain at scale |
| **HTTP headers** | Non-HTML files (PDFs, documents) | Works for any file type | Complex server config, not visible in HTML |
| **XML sitemap** | Large sites, cross-domain setups | Scalable, centralized management | Not visible on page, requires sitemap maintenance |

**Sitemap hreflang format** (recommended for large sites):
```xml
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
  <url>
    <loc>https://example.com/page</loc>
    <xhtml:link rel="alternate" hreflang="en-US" href="https://example.com/page" />
    <xhtml:link rel="alternate" hreflang="fr" href="https://example.com/fr/page" />
    <xhtml:link rel="alternate" hreflang="x-default" href="https://example.com/page" />
  </url>
</urlset>
```
Every `<url>` entry must include all language alternates including itself. Cross-domain hreflang requires both domains verified in GSC.

→ See `references/international-seo.md` | Run `scripts/hreflang_checker.py`

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

**Scaled Content Abuse enforcement timeline:**
- **November 2024**: Site reputation abuse enforcement escalated — publishing programmatic content under a high-authority domain you don't own triggers penalties
- **June 2025**: Wave of manual actions targeting AI-generated content at scale
- **August 2025**: SpamBrain update enhanced pattern detection for AI content farms and link schemes
- **Result**: Google reported 45% reduction in low-quality, unoriginal content in search results post-March 2024
- **Progressive rollout rule**: Publish in batches of 50–100 pages. Monitor indexing and rankings for 2–4 weeks before expanding. Never publish 500+ programmatic pages simultaneously without explicit quality review.

**Automated audit**: Run `scripts/programmatic_seo_auditor.py URL --depth 2 --max-pages 100 --json` to auto-detect template URL patterns and audit each group for boilerplate ratio, content uniqueness, title/description/H1 duplication, and cross-linking health. The script flags pages below the 30% uniqueness hard stop (scaled content abuse) and 40% warning threshold.

→ See `references/programmatic-seo.md` (12 playbooks taxonomy, data-asset-to-playbook decision matrix, data defensibility hierarchy, Scaled Content Abuse enforcement timeline with dates, uniqueness calculation formula, progressive rollout strategy)

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

→ See `references/analytics-reporting.md`

---

## 18. Google's Official Stance — Myths & Misconceptions

14 common SEO myths with Google's official positions are documented in `references/analytics-reporting.md` → "Myths & Misconceptions" section. Load when a user asks "does X help SEO?" or "is X a ranking factor?" Key myths to know without loading: meta keywords tag is ignored, word count has no minimum/maximum, Core Web Vitals are a tiebreaker not primary factor, E-E-A-T describes quality but is not a direct ranking factor.

→ See `references/analytics-reporting.md`

---

## 19. Quality Gates & Hard Rules

Global rules — apply across all sections.

### Audit Self-Evaluation Pass (Evaluator-Optimizer)

After generating any Mode 1 audit output — before delivering it — run this internal evaluation pass. The purpose is to catch quality failures before the user sees them. If any criterion fails, revise before responding.

| # | Criterion | Pass Signal | Fail Action |
|---|---|---|---|
| 1 | Every Critical and High finding has an **Evidence** field from actual script output or verifiable page observation | Evidence: present on each | Add evidence or downgrade severity to Medium |
| 2 | No fabricated metrics | PSI/CrUX/LCP/CLS/INP numbers only appear if `pagespeed.py` returned JSON | Strip invented numbers; replace with "could not retrieve — verify at pagespeed.web.dev" |
| 3 | Health Score is supported by findings distribution | Critical = −15, High = −8, Medium = −3, Low = −1 applied | Recalculate or note discrepancy |
| 4 | Structured format used on every finding | Finding / Evidence / Impact / Fix / Confidence all present | Add missing fields |
| 5 | No duplicate findings | Run `finding_verifier.py` if available; manually check if not | Merge duplicates before scoring |
| 6 | Scope respected | Full audit only if user confirmed they own the site; Competitive Mode labeled "External Observation Only" | Re-label or scope down |
| 7 | Fix directives are actionable | Each fix names the specific element, file, or page to change | Rewrite vague fixes ("improve content") with exact instructions |
| 8 | No YMYL-sensitive schema without verified credentials | Never recommend MedicalWebPage, MedicalCondition, LegalService, FinancialProduct, or similar authority-claiming schema unless the site has verified professional credentials (licensed practitioners, published medical reviewers). Suggesting these without credentials risks manual action for misleading structured data. | Remove the recommendation; suggest safer alternatives (Article, WebPage, FAQPage) |
| 9 | No low-value mass changes | Never recommend touching 10+ pages for changes with zero ranking impact (e.g., removing `keywords` meta tags, cosmetic HTML cleanup). Wastes effort and introduces deployment risk. | Remove or downgrade to informational note |
| 10 | No recommending removal of valid schema | Never recommend removing structured data just because one search engine stopped showing rich results for it (e.g., HowTo). Only recommend removing truly retired types no longer processed at all. | Change "remove" to "keep — no rich results but still valid" |
| 11 | High-Risk deliverables withheld until confirmation | robots.txt, redirect maps, noindex directives, canonical overrides, and hreflang changes must NOT appear as code/file output before the user explicitly confirms. The response should describe the change and its consequences in plain language only. | Remove the code block; replace with a plain-language description and a confirmation prompt |

This pattern is adapted from Anthropic's [Evaluator-Optimizer workflow](https://github.com/anthropics/claude-cookbooks/tree/main/patterns/agents) — one pass generates, a second pass evaluates before output reaches the user.

**Retired schema (safe to remove)** — Google no longer processes these types at all: SpecialAnnouncement (July 2025), ClaimReview (June 2025), Dataset (late 2025), VehicleListing (June 2025), Practice Problem (late 2025), EstimatedSalary (June 2025), LearningVideo (June 2025), EnergyConsumptionDetails (replaced by Certification, April 2025), CourseInfo (June 2025).

**Rich results removed but schema still valid (do NOT recommend removal)** — HowTo (Sept 2023): Google no longer shows HowTo rich results, but the schema is still valid structured data. It helps Bing (which still renders HowTo rich results), AI systems that parse structured data for citations, and general content understanding. Never recommend removing valid schema just because one search engine stopped displaying rich results for it.

**INP not FID** — FID removed September 9, 2024. Referencing FID confuses users and dates the audit.

**Mobile-first is complete** — Mobile Googlebot for ALL sites since July 5, 2024.

**E-E-A-T is universal** — All competitive queries, December 2025.

**AI citation ≠ ranking** — 85% of pages ChatGPT retrieves are never cited. Being retrieved is necessary but not sufficient.

**Mentions > Backlinks for AI** — 0.664 vs. 0.218 correlation. Brand mentions on third-party platforms matter more than link building for AI citation.

**Paid links risk manual action** — violates Google's spam policy. Recommend earning links through content quality instead.

**Fake reviews risk GBP suspension** — Google actively detects fake review patterns. A suspended profile loses all local visibility.

**Programmatic guardrails** — Warn at 100+ pages; hard stop at 500+ or <30% unique content. Google's March 2024 Core Update specifically targets thin scaled content.

**Blocking AI crawlers harms GEO** — Blocking OAI-SearchBot/PerplexityBot removes the site from AI search results entirely.

**GPTBot ≠ training only** — Blocking it also limits ChatGPT Search citation. Users who block GPTBot expecting only training-opt-out lose live search visibility.

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

→ See `references/site-migration.md` | Run `scripts/redirect_checker.py`

---

## 21. Script Toolbox — Automated Checks

**Run scripts as black boxes.** Always try `python scripts/<name>.py --help` first to see usage and options. Do not read the script source code unless `--help` is insufficient and you need to customize behavior — script files are large and reading them wastes context tokens. They are designed to be invoked directly, not ingested.

There are **24** Python **diagnostic** scripts for URL/HTML checks, plus **`requirements-check.py`** (dependency preflight) and **`score_eval_transcript.py`** (regression scoring for `evals/evals.json`). **`check-plugin-sync.py`** is maintainers/CI only and is **not** copied into the plugin bundle. **Every major audit step maps to a script** — see `references/audit-script-matrix.md`. **Merge duplicate findings** with `finding_verifier.py` using `references/finding-verifier-example.json` as the JSON shape reference (optional `references/finding-verifier-context-example.json` for context).

They are **not** invoked via subagents in this skill file: the default path is **one shell process** — either `generate_report.py` (bundled pipeline, runs the URL + HTML checks below) or targeted `python scripts/... --json` calls. **Optional:** In clients that expose a Task/subagent tool, you may delegate **independent** script runs in parallel **only when** you are **not** already running `generate_report.py` for the same URL (avoid duplicate work). Merge subagent outputs in the main thread before scoring.

**Run all individual URL checks in sequence (bash):** `bash scripts/run_individual_checks.sh https://example.com` (prints JSON from each tool; for a single HTML dashboard use `generate_report.py` instead).

### Context Management for Long Audit Sessions

Full-site audits across many pages can fill the context window. When this happens:

1. **Compact findings** — Before context fills, summarize completed findings into the compact format: `[Section] Finding | Severity | Fix` — one line per finding. This preserves all actionable information in minimal tokens.
2. **Checkpoint the score** — Record the running Health Score and findings count before compacting.
3. **Continue with fresh context** — Resume from the checkpoint; load only the reference file for the next section being audited.
4. **Final merge** — At the end, merge all compacted finding lines back into the full Finding/Evidence/Impact/Fix/Confidence format for delivery.

This is adapted from Anthropic's [session memory compaction pattern](https://github.com/anthropics/claude-cookbooks/blob/main/misc/session_memory_compaction.ipynb), which uses background compaction + prompt caching to manage long-running agent conversations.

### Orchestrator-Workers: Parallel Script Execution

When the client exposes a Task/subagent tool (e.g., Cursor agents, Claude Code with parallel tool calls), scripts can be delegated as independent workers. The orchestrator (this skill) delegates, waits for all workers to complete, then synthesizes:

```
Orchestrator (this skill)
├── Worker A: python scripts/robots_checker.py   → JSON findings
├── Worker B: python scripts/sitemap_checker.py  → JSON findings
├── Worker C: python scripts/security_headers.py → JSON findings
└── Synthesize: merge all JSON → run finding_verifier.py → score
```

**Hard constraints:** Never delegate `generate_report.py` and individual script workers for the same URL simultaneously — they overlap and produce duplicate findings. Use one or the other. This pattern follows Anthropic's [Orchestrator-Workers pattern](https://github.com/anthropics/claude-cookbooks/blob/main/patterns/agents/orchestrator_workers.ipynb).

### DataForSEO MCP (Optional)

If DataForSEO MCP tools are available, they can enrich audits with live data beyond what the bundled scripts provide:

| Tool | Purpose |
|---|---|
| `ai_optimization_chat_gpt_scraper` | Check actual ChatGPT web search results for target queries (real GEO visibility check) |
| `ai_opt_llm_ment_search` + `ai_opt_llm_ment_top_domains` | LLM mention tracking across AI platforms |
| `on_page_instant_pages` | Real page analysis — status codes, page timing, broken links, on-page checks |
| `on_page_lighthouse` | Lighthouse audit — performance, accessibility, SEO scores |
| `dataforseo_labs_google_competitors_domain` + `domain_intersection` | Real competitive intelligence |
| `kw_data_google_ads_search_volume` + `dataforseo_labs_bulk_keyword_difficulty` | Keyword volume and difficulty |
| `serp_organic_live_advanced` | Live SERP positions and SERP feature analysis |
| `backlinks_summary` | Backlink data with spam scores |
| `business_data_business_listings_search` | Local business data for Local SEO |

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

For the complete script-to-section mapping (all 24 scripts with purpose and audit section), see `references/audit-script-matrix.md`.

### Targeted Usage

```bash
# Validate schema after generating it
python scripts/validate_schema.py page.html --json

# Check AI crawler access
python scripts/robots_checker.py https://example.com

# Check llms.txt
python scripts/llms_txt_checker.py https://example.com

# Regression: score a transcript against eval fixtures
python scripts/score_eval_transcript.py --all-fixtures
```

---

### Attribution

Frameworks and sources this skill builds on:

| Source | Credit |
| --- | --- |
| Agentic-SEO-Skill (github.com/Bhanunamikaze) | Bhanunamikaze — SEO toolkit architecture, specialist agents, technical SEO audit framework |
| claude-seo (github.com/AgriciDaniel) | AgriciDaniel — GEO / DataForSEO patterns, AI crawler tables, subagent delegation |
| core-eeat-content-benchmark (github.com/aaron-he-zhu) | aaron-he-zhu — CORE-EEAT 80-item framework, weights, GEO-first mapping |
| cite-domain-rating (github.com/aaron-he-zhu) | aaron-he-zhu — CITE 40-item domain authority, weights, diagnosis matrix |
| Entity Optimizer (github.com/aaron-he-zhu) | aaron-he-zhu — entity checklist, AI entity resolution, Knowledge Graph guide |
| AI SEO / GEO Content Optimizer (github.com/aaron-he-zhu) | aaron-he-zhu — Princeton GEO data, engine preference mapping, citation-share data |
| Anthropic claude-cookbooks (github.com/anthropics/claude-cookbooks) | Anthropic — Evaluator-Optimizer pattern (§19 self-review), Progressive Disclosure architecture (§0), Orchestrator-Workers for parallel scripts (§21), Session Memory Compaction (§21), Citations pattern for GEO demonstration (§3) |
