<!-- Updated: 2026-03-22 | Review: 2026-09-22 -->

# Programmatic SEO — Planning, Quality, & Execution
## Updated: March 2026

---

## What Is Programmatic SEO?

Programmatic SEO = generating many pages from structured data at scale, targeting a pattern of similar long-tail keywords. Examples:
- **Integration pages**: "Zapier + [1,200 tools]" → 1,200 pages
- **Location pages**: "[Service] in [City]" → 500+ city pages
- **Glossary pages**: "[Industry Term] definition" → hundreds of definition pages
- **Comparison pages**: "[Tool A] vs [Tool B]" → all competitor combinations
- **Template pages**: "[Action] template" → dozens of downloadable templates

**High reward**: Can capture enormous long-tail traffic with relatively low per-page effort.
**High risk**: Google's Helpful Content assessment directly targets thin, repetitive programmatic content.

---

## Google Enforcement Context (2026)

Google has escalated action against scaled content abuse:

| Update | Impact |
|---|---|
| **Helpful Content System (2022-ongoing)** | Site-wide quality signal — if a significant portion of a site is unhelpful, all content may be deprioritized |
| **March 2024 Core Update** | Explicitly targeted "scaled content abuse" — pages created at scale to manipulate rankings with little unique value |
| **2025 Continued Enforcement** | Sites with >40% thin programmatic content saw 60-80% traffic declines |

**The threshold**: Google doesn't penalize scale itself — it penalizes pages where the only difference is a substituted variable (city name, product name) with no genuinely unique content.

---

## Quality Gates (Non-Negotiable)

| Threshold | Action | Reason |
|---|---|---|
| Planning >100 pages | ⚠️ **WARNING** — review content differentiation plan before building | Ensure template design includes genuine unique value per page |
| Planning >500 pages OR <30% unique content per page | 🛑 **HARD STOP** — requires explicit quality justification | Google's scaled content abuse threshold |
| Content differentiation <40% between pages | Flag as thin content risk | Below this threshold, pages are functionally duplicate |
| No human review before launch | ⚠️ **WARNING** | Require 5-10% sample human review before publishing |

---

## Data Source Assessment

### What Makes a Good Data Source?

| Criterion | Pass | Fail |
|---|---|---|
| **Uniqueness** | Each record produces genuinely different content | >80% field overlap between records |
| **Freshness** | Data is current and verifiable | Outdated, static, or unverifiable data |
| **Depth** | Enough data points per record to fill a useful page | 2-3 fields per record (not enough for a useful page) |
| **Accuracy** | Data is trustworthy (first-party, official APIs, verified) | Scraped, unverified, or user-submitted without validation |

### Data Source Types (Ranked by Quality)

1. **First-party data** — your own product database, transaction history, user data → strongest
2. **Official APIs** — government databases, verified business APIs → very strong
3. **Licensed datasets** — industry databases with rights to use → strong
4. **Third-party scrapes** — only if deeply transformed and enriched → risky without transformation
5. **User-generated content** — valuable if volume and quality are high → needs moderation

---

## Template Engine Planning

### Variable Injection Points (Required)

Every programmatic template MUST have unique content injection for:

| Element | Minimum Unique Content |
|---|---|
| `<title>` tag | Unique per page (inject primary variable) |
| `<h1>` | Unique per page |
| Meta description | Unique per page |
| Body content (first section) | Minimum 30% unique across all instances |
| Schema markup | Accurate per-page data (name, URL, specific properties) |

### Anti-Pattern: "Mad Libs" Templates

**BAD (Google targets this):**
```
[City] Plumber | Emergency Plumbing Services
Need a plumber in [City]? Our [City] plumbers serve the [City] area 24/7.
Call for [City] plumbing services today!
```
→ Only the city name changes. Zero unique value. Explicit scaled content abuse target.

**GOOD:**
```
Austin Plumber | Emergency Plumbing Services in Austin, TX
[Specific: Austin water quality issues, Austin municipal plumbing codes,
 local neighborhoods served with specific context, Austin climate pipe freeze
 statistics, local customer testimonials, Austin-specific pricing context]
```
→ City-specific data, local context, unique value.

### Content Differentiation Checklist

- [ ] Template has ≥3 unique data fields per record (not just name/location)
- [ ] Page body contains record-specific facts, not just the name substituted
- [ ] At least one unique section per page (local stats, specific features, actual data)
- [ ] Schema markup uses per-page specific values (no placeholder text)
- [ ] Images are page-specific (not the same stock photo on all 500 pages)

---

## URL Pattern Strategy

### Recommended Patterns

| Pattern | Example | Notes |
|---|---|---|
| Tool/integration | `/integrations/[platform]` | Feature list must be current and accurate |
| Location-service | `/[city]/[service]` | Requires genuinely unique local content per city |
| Glossary | `/glossary/[term]` | Definition must be original, not scraped |
| Comparison | `/compare/[tool-a]-vs-[tool-b]` | Comparison must be accurate and current |
| Template | `/templates/[use-case]` | Template must be downloadable and genuinely useful |

### URL Best Practices

- Lowercase letters and hyphens only
- Maximum 100 characters
- Match URL to actual content (city name in URL + city-specific content on page)
- Logical hierarchy: `/location/city/service` > `/city-service-page`
- Consistent slug format across all instances (no mixing `new-york` and `new_york`)

---

## Internal Linking Architecture

Programmatic pages need systematic internal linking — without it, many pages become orphans.

### Hub-Spoke Model

```
Hub Page: "[Service] — All Locations"
  ↓ Links to all location pages + receives links from all location pages
  ├── /locations/austin/plumbing
  ├── /locations/denver/plumbing
  ├── /locations/seattle/plumbing
  └── ... (all link back to hub)
```

### Internal Linking Standards for Programmatic Pages

| Standard | Target |
|---|---|
| Links per 1,000 words | 3-5 internal links |
| Hub page links to all spokes | Yes |
| Each spoke links back to hub | Yes |
| Related spoke links | 3-5 related pages per spoke |
| BreadcrumbList schema | Required on all pages |
| Crawl depth from homepage | ≤3 clicks |

---

## Index Management

Not all programmatic pages should be indexed immediately (or ever).

### Index vs. Noindex Decision

| Page Status | Index? | Reasoning |
|---|---|---|
| Rich data, unique content, target keyword has search volume | ✅ Index | Full value; index these |
| Thin content, low search volume, duplicate-ish | ❌ Noindex | Protect crawl budget; avoid thin content signals |
| Pagination pages beyond page 1 | ❌ Noindex | No unique value; canonical to page 1 |
| Parameter variants (`?sort=`, `?filter=`) | ❌ Noindex + canonical | Crawl waste |
| Low-volume long-tail with no unique data | Evaluate | Noindex if <10 monthly searches AND no unique content |

### Crawl Budget Management (for large programmatic sites)

Matters at >10,000 programmatic pages:
- Submit only indexable, canonical pages in sitemap
- Block parameter variants in robots.txt
- Add noindex to faceted navigation and filter pages
- Monitor GSC Coverage report for "Crawled - currently not indexed" (thin content signal)
- Track crawl stats in GSC → Settings → Crawl Stats

### Monitoring Indexation Health

| Metric | Healthy | Investigate |
|---|---|---|
| Submitted/Indexed ratio | > 90% | < 70% |
| "Crawled - not indexed" % | < 10% | > 20% |
| Index growth rate | Steady, consistent | Sudden drop or plateau |

---

## Safe vs. Risky Programmatic Page Types

| Page Type | Risk Level | Key Requirement |
|---|---|---|
| Integration pages (SaaS) | Low | Accurate feature data per integration |
| Glossary/dictionary pages | Low | Original definitions, not scraped |
| Data-driven pages (actual datasets) | Low | Unique, structured data per page |
| Comparison pages | Medium | Must be accurate and up-to-date |
| Location service pages | High | Genuinely unique local content per location |
| City + keyword pages (no local data) | Very High | Only city name substituted = scaled content abuse |
| Doorway pages (redirect to same content) | 🚫 Never | Google spam policy violation |

---

## Pre-Launch Checklist

Before publishing any programmatic SEO campaign:

- [ ] Data source assessed for quality, freshness, uniqueness
- [ ] Template reviewed for ≥40% unique content per record
- [ ] URL structure confirmed (consistent, lowercase, hyphens, logical hierarchy)
- [ ] Internal linking structure planned and implemented (hub + spokes)
- [ ] BreadcrumbList schema on every page
- [ ] Noindex strategy defined for thin/low-value records
- [ ] 5-10% sample of pages reviewed by humans before launch
- [ ] GSC Coverage report baseline captured (for post-launch comparison)
- [ ] Crawl budget impact estimated for large campaigns (>5,000 pages)
- [ ] Analytics tracking confirmed (organic traffic to programmatic URL pattern)

---

## Post-Launch Monitoring

| Timeframe | Check |
|---|---|
| Week 1-2 | GSC Coverage → are pages being indexed at expected rate? |
| Week 2-4 | Rankings for sample of target keywords — any initial movement? |
| Month 2-3 | Traffic to programmatic URL pattern in GA4 — growing or flat? |
| Month 3-6 | E-E-A-T signals on top-performing pages — add content to improve |
| Ongoing | "Crawled - currently not indexed" % — if rising, improve content quality |

**Success signal**: Steady indexation rate + growing long-tail organic traffic.
**Failure signal**: GSC shows many pages as "Crawled - currently not indexed" → content quality issue → improve differentiation or noindex thin pages.
