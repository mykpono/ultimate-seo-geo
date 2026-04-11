# Ultimate SEO + GEO — Claude Code Plugin

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](../../LICENSE)
[![Claude Skill](https://img.shields.io/badge/Claude-Skill-blueviolet)](https://claude.ai)
[![Version](https://img.shields.io/badge/version-1.8.5-green.svg)](../../CHANGELOG.md)

> The definitive SEO + GEO skill for Claude. Full site audits, AI search optimization, schema generation, E-E-A-T assessment, and **31** bundled diagnostic Python scripts.

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

### Still seeing an old version (e.g. 1.8.2)?

GitHub **main** and release **v1.8.5** already declare `"version": "1.8.5"` in `plugins/ultimate-seo-geo/.claude-plugin/plugin.json`. If the UI shows something older, the marketplace **git clone under your home directory is stale** (it does not auto-pull), or the Claude.ai web cache needs a refresh.

**Check what is on disk (run in Terminal, not inside Claude chat):**

```bash
grep '"version"' ~/.claude/plugins/marketplaces/ultimate-seo-geo/plugins/ultimate-seo-geo/.claude-plugin/plugin.json
```

**Pull latest `main` into that clone:**

```bash
cd ~/.claude/plugins/marketplaces/ultimate-seo-geo && git fetch origin && git reset --hard origin/main
```

**Then in Claude Code (slash commands in chat):**

```text
/plugin marketplace add mykpono/ultimate-seo-geo
/plugin install ultimate-seo-geo@ultimate-seo-geo
```

Restart Claude Code after that. **Nuclear option** if the version line is still wrong: `rm -rf ~/.claude/plugins/marketplaces/ultimate-seo-geo` and run `/plugin marketplace add mykpono/ultimate-seo-geo` again (re-clones from GitHub).

**Claude.ai (web):** Customize → remove the plugin → Marketplace → add **ultimate-seo-geo** again → new chat.

---

## What It Does

Give it a URL and it returns a scored audit, prioritized action plan, and executable fixes — not vague advice.

| Mode | What It Does | Output |
|------|-------------|--------|
| **Audit** | Fetches site, runs all checks, scores findings | SEO Health Score (0–100) + prioritized findings |
| **Plan** | Converts findings into phased roadmap | Implementation table with effort/impact/owner |
| **Execute** | Produces the actual fixes + verifies them | JSON-LD, meta rewrites, redirect maps, robots.txt |

Most requests run all three in sequence automatically.

The bundled skill folder includes **`scripts/`** (audit tools), **`references/`**, **`agents/`** (parallel audit worker scopes), and **`evals/`** so instructions like `python scripts/generate_report.py …` work after a Claude Code plugin install—not only on a full repo checkout.

- **Parallel audits:** `agents/PARALLEL-AUDIT.md` defines independent script groups for Task/subagent tools; merge with `finding_verifier.py` (see `agents/README.md`).
- **Optional MCP:** Firecrawl and DataForSEO — **`references/optional-extensions-mcp.md`** (install from a full repo clone or GitHub paths).
- **Reports:** `generate_report.py` writes **HTML** (default), **XLSX** with `openpyxl`, **PDF** with optional **WeasyPrint**, or **HTML + XLSX** with `--format all`. Without WeasyPrint, open the HTML report and use **Print → Save as PDF**.

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

### Bundled Python tools
**31** audit `.py` scripts in `scripts/` (maintainer-only checkers are not bundled). Full step ↔ script map: **`references/audit-script-matrix.md`**. Eval regression: `evals/fixtures/` + `score_eval_transcript.py --all-fixtures`.

---

## Scope

This skill covers **organic search and AI search visibility only**. It does not cover PPC / Google Ads, social media management, general marketing strategy, or content writing.

---

## License

[MIT](../../LICENSE) — use it, modify it, ship it.
