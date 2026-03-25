<!-- Updated: 2026-03-24 | Review: 2026-09-24 -->
<!-- Source: content-quality-auditor skill (aaron-he-zhu/core-eeat-content-benchmark) -->

# CORE-EEAT Content Quality Framework
## Updated: March 2026

80-item content audit across 8 dimensions. Produces a **GEO Score** (AI citation readiness) and an **SEO Score** (search ranking quality), plus a content-type-weighted total.

---

## Scoring System

| Grade | Points |
|---|---|
| **Pass** | 10 |
| **Partial** | 5 |
| **Fail** | 0 |
| **N/A** | Excluded from dimension average |

**GEO Score** = average of CORE dimensions (C + O + R + E) / 4
**SEO Score** = average of EEAT dimensions (Exp + Ept + A + T) / 4
**Total Score** = weighted average using content-type weights below

**N/A handling**: If >50% of items in a dimension are N/A, mark the dimension as "Insufficient Data" and exclude it — redistribute its weight proportionally to remaining dimensions.

---

## Veto Items

Three items that **override the total score** regardless of how high other dimensions score. If any veto item scores Fail, the content cannot receive an overall rating above "Needs Improvement."

| Veto Item | Dimension | Why It Vetoes |
|---|---|---|
| **C01 — Intent Alignment** | Contextual Clarity | Content that doesn't match user intent fails the fundamental quality test |
| **R10 — Content Consistency** | Referenceability | Contradictory or inconsistent claims destroy trust for both users and AI |
| **T04 — Disclosure Statements** | Trust | Missing disclosures (sponsorship, affiliation, conflicts) is a Google spam signal |

---

## Content-Type Weight Tables

Different content types emphasize different dimensions. Use the appropriate weight profile.

| Dimension | Blog Post | Product Review | How-To Guide | Research/Data | Landing Page | News Article |
|---|---|---|---|---|---|---|
| **C — Contextual Clarity** | 15% | 10% | 15% | 10% | 20% | 15% |
| **O — Organization** | 10% | 10% | 15% | 10% | 10% | 10% |
| **R — Referenceability** | 10% | 10% | 10% | 20% | 5% | 15% |
| **E — Exclusivity** | 10% | 15% | 10% | 20% | 10% | 10% |
| **Exp — Experience** | 15% | 20% | 15% | 10% | 10% | 10% |
| **Ept — Expertise** | 15% | 15% | 15% | 15% | 10% | 15% |
| **A — Authoritativeness** | 10% | 10% | 10% | 10% | 15% | 15% |
| **T — Trust** | 15% | 10% | 10% | 5% | 20% | 10% |

---

## All 80 Items — Complete Reference

### Dimension 1: Contextual Clarity (C) — GEO

| ID | Item | Pass | Partial | Fail |
|---|---|---|---|---|
| C01 | **Intent Alignment** ⚠️ VETO | Content directly addresses the user's search intent | Partially addresses intent but drifts | Mismatches intent entirely |
| C02 | **Direct Answer** | Target query answered in first 150 words | Answer present but buried (150–500 words in) | No direct answer to the core query |
| C03 | **Query Coverage** | All facets of the query addressed | Major facets covered, minor ones missing | Key aspects of the query ignored |
| C04 | **Definition First** | Key term defined in opening paragraph | Definition present but not prominent | No clear definition of core concept |
| C05 | **Topic Scope** | Comprehensive coverage appropriate to format | Adequate but missing 1–2 important subtopics | Superficial or off-topic |
| C06 | **Audience Targeting** | Clear who the content is for; language matches audience level | Implicit audience but inconsistent tone | No discernible target audience |
| C07 | **Semantic Coherence** | Logical flow from section to section; no non-sequiturs | Mostly coherent with minor jumps | Disjointed; sections don't connect |
| C08 | **Use Case Mapping** | Specific use cases or scenarios provided | Generic examples without specificity | No practical application shown |
| C09 | **FAQ Coverage** | Structured FAQ section addressing common follow-up questions | Some questions answered inline | No FAQ or follow-up coverage |
| C10 | **Semantic Closure** | Content reaches a clear conclusion; no loose ends | Conclusion present but weak | Ends abruptly or trails off |

### Dimension 2: Organization (O) — GEO

| ID | Item | Pass | Partial | Fail |
|---|---|---|---|---|
| O01 | **Heading Hierarchy** | Clean H1→H2→H3; no skipped levels | Mostly correct with minor inconsistencies | Broken hierarchy or missing headings |
| O02 | **Summary Box** | Key takeaways / TL;DR at top or per section | Summary present but incomplete | No summary or takeaway section |
| O03 | **Data Tables** | Comparative data presented in tables, not prose | Some tabular data but key comparisons in prose | No tables; all data in paragraphs |
| O04 | **List Formatting** | Steps, features, items in numbered/bulleted lists | Some lists but inconsistent usage | Wall of text; no list structure |
| O05 | **Schema Markup** | Appropriate JSON-LD schema (Article, FAQ, HowTo, etc.) | Partial schema (e.g., Article but missing FAQ) | No structured data |
| O06 | **Section Chunking** | Sections are self-contained (readable independently) | Most sections self-contained; some depend on prior context | Sections require reading prior content |
| O07 | **Visual Hierarchy** | Bold/italic for emphasis; clear visual scanning path | Some emphasis but inconsistent | No visual hierarchy; flat text |
| O08 | **Anchor Navigation** | Table of contents or jump links for long content | Partial TOC or jump links | No navigation aids on long content |
| O09 | **Information Density** | High signal-to-noise ratio; every paragraph adds value | Some filler but mostly substantive | Padded content; low information per word |
| O10 | **Multimedia Structure** | Images, videos, or diagrams enhance understanding | Some media but not integrated with content | No supporting media or irrelevant media |

### Dimension 3: Referenceability (R) — GEO

| ID | Item | Pass | Partial | Fail |
|---|---|---|---|---|
| R01 | **Data Precision** | Specific numbers with sources ("73% of users, Forrester 2025") | Numbers present but unsourced | Vague claims ("many users", "most people") |
| R02 | **Citation Density** | 5+ citations to authoritative sources per 1,000 words | 2–4 citations per 1,000 words | Fewer than 2 citations per 1,000 words |
| R03 | **Source Hierarchy** | Primary sources cited (studies, official docs, original data) | Mix of primary and secondary sources | Only secondary or no sources |
| R04 | **Evidence-Claim Mapping** | Every major claim has supporting evidence | Most claims supported; some unsupported | Claims made without evidence |
| R05 | **Methodology Transparency** | Process/methodology explained when presenting data or results | Methodology implied but not explicit | Results stated without method |
| R06 | **Timestamp & Versioning** | Publication date + last-updated date visible | Publication date only | No dates visible |
| R07 | **Entity Precision** | People, organizations, products named precisely | Some entities named, others vague | Generic references ("experts say") |
| R08 | **Internal Link Graph** | 3–5 relevant internal links per 1,000 words | 1–2 internal links per 1,000 words | No internal links |
| R09 | **HTML Semantics** | Proper use of semantic HTML (article, section, aside, figure) | Some semantic elements | No semantic HTML; div soup |
| R10 | **Content Consistency** ⚠️ VETO | No contradictions within content or vs. other site pages | Minor inconsistencies that don't mislead | Contradictory claims or data |

### Dimension 4: Exclusivity (E) — GEO

| ID | Item | Pass | Partial | Fail |
|---|---|---|---|---|
| E01 | **Original Data** | First-party data, survey results, or unique analysis | Data derived from public sources with added analysis | No original data; all from existing sources |
| E02 | **Novel Framework** | Original model, framework, or methodology introduced | Existing framework applied to new context | No original contribution |
| E03 | **Primary Research** | Original interviews, experiments, or field research | Synthesis of others' primary research | No research component |
| E04 | **Contrarian View** | Well-argued position that challenges conventional wisdom | Acknowledges alternative viewpoints | Pure consensus repetition |
| E05 | **Proprietary Visuals** | Original charts, diagrams, infographics | Mix of original and stock/generic visuals | Only stock images or no visuals |
| E06 | **Gap Filling** | Addresses a topic or angle not covered elsewhere | Adds modest value to existing coverage | Redundant with existing content |
| E07 | **Practical Tools** | Downloadable templates, calculators, checklists | Links to existing tools | No actionable resources |
| E08 | **Depth Advantage** | Covers the topic more deeply than any competing page | Comparable depth to competitors | Shallower than competing content |
| E09 | **Synthesis Value** | Combines insights from multiple domains/sources uniquely | Decent synthesis of related information | Single-source perspective |
| E10 | **Forward Insights** | Predictions, trends, or emerging developments discussed | Brief mention of future implications | Purely retrospective; no forward look |

### Dimension 5: Experience (Exp) — SEO

| ID | Item | Pass | Partial | Fail |
|---|---|---|---|---|
| Exp01 | **First-Person Narrative** | Author's direct experience clearly conveyed | Some personal anecdotes | No first-hand perspective |
| Exp02 | **Sensory Details** | Specific sensory or situational details from experience | Some descriptive details | Abstract; no experiential detail |
| Exp03 | **Process Documentation** | Step-by-step account of actually doing the thing | Partial process description | No process insight |
| Exp04 | **Tangible Proof** | Screenshots, photos, recordings from real experience | References to experience without proof | Claims of experience with no evidence |
| Exp05 | **Usage Duration** | Long-term experience evident (months/years) | Some experience but duration unclear | No indication of sustained engagement |
| Exp06 | **Problems Encountered** | Real problems and how they were solved | Brief mention of challenges | Only positive outcomes; no realism |
| Exp07 | **Before/After Comparison** | Measurable outcomes from applying advice | Qualitative before/after comparison | No outcome measurement |
| Exp08 | **Quantified Metrics** | Specific measurable results from experience | Some metrics but not specific | No measurable outcomes |
| Exp09 | **Repeated Testing** | Multiple trials or iterations documented | Single test documented | No testing evidence |
| Exp10 | **Limitations Acknowledged** | Honest about what didn't work or what limits apply | Brief caveats mentioned | Presents advice as universally applicable |

### Dimension 6: Expertise (Ept) — SEO

| ID | Item | Pass | Partial | Fail |
|---|---|---|---|---|
| Ept01 | **Author Identity** | Named author with verifiable identity | Author name but limited verifiability | Anonymous or no author attribution |
| Ept02 | **Credentials Display** | Relevant qualifications, certifications, or training visible | Some credentials but not prominently displayed | No credentials shown |
| Ept03 | **Professional Vocabulary** | Domain-specific terminology used correctly and naturally | Mostly correct terminology | Misused jargon or overly simplified |
| Ept04 | **Technical Depth** | Explains mechanisms, not just surface-level advice | Some technical explanation | Superficial coverage only |
| Ept05 | **Methodology Rigor** | Sound methodology when presenting findings or recommendations | Acceptable method but room for improvement | No methodology or flawed approach |
| Ept06 | **Edge Case Awareness** | Addresses exceptions, caveats, and non-obvious scenarios | Some edge cases mentioned | Only covers the happy path |
| Ept07 | **Historical Context** | Shows how the topic evolved over time | Brief historical reference | No historical grounding |
| Ept08 | **Reasoning Transparency** | Shows the reasoning behind recommendations (not just "do X") | Some reasoning but incomplete | Prescriptive without explanation |
| Ept09 | **Cross-domain Integration** | Connects insights from related fields | Mentions related domains | Siloed perspective |
| Ept10 | **Editorial Process** | Evidence of review, fact-checking, or editorial standards | Some quality signals | No editorial process evident |

### Dimension 7: Authoritativeness (A) — SEO

| ID | Item | Pass | Partial | Fail |
|---|---|---|---|---|
| A01 | **Backlink Profile** | Page/site has authoritative inbound links | Some backlinks but not from top-tier sources | No meaningful backlink profile |
| A02 | **Media Mentions** | Brand/author mentioned in authoritative publications | Some media coverage | No external media mentions |
| A03 | **Industry Awards** | Recognized awards, certifications, or honors | Nominated or industry participation | No industry recognition |
| A04 | **Publishing Record** | Consistent publishing track record in the domain | Some history but irregular | New or unproven publisher |
| A05 | **Brand Recognition** | Brand has search volume and name recognition | Some brand awareness | Unknown brand |
| A06 | **Social Proof** | Testimonials, case studies, user reviews | Some social proof | No social proof |
| A07 | **Knowledge Graph Presence** | Brand/author in Google Knowledge Graph or Wikidata | Partial presence (e.g., Wikidata stub only) | No Knowledge Graph presence |
| A08 | **Entity Consistency** | Consistent entity information across web (NAP, sameAs, profiles) | Mostly consistent with minor discrepancies | Inconsistent or conflicting entity data |
| A09 | **Partnership Signals** | Partnerships, collaborations, or endorsements from authorities | Some partnerships | No authority partnerships |
| A10 | **Community Standing** | Active participant in professional communities | Occasional community involvement | No community presence |

**Note**: A01–A10 and several T items require site-level or organizational data not always observable from a single page. When auditing a standalone page without site context, mark these as "N/A — requires site-level data" and exclude from the dimension average.

### Dimension 8: Trust (T) — SEO

| ID | Item | Pass | Partial | Fail |
|---|---|---|---|---|
| T01 | **Legal Compliance** | Privacy policy, terms of service, cookie consent present | Some legal pages but incomplete | No legal compliance pages |
| T02 | **Contact Transparency** | Multiple contact methods clearly accessible | Contact info present but hard to find | No contact information |
| T03 | **Security Standards** | HTTPS, security headers (HSTS), no mixed content | HTTPS but missing some security headers | HTTP or significant security issues |
| T04 | **Disclosure Statements** ⚠️ VETO | Sponsorship, affiliation, and conflict-of-interest disclosures present | Partial disclosures | No disclosures when required |
| T05 | **Editorial Policy** | Published editorial standards or review process | Implied standards but not published | No editorial standards |
| T06 | **Correction & Update Policy** | Visible correction/update history or policy | Updates mentioned but no formal policy | No correction policy; content appears abandoned |
| T07 | **Ad Experience** | Ads don't interfere with content consumption | Some ad interference but manageable | Ads overwhelm or obscure content |
| T08 | **Risk Disclaimers** | Appropriate disclaimers for health, financial, legal content | General disclaimers but not specific | No disclaimers where required (YMYL) |
| T09 | **Review Authenticity** | Reviews/testimonials appear genuine with verifiable details | Some reviews but authenticity questionable | Fake or purchased reviews |
| T10 | **Customer Support** | Accessible support channels (chat, email, phone) | Limited support options | No customer support evidence |

---

## GEO-First Items

These items have the strongest correlation with AI citation probability. Prioritize when optimizing specifically for AI search visibility.

| Priority | ID | Item | Why |
|---|---|---|---|
| 1 | C02 | Direct Answer | All AI engines extract from the first paragraph |
| 2 | C09 | FAQ Coverage | Directly matches AI follow-up queries |
| 3 | O03 | Data Tables | Most extractable structured format for AI |
| 4 | O05 | Schema Markup | Helps AI understand content type and structure |
| 5 | E01 | Original Data | AI prefers exclusive, verifiable sources |
| 6 | O02 | Summary Box | First choice for AI summary citations |

**All GEO-First Items**: C02, C04, C05, C07, C08, C09 | O02, O03, O04, O05, O06, O09 | R01, R02, R03, R04, R05, R07, R09 | E01, E02, E03, E04, E06, E08, E09, E10 | Exp10 | Ept05, Ept08 | A08

---

## AI Engine Preferences

Different AI platforms weight different CORE-EEAT items. Use this to prioritize by target platform.

| Engine | Priority CORE-EEAT Items | Why |
|---|---|---|
| **Google AI Overviews** | C02, O03, O05, C09 | Extracts structured answers from well-organized, schema-rich content |
| **ChatGPT Search** | C02, R01, R02, E01 | Prefers quotable facts with precise data and original sources |
| **Perplexity** | E01, R03, R05, Ept05 | Values original data, primary sources, and methodological rigor |
| **Claude** | R04, Ept08, R03, Exp10 | Prioritizes evidence-backed reasoning and acknowledged limitations |

---

## Audit Workflow

1. Read the content in full
2. Score each of the 80 items as Pass (10) / Partial (5) / Fail (0) / N/A
3. Calculate dimension averages (excluding N/A items)
4. Check veto items — if any Fail, cap overall at "Needs Improvement"
5. Apply content-type weights to calculate Total Score
6. Calculate GEO Score (C+O+R+E average) and SEO Score (Exp+Ept+A+T average)
7. Identify weakest dimension — this is the highest-leverage fix
8. Generate prioritized improvement plan sorted by `weight × points lost`

### Rating Scale

| Score | Rating | Interpretation |
|---|---|---|
| 90–100 | Excellent | Publication-ready; strong AI citation candidate |
| 75–89 | Good | Minor improvements needed; competitive |
| 60–74 | Adequate | Significant gaps; not competitive for head terms |
| 40–59 | Needs Improvement | Major revision required |
| 0–39 | Poor | Complete rewrite recommended |

### Output Template

```
# CORE-EEAT Audit — [Page Title]
Content Type: [type] | URL: [url] | Date: [date]

## Scores
| Dimension | Score | Rating |
|---|---|---|
| C — Contextual Clarity | XX/100 | ✅/⚠️/❌ |
| O — Organization | XX/100 | ✅/⚠️/❌ |
| R — Referenceability | XX/100 | ✅/⚠️/❌ |
| E — Exclusivity | XX/100 | ✅/⚠️/❌ |
| Exp — Experience | XX/100 | ✅/⚠️/❌ |
| Ept — Expertise | XX/100 | ✅/⚠️/❌ |
| A — Authoritativeness | XX/100 | ✅/⚠️/❌ |
| T — Trust | XX/100 | ✅/⚠️/❌ |

**GEO Score**: XX/100 | **SEO Score**: XX/100 | **Total**: XX/100

## Veto Check
- C01 Intent Alignment: [Pass/Fail]
- R10 Content Consistency: [Pass/Fail]
- T04 Disclosure Statements: [Pass/Fail]

## Top 5 Priority Improvements
[Sorted by weight × points lost]
```
