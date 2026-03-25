<!-- Updated: 2026-03-22 | Review: 2026-09-22 -->

# GEO Signals & AI Search Optimization Reference
## Updated: March 2026

**Contents:** 2026 AI Search Landscape · GEO Health Score · Citability Signals · Structural Readability · Authority & Brand Signals · Technical Accessibility · Multi-Modal Content · Platform-Specific Optimization · GEO Quick Wins · Brand Mention Strategy · Wikipedia & Wikidata Entity Setup · Passage Indexing Optimization · DataForSEO MCP Integration · GEO Error Handling

---

## 2026 AI Search Landscape

| Platform | Reach | Query Coverage | Key Insight |
|---|---|---|---|
| **Google AI Overviews** | 1.5B users/month | 48% of queries (projected 70-80% by end 2026) | Citations from top-10 pages dropped from 76% to 38% in 2025 — ranking rank matters less |
| **Google AI Mode** | 180+ countries (launched May 2025) | Separate search tab | Zero organic blue links — AI citation is the ONLY visibility mechanism |
| **ChatGPT Search** | 900M weekly active users | All queries | 85% of retrieved pages are never cited; no referral traffic header |
| **Perplexity** | 500M+ queries/month | All queries | Sends trackable referral traffic in GA; cites Reddit (46.7%) and Wikipedia heavily |
| **Bing Copilot** | Integrated in Bing | All queries | Bing index authority; supports IndexNow for faster indexing |

**AI-referred sessions grew 527% year-over-year** (Jan–May 2025, SparkToro/Previsible).

**Platform citation overlap**: Only 11–13.7% of domains cited by both ChatGPT and Google AI Overviews for the same query. Platform-specific optimization is essential.

---

## GEO Health Score (0-100)

| Dimension | Weight | Optimal Signal |
|---|---|---|
| Citability | 25% | 134-167 word self-contained answer blocks, direct answer in first 40-60 words of section |
| Structural Readability | 20% | Clean H1→H2→H3, question-based headings, 2-4 sentence paragraphs, tables, lists |
| Authority & Brand Signals | 20% | Author bio + credentials, publication dates, citations, entity presence across platforms |
| Technical Accessibility | 20% | AI crawlers allowed in robots.txt, server-side rendering, llms.txt present |
| Multi-Modal Content | 15% | Text + images + video + structured data (78% of cited sources combine these) |

### Platform-to-Dimension Mapping

Different AI platforms prioritize different GEO dimensions. Use this matrix to allocate optimization effort by platform importance for your strategy.

| Platform | Citability (25%) | Structural Readability (20%) | Authority & Brand (20%) | Technical Accessibility (20%) | Multi-Modal (15%) |
|---|---|---|---|---|---|
| **Google AI Overviews** | Critical (44.2% of citations in first 30%) | High — question-based H2/H3 | High — entity signals matter | Essential — SEO foundational | Moderate — images boost |
| **Google AI Mode** | High — deep, comprehensive | Critical — multi-turn requires clarity | High — expertise signals | Essential — server-side rendering | High — images + video |
| **ChatGPT Search** | High — quotable facts | Moderate — less structured | Critical — 3× more important than backlinks; Wikipedia/Reddit favored | Essential — Allow OAI-SearchBot | Moderate |
| **Perplexity** | Critical — factual, data-driven | High — Q&A format, definitive opens | High — brand mentions tracked | Essential — Allow PerplexityBot | Moderate — GA trackable |
| **Bing Copilot** | High | Moderate | Moderate | Essential — IndexNow, HTTPS | Moderate |

**Key Takeaways**:
- **If optimizing for all platforms**: Prioritize Citability (25%) and Technical Accessibility (20%) universally
- **If ChatGPT Search is priority**: Over-invest in Authority & Brand (Wikipedia, Reddit, LinkedIn presence)
- **If Google AI Mode is priority**: Over-invest in Structural Readability and Multi-Modal content
- **If Perplexity is priority**: Focus on Citability with fresh data and trackable Authority signals

---

## Citability Signals (Dimension 1: 25%)

**Optimal passage length: 134-167 words** for AI citation extraction.

### Strong Citability Signals
- Clear, quotable sentences with specific facts, statistics, or data
- Self-contained answer blocks (extractable without surrounding context)
- Direct answer in first 40-60 words of each section
- Claims attributed to specific sources ("According to [Study], X% of...")
- Definition patterns: "X is...", "X refers to...", "X means..."
- Unique data points not found elsewhere on the web

### Weak Citability Signals
- Vague, general statements without specifics
- Opinion without evidence or sourcing
- Conclusions buried 3+ paragraphs in
- No measurable/verifiable data points

### Citation Placement Data (2025)
- **First 30% of content**: 44.2% of all LLM citations
- **Middle 30-70%**: 31.1% of citations
- **Final 30%**: 24.7% of citations

**Implication**: Lead with the answer, not with context. Top-loading key information is the single highest-leverage writing change.

---

## Structural Readability (Dimension 2: 20%)

47% of AI Overview citations come from pages ranking **below position 5** — demonstrating that AI selection logic differs from traditional ranking.

### Strong Structural Signals
- Clean heading hierarchy: H1 (one per page) → H2 (main sections) → H3 (subsections)
- Question-based headings that match query patterns: "How does X work?", "What is the difference between X and Y?"
- Short paragraphs: 2-4 sentences, one idea per paragraph
- Tables for comparative information (formats, pricing, options)
- Numbered/bulleted lists for steps, features, or multi-item content
- FAQ sections with clear Q&A format

### Weak Structural Signals
- Walls of text with no structural breaks
- Inconsistent or skipped heading levels (H1 → H3 without H2)
- No lists, tables, or visual structure
- Important answers buried inside long paragraphs

---

## Authority & Brand Signals (Dimension 3: 20%)

### Brand Mentions vs. Backlinks

**Brand mentions are 3× more predictive of AI visibility than backlinks.**

| Signal | Correlation with AI Citations |
|---|---|
| YouTube mentions/descriptions | ~0.737 (strongest) |
| Reddit community presence | High (0.6+) |
| Wikipedia / Wikidata entity | High |
| Web mentions (aggregate) | 0.664 |
| LinkedIn articles + presence | Moderate |
| Domain Rating / Backlinks | ~0.266 (weak) |

**48% of all AI citations** come from user-generated/community sources (Reddit, LinkedIn, Wikipedia, YouTube, arXiv).

**<20% of brands** achieve both frequent mentions AND consistent citations (the "Mention-Source Divide").

### Brand Mention Channels (Priority Order)
1. **YouTube** — create video content; get mentioned in others' videos
2. **Reddit** — genuine participation in relevant subreddits (r/ProductManagement, r/SaaS, r/startups, etc.)
3. **Wikipedia / Wikidata** — create entity entry with citations; link to your site
4. **LinkedIn** — publish articles (not just posts) that LinkedIn indexes as standalone pages
5. **Third-party review sites** — G2, Trustpilot, Capterra, Yelp (3× citation increase for brands with profiles)
6. **arXiv / research** — for scientific/technical domains

### Wikipedia & Wikidata Strategy (5-Step Process)

Wikipedia and Wikidata entities are among the highest-signal sources for AI citations. This 5-step process maximizes impact while respecting notability guidelines.

**Step 1: Check Wikidata First**
- Search for your brand/person on Wikidata.org
- If a stub exists, verify accuracy and completeness
- If none exists, create a Wikidata entity with: name, entity type (Q-code), founding date, official website, official social links (Twitter, LinkedIn, YouTube)
- Wikidata entries require minimal editorial scrutiny and serve as the foundation for Wikipedia

**Step 2: Assess Wikipedia Notability**
- Wikipedia requires demonstrable notability via independent, reliable sources
- You need 3+ substantial citations in publications with editorial standards (journalists, academic presses, established industry outlets)
- Community-generated content (your own Reddit posts, LinkedIn) does NOT count
- Award nominations, press coverage, industry recognition, and academic mentions count

**Step 3: If Notable — Create Article**
- Write article in neutral, encyclopedic tone (no promotional language)
- Structure: Lede (summary paragraph), History, Products/Services, Key Personnel, Impact/Recognition, External Links
- Include {{cite}} tags linking to independent, high-authority sources
- Citations should come from news outlets, industry publications, academic papers, and established directories
- Avoid self-promotion; focus on factual, verifiable achievements

**Step 4: If Not Notable — Earn Citations First**
- Before attempting Wikipedia, pursue digital PR and thought leadership:
  - Guest posts on industry-recognized publications
  - Speaking at conferences with documented attendance
  - Features in trade publications, analyst reports, or industry reviews
  - Academic case studies or research partnerships
  - Awards and recognitions from recognized bodies
- Once you accumulate 3+ independent citations, revisit Wikipedia eligibility

**Step 5: Keep Wikidata Updated**
- Update quarterly: current CEO, key products, employee count, major partnerships
- Add official social links (Twitter, LinkedIn, YouTube) to Wikidata
- Link to Wikipedia article in Wikidata when created
- Monitor for user edits; maintain accuracy without over-editing (avoid edit-warring)

---

### E-E-A-T Authority Signals
- Author byline with credentials visible on every post
- Detailed author bio with relevant experience + external links (LinkedIn, publications)
- Publication date AND last-updated date visible
- Citations to primary sources (studies, official docs, original data)
- Expert quotes with name + title
- Organization/brand described with credentials

---

## Technical Accessibility (Dimension 4: 20%)

### AI Crawler Management

**AI crawlers do NOT execute JavaScript** — content that requires JS to render is invisible to AI crawlers.

| Crawler | Owner | Purpose | Recommendation |
|---|---|---|---|
| GPTBot | OpenAI | ChatGPT model training | **Allow** — enables ChatGPT to learn your content |
| OAI-SearchBot | OpenAI | ChatGPT Search index | **Always allow** — needed for ChatGPT Search citations |
| ChatGPT-User | OpenAI | ChatGPT browsing | **Always allow** — real-time browsing citations |
| ClaudeBot | Anthropic | Claude training | **Allow** — brand awareness |
| PerplexityBot | Perplexity | Perplexity index | **Always allow** — essential for Perplexity citations |
| Google-Extended | Google | Gemini AI training | Optional block — does NOT affect Google Search or AI Overviews |
| Bytespider | ByteDance | TikTok AI | Optional |
| CCBot | Common Crawl | Open training dataset | Optional block |
| anthropic-ai | Anthropic | Claude training | Optional |
| cohere-ai | Cohere | Cohere models | Optional |

**Key distinction**: Blocking `Google-Extended` prevents Gemini training but does NOT affect Googlebot, Google Search rankings, or AI Overviews. Blocking `GPTBot` blocks training but does NOT block `OAI-SearchBot` (search) or `ChatGPT-User` (browsing).

### robots.txt — Recommended Configuration for AI Visibility
```
# Allow all AI search crawlers
User-agent: GPTBot
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: ClaudeBot
Allow: /

# Block AI training-only crawlers (optional)
User-agent: CCBot
Disallow: /

# Standard crawlers
User-agent: *
Allow: /
```

### llms.txt Standard

**Status**: Proposed standard, not officially adopted by Google/OpenAI/Anthropic. Current research shows no proven citation impact.

**Recommendation**: Implement as a low-cost hygiene step — it signals intent to AI crawlers and may help as the standard matures, but do not prioritize it over citability, brand signals, or technical accessibility. Current research shows no proven citation impact.

**Implemented by**: Anthropic (Claude docs), Cloudflare, Stripe

**Format** (place at `/llms.txt` in domain root):
```
# [Site Name]
> [One-line description]

## Key Pages
- [Page title](url): [What it covers]
- [Article](url): [Brief description]

## About the Author/Organization
- [Name]: [Title and expertise]
- Contact: [Email or contact URL]
```

### RSL 1.0 (Really Simple Licensing)

**Status**: Official standard published December 10, 2025. 1,500+ media organizations endorsing.

RSL defines machine-readable AI content licensing terms via `robots.txt` directives:
- **ai-all**: Permits all AI usage (training + inference + indexing)
- **ai-input**: Permits AI input processing only
- **ai-index**: Permits indexing for AI search only

Useful for organizations wanting to differentiate between allowing AI Search citations (beneficial) and AI training (revenue concern).

---

## Multi-Modal Content (Dimension 5: 15%)

Content with multi-modal elements sees **156% higher AI selection rates**.

**78% of AI-cited sources** combine text, images, and structured data.

### What to Include
- Feature images / hero images (with descriptive alt text)
- Charts and graphs (especially for statistics and comparisons)
- Infographics (complex information in visual format)
- Embedded video content (with VideoObject schema)
- Interactive tools or calculators (highest citation signal)
- Before/after examples (screenshots, case study images)

---

## Platform-Specific Optimization

### Google AI Overviews
- Ranking in top-10 is still a prerequisite (92% of citations from top-10 historically; now 38%)
- Passage-level optimization matters more than page-level
- Question-based H2/H3 headings closely match AI Overview triggers
- First 30% of content provides 44.2% of citations — front-load your answers
- Semantic completeness (r=0.89): self-contained sections score 4.2× more citations

### Google AI Mode (launched May 2025)
- Conversational, multi-turn — requires comprehensive depth
- "Deep Search" runs 100+ sub-searches for complex queries
- No organic blue links — AI citation is the only visibility
- Optimize for multi-step, research-style queries
- Images and video inputs supported (multi-modal input)

### ChatGPT Search
- Citations heavily favor Wikipedia (47.9%), Reddit (11.3%), and LinkedIn
- No referral traffic header — cannot track via GA
- Brand mentions and entity strength matter more than traditional SEO
- Content freshness: update within 2 months for 28% more citations
- 85% of retrieved pages are NEVER cited — quality threshold above retrieval

### Perplexity
- Content freshness is the #1 factor — newly published content indexed within hours-days
- Sends trackable referral traffic (can monitor in GA)
- Q&A format headings and definitive opening paragraphs
- AI, science, marketing content gets 3× ranking multiplier
- Uses RAG (Retrieval-Augmented Generation) — factual, well-structured content preferred

### Bing Copilot
- Bing index authority (same as Bing SEO)
- IndexNow support for faster indexing of new/updated content
- Security headers and HTTPS required

---

## GEO Quick Wins (High Impact, Low Effort)

1. Add "What is [topic]?" definition in first 60 words of each post
2. Create 134-167 word self-contained answer blocks at start of each H2 section
3. Convert paragraph-heavy sections to Q&A format headings
4. Include 5-8 statistics with source attribution per article (40% AI visibility boost)
5. Add publication date AND last-updated date to every post
6. Ensure AI crawlers (GPTBot, OAI-SearchBot, PerplexityBot) are allowed in robots.txt
7. Create author bio page with credentials, LinkedIn link, and external mentions
8. Add Article/BlogPosting JSON-LD schema to all posts

## GEO Medium Effort

1. Create `/llms.txt` file
2. Expand author bio: years of experience, companies, publications, external links
3. Build entity presence: LinkedIn articles, Reddit participation, YouTube channel
4. Create Wikidata/Wikipedia entity for brand/key people
5. Publish comparison tables on every decision-making post
6. Add FAQ sections to top 5 long-form guides
7. Pursue 3-5 guest posts/bylines on high-DA publications in your niche

## GEO High Impact

1. Create original research/survey ("State of [Industry] 2026") — most-cited content type
2. Build YouTube channel with educational content on your core topics
3. Establish Wikipedia presence for brand and key people
4. Develop interactive tools or calculators
5. Achieve 32,000+ referring domains (3.5× citation probability threshold)

---

## Brand Mention Strategy (Full Correlation Data)

Ahrefs/75k brand study: brand mention correlation with AI citations = **0.664** vs. backlinks = **0.218**. Brand mentions are 3× more powerful than backlinks for AI citation.

**Priority channels (highest to lowest correlation):**

| Channel | AI Citation Correlation | Action |
|---|---|---|
| **YouTube** | ~0.737 (highest) | Educational explainers on core topics |
| **Reddit** | High | Contribute to niche subreddits (r/microdosing, etc.) |
| **Wikipedia/Wikidata** | High | Wikidata stub + Wikipedia article if notable |
| **LinkedIn articles** | Medium | Thought leadership from author profiles |
| **G2, Trustpilot, Capterra** | Medium | Third-party review profiles |

For each channel with zero presence, create a plan to establish it. YouTube and Reddit drive the highest AI citation correlation — prioritize first.

## Wikipedia & Wikidata Entity Setup (Full Steps)

Wikipedia and Wikidata presence correlates strongly with AI citations — both ChatGPT and Perplexity pull heavily from Wikipedia.

1. **Check Wikidata first** — Search wikidata.org for the brand. If no entry: create a Wikidata stub (brand name, type, founding date, website, official social links). Takes under an hour and alone can improve AI citation likelihood.
2. **Assess Wikipedia notability** — Wikipedia requires substantial coverage in 3+ independent, reliable sources with editorial standards (not press releases or self-published content).
3. **If notable** — Create a Wikipedia article with neutral tone, citing only independent reliable sources. No promotional language — it will be deleted.
4. **If not yet notable** — Earn 3+ substantial independent citations in publications with editorial standards. Once met, revisit Wikipedia.
5. **Keep Wikidata current** — Add current CEO, products, founding year, employee count, and official social links. AI models retrieve Wikidata structured facts directly.

## Passage Indexing Optimization

Google Passage Indexing (active since 2021) ranks individual passages independently from the full page. It's also the primary mechanism for AI citation of specific answers — both systems prefer the same structure.

**Rules for passage-optimized content:**
1. Each H2 block should be **self-contained** — answers one clear question without requiring context from other sections.
2. **Optimal passage length: 100–200 words per block** — sweet spot for both Passage Indexing and AI citation (confirmed citability range: 134–167 words).
3. **No pronoun-heavy openings** — never start a section with "It" or "This" referring to a previous section. Start with the full subject ("Email marketing automation is...").
4. **Question → Direct Answer structure** — question-phrased H2/H3 immediately followed by a direct answer in the first sentence.

| Scenario | Google Behavior |
|---|---|
| Strong overall page, weak section | Full page ranks |
| Weak overall page, one excellent section | That passage can rank independently |
| Long FAQ page with 20 Q&As | Individual Q&A passages rank independently |

---

## DataForSEO MCP Integration (Optional)

If DataForSEO MCP tools are available in the environment, use them for live GEO visibility checks:

| Tool | Purpose |
|---|---|
| `ai_optimization_chat_gpt_scraper` | Check what ChatGPT web search returns for target queries — real-time GEO visibility check |
| `ai_opt_llm_ment_search` | Track LLM mentions of a brand across AI platforms |
| `ai_opt_llm_ment_top_domains` | Identify top-cited domains for target queries across AI platforms |

These provide ground-truth data that supplements the structural analysis. If not available, rely on manual ChatGPT/Perplexity searches for the 3–5 target keywords.

---

## Research-Backed GEO Techniques (Princeton, KDD 2024)

Empirical data from Princeton's Generative Engine Optimization study on specific technique effectiveness:

| Technique | AI Visibility Boost | How to Apply |
|---|---|---|
| **Cite authoritative sources** | +40% | Add references with links to studies, official docs |
| **Add specific statistics** | +37% | Include precise numbers with named sources |
| **Add expert quotations** | +30% | Expert quotes with name and title attribution |
| **Use authoritative tone** | +25% | Write with demonstrated expertise; avoid hedging |
| **Improve clarity** | +20% | Simplify complex concepts; short sentences |
| **Use technical terminology** | +18% | Domain-specific terms used correctly |
| **Increase vocabulary diversity** | +15% | Avoid repetitive phrasing; use varied language |
| **Fluency optimization** | +15–30% | Improve readability and natural flow |
| ~~Keyword stuffing~~ | **-10%** | **Actively hurts AI visibility** |

**Best combination**: Fluency + Statistics = maximum visibility boost. Low-ranking sites benefit disproportionately — up to **115% visibility increase** when adding citations to previously uncited content.

---

## Content Type Citation Share

Which content types get cited most by AI systems:

| Content Type | Citation Share | Why AI Cites It |
|---|---|---|
| **Comparison articles** | ~33% | Structured, balanced, high-intent queries |
| **Definitive guides** | ~15% | Comprehensive, authoritative single source |
| **Original research/data** | ~12% | Unique, citable statistics unavailable elsewhere |
| **Best-of / listicles** | ~10% | Clear structure, entity-rich, commercial intent |
| **Product pages** | ~10% | Specific details AI can extract and attribute |
| **How-to guides** | ~8% | Step-by-step structure matches procedural queries |
| **Opinion / analysis** | ~10% | Expert perspective, quotable conclusions |

**Implication**: If you only create one new content type for GEO, create a comparison article — they receive 1/3 of all AI citations.

---

## AI Visibility Monitoring Tools

Track whether AI systems are citing your content:

| Tool | Platform Coverage | Best For |
|---|---|---|
| **Otterly AI** | ChatGPT, Perplexity, Google AI Overviews | Share of AI voice tracking |
| **Peec AI** | ChatGPT, Gemini, Perplexity, Claude, Copilot+ | Multi-platform monitoring at scale |
| **ZipTie** | Google AI Overviews, ChatGPT, Perplexity | Brand mention + sentiment tracking |
| **LLMrefs** | ChatGPT, Perplexity, AI Overviews, Gemini | SEO keyword → AI visibility mapping |

**Manual monitoring**: Search 3–5 target keywords monthly in ChatGPT and Perplexity. Document which competitors get cited. Repeat quarterly to track improvement.

---

## AI Platform Source Selection (Factor-by-Factor)

How each AI platform selects sources differently:

| Factor | Google AI Overviews | ChatGPT | Perplexity | Claude |
|---|---|---|---|---|
| **Freshness bias** | High | Medium | Very high | N/A (training data) |
| **Authority weight** | Very high | High | High | High |
| **Structure importance** | High | Medium | Very high | Medium |
| **Typical citation count** | 3–8 | 1–6 | 5–10 | N/A |
| **Quotable focus** | High | Medium | Very high | High |
| **Domain trust** | Very high | High | Medium | High |
| **Factual density** | High | High | Very high | Very high |

---

## GEO Error Handling

| Scenario | Action |
|---|---|
| URL unreachable (DNS failure, connection refused) | Report the error clearly. Do not guess site content. Ask user to verify URL. |
| AI crawlers blocked by robots.txt | Report exactly which crawlers are blocked and which are allowed. Provide specific robots.txt directives to add. |
| No llms.txt found | Note the absence and generate a ready-to-use llms.txt template based on the site's content structure. |
| No structured data detected | Report the gap and provide specific schema recommendations (Article, Organization, Person) for AI discoverability. |
| Content is JS-rendered only | Flag that AI crawlers cannot execute JavaScript. Recommend SSR or pre-rendering. Test raw HTML vs. rendered DOM. |
| Brand has zero external platform presence | Prioritize YouTube and Reddit first (highest correlation). Provide a 30-day brand mention launch plan. |
