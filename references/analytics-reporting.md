<!-- Updated: 2026-03-22 | Review: 2026-09-22 -->

# Analytics & SEO Reporting
## Updated: March 2026

---

## Core Analytics Stack

| Tool | Purpose | Priority |
|---|---|---|
| **Google Search Console (GSC)** | Impressions, clicks, CTR, position; coverage; Core Web Vitals field data | Critical |
| **GA4** | Traffic sources, engagement, conversions, revenue | Critical |
| **PageSpeed Insights** | CrUX field data + lab data for CWV | High |
| **Bing Webmaster Tools** | Bing-specific indexation, keyword data (different from Google) | Medium |
| **Rank tracker** (Ahrefs/Semrush/SERPWatcher) | Daily/weekly keyword position tracking | High |
| **Log analyzer** (Screaming Frog, Botify) | Crawl budget, bot behavior, indexation issues | Medium |

---

## Google Search Console — Key Reports

### Performance Report

**Primary metrics:**
| Metric | What It Tells You |
|---|---|
| **Total Clicks** | Actual organic visits from Google Search |
| **Total Impressions** | How many times your pages appeared in SERPs |
| **Average CTR** | Clicks ÷ Impressions — should rise as you optimize titles/meta descriptions |
| **Average Position** | Mean ranking across all queries shown |

**Critical segmentations to apply:**
- **Search type**: Web vs. Image vs. Video vs. Discover — filter to "Web" for standard SEO
- **Date range**: 28-day rolling vs. 3-month vs. 12-month for trend analysis
- **Compare periods**: YoY comparison more useful than MoM for seasonal sites
- **Device**: Mobile vs. Desktop — flag significant CTR gaps
- **Country**: Identify underperforming markets for international expansion

**Query analysis workflow:**
1. Filter to queries with avg position 4-15 (ranking, not winning) → optimize title/meta to improve CTR
2. Filter to queries with high impressions + low CTR → title/meta description issue
3. Filter to queries with declining clicks YoY → content freshness or algorithm update impact
4. Export and segment by informational vs. transactional intent

**Page analysis workflow:**
1. Sort pages by impressions descending → high impression / low clicks = CTR problem
2. Sort by clicks descending → top performers to protect and expand
3. Identify pages losing click share YoY → content audit candidates

### Coverage / Index Report

| Status | Action |
|---|---|
| **Valid** | All indexed pages — review for any unexpected inclusions |
| **Valid with warning** | Indexed but issue detected (e.g., soft 404, duplicate without canonical) |
| **Excluded** | Review each exclusion reason — some are intentional, others are not |
| **Error** | Fix immediately (404, server error, redirect error) |

**Key exclusion reasons to investigate:**
- "Duplicate without user-selected canonical" → add explicit canonical tags
- "Crawled - currently not indexed" → thin content, low quality, or crawl budget issue
- "Discovered - currently not indexed" → crawl budget exhausted; improve internal linking to these pages
- "Page with redirect" → may indicate redirect chain or unintentional redirect

### Core Web Vitals Report (Field Data)

GSC shows CrUX (real user) data, which is what Google uses for rankings:
- Good, Needs Improvement, Poor — aggregate by URL group
- Use "URL details" to identify specific page clusters underperforming
- Prioritize pages with most traffic in "Poor" status

### Enhancement Reports

- **Rich results**: Eligible vs. Valid vs. Error by schema type
- **Breadcrumbs**: Structured data parsing errors
- **Sitelinks searchbox**: If applicable

---

## GA4 — SEO Reporting Setup

### Key Dimensions & Metrics for SEO

**Acquisition reports:**
- `Session source / medium` → filter to `google / organic` or `(organic)`
- `Landing page + query string` → which pages receive organic traffic
- `First user source` → attribution for new user acquisition

**Engagement metrics (replace Bounce Rate from UA):**
- **Engaged sessions**: Sessions > 10 seconds OR ≥ 2 pageviews OR conversion event
- **Engagement rate**: Engaged sessions ÷ Total sessions (60%+ is healthy for content)
- **Average engagement time**: Replaces Time on Page — compare by landing page

**Conversion tracking:**
- Set up key events: form submissions, purchases, sign-ups, phone clicks
- Create GA4 conversions from key events
- Attribution: use "Data-driven" model; cross-reference with GSC clicks for organic conversion rate

### Custom Exploration Reports Worth Building

1. **Organic Landing Page Performance**
   - Dimension: Landing page
   - Metrics: Sessions, Engaged sessions, Engagement rate, Conversions, Revenue
   - Filter: Session source = google, medium = organic

2. **Content Decay Dashboard**
   - Compare organic traffic by landing page: current 90 days vs. prior year 90 days
   - Flag pages with > 20% traffic decline for content audit

3. **New vs. Returning Organic Visitors**
   - Segmented by source = organic
   - High new visitor % = good discovery; high returning % = brand strength

### Organic CTR Benchmarks by Position

| Average Position | Expected CTR |
|---|---|
| 1 | 27-39% |
| 2 | 15-22% |
| 3 | 10-14% |
| 4 | 7-10% |
| 5 | 5-7% |
| 6-10 | 2-5% |
| 11-20 | 0.5-2% |

**Below-benchmark CTR at any position** → rewrite title tag and meta description. Test question-format titles, add numbers, power words, or year.

---

## Rank Tracking

### Setup Best Practices

- Track keywords in **3 buckets**:
  1. **Head terms** (high volume, competitive) — track for trend
  2. **Mid-tail targets** (your primary SEO focus) — track weekly
  3. **Long-tail / conversational** — track for AI Overviews triggers

- Always track **mobile and desktop separately** — can differ by 3-5 positions
- Set **location-specific** tracking for local businesses
- Track **SERP features**: featured snippet, AI Overview, image pack, video, PAA — not just blue link positions

### Rank Tracking Workflow (Weekly)

1. Check for significant drops (>5 positions) since last week → cross-reference with Google algorithm update calendar
2. Check for pages entering positions 4-15 → internal linking and content optimization opportunity
3. Check SERP feature changes → lost featured snippet? Gained AI Overview trigger?
4. Report positions alongside GSC clicks — rank alone is misleading (SERP feature cannibalization)

---

## Algorithm Update Response Protocol

### Detection Workflow

1. **Traffic drops > 15% in 7 days**: Cross-reference with [Google Algorithm Update History](https://developers.google.com/search/updates/ranking)
2. **Identify affected page types**: Are drops concentrated in blog posts? Product pages? All pages?
3. **Compare to GSC impressions**: Clicks dropped but impressions stable → SERP feature change (not ranking drop)
4. **Check competitors**: Did competing domains gain what you lost? Confirms algo update vs. technical issue

### Common Update Types & Response

| Update Type | Signals | Response |
|---|---|---|
| **Core update** | Broad traffic loss across site | E-E-A-T audit, content quality improvement |
| **Helpful Content** | Thin, low-value pages hit hardest | Consolidate, rewrite, or delete thin content |
| **Spam update** | Sudden dramatic loss | Check for manual action in GSC; backlink audit |
| **SERP feature shift** | Impressions stable, clicks fall | AI Overview or featured snippet now present — optimize for these |

---

## SEO ROI Reporting

### Monthly Report Template

```
## SEO Performance Report — [Month YYYY]
Site: [domain] | Reporting Period: [date range]

### Headline Metrics
| Metric | This Period | Prior Period | YoY | Target |
|---|---|---|---|---|
| Organic Sessions | | | | |
| Organic Conversions | | | | |
| Organic Revenue / Value | | | | |
| Avg. Position (tracked keywords) | | | | |
| Indexed Pages | | | | |
| Referring Domains | | | | |

### Keyword Performance
- Keywords in positions 1-3: [N] (was: [N])
- Keywords in positions 4-10: [N] (was: [N])
- Keywords in positions 11-20: [N] (was: [N])
- Total tracked keywords: [N]

### Notable Wins This Period
1. [Page or keyword that improved significantly]
2. ...

### Issues Identified
1. [Issue + root cause]
2. ...

### Actions Completed
- [List of implemented changes]

### Actions Planned (Next Period)
- [Priority 1]
- [Priority 2]

### Algorithm Updates / External Factors
[Note any confirmed updates or SERP changes]
```

### Calculating SEO ROI

```
SEO ROI = (Organic Revenue - SEO Investment) / SEO Investment × 100

Organic Revenue = Organic Sessions × Conversion Rate × Avg. Order Value

For lead gen:
Organic Value = Organic Conversions × Avg. Lead Value
```

**If e-commerce is not set up in GA4**: Estimate using average contract/lead value × organic conversion count from GA4 goals.

---

## GEO / AI Search Analytics

Traditional analytics cannot capture AI-driven traffic directly. Use these proxies:

### What to Track

| Metric | Tool | What It Indicates |
|---|---|---|
| **Perplexity referral traffic** | GA4 (source: perplexity.ai) | Perplexity citations — trackable |
| **Direct traffic uplift** | GA4 | ChatGPT citations (no referrer header; appears as Direct) |
| **Branded search impressions** | GSC | Brand visibility in AI-driven discovery |
| **Zero-click impressions** | GSC | AI Overview presence (impressions without clicks) |
| **Brand mention volume** | Google Alerts, Ahrefs Mentions | AI training signal health |

### Interpreting the "Dark Traffic" Problem

ChatGPT Search does NOT pass referrer headers — traffic appears as **Direct** in GA4.

**Estimate AI traffic share:**
1. Establish Direct traffic baseline (12-month average before ChatGPT Search scaled)
2. Measure Direct traffic lift after chatGPT Search growth (late 2024 onward)
3. Segment: Direct traffic on mobile vs. desktop vs. branded landing pages
4. Spike in branded Direct + no other explanation → likely AI-driven discovery

---

## Analytics Scoring

| Dimension | Excellent | Good | Needs Work |
|---|---|---|---|
| GSC connected & verified | Yes, HTML tag + DNS | Yes | Not verified |
| GA4 installed & tracking | Events + conversions set up | Basic pageview only | Not installed |
| Rank tracking | 50+ keywords, weekly, mobile+desktop | 20+ keywords monthly | < 20 keywords or none |
| Reporting cadence | Weekly dashboard + monthly report | Monthly report | Ad hoc only |
| Conversion tracking | Revenue/lead value tracked | Conversion events only | No conversions |
| Algorithm monitoring | Alerts configured | Manual check | Not monitored |

---

## Monthly Maintenance Checklist

### Technical Health
- [ ] **GSC Coverage** — New "Crawled - currently not indexed" or coverage errors?
- [ ] **Core Web Vitals** — PageSpeed Insights on top 5 pages. LCP, INP, CLS regressions?
- [ ] **robots.txt** — AI crawlers still unblocked? Deployments sometimes overwrite.
- [ ] **Redirect integrity** — New 404 errors in GSC?

### Content & Rankings
- [ ] **Rank tracking** — Drops in top 20 keywords?
- [ ] **CTR check** — Pages with impressions but CTR below benchmark?
- [ ] **Algorithm updates** — Google updates in past 30 days? Cross-reference with traffic.
- [ ] **Content decay** — Pages losing impressions after 3+ months ranking? Flag for refresh.

### GEO / AI Search
- [ ] **Test brand in ChatGPT and Perplexity** — Still cited for primary keywords?
- [ ] **Brand mentions** — New mentions on Reddit, YouTube, industry publications?
- [ ] **llms.txt** — Reflects new key pages published this month?

### Local SEO (if applicable)
- [ ] **New reviews** — Negative reviews needing response?
- [ ] **GBP posts** — New What's New or Offer post this week?

### Analytics Integrity
- [ ] **GA4 organic sessions** — Trending vs. prior month? Anomalies?
- [ ] **Conversion tracking** — Goal completions still firing?

---

## Google's Official Stance — Myths & Misconceptions

| Myth | Google's Official Position |
|---|---|
| **Meta keywords tag helps SEO** | "Google does not use the keywords meta tag." Ignore it. |
| **Keyword stuffing improves rankings** | Actively penalised as spam. Natural writing wins. |
| **Keywords in domain name help ranking** | "Hardly any effect." Brand > keywords. |
| **TLD matters (.com vs .io)** | Google doesn't care — except ccTLDs for geo-targeting. |
| **Word count minimums** | "No minimum or maximum." Cover the topic. |
| **Subdomains hurt vs. subdirectories** | No ranking difference. |
| **Heading order matters for SEO** | "From Google Search perspective, it doesn't matter." |
| **E-E-A-T is a direct ranking factor** | "No, it's not." Describes quality; proxies are measured. |
| **Duplicate content is penalised** | Not spam — Google picks one canonical. |
| **Social signals directly affect rankings** | Not direct. Social → links/mentions → those affect rankings. |
| **HCS is a separate filter** | Merged into core algorithm March 2024. |
| **Readability scores help rankings** | Google does not use Flesch-Kincaid. |
| **CWV are primary ranking factors** | CWV are a **tiebreaker** — content quality dominates. |
| **Voice search needs separate SEO** | Voice answers come from Featured Snippets — optimize for featured snippets. |
