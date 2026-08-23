# Backlink Quality Reference

Version: 1.0 | Updated: 2026-04-01

## 1. Backlink Health Score (0–100)

```
health_score = Σ (factor_score × weight)
```

Each factor scored 0–100 independently, then weighted.

| Factor | Weight | Scoring |
|--------|--------|---------|
| Referring domain count | 20% | 100 if ≥ industry P75; 0 if < P10; linear between |
| Domain quality distribution | 20% | `(domains_DR40+ / total_referring_domains) × 100` |
| Toxic link ratio | 20% | 100 if 0% toxic; 0 if ≥ 15% toxic; `100 − (toxic_pct × 6.67)` |
| Anchor text naturalness | 15% | 100 − (sum of deviations from ideal midpoints × penalty multiplier) |
| Geographic relevance | 10% | `(links_from_target_countries / total_links) × 100` |
| Link velocity trend | 10% | Coefficient of variation across 30/60/90-day windows; CV < 0.3 = 100, CV > 1.5 = 0 |
| Follow/nofollow ratio | 5% | 100 if 70–85% follow; −10 per 5% outside range, floor 0 |

### Industry Benchmarks — Referring Domains

| Site Type | P25 | P50 | P75 |
|-----------|-----|-----|-----|
| Local business | 20 | 80 | 250 |
| SaaS | 100 | 500 | 2,000 |
| E-commerce | 200 | 1,000 | 5,000 |
| Publisher | 500 | 3,000 | 15,000 |
| Enterprise | 1,000 | 8,000 | 50,000 |

### Severity Thresholds

| Score | Rating | Action |
|-------|--------|--------|
| 80–100 | Healthy | Monitor quarterly |
| 60–79 | Moderate | Review toxic links, diversify anchors |
| 40–59 | At Risk | Active disavow + link building needed |
| 0–39 | Critical | Immediate disavow + manual review |

---

## 2. Ideal Anchor Text Distribution

| Type | Healthy Range | Over-Optimization Signal | Example |
|------|---------------|--------------------------|---------|
| Branded | 30–50% | < 20% = weak brand signal | "Acme Corp", "acme.com" |
| Exact match | 3–10% | > 15% = Penguin risk | "best project management software" |
| Partial match | 10–20% | > 25% = manipulation pattern | "project management tools by Acme" |
| Generic | 10–20% | > 30% = unnatural profile | "click here", "read more", "this site" |
| URL / naked link | 10–20% | > 30% = low-effort profile | "https://acme.com/features" |
| Misc / random | 5–15% | — | Image alt text, non-English anchors |

### Naturalness Score Calculation

```
deviation = Σ |actual_pct − midpoint| for each type
penalty = deviation × 1.5
anchor_score = max(0, 100 − penalty)
```

Midpoints: Branded 40, Exact 6.5, Partial 15, Generic 15, URL 15, Misc 10.

Flag if any single anchor phrase accounts for > 5% of total backlinks (excluding brand name).

---

## 3. Toxic Link Detection — 30 Patterns

### High Risk (disavow immediately)

| # | Pattern | Description | Detection |
|---|---------|-------------|-----------|
| 1 | PBN — footprint match | Private blog network with shared hosting, templates, or WHOIS | ≥ 3 referring domains share IP/C-class + identical CMS theme + thin content |
| 2 | PBN — interlinked cluster | Group of sites linking to each other and to target | Graph analysis: mutual linking ratio > 40% among cluster |
| 3 | Link farm | Site exists solely to sell/exchange links; 90%+ outbound | Outbound link ratio > 10:1 vs. content words; DR < 15 |
| 4 | Paid link — sponsored not tagged | Commercial link without `rel="sponsored"` or `rel="nofollow"` | Dofollow link from "sponsored post", "partner", "advertiser" page context |
| 5 | Keyword-stuffed anchor | Exact-match commercial anchor from unrelated site | Anchor = high-volume commercial keyword + referring domain topical mismatch |
| 6 | Gambling/casino spam | Links from gambling domains to non-gambling site | Referring domain in gambling/casino/betting TLD or keyword pattern |
| 7 | Pharma spam | Links from pharmaceutical spam sites | Referring page contains pharma keywords (viagra, cialis, etc.) |
| 8 | Adult content spam | Links from adult content sites to non-adult site | Referring domain flagged in adult content classifiers |
| 9 | Deindexed domain | Referring domain no longer in Google's index | `site:domain.com` returns 0 results; domain has backlinks but no indexed pages |
| 10 | Expired domain abuse | Recently re-registered domain used to inject links | Domain age reset (WHOIS creation < 12 months) + historical DR > 30 + current thin content |
| 11 | Tiered link building | Tier 2/3 links pointing to tier 1 link pages | Referring page itself has suspicious inbound links from low-quality sources |
| 12 | Redirect chain manipulation | 301/302 chains used to pass link equity from unrelated domains | Link resolves through 2+ redirects; origin domain topically unrelated |
| 13 | Hacked site injection | Links injected into compromised legitimate sites | Link appears in footer/sidebar with no editorial context; page content unrelated |
| 14 | Cloaked links | Different content served to crawlers vs. users | User-agent–based content variation detected on referring page |
| 15 | Scraper site | Auto-generated site copying content from other sources | Near-duplicate content (> 80% simhash similarity) with other indexed pages |

### Medium Risk (review and monitor)

| # | Pattern | Description | Detection |
|---|---------|-------------|-----------|
| 16 | Comment spam | Links in blog comments, often with keyword anchors | Link in `<comment>` or user-generated section; `rel="ugc"` missing |
| 17 | Forum profile spam | Links from forum profiles or signatures, not posts | URL pattern: `/profile/`, `/member/`, `/user/`; no contextual content |
| 18 | Directory spam | Low-quality web directories (not niche/curated) | Referring domain matches directory pattern; DR < 20; 500+ outbound links per page |
| 19 | Social bookmark spam | Links from social bookmarking sites (Digg clones, etc.) | Referring domain is known bookmarking platform with no editorial control |
| 20 | Press release spam | Syndicated press releases with dofollow keyword links | Same anchor + URL appears on 10+ press release distribution domains |
| 21 | Blog network (gray hat) | Guest posts on low-quality blogs with author bio links | Referring site accepts guest posts at scale; author has 50+ guest post bylines |
| 22 | Reciprocal link scheme | Systematic link exchanges beyond natural cross-referencing | Bidirectional link ratio > 30% between two domains |
| 23 | Footer/sidebar sitewide | Link appears on every page of referring domain | Same link on > 50 pages of referring domain; not a legitimate business partner |
| 24 | Thin content linker | Referring page has < 200 words of unique content | Word count < 200 after stripping boilerplate; page exists primarily to host links |
| 25 | Translated spam | Auto-translated content with injected links | Content quality score < 30; language mismatch between page lang attr and content |
| 26 | Widget/embed link | Link injected via embeddable widget or badge | Link source is `<iframe>`, `<embed>`, or JS widget; anchor text = keyword |
| 27 | Scholarship link scheme | Fake scholarship pages created to get .edu backlinks | Page at `/scholarship` with no real application process; links to commercial sites |
| 28 | Resource page link farm | Resource page listing 100+ outbound links with no curation | Outbound links > 100 on single page; no editorial descriptions |
| 29 | Coupon/deal aggregator | Low-quality coupon sites with dofollow links | Referring domain matches coupon/deal pattern; DR < 25; template content |
| 30 | Unrelated foreign language | Link from foreign-language site with no topical relevance | Language mismatch + topical mismatch + no geographic business presence |

---

## 4. Disavow File Generation

### Format (Google Disavow Tool)

```
# Disavow file for domain.com
# Generated: YYYY-MM-DD
# Toxic links identified: N domains, M individual URLs

# --- Domain-level disavows (preferred) ---
domain:spamsite1.com
domain:linkfarm2.net

# --- URL-level disavows (when domain has mixed quality) ---
https://mixedsite.com/spammy-page
```

### Rules

1. Prefer `domain:` over individual URLs — covers future spam from same domain.
2. Use URL-level only when the referring domain has legitimate links on other pages.
3. Never disavow your own domain, legitimate business partners, or high-DR news/media domains.
4. Include a comment header with generation date and count.
5. One entry per line. Lines starting with `#` are comments.
6. Max file size: 2 MB / 100,000 entries.
7. Re-upload replaces previous file — always include all previous entries.

### Workflow

> **Gate first — do not run this workflow by default.** Google's guidance is that most sites never
> need a disavow file. Proceed only with (1) an active **manual action** for unnatural links, or
> (2) a documented negative-SEO campaign. Without one of those, Google already discounts these links
> and disavowing on a computed score strips credit from borderline-but-legitimate domains for no
> gain. The "toxic" scoring in this file is a **triage aid for deciding what to stop doing**, not a
> disavow trigger — Google publishes no toxicity metric and does not use the term.

1. Confirm the gate above applies. If it does not, stop here.
2. Export the flagged links from `link_profile.py` output.
3. Filter: high_risk **plus manual confirmation of every entry** — nothing is auto-disavowed.
4. Group by domain — if ≥ 3 flagged URLs from the same domain, escalate to `domain:`.
5. Generate file with comments.
6. Submit at [search.google.com/search-console/disavow-links](https://search.google.com/search-console/disavow-links) — it is a standalone tool, not a page inside the Search Console navigation.
7. Re-check in 4–8 weeks for impact.

---

## 5. Competitor Gap Analysis

### Referring Domain Gap

```
gap_domains = competitor_referring_domains − intersection(target, competitor)
```

### Prioritization Matrix

| Signal | Weight | Scoring |
|--------|--------|---------|
| Domain Rating of gap domain | 30% | DR 60+ = high value |
| Topical relevance to target | 25% | Same industry/niche = high |
| Link type (editorial vs. UGC) | 20% | Editorial = high; UGC = low |
| Freshness of competitor's link | 15% | < 6 months = high; > 24 months = low |
| Replicability | 10% | Guest post/resource/mention = replicable; unique partnership = not |

### Opportunity Score

```
opportunity = Σ (signal_score × weight)
```

Priority tiers:
- **Tier 1 (score 70+):** Pursue immediately — high DR, relevant, replicable.
- **Tier 2 (score 40–69):** Queue for outreach — moderate value.
- **Tier 3 (score < 40):** Skip — low ROI or unreplicable.

### Gap Report Output

```
| Domain | DR | Competitors Linking | Link Type | Freshness | Opportunity |
```

### Outreach Prioritization

1. Domains linking to 2+ competitors but not target (highest conversion probability).
2. High-DR domains linking to 1 competitor with editorial content.
3. Resource pages and listicles where target is a natural fit.
4. Broken links on competitor profiles that target could replace.

Flag domains where all competitor links are from the same campaign (e.g., press release syndication) — low unique value.
