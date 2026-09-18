<!-- Updated: 2026-09-18 | Review: 2027-03-18 -->

# Report Template — the client report

How a finished SEO & GEO engagement is delivered to a reader. This is the **design and layout contract** for the client-facing report; the Mode 1 Markdown template in `references/procedures/02-full-site-audit.md` remains the form the agent *writes* and `scripts/report_lint.py` checks. The two share one data model: the report source (§ 5), which extends the `generate_report.py --json` summary (schema_version 2).

`scripts/render_report.py` turns a report source into `report.html`; `scripts/report_data_lint.py` checks the source. The CSS and component catalogue live beside this file: `report.css`, `print.css`, `components.html`.

---

## 1. The report

One file, `report.html`, rendered from one source. Readers differ, so the page is split into parts in the order a reader stops: leadership reads Part 1 and can stop there.

| Part | Reader | Contains |
|---|---|---|
| 1 **Summary** | Leadership | Verdict and up to four figures, decisions needed, this week's actions, what is not known yet. ≤ 700 words of prose. |
| 2 **Audit** | Marketing lead, analyst | Scope and coverage, the author's diagnosis sections, site shape (measured), findings, strengths, opportunities, GEO readiness |
| 3 **Strategy** | Marketing, content | Lanes and stop / upgrade / rebuild / new, the prompt roster, page cards (folded by wave) |
| 4 **Plan** | Engineering, content, PM, agents | Priority rule, timeline by horizon with **Start today** marked, the full recommendation register, monitoring, standards |
| 5 **Appendix** | Reviewers | Validity review, corrections, open tests, machine checks, Mermaid section tree, glossary. Every section folded. |

A part with nothing to show (no strategy content, no appendix material) is left out, with its nav link.

**Render-once rule.** Each thing appears in one place and everything else links to it by ID: the verdict and the decisions in the Summary, coverage and findings in the Audit, prompts and page cards in the Strategy, the register in the Plan, machine checks in the Appendix. Each finding, recommendation, decision and prompt ID is an anchor exactly once on the page (`tests/test_report_set.py`).

## 2. The spine

1. **Masthead** — title (`meta.title`, default "<client> SEO & GEO report"), one-sentence purpose (`meta.purpose`), prepared for / by, date, data window, site type, source version.
2. **Sticky nav** — the five parts, with scroll-spy.
3. **Parts** — each opens with "Part n", its title, a contents line of its sections and a one- or two-sentence lead (`docs.<part>.verdict`, ≤ 60 words). Sections number within their part (`2.3`) and their ids are prefixed with the part (`audit-findings`, `plan-register`).
4. **Footer** — date, author, generator and source version, and what to do when a preview pane swallows links.

Where the source has no `docs.brief`, the Summary takes the audit's verdict and figures and the Audit does not repeat them.

Audit order: **Scope and coverage → the author's sections (what happened, what it cost) → Site shape → Findings → Strengths to protect → Opportunities → GEO readiness**. Site shape comes before Findings because the structural findings rest on it.

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

Rendered once, as the first section of the Audit; the Summary lists what is not known and links to it. Four parts; the first two are generated.

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
| `validity` | `Confirmed` · `Revised` · `Added` · `Dropped`, from the validity review; dropped items stay in the source with `status: dropped` and render struck through in the register and in the validity review, never in the timeline or this week's actions |
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

Views generated from the register: the Plan timeline by horizon, with **Start today** marked on every `Auto` or `Assisted` item that has no unmet blocker; this week's actions in the Summary (items flagged `brief`, else the first six with horizon `now`); by page (the Strategy's page cards). Only the full register carries each recommendation's anchor; the other views link to it.

## 6. Prioritisation rule

State it, then apply it visibly. Precedence:

1. **Measurement prerequisites** — exports with expiry dates, the site graph, the prompt baseline. Nothing later can be read without them.
2. **Stop-loss and public-fact fixes** — wrong claims, broken redirects, corrupted assets: confirmed defects with a clear right answer and a cost per day.
3. **Confirmed defects** with a documented fix and no measurement dependency (Track A).
4. **Tested changes** (Track B), one test per page set, ordered by value at stake × confidence ÷ effort.
5. **Bets** (Track C), including page-type opportunities, gated on a test read or the baseline.

Within a level, tie-break by value at stake × confidence ÷ effort. The risk tier is a gate, not a score input. Every row shows Blocked by / Unblocks.

## 7. Health Score

The client report shows a `/100` only when it is the `overall` of a `generate_report.py` run, with its source line; otherwise "not scored" with a reason (the v1.14.0 contract). Structure checks, citability and other display-only checks never carry a score.

## 8. Design system

`report.css` holds the tokens and components; `components.html` renders each once in light and dark. Rules:

- **Fonts**: Instrument Sans (headings, UI, tables and prose; `--serif` is an alias of `--sans` kept for compatibility) and JetBrains Mono (IDs, numbers, code, eyebrows), the Tobto faces, loaded from Google Fonts with system fallbacks.
- **Colour** is semantic only: `critical`, `warn`, `good`, `accent`, `opp`, plus paper / surface / ink / muted / line. Values come from the Tobto design system: brand blue `#0057B7` is the accent, neutrals are the ink ladder, each semantic hue uses its -700 step as type on light and its -300 step on dark, and Blaze orange `#FF6A1A` (`--opp`) marks opportunities and new pages only, never small type. Surfaces separate with hairlines, not shadows; cards use `--r-card` (14px) and chips `--r-chip` (6px). Dark mode by `prefers-color-scheme` and `data-theme`.
- **Components**: masthead, sticky part nav, part head with contents line, folded section (`details.fold`), verdict, figure strip, table wrapper, finding card, opportunity block, keep block, recommendation row, chips (severity, kind, evidence status, tier, lane, validity, basis), coverage table, callout, before / after, page card, prompt card, section tree (nested list), dependency list, glossary, footer.
- **Diagrams** are static. The section tree from `site_architecture.py` renders as a nested list; the Mermaid text goes in the appendix for readers who want to paste it.
- **Print**: `print.css` sets A4, page numbers, no sticky nav, tables unbroken, links expanded, each part on a new page. Printing opens every folded section and restores them afterwards.
- **No CDN scripts.** The only JavaScript is scroll-spy, unfolding a folded section a link points into, opening folds for print, the theme toggle, the finding filter, copy buttons and a click handler that scrolls in-page links (a chat or IDE preview embeds the report as an iframe `srcdoc`, where a plain `#id` link resolves to the host page and navigates away). The page reads fully without it; where a preview also blocks scripts, the footer tells the reader to open the file in a browser. Every `href="#…"` must name an `id` on the same page (`tests/test_report_anchors.py`).
- **Length targets**: Summary ≤ 700 words of prose (lint warning); each part's lead ≤ 60 words (lint warning); Audit ≤ 8,000 words of prose outside registers; Strategy ≤ 6,000; the Plan is mostly table.
- **One design system.** `generate_report.py` reads `report.css` and `print.css` from this folder at run time and inlines them, so the automated report, the client report and the agent's HTML share one visual language. Its page follows the same masthead-then-verdict order (§ 2) with the sections a machine-only run can fill: masthead with a coverage bar, verdict and figures (severity, then who acts), the delta since a `--previous` run, the **action plan** by lane (§ 5 `lane`: `Auto` first, with a copyable fix prompt for an agent, then `Assisted`, `Human`, `Decision`), **open questions** (unmeasured checks and `data_gap` findings, each with what closes it; never counted as defects), Health Score by category, coverage, site shape, findings by kind, GEO readiness, platform, and check details as the appendix, which is the only place a check's recommendations are printed.

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
- Every id the page carries is unique: author section ids (`docs.audit.sections`, `docs.strategy.sections`) are valid HTML ids, unique within their part and never one the renderer writes (`coverage`, `findings`, `prompts` …); prompt ids never repeat and never reuse a finding, recommendation or decision id. A section without `id` or `title` is an error.
- Warnings: the Summary over 700 words, a part's lead over 60, and `docs.*.title`, `docs.*.sub` or `docs.index.how`, which the single page does not render.
