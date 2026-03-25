# Ultimate SEO + GEO Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Claude Skill](https://img.shields.io/badge/Claude-Skill-blueviolet)](https://claude.ai)
[![Version](https://img.shields.io/badge/version-1.1.1-green.svg)](CHANGELOG.md)

The definitive SEO and Generative Engine Optimization skill for Claude. Runs full site audits with scored findings, generates ready-to-deploy fixes, and optimizes content for both Google Search and AI search engines (Google AI Overviews, AI Mode, ChatGPT Search, Perplexity).

**Author:** [Myk Pono](https://mykpono.com) · [Lab](https://lab.mykpono.com) · [LinkedIn](https://www.linkedin.com/in/mykolaponomarenko/)

---

## What It Does

Give it a URL and it returns a scored audit, prioritized action plan, and executable fixes — not vague advice.

**Three modes, one skill:**

| Mode | What It Does | Output |
|---|---|---|
| **Audit** | Fetches site, runs all checks, scores findings | SEO Health Score (0–100) + prioritized findings |
| **Plan** | Converts findings into phased roadmap | Implementation table with effort/impact/owner |
| **Execute** | Produces the actual fixes + verifies them | JSON-LD, meta rewrites, redirect maps, robots.txt |

Most requests run all three in sequence. Skip to Mode 2 if you already have audit findings; skip to Mode 3 if you know exactly what to fix.

---

## Coverage

### SEO (21 Modules)

- **Technical SEO** — Core Web Vitals (LCP/INP/CLS), crawlability, indexability, JavaScript rendering, security headers, mobile-first
- **On-Page SEO** — Title tags, meta descriptions, H1s, URLs, canonicals
- **Content & E-E-A-T** — Content quality scoring, author credentials, experience signals, readability, thin content detection, content pruning/refresh
- **Schema Markup** — All active Schema.org types, deprecation-aware (HowTo, SpecialAnnouncement removed), JSON-LD generation and validation
- **Keywords & Content Strategy** — Keyword research, topic clusters, content gaps, funnel mapping (TOFU/MOFU/BOFU)
- **Link Building** — Internal link audit, orphan page detection, anchor text analysis, external link quality hierarchy
- **Local SEO** — Google Business Profile, NAP consistency, review strategy, LocalBusiness schema, citation building
- **International SEO** — Hreflang audit, language code validation, bidirectional return tags
- **Programmatic SEO** — Quality gates for pages at scale, thin content safeguards, template optimization
- **Site Migrations** — Pre/during/post migration checklists, redirect map validation, Change of Address tool
- **Analytics & Reporting** — GA4/GSC setup, traffic drop diagnostics, CTR benchmarks, monthly maintenance

### GEO (AI Search Optimization)

- **Platform Coverage** — Google AI Overviews, Google AI Mode, ChatGPT Search, Perplexity, Bing Copilot
- **Citability Scoring** — Passage-level optimization (134–167 word answer blocks), answer placement in first 60 words
- **Brand Mention Strategy** — YouTube/Reddit/Wikipedia/LinkedIn correlation data, Wikidata entity setup
- **AI Crawler Management** — robots.txt configuration for GPTBot, OAI-SearchBot, PerplexityBot, ClaudeBot
- **llms.txt** — Template generation for the emerging AI content standard
- **RSL 1.0** — Machine-readable AI licensing (December 2025 standard)

---

## Installation

### Claude Code — Plugin Marketplace (recommended)

**Use [Claude Code](https://code.claude.com/)** (the terminal-based Claude product). The lines below are **slash commands** you type in the **Claude Code chat**, not in macOS Terminal or zsh. If you paste them into a shell, you will see `zsh: no such file or directory: /plugin` because `/plugin` is not a file on disk.

In Claude Code, run:

```text
/plugin marketplace add mykpono/ultimate-seo-geo
/plugin install ultimate-seo-geo@ultimate-seo-geo
```

Or install directly without adding the marketplace first:

```text
/plugin install https://github.com/mykpono/ultimate-seo-geo.git
```

### Claude Code — Manual skill install (global)

```bash
cp -r ultimate-seo-geo ~/.claude/skills/
```

### Claude Desktop / Cowork

Install the `.skill` file from the [Releases](https://github.com/mykpono/ultimate-seo-geo/releases) page.

### Manual (any agent)

Copy the folder into your skills directory:

```
~/.claude/skills/ultimate-seo-geo/
├── SKILL.md
├── references/    (18 .md files)
├── scripts/       (20 audit scripts + check-plugin-sync.py for CI)
└── evals/         (test cases)
```

---

## Usage Examples

**Full site audit:**
> "Audit mysite.com — we've seen a traffic drop over the past 3 months"

**Schema generation:**
> "Generate the complete schema markup for my SaaS product page at app.example.com"

**Local SEO:**
> "I run a plumbing company in Austin, TX. We're not showing up for 'plumber near me'. What's wrong?"

**GEO optimization:**
> "How do I get cited by ChatGPT and Perplexity for our core product keywords?"

**Site migration:**
> "We're moving from Magento to Shopify — 3,000 product pages. What do we need for SEO?"

---

## Architecture

```
ultimate-seo-geo/
├── SKILL.md              ← Core instructions (~1,070 lines)
│                           Mode routing, audit process, output templates
│
├── references/            ← Domain knowledge (18 .md files, load on demand)
│   ├── ai-search-geo.md     GEO signals, platform data, brand strategy
│   ├── technical-checklist.md  CWV fixes, JS SEO, IndexNow
│   ├── schema-types.md       All Schema.org types + templates
│   ├── eeat-framework.md     E-E-A-T scoring, spam categories
│   ├── core-eeat-framework.md  80-item CORE-EEAT content benchmark
│   ├── cite-domain-rating.md   40-item CITE domain authority
│   ├── entity-optimization.md  Entity / Knowledge Graph checklist
│   ├── content-eeat.md       Content quality, freshness, pruning
│   ├── site-migration.md     Pre/during/post migration checklists
│   ├── link-building.md      Backlink strategy, comparison pages
│   ├── local-seo.md          GBP, NAP, review strategy
│   ├── analytics-reporting.md  GA4/GSC, traffic diagnostics, myths
│   ├── keyword-strategy.md   Keyword research, intent mapping
│   ├── industry-templates.md  Per-industry architecture + schema
│   ├── international-seo.md  Hreflang, geo-targeting
│   ├── programmatic-seo.md   Pages at scale, quality gates
│   ├── crawl-indexation.md   Sitemaps, canonicals, crawl budget
│   └── image-seo.md          Alt text, WebP, responsive images
│
├── scripts/               ← 20 audit Python scripts (+ check-plugin-sync.py for CI)
│   ├── generate_report.py    Full-site HTML dashboard (runs all scripts)
│   ├── validate_schema.py    JSON-LD validation
│   ├── robots_checker.py     AI crawler access check
│   ├── pagespeed.py          Core Web Vitals via PageSpeed API
│   ├── hreflang_checker.py   All 8 hreflang rules
│   ├── internal_links.py     Link graph, orphan detection
│   ├── broken_links.py       4xx/5xx detection
│   ├── readability.py        Flesch-Kincaid scoring
│   ├── ...and 12 more
│
└── evals/                 ← Test cases
    └── evals.json            6 evals, 26 assertions (incl. negative test)
```

**Three-layer progressive disclosure:**
- **Layer 1** — Skill description (~100 words): always in context, triggers the skill
- **Layer 2** — SKILL.md (~1,070 lines): loaded when skill fires, contains all routing and instructions
- **Layer 3** — References + scripts (unlimited): loaded on demand per task

This means a simple schema request loads SKILL.md + `references/schema-types.md` — not the full 5,300+ lines of domain knowledge.

**Claude Code plugin install:** `bash setup-plugin.sh` mirrors `SKILL.md`, `references/`, `scripts/` (audit scripts only), and `evals/` into `plugins/.../skills/ultimate-seo-geo/` so `python scripts/...` paths work after marketplace install.

### Claude Code: why two `.claude-plugin/` folders?

Do **not** merge them into one directory. This repo follows the layout Claude Code expects for a **GitHub marketplace** plus an **installable plugin**:

| Location | File | Role |
|----------|------|------|
| **Repo root** | `.claude-plugin/marketplace.json` | **Marketplace catalog** — lists plugins, owner metadata, and each plugin’s `source` path (here: `./plugins/ultimate-seo-geo`). |
| **Under that path** | `plugins/ultimate-seo-geo/.claude-plugin/plugin.json` | **Plugin manifest** for the package at `source` — name, version, keywords, repository URL, etc. |

When someone runs `/plugin marketplace add mykpono/ultimate-seo-geo`, the tool reads the **root** catalog, then resolves **`source`** and loads **that folder’s** `plugin.json`. Putting both JSON files in a single `.claude-plugin/` would break that resolution. A repo that is **only** a plugin (no marketplace) can use a single plugin manifest at the root, but then you typically would **not** use the marketplace flow for that repo.

---

## Scripts

The **20 audit** Python scripts (excluding maintainer-only `check-plugin-sync.py`) require Python 3.8+ and install dependencies with:

```bash
pip install requests beautifulsoup4 --break-system-packages -q
```

Run the full-site report to start any audit:

```bash
python scripts/generate_report.py https://example.com --output seo-report.html
```

| Script | Purpose |
|---|---|
| `generate_report.py` | Full-site HTML dashboard — bundled analysis pipeline |
| `validate_schema.py` | Validates JSON-LD blocks (pure stdlib) |
| `robots_checker.py` | robots.txt rules + AI crawler allow/block status |
| `pagespeed.py` | Core Web Vitals via PageSpeed Insights API |
| `hreflang_checker.py` | All 8 hreflang rules + bidirectional return tags |
| `internal_links.py` | Link graph, orphan pages, anchor text, crawl depth |
| `broken_links.py` | 4xx/5xx broken links + redirect counts |
| `redirect_checker.py` | Full redirect chain analysis — loops and mixed HTTP/HTTPS |
| `security_headers.py` | HSTS, CSP, X-Frame-Options — weighted score |
| `entity_checker.py` | Wikidata, Wikipedia, sameAs entity signals |
| `llms_txt_checker.py` | llms.txt presence + format validation |
| `indexnow_checker.py` | IndexNow key file validation + ping |
| `social_meta.py` | Open Graph + Twitter Card validation |
| `readability.py` | Flesch-Kincaid grade + sentence stats |
| `duplicate_content.py` | Near-duplicate detection |
| `article_seo.py` | CMS-aware article structure + keyword analysis |
| `link_profile.py` | Link equity distribution |
| `finding_verifier.py` | Deduplicates findings across a full audit |
| `fetch_page.py` | Fetch and save raw HTML (utility) |
| `parse_html.py` | Extract titles, H1s, meta, canonical, schema (utility) |

---

## Eval Results

Benchmarked against baseline (no skill) across 3 test scenarios:

| Metric | With Skill | Without Skill | Delta |
|---|---|---|---|
| Pass rate | **100%** | 87% | **+13 pts** |
| Avg time | 103s | 54s | +49s |
| Avg tokens | 83K | 64K | +19K |

The skill adds ~50 seconds and ~19K tokens per task, but achieves 100% on structured output requirements (finding format, correct schema types, health scoring) where the baseline misses.

**Test scenarios:** health publisher full audit (YMYL), local HVAC schema + audit, SaaS schema generation, site migration guidance, general recipe blog advice, negative test (Google Ads — should NOT trigger).

---

## What It Doesn't Do

This skill focuses on organic search and AI search visibility. It does not cover:

- PPC / Google Ads / paid advertising
- Social media management or posting
- General marketing strategy
- Web design or UX (beyond SEO-relevant elements)
- Content writing (it generates briefs and meta tags, not full articles)

---

## Credits

Built on research, patterns, and prior work from:

- **[Bhanunamikaze/Agentic-SEO-Skill](https://github.com/Bhanunamikaze/Agentic-SEO-Skill)** — SEO analysis toolkit architecture, specialist agent patterns, technical SEO audit framework
- **[AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo)** — GEO platform citation data, DataForSEO integration patterns, AI crawler detection tables, subagent delegation architecture

---

## Maintainers

Releases, version alignment, and syncing the plugin skill tree: [RELEASE.md](RELEASE.md).

---

## License

[MIT](LICENSE) — use it, modify it, ship it.
