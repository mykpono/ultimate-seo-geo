<!-- Updated: 2026-03-24 | Review: 2026-09-24 -->
<!-- Source: entity-optimizer skill (aaron-he-zhu) -->

# Entity Optimization — Knowledge Graph, Brand Entity & AI Recognition
## Updated: March 2026

Structured framework for building and optimizing brand/person entity presence across Google Knowledge Graph, Wikidata, Wikipedia, and AI systems. Includes a 47-signal audit checklist, AI Entity Resolution Test protocol, and implementation roadmap.

---

## AI Entity Resolution Test

Before any optimization, test how AI systems currently perceive the entity. Run these 4 queries across 4 AI platforms.

### Test Queries

| # | Query Template | Tests |
|---|---|---|
| 1 | "What is [Entity Name]?" | Basic recognition and accuracy |
| 2 | "Who founded [Entity Name]?" or "Who is [Person Name]?" | Attribute knowledge depth |
| 3 | "How does [Entity] compare to [Known Competitor]?" | Competitive positioning awareness |
| 4 | "[Entity]'s approach to [Core Topic]" | Topical association strength |

### Scoring Matrix

For each query × platform combination, score:

| Score | Meaning |
|---|---|
| **3 — Full** | Correctly identified, accurate description, cited source |
| **2 — Partial** | Recognized but incomplete or slightly inaccurate |
| **1 — Minimal** | Mentioned but wrong details or confused with another entity |
| **0 — None** | Not recognized or not mentioned |

### Results Template

| Query | ChatGPT | Perplexity | Google AI Overview | Claude |
|---|---|---|---|---|
| "What is [Entity]?" | X/3 | X/3 | X/3 | X/3 |
| "Who founded [Entity]?" | X/3 | X/3 | X/3 | X/3 |
| "How does [Entity] compare to [Competitor]?" | X/3 | X/3 | X/3 | X/3 |
| "[Entity]'s approach to [Topic]" | X/3 | X/3 | X/3 | X/3 |
| **Platform Total** | /12 | /12 | /12 | /12 |

**Overall Entity Recognition Score**: /48

| Score Range | Assessment | Action |
|---|---|---|
| 36–48 | Strong recognition | Maintain and refine accuracy |
| 24–35 | Moderate recognition | Fill specific gaps identified |
| 12–23 | Weak recognition | Prioritize foundation signals |
| 0–11 | Not recognized | Full entity building program needed |

---

## 47-Signal Entity Checklist

### Priority 1: Foundation Signals (Must-Have) — Signals 1–13

**On-Site Structured Data (1–5)**

| # | Signal | Pass | Fail |
|---|---|---|---|
| 1 | Organization/Person schema on homepage | JSON-LD with @type, name, url, sameAs | Missing or incomplete |
| 2 | sameAs property links to all official profiles | 5+ verified sameAs URLs | <3 sameAs or missing key profiles |
| 3 | Consistent @id across all pages | Same @id URI for the entity everywhere | Different @id per page or none |
| 4 | About page with entity-rich content | Detailed about page with history, team, mission | No about page or thin content |
| 5 | Contact page with verifiable information | Address, phone, email, map if applicable | No contact info or unverifiable |

**Key External Profiles (6–10)**

| # | Signal | Pass | Fail |
|---|---|---|---|
| 6 | Wikidata entry | Active entry with 10+ properties | No entry |
| 7 | Google Business Profile (if local) | Claimed, verified, complete | Unclaimed or incomplete |
| 8 | LinkedIn company/person page | Complete profile with activity | Missing or abandoned |
| 9 | CrunchBase profile (if applicable) | Current profile with funding, team data | No entry |
| 10 | Primary industry directory listing | Listed in top industry directory | Not listed |

**Branded Search Presence (11–13)**

| # | Signal | Pass | Fail |
|---|---|---|---|
| 11 | Branded search returns correct entity | Top 5 results are owned properties | Branded search returns competitors or wrong entity |
| 12 | No disambiguation confusion | Entity is the primary result for its name | Confused with another entity |
| 13 | Branded search volume exists | Measurable monthly branded searches | Zero branded search volume |

### Priority 2: Authority Signals (Should-Have) — Signals 14–27

**Knowledge Graph Depth (14–18)**

| # | Signal | Pass | Fail |
|---|---|---|---|
| 14 | Knowledge Panel present | Active Google Knowledge Panel | No panel |
| 15 | Panel attributes complete | Logo, description, key facts populated | Partial or missing attributes |
| 16 | Panel image correct | Official, appropriate image | Wrong or missing image |
| 17 | Wikipedia article (or notability path) | Published article or 3+ independent sources for one | Not notable and no path to notability |
| 18 | Wikidata properties complete (10+) | 10+ well-maintained properties | <10 properties |

**Third-Party Validation (19–23)**

| # | Signal | Pass | Fail |
|---|---|---|---|
| 19 | Authoritative media mentions | 3+ mentions in recognized publications | No media coverage |
| 20 | Industry awards or recognitions | Recognized award or certification | No awards |
| 21 | Co-citation with established entities | Mentioned alongside known brands in the niche | Not co-cited |
| 22 | Speaking engagements / publications | Conference talks, published articles, bylines | None |
| 23 | Reviews on third-party platforms | Active reviews on G2, Trustpilot, Capterra, etc. | No third-party reviews |

**Content Authority (24–27)**

| # | Signal | Pass | Fail |
|---|---|---|---|
| 24 | Topical content depth | 10+ pages covering core topic comprehensively | Thin topical coverage |
| 25 | Author pages with credentials | Detailed author bios with expertise + external links | No author pages or thin bios |
| 26 | Original research or data | Published studies, surveys, or unique datasets | No original research |
| 27 | Entity mentioned naturally in own content | Brand name used contextually throughout site | Brand barely mentioned on own site |

### Priority 3: AI-Specific Signals (Must-Have for GEO) — Signals 28–37

**AI Recognition (28–32)**

| # | Signal | Pass | Fail |
|---|---|---|---|
| 28 | ChatGPT recognizes entity | Correct identification when queried | Not recognized |
| 29 | Perplexity recognizes entity | Correct identification with sources cited | Not recognized |
| 30 | Google AI Overview mentions entity | Included in relevant AI Overview responses | Not mentioned |
| 31 | AI description is accurate | Key facts (founding, product, mission) correct | Inaccurate or outdated description |
| 32 | AI associates entity with correct topics | Entity linked to its primary domain/expertise | Wrong topic association |

**AI Optimization (33–37)**

| # | Signal | Pass | Fail |
|---|---|---|---|
| 33 | Entity definition quotable in first paragraph | Clear "X is..." definition in opening of about/homepage | Definition buried or missing |
| 34 | Factual claims verifiable | Key claims have authoritative sources | Unsourced claims |
| 35 | Entity name used consistently | Same entity name across all platforms and content | Name variations causing confusion |
| 36 | Content crawlable by AI systems | AI crawlers (GPTBot, PerplexityBot) allowed in robots.txt | AI crawlers blocked |
| 37 | Fresh information available | Key pages updated within last 6 months | Stale content (12+ months) |

### Priority 4: Advanced Signals (Nice-to-Have) — Signals 38–47

**Extended Knowledge Base (38–41)**

| # | Signal | Pass | Fail |
|---|---|---|---|
| 38 | Multiple-language Wikidata entries | Entity info in 2+ languages | English only |
| 39 | DBpedia entry | Listed in DBpedia (auto-generated from Wikipedia) | No Wikipedia → no DBpedia |
| 40 | Google Knowledge Graph ID known | Can retrieve via KG API | Unknown |
| 41 | ISNI/VIAF identifier (for persons) | Official identifier registered | Not applicable or not registered |

**Social Entity Signals (42–44)**

| # | Signal | Pass | Fail |
|---|---|---|---|
| 42 | Social profiles bidirectionally linked | Website → social AND social → website | One-way linking only |
| 43 | Consistent entity description across social | Same bio/description on all platforms | Different descriptions per platform |
| 44 | Social engagement demonstrates real audience | Genuine engagement metrics | Ghost accounts or purchased followers |

**Technical Entity Signals (45–47)**

| # | Signal | Pass | Fail |
|---|---|---|---|
| 45 | Entity homepage has strong backlink profile | 50+ unique referring domains to homepage | <50 referring domains |
| 46 | Branded anchor text in backlinks | Natural branded anchors in inbound links | No branded anchor text |
| 47 | Entity subdomain consistency | All subdomains link back to main entity | Orphaned subdomains |

---

## Priority Action Matrix

| Current State | Focus Area | Expected Timeline |
|---|---|---|
| Most Priority 1 signals fail | Foundation signals only | 2–4 weeks |
| Priority 1 mostly pass, Priority 2 mixed | Authority signals | 1–2 months |
| Priority 1–2 mostly pass | AI-specific signals (Priority 3) | 2–3 months |
| Priority 1–3 mostly pass | Selective Priority 4 for completeness | Ongoing |
| All tiers mostly pass | Maintenance + quarterly re-audit | Quarterly |

---

## Entity Building Roadmap

### Weeks 1–2: Foundation

1. Create or verify Organization/Person schema with complete sameAs
2. Create Wikidata entry (or verify/update existing)
3. Claim and complete Google Business Profile (if applicable)
4. Ensure LinkedIn, CrunchBase, and industry directory profiles are complete
5. Verify branded search returns correct entity in top 5

### Month 1: Knowledge Bases

1. Add 10+ Wikidata properties (founding date, CEO, products, social links)
2. Begin Wikipedia notability assessment — identify existing independent sources
3. If notable: draft Wikipedia article in neutral tone with 3+ independent citations
4. If not yet notable: begin digital PR to earn independent citations

### Months 2–3: Authority Building

1. Pursue 3–5 media mentions or guest bylines in industry publications
2. Submit for relevant industry awards or certifications
3. Build topical content depth (10+ pages on core expertise area)
4. Create author pages with detailed credentials and external links
5. Publish original research or data (survey, report, case study)

### Ongoing: AI Optimization & Maintenance

1. Run AI Entity Resolution Test quarterly — track score changes
2. Ensure AI crawlers remain unblocked
3. Update key pages every 6 months with fresh data
4. Monitor Knowledge Panel for accuracy (claim if available)
5. Update Wikidata quarterly (CEO, products, key facts)

---

## Entity Type Reference

| Entity Type | Primary Signals | Key Schema |
|---|---|---|
| Person | Author pages, social profiles, publication history | Person, ProfilePage |
| Organization | Registration records, Wikidata, industry listings | Organization, Corporation |
| Brand | Trademark, branded search volume, social presence | Brand, Organization |
| Product | Product pages, reviews, comparison mentions | Product, SoftwareApplication |
| Creative Work | Publication record, citations, reviews | CreativeWork, Book, Movie |
| Event | Event listings, press coverage, social buzz | Event |

## Disambiguation Strategies

| Situation | Strategy |
|---|---|
| Common name, unique entity | Strengthen all signals; let signal volume resolve ambiguity |
| Name collision with larger entity | Add qualifier consistently; use sameAs extensively; build topic-specific authority |
| Name collision with similar entity | Geographic/industry/product qualifiers; ensure Schema @id is unique; prioritize Wikidata disambiguation |
| Abbreviation/acronym conflict | Prefer full name in structured data; use abbreviation only in established contexts |
| Merged or renamed entity | Redirect old entity signals; update all structured data; create "formerly known as" content; update Wikidata |

---

## Cross-Reference to Other Frameworks

- **CORE-EEAT**: A07 (Knowledge Graph Presence), A08 (Entity Consistency) directly measure entity signals
- **CITE**: Entire I-dimension (Identity) maps to entity optimization
- **GEO Score**: Authority & Brand Signals dimension (20% weight) depends on entity strength
