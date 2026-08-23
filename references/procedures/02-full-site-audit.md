> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

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
6. **Audit assumptions** — Before assembling recommendations, explicitly list the assumptions underpinning the audit (e.g., "homepage is representative of site quality", "low traffic pages = low value", "CMS renders server-side", "no recent algorithm penalty"). Surface these in the report's **Assumptions Audit** section so the user can reject or correct them. Revise any findings that depend on a shaky assumption.
7. **Prioritize findings** — Critical → High → Medium → Quick Wins. Apply the PERCEIVE → ANALYZE → VALIDATE → ACT framework (`references/thinking-framework.md`) to ensure each finding is grounded, falsifiable, and dependency-mapped.

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

### Thinking Framework

Before assembling recommendations, apply the **PERCEIVE → ANALYZE → VALIDATE → ACT** framework from `references/thinking-framework.md`. This ensures every finding traces to a first-principle observation, maps its dependencies, includes a falsifiability check, and names a leading indicator. For Critical and High findings, all four framework fields are required. For Medium findings, Falsifiability and Leading Indicator are sufficient.

### Finding Format

Every audit finding must use this structure:

```
Finding: [what the issue is]
Evidence: [what was observed / what data shows this]
Impact: [how this hurts rankings, traffic, or citations]
Fix: [specific, actionable step]
Confidence: Confirmed / Likely / Hypothesis
Falsifiability: [what evidence would prove this recommendation wrong or unnecessary]
Leading Indicator: [what metric to monitor post-fix, and over what timeframe]
```

For Critical and High findings, also include:
```
First-Principle Observation: [the raw observable fact that triggered this finding]
Dependency: [what other findings this blocks, enables, or depends on — use finding IDs]
```

**Confidence labels:**
- **Confirmed**: Direct evidence in fetched source/data
- **Likely**: Strong inference from partial data (2–3 signals)
- **Hypothesis**: Pattern-based assumption; limited page access

**Scoring formula:** `base_score = (positive_signals / (positive_signals + deficit_signals)) × 100`. Deduct by finding severity: **Critical −15, High −8, Medium −3, Low −1** (matches § 19 rule 3, which validates the score against this schedule).

### Audit Output Format

Use this exact template:

```
# SEO Audit Report — [site.com]
Date: [date] | Business Type: [type] | Audited Pages: [N] | Confidence: High/Medium/Low

## SEO Health Score: XX/100
[chain-of-thought: positive_signals=N, deficit_signals=N, base=XX, Critical −15×N, High −8×N, Medium −3×N, Low −1×N = final]

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
## Assumptions Audit
[List assumptions made during this audit and flag any that may not hold.
 e.g., "Homepage represents overall site quality", "Low traffic = low value page",
 "CMS is server-rendered". The user can reject or correct these.]

## Full Findings [per-category, each in Finding/Evidence/Impact/Fix/Confidence/Falsifiability/Leading Indicator format]
```

For a 3-finding excerpt showing the output format, see `references/audit-output-example.md`.

### Mode 2 Plan Entry Format

When converting audit findings into a roadmap (§ 16), use this format per item:

```
| Fix schema on all product pages | Dev | 2 hr | Star ratings in SERPs (+15–30% CTR) | Phase 1 | — | F3, F7 |
```
Columns: Action | Owner | Effort | Expected Outcome | Phase | Blocked By | Unblocks

#### Dependency-Graph Sequencing

Replace flat priority lists with a dependency-aware sequence. For every action item:

1. **Blocked By** — which other action(s) must complete first (use finding IDs or action IDs). Use `—` if none.
2. **Unblocks** — which downstream actions become possible after this one completes.
3. **Parallelizable** — actions with no mutual dependencies can run simultaneously; group them in the plan.

Present the plan as a **topologically sorted** sequence: items with no blockers first, then items whose blockers are satisfied, and so on. Within each level, sort by impact descending.

**Example dependency chain:**
```
A1: Fix canonical conflicts          | Blocked By: —   | Unblocks: A3, A5
A2: Add author bios to blog posts    | Blocked By: —   | Unblocks: A4
A3: Submit cleaned sitemap           | Blocked By: A1  | Unblocks: A6
A4: Add Person schema                | Blocked By: A2  | Unblocks: —
A5: Fix duplicate content            | Blocked By: A1  | Unblocks: A6
A6: Request re-indexation            | Blocked By: A3, A5 | Unblocks: —
```

Actions A1 and A2 can run in parallel (no shared blockers). A3 and A5 can run in parallel once A1 is done. A6 waits for both A3 and A5.

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
