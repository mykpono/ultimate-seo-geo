<!-- Updated: 2026-03-24 | Review: 2026-09-24 -->
<!-- Source: domain-authority-auditor skill (aaron-he-zhu/cite-domain-rating) -->

# CITE Domain Authority Rating Framework
## Updated: March 2026

40-item domain-level audit across 4 dimensions: **Citation** (link authority), **Identity** (brand/entity presence), **Trust** (safety and legitimacy), and **Eminence** (visibility and reputation). Companion to the CORE-EEAT content-level framework.

---

## Scoring System

| Grade | Points |
|---|---|
| **Pass** | 10 |
| **Partial** | 5 |
| **Fail** | 0 |
| **N/A** | Excluded from dimension average |

**CITE Score** = weighted average of all 4 dimensions using domain-type weights below.

**N/A handling**: Same as CORE-EEAT — if >50% of items in a dimension are N/A, mark "Insufficient Data" and redistribute weight.

---

## Veto Items

Three items that **cap the total score at 39 (Poor)** if they trigger, regardless of other dimensions.

| Veto Item | Dimension | Trigger |
|---|---|---|
| **T03 — Link-Traffic Coherence** | Trust | High backlink count but near-zero organic traffic (PBN signal) |
| **T05 — Backlink Profile Uniqueness** | Trust | >60% of backlinks share patterns (same network, same anchor, same C-class) |
| **T09 — Penalty & Deindex History** | Trust | Active manual action in GSC, or evidence of past algorithmic penalty without recovery |

---

## Domain-Type Weight Tables

| Dimension | Default | Content Publisher | Product & Service | E-commerce | Community & UGC | Tool & Utility | Authority & Institutional |
|---|---|---|---|---|---|---|---|
| **C — Citation** | 35% | **40%** | 25% | 20% | 35% | 25% | **45%** |
| **I — Identity** | 20% | 15% | **30%** | 20% | 10% | **30%** | 20% |
| **T — Trust** | 25% | 20% | 25% | **35%** | 25% | 25% | 20% |
| **E — Eminence** | 20% | 25% | 20% | 25% | **30%** | 20% | 15% |

---

## All 40 Items — Complete Reference

### Dimension 1: Citation (C) — Link Authority

| ID | Item | Pass | Partial | Fail |
|---|---|---|---|---|
| C01 | **Referring Domains Volume** | 500+ unique referring domains | 50–499 | <50 |
| C02 | **Referring Domains Quality** | >30% from DA 40+ domains | 10–30% from DA 40+ | <10% from high-authority domains |
| C03 | **Link Growth Trajectory** | Consistent monthly growth over 12+ months | Irregular but positive trend | Flat, declining, or sudden spikes |
| C04 | **Topical Link Relevance** | >50% of links from same-niche sites | 25–50% topically relevant | <25% topical relevance |
| C05 | **AI Citation Volume** | Cited by 2+ AI platforms for target queries | Cited by 1 AI platform | Not cited by any AI platform |
| C06 | **AI Citation Accuracy** | AI descriptions are factually correct | Partially accurate AI descriptions | Inaccurate or no AI descriptions |
| C07 | **AI Citation Breadth** | Cited for multiple topic areas | Cited for 1 topic area only | Not cited |
| C08 | **AI Citation Recency** | Cited with current information (within 6 months) | Cited but with outdated data | Not cited or severely outdated |
| C09 | **Editorial Link Ratio** | >40% editorial (in-content) links | 20–40% editorial links | <20% editorial; mostly sidebar/footer |
| C10 | **Link Source Diversity** | Links from 10+ countries and 5+ TLDs | 5–9 countries, 3–4 TLDs | Concentrated in 1–2 sources |

### Dimension 2: Identity (I) — Brand & Entity Presence

| ID | Item | Pass | Partial | Fail |
|---|---|---|---|---|
| I01 | **Knowledge Graph Presence** | Active Google Knowledge Panel with complete attributes | Wikidata stub or partial panel | No Knowledge Graph presence |
| I02 | **Wikidata Completeness** | 10+ populated properties with active maintenance | 5–9 properties | <5 properties or no entry |
| I03 | **Brand SERP Control** | Brand search returns owned properties in top 5 | Brand search returns mix of owned/unowned | Brand search returns primarily third-party content |
| I04 | **Consistent NAP+E** | Name, Address, Phone, Entity info consistent everywhere | Minor discrepancies across platforms | Significant inconsistencies |
| I05 | **Schema.org Completeness** | Organization + sameAs + all relevant schema types | Organization schema only | No organization schema |
| I06 | **Social Profile Authority** | Active profiles on 5+ platforms with engagement | Profiles exist but low engagement | Missing key platform profiles |
| I07 | **Visual Brand Consistency** | Logo, colors, imagery consistent across web | Mostly consistent with minor variations | Inconsistent visual identity |
| I08 | **Entity Disambiguation** | No confusion with other entities sharing the name | Minor disambiguation issues | Frequently confused with another entity |
| I09 | **Wikipedia Presence** | Published Wikipedia article meeting notability standards | Draft article or sufficient sources to create one | No article and insufficient notability |
| I10 | **Cross-Platform Entity Linking** | sameAs links connect all official profiles | Some cross-linking but incomplete | No formal entity linking |

### Dimension 3: Trust (T) — Safety & Legitimacy

| ID | Item | Pass | Partial | Fail |
|---|---|---|---|---|
| T01 | **Link Profile Naturalness** | Natural distribution of anchor text, follow/nofollow, deep/homepage | Mostly natural with minor anomalies | Unnatural patterns (bought links, PBN) |
| T02 | **HTTPS & Security** | Full HTTPS, HSTS, no mixed content, security headers present | HTTPS but missing some headers | HTTP pages, mixed content, or security issues |
| T03 | **Link-Traffic Coherence** ⚠️ VETO | Backlink count proportional to organic traffic | Minor discrepancy | High backlinks + near-zero traffic |
| T04 | **IP & Hosting Diversity** | Backlinks from diverse IP ranges and hosting providers | Moderate diversity | Concentrated on few IP ranges |
| T05 | **Backlink Profile Uniqueness** ⚠️ VETO | <30% of backlinks share patterns | 30–60% shared patterns | >60% shared patterns (network signal) |
| T06 | **Legal & Compliance Pages** | Privacy policy, terms, GDPR/CCPA compliance, cookie consent | Some legal pages but incomplete | No legal compliance pages |
| T07 | **Contact Accessibility** | Multiple verified contact methods, physical address if applicable | Contact form or email only | No contact information |
| T08 | **Review Authenticity** | Third-party reviews on established platforms (G2, Trustpilot) | Some reviews but limited | No third-party reviews or suspicious reviews |
| T09 | **Penalty & Deindex History** ⚠️ VETO | Clean history, no manual actions | Past penalty fully recovered | Active manual action or unresolved penalty |
| T10 | **Ad-to-Content Ratio** | Content dominant; ads supplementary and non-intrusive | Moderate ad presence | Ads overwhelm content |

### Dimension 4: Eminence (E) — Visibility & Reputation

| ID | Item | Pass | Partial | Fail |
|---|---|---|---|---|
| E01 | **Organic Search Visibility** | Ranking for 100+ keywords with consistent traffic | Ranking for 20–99 keywords | <20 ranking keywords |
| E02 | **Traffic Growth Trend** | Consistent organic growth over 12+ months | Flat or irregular | Declining traffic |
| E03 | **Content Publishing Cadence** | Regular publication schedule (weekly/biweekly) | Irregular but ongoing | No recent publications (3+ months) |
| E04 | **Content Freshness** | Key pages updated within last 6 months | Updated within 12 months | Stale content (12+ months) |
| E05 | **Thought Leadership Signals** | Speaking engagements, bylines, podcast appearances | Some thought leadership | No external thought leadership |
| E06 | **Media Mention Volume** | 10+ authoritative media mentions in past 12 months | 3–9 mentions | <3 mentions |
| E07 | **Industry Award Recognition** | Recognized awards or certifications | Nominations or minor recognitions | No industry awards |
| E08 | **Community Engagement** | Active community presence (Reddit, forums, LinkedIn) | Occasional participation | No community presence |
| E09 | **User-Generated Content Signal** | Reviews, testimonials, discussions about the brand | Some user-generated mentions | No user-generated content about brand |
| E10 | **Industry Share of Voice** | Top-5 brand in niche for key topic areas | Recognized but not top-tier | Unknown in the industry |

---

## Diagnosis Matrix: CITE + CORE-EEAT

Cross-reference domain authority (CITE) with content quality (CORE-EEAT) to determine the right strategy.

| | High CORE-EEAT (≥75) | Low CORE-EEAT (<75) |
|---|---|---|
| **High CITE (≥75)** | **Maintain & Expand** — Strong foundation. Scale content production, pursue competitive keywords, invest in original research and thought leadership. | **Prioritize Content Quality** — Domain is trusted but content is weak. Upgrade E-E-A-T signals, add original data, improve depth and experience signals. |
| **Low CITE (<75)** | **Build Domain Authority** — Content is strong but domain lacks authority. Focus on link building, brand mentions, entity establishment, third-party reviews. | **Start with Content, Then Domain** — Build content quality first (faster wins), then invest in authority. Avoid competitive keywords until both scores improve. |

---

## Rating Scale

| Score | Rating |
|---|---|
| 90–100 | Excellent |
| 75–89 | Good |
| 60–74 | Medium |
| 40–59 | Low |
| 0–39 | Poor (or veto-capped) |

---

## Audit Output Template

```
# CITE Domain Authority Report — [domain.com]
Domain Type: [type] | Date: [date]

## CITE Score: XX/100

| Dimension | Score | Status |
|---|---|---|
| C — Citation | XX/100 | ✅/⚠️/❌ |
| I — Identity | XX/100 | ✅/⚠️/❌ |
| T — Trust | XX/100 | ✅/⚠️/❌ |
| E — Eminence | XX/100 | ✅/⚠️/❌ |

## Veto Check
- T03 Link-Traffic Coherence: [Pass/Fail]
- T05 Backlink Profile Uniqueness: [Pass/Fail]
- T09 Penalty & Deindex History: [Pass/Fail]

## Combined Assessment (if CORE-EEAT available)
CITE: XX | CORE-EEAT: XX → Strategy: [from Diagnosis Matrix]

## Top 5 Priority Actions
[Sorted by dimension weight × points lost]
```
