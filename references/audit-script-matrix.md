<!-- Updated: 2026-08-22 | Review: 2027-02-22 -->

# Audit steps ↔ diagnostic scripts

Each major automated check has a **script** you can run alone (usually with `--json`). The full-site dashboard runs the **bundled pipeline** in `scripts/generate_report.py`, which executes the same tools in one pass.

| Audit area | SKILL § | Script | CLI example |
|------------|---------|--------|-------------|
| Full bundled report | §2, §21 | `generate_report.py` | `python scripts/generate_report.py https://example.com -o report.html` |
| CI gate on the full report (JSON summary, exit codes) | §21, §22 | `generate_report.py` | `python scripts/generate_report.py URL --format none --json summary.json --fail-under 70 --fail-on critical` |
| Monthly re-run with the delta since last time | §21 | `generate_report.py` | `python scripts/generate_report.py URL --json summary.json --previous last-month.json` |
| Robots.txt + AI crawlers | §4, §3 | `robots_checker.py` | `python scripts/robots_checker.py URL --json` |
| AI crawler access through firewalls / CDNs (suspected blocks) | §3, §4 | `ai_bot_access.py` | `python scripts/ai_bot_access.py URL --json` |
| AI crawler visits in server logs (verified against published IP ranges) | §3, §11 | `ai_bot_logs.py` | `python scripts/ai_bot_logs.py access.log --verify-ips --json` |
| AI citation rates from repeated runs (95% intervals; no API calls) | §3, §8 | `citation_sampling.py` | `python scripts/citation_sampling.py runs.csv --domain example.com --json` |
| Hidden instructions to AI systems (prompt injection, invisible Unicode) | §3, §4 | `hidden_instructions.py` | `python scripts/hidden_instructions.py URL --json` (a saved HTML file also works) |
| Security headers | §4 | `security_headers.py` | `python scripts/security_headers.py URL --json` |
| Open Graph / Twitter | §4 | `social_meta.py` | `python scripts/social_meta.py URL --json` |
| Redirect chains | §4, §20 | `redirect_checker.py` | `python scripts/redirect_checker.py URL --json` |
| llms.txt (non-Google engines; Google ignores it) | §3 | `llms_txt_checker.py` | `python scripts/llms_txt_checker.py URL --json` |
| llms.txt links vs sitemap (stale / dead links; informational) | §3 | `llms_txt_checker.py` | `python scripts/llms_txt_checker.py URL --check-sitemap --json` |
| Preferred sources opt-in (publishers) | §3 | `preferred_sources_checker.py` | `python scripts/preferred_sources_checker.py URL --json` |
| GSC generative-AI impressions (manual CSV) | §10 | `gsc_ai_import.py` | `python scripts/gsc_ai_import.py export.csv --json` |
| Broken links (single page) | §9 | `broken_links.py` | `python scripts/broken_links.py URL --json` |
| Broken links (site-wide) | §9, §11 | `broken_links.py` | `python scripts/broken_links.py URL --crawl --depth 2 --json` |
| Internal links / redirects | §9, §11 | `internal_links.py` | `python scripts/internal_links.py URL --depth 1 --json` |
| Anchor text per destination (in-content links only; vague anchors) | §9 | `internal_links.py` | `python scripts/internal_links.py URL --graph site_graph.json --json` (graph from `site_graph.py URL --out site_graph.json`) |
| Core Web Vitals (PSI) | §4 | `pagespeed.py` | `python scripts/pagespeed.py URL --strategy mobile --json` |
| Entity / Wikidata | §3 | `entity_checker.py` | `python scripts/entity_checker.py URL --json` |
| Citability and structure (prose walls, paragraph length, headings, lead; article pages) | §3 | `citability_checker.py` | `python scripts/citability_checker.py --url URL --json` (or a saved HTML file) |
| Link equity / graph / orphans (complete crawls only; otherwise `inconclusive`) | §9, §11 | `link_profile.py` | `python scripts/link_profile.py URL --json` |
| Hreflang | §14 | `hreflang_checker.py` | `python scripts/hreflang_checker.py URL --json` |
| Near-duplicate / thin + canonical | §6, §11 | `duplicate_content.py` | `python scripts/duplicate_content.py URL --json` |
| Canonical validation + alternate detection | §4, §11 | `canonical_checker.py` | `python scripts/canonical_checker.py URL --json` (single) / `--crawl --json` (site-wide, detects alternate pages) |
| Sitemap + URL health | §11 | `sitemap_checker.py` | `python scripts/sitemap_checker.py URL --sample 50 --json` |
| Sitemap lastmod plausibility (coverage, invalid / future / one-date-everywhere, 20-page comparison with the pages' own modified dates) | §11 | `sitemap_checker.py` | `python scripts/sitemap_checker.py URL --lastmod --json` (`--no-page-dates` skips the page fetches) |
| Sitemap structure (index layout, per-section children, file sizes, duplicates, foreign hosts, http entries) | §11 | `sitemap_checker.py` | `python scripts/sitemap_checker.py URL --structure --json` |
| Page indexing week over week (two GSC exports: reasons that moved, technical vs quality vs discovery, one to investigate) | §11 | `index_coverage_diff.py` | `python scripts/index_coverage_diff.py last-week.zip this-week.zip --shipped shipped.txt --json` (`--examples OLD NEW --sitemap URL` for one reason's URLs) |
| Sitemap vs crawl reconciliation (unlisted indexable pages; listed noindex / redirect / canonicalised / 404 URLs; orphans after a complete crawl) | §11, §9 | `sitemap_checker.py` | `python scripts/sitemap_checker.py URL --reconcile site_graph.json --json` |
| Local surface signals | §12 | `local_signals_checker.py` | `python scripts/local_signals_checker.py URL --json` |
| IndexNow (full key validation) | §4 | `indexnow_checker.py` | `python scripts/indexnow_checker.py URL --key KEY --json` |
| IndexNow (probe, no key) | §4 | `indexnow_checker.py` | `python scripts/indexnow_checker.py URL --probe --json` |
| On-page extract | §2, §4 | `parse_html.py` | `python scripts/parse_html.py file.html --url URL --json` |
| Title / meta / H1 lengths | §2 | `meta_lengths_checker.py` | `python scripts/meta_lengths_checker.py --url URL --json` |
| Readability | §6 | `readability.py` | `python scripts/readability.py file.html --json` |
| Article / CMS patterns | §6 | `article_seo.py` | `python scripts/article_seo.py URL --json` |
| JSON-LD validation | §5 | `validate_schema.py` | `python scripts/validate_schema.py file.html --json` |
| Image alt coverage | §13 | `image_checker.py` | `python scripts/image_checker.py page.html --base-url URL --json` |
| Site architecture (sections by directory, link equity by section on complete crawls, hubs, sections outside the navigation, URL hygiene, Mermaid tree; display-only) | §2, §9, §11 | `site_architecture.py` | `python scripts/site_architecture.py URL --graph site_graph.json --json` (or without `--graph` to crawl 80 pages) |
| Global navigation, footer and breadcrumbs (money pages reachable from nav, broken/redirected nav links, footer link dump, breadcrumb vs BreadcrumbList; display-only) | §2, §9, §11 | `navigation_checker.py` | `python scripts/navigation_checker.py URL --graph site_graph.json --json` (or without `--graph` to crawl a 40-page sample) |
| Page-type coverage (content-type matrix, missing comparison / alternatives / use-case pages; display-only) | §2, §3, §7 | `page_type_classifier.py` | `python scripts/page_type_classifier.py URL --graph site_graph.json --json` (or without `--graph` to crawl 80 pages) |
| Programmatic SEO audit | §15 | `programmatic_seo_auditor.py` | `python scripts/programmatic_seo_auditor.py URL --depth 2 --max-pages 100 --json` |
| Content quality signals | §6 | `content_quality.py` | `python scripts/content_quality.py URL --json` |
| Content brief generation | §7 | `content_brief.py` | `python scripts/content_brief.py "target keyword" --json` |
| Topic clustering (SERP overlap) | §23 | `topic_cluster.py` | `python scripts/topic_cluster.py --input serp_data.csv --format serp_overlap --json` |
| E-commerce schema (Product/Offer) | §24 | `ecommerce_schema.py` | `python scripts/ecommerce_schema.py URL --json` |
| Maps / GBP intelligence | §25 | `maps_checker.py` | `python scripts/maps_checker.py URL --json` |
| Core Web Vitals history (CrUX) | §4 | `crux_history.py` | `python scripts/crux_history.py URL --metric lcp --json` |
| SEO drift baseline / compare | §22 | `drift_monitor.py` | `python scripts/drift_monitor.py baseline URL` then `compare URL` |
| Search Console sign-in (Tier 1) | §10 | `google_auth.py` | `python3 scripts/google_auth.py setup` once, then `python3 scripts/google_auth.py login` (browser, read-only; `status`, `logout`) |
| GSC performance query (Tier 1) | §10 | `gsc_query.py` | `python scripts/gsc_query.py sc-domain:example.com --dimension page --json` (site URL is positional, not a flag; page rows are merged across `#fragment` URLs, `--keep-fragments` for raw) |
| GSC opportunities: striking distance, low CTR vs the site's own curve, cannibalisation, decay, serve map (Tier 1) | §10, §6 | `gsc_insights.py` | `python scripts/gsc_insights.py sc-domain:example.com --all --json` (`--human-basis` blended vs human-only; machine queries set aside unless `--include-machine`; `--serve-map targets.csv`; `--save-rows`/`--replay` to analyse without re-fetching) |
| GSC URL inspection export (Tier 1) | §10 | `gsc_export.py` | `python scripts/gsc_export.py --property SITE --sitemap-url URL` |
| GSC generative-AI impressions (manual CSV) | §10 | `gsc_ai_import.py` | `python scripts/gsc_ai_import.py export.csv --json` |
| GA4 organic reporting (Tier 2) | §10 | `ga4_report.py` | `python scripts/ga4_report.py --property 123456789 --organic-only --json` |
| GA4 AI assistant referrals (a floor; untagged clicks read as Direct) | §10, §3 | `ga4_report.py` | `python scripts/ga4_report.py --property 123456789 --ai-referrals --json` |
| Written report vs § 2 contract (fields, severities, score vs summary, unmeasured metrics, one `Next action:`, unsourced traffic figures and forecasts) | §2, §19 | `report_lint.py` | `python scripts/report_lint.py report.md --summary summary.json --json` (`--excerpt` for partial reports) |
| Finding deduplication | §2 | `finding_verifier.py` | `python scripts/finding_verifier.py --findings-json references/finding-verifier-example.json --json` (see `references/finding-verifier-context-example.json` for optional `--context-json`) |

## Utilities (supporting tools)

| Script | Role |
|--------|------|
| `requirements-check.py` | Preflight: verify `requests` + `beautifulsoup4` (`python scripts/requirements-check.py --json`) |
| `site_mapper.py` | URL discovery via sitemap + BFS crawl (`python scripts/site_mapper.py URL --max-pages 100 --json`) |
| `site_graph.py` | One crawl, saved for reuse: sitemap with `lastmod`, BFS link graph, every link tagged with its page region (header / nav / footer / breadcrumb / aside / main), URL decomposition, and an explicit `crawl.complete` / `sitemap.complete` verdict (`python scripts/site_graph.py URL --max-pages 100 --depth 3 --out site_graph.json`) |
| `render_report.py` | Render the client report, one `report.html` (summary, audit, strategy, plan, folded appendix), from a report source; folds in `generate_report.py --json`, `site_graph.py` and the structure-check outputs (`python scripts/render_report.py source.json --out reports/ --summary summary.json --graph site_graph.json --structure structure/`); `--catalogue components.html` writes the component catalogue |
| `report_data_lint.py` | Lint a report source against `references/report-template/report-template.md` § 10: fields and scales, orphan IDs, blocked-by cycles, display-only never scored, absence claims only from a complete inventory (`python scripts/report_data_lint.py source.json --json`) |
| `crawl_adapter.py` | Pluggable fetch backend (urllib / Firecrawl / Playwright) — called internally by other scripts |
| `backlink_analyzer.py` | 7-section backlink report from CSV exports (Ahrefs, Moz, Semrush) or built-in sample data (`python scripts/backlink_analyzer.py --source csv --input links.csv --json`) |
| `score_eval_transcript.py` | Score a saved model reply vs `evals/evals.json` (`--eval-id N` or `--all-fixtures`; `report_lint` assertions check the § 2 report contract, `--summary` checks the score) |
| `fetch_page.py` | Fetch HTML to disk for manual inspection |
| `render_page.py` | Render a page with Playwright (JS-heavy sites) so client-rendered content is visible to the other checkers |
| `google_api_tier.py` | Report which Google API tier is available from configured credentials (`python scripts/google_api_tier.py --check`) |
| `check-plugin-sync.py` | CI / release: verify plugin bundle matches repo root |

## Reference-only areas (no dedicated `.py` checker)

LLM + checklist work uses these references; there is **no separate script** by design:

| Area | SKILL § | Reference |
|------|---------|-----------|
| Keyword / topic strategy | §7 | `references/keyword-strategy.md` |
| Analytics / GSC / GA4 | §10 | `references/analytics-reporting.md` |
| AI search narrative / GEO | §3 | `references/ai-search-geo.md` |
| CORE-EEAT scoring | §6 | `references/core-eeat-framework.md` |
| CITE domain rating | §6 | `references/cite-domain-rating.md` |
| Entity optimization depth | §3 | `references/entity-optimization.md` |

## Eval / QA

- Spec: `evals/evals.json` (**16** scenarios, **69** assertions including negative PPC).  
- Golden transcripts: `evals/fixtures/eval*_pass.txt` — run `python scripts/score_eval_transcript.py --all-fixtures` (exit `0` if all pass).  
- Report contract: a `report_lint` assertion (eval 1) runs the written report through `report_lint.py` and passes only with zero errors; `"strict": true` also fails on warnings, `"excerpt": true` skips required sections. Text before the report title is ignored. Pass `--summary summary.json` to check the score against a real `generate_report.py` run: `python scripts/score_eval_transcript.py --eval-id 1 --text-file transcript.txt --summary summary.json`.

## Progressive checks

0. **Dependencies:** `python scripts/requirements-check.py` (or `--json`) before URL-based audits.  
1. **Fast baseline:** `generate_report.py` (one command, all wired checks).  
2. **Deep dive:** run any row’s script alone for that dimension.  
3. **Schema after edits:** `validate_schema.py` on saved HTML.  
4. **IndexNow with key:** use `--key` when you have an IndexNow key (probe mode is keyless).  
5. **Regression:** after SKILL changes, `score_eval_transcript.py --all-fixtures` on saved replies.
