<!-- Updated: 2026-03-22 | Review: 2026-09-22 -->

# Content Quality & AI Citation Analysis
## Updated: March 2026

**Contents:** Content Quality Score · Word Count Floors · On-Page Optimization · AI Citation Readiness · Content Freshness · Content Pruning & Refresh · AI Content Assessment · Readability Guidelines · Content Audit Scoring · Freshness Thresholds

---

## Content Quality Score Components

| Category | Weight | What to Assess |
|---|---|---|
| E-E-A-T signals | 35% | See `eeat-framework.md` |
| On-page optimization | 25% | Title, headings, keyword placement, meta |
| Depth & comprehensiveness | 20% | Coverage completeness, original value |
| AI citation readiness | 10% | Passage structure, answer-first format |
| Freshness | 10% | Publication date, last-updated, recency |

---

## Word Count Floors

These are **coverage floors**, not optimization targets. Google has confirmed word count is NOT a direct ranking factor. A 500-word page that fully answers the query outperforms a 2,000-word page that doesn't. Use these as minimums for adequate topical coverage.

| Page Type | Minimum Words |
|---|---|
| Blog post / long-form guide | 1,500 |
| Service page | 800 |
| Homepage | 500 |
| Product page | 300 (400+ for complex products) |
| About page | 400 |
| Location page | 500-600 |

---

## On-Page Optimization

### Title Tag
- Primary keyword in title
- Under 60 characters (prevents truncation in SERPs)
- Compelling — includes value proposition or emotional hook
- Unique across all pages

### Meta Description
- 150-160 characters
- Includes primary keyword naturally
- Clear value proposition with CTA implied
- Unique per page

### Heading Structure
- One H1 per page, includes primary keyword
- H2s for main sections (2-5 is typical)
- H3s for subsections
- No skipped levels (H1 → H3 without H2)
- Question-based headings where appropriate (boosts AI citability)

### Keyword Optimization
- Primary keyword in H1, first 100 words of body
- Semantic variations and related terms used naturally throughout
- No keyword stuffing (density > 3-4% is a warning sign)
- LSI keywords / related terms: check competitor content for vocabulary to include

### Internal Linking
- 3-5 relevant internal links per 1,000 words
- Descriptive anchor text (not "click here" or "read more")
- Links to topically related content (pillar → cluster and cluster → pillar)
- No orphan pages (every page has at least one internal link pointing to it)

### External Linking
- Cite authoritative primary sources
- 2-5 external links per long-form post
- Open external links in new tab (UX standard)
- Link to specific pages, not just homepages

---

## AI Citation Readiness

**44.2% of AI citations come from the first 30% of content.** Front-loading answers is the highest-leverage writing change.

### Answer-First Structure

For any post or section targeting a query:
1. **Lead with the answer** (first 1-3 sentences)
2. **Provide evidence/context** (body of section)
3. **Expand with examples/data** (supporting detail)

Avoid: "In this article, we will explore..." preambles that bury the answer.

### Citability Scoring

| Signal | Strong | Weak |
|---|---|---|
| **Passage length** | 134-167 words (optimal for extraction) | Walls of text (500+ word paragraphs) |
| **Answer placement** | Direct answer in first 40-60 words of each section | Answer buried 200+ words in |
| **Fact density** | 5-8 statistics/citations per article (+40% AI visibility) | Vague claims without supporting data |
| **Quotability** | Clear, standalone sentences with specific claims | Opinion-heavy, context-dependent statements |
| **Definition patterns** | "X is...", "X refers to...", "X means..." | Assumed knowledge, no clear definition |

### Question-Based Headings

Convert topic headings into question headings to match how people search:

| Instead of... | Use... |
|---|---|
| "Benefits of PLG" | "What are the benefits of product-led growth?" |
| "Implementation Steps" | "How do you implement a PLG strategy?" |
| "Pricing Models" | "What pricing model works best for PLG?" |

### FAQ Section Format

Add a FAQ section at the end of long-form posts (especially for GEO):
```
## Frequently Asked Questions

### What is [topic]?
[Direct answer in 1-3 sentences, 50-100 words. Self-contained answer block.]

### How does [topic] work?
[Direct answer...]

### What is the difference between [A] and [B]?
[Direct comparison...]
```

---

## Content Freshness

- Publication date visible on all articles
- Last-updated date shown when content has been meaningfully revised
- Flag content older than 12 months for fast-changing topics (technical, industry news, statistics)
- Update key statistics annually — stale numbers reduce AI citability

**GEO impact:** Content updated within 2 months receives 28% more AI citations than older content. ChatGPT particularly penalizes stale information.

### What "Meaningfully Revised" Means

Content is **meaningfully revised** only when:
- **Adding new data/statistics** — incorporating recent studies, market research, or updated metrics
- **Adding a new section** — covering recent developments, new tools, industry shifts, or emerging best practices
- **Substantially rewriting an outdated section** — not just tweaking a paragraph, but rewriting 200+ words to reflect current reality
- **Updating all referenced tools/products** — replacing discontinued tools, adding new alternatives, updating pricing/features

**Does NOT count as meaningful revision:**
- Fixing typos, grammar, or formatting only
- Updating publication dates or timestamps without substantive changes
- Minor copy edits
- Rearranging existing text without new information

---

## Content Pruning & Refresh

Regularly audit your content inventory to identify pages that need attention. Use the categories below to determine whether to refresh, prune, consolidate, or keep each page.

### Categorization Framework

| Category | Criteria | Action Priority |
|---|---|---|
| **Keep (No Action)** | Page is current, ranks well, has strong internal links and backlinks, high E-E-A-T signals, updated within freshness thresholds | Monitor only; audit annually |
| **Refresh** | Page covers good topic, has some backlinks/internal links, but is outdated, missing new data, or could rank higher with updated content | Update content immediately; republish with new last-updated date |
| **Consolidate** | Multiple thin pages cover similar topics or keywords; better served by one comprehensive page | Merge into one strong page; 301 redirect obsolete URLs |
| **Prune** | Page has minimal traffic, no backlinks, thin content, doesn't align with current strategy, and is not linked internally or externally | 301 redirect to related page OR delete with proper 404 handling if no backlinks exist |

### Freshness Thresholds by Content Type

Use these guidelines to flag content for review. Crossing the threshold doesn't automatically mean prune — it means evaluate and refresh if the topic is still relevant.

| Content Type | Freshness Threshold | Why It Matters |
|---|---|---|
| **News / Events / Announcements** | 30-90 days | Readers expect very recent information; stale news is low-value and signals outdated coverage |
| **Data / Statistics / Industry Reports** | 6-12 months | Outdated numbers reduce credibility and AI citability; stats older than 18 months are high-risk |
| **How-To Guides / Tutorials** | 12-18 months | Tools, screenshots, steps change; guides older than 2 years often contain outdated instructions |
| **Comparison Pages / Product Reviews** | 12 months | New products emerge, features change, pricing updates; stale comparisons mislead readers |
| **Evergreen Pillar Content** | 18-24 months | Foundational topics age slower, but need periodic fact-checks and new examples |
| **Technical / API Documentation** | 6-12 months (depending on API churn) | Outdated docs cause implementation failures; treat as critical |
| **Industry Trends / Analysis** | 12 months | Trends shift; last year's analysis may miss emerging patterns |

### Step-by-Step Process by Category

#### Refresh Pages

**When to use:** Page is fundamentally sound, ranks for target keyword, has backlinks/internal links, but needs updated data or new sections.

Steps:
1. Identify what's outdated: missing recent data, tools no longer available, advice that's changed, new competitors/alternatives
2. **Add new section** covering developments since publication (e.g., "Updates for 2025" or "Recent Developments")
3. **Replace outdated statistics** with current data; cite new sources
4. **Update tool/product references** — remove discontinued tools, add new alternatives with current pricing/features
5. **Rewrite 1-2 key sections** if the landscape has shifted significantly (e.g., AI adoption has changed best practices)
6. Keep original author + byline; add "Updated [date]" below title or in metadata
7. **Republish with new last-updated date** — does NOT create a new page, stays at same URL
8. **Update internal links** — add links from related content, ensure this page links to new companion content if created
9. **Preserve all backlinks** — URL never changes, so external links continue to flow

**Expected outcome:** Refresh typically adds 15-30% traffic lift within 4-6 weeks.

#### Prune Pages

**When to use:** Page has minimal traffic, no external backlinks, weak internal linking, thin content, and doesn't fit current strategy.

**CRITICAL WARNING:** Never prune pages with external backlinks without redirecting. Even one backlink is a signal of external interest; losing that link equity damages your site's authority.

Steps:
1. **Check for external backlinks** using Ahrefs, SEMrush, or Google Search Console. If ANY external links point to this URL, DO NOT delete it.
2. **If backlinks exist:** 301 redirect to the most relevant related page (preserve link equity)
3. **If no backlinks exist AND no internal links:** evaluate for deletion:
   - Check Google Search Console for any impressions (even 1-2 impressions = some user interest)
   - If zero impressions and zero traffic: safe to delete with proper 404 handling
   - If page appears in SERPs for any keyword: do NOT prune; refresh instead
4. **Before removing:** check if page is referenced in published outreach, guides, or external documentation
5. **Execute deletion or redirect:**
   - **If redirecting:** 301 to related content; monitor for 404s in GSC for 6 months
   - **If deleting:** ensure 404 page is helpful; update XML sitemap; monitor GSC for missing pages
6. **Update internal links** — remove or redirect any internal links that pointed to pruned page

**Red flags (do NOT prune):**
- Page has ANY external backlinks
- Page gets ANY traffic (even 1 visit/month)
- Page ranks for ANY keyword (even position 50+)
- Page has internal links from pillar or high-authority pages
- Topic is on roadmap or part of planned content expansion

#### Consolidate Pages

**When to use:** Multiple pages target the same keyword or topic, creating internal competition and cannibalization.

Steps:
1. **Identify clusters** of related pages (e.g., three separate posts on "email marketing best practices" with slight variations)
2. **Evaluate quality:** which page has:
   - Better E-E-A-T signals
   - More internal links
   - More external backlinks
   - Better structure/comprehensiveness
   - Higher traffic
3. **Merge weaker pages into stronger page:**
   - Extract unique sections/data from weaker pages
   - Integrate into stronger page under appropriate headings
   - Expand weak page from 1,500 words to 2,500+ words with consolidated content
4. **Create 301 redirects** for all merged pages → consolidated page
5. **Update internal links:** relink all pages that linked to old URLs to the new consolidated page
6. **Update external references:** outreach to high-authority external sites linking to old URLs; request link update (optional but high-value)
7. **Delete old files** after confirming redirects are working (wait 2-4 weeks, check GSC for crawl)

**Expected outcome:** Consolidation typically increases domain authority flow to the topic cluster and improves consolidated page's ranking.

---

## Answer-First Structure vs. Depth Trade-Off

### The Core Principle

**Word count alone does NOT determine ranking quality.** A focused, answer-first page can outrank lengthy walls of text when it properly matches search intent.

### Answer-First Wins (Informational Intent)

When search intent is primarily **informational** and users want a quick, direct answer:
- **500-word answer-first article outranks 2,000-word wall of text** if the 500-word article directly answers the query in the first 50-100 words
- **44.2% of AI citations come from the first 30% of content** — front-loading the answer boosts AI visibility dramatically
- **Example:** Query: "What is product-led growth?" — a crisp 500-word page with answer-first structure beats a 2,500-word article that buries the definition

**Structure for informational queries:**
1. **Direct answer in 40-60 words** (first paragraph)
2. **2-3 supporting details** (next 200-300 words)
3. **FAQ section** with 3-5 common follow-ups
4. **Done** — no need to pad for length

### Depth + Answer-First Wins (Competitive, Comprehensive Topics)

When the topic is **highly competitive** or users need **comprehensive, in-depth coverage**:
- **Depth + answer-first structure is optimal** — answer immediately (first 50-100 words), then elaborate with 2,000+ words of depth
- Search engines reward both directness AND comprehensiveness for high-intent, complex topics
- **Example:** Query: "How to implement a product-led growth strategy?" — a 2,000+ word guide with answer-first structure (answer in first paragraph, then step-by-step details) outranks shorter articles

**Structure for comprehensive/competitive queries:**
1. **Direct answer in 50-100 words** (first paragraph/section)
2. **Expand with 5-8 main sections** (step-by-step, detailed examples, case studies)
3. **Support with statistics, data, and original insights** (1,800-2,500 total words)
4. **Internal links** to related pillar/cluster content
5. **FAQ section** covering edge cases and advanced questions

### How to Determine Which Approach

Before writing:
1. **Search the keyword** and analyze top 5 results:
   - Are most results 500-800 words? → answer-first is optimal
   - Are most results 2,000+ words? → use depth + answer-first
2. **Check search intent:** "What is...", "How do...", "Why...", "When..." = often answer-first wins; "Best practices for...", "Complete guide to..." = depth usually necessary
3. **Check your target keyword difficulty:** high competition (KD >60) almost always requires depth + answer-first; low competition (KD <30) can win with focused answer-first

### Key Takeaway

**Answer-first is non-negotiable; depth is situational.**
- Always lead with the answer (first 40-100 words)
- Expand only if competitive landscape or search intent demands comprehensiveness
- Never pad word count for ranking purposes — match answer depth to user need

---

## AI Content Assessment (September 2025 QRG)

Google raters now formally assess whether content appears AI-generated.

### Acceptable AI Content
- Demonstrates genuine E-E-A-T (human perspective, not just AI-generated)
- Provides unique value beyond what AI can independently generate
- Has visible author with real credentials
- Contains original insights, first-hand experience, or proprietary data

### Low-Quality AI Content Markers (Penalized)
- Generic phrasing: "In today's competitive landscape...", "It's important to note that..."
- No original insight — just rephrases what's commonly known
- Repetitive structure across multiple pages
- No author attribution
- Factual inaccuracies from AI hallucination
- No specific examples, statistics, or first-hand data

---

## Readability Guidelines

These are guidelines, not ranking factors:
- Sentence length: average 15-20 words
- Paragraph length: 2-4 sentences per paragraph
- Reading level: match your target audience (technical topics can be more complex; general business = ~8th grade)
- Active voice preferred over passive
- Short intro: first paragraph answers the core question, no throat-clearing

---

## Image Optimization

- **Alt text**: descriptive, includes relevant keyword naturally; not keyword-stuffed
- **File names**: descriptive hyphenated names (not `IMG_001.jpg`)
- **Format**: WebP preferred for photographs; SVG for icons/logos
- **Compression**: use modern compression (no unnecessarily large files)
- **Dimensions**: specify `width` and `height` attributes to prevent CLS
- **Lazy loading**: `loading="lazy"` for below-the-fold images
- **Featured/hero images**: always present for GEO (multi-modal signal)

---

## Content Audit Scoring Matrix

| Score | Description |
|---|---|
| 90-100 | Comprehensive, well-structured, strong E-E-A-T, excellent AI citability |
| 70-89 | Good coverage, clear structure, solid E-E-A-T signals |
| 50-69 | Adequate coverage but gaps in E-E-A-T or structure |
| 30-49 | Thin content or significant structural issues |
| 0-29 | Thin, duplicate, or potentially penalized content |

---

## Freshness Thresholds by Content Type

| Content Type | Refresh Frequency | Prune Signal |
|---|---|---|
| Data / statistics posts | Every 6–12 months | Data is > 2 years old with no update |
| How-to guides | Every 12–18 months | Tool or process covered no longer exists |
| Comparison / review pages | Every 12 months | Product discontinued or pricing materially changed |
| News / event-specific | 30–90 days | One-time event with no ongoing search demand |
| Evergreen pillar pages | Every 18–24 months | Rarely prune — update and strengthen |
