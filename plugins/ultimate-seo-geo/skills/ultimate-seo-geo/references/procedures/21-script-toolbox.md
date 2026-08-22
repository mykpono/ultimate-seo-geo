> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

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

**Excel:** `python scripts/generate_report.py https://example.com --format xlsx --output report.xlsx` (requires `openpyxl`).

**PDF:** `python scripts/generate_report.py https://example.com --format pdf --output report.pdf` — optional **`weasyprint`** (`pip install weasyprint`; [system dependencies](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation) may apply). If WeasyPrint is unavailable or rendering fails, generate HTML and use the browser **Print → Save as PDF**.

**Both HTML + XLSX:** `--format all --output report` → writes `report.html` and `report.xlsx`.

### Script Quick Reference

For the complete script-to-section mapping (all 24 scripts with purpose and audit section), see `references/audit-script-matrix.md`.

### Targeted Usage

```bash
# Validate schema after generating it
python scripts/validate_schema.py page.html --json

# Check AI crawler access
python scripts/robots_checker.py https://example.com

# Check llms.txt (non-Google engines only — Google Search ignores it)
python scripts/llms_txt_checker.py https://example.com

# Check the preferred sources opt-in (news/publisher sites)
python scripts/preferred_sources_checker.py https://example.com

# Import a hand-exported GSC generative-AI performance CSV (no API exists)
python scripts/gsc_ai_import.py ai-performance-export.csv --json

# Regression: score a transcript against eval fixtures
python scripts/score_eval_transcript.py --all-fixtures
```


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
