> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

## 21. Script Toolbox — Automated Checks

**Run scripts as black boxes.** Always try `python scripts/<name>.py --help` first to see usage and options. Do not read the script source code unless `--help` is insufficient and you need to customize behavior — script files are large and reading them wastes context tokens. They are designed to be invoked directly, not ingested.

There are **27** Python **diagnostic** scripts for URL/HTML checks, plus **`requirements-check.py`** (dependency preflight) and **`score_eval_transcript.py`** (regression scoring for `evals/evals.json`). **`render_report.py`** and **`report_data_lint.py`** render and lint the client report set (`references/report-template/report-template.md`). **`check-plugin-sync.py`** is maintainers/CI only and is **not** copied into the plugin bundle. **Every major audit step maps to a script** — see `references/audit-script-matrix.md`. **Merge duplicate findings** with `finding_verifier.py` using `references/finding-verifier-example.json` as the JSON shape reference (optional `references/finding-verifier-context-example.json` for context).

They are **not** invoked via subagents in this skill file: the default path is **one shell process** — either `generate_report.py` (bundled pipeline, runs the URL + HTML checks below) or targeted `python scripts/... --json` calls. **Optional:** In clients that expose a Task/subagent tool, you may delegate **independent** script runs in parallel **only when** you are **not** already running `generate_report.py` for the same URL (avoid duplicate work). Merge subagent outputs in the main thread before scoring.

**Run all individual URL checks in sequence (bash):** `bash scripts/run_individual_checks.sh https://example.com` (prints JSON from each tool; for a single HTML report use `generate_report.py` instead).

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
└── Synthesize: merge all JSON → run finding_verifier.py → write report (not scored unless generate_report.py ran) → report_lint.py
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

**Layout:** the HTML follows the report design in `references/report-template/report-template.md` (one page, the same `report.css` as the client set): masthead with a coverage bar, verdict and figures, Health Score by category, scope and coverage, site shape, findings by kind (opportunities apart), GEO readiness, recommendations, platform, and every check's detail as an appendix. Nothing is hidden behind JavaScript.

**Previous run:** `python scripts/generate_report.py https://example.com --json summary.json --previous last-month.json` opens the report with what changed since the earlier `--json` summary (score delta, findings resolved and new, checks that changed status) and writes the same comparison under `"previous"` in the new summary.

**White-label:** `--prepared-for "Client"`, `--prepared-by "Agency"` fill the masthead; `--accent "#B83F00"` sets the accent colour. Nothing else in the design changes per brand.

**Excel:** `python scripts/generate_report.py https://example.com --format xlsx --output report.xlsx` (requires `openpyxl`).

**PDF:** `python scripts/generate_report.py https://example.com --format pdf --output report.pdf` — optional **`weasyprint`** (`pip install weasyprint`; [system dependencies](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation) may apply). If WeasyPrint is unavailable or rendering fails, generate HTML and use the browser **Print → Save as PDF**.

**Both HTML + XLSX:** `--format all --output report` → writes `report.html` and `report.xlsx`.

### CI Gate on the Full Report

Fail a build when the audited site regresses:

```bash
python scripts/generate_report.py https://staging.example.com --format none --json seo-summary.json --fail-under 70 --fail-on critical --github-annotations
```

| Exit code | Meaning |
|---|---|
| 0 | Gates passed, or none set |
| 1 | Gate failed: overall score below `--fail-under`, or a finding at or above `--fail-on` |
| 2 | Usage error |
| 3 | Inconclusive: fewer than 5 weighted checks were measured, so the score is not judged. A critical finding still fails with `--fail-on`. |

- **Summary file:** `--json` writes a stable summary (`schema_version` 2). `--json -` writes it to stdout and sends progress to stderr. It holds:
  - `overall`, `grade`, `measured_categories`, `unmeasured` (checks left out of the score) and `gate`
  - `severity_scale`: `["critical", "high", "medium", "low", "info"]`, strongest first
  - `groups`: the nine report categories of § 2 (`content`, `technical`, `on_page`, `links`, `schema`, `performance`, `geo`, `images`, `local`)
  - `categories`: per check, `label`, `group`, `score` (`null` when unmeasured or not applicable), `weight` and `status`
  - `group_scores`: per report category, `score` (weighted mean of its measured checks, `null` if none), `share` (percent of the measured weight, so `overall` is the share-weighted mean of the group scores, to within a point of rounding), `status` (Strong / Needs work / Gap / Not measured / Not applicable), `checks` and `unmeasured`. This is the category table of the § 2 audit template
  - `counts`: findings per severity on the full scale
  - `findings`, strongest first. Each has the same fields the § 2 Finding Format uses, so agent-written findings can share the shape:

    | Field | Meaning |
    |---|---|
    | `id` | `F01`, `F02`, … in severity order; matches the HTML report |
    | `severity` | On `severity_scale`. A script's older `warning` is read as `medium` |
    | `level` | `critical` / `warning` / `info`: the bucket `--fail-on`, annotations and the HTML use. `high` → `critical`, `medium` → `warning`, `low` → `info` |
    | `section`, `group` | The check that raised it, and its report category |
    | `finding`, `fix` | What is wrong and what to do (`fix` may be empty) |
    | `evidence`, `impact`, `falsifiability`, `leading_indicator`, `dependency` | As supplied by the script, else `null`. Never filled with generic text |
    | `confidence` | `Confirmed` / `Likely` / `Hypothesis`, or `null` when the script gave none of these |
    | `source` | `script:<section>` |
    | `tags` | e.g. `quick_win`; `[]` when none |

  **Migrating from `schema_version` 1:** v1 `severity` is v2 `level`. Counts are keyed by the full scale, so `counts.warning` is now `counts.medium`. Gate behaviour and exit codes are unchanged.
- **Unmeasured checks don't count.** A check that errors or never runs (a rate-limited PageSpeed call, a timeout) is left out of the overall score and listed as unmeasured, so it cannot fail the gate on its own.
- **Target a URL the job controls,** such as a staging or preview URL. The run fetches the target from the CI runner, so rate limits and bot protection on the target can leave checks unmeasured. Treat exit 3 as "rerun", not as a pass.
- **Annotations:** `--github-annotations` prints `::error` / `::warning` lines for critical and warning findings. Site text is escaped so it cannot inject workflow commands.

GitHub Actions step:

```yaml
- name: SEO gate
  run: |
    pip install -r requirements.txt
    python scripts/generate_report.py "$PREVIEW_URL" --format none --json seo-summary.json --fail-under 70 --fail-on critical --github-annotations
```

### Script Quick Reference

For the complete script-to-section mapping (all 24 scripts with purpose and audit section), see `references/audit-script-matrix.md`.

### Targeted Usage

```bash
# Validate schema after generating it
python scripts/validate_schema.py page.html --json

# Check AI crawler access
python scripts/robots_checker.py https://example.com

# Check whether a firewall or CDN refuses AI crawlers that robots.txt allows (suspected, not proven)
python scripts/ai_bot_access.py https://example.com

# What AI crawlers actually requested, from server access logs (IPs verified, never printed)
python scripts/ai_bot_logs.py access.log --verify-ips --json

# AI citation presence as a rate: write a prompt x engine x run grid, fill it in, then score it
python scripts/citation_sampling.py --template --prompts prompts.txt --engines chatgpt,perplexity --runs 5 --output runs.csv
python scripts/citation_sampling.py runs.csv --domain example.com --json

# Instructions to AI systems hidden from visitors (prompt injection, invisible Unicode)
python scripts/hidden_instructions.py https://example.com --json

# AI assistant referral sessions in GA4 (Tier 2; a floor, untagged clicks read as Direct)
python scripts/ga4_report.py --property 123456789 --ai-referrals --json

# Check llms.txt (non-Google engines only — Google Search ignores it)
python scripts/llms_txt_checker.py https://example.com

# llms.txt links the sitemap no longer lists, and which of them are dead (informational)
python scripts/llms_txt_checker.py https://example.com --check-sitemap --json

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
