# Ultimate SEO + GEO Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![AGENTS.md](https://img.shields.io/badge/AGENTS.md-compatible-blue)](https://agents.md)
[![Version](https://img.shields.io/badge/version-1.7.2-green.svg)](CHANGELOG.md)

The definitive SEO and Generative Engine Optimization skill for AI coding agents. Runs full site audits with scored findings, generates ready-to-deploy fixes, and optimizes content for both Google Search and AI search engines (Google AI Overviews, AI Mode, ChatGPT Search, Perplexity).

Works with **any AGENTS.md-compatible tool**: Claude Code, Cursor, OpenAI Codex, Gemini CLI, GitHub Copilot, Windsurf, Cline, Aider, Devin, and more.

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

## Platform Compatibility

| Platform | How It Loads Instructions | Script Execution | Setup |
|---|---|---|---|
| **OpenAI Codex** | `AGENTS.md` auto-loaded (32 KiB limit) | Full (shell access) | Clone repo, start coding |
| **Google Gemini CLI** | `GEMINI.md` → imports `AGENTS.md` | Full (shell access) | Clone repo, start coding |
| **Claude Code** | Plugin marketplace + `SKILL.md` | Full (shell access) | `/plugin install` (see below) |
| **Cursor IDE** | `AGENTS.md` + `.cursor/rules/` + skill auto-discovery | Full (shell access) | Clone repo or install skill |
| **GitHub Copilot** | `AGENTS.md` + `.github/copilot-instructions.md` | Full (agent mode) | Clone repo, start coding |
| **Windsurf** | `AGENTS.md` auto-loaded | Full (shell access) | Clone repo, start coding |
| **Cline** | `AGENTS.md` auto-loaded | Full (shell access) | Clone repo, start coding |
| **Aider / Devin / Goose / Amp** | `AGENTS.md` auto-loaded | Full (shell access) | Clone repo, start coding |
| **ChatGPT Custom GPT** | Uploaded instructions + knowledge files | Limited (no scripts) | See `chatgpt/README.md` |
| **Claude Desktop (claude.ai)** | Upload `SKILL.md` to Project Knowledge | No shell access | Manual upload |

`AGENTS.md` is the [cross-tool standard](https://agents.md) (Linux Foundation, 20+ tools). One file covers all AGENTS.md-compatible platforms.

## Installation

### Any AGENTS.md-Compatible Tool (Codex, Gemini CLI, Copilot, Windsurf, Cline, Aider, etc.)

Clone the repo into your project or working directory. The tool auto-discovers `AGENTS.md`:

```bash
git clone https://github.com/mykpono/ultimate-seo-geo.git
cd ultimate-seo-geo
pip install -r requirements.txt
```

That's it. Open the folder in your tool and start asking for SEO audits.

### Claude Code — Plugin Marketplace

**Use [Claude Code](https://code.claude.com/)** (the terminal-based Claude product). The lines below are **slash commands** you type in the **Claude Code chat**, not in macOS Terminal or zsh.

In Claude Code, run:

```text
/plugin marketplace add mykpono/ultimate-seo-geo
/plugin install ultimate-seo-geo@ultimate-seo-geo
```

Or install directly without adding the marketplace first:

```text
/plugin install https://github.com/mykpono/ultimate-seo-geo.git
```

#### Updating the plugin after a GitHub release

Claude Code caches the marketplace clone locally — it does **not** auto-pull new commits. Pick one approach:

**Option A — Update the cache (fastest):**

```bash
cd ~/.claude/plugins/marketplaces/ultimate-seo-geo && git pull
```

Then restart your Claude session (or run `/reload-plugins` in Claude Code).

**Option B — Full reinstall:**

```text
/plugin uninstall ultimate-seo-geo
/plugin marketplace add mykpono/ultimate-seo-geo
/plugin install ultimate-seo-geo@ultimate-seo-geo
```

**For maintainers** — before pushing a release, verify plugin sync:

```bash
python3 scripts/check-plugin-sync.py
```

### Claude Code — Manual skill install (global)

```bash
cp -r ultimate-seo-geo ~/.claude/skills/
```

### Cursor IDE

Cursor reads `AGENTS.md` automatically from the repo root. For the full skill experience with progressive disclosure, install to the skills directory:

```bash
rsync -a --delete --exclude='.git/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='.venv/' \
  /path/to/ultimate-seo-geo/ ~/.claude/skills/seo/
```

### ChatGPT Custom GPT

ChatGPT Custom GPTs cannot read repo files — they need uploaded knowledge files. See [`chatgpt/README.md`](chatgpt/README.md) for step-by-step setup.

### Claude Desktop App (claude.ai)

The Claude desktop app does not load skills from `~/.claude/skills/`. Instead:

1. Open a **Project** in claude.ai
2. Go to **Project Knowledge**
3. Upload `SKILL.md` as a file, or paste its contents into custom instructions

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
├── AGENTS.md             ← Universal entrypoint (24KB, under 32KB Codex limit)
│                           Auto-loaded by Codex, Gemini, Copilot, Windsurf, Cline, etc.
├── GEMINI.md             ← Gemini CLI entrypoint (imports AGENTS.md)
├── SKILL.md              ← Full instructions (~1,280 lines, 81KB)
│                           Mode routing, audit process, output templates, examples
│
├── .github/
│   └── copilot-instructions.md  ← GitHub Copilot supplementary context
│
├── chatgpt/              ← ChatGPT Custom GPT bundle
│   ├── instructions.txt     Condensed instructions (under 8K chars)
│   ├── README.md            Setup guide
│   └── copy-knowledge-files.sh  Copies files for upload
│
├── references/            ← Domain knowledge (20 .md files, load on demand)
│   ├── ai-search-geo.md     GEO signals, platform data, brand strategy
│   ├── technical-checklist.md  CWV fixes, JS SEO, IndexNow
│   ├── schema-types.md       All Schema.org types + templates
│   ├── eeat-framework.md     E-E-A-T scoring, spam categories
│   ├── core-eeat-framework.md  80-item CORE-EEAT content benchmark
│   ├── cite-domain-rating.md   40-item CITE domain authority
│   ├── entity-optimization.md  Entity / Knowledge Graph checklist
│   ├── ...and 13 more
│
├── scripts/               ← 25 bundled Python scripts
│   ├── generate_report.py    Full-site HTML dashboard (runs all scripts)
│   ├── validate_schema.py    JSON-LD validation
│   ├── robots_checker.py     AI crawler access check
│   ├── ...and 22 more
│
└── evals/                 ← 14 scenarios, 60 assertions + golden fixtures
    ├── evals.json
    └── fixtures/
```

**Two-layer progressive disclosure for cross-platform support:**
- **Layer 1** — `AGENTS.md` (24KB): auto-loaded by all AGENTS.md-compatible tools. Contains routing, condensed procedures, script reference, and quality gates.
- **Layer 2** — `SKILL.md` (81KB) + `references/` + `scripts/`: loaded on demand when deeper detail or execution is needed.

For Claude Code and Cursor, `SKILL.md` is loaded natively as a skill. For all other platforms, `AGENTS.md` provides enough context to route and execute, with pointers to load `SKILL.md` sections when full detail is needed.

**Claude Code plugin install:** `bash setup-plugin.sh` mirrors `SKILL.md`, `AGENTS.md`, `GEMINI.md`, `references/`, `scripts/` (audit scripts only), and `evals/` into `plugins/.../skills/ultimate-seo-geo/` so `python scripts/...` paths work after marketplace install.

### Claude Code: why two `.claude-plugin/` folders?

Do **not** merge them into one directory. This repo follows the layout Claude Code expects for a **GitHub marketplace** plus an **installable plugin**:

| Location | File | Role |
|----------|------|------|
| **Repo root** | `.claude-plugin/marketplace.json` | **Marketplace catalog** — lists plugins, owner metadata, and each plugin’s `source` path (here: `./plugins/ultimate-seo-geo`). |
| **Under that path** | `plugins/ultimate-seo-geo/.claude-plugin/plugin.json` | **Plugin manifest** for the package at `source` — name, version, keywords, repository URL, etc. |

When someone runs `/plugin marketplace add mykpono/ultimate-seo-geo`, the tool reads the **root** catalog, then resolves **`source`** and loads **that folder’s** `plugin.json`. Putting both JSON files in a single `.claude-plugin/` would break that resolution. A repo that is **only** a plugin (no marketplace) can use a single plugin manifest at the root, but then you typically would **not** use the marketplace flow for that repo.

---

## Scripts

**Bundled in the plugin:** **25** URL/HTML diagnostic scripts, plus **`requirements-check.py`** (preflight), **`score_eval_transcript.py`** (eval regression), and **`meta_lengths_checker.py`**. **`check-plugin-sync.py`**, **`check_github_release.py`**, and **`check_version_sync.py`** are repo-only for CI. Python 3.8+; install dependencies with:

```bash
pip install -r requirements.txt
```

On **PEP 668**–managed Python (e.g. Homebrew), use a venv first: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`, then run scripts with `.venv/bin/python`.

Preflight (optional): `python scripts/requirements-check.py` or `python scripts/requirements-check.py --json` — exits non-zero if `requests` / `beautifulsoup4` are missing.

**Eval regression (optional):** save a model reply to `transcript.txt`, then `python scripts/score_eval_transcript.py --eval-id 1 --text-file transcript.txt`. CI runs `python scripts/score_eval_transcript.py --all-fixtures` against `evals/fixtures/`.

Run the full-site report to start any audit:

```bash
python scripts/generate_report.py https://example.com --output seo-report.html
```

| Script | Purpose |
|---|---|
| `generate_report.py` | Full-site HTML dashboard — bundled analysis pipeline |
| `requirements-check.py` | Preflight: `requests` + `beautifulsoup4` installed (`--json`) |
| `score_eval_transcript.py` | Score replies vs `evals/evals.json` (`--eval-id` or `--all-fixtures`) |
| `meta_lengths_checker.py` | Title / meta description / H1 lengths (`--url` or local HTML) |
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
| `sitemap_checker.py` | Sitemap discovery via robots.txt + first sitemap sanity |
| `local_signals_checker.py` | LocalBusiness / tel / address signals on a URL |
| `image_checker.py` | Image alt coverage from saved HTML |

---

## Eval Results

Benchmarked against baseline (no skill) across multiple scenarios (see `evals/evals.json`; **14** prompts, **60** assertions):

| Metric | With Skill | Without Skill | Delta |
|---|---|---|---|
| Pass rate | **100%** | 87% | **+13 pts** |
| Avg time | 103s | 54s | +49s |
| Avg tokens | 83K | 64K | +19K |

The skill adds ~50 seconds and ~19K tokens per task, but achieves 100% on structured output requirements (finding format, correct schema types, health scoring) where the baseline misses.

**Test scenarios include:** YMYL publisher audit, local HVAC + schema, SaaS schema, migration plan, recipe content (no URL), negative PPC, news/paywall, scoped robots+sitemap-only, international hreflang, pre-launch strategy (no live site), traffic drop routing, GEO platform routing, execute mode risk gate (robots.txt), evaluator-optimizer fabrication check. **Automated check:** `python scripts/score_eval_transcript.py --all-fixtures`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "This plugin doesn't have any skills or agents" | Marketplace not cloned to local cache | Run `/plugin marketplace add mykpono/ultimate-seo-geo` then `/plugin install ultimate-seo-geo@ultimate-seo-geo`, or manually clone: `git clone https://github.com/mykpono/ultimate-seo-geo.git ~/.claude/plugins/marketplaces/ultimate-seo-geo` |
| "Could not load skill files" | Stale cache after a GitHub update | `cd ~/.claude/plugins/marketplaces/ultimate-seo-geo && git pull`, then restart session |
| Plugin enabled but skill not appearing | Known Claude Code bug — `/reload-plugins` sometimes misses new skills ([#35641](https://github.com/anthropics/claude-code/issues/35641)) | Fully restart your Claude session |
| `zsh: no such file or directory: /plugin` | `/plugin` is a Claude Code slash command, not a shell command | Run `claude` first to start a Claude Code session, then type the `/plugin` commands inside it |
| Only some skills downloaded | Incomplete cache clone ([#35989](https://github.com/anthropics/claude-code/issues/35989)) | Delete `~/.claude/plugins/marketplaces/ultimate-seo-geo` and re-clone |

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
