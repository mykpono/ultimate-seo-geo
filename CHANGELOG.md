# Changelog

## [Unreleased]

_Nothing yet._

## [1.12.1] - 2026-08-23

> Folds in what was sitting under `[Unreleased]`: the reference-file refresh (PR #24) landed on
> `main` before this version was tagged, so it ships inside 1.12.1 and is described here rather
> than being held back for a release it would not actually be part of.

Two workstreams. **Codex compatibility** — `AGENTS.md` was over the instruction-file budget and
silently truncating. **Reference accuracy** — the thirteen March-dated reference files came due
for review, and auditing them turned up three real defects rather than just stale timestamps.

### Fixed

- **`AGENTS.md` no longer truncates on Codex** — the file was **37,238 bytes** against Codex's
  32 KiB `project_doc_max_bytes` default. Codex truncates **silently**: no warning in the TUI,
  `/stats`, `exec`, or the VS Code extension, and everything past the cutoff is never sent to the
  model. Since the README advertises AGENTS.md compatibility, this was a correctness bug, not
  housekeeping. Five sections were invisible to every Codex user:
  §22 Drift Monitoring, §23 Semantic Clustering, §24 E-commerce, §25 Maps Intelligence, and the
  Google API Tier System — plus **the "Full Detail Reference" table**, the map to `references/`,
  so the agent could not find the files it was being told to read. Now **32,726 bytes** with
  nothing truncated.

- **12 CLI tools were missing from `references/audit-script-matrix.md`** — `content_quality.py`,
  `gsc_export.py` and `render_page.py` appeared in **no** index at all; the other nine
  (`content_brief`, `crux_history`, `drift_monitor`, `ecommerce_schema`, `ga4_report`,
  `google_api_tier`, `gsc_query`, `maps_checker`, `topic_cluster`) were listed only in the
  AGENTS.md section that truncates. The matrix now indexes **all 45** CLI tools and is the single
  source of truth; `render_page.py` and `google_api_tier.py` were added to the Utilities table.

- **Four procedure files were unreachable from `AGENTS.md`** — `01-request-detection-routing.md`,
  `16-strategy-roadmap.md`, `17-monthly-maintenance.md` and `19-quality-gates-hard-rules.md` had no
  pointer, so the agent had no route to them. All **25** are now referenced, with none broken.

- **README version badge and Layer 1 size** — badge tracked 1.10.2 through two releases; the
  architecture note claimed `AGENTS.md (~27KB)` when it was 37 KB.

- **"Helpful Content" described as a live, separate system in three places** — `references/programmatic-seo.md`
  called it the "Helpful Content System (2022-ongoing)" and both it and `references/local-seo.md` framed thin
  content as a "Helpful Content risk", while `references/procedures/06-content-eeat-and-pruning.md` and
  `references/analytics-reporting.md` correctly recorded it as **merged into core in March 2024**. The plugin
  contradicted itself, and the practical harm is specific: it implies a client should wait for "the next
  Helpful Content update", which will never come. Rewritten to say helpfulness is weighted continuously
  inside core — the site-wide effect persists, the separate event does not.

- **Cross-language canonicalization was uncovered** (`references/international-seo.md`, `scripts/hreflang_checker.py`)
  — the reference required hreflang to *point at* canonical URLs (rule 4) but never said each language version
  must canonicalize to **itself**. A French page canonicalizing to the English one declares itself a duplicate,
  collapsing the language cluster and silently voiding an otherwise valid hreflang set. Added as rule 6 with the
  Search Console symptom ("Duplicate, Google chose different canonical" while hreflang validates cleanly).
  `check_canonical_alignment()` now detects the specific case — canonical matching one of the page's own
  hreflang alternates — and names it, instead of reporting the generic "points to a different URL". The generic
  branch and the passing branch are unchanged.

- **JPEG XL row was stale** (`references/image-seo.md`) — said "Chrome roadmap restored late 2025". Chrome 145
  (Feb 2026) ships a Rust decoder but **behind `chrome://flags`, off by default**; Safari is default-on, Firefox
  is Nightly. The verdict ("not production-ready") was already right; the evidence behind it was not. Chrome's
  default-on is expected H2 2026 but Google has not confirmed its stated conditions are met, so the row says so
  rather than predicting.

- **Thirteen reference files carried "Updated: March 2026"** while three of them had already gained
  August 2026 content in v1.12.0 — the canonical re-evaluation ceiling in `crawl-indexation.md` and the
  AI-citation spam-policy entries in `link-building.md` and `programmatic-seo.md` were sitting under a
  five-month-old header. All 13 refreshed; no reference file now lapses before 2027-02-11.

### Changed

- **`AGENTS.md` §21 Script Toolbox** — the 39-row inventory table (the file's largest section at
  5,119 bytes) is replaced with a pointer to `references/audit-script-matrix.md`. The operating
  rule and the three runnable commands stay inline. Content was **moved, not deleted** — the matrix
  now covers more scripts than the table ever did.

- **Routing Index and Full Detail Reference merged into one table** — two adjacent tables both
  mapping need→file became a single `Goal | Read | Run | Procedure` table, and it now sits at byte
  853 instead of 35,781. This is the structural half of the fix: everything else in `AGENTS.md` is
  recoverable by reading a reference file, but only while the agent can still see the table telling
  it which file to read.

- **README documents Codex's instruction budget** — `project_doc_max_bytes` is a **combined** cap
  across every instruction file Codex loads in the hierarchy, not this file alone, so a user with
  their own root `AGENTS.md` spends the same budget. No amount of self-trimming can guarantee fit;
  the README now says so and gives the `~/.codex/config.toml` override, plus the symptom to watch
  for (Codex acting unaware of §§22–25).

- **Each refreshed file records what its review actually consisted of**, in an HTML comment beside the date, so
  the new timestamp does not overclaim. Eight are marked `corrected` with the specific change. Five —
  `keyword-strategy`, `industry-templates`, `site-migration`, `cite-domain-rating`, `entity-optimization` — are
  marked `verified, no change needed`: they were audited for Google-behaviour claims and externally-sourced
  statistics and contain neither, their numbers being internal rubric thresholds that do not decay. A negative
  result is still a review, but a reader deserves to know which kind they are looking at.
  **September 2025 remains the current Quality Rater Guidelines version** — re-verified, so the E-E-A-T files
  needed no change.

### Added

- **`tests/test_agents_md_size.py`** — four guards, in both trees: the file fits the 32 KiB cap;
  headroom under 512 bytes `xfail`s rather than passing silently (it is currently 42 bytes — known,
  accepted, and documented); the Routing Index stays within the first 4 KB; and every procedure
  file on disk is reachable from `AGENTS.md` with no broken pointers. Validated by reintroducing
  each failure mode in turn and confirming all three are caught.

## [1.12.0] - 2026-08-22

Refresh of the Google-facing guidance against everything Google shipped between the last content
update and 2026-08-22, verified against primary sources (the Search Status Dashboard and
`developers.google.com/search/updates`) rather than third-party reporting. Two internal
contradictions are resolved and a parity test added so they cannot silently return.

### Added

- **Search Generative AI performance reports** (`references/analytics-reporting.md`) — Google launched
  direct measurement of AI Overviews / AI Mode impressions on June 3, 2026. The reference was dated
  March 2026 and still taught that Google AI visibility could only be inferred from proxies. Documents
  what the report does and does not contain (impressions by page/country/device/date; **no** clicks,
  CTR, queries or position), that rollout is partial, and that the AI-features opt-out control is a
  High-Risk deliverable under § 19 rule 11.
  - **No-API warning recorded explicitly.** There is no Search Console API endpoint, no BigQuery
    export, and `searchanalytics.query`'s `type` field is unchanged. Without this stated, the skill
    would confidently invent an API call — a fabrication guard, not a footnote.

- **`scripts/gsc_ai_import.py`** — Ingests the hand-exported generative-AI CSV and normalises it into
  the row shape `gsc_query.py:format_rows()` produces. Manual export is the *only* mechanically
  possible path, so `gsc_query.py` was deliberately **not** extended. Rejects a standard Performance
  export rather than silently mis-reading it, and never synthesises the absent metrics.

- **Preferred sources** (`references/ai-search-geo.md`, new § under Platform-Specific Optimization) —
  Previously zero coverage. The Top Stories carousel went live *inside* AI Overviews on July 17, 2026
  and surfaces the searcher's preferred sources, making this the only AI-answer visibility lever the
  reader controls rather than the ranking system. Covers all three documented integration routes and
  the host-level eligibility rule (`example.com` and `code.example.com` qualify; `example.com/blog`
  does not).

- **`scripts/preferred_sources_checker.py`** — Dependency-free, standard library only, matching
  `faq_parity.py`. Detects the publisher.js tag, the button element, the deeplink and the advanced JS
  API, and reports host-level eligibility. Catches the silent-failure case where the button element is
  present but publisher.js is not loaded. Gated in `generate_report.py` on a publisher schema signal
  (`NewsArticle`/`NewsMediaOrganization`/`LiveBlogPosting`) so it does not fire on every site.

- **`AGENTS.md` § 19 / `19-quality-gates-hard-rules.md` — new rule 10c** — Google's spam policy
  definition was rewritten on May 15, 2026 to cover *"attempting to manipulate generative AI responses
  in Google Search"*, and the June 24 and August 18–21, 2026 spam updates enforced it. Bought or placed
  citations, recommendation-poisoning listicles, and coordinated posting for citation capture are now
  spam. **The carve-out is stated as a test, mirroring rule 10b:** the barred thing is the *stated
  purpose*, not the channel. § 3's Quora, Reddit, YouTube and Wikipedia playbooks remain fully in
  scope; the same action flips to spam when the goal becomes placement rather than usefulness.

- **`tests/test_geo_signal_parity.py`** — 13 tests guarding the llms.txt fixes below across both trees.
  Validated the way `test_schema_status_parity.py` was: each drift reintroduced one at a time and
  confirmed caught (rubric row in either file, report severity re-escalation, and complete removal of
  the checker's disclaimer).

- **Product `category` and sale duration** (July 7, 2026) — `Product.category` (Text *or* CategoryCode)
  and the `priceSpecification` `validFrom`/`validThrough` sale range were absent from the repo entirely.
  Added to `references/procedures/24-ecommerce-seo.md` with markup examples, and validated in
  `scripts/ecommerce_schema.py`. The sale-duration check only fires on markup that actually claims a
  `SalePrice` — a plain price needs no date range.

- **Canonical re-evaluation timeframe** (`references/crawl-indexation.md`, `canonical_checker.py`) —
  Google's canonicalization guide was updated July 10, 2026: re-evaluation can take **up to two weeks**.
  Recorded as the ceiling it is — Google publishes no minimum, median or distribution, so it does not
  support "usually two weeks" or any average-case claim.

- **Social and video platform performance guide** (July 29, 2026) — cross-linked to § Brand Mention
  Channels, which asserted the YouTube/Reddit correlation without naming how the resulting Search
  visibility gets measured.

### Changed

- **llms.txt comes off the GEO scoring rubric** — The prose in `ai-search-geo.md` and
  `03-geo-ai-search.md` already said Google ignores llms.txt (June 2026), while the GEO Health Score
  rubric in **both** files still listed "llms.txt present" as a Technical Accessibility signal, and
  "Create /llms.txt" sat at **#1** under GEO Medium Effort. This is the same doc/code drift 1.11.0
  fixed for schema status: a green `check-plugin-sync.py` proves the trees are *identical*, never that
  either is *correct*. Removed from both rubrics, demoted to last under Medium Effort and labelled
  non-Google-only, and the GEO error-handling row rewritten from "note the absence" to "not a finding
  for Google".

- **Incentivized reviews promoted from EU-UCP framing to a global Google guideline**
  (`24-ecommerce-seo.md`) — the review snippet guideline added July 24, 2026 applies wherever the site
  operates. The rule covers the visible page *and* the structured data. Disclosed incentivized reviews
  remain permitted — the defect is the missing disclosure, so the doc explicitly bars recommending
  deletion of a compliant programme.

- **Algorithm Update Response Protocol** (`analytics-reporting.md`) — added the Aug 18–21, 2026 spam
  update and an AI-manipulation response row; folded the standalone "Helpful Content" row into core,
  where it has belonged since 2024. Added a dated update-history table sourced from the Search Status
  Dashboard, with an explicit instruction not to attribute a drop to an update Google never confirmed.
  **There was no core update in July or August 2026** — the most recent is May 2026 — and several
  third-party trackers claim otherwise.

- **`.gitignore`** — Added `.axme-code/` (AXME agent session data, audit logs and knowledge base — ~681 files regenerated per session) and `.mcp.json` (MCP server wiring pointing at a locally installed binary). Both sat untracked in the repo root and appeared in every `git status`, making accidental inclusion in unrelated commits easy. Neither was ever tracked, so no history is affected. `.cursor/rules/*.md` is deliberately not ignored — those are authored shared agent rules rather than generated state.

- **Retired the "zero-click impressions ⇒ AI Overview presence" proxy** — superseded by direct
  measurement. Retained only for date ranges predating the report's availability on a property.

- **`references/schema-types.md`** — the FAQ Search Console API sunset window (August 2026) is now
  current. Re-checked and still not confirmable against any Google primary source, so the secondary
  attribution stands. Added the actionable part: the documented failure mode is **silent nulls, not an
  error**, so a pipeline that "still runs" is not evidence the data is still arriving.

- **`scripts/llms_txt_checker.py`** — the Google position now travels with the script's own output
  (docstring, human footer, and a `google_search_signal: false` field in JSON), because script output
  is routinely pasted into reports without the surrounding reference docs. The `🔴` critical-failure
  marker was replaced for a file whose absence has no Google Search effect.

### Fixed

- **`scripts/generate_report.py`** — the "No llms.txt found" finding was emitted at `warning`,
  consuming Health Score and reviewer attention for a file Google does not read. Demoted to `info`
  and retitled, with the June 2026 confirmation stated in the finding itself.

- **`README.md` version badge** — stuck at 1.10.2 since the 1.11.0 release; now tracks the current
  version.

- **`references/audit-script-matrix.md`** — review date had lapsed (2026-06-26); refreshed along with
  the two new script registrations.

## [1.11.0] - 2026-08-17

> Supersedes the 1.10.3 version bump, which was raised and then superseded
> within the same day and never tagged. Its entries are folded in below, so
> anything referencing 1.10.3 (PR #17, commit messages) is covered here.

### Added

- **Visible-HTML parity check for FAQ answers** — Flags FAQ answer text that appears in JSON-LD but not in the rendered HTML: the markup satisfies a parser while users and AI crawlers see nothing. A specialisation of `references/procedures/03-geo-ai-search.md` step 4, feeding the Citability dimension of the GEO Score.
  - New dependency-free module `scripts/faq_parity.py`. `validate_schema.py` is regex/json only and must not grow a BeautifulSoup dependency.
  - Comparison is **containment over normalised text**, not equality: tags stripped, entities unescaped (including the `U+00A0` that `&nbsp;` produces), whitespace collapsed, casefolded. JSON-LD `answerText` routinely carries markup the rendered DOM does not.
  - `<script>`/`<style>` contents are stripped before comparison, so JSON-LD cannot trivially "contain" its own answer text.
  - Severity split by what the script can actually know: **High** in `parse_html.py`/`article_seo.py`, which run against fetched pages where absence is a real signal; **`[info]` only** in `validate_schema.py`, gated to `.html`/`.htm`. On `.jsx`/`.tsx`/`.vue`/`.svelte`/`.php`, answer text legitimately lives in props, a `.map()` or a CMS fetch — flagging there would be a false positive on exactly the frameworks the script advertises support for.
  - Answers under 25 normalised characters are skipped; short strings match incidentally and containment would be meaningless.

- **`tests/test_schema_status_parity.py`** — Asserts the script-level schema status sets match the tables in `references/schema-types.md`, that the retired and no-rich-results buckets are mutually exclusive, and that all three scripts agree with each other. `check-plugin-sync.py` verifies the two trees are identical but says nothing about whether either is *correct* — a green sync check sat on top of every bug fixed in 1.10.3. Verified by reintroducing each of those bugs in turn; the new test catches all four.

- **Tests** — 45 new tests; 117 total, up from 72. Of these, 18 regression tests in `tests/test_validate_schema.py` cover the schema status fixes (rich-results-removed types stay `[info]` and never block, `FAQPage` carries no gov/health restriction, `Dataset` never triggers `_is_critical()`, truly retired types still block, and neither bogus practice-problem spelling is flagged) and all 18 fail against the pre-fix code. The remaining 27 cover FAQ visible-HTML parity and doc/code status parity.

### Changed

- **FAQPage comes off the severity ladder** — `references/procedures/05-schema-structured-data.md` step 6 and the `references/schema-types.md` FAQPage row/decision tree no longer say "Info priority", which implied a defect where none exists. Replaced with a routing statement: *not scored for Google rich results; scored under § 3 GEO citability*.
  - The finding is rerouted, not dropped. `procedures/03` previously never mentioned FAQPage, so removing the label alone would have made it vanish. Step 3 now scores FAQ Q&A content as a Citability signal and step 4 covers visible-HTML parity, with cross-references in both directions between `03` and `05`.

- **`AGENTS.md` §19 / `19-quality-gates-hard-rules.md` — new rule 10b** — Rule 10 protects the FAQPage *markup*; 10b protects the *content*. Never recommend deleting or trimming FAQ content **on the grounds that Google withdrew FAQ rich results**. Carve-out is explicit so quality-based pruning still works: § 6 may still cut thin, duplicated or keyword-stuffed FAQ blocks, and `ai-generated-content-artifacts.md` may still flag an answer block that does not stand alone. The test is the stated reason, not the action.

- **Schema status sets hoisted to module level** in `validate_schema.py` (`RETIRED_TYPES`, `NO_RICH_RESULTS_TYPES`) and `parse_html.py` (`DEPRECATED_SCHEMA`, `NO_RICH_RESULTS`) so the parity test can import them. Minimal form of the single-source-of-truth refactor; behaviour unchanged.

- **`references/schema-types.md`** — `Practice Problem` and `Dataset` removed from the RETIRED table (both contradicted the rich-results-removed table above it); `Quiz` and `Dataset` rows added to RICH RESULTS REMOVED; `EnergyConsumptionDetails` added to RETIRED. FAQ tooling-sunset phases (search appearance filter, rich result report, and Rich Results Test in June 2026; Search Console API in August 2026) recorded and **explicitly attributed to secondary reporting** — Google deleted the FAQ documentation on June 15, 2026, so only the May 7, 2026 withdrawal is confirmable against Google's own changelog.

- **`AGENTS.md` §19 and `references/procedures/19-quality-gates-hard-rules.md`** — Retired-schema list no longer lists Practice Problem; Dataset and Quiz notes clarified so docs and scripts agree.

### Fixed

- **Schema status correctness across `validate_schema.py`, `article_seo.py`, `parse_html.py`** — The three scripts hand-maintained schema-status sets that had drifted from each other and from `AGENTS.md` §19, causing the skill to emit recommendations that contradicted its own hard rules. All three now agree.

- **`scripts/validate_schema.py`** — `FAQPage` no longer carries the superseded Aug 2023 "government and healthcare sites only" restriction. Google withdrew FAQ rich results for *all* sites on May 7, 2026, including the gov/health sites that had retained them; the `FAQPage` *type* was never deprecated. It is now reported as `[info]` with keep-the-markup guidance.

- **`scripts/validate_schema.py`** — `Dataset` removed from the `retired` set. Google's November 5, 2025 update *clarified* that Dataset markup is consumed by Dataset Search rather than general Google Search — a scope clarification, not a retirement. Because `_is_critical()` matches the substring `"retired"`, this made the script exit 2 and **hard-block edits on pages carrying valid Dataset markup**.

- **`scripts/article_seo.py`, `scripts/parse_html.py`** — `HowTo` and `FAQPage` moved out of `DEPRECATED_SCHEMA` (which emitted Critical / "Remove deprecated schema type immediately") into a new `NO_RICH_RESULTS` set emitted at Info severity with keep-the-markup guidance. Both prior branches violated `references/procedures/19-quality-gates-hard-rules.md` rule 10.

- **`scripts/article_seo.py`** — Fixed a latent `NameError`: the structured-data extractor referenced `RESTRICTED_SCHEMA` from its own producer block, separate from the consumer branch in `detect_seo_issues`.

- **Practice problem schema type corrected to `Quiz`** — `validate_schema.py` used `"PracticeProblem"` and the other two used `"PracticeProblems"`. Neither is a real schema.org type (both 404); the markup behind Google's retired practice-problem feature is `@type: Quiz`, which remains valid under `LearningResource`. Both dead strings never matched real markup. Now keyed on `Quiz` and treated as rich-results-removed, not retired.

- **`EnergyConsumptionDetails` added to the retired sets** — Documented in `AGENTS.md` and `references/schema-types.md` but present in no script. Confirmed retired April 24, 2025, replaced by the `Certification` type.

## [1.10.2] - 2026-08-12

### Fixed

- **`scripts/robots_checker.py`** — Consecutive User-agent lines now form one group sharing the rules that follow (RFC 9309 sec 2.2.1). Previously only the last agent in a stacked block received the Disallow rule. Also fixed case-sensitive user-agent matching — tokens are now matched case-insensitively per the RFC while preserving original casing for display.

- **`scripts/validate_schema.py`** — JSON-LD extraction regex no longer requires `type` to be the sole attribute on the `<script>` tag. Sites using Yoast (`class="yoast-schema-graph"`), Next.js (`id=`), and Shopify were silently returning no schema. Also fixed: `@graph` members no longer require their own `@context` (they inherit from wrapper per JSON-LD 1.1 §4.9), and the placeholder detector no longer matches articles containing the word "Replace" in ordinary prose.

- **`scripts/link_profile.py`** — Added `validate_url()` to `fetch_page`, closing an SSRF/LFI vector where a malicious sitemap `<loc>file:///etc/passwd</loc>` or `<loc>http://169.254.169.254/...</loc>` entry would be fetched and included in the report.

- **`scripts/redirect_checker.py`** — Added per-hop URL validation in `check_redirects`. Previously followed `Location` headers blindly, allowing an audited host to steer the checker into cloud metadata endpoints via a single 302 redirect.

- **`scripts/drift_monitor.py`** — Fixed tautological severity in rule 3: `"critical" if "noindex" in ... else "critical"` → else branch is now `"warning"`. Benign robots-meta additions (e.g. `max-image-preview:large`) no longer trigger critical alerts.

- **`scripts/hreflang_checker.py`** — Removed "LA" from `COMMON_REGION_MISTAKES`. LA is the valid ISO 3166-1 code for Laos; it was incorrectly mapped to `None` with the comment "Latin America is not a country", breaking all `lo-LA` and `en-LA` hreflang tags.

- **`scripts/entity_checker.py`** — Phone regex `[\+]?[\d\-\(\)\s]{7,15}` matched 7+ whitespace characters as a phone number. Extracted to `has_visible_phone()` with a minimum 7-digit floor.

- **`scripts/backlink_analyzer.py`** — Reports now include `data_source` and `is_sample_data` fields so output from `generate_sample_data()` is clearly labeled rather than being indistinguishable from real backlink profiles.

- **`scripts/readability.py`** — Fallback `sentence_rewrites` contained hardcoded client copy ("Learn practical ethical hacking...") that leaked into unrelated clients' reports. Replaced with domain-neutral placeholder text.

### Added

- **CI: pytest in workflow** — `.github/workflows/validate-plugin.yml` now includes a `tests` job running `pytest tests/ -v` on Python 3.11. `tests/**` and `requirements.txt` added to path triggers. Previously the `tests/` directory existed but nothing executed it.

- **`references/ai-generated-content-artifacts.md`** — New reference for detecting mechanical traces of AI-generated content (unclosed fences, writer-prompt labels, unicode math-bold, heading-dependent openers). Includes severity model separating integrity artifacts from voice/taste, with measured hit rates from a 132-post published corpus.

- **Tests** — 59 new tests across 5 test files: `test_robots_checker.py` (9), `test_fetch_url_validation.py` (13), `test_verified_one_liners.py` (9), `test_validate_schema.py` (17), `test_report_provenance.py` (11).

## [1.10.1] - 2026-08-11

### Added — Methodology Upgrades (M1–M4)

- **M1: 10-Principle Thinking Framework** — New `references/thinking-framework.md` with PERCEIVE → ANALYZE → VALIDATE → ACT methodology. Integrated into `references/procedures/02-full-site-audit.md`. Every Critical/High recommendation now gets: (1) first-principle observation, (2) dependency relationship, (3) falsifiability check, (4) leading indicator.

- **M2: Falsifiability on every recommendation** — Extended Finding format from `Finding/Evidence/Impact/Fix/Confidence` to include **Falsifiability** ("what evidence would prove this wrong?") and **Leading Indicator** ("what metric to monitor post-fix, and over what timeframe"). Updated `AGENTS.md` §2, §19, and `procedures/02-full-site-audit.md`.

- **M3: Dependency-graph action plans** — Mode 2 Action Plans now use topologically sorted dependency sequencing: each action has **Blocked By** and **Unblocks** columns. Parallelizable actions are grouped together. Replaces flat priority lists. Updated `AGENTS.md` §2 (Mode 2 Plan Format) and `procedures/16-strategy-roadmap.md`.

- **M4: Assumptions audit** — Before assembling recommendations, the audit explicitly lists every assumption it relies on (e.g., "homepage represents site quality", "CMS is server-rendered"). Surfaced in a new **Assumptions Audit** section of the report so the user can reject or correct them. Updated `AGENTS.md` §2, §19 (quality gate #12), and `procedures/02-full-site-audit.md`.

### Added — New Feature Modules (F1–F8)

- **F1: SEO Drift Monitoring (§ 22)** — Expanded `scripts/drift_monitor.py` with 17-rule comparison engine across 3 severity levels (6 critical, 7 warning, 4 info), `report` command, and Open Graph + word count tracking. New procedure `references/procedures/22-drift-monitoring.md`. Use cases: pre/post deployment checks, ongoing monitoring, traffic drop investigation, migration validation.

- **F2: Semantic Topic Clustering (§ 23)** — New `scripts/topic_cluster.py` for SERP-overlap-based topic clustering. Clusters keywords by shared top-10 SERP results, generates hub-and-spoke architecture with pillar pages and cluster posts, and produces internal link matrices. Requires SERP data input (DataForSEO extension or manual CSV). New procedure `references/procedures/23-semantic-clustering.md`.

- **F3: Content Brief Generation** — New `scripts/content_brief.py` for structured content briefs from competitor analysis. Covers target keywords, H2/H3 outline, internal links, word count targets, competing pages, schema recommendations, and featured snippet / AI citation opportunities. Updated `references/procedures/07-keywords-clusters-aeo.md`.

- **F4: E-commerce SEO (§ 24)** — New `scripts/ecommerce_schema.py` for Product + Offer schema validation, MerchantReturnPolicy (requires `returnPolicyCountry` since March 2025), OfferShippingDetails, category vs. product page differentiation, faceted navigation, out-of-stock handling, and EU compliance. New procedure `references/procedures/24-ecommerce-seo.md`.

- **F5: Google API Tier System** — New scripts: `scripts/google_api_tier.py` (credential detection), `scripts/crux_history.py` (CrUX History API, Tier 0), `scripts/gsc_query.py` (Google Search Console, Tier 1), `scripts/gsc_export.py` (GSC data export), `scripts/ga4_report.py` (GA4 organic traffic, Tier 2). Auto-detects available credentials and adapts audit depth. Each tier adds data but lower tiers produce valid audits.

- **F6: Expanded MCP Extensions** — Updated `references/optional-extensions-mcp.md` with Ahrefs (backlinks, keyword rankings, content gap), SE Ranking (AI Share-of-Voice, GEO visibility), Profound (LLM citation tracking), and Bing Webmaster (Bing indexation + IndexNow submission) MCP configurations.

- **F7: Maps Intelligence (§ 25)** — New `scripts/maps_checker.py` for geo-grid rank tracking, GBP completeness audit, review intelligence (rating, count, recency, velocity, sentiment), competitor radius mapping, and NAP consistency checking across directories. New procedure `references/procedures/25-maps-intelligence.md`.

- **F8: Professional PDF Reports** — New `scripts/pdf_charts.py` (SVG chart generation) and `scripts/pdf_template.py` (A4 template with cover page + table of contents). Produces presentation-ready PDF reports with health score gauge, category radar chart, and CWV bar charts.

### Changed

- **AGENTS.md** — Added §22 (Drift Monitoring), §23 (Semantic Clustering), §24 (E-commerce SEO), §25 (Maps Intelligence), Google API Tier System table. Updated §1 request detection table with new routing rows. Updated §2 finding format and Mode 2 plan format. Updated §19 quality gates (#12 assumptions, #13 falsifiability, #14 dependency sequencing). Updated §21 script table (+11 scripts).
- **SKILL.md** — Updated routing index with new sections and scripts.
- **Request detection (§ 1)** — New routing rows: SEO Drift, Semantic Clustering, E-commerce SEO, Maps / Advanced Local, Content Brief, Google API Tiers.
- **Audit output template** — Added Assumptions Audit section, First-Principle Observation and Dependency fields for Critical/High findings.
- **Script count** — 35 → 46 bundled audit scripts (+11 new).
- **Plugin bundle** synced — all updated files and 11 new scripts copied to `plugins/ultimate-seo-geo/skills/ultimate-seo-geo/`.

### Fixed

- **`scripts/gsc_export.py`** — Tracked in repo (was present in plugin bundle but missing from root `scripts/`).
- **Plugin sync** — Fixed mismatch between root and plugin script trees.

## [1.10.0] - 2026-08-11

### Changed — Knowledge Currency (10 updates)

- **K1: FAQ rich results retired** — Google retired FAQ rich results for ALL sites on May 7, 2026 (supersedes the Aug 2023 gov/health restriction). FAQPage moved from "Restricted" to "No Google Rich Results" in `schema-types.md`. Decision tree updated: keep existing FAQPage as AI/entity signal (Info priority), do not recommend for Google rich results. Added QAPage to active schema types for genuine user Q&A pages. Updated `AGENTS.md` §5 (removed FAQPage from SaaS essential schema), §19 hard rules, and `procedures/05-schema-structured-data.md`.

- **K2: Google Search ignores llms.txt** — Google confirmed (June 2026) that Search ignores `llms.txt`. Updated `ai-search-geo.md` and `procedures/03-geo-ai-search.md` to reframe as non-Google AI hygiene only, not a Google citation lever. Added hard rule in `AGENTS.md` §19.

- **K3: AI Mode as distinct citation engine** — AI Overviews and AI Mode share only 13.7% URL overlap (Ahrefs, 540K query pairs). Updated `ai-search-geo.md` landscape table and AI Mode section to model them as separate citation engines with distinct optimization surfaces. AI Mode powered by custom Gemini 2.5, 1B+ MAU. Added hard rule in `AGENTS.md` §19.

- **K4: AI Overviews reach 2.5B+ MAU** — Updated AI Overviews reach figure from 1.5B to 2.5B+ users/month (I/O 2026) in `ai-search-geo.md`.

- **K5: Content recency as AI citation lever** — Content under 3 months old receives ~3x AI citation rate (SE Ranking, 2026). Added "Content Recency as Citation Lever" subsection to `ai-search-geo.md` citability signals. Updated AI Mode section. Added key insight in `AGENTS.md` §3 GEO.

- **K6: E-E-A-T scoring weights clarified** — Added explicit disclaimer that E-E-A-T weights (20/25/25/30) are this skill's internal scoring model, not Google's published values. Google publishes no numeric weights, only that "trust is most important." Updated `eeat-framework.md` and `AGENTS.md` §19 hard rules.

- **K7: May 2026 core update + Lighthouse 13.4.0** — Added May 2026 core update (completed May 21) and March 2026 core update to `technical-checklist.md`. Added Lighthouse 13.4.0 section covering Agentic Browsing category and insight-based audits.

- **K8: FID was never in Lighthouse** — Precision fix across all files: Lighthouse is a lab tool and never reported FID; removal was from Chrome's field-data tools (CrUX API, PageSpeed Insights). Updated `AGENTS.md`, `technical-checklist.md`, `procedures/04-technical-seo.md`, and `procedures/19-quality-gates-hard-rules.md`.

- **K9: Back-button hijacking spam policy** — Added as Google spam policy item to `technical-checklist.md` and `procedures/19-quality-gates-hard-rules.md`. Includes detection guidance (history.pushState abuse, popstate redirect loops). Added hard rule in `AGENTS.md` §19.

- **K10: WebMCP origin trial** — Added as emerging standard in `technical-checklist.md`. Chrome 149 origin trial (June 9, 2026), three shipped Lighthouse audits. Not yet required for SEO; monitor as agent-era web development signal.

### Changed

- **Version** bumped to 1.10.0 across SKILL.md, AGENTS.md, README.md, plugin.json, marketplace.json, and plugin README.
- **Review dates** updated on `schema-types.md`, `ai-search-geo.md`, `eeat-framework.md`, and `technical-checklist.md`.
- **Dataset schema** corrected — was listed as "retired/discontinued" but Dataset Search still consumes it. Moved to conditional active status in `schema-types.md`; removed from retired list in `AGENTS.md` §19.
- **Plugin bundle** synced — all 10 updated reference files copied to `plugins/ultimate-seo-geo/skills/ultimate-seo-geo/`.

## [1.9.0] - 2026-05-28

### Added

- **Shared URL safety layer** — `scripts/url_safety.py` centralizes outbound URL validation for audit fetches, blocking private/internal IPs, loopback, link-local ranges, obfuscated IPv4 forms, URL credentials, and unsafe redirect targets.
- **SPA-aware rendering** — `scripts/render_page.py` adds optional Playwright rendering, and `fetch_page.py` / `generate_report.py` now support `--render never|auto|always` for JavaScript-heavy sites.
- **Content quality scanner** — `scripts/content_quality.py` detects deterministic E-E-A-T risks including filler phrasing, citation gaps around statistics/claims, missing author signals, and missing dates.
- **SEO drift monitor** — `scripts/drift_monitor.py` adds SQLite-backed `baseline`, `compare`, and `history` snapshots for SEO-critical elements like title, meta description, canonical, robots, H1, schema hash, headings hash, and internal link count.
- **Regression tests** — Added focused `unittest` coverage for URL safety, render detection, redirect safety, recommendation metadata, content-quality scoring, and drift snapshot extraction.

### Changed

- **`scripts/crawl_adapter.py`** — Routes requests, Firecrawl, and Playwright fetching through the shared URL safety layer and preserves rendered-page metadata.
- **`scripts/generate_report.py`** — Adds content quality into the report pipeline and renders falsifiable recommendation metadata: dependency, failure check, and leading indicator.
- **Plugin bundle** — Root scripts and plugin-bundled scripts now include the new safety, rendering, content-quality, and drift-monitoring tools.

## [1.8.5] - 2026-04-11

### Added

- **`scripts/generate_report.py`** — `--crawl-deep`, `--crawl-max-pages`, `--crawl-depth` to run multi-page `broken_links` and `canonical_checker` crawls (capped; longer script timeouts).
- **`scripts/parse_html.py`** — `og:description` fallback with `meta_description_source`; duplicate `<title>`, duplicate `meta name="description"`, and duplicate `rel=canonical` findings; multi-H1 info note; canonical `rel` parsing when `rel` is a list.
- **HTML report** — Raw-HTML disclaimer for Next.js/Nuxt/JS-heavy stacks; on-page canonical filled from canonical audit when HTML has no `<link rel="canonical">`; labels for og-description fallback and audit-filled canonical.

### Changed

- **`scripts/canonical_checker.py`** — Treat canonical sent only via HTTP `Link: ...; rel="canonical"` as present (with warning to add HTML `<link>` for parity).
- **`AGENTS.md`** — GEO vs traditional robots.txt: scope “remove Disallow” to AI crawlers; do not recommend removing Googlebot facet/category disallows unless the user asks for crawl-budget review.
- **`SKILL.md`** — Routing row for content relevance + GEO (procedures 03 + 06, `article_seo`, `readability`, `internal_links`).
- **`README.md`**, **`.claude-plugin/marketplace.json`**, **`plugin.json`** — Audience, default vs deep crawl scope, marketplace descriptions.

## [1.8.4] - 2026-04-06

### Added

- **`references/optional-extensions-mcp.md`** — Optional Firecrawl / DataForSEO MCP setup for plugin installs that do not include the monorepo `extensions/` tree; `AGENTS.md` Extensions row now points here.
- **`scripts/generate_report.py --format pdf`** — PDF export via optional **WeasyPrint** (`pip install weasyprint`; OS libraries may be required). Documented in `references/procedures/21-script-toolbox.md` and `AGENTS.md` with HTML + browser print-to-PDF fallback.
- **Plugin bundle: `agents/`** — `setup-plugin.sh` now copies `agents/*.md` into `plugins/.../skills/.../agents/` so `agents/PARALLEL-AUDIT.md` resolves in Claude Code installs. **`scripts/check-plugin-sync.py`** validates root vs plugin `agents/` parity.
- **`requirements.txt`** — Comment block for optional `weasyprint`.

### Changed

- **`extensions/README.md`** — Points to `references/optional-extensions-mcp.md` for the skill/plugin copy.
- **`.github/workflows/validate-plugin.yml`** — Triggers on `agents/**` changes.
- **Marketplace / `plugin.json`** — Descriptions and keywords (`mcp`, `pdf`, `parallel-agents`) updated for the gaps above.

## [1.8.3] - 2026-04-03

### Changed

- **`SKILL.md`** — Refactored into a **routing shell** (~230 lines): §0, global guardrails, and an index to `references/procedures/*.md`. Detailed procedures for former §1–§21 moved verbatim into `references/procedures/` (22 files + `README.md`) for progressive disclosure and lower default context size when the host loads the skill.
- **`AGENTS.md`**, **`GEMINI.md`**, **`.github/copilot-instructions.md`** — Pointers updated to `references/procedures/` instead of monolithic `SKILL.md` sections.
- **`agents/`** — Replaced six per-agent markdown files with **`agents/PARALLEL-AUDIT.md`** + shorter **`agents/README.md`**.
- **`chatgpt/copy-knowledge-files.sh`** — Also copies `references/procedures/*.md` into `chatgpt/knowledge/procedures/` for Custom GPT uploads.
- **Version** — `1.8.3` in `SKILL.md`, `AGENTS.md`, `plugin.json`, and marketplace catalog.

## [1.8.2] - 2026-04-03

### Fixed

- **`scripts/robots_checker.py`** — Added `OAI-SearchBot` (ChatGPT Search indexing crawler) to `AI_CRAWLERS` list with inline comment distinguishing it from `GPTBot` (training-only). Every GEO audit that checks robots.txt now correctly detects whether ChatGPT Search can index the site. Previously, a site blocking `OAI-SearchBot` would pass the AI crawler check undetected.
- **`scripts/pagespeed.py`** — Critical: the entire response-processing block (performance score, CrUX field data, opportunities, diagnostics — ~100 lines) was inside the `for` retry loop body *after* the `break` statement, making it completely unreachable. The script fetched the PSI API successfully but always returned empty metrics `{}`. Fixed by initializing `data = None` before the loop and moving extraction to function scope after the loop. CrUX distribution buckets (% good / needs-improvement / poor per metric) and a `"source": "field"/"lab"` tag are now also surfaced in the output.
- **`scripts/hreflang_checker.py`** — Stale internal path in docstring (`resources/skills/seo-hreflang.md` → `references/international-seo.md`).
- **`scripts/image_checker.py`** — Expanded from alt-text-only to full image SEO check: added `fetchpriority="high"` detection on first/LCP image (critical severity if missing on lazy-loaded hero), `srcset`/`sizes` coverage, `width`/`height` dimension attributes (CLS prevention), and WebP format detection. Also fixed missing-alt finding not being emitted (counter populated but `issues.append` dropped in prior refactor).
- **`scripts/run_individual_checks.sh`** — Added `canonical_checker.py`, `site_mapper.py`, and `programmatic_seo_auditor.py` which existed but were missing from the runner.
- **`references/audit-script-matrix.md`** — Added `site_mapper.py`, `crawl_adapter.py`, and `backlink_analyzer.py` to the Utilities table; all three are user-facing tools mentioned in AGENTS.md but absent from the matrix.
- **`scripts/backlink_analyzer.py`** — Documented CSV column mapping in docstring (field name variants for Ahrefs/Moz/Semrush exports were handled by `normalize_backlinks` but never documented).
- **`AGENTS.md`** — Version synced to match `SKILL.md` (was 1.8.0 while SKILL.md was already 1.8.1).

## [1.8.1] - 2026-04-01

### Added

- **Functional page exemption** — Sign up, sign in, log in, register, create account, forgot/reset password, membership enroll, checkout, cart, account dashboard, profile settings pages are now explicitly excluded from thin-content checks and word-count floors. Audit rule table added to `SKILL.md` § 6 and `AGENTS.md` § 6. Relevant checks for these pages: title accuracy, meta description, form labels, trust signals, schema.
- **Eval 15** — Regression test: auditing `/signup` and `/login` pages must not flag thin content or recommend adding copy. 3 assertions.

### Changed

- **`SKILL.md` § 6** — Added "Functional Page Exemption" table before the Content Audit step-by-step. Classifies functional pages (task UI), landing/marketing pages, and content pages with clear audit rules per type.
- **`AGENTS.md` § 6** — Prepended functional page exemption notice with page-type list and applicable checks.

## [1.8.0] - 2026-04-01

### Added

- **`scripts/backlink_analyzer.py`** — 7-section backlink analysis with CSV/API data adapter. Profile overview, anchor text distribution, referring domain quality, toxic link detection (22 patterns, 2 risk tiers), top pages, competitor gap analysis, and velocity placeholder. Backlink Health Score (0-100) with weighted composite. Supports `--source csv|gsc|sample`.
- **`scripts/crawl_adapter.py`** — Pluggable crawl backend abstraction. Supports `requests` (default, stdlib), `firecrawl` (optional, via API key), and `playwright` (optional, local install). Auto-detection selects best available backend. Used by other scripts via import.
- **`scripts/site_mapper.py`** — Fast URL discovery via sitemap parsing + BFS internal link crawl. Supports `--max-pages`, `--depth`, `--include-status`. Uses `crawl_adapter.py` for all fetching.
- **`references/backlink-quality.md`** — 30 toxic link patterns, anchor text benchmarks, health score formula, disavow file format, competitor gap analysis methodology.
- **`generate_report.py --format xlsx|all`** — Excel export with openpyxl. Sheets: Summary, Issues, Links, Technical. Navy header styling, frozen headers, auto-filter, auto-column-width. `--format all` generates HTML + XLSX together.
- **`extensions/` directory** — Platform-neutral extension architecture. Each extension has `extension.json` manifest + install adapters for Claude Code, Cursor, and generic (env vars). Two extensions: Firecrawl (JS-rendered crawling) and DataForSEO (live SERP/backlink data).
- **`agents/` directory** — 6 subagent capability definitions (seo-technical, seo-content, seo-schema, seo-geo, seo-performance, seo-links). Platform-neutral markdown format — each platform interprets natively.
- **LLM-agnostic agent identity** — AGENTS.md, SKILL.md, README.md updated to reflect multi-platform support. Platforms row added to header tables. Descriptions reframed from "skill" to "agent."

### Changed

- **User-Agent strings** — All 20 scripts updated from `SEOSkill/*` and `ClaudeSEO/*` to `UltimateSEO/*` with project homepage URL.
- **AGENTS.md routing index** — Added backlinks, URL discovery, and extensions rows.
- **AGENTS.md script table** — Added `backlink_analyzer.py`, `crawl_adapter.py`, `site_mapper.py`. Updated `generate_report.py` description to mention XLSX.
- **AGENTS.md section 21** — Added Excel export usage, extensions table, and subagent definitions table.
- **`requirements.txt`** — Added `openpyxl>=3.1.0` as commented optional dependency.

## [1.7.2] - 2026-03-31

### Changed

- **SKILL.md** — Strengthen robots.txt High-Risk gate: withhold file/code until user confirms. Add context-budget awareness section to § 0 (graceful degradation for fast models). Add Quality Gate criterion 11 for High-Risk deliverable withholding check.
- **Evals** — 3 new discriminating GEO assertions (eval 12), 5 assertion fixes across evals (regex precision, subtype broadening, hyphenated deindex variant). Total: 14 prompts, 60 assertions.

### Fixed

- **README** — Version badge updated to 1.7.2; eval assertion count corrected to 60.

## [1.7.1] - 2026-03-30

### Added

- **Eval 13 — Execute mode risk gate** — Negative test: user requests blocking all crawlers via robots.txt. Verifies the skill warns about deindexing, classifies the change as high-risk, and asks for explicit confirmation before producing the file. 4 assertions.
- **Eval 14 — Evaluator-Optimizer fabrication check** — User requests CWV scores for example.com with no pagespeed.py data available. Verifies the skill does NOT fabricate LCP/INP/CLS numbers and instead states data is unavailable. Tests §19 criterion 2. 4 assertions.
- **Competitive mode output example** (`references/audit-output-example.md`) — Full "External Observation Only" example with no /100 Health Score, showing correct labeling and scope constraints for external site observations.
- **GEO-only audit output example** (`references/audit-output-example.md`) — Complete GEO Quick Check table, GEO Score breakdown by dimension, AI citation findings, and before/after citation demonstration for a scoped GEO request.

### Fixed

- **README version badge** — Updated from stale `v1.2.1` to current version (was 5 major versions behind).
- **README eval counts** — Updated from "12 prompts, 49 assertions" to "14 prompts, 57 assertions" in Eval Results section, architecture file tree, and test scenario description.

## [1.7.0] - 2026-03-30

### Added

- **§ 3 GEO — RSL 1.0** — Added check for RSL 1.0 (Really Simple Licensing), the December 2025 standard backed by Reddit, Yahoo, Medium, Quora, Cloudflare, Akamai, and Creative Commons. GEO Audit step 2 now includes `/rsl.txt` and RSL meta tag verification alongside llms.txt.
- **§ 4 Technical — AI crawler distinctions** — Added explicit guidance on `Google-Extended` (blocks Gemini training only, not Google Search or AI Overviews) and `GPTBot` vs `ChatGPT-User` (blocking GPTBot does not block ChatGPT Search citations). Common misconfiguration that silently removes sites from ChatGPT live search.
- **§ 6 Content — Word count caveat** — Clarified that word count minimums are topical coverage floors, not targets. Google confirmed word count is not a direct ranking factor.
- **§ 6 Content — Google AI Mode** — Added to Key Policy Updates table: AI Mode (May 2025, 180+ countries) delivers zero blue links; AI citation is the only visibility mechanism.
- **§ 8 Competitors — Comparison page title formulas** — Added proven title formulas for X vs Y, alternatives, and roundup pages. Added `ItemList` schema recommendation for roundup pages.
- **§ 11 Crawl — Sitemap tag note** — Added that `<priority>` and `<changefreq>` tags are ignored by Google and Bing; omit from new sitemaps.
- **§ 13 Images — `decoding="async"`** — Added `decoding="async"` guidance for non-LCP images to prevent image decoding from blocking the main thread.
- **§ 13 Images — JPEG XL** — Added note that Chrome reversed its 2022 removal decision in November 2025 (Rust-based decoder); not yet in stable, ~20% lossless savings over JPEG.
- **§ 14 Hreflang — 3-method comparison** — Added implementation method comparison table (HTML link tags vs HTTP headers vs XML sitemap), sitemap hreflang XML format, and cross-domain setup guidance.
- **§ 15 Programmatic — Enforcement timeline** — Added Scaled Content Abuse enforcement dates: November 2024 site reputation abuse, June 2025 manual actions wave, August 2025 SpamBrain update, 45% low-quality content reduction statistic, progressive rollout rule (50–100 page batches).
- **§ 21 Scripts — DataForSEO MCP** — Added optional DataForSEO MCP integration table covering GEO visibility checks, on-page analysis, competitive intelligence, keyword research, and live SERP data.

## [1.6.2] - 2026-03-30

### Performance

- **`generate_report.py`: parallel script execution** — All analysis scripts (17–20 depending on HTML fetch) now run concurrently via `ThreadPoolExecutor` (max 8 workers) instead of sequentially. Wall-clock time for a full audit drops from sum-of-all-scripts to max-of-any-script — typically a 3–6× speedup on real sites where each script spends most of its time waiting on network I/O. Profiling showed startup overhead (`requests` + `bs4` imports) was stacking at ~140–180ms per script × 20 scripts = ~3s of dead import time alone.
- **`entity_checker.py`: parallel Wikidata + Wikipedia lookups** — `check_wikidata()` and `check_wikipedia()` were called serially (each with an 8s timeout). They now run concurrently via `ThreadPoolExecutor(max_workers=2)`, cutting entity check I/O wait time roughly in half.
- **`score_eval_transcript.py`: pre-compiled regex patterns** — Regex patterns in `evals.json` assertions are now compiled once at load time (`_compile_assertions`) and stored as `_compiled` on each assertion object. `check_assertion` uses the pre-compiled object directly, eliminating per-call compilation overhead. This matters most in long-running eval sessions scoring many transcripts.

## [1.6.1] - 2026-03-30

### Fixed

- **CI: `check_version_sync.py` excluded from plugin bundle sync check** — Added `check_version_sync.py` to `SCRIPT_EXCLUDE` in `scripts/check-plugin-sync.py` and to `SCRIPT_EXCLUDE_LIST` in `setup-plugin.sh`. This maintainer-only CI script was incorrectly being compared against the plugin bundle, causing the "scripts/*.py list mismatch" CI failure introduced in v1.6.0.

## [1.5.6] - 2026-03-27

### Added

- **Evaluator-Optimizer self-review pass (§19)** — Mandatory 7-criterion internal evaluation table Claude runs after generating any Mode 1 audit output, before delivering it: checks Evidence presence on Critical/High findings, no fabricated metrics, Health Score justification, structured format, no duplicates, scope label, and actionable fix directives. Adapted from Anthropic's Evaluator-Optimizer pattern (`claude-cookbooks/patterns/agents`).
- **Progressive Disclosure hard rule (§0)** — Explicit "load at most 3 reference files per response" rule with reasoning, linked to Anthropic's Skills progressive disclosure architecture. Prevents unnecessary context bloat on single-topic requests.
- **Orchestrator-Workers pattern (§21)** — Formal ASCII diagram showing how to delegate independent scripts as worker nodes and synthesize in the main thread. Includes hard constraint: never run `generate_report.py` + individual scripts for the same URL simultaneously.
- **Context compaction guidance (§21)** — Step-by-step instructions for managing long audit sessions when context fills: compact findings to one-line format, checkpoint score, continue, merge at end. Adapted from Anthropic's session memory compaction pattern.
- **Citation demonstration pattern (§3 GEO)** — "Before/After" citation rewrite block added to GEO section. Audits now produce a concrete example of what an AI-quotable passage from the user's content would look like, not just a score. Adapted from Anthropic's Citations cookbook.
- **Attribution row** for `anthropics/claude-cookbooks` added to §21 Attribution table.

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
