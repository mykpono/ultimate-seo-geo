> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

## 2. Full Site Audit

**This file is the whole Mode 1 playbook.** A standard audit needs no other procedure or reference file: the finding fields, the score rules, the report template and the pre-delivery checks are all below. Open `references/procedures/21-script-toolbox.md` or `references/audit-script-matrix.md` only to run one script on its own, `references/procedures/19-quality-gates-hard-rules.md` only for a rule's full wording, and `references/industry-templates.md` only when the business type changes what to prioritise.

### Process

**In a bash-capable environment**: Run `python scripts/generate_report.py https://example.com --output report.html --json summary.json --digest digest.md` first. **Read `digest.md`, not `summary.json`**: it carries the score, group scores, every non-info finding (ID, severity, lane, fix), the action plan and the open questions in about a tenth of the tokens. Open `summary.json` only to copy one finding's `evidence`, `impact` or `falsifiability` fields by its ID; it stays the score source that `report_lint.py` checks. The run covers the **bundled analysis pipeline** in `generate_report.py` (robots, security, social, redirects, llms.txt, links, PageSpeed, entities, hreflang, duplicates, sitemap discovery, local signals, IndexNow probe, on-page parse, readability, article SEO, JSON-LD validation, image alt coverage, and — from one shared 80-page crawl — page-type coverage, navigation and site architecture, shown but not weighted; § 26). Then use `finding_verifier.py` to deduplicate at the end. For any single dimension, run the matching script from **`references/audit-script-matrix.md`** or **§21**.

**Evidence Integrity** — the table in `SKILL.md` (Global guardrails) applies in full. Two more rows for audits: a **thin content** finding needs `readability.py` and `duplicate_content.py` both to have run, and **schema "not found" on a CMS site** needs the Rich Results Test or a browser check, because Yoast, RankMath and AIOSEO inject JSON-LD with client-side JS that raw HTML cannot show.

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
4. **Score** — the SEO Health Score is `overall` from the `generate_report.py --json` summary, reported unchanged; category rows come from its `group_scores` (see Health Score below). Never compute a score by hand.
5. **Assign confidence level**: High (8+ pages fetched + analytics access) / Medium (4–7 pages, no analytics) / Low (1–3 pages).
6. **Audit assumptions** — Before assembling recommendations, explicitly list the assumptions underpinning the audit (e.g., "homepage is representative of site quality", "low traffic pages = low value", "CMS renders server-side", "no recent algorithm penalty"). Surface these in the report's **Assumptions Audit** section so the user can reject or correct them. Revise any findings that depend on a shaky assumption.
7. **Prioritize findings** — Critical → High → Medium → Low (see Severity Scale), then tag quick wins. Apply the PERCEIVE → ANALYZE → VALIDATE → ACT framework (`references/thinking-framework.md`) to ensure each finding is grounded, falsifiable, and dependency-mapped.

### SEO Health Score Weights

There is one Health Score: the one `generate_report.py` computes. It is the weighted mean of its check scores; each check belongs to one category. The table is each category's share when every check is measured:

| Category | Weight | Checks |
|---|---|---|
| Technical SEO | 32% | security, robots, broken_links, canonical, hreflang, redirects, sitemap, indexnow_probe (robots scores crawl rules only: a readable file, a declared sitemap, Googlebot and Bingbot not blocked) |
| Content quality / E-E-A-T | 18% | readability, content_quality, duplicate_content, programmatic_seo |
| On-page SEO | 11% | onpage, social |
| Link authority | 11% | internal_links, link_profile |
| Core Web Vitals | 10% | pagespeed |
| AI search readiness (GEO) | 10% | ai_search_access, entity (ai_search_access is the share of AI search crawlers robots.txt lets fetch the site; llms.txt, AI crawler firewall, hidden-instruction and citability checks are shown but not weighted) |
| Schema / structured data | 4% | schema_validation |
| Images | 2% | image_seo |
| Local SEO | 2% | local_signals (only for local businesses) |

A check that errors, is rate-limited, or does not apply drops out, and the other categories' shares grow. Report the actual shares from `group_scores[].share`, not this table. The weights live in `CHECK_WEIGHTS` in `scripts/generate_report.py`; `tests/test_health_score_contract.py` fails if this table drifts from them.

For the on-page element checklist (title tags, meta descriptions, H1, URLs, canonicals), see `references/technical-checklist.md`.

**First check for any new site:** `site:yourdomain.com` in Google. Zero results = indexation problem → go to § 4 immediately.

### Thinking Framework

Apply **PERCEIVE → ANALYZE → VALIDATE → ACT**: observe the raw signal before concluding, trace each finding to that observation, map what it blocks or depends on, state what would prove it wrong, and name the metric to watch after the fix. The fields this produces are in the Finding Format below: all four for Critical and High findings, Falsifiability and Leading Indicator for Medium. `references/thinking-framework.md` has a worked example; it is not needed to run an audit.

### Severity Scale

One scale for every report, strongest first. It is the `severity_scale` of the `generate_report.py --json` summary (§ 21), so script findings and your own use the same words.

| Severity | Meaning | Section |
|---|---|---|
| Critical | Blocks indexing, ranking or citation now | 🔴 Critical Issues (fix immediately) |
| High | Measurable loss; fix this week | 🟠 High Priority |
| Medium | Real but contained; fix this month | 🟡 Medium Priority |
| Low | Minor polish | 🔵 Low Priority |
| Info | Context, no action required | Full Findings only |

When `generate_report.py` ran, take each script finding's severity from its summary `severity` field; do not re-grade it. Scripts that still say "warning" are reported as Medium.

**Quick win** and **opportunity** are tags, not severities: a finding keeps its severity and is also listed under ⚡ Quick Wins (under 2 hours of work) or 💡 Opportunity Signals. In JSON, use `"tags": ["quick_win"]` or `["opportunity"]`.

### Finding Format

Every audit finding must use this structure. The field names match the summary JSON (`evidence`, `impact`, `confidence`, `falsifiability`, `leading_indicator`, `dependency`), so findings from scripts, subagents and your own analysis merge through `finding_verifier.py`.

```
Finding: [what the issue is]
Evidence: [what was observed / what data shows this]
Impact: [how this hurts rankings, traffic, or citations]
Fix: [specific, actionable step]
Confidence: Confirmed / Likely / Hypothesis | Severity: Critical / High / Medium / Low / Info
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

### Health Score

- **Scored:** `generate_report.py` ran and measured at least 5 weighted checks (`measured_categories` ≥ 5). Report `overall` as the score, list what was not measured, and fill the category table from `group_scores` (score, share, status). Do not adjust the number for findings: the checks already scored them.
- **Not scored:** it did not run (no shell, network blocked, parallel workers only), or measured fewer than 5 weighted checks. Write `SEO Health Score: not scored`, give the reason, and fill the category table with status only (Strong / Needs work / Gap / Not measured), each backed by findings. Never estimate a number.

### Audit Output Format

Use this exact template:

```
# SEO Audit Report — [site.com]
Date: [date] | Business Type: [type] | Audited Pages: [N] | Confidence: High/Medium/Low

## SEO Health Score: XX/100
Source: generate_report.py — N weighted checks measured; not measured: [checks, or "none"]

| Category | Score | Share | Status |
|---|---|---|---|
| Technical SEO | XX/100 | XX% | Strong / Needs work / Gap / Not measured |
...

[When not scored, replace the two lines above with:
 ## SEO Health Score: not scored
 Reason: [generate_report.py did not run / only N weighted checks measured]
 and drop the Score and Share columns.]

## Executive Summary
[2–3 sentences: biggest strength, biggest gap]
Next action: [ONE change — what, on which page or template, and the finding it closes. Not a list.]

## 🔴 Critical Issues (fix immediately)
## 🟠 High Priority (fix this week)
## 🟡 Medium Priority (fix this month)
## 🔵 Low Priority
## ⚡ Quick Wins (findings tagged quick_win, any severity)
## 💡 Opportunity Signals (findings tagged opportunity)
## Assumptions Audit
[List assumptions made during this audit and flag any that may not hold.
 e.g., "Homepage represents overall site quality", "Low traffic = low value page",
 "CMS is server-rendered". The user can reject or correct these.]

## Full Findings [per-category, each in Finding/Evidence/Impact/Fix/Confidence/Falsifiability/Leading Indicator format]
```

For a 3-finding excerpt showing the output format, see `references/audit-output-example.md`.

**Client report.** When the audit is delivered to a company rather than answered in chat, the Markdown report above is the written form; the deliverable is one `report.html` (summary, audit, strategy, plan and a folded appendix) rendered by `scripts/render_report.py` from a report source that extends the `generate_report.py --json` summary with findings, recommendations, coverage, prompts and page cards. Contract, fields and the coverage / automation-lane rules: `references/report-template/report-template.md`; lint the source with `scripts/report_data_lint.py`.

**Lint before delivering.** Save the report and run `python scripts/report_lint.py report.md --summary summary.json` (drop `--summary` when `generate_report.py` did not run). It checks the title and metadata, the Health Score against the summary, the required sections, every finding's fields, severity and section, the single `Next action:` line, and that no Core Web Vitals or backlink numbers appear for checks that never ran. It warns about click, impression, session and CTR figures when no Search Console data reached the summary, and about forecasts ("+20% traffic") with no basis on the line. **A number the data cannot support is written as `cannot compute from this data`, with what would supply it** — never estimated. Fix every error; each warning names what it could not verify.

### Before delivering: judgment checks

`report_lint.py` checks the score, the required sections, each finding's fields and unsupported numbers. It cannot judge these; check each, and revise before delivering (full wording: `references/procedures/19-quality-gates-hard-rules.md`):

1. Every Critical and High finding has Evidence from script output or an observed page; otherwise downgrade it to Medium.
2. No duplicates: run `finding_verifier.py` when findings came from more than one source.
3. Scope: a scored audit only for a site the user owns; a competitor's site is labelled "External Observation Only" and not scored.
4. Every fix names the page, element, file or template to change.
5. No authority-claiming YMYL schema (MedicalWebPage, LegalService, FinancialProduct and similar) without verified credentials.
6. No 10+ page changes with no ranking effect (removing `keywords` meta, cosmetic HTML).
7. Never recommend removing valid schema, FAQPage markup or FAQ content because a rich result was retired; prune only on quality grounds.
8. No tactic whose stated purpose is to manipulate AI answers (placed citations, seeded listicles, coordinated posts), and no text aimed at AI that visitors cannot see.
9. High-Risk deliverables (robots.txt, redirects, noindex, canonicals, hreflang) are described, not output, until the user confirms.
10. The Assumptions Audit section names what the audit relies on.

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

**Working from a `generate_report.py` run:** the summary JSON already carries this classification. `action_plan.Auto` is the Safe lane in working order — do these first, without asking. `action_plan.Assisted` items are High-Risk: confirm each one as below. `Human` and `Decision` items go back to the user with the `lane_reason`. `open_questions` are not defects: close them (re-run the named check, set the named key) before trusting the part of the audit they cover, and never present one as a finding. After fixing, re-run with `--previous <that summary>` and report `previous.resolved` as what cleared; a finding under `previous.not_rechecked` is unverified, not fixed — re-run its check before claiming it.

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
Addressing: Organization schema on / has no sameAs links (entity not tied to its profiles)
Fix: [Organization JSON-LD below, sameAs → LinkedIn, Wikidata, Crunchbase]
Verify: python scripts/validate_schema.py home.html → 0 errors
Confirmed: Organization valid with 3 sameAs URLs, each resolving to the brand's own profile.
```

---
