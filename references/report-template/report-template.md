<!-- Updated: 2026-09-17 | Review: 2027-03-17 -->

# Report Template — the client report set

How a finished SEO & GEO engagement is delivered to a reader. This is the **design and layout contract** for the client-facing set; the Mode 1 Markdown template in `references/procedures/02-full-site-audit.md` remains the form the agent *writes* and `scripts/report_lint.py` checks. The two share one data model: the report source (§ 5), which extends the `generate_report.py --json` summary (schema_version 2).

`scripts/render_report.py` turns a report source into the set; `scripts/report_data_lint.py` checks the source. The CSS and component catalogue live beside this file: `report.css`, `print.css`, `components.html`.

---

## 1. The set

Several documents, one source. Readers differ and no single document serves all of them.

| # | Document | File | Reader | Contains |
|---|---|---|---|---|
| 0 | **Executive brief** | `0-brief.html` | Leadership | Verdict, five figures, decisions needed, top actions, what is not known. Two screens. |
| 1 | **Audit** | `1-audit.html` | Marketing lead, analyst | Diagnosis narrative, site shape (measured), findings register, strengths, opportunities, GEO readiness, coverage |
| 2 | **Strategy** | `2-strategy.html` | Marketing, content | Lanes, stop / upgrade / rebuild / new mapped to page types, prompt roster; page cards as the annex |
| 3 | **Implementation plan** | `3-plan.html` | Engineering, content, PM, agents | Recommendation register with tiers, owners, automation lanes, dependencies, done-when, status; start-today view; monitoring; standards |
| A | **Appendices** | `4-appendix.html` | Reviewers | Validity review, open tests, corrections, machine checks, glossary |
| — | **Index** | `index.html` | Everyone | One line per document, data window, version |

**Ownership rule.** Findings live only in the Audit, recommendations only in the Plan, prompts only in the Strategy, machine checks only in the Appendices. Every other document links to them by ID and never restates them.

## 2. The spine

Every document follows the same order, so a reader learns it once.

1. **Masthead** — title, one-sentence purpose, prepared for / by, date, data window, site type, set position ("2 of 4"), source version.
2. **Verdict** — one paragraph that answers the document's question, plus up to four figures that change what the reader does.
3. **Scope and coverage** — § 4.
4. **Body** — the document's own work.
5. **Register** — the structured table other documents reference.
6. **Decisions needed** — what the company must decide before work starts.
7. **Appendix** — method, tests, corrections, glossary (rendered once, in document A; other documents link).

Audit body order: **What happened → What it cost → Site shape → Findings → Strengths to protect → Opportunities → GEO readiness**. Site shape comes before Findings because the structural findings rest on it.

## 3. Findings

A finding is one defect, risk, opportunity or strength with a stated consequence. It is never a recommendation and never a bare observation.

| Field | Rule |
|---|---|
| `id` | `F1`, `F2` … stable for the engagement |
| `kind` | `defect` · `risk` · `opportunity` · `keep`. Opportunities (pages to create, tagged `opportunity` by the scripts) render in their own block, never in the severity list, unless the site type makes the absence a gap. `keep` findings render as "Strengths to protect". |
| `severity` | `critical` · `high` · `medium` · `low` · `info` (the § 2 scale) |
| `title` | One line, the consequence first |
| `observation` | The raw fact that triggered the finding (First-Principle Observation) |
| `evidence` | Numbers with window and source. Free text; sources listed in `sources` |
| `evidence_status` | `weighted` (a scored check ran) · `display_only` (a v1.15.0 structure check or another display-only check ran) · `measured` (API data or a live check outside the scored pipeline) · `sampled` · `internal` (company records) · `inferred` · `not_measured` |
| `impact` | On pipeline or on how the brand is described |
| `confidence` | `Confirmed` · `Likely` · `Hypothesis` |
| `falsifiability` | What would prove it wrong |
| `fixes` | Recommendation IDs only. The wording lives in the register |
| `watch` | Leading indicator and read date |
| `depends_on` / `blocks` | Finding and recommendation IDs |
| `machine_source` | `check:finding_id` from the summary JSON when a script produced it; absent when human-derived |
| `sources` | Source keys from `coverage.sources` |

Ordering in the Audit: by expected impact, as the author decides (`order` field), with a severity filter for the linter's view.

## 4. Scope and coverage

Present in every document. Four parts; the first two are generated.

1. **Inventory and completeness** — from the site graph: sitemap URLs, pages fetched, depth, `sitemap.complete`, `crawl.complete`, site type, and one sentence stating whether absence claims are allowed. Never claim a page type, hub, orphan or equity share is absent from an incomplete inventory (§ 26 hard rule).
2. **Checks run** — from the summary `categories` and `unmeasured`: every check with its status. Weighted checks: Strong / Needs work / Gap. Display-only checks: Reviewed / Needs work / Gap. Plus Not measured and Not applicable. Display-only checks never show a score or a weight.
3. **Data sources** — human-written: name, kind (`api` · `export` · `crawl` · `sample` · `internal` · `documentation` · `research`), window, date, limits. Followed by **Not examined** (each with a reason and the recommendation that would enable it) and **Out of scope** (each with a reason).
4. **Assumptions** the reader can reject (the § 2 Assumptions Audit).

Every finding carries `evidence_status`, so coverage is visible where it is used.

## 5. Recommendations

One register, rendered once in the Plan and referenced everywhere.

| Field | Rule |
|---|---|
| `id` | Prefixed: `T` technical · `M` measurement · `G` GEO and public facts · `C` commercial and content · `P` portfolio |
| `action` | Imperative, names the URL, template or file |
| `fixes` | Finding IDs. Every recommendation fixes at least one finding |
| `basis` | `Documented` (matches official guidance or a verified defect) · `Data-backed` · `Test first` |
| `validity` | `Confirmed` · `Revised` · `Added` · `Dropped`, from the validity review; dropped items stay in the source with `status: dropped` and render only in the appendix |
| `tier` | `Free` (PR + automated checks) · `Review` (PR + content owner) · `Gated` (written plan, staging, rollback, named approver) · `Legal` (approved data files only) · `Never` |
| `owner_role` | `Engineering` · `Content` · `Product marketing` · `Product` · `Analytics` · `Legal/InfoSec` · `Leadership` · `Sales` |
| `lane` | `Auto` (agent end to end under Free) · `Assisted` (agent drafts, human merges) · `Human` (access or authority the agent lacks) · `Decision` (a company decision must exist first) |
| `effort` | `S` ≤ 2 days · `M` ≤ 2 weeks · `L` > 2 weeks |
| `effect` | Expected effect in one line, with the metric it moves |
| `blocked_by` / `unblocks` | Recommendation IDs; the graph must be acyclic |
| `done_when` | The pass condition |
| `horizon` | `now` · `weeks_1_4` · `weeks_3_12` · `later` |
| `track` | `A` fixes · `B` tests · `C` bets |
| `status` | `planned` · `in_progress` · `shipped` · `reverted` · `read` · `dropped` |
| `supersedes` | `{check, finding_id, reason}` when a human judgement overrides a machine finding, so the reader sees both and why |
| `decision` | The decision ID this needs, when `lane` is `Decision` |

Views generated from the register: by horizon (the Plan timeline), by owner, **start today** (every `Auto` or `Assisted` item with no unmet `Decision` or `Human` blocker), by page type (what to create), by page (the annex cards).

## 6. Prioritisation rule

State it, then apply it visibly. Precedence:

1. **Measurement prerequisites** — exports with expiry dates, the site graph, the prompt baseline. Nothing later can be read without them.
2. **Stop-loss and public-fact fixes** — wrong claims, broken redirects, corrupted assets: confirmed defects with a clear right answer and a cost per day.
3. **Confirmed defects** with a documented fix and no measurement dependency (Track A).
4. **Tested changes** (Track B), one test per page set, ordered by value at stake × confidence ÷ effort.
5. **Bets** (Track C), including page-type opportunities, gated on a test read or the baseline.

Within a level, tie-break by value at stake × confidence ÷ effort. The risk tier is a gate, not a score input. Every row shows Blocked by / Unblocks.

## 7. Health Score

Client documents show a `/100` only when it is the `overall` of a `generate_report.py` run, with its source line; otherwise "not scored" with a reason (the v1.14.0 contract). Structure checks, citability and other display-only checks never carry a score.

## 8. Design system

`report.css` holds the tokens and components; `components.html` renders each once in light and dark. Rules:

- **Fonts**: Instrument Sans (headings, UI, tables and prose; `--serif` is an alias of `--sans` kept for compatibility) and JetBrains Mono (IDs, numbers, code, eyebrows), the Tobto faces, loaded from Google Fonts with system fallbacks.
- **Colour** is semantic only: `critical`, `warn`, `good`, `accent`, `opp`, plus paper / surface / ink / muted / line. Values come from the Tobto design system: brand blue `#0057B7` is the accent, neutrals are the ink ladder, each semantic hue uses its -700 step as type on light and its -300 step on dark, and Blaze orange `#FF6A1A` (`--opp`) marks opportunities and new pages only, never small type. Surfaces separate with hairlines, not shadows; cards use `--r-card` (14px) and chips `--r-chip` (6px). Dark mode by `prefers-color-scheme` and `data-theme`.
- **Components**: masthead, sticky section nav, verdict, figure strip, table wrapper, finding card, opportunity block, keep block, recommendation row, chips (severity, kind, evidence status, tier, lane, validity, basis), coverage table, callout, before / after, page card, prompt card, section tree (nested list), dependency list, glossary, footer.
- **Diagrams** are static. The section tree from `site_architecture.py` renders as a nested list; the Mermaid text goes in the appendix for readers who want to paste it.
- **Print**: `print.css` sets A4, page numbers, no sticky nav, tables unbroken, links expanded.
- **No CDN scripts.** Scroll-spy is the only JavaScript and the page reads fully without it.
- **Length targets**: brief ≤ 700 words; audit ≤ 8,000 words of prose outside registers; strategy ≤ 6,000; plan is mostly table.
- **One design system.** `generate_report.py` reads `report.css` and `print.css` from this folder at run time and inlines them, so the automated report, the client set and the agent's HTML share one visual language. Its page is the same spine (§ 2) with the sections a machine-only run can fill: masthead with a coverage bar, verdict and figures, the delta since a `--previous` run, Health Score by category, coverage, site shape, findings by kind, GEO readiness, recommendations, platform, and check details as the appendix.

## 9. Freshness and versioning

The masthead shows the source `version` and `generated` date; every generated table shows the data date it came from (`graph.generated`, `summary.timestamp`, each source's `date`). A change log for shipped changes lives with the client (`CHANGELOG-SEO.md`), linked from the Plan.

## 10. Checks the source lint enforces

- Required fields per finding and recommendation, values on their scales.
- Every `fixes` ID exists; every recommendation fixes ≥ 1 finding; every `blocked_by` / `unblocks` / `depends_on` ID exists; the blocked-by graph is acyclic.
- Display-only findings never carry a weight; a `/100` score only with a `summary` source.
- `opportunity` findings are not in the severity list; `keep` findings carry no fix.
- Absence claims (a finding whose `observation` says a page type, hub or orphan is missing) only when the graph says the inventory is complete.
- Every `Decision`-lane recommendation names a decision; every decision is listed.
- No Core Web Vitals or backlink numbers in prose when the corresponding source is `not_measured`.
