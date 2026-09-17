> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

## 26. Site Structure and Content-Type Coverage

What the site *is made of* and how it is *held together*: which page types exist (comparison, alternatives, pricing, solutions, persona, industry, glossary, docs, …), whether the ones a site of this kind needs are present, what the global navigation and footer actually link to, how link equity spreads across sections, and whether the sitemap tells the truth about the crawl.

All of it is **display-only**: nothing in this section moves the Health Score (v1.14.0 contract). Findings carry the standard Finding / Evidence / Impact / Fix / Confidence fields and are tagged `opportunity` where they describe pages to create rather than defects to fix.

### When to run it

| Trigger | Run |
|---|---|
| Full Mode 1 audit | `generate_report.py` runs all four automatically (one shared crawl of 80 pages) |
| "What content are we missing?", "do we have comparison pages?", GEO content planning | `page_type_classifier.py` |
| "Is X reachable from the nav?", footer bloat, breadcrumb rich results | `navigation_checker.py` |
| "Which sections get the link equity?", hub pages, site architecture review, IA redesign | `site_architecture.py` |
| Sitemap freshness, sitemap vs crawl, "Indexed, not submitted in sitemap" in Search Console | `sitemap_checker.py --lastmod --structure --reconcile` |

### Procedure

1. **Build the graph once.** `python scripts/site_graph.py URL --max-pages 200 --depth 3 --out site_graph.json`. Read `crawl.complete` and `sitemap.complete` in the output: they decide which claims below are allowed. Raise `--max-pages` above the site's page count when you need a complete crawl (equity, orphans).
2. **Classify.** `python scripts/page_type_classifier.py URL --graph site_graph.json --json`. Read `site_type` (override with `--site-type` if wrong), the `matrix` by label, `by_intent`, and `issues`. A `missing_page_type` finding is only made from a complete inventory; otherwise you get one `coverage_inconclusive` finding listing what was not seen. Over 40% `generic` means the site's URL scheme needs `--rules` (see `references/page-types.md`).
3. **Navigation.** `python scripts/navigation_checker.py URL --graph site_graph.json --json`. `status: not_measured` means the raw HTML has fewer than three landmark links (JavaScript navigation): report it as not measured, confirm with `render_page.py`, and do **not** say the site has no navigation. `taxonomy.sections` is the top-level structure the nav defines.
4. **Architecture.** `python scripts/site_architecture.py URL --graph site_graph.json --json`. `sections` gives size, dominant type, nav reach, hub, depth and equity share per section; `equity.status` is `measured` only on a complete crawl of at least 10 pages covering 80% of the sitemap. The `mermaid` field renders the tree in the report.
5. **Sitemap.** `python scripts/sitemap_checker.py URL --lastmod --structure --reconcile site_graph.json --json`. `--no-page-dates` skips the 20 page fetches. The `sitemap_unreached_by_crawl` bucket is `inconclusive` unless the crawl was complete.
6. **Write it up.** Group the findings under the report categories they belong to (page types → Content quality / E-E-A-T; navigation and architecture → Link authority; sitemap → Technical SEO). Missing page types go in **Opportunity Signals**, not the severity buckets, unless the site type makes them a gap (a SaaS site with no pricing page). Turn each into a Mode 2 plan row: the fix directive names the URL pattern to create or the hub to link.

### Reading the page-type matrix for GEO

Comparison articles take about a third of AI citations (`references/ai-search-geo.md`). On a SaaS or e-commerce site with zero `comparison` and zero `alternatives` pages, that is the first Opportunity Signal in the report, with the fix "create /vs/[competitor]/ for the top three competitors". `glossary_definition` and `pillar_guide` counts show whether the site has the definitional and hub content AI systems cite for "what is X" queries; `faq` and `community_qa` show self-contained answer blocks.

### Hard rules

- Never claim a page type, hub, orphan or equity share is **absent** from an incomplete inventory. The scripts gate this; do not override them in prose.
- Never call a JavaScript-rendered navigation "missing". Say "not measured from raw HTML" and note that AI crawlers see the same raw HTML.
- Never move these findings into the Health Score or invent a `/100` for them.
- `--rules` is for site-specific URL schemes; do not edit `PAGE_TYPES` in the script for one site (the taxonomy is pinned to `references/page-types.md` by CI).

### Files

| File | Role |
|---|---|
| `references/page-types.md` | The 28-label taxonomy, intent stages, expected types per site type, thresholds, `--rules` format |
| `references/industry-templates.md` | The ideal tree per business type the expected-types check derives from |
| `scripts/site_graph.py` | One crawl, saved for reuse; link regions and containers; completeness verdicts |
| `scripts/page_type_classifier.py`, `scripts/navigation_checker.py`, `scripts/site_architecture.py` | The three checkers |
| `scripts/sitemap_checker.py` | `--lastmod`, `--structure`, `--reconcile` |
