---
name: ultimate-seo-geo
description: Audits and optimizes websites for search engine visibility (SEO) and AI search citation (GEO, also called AEO or answer engine optimization), covering technical health, E-E-A-T content scoring, domain authority, structured data, rich results, and entity signals. Use when running SEO audits, diagnosing traffic drops or ranking losses, generating Schema.org JSON-LD, checking Core Web Vitals, crawlability, robots.txt, sitemaps, hreflang, backlinks, planning content strategy or site migrations, fixing indexing issues, or optimizing for AI search: AI Overviews, AI Mode, ChatGPT, and Perplexity. NOT for paid ads (PPC/SEM), social media strategy, email marketing, or general web development unrelated to search.
version: 1.23.0
---

# Ultimate SEO + GEO — LLM-Agnostic SEO Agent

| Attribute | Details |
| --- | --- |
| **Version** | 1.23.0 |
| **Updated** | 2026-11-25 |
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

**This file is the routing shell.** Procedures for §1–§26 live under `references/procedures/` and domain tables under `references/*.md`; read only what the task needs (see Routing below).

## 0. Before You Start

### Routing (read only what you need)

Read **one** procedure file and at most **two** topical `references/*.md` files per task. Loading more adds tokens and latency with no quality gain ([Skills progressive disclosure](https://github.com/anthropics/claude-cookbooks/tree/main/skills)). A full audit reads only `02-full-site-audit.md`: it is the complete Mode 1 playbook.

| Goal | Read | Run |
|------|------|-----|
| Quick look ("how does my site look?", first call, no time for a crawl) | — | `generate_report.py URL --quick`: prints a digest of the homepage checks. Its number is **not** a Health Score; offer the full audit |
| Full scored audit | `procedures/02-full-site-audit.md` | `generate_report.py --json summary.json --digest digest.md`, then read `digest.md` |
| AI citations / GEO | `procedures/03-geo-ai-search.md`, `ai-search-geo.md` | `robots_checker.py`, `entity_checker.py`, `citability_checker.py`, `llms_txt_checker.py` |
| Content, E-E-A-T, AI-drafted text | `procedures/06-content-eeat-and-pruning.md`, `eeat-framework.md` or `ai-generated-content-artifacts.md` | `article_seo.py`, `readability.py`, `content_quality.py` |
| Schema | `procedures/05-schema-structured-data.md`, `schema-types.md` | `validate_schema.py` |
| Technical / CWV | `procedures/04-technical-seo.md`, `technical-checklist.md` | `pagespeed.py`, `robots_checker.py`, `security_headers.py` |
| Crawl / indexation | `procedures/11-crawl-indexation.md`, `crawl-indexation.md` | `sitemap_checker.py`, `index_coverage_diff.py`, `canonical_checker.py`, `duplicate_content.py` |
| Site structure, page types, navigation | `procedures/26-site-structure-content-types.md`, `page-types.md` | `site_graph.py`, `page_type_classifier.py`, `navigation_checker.py`, `site_architecture.py` |
| Keywords, clusters, briefs (no URL yet) | `procedures/07-keywords-clusters-aeo.md` or `23-semantic-clustering.md` | `content_brief.py`, `topic_cluster.py`; never invent a `/100` score |
| Strategy / roadmap | `procedures/16-strategy-roadmap.md` | — |
| Links / authority | `procedures/09-link-building-internal.md`, `link-building.md` or `cite-domain-rating.md` | `internal_links.py`, `broken_links.py`, `link_profile.py` |
| Local and maps | `procedures/12-local-seo.md` or `25-maps-intelligence.md`, `local-seo.md` | `local_signals_checker.py`, `maps_checker.py` |
| E-commerce | `procedures/24-ecommerce-seo.md` | `ecommerce_schema.py`, `validate_schema.py` |
| Images · international · programmatic | `procedures/13-…`, `14-…`, `15-…` with `image-seo.md`, `international-seo.md`, `programmatic-seo.md` | `image_checker.py`, `hreflang_checker.py`, `programmatic_seo_auditor.py` |
| Migration | `procedures/20-site-migration.md`, `site-migration.md` | `redirect_checker.py` |
| Traffic drop, analytics, GSC / GA4 | `procedures/10-analytics-reporting.md`, `analytics-reporting.md` | `gsc_insights.py`, `ga4_report.py`, `google_api_tier.py` |
| Drift / change tracking | `procedures/22-drift-monitoring.md` | `drift_monitor.py`, or `generate_report.py --previous` |
| Client report (`report.html`) | `report-template/report-template.md` | `render_report.py`, `report_data_lint.py` |
| Running one script by hand | `procedures/21-script-toolbox.md` or `audit-script-matrix.md` | `brief.py SCRIPT.py ARGS`; the script's `--help` |

Paths are under `references/`. Every topic's section number (§1–§26) and request phrasing: `references/procedures/01-request-detection-routing.md`.

### When *not* to run Mode 1 (full audit)

| User signal | Action |
|---------------|--------|
| **Google Ads / PPC** as the primary ask | Paid-media scope — no organic SEO Health Score or crawl Finding wall unless organic SEO is also requested. |
| Employer branding only, **pure** press/PR distribution, **email-only** marketing | Narrow guidance; no implied full technical + content audit. |
| **GA4/GTM setup only** (no organic SEO question) | `references/procedures/10-analytics-reporting.md` — **no** fabricated domain-wide numeric score. |
| **Social** community management only | Out of scope unless tied to organic discovery (e.g. `sameAs`, entity signals). |
| **Explicitly scoped** task (e.g. “only robots.txt + sitemap”) | Stay in that scope — no domain-wide E-E-A-T essay or `/100` score unless the user asks. |

### Audit Context: Internal vs. Competitive Mode

Before routing, determine which audit context applies. This controls what outputs are valid.

| Signal | Context | What's Allowed |
|---|---|---|
| User says "my site", "our site", "I own", provides GSC/GA4 access, or confirms backend access | **Internal Mode** | Full scored audit, every script eligible, Execute mode available, /100 Health Score valid |
| External URL the user does not own (competitor, prospect, reference site) | **Competitive Mode** | Surface crawl only (homepage + up to 20 pages), no /100 Health Score, Execute mode disabled, all output labeled **"External Observation Only"** |

**When in doubt, ask:** "Is this your site, or are you analyzing a competitor?"

This skill operates in three modes. Identify which mode applies before touching anything else.

### The Three Modes

**Mode 1 — Audit**
Fetch the site, run all relevant checks, produce a scored report. Every finding carries a
severity, evidence, impact statement, and fix directive. Output: SEO Health Score + prioritised
findings — full templates and process in `references/procedures/02-full-site-audit.md`.

**Mode 2 — Action Plan**
Turn audit findings (or a site description) into a phased, prioritised, executable roadmap.
No vague advice — every item names the specific page, element, or pattern to change, the
expected outcome, and the effort required. Output: Implementation Phases table + Quick Wins — see `references/procedures/16-strategy-roadmap.md` and Mode 2 format in `references/procedures/02-full-site-audit.md`.

**Mode 3 — Execute**
Do the work. Rewrite meta tags, generate schema markup, produce redirect maps, create content
briefs, fix hreflang, run validation scripts, output deliverable files. Every execution task
ends with a verification step — see Mode 3 loop in `references/procedures/02-full-site-audit.md`.
After a `generate_report.py` run, work the summary's `action_plan` in lane order: `Auto` first
(safe, no sign-off), then `Assisted` (High-Risk gate applies), and hand `Human` / `Decision` items
and `open_questions` back to the user. Open questions are missing data, never findings.

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

### Mode order

Most requests run **Audit → Plan → Execute**. Skip to Mode 2 if audit findings already exist; skip to Mode 3 when the user names a specific fix. A traffic drop starts with `procedures/10-analytics-reporting.md`; an AI-citation question with `procedures/03-geo-ai-search.md`; a URL with "audit and fix everything" runs Modes 1, 2 and 3 in turn.

### What "Done" Looks Like per Mode

**Audit complete** when: SEO Health Score delivered (or "not scored" with the reason), all Critical and High findings documented in
Finding/Evidence/Impact/Fix/Confidence/Falsifiability/Leading Indicator format (with First-Principle Observation and Dependency for Critical/High), Assumptions Audit section present, no section skipped without reason stated.

**Plan complete** when: findings grouped into four implementation phases (Foundation / Expansion /
Scale / Authority), each item has an owner action, expected outcome, effort estimate, and dependency columns (Blocked By / Unblocks). Plan is topologically sorted by dependencies.

**Execute complete** when: every fix implemented AND verified — run the relevant validation script,
review the output, confirm it resolves the original finding.

### Context budget

1. **Read the digest, not the JSON.** `generate_report.py --digest digest.md` writes a 3–6 KB summary of a 30–50 KB `summary.json`. Open the JSON only for one finding's detail, by ID.
2. **Scope narrow tasks.** Schema, robots.txt or llms.txt questions run one script; never a full crawl.
3. **Run a single script through `brief.py`**: `python scripts/brief.py internal_links.py https://example.com --json` prints a short view (lists cut to 8 items, each cut counted) and saves the full output to a file. Use it for any script whose output you have not seen; `site_graph.py --json` alone can print megabytes.
4. **Prefer partial delivery over a timeout.** Deliver the score and the findings you have, and list what was skipped and why.
5. **A site that rate-limits** (digest line `⚠ THROTTLED`, HTTP 429): the listed checks were discarded. Wait 1–2 minutes and re-run with `--polite`.
6. **If context fills mid-audit**, compress finished sections into bullets and continue (`procedures/21-script-toolbox.md`, Context Management).

---

## Global guardrails (always apply)

These rules apply to every mode. **Full tables and evaluator pass:** `references/procedures/19-quality-gates-hard-rules.md`.

### Evidence integrity (do not claim without data)

| Claim | Only state if |
|---|---|
| LCP / INP / CLS / performance score | `pagespeed.py` ran successfully, or user pasted PageSpeed Insights / CrUX output |
| Backlink count or referring domains | `link_profile.py` ran and returned data |
| Organic traffic or impression numbers | GSC / GA4 access confirmed and data retrieved |
| Health Score /100 | Internal Mode + `generate_report.py` measured at least 5 weighted checks; report its `overall` unchanged, else "not scored" |
| Schema errors or validation status | `validate_schema.py` ran against the page |
| Schema "not found" on a CMS site | Confirmed via Rich Results Test or browser JS — raw HTML cannot detect JS-injected schema |

**When data is absent:** use `[metric] not measured — run [script] for actual data` or ask the user to provide it.

### Finding format (mandatory)

Every finding: **Finding** / **Evidence** / **Impact** / **Fix** / **Confidence** (Confirmed / Likely / Hypothesis) / **Falsifiability** (what would prove this wrong) / **Leading Indicator** (what to monitor post-fix). Critical and High findings also require **First-Principle Observation** and **Dependency**. Apply the PERCEIVE → ANALYZE → VALIDATE → ACT framework from `references/thinking-framework.md`. Example report excerpt: `references/audit-output-example.md`.

### High-Risk execute gate

**High-Risk** changes (robots.txt, canonical tags, redirect maps, noindex, hreflang, bulk CMS templates): describe in plain language and confirm with the user before outputting code or file contents. **Safe** changes (meta, alt text, most schema, content rewrites, llms.txt): may output directly. Full classification table: `references/procedures/02-full-site-audit.md` (Mode 3).

### Before delivering any Mode 1 audit

Run `python scripts/report_lint.py report.md --summary summary.json` when a shell is available, then the judgment checks at the end of `references/procedures/02-full-site-audit.md` (full wording in `references/procedures/19-quality-gates-hard-rules.md`).

---

## Procedure files (§1–§26)

`references/procedures/01-request-detection-routing.md` · `references/procedures/02-full-site-audit.md` · `references/procedures/03-geo-ai-search.md` · `references/procedures/04-technical-seo.md` · `references/procedures/05-schema-structured-data.md` · `references/procedures/06-content-eeat-and-pruning.md` · `references/procedures/07-keywords-clusters-aeo.md` · `references/procedures/08-competitor-analysis.md` · `references/procedures/09-link-building-internal.md` · `references/procedures/10-analytics-reporting.md` · `references/procedures/11-crawl-indexation.md` · `references/procedures/12-local-seo.md` · `references/procedures/13-image-seo.md` · `references/procedures/14-international-hreflang.md` · `references/procedures/15-programmatic-seo.md` · `references/procedures/16-strategy-roadmap.md` · `references/procedures/17-monthly-maintenance.md` · `references/procedures/18-myths.md` · `references/procedures/19-quality-gates-hard-rules.md` · `references/procedures/20-site-migration.md` · `references/procedures/21-script-toolbox.md` · `references/procedures/22-drift-monitoring.md` · `references/procedures/23-semantic-clustering.md` · `references/procedures/24-ecommerce-seo.md` · `references/procedures/25-maps-intelligence.md` · `references/procedures/26-site-structure-content-types.md`

Index with one line per section: [`references/procedures/README.md`](references/procedures/README.md)
