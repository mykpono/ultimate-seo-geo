<!-- Audit output examples — referenced from SKILL.md § 2 and § 3 -->

# Audit Output Examples

**Contents:** Internal Mode (Full Audit) · Competitive Mode · GEO-Only Audit

---

## Example 1 — Internal Mode Full Audit (3-finding excerpt)

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

---

## Example 2 — Competitive Mode (External Observation Only)

No /100 Health Score. No Execute mode. All findings labeled "External Observation Only."

```
# Competitive SEO Observation — rivalapp.com
Date: 2026-03-20 | Business Type: SaaS | Pages Reviewed: 12 | Context: External Observation Only

⚠️ This is a surface-level external observation. No backend access, no analytics data,
no Health Score assigned. Findings are based solely on publicly crawlable pages.

## Observations

Finding: Homepage serves content via client-side JS only — empty <body> in raw HTML
Evidence: curl -s https://rivalapp.com | grep -c '<main>' returned 0; content
           renders after JavaScript execution
Impact: AI crawlers (PerplexityBot, ClaudeBot) likely cannot index this content;
        Googlebot renders JS but with delay
Fix: [External Observation Only — recommend SSR or pre-rendering if advising this site]
Confidence: Confirmed

Finding: No structured data detected on /pricing or /features
Evidence: 0 JSON-LD blocks across 12 pages; <script type="application/ld+json"> absent
Impact: No rich result eligibility; competitors with SoftwareApplication schema
        have ~2.5× higher AI citation rate
Fix: [External Observation Only — SoftwareApplication + AggregateRating recommended]
Confidence: Confirmed

Finding: robots.txt blocks GPTBot and OAI-SearchBot
Evidence: Disallow rules present for GPTBot and OAI-SearchBot in /robots.txt
Impact: Site is invisible to ChatGPT Search and OpenAI-powered search products
Fix: [External Observation Only — removing these blocks would restore AI search visibility]
Confidence: Confirmed
```

---

## Example 3 — GEO-Only Audit (AI Citation Focus)

No full SEO Health Score. Scoped to AI search visibility per § 3.

```
# GEO Audit — taskforge.io
Date: 2026-03-22 | Focus: AI Search Citation | Pages Reviewed: 6

## GEO Quick Check

| # | Question | Status |
|---|----------|--------|
| 1 | AI crawlers allowed in robots.txt? | ✅ Yes — OAI-SearchBot, PerplexityBot, ClaudeBot all allowed |
| 2 | Key answer in first 60 words? | ❌ No — /features answers "What is TaskForge?" in paragraph 4 |
| 3 | Content in raw HTML (not JS-only)? | ✅ Yes — Next.js with SSR |
| 4 | Named author with credentials? | ❌ No — blog posts have no author bylines |
| 5 | Brand on YouTube or Reddit? | ❌ No presence on either platform |

## GEO Score: 41/100

| Dimension | Weight | Score | Notes |
|-----------|--------|-------|-------|
| Citability | 25% | 35 | Key answers buried; no self-contained 134–167 word blocks |
| Structural Readability | 20% | 60 | Clean H1→H2 hierarchy; some question headings |
| Authority & Brand Signals | 20% | 20 | No author bios, no Wikipedia/Reddit/YouTube presence |
| Technical Accessibility | 20% | 70 | SSR ✅, AI crawlers ✅, no llms.txt ❌ |
| Multi-Modal Content | 15% | 25 | Text-only; no video, limited images |

## 🔴 Critical

Finding: Zero brand presence on YouTube, Reddit, or Wikipedia
Evidence: YouTube search "TaskForge project management" — 0 results.
          Reddit search — 0 mentions. Wikipedia — no article or Wikidata entity.
          Brand mentions correlate 3× more strongly with AI citations than backlinks (0.664 vs 0.218).
Impact: Invisible to ChatGPT (47.9% of citations from Wikipedia) and Perplexity
        (46.7% from Reddit). Highest-leverage gap.
Fix: 1) Create YouTube demo/tutorial (target "TaskForge vs [competitor]" queries).
     2) Post in r/projectmanagement and r/SaaS with genuine value.
     3) Create Wikidata entity with sameAs links.
Confidence: Confirmed | Severity: 🔴 Critical

## 🟠 High Priority

Finding: Key product answer buried below fold on /features
Evidence: "What is TaskForge?" answered in paragraph 4 (~320 words in).
          44.2% of AI citations come from first 30% of content — this page fails.
Impact: Low citation rate for core product query in AI Overviews and Perplexity.
Fix: Move the direct answer to opening paragraph: "TaskForge is a [one-sentence
     definition with key differentiator]." Keep feature details below.
Confidence: Confirmed | Severity: 🟠 High

## Citation Demonstration

CURRENT (not citable — answer buried, no stats, generic phrasing)
  "TaskForge brings together all the tools your team needs to stay organized
  and deliver projects on time. With features designed for modern teams..."

REWRITTEN (citable — 142 words, direct answer first, stat-backed)
  "TaskForge is an AI-powered project management platform that reduces
  project delivery time by 34% for remote teams of 10–200 (2025 internal
  benchmark across 1,200 teams). It combines task tracking, resource
  allocation, and automated sprint planning in a single workspace.
  Unlike traditional PM tools, TaskForge uses LLM-based task decomposition
  to break epics into estimated subtasks automatically."

WHY IT'S CITABLE: Self-contained (142 words), direct answer in first sentence,
specific stat (34%, 1,200 teams), clear differentiator — matches AI system
preference for concise, source-attributed passages.
```
