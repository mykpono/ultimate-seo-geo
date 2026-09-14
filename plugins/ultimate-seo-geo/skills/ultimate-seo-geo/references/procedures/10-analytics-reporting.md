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

### CTR Benchmarks

| Position | Expected CTR | Action |
|---|---|---|
| 1 | 27–39% | Rewrite title; test question format |
| 3 | 10–14% | Improve meta description; add rich result schema |
| 5 | 5–7% | Rewrite title + meta; optimize for featured snippet |
| 10 | 2–3% | Major content upgrade to push to top 5 |

**AI traffic**: `python scripts/ga4_report.py --property ID --ai-referrals --json` groups GA4 sessions from ChatGPT (`chatgpt.com`, including its `utm_source=chatgpt.com` links), Perplexity, Claude, Gemini, Copilot and others by source and landing page. Clicks with neither a referrer nor a UTM still read as Direct, so the number is a floor.

→ See `references/analytics-reporting.md`
