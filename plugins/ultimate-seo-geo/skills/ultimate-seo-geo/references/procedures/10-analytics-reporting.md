> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

## 10. Analytics & Reporting

### Setup — Step by Step

1. **Confirm GA4** — `gtag.js` in page source. Missing → install and configure organic reporting.
2. **Confirm Search Console verified** — If not → verify and submit sitemap.
3. **Confirm rank tracking** — Weekly position tracking for primary keywords (mobile + desktop separately).
4. **Run PageSpeed Insights** on homepage + 2 key pages.

### Minimum Stack

| Tool | Purpose |
|---|---|
| **Google Search Console** | Indexation, Performance, Core Web Vitals (field data) |
| **GA4** | Organic sessions, engagement, conversions |
| **PageSpeed Insights** | Core Web Vitals field + lab data |
| **Rank tracker** | Weekly position tracking |

### Traffic Drop Diagnostic

1. **GSC impressions dropped** → Ranking issue. Check algorithm update calendar. Identify pages + dates.
2. **Impressions stable, clicks fell** → SERP feature change (AI Overview absorbing clicks). Optimize for AI citation (§ 3) and featured snippet (§ 7c).
3. **Segment by page type** → Isolate which category is affected.

### Search Console Opportunities (Tier 1)

Run `python scripts/gsc_insights.py sc-domain:example.com --all --json` before advising on titles, refreshes or cannibalisation. It reads query x page data for the last 28 days and reports:

| Analysis | Rule | Default action |
|---|---|---|
| Striking distance | Average position 8–15, ≥200 impressions (`--min-impressions` for small sites) | Put the query's words in the title, H1 and opening paragraph; add one internal link with the query as anchor |
| Low CTR | Position ≤10, ≥100 impressions, CTR below **half this property's own median CTR** at that rounded position | Rewrite title and meta description, unless a SERP feature sits above the result |
| Cannibalisation | Query with ≥50 impressions where a second URL holds ≥10% of them (fragment URLs merged first) | Pick the winner; merge with a 301 (high-risk, confirm first) or re-target the other page |
| Decay | Clicks down ≥20% in the latest window **and** down in the one before, ≥30 clicks; tagged seasonal when the same windows fell last year | Refresh non-seasonal pages: find the lost queries, compare with the pages now outranking them |
| Serve map | `--serve-map targets.csv` (query,url) vs the page with the most impressions | Strengthen the intended page, or update the map |
| Human basis | Blended vs human-only impressions, CTR and position, now and vs the previous window; the queries set aside, why, and the pages mostly shown to them | Quote trends on the human basis; decide whether pages shown mostly to machines belong on the site |

Every figure comes from the API. The CTR benchmark is the property's own; a position bucket with fewer than 5 qualifying rows reads "cannot compute", never an industry number. Upside estimates name the bucket they came from. Output lists its limits (anonymised queries, row caps). Without credentials, `--replay rows.json` analyses rows saved earlier with `--save-rows`.

**Machine queries are set aside before any analysis.** Search Console has no user agent, so rank trackers, scrapers and agents show up as queries. A query is **machine** when its text is machine-shaped (search operators, URLs, quoted-phrase templates such as `"roku" data governance strategy`, scraper syntax) or when its clicks are impossible for people: on positions 1–20 with 500+ impressions, fewer clicks than a floor CTR of 0.2% (positions 1–3), 0.1% (4–10) or 0.05% (11–20) allows at Poisson P < 1e-6. The floor sits well below AI Overview citation CTRs. A query of 12+ words is **agent-like**. Both are left out of striking distance, low CTR and cannibalisation, so no title rewrite is proposed for a query no person typed; `--include-machine` keeps them. The site's own CTR curve cannot find this contamination when it dominates the site (Improvado's median CTR was 0% at every position), which is why the floor is fixed. Quote site-level trends from `human_basis.current.human` and name the basis. On Improvado, Sep 2–15 2026: 41% of impressions were machine or agent-like (8 clicks), and 56% of the position gain since Aug 18–31 was a change in who searched.

**Quoting a page's Search Console figures:** use `gsc_query.py --dimension page` (it sums `#fragment` jump-link rows into their page) or `gsc_insights.py`. Never quote a single row from the Performance UI or a raw export for a page with a table of contents: its anchor rows are separate URLs there. State the property with the number (`sc-domain:` and URL-prefix figures never add), and say that fragment sums are an upper bound.

**In the full report:** `generate_report.py URL --gsc-property sc-domain:example.com` runs these as the display-only *Search performance* check and adds each finding's Search Console clicks ("Traffic at stake"). `--gsc-pages Pages.csv` (the Performance report's Pages export) adds the clicks without API access.

### CTR Benchmarks

Industry ranges for orientation only. For a verified property, judge CTR against the property's own curve (`gsc_insights.py --low-ctr`), not this table.

| Position | Expected CTR | Action |
|---|---|---|
| 1 | 27–39% | Rewrite title; test question format |
| 3 | 10–14% | Improve meta description; add rich result schema |
| 5 | 5–7% | Rewrite title + meta; optimize for featured snippet |
| 10 | 2–3% | Major content upgrade to push to top 5 |

**AI traffic**: `python scripts/ga4_report.py --property ID --ai-referrals --json` groups GA4 sessions from ChatGPT (`chatgpt.com`, including its `utm_source=chatgpt.com` links), Perplexity, Claude, Gemini, Copilot and others by source and landing page. Clicks with neither a referrer nor a UTM still read as Direct, so the number is a floor.

→ See `references/analytics-reporting.md`
