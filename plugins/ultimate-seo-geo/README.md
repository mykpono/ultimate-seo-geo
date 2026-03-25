# Ultimate SEO + GEO — Claude Code Plugin

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](../../LICENSE)
[![Claude Skill](https://img.shields.io/badge/Claude-Skill-blueviolet)](https://claude.ai)
[![Version](https://img.shields.io/badge/version-1.1.2-green.svg)](../../CHANGELOG.md)

> The definitive SEO + GEO skill for Claude. Full site audits, AI search optimization, schema generation, E-E-A-T assessment, and 20 diagnostic scripts.

**Author:** [Myk Pono](https://mykpono.com) · [Lab](https://lab.mykpono.com) · [GitHub](https://github.com/mykpono/ultimate-seo-geo)

---

## Install via Claude Code

These are **slash commands** for **Claude Code**’s chat input—not for Terminal/zsh. Pasting `/plugin …` into a shell causes `no such file or directory: /plugin`.

**Add the marketplace (one-time):**

```text
/plugin marketplace add mykpono/ultimate-seo-geo
```

**Install the plugin:**

```text
/plugin install ultimate-seo-geo@ultimate-seo-geo
```

**Or install directly without a marketplace:**

```text
/plugin install https://github.com/mykpono/ultimate-seo-geo.git
```

---

## What It Does

Give it a URL and it returns a scored audit, prioritized action plan, and executable fixes — not vague advice.

| Mode | What It Does | Output |
|------|-------------|--------|
| **Audit** | Fetches site, runs all checks, scores findings | SEO Health Score (0–100) + prioritized findings |
| **Plan** | Converts findings into phased roadmap | Implementation table with effort/impact/owner |
| **Execute** | Produces the actual fixes + verifies them | JSON-LD, meta rewrites, redirect maps, robots.txt |

Most requests run all three in sequence automatically.

The bundled skill folder includes **`scripts/`** (audit tools) and **`evals/`** so instructions like `python scripts/generate_report.py …` work after a Claude Code plugin install—not only on a full repo checkout.

---

## Usage Examples

```
Audit mysite.com — we've seen a traffic drop over the past 3 months
```
```
Generate the complete schema markup for my SaaS product page at app.example.com
```
```
I run a plumbing company in Austin, TX. We're not showing up for 'plumber near me'. What's wrong?
```
```
How do I get cited by ChatGPT and Perplexity for our core product keywords?
```
```
We're moving from Magento to Shopify — 3,000 product pages. What do we need for SEO?
```

---

## Coverage

### SEO (21 Modules)
- **Technical SEO** — Core Web Vitals (LCP/INP/CLS), crawlability, indexability, JS rendering, security headers, mobile-first
- **On-Page SEO** — Title tags, meta descriptions, H1s, URLs, canonicals
- **Content & E-E-A-T** — Content quality scoring, author credentials, experience signals, readability, thin content detection
- **Schema Markup** — All active Schema.org types, deprecation-aware, JSON-LD generation and validation
- **Keywords & Content Strategy** — Keyword research, topic clusters, content gaps, funnel mapping
- **Link Building** — Internal link audit, orphan page detection, anchor text analysis
- **Local SEO** — Google Business Profile, NAP consistency, review strategy, LocalBusiness schema
- **International SEO** — Hreflang audit, language code validation, bidirectional return tags
- **Programmatic SEO** — Quality gates for pages at scale, thin content safeguards
- **Site Migrations** — Pre/during/post migration checklists, redirect map validation
- **Analytics & Reporting** — GA4/GSC setup, traffic drop diagnostics, CTR benchmarks

### GEO (AI Search Optimization)
- **Platform Coverage** — Google AI Overviews, AI Mode, ChatGPT Search, Perplexity, Bing Copilot
- **Citability Scoring** — Passage-level optimization, answer placement optimization
- **Brand Mention Strategy** — YouTube/Reddit/Wikipedia/LinkedIn correlation data, Wikidata entity setup
- **AI Crawler Management** — robots.txt for GPTBot, OAI-SearchBot, PerplexityBot, ClaudeBot
- **llms.txt** — Template generation for the emerging AI content standard
- **RSL 1.0** — Machine-readable AI licensing (December 2025 standard)

### 23 Python audit scripts
Includes `sitemap_checker.py`, `local_signals_checker.py`, `image_checker.py`, full `generate_report.py` pipeline, and the rest — see **`references/audit-script-matrix.md`** in the skill tree for the step ↔ script map.

---

## Scope

This skill covers **organic search and AI search visibility only**. It does not cover PPC / Google Ads, social media management, general marketing strategy, or content writing.

---

## License

[MIT](../../LICENSE) — use it, modify it, ship it.
