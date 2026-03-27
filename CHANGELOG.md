# Changelog

## [Unreleased]

## [1.5.5] - 2026-03-27

### Added

- **`scripts/check_github_release.py`** — pre-deployment check that verifies the current plugin version has a published GitHub Release on the Marketplace. Reads version from `plugin.json`, queries GitHub public API, exits 1 if the release is missing or a draft. Prints the exact `gh release create` fix command. Run after `git push` to confirm the Marketplace is live.
- **CI Marketplace check** — `validate-plugin.yml` now includes a "Check GitHub Marketplace Release" step that runs `check_github_release.py --warn` on every push. Warns without blocking CI so you're alerted if a GitHub Release was never published.
- **RELEASE.md step 6b** — new required verification step after `git push`, plus updated step 6c with the `gh release create` one-liner.

### Changed

- `setup-plugin.sh` — added `check_github_release.py` to the maintainer-script exclusion list so it is never bundled into the plugin for end users.
- `scripts/check-plugin-sync.py` — `SCRIPT_EXCLUDE` updated to include `check_github_release.py`.

## [1.5.4] - 2026-03-27

### Added

- **Browser caching / Expires header coverage** — `technical-checklist.md` now includes a dedicated "Browser Caching checklist" block under §6 Core Web Vitals (4 pass/fail items), a new row in the Critical Technical Issues table with detect + fix instructions, and a full `### Fixing Missing Browser Cache Headers` section with working Apache `.htaccess`, NGINX, and WordPress plugin fix code (including the safety note on 1-year cache with versioned filenames).
- **Image-level caching audit** — `image-seo.md` gains a `### Browser Caching for Images` section (3-row audit table, DevTools quick-check, fix pointers) and a `Browser Caching` dimension (5pts) in the Image SEO Score audit template.

### Changed

- `technical-checklist.md` — added missing cache headers to the Common LCP Issues list; tightened `Cache-Control` reference in the LCP fix steps.
- `image-seo.md` — updated Contents header and Alt Text score weight (30 → 25) to accommodate new Browser Caching dimension while keeping total at 100.

## [1.5.3] - 2026-03-26

### Changed

- **Skill description made "pushier"** for better triggering — added explicit "Make sure to use this skill whenever..." phrasing and expanded trigger keywords (site speed, Core Web Vitals, structured data, rich results, indexing issues, search engine visibility). Follows Anthropic's skill-creator guidance that Claude tends to "undertrigger" skills.
- **Mode routing converted from table to decision tree** — ASCII tree format is easier for the model to follow branching logic vs. scanning table rows. Sourced from Anthropic's `webapp-testing` and `claude-api` skill patterns.
- **Quality Gates (§19) rewritten with reasoning** — every hard rule now explains *why* it exists (e.g., deprecated schema wastes effort, blocking GPTBot loses live search visibility). Follows Anthropic's skill-creator principle: "explain the why" instead of rigid MUSTs.
- **Featured Snippet advice (§7c) softened with reasoning** — "Never exceed 60 words" → explains Google truncation; "Never defer the answer" → "Lead with the direct answer" with explanation.

### Added

- **Script black-box rule (§21)** — "Run scripts as black boxes. Always try `--help` first. Do not read script source unless `--help` is insufficient." Prevents wasting context tokens on large script files. Pattern from Anthropic's `webapp-testing` skill.
- **Reference Reading Guide table (§0)** — consolidated task→file→script mapping near the top of SKILL.md. Allows the model to identify which reference file to load without scanning every section. Pattern from Anthropic's `claude-api` skill.

### Meta

- All 12 evals pass (0 regressions). SKILL.md: 1,070 lines (+38 from structural additions, net from 1,032).

## [1.5.2] - 2026-03-26

### Changed

- **SKILL.md optimized per Anthropic Skill best practices** — reduced from 1,167 to 1,031 lines (-136 lines, ~2,300 fewer tokens per request).
  - Removed 7 content blocks duplicated in reference files (On-Page SEO Checklist, audit example, AI Search Landscape table, Brand Signals playbook, AI Crawler table, llms.txt template, Local review benchmarks, Script table + usage blocks). Replaced with 1-2 line pointers to the existing reference files.
  - On-Page SEO Checklist moved to `references/technical-checklist.md`; audit output example moved to new `references/audit-output-example.md`.
  - All 18 ambiguous script references now have explicit execution intent verbs ("Run `scripts/...`" or "See `references/...`").
  - Standardized "Core Web Vitals" / "CWV" terminology — full name on first use per section, abbreviation after.

### Added

- **Table of Contents** added to 13 reference files over 100 lines (previously 0/15 had TOCs). Ensures Claude sees full scope of available content even on partial file reads.
- New `references/audit-output-example.md` — 3-finding Greenleaf.io excerpt extracted from SKILL.md.
- Quora, Reddit, and Influencer/Newsletter tactical playbooks added to `references/ai-search-geo.md` → Tactical Playbooks per Channel.

## [1.5.1] - 2026-03-26

### Changed

- **Routing table (§ 1) — improved coverage and precision.**
  - Added disambiguation rule above the table: most specific match wins; first match breaks ties; no-match falls back to § 0 Intake Checklist.
  - Added cross-reference linking § 1 (topic routing) to § 0 Mode Routing to clarify the two-level dispatch.
  - Added section labels to every "Go To" cell (e.g., "§ 3 GEO" instead of bare "§ 3") for self-documenting routing.
  - New **Traffic Drop / Rankings Lost** row — triggers on "traffic dropped", "lost rankings", "rankings fell", "core update", "algorithm update", "rankings dropped"; routes to § 10 Analytics first, then § 4 / § 6.
  - Expanded GEO trigger keywords: added "SearchGPT", "Gemini", "llms.txt", "AI search".
  - Expanded Technical SEO trigger keywords: added "mobile", "mobile-friendly", "HTTPS", "security headers", "redirect chain".
  - Expanded Analytics / Reporting trigger keywords: added "penalty", "manual action" (removed "traffic drop" — now has its own dedicated row).
  - Expanded Crawl & Indexation trigger keywords: added "duplicate content", "content cannibalization".
  - New **No clear match** fallback row at bottom of main table.

### Added

- **Eval 11** — traffic drop routing test: verifies analytics-first response to core update traffic loss; asserts no schema-first or migration routing.
- **Eval 12** — GEO platform routing test: verifies GEO-focused response to Gemini/SearchGPT citation request; asserts no health score or full crawl audit.
- All 12 evals pass (0 regressions).

## [1.5.0] - 2026-03-26

### Added

- **Schema Detection Caveat** (§2 Evidence Integrity + §5 Schema Audit) — new Evidence Integrity row for "Schema not found on a CMS site" requires confirmation via Rich Results Test or browser JS console before reporting missing schema. Schema Audit step 1 expanded with caveat that `web_fetch`/`curl`/raw HTML cannot detect JS-injected schema from plugins like Yoast, RankMath, and AIOSEO.
  WHY: Many CMS sites inject JSON-LD via client-side JavaScript. Static source fetch shows no schema, leading to false "no schema found" findings. This prevents misdiagnosis on WordPress/CMS sites.

- **Expanded Competitor & Alternatives Page Playbook** (`references/link-building.md`) — four detailed page-structure templates: `[Competitor] Alternative (Singular)`, `[Competitor] Alternatives (Plural)`, `You vs [Competitor]`, and `[Competitor A] vs [Competitor B] (Third-Party)`. Each template includes URL patterns, target keywords, search intent, and 7-point content outlines. Added centralized competitor data architecture with update cadences and a 5-step competitor research process.
  WHY: The existing playbook listed page types but lacked actionable structure. Practitioners needed concrete outlines for each format to produce consistently structured comparison/alternatives pages at scale.

### Changed

- SKILL.md version → **1.5.0**; updated date → 2026-03-26.

## [1.4.1] - 2026-03-26

### Fixed

- Remove `"skills"`, `"license"`, `"homepage"`, and `"repository"` fields from `plugin.json` that blocked skill discovery in Claude.ai web app and Claude Code.
- Add `version` field to `SKILL.md` YAML frontmatter for Claude Code skill detection.
- Fix Attribution table rendering in Claude.ai web app (plain-text URLs instead of object references).

## [1.4.0] - 2026-03-26

### Added

- **GEO Brand Signal Tactical Playbook** (§3) — new "Building Brand Signals" section placed after the GEO Score Components table, directly below the line that surfaces Brand Signals as 20% of the GEO Score.
  WHY: The skill already audited whether Reddit, YouTube, and Quora signals were present, but had no fix directive for building them. This closes the gap between "Finding" and "Fix" — without the playbook, a practitioner seeing a brand-signal gap had nowhere to go next.

- **Competitor GEO Stance** (§8 Step 2 + Assessment Table) — Step 2 now instructs fetching `[competitor-url]/robots.txt` and `[competitor-url]/llms.txt` alongside top-ranking pages. Two new rows added to the Competitor Assessment Dimensions table: "AI crawler configuration" and "llms.txt presence."
  WHY: A competitor blocking OAI-SearchBot or lacking llms.txt is invisible to ChatGPT Search and gives the audited site an immediate GEO first-mover advantage. Previously §8 checked citation presence but not the configuration-level reasons behind it.

- **Competitor Sitemap Gap Analysis** (§8 Step 2 + Assessment Table) — Step 2 extended to run `sitemap_checker.py [competitor-url]` for reachability, then fetch raw sitemap XML and read `<loc>` URL path patterns. New "Topic coverage gap (sitemap)" row added to the Assessment Dimensions table.
  WHY: Topic clusters present in a competitor's sitemap but absent from the audited site are the most reliable, evidence-backed content calendar input. Previously gap identification was inferred from fetched pages only — sitemap analysis makes it systematic.

### Changed

- SKILL.md version → **1.4.0**; updated date → 2026-03-26.

## [1.3.0] - 2026-03-25

### Added

- **Internal vs. Competitive Mode** (§0) — two-mode split enforced before routing. Internal Mode (user's own site) enables full scored audit, all scripts, Execute mode, and /100 Health Score. Competitive Mode (external URL) limits to surface crawl (homepage + up to 20 pages), disables Execute mode, and labels all output "External Observation Only."
  WHY: Prevents confident /100 scores on sites the model has never fully seen; enforces evidence integrity by architecture, not by rule.

- **Evidence Integrity Table** (§2) — replaces the single CWV-only evidence rule with a six-row table covering LCP/INP/CLS, backlinks, traffic, Health Score, thin content, and schema validation. Each claim now has an explicit data-source precondition. When data is absent the output reads `[metric] not measured — run [script] for actual data`.
  WHY: The old rule guarded only performance scores. Backlink counts, traffic numbers, and thin content findings were unguarded and could be hallucinated.

- **Execute Mode Risk Gate** (§2 Mode 3) — classifies every Execute output as Safe (output directly) or High-Risk (state change, ask for confirmation before outputting). High-Risk covers robots.txt, canonical tags, redirect maps, noindex, hreflang, and bulk CMS template changes.
  WHY: One bad robots.txt change can deindex a site. The confirmation step is asymmetric — costs 5 seconds, prevents weeks of recovery.

### Changed

- SKILL.md version → **1.3.0**; updated date → 2026-03-25.

## [1.2.1] - 2026-03-25

### Changed

- **SKILL.md** — Flat YAML frontmatter (`name`, `license`, `version`, `updated`, `description` only). Author, links, and upstream credits moved to readable markdown tables so previews no longer nest YAML as awkward “tables in cells.”
- **check-plugin-sync.py** — Reads top-level `version:` in skill frontmatter (still accepts legacy indented `version` under `metadata:`).
- **README** — Clearer update instructions (cache git-pull one-liner, full reinstall commands); added Cursor IDE and Claude Desktop install methods; replaced `.skill` file reference; added Troubleshooting table covering known cache/skill-loading bugs.

### Fixed

- **plugin.json** — Skills auto-discovery now works correctly (removed invalid `"skills"` field that caused "Plugin not found" errors in some Claude Code versions).
- **.gitignore** — Added `.claude/` to prevent accidental commits of local Claude Code settings.

## [1.2.0] - 2026-03-24

### Added

- `scripts/score_eval_transcript.py` — score saved model transcripts against `evals/evals.json` (`--eval-id`, `--all-fixtures`).
- `scripts/meta_lengths_checker.py` — title, meta description, and H1 length/presence from local HTML or `--url`.
- `evals/fixtures/eval{1–10}_pass.txt` — golden transcripts; CI runs `score_eval_transcript.py --all-fixtures`.
- `evals/evals.json` — four new scenarios (7–10): news publisher, scoped technical-only, international, pre-launch strategy.
- `references/finding-verifier-example.json` + `finding-verifier-context-example.json` — sample input for `finding_verifier.py`.

### Changed

- **SKILL.md** — §0 routing index; “when not to run Mode 1” table; §1 routing notes; §2 lab/PSI evidence rule + industry preset table; §21 script list + evidence integrity + `pip install -r requirements.txt`; version **1.2.0**.
- **README** — script/eval counts, `score_eval_transcript` / `meta_lengths_checker`, **Updating the Claude Code plugin** (cache refresh).
- **references/audit-script-matrix.md** — meta lengths row, eval/QA section, `score_eval_transcript`, finding_verifier CLI + examples.
- **scripts/run_individual_checks.sh** — runs `meta_lengths_checker` when HTML fetch succeeds.
- **CI** (`.github/workflows/validate-plugin.yml`) — `py_compile` all `scripts/*.py` + eval fixture regression.
- Marketplace + `plugin.json` descriptions and version **1.2.0**.

### Fixed

- `score_eval_transcript.py` — clear stderr + exit `2` when `--text-file` is missing (no traceback); docstring points at `evals/fixtures/eval1_pass.txt`.
- `meta_lengths_checker.py` — JSON error includes `hint` to run `pip install -r requirements.txt` / `requirements-check.py`.

## [1.1.2] - 2026-03-24

### Added

- `sitemap_checker.py`, `local_signals_checker.py`, `image_checker.py` — URL/HTML checks for crawl/sitemap, local surface signals, and image alt coverage.
- `references/audit-script-matrix.md` — maps each audit step to its script and example CLI (plus **reference-only** rows where no script exists by design).
- `scripts/run_individual_checks.sh` — runs each diagnostic sequentially (JSON samples); bundled beside audit scripts in the plugin tree.
- `requirements.txt` — `requests` + `beautifulsoup4` for fetch/HTML scripts.

### Changed

- `RELEASE.md` §3 — points to the audit matrix and `run_individual_checks.sh` smoke path.
- `generate_report.py` wired to schema JSON-LD validation, image alt, sitemap, local, and IndexNow **probe** (keyless) sections + scoring and dashboard blocks.
- `validate_schema.py` supports `--json` for tooling; `indexnow_checker.py` supports `--probe` without `--key`.
- Skill §21 + README updated for **23** audit scripts; README documents `requirements.txt` and PEP 668 venv use.

### Fixed

- `generate_report.py` — On-Page table no longer crashes when `canonical` is JSON `null`.

## [1.1.1] - 2026-03-24

### Changed

- Skill YAML `description` tightened to stay within common 1024-character limits while preserving trigger terms.
- Plugin bundle (`setup-plugin.sh`) now copies **`scripts/`** (all audit `.py` files except `check-plugin-sync.py`) and **`evals/`** into `plugins/.../skills/ultimate-seo-geo/` so Claude Code plugin installs can run `python scripts/...` as documented.

## [1.1.0] - 2026-03-24

### Added

- Reference library expanded: `core-eeat-framework.md`, `cite-domain-rating.md`, `entity-optimization.md` (CORE-EEAT, CITE domain authority, entity / Knowledge Graph signals).
- Credits updated for CORE-EEAT benchmark, CITE Domain Rating, Entity Optimizer, and AI SEO / GEO content optimizer sources.
- Skill routing extended for CORE-EEAT / CITE scoring, entity optimization, and related triggers.

### Changed

- Documentation alignment: `generate_report.py` wording reflects the bundled pipeline (not a literal “19 scripts” count); §21 clarifies orchestration vs optional parallel subagents.

## [1.0.0] - 2026-03-23

### Initial Public Release

**Core Capabilities**

- Full-site SEO audits with SEO Health Score (0–100) and prioritized findings
- Generative Engine Optimization (GEO) for AI Overviews, ChatGPT, Perplexity
- Technical SEO, on-page, content/E-E-A-T, schema, links, local, international, programmatic SEO
- Site migration playbooks and analytics alignment
- Bundled Python audit scripts and eval scenarios
