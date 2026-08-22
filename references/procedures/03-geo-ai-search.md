> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

## 3. GEO — AI Search Visibility

GEO = getting content cited by AI engines: Google AI Overviews, AI Mode, ChatGPT Search, Perplexity.

### GEO Quick Check (run first — 5 yes/no questions)

| # | Question | If No → Action |
|---|---|---|
| 1 | Are AI crawlers (OAI-SearchBot, PerplexityBot) allowed in robots.txt? | Remove Disallow rules immediately |
| 2 | Does the page answer its target query in the first 60 words? | Move key answer to opening paragraph |
| 3 | Is page content present in raw HTML (not JS-rendered only)? | Implement SSR or pre-rendering |
| 4 | Does the page have a named author with credentials and a publication date? | Add author bio + date to every key page |
| 5 | Is the brand mentioned on YouTube or Reddit? | Start a presence on the missing platform |

Any "No" = fix before deeper analysis. All "Yes" → proceed to full GEO Score.

For 2026 platform reach and traffic signal data, see `references/ai-search-geo.md`.

### GEO Audit — Step by Step

1. **Check AI crawler access** — Fetch `/robots.txt`. Confirm OAI-SearchBot, PerplexityBot, ClaudeBot are not Disallowed.
2. **Check llms.txt** — Fetch `/llms.txt`. **Google confirmed (June 2026) that Search ignores llms.txt entirely** — it neither helps nor hurts, including in AI Overviews and AI Mode. Absence is **not a finding** and must not be scored; do not claim any Google SEO or Google AI citation benefit. Offer the template in `references/ai-search-geo.md` only if the user has named a non-Google AI engine as a target. Also check for **RSL 1.0 (Really Simple Licensing)** — December 2025 standard backed by Reddit, Yahoo, Medium, Quora, Cloudflare, Akamai, and Creative Commons. Check for a `/rsl.txt` file or RSL `<meta>` tag on key pages. Absence is not a penalty but early adoption signals AI-friendly intent.
3. **Score citability** — For each key page: does the first 40–60 words answer the target query? Self-contained 134–167 word answer blocks? Question-format headings? Pages already optimized for Featured Snippets (§ 7c) have a structural head-start on AI citation.
   - **FAQPage markup routes here.** Since Google withdrew FAQ rich results (May 7, 2026), FAQPage is no longer scored as a Google rich-result opportunity in § 5 — it is scored here, as a Citability signal. Q&A pairs are self-contained question-and-answer blocks, which is the shape AI engines cite. Assess the *content*: does each answer stand alone and directly answer its question? Do not assess the markup for SERP benefit. See § 5 step 6.
4. **Check JavaScript rendering** — Fetch raw page source. Key content absent from raw HTML = invisible to AI bots.
   - **Visible-HTML parity for FAQ answers.** Answer text present in JSON-LD but absent from the rendered HTML is a specific instance of this: the markup satisfies a parser while the user and the AI crawler see nothing. `scripts/parse_html.py` and `scripts/article_seo.py` flag this at High on fetched pages. Treat it as a Citability deduction, not a schema error.
5. **Check preferred sources (publisher sites only)** — Run `scripts/preferred_sources_checker.py`. Since the Top Stories carousel went live inside AI Overviews (July 17, 2026), a reader's preferred sources can surface in AI answers on developing-news queries — the only AI-visibility lever the reader controls. Selection is **host-level**: a publication in a subdirectory is structurally ineligible. Report at Info; **skip entirely** on sites that publish no dated news-style content. See `references/ai-search-geo.md` → Preferred Sources.
6. **Audit brand signals** — Search brand on YouTube, Reddit, Wikipedia. Missing platforms = highest-priority targets. See `references/ai-search-geo.md` for correlation data and Wikipedia/Wikidata setup.
7. **Test AI citation presence** — Search 3–5 target keywords in ChatGPT and Perplexity. Note where competitors appear and the site doesn't.
8. **Output GEO Score** using component weights below.

### GEO Score Components

| Dimension | Weight | Key Checks |
|---|---|---|
| **Citability** | 25% | Answer in first 40–60 words; 134–167 word self-contained blocks; specific stats |
| **Structural Readability** | 20% | H1→H2→H3 hierarchy; question-based headings; tables |
| **Authority & Brand Signals** | 20% | Author bio + credentials; publication date; Wikipedia/Reddit/YouTube presence |
| **Technical Accessibility** | 20% | AI crawlers allowed; SSR; key content in raw HTML |
| **Multi-Modal Content** | 15% | Text + images + video = 78% of cited sources |

**Key insight**: 44.2% of AI citations come from the *first 30%* of content. Restructuring alone can 2× citation rate.

For the Quora, Reddit, influencer, and newsletter outreach playbooks, see `references/ai-search-geo.md` → Tactical Playbooks per Channel.

For Google AI Mode–specific optimization (zero blue links, follow-up queries, Related Questions sections), see `references/ai-search-geo.md` → Platform-Specific Optimization.

For the AI crawler allow/block table (OAI-SearchBot, PerplexityBot, ClaudeBot, GPTBot, Google-Extended) and the llms.txt quick template, see `references/ai-search-geo.md`.

### GEO Finding Example

```
Finding: Key answer buried below fold — target query not answered in first 30% of content
Evidence: "How does [product] work" answered in paragraph 6, ~800 words in.
           44.2% of AI citations come from first 30% of content — this page fails.
Impact: Low AI Overview and Perplexity citation rate for the site's core query.
Fix: Move the direct answer to the opening paragraph. Keep detail further down.
Confidence: Confirmed | Severity: 🟠 High
```

### Citation Demonstration (Evaluator-Optimizer Pattern)

When auditing a page's citation potential, always produce a **before/after citation demonstration** — not just a score. Show the user what an AI-quotable passage from their content would look like:

```
CURRENT (not citable — 340 words, no direct answer in first 30%)
  "Psilocybin has been the subject of considerable scientific investigation in recent
  years, with researchers from leading institutions exploring its..."

REWRITTEN (citable — 148 words, direct answer in first sentence, source attributed)
  "Psilocybin produces psychedelic effects by binding to serotonin 5-HT2A receptors
  in the brain, temporarily altering perception and cognition (Johns Hopkins Center
  for Psychedelic Research, 2024). Effects last 4–6 hours at typical doses of
  10–30 mg. A 2023 JAMA Psychiatry meta-analysis of 11 RCTs found response rates
  of 57–80% for treatment-resistant depression."

WHY IT'S CITABLE: Self-contained (148 words, within 134–167 target), direct answer
first, specific numeric stat, dated institutional source — exactly what AI systems
prefer for citation inclusion.
```

This concrete demonstration is more actionable than a score alone. Adapted from Anthropic's [Citations cookbook](https://github.com/anthropics/claude-cookbooks/blob/main/misc/using_citations.ipynb) pattern of showing source attribution in structured output.

→ See `references/ai-search-geo.md` (full platform data, brand correlation, Wikipedia/Wikidata setup, Passage Indexing, Princeton GEO research techniques, content type citation share, AI monitoring tools, platform source selection factors) | See `references/entity-optimization.md` (47-signal entity checklist, AI Entity Resolution Test, Knowledge Graph guide) | Run `scripts/robots_checker.py` Run `scripts/entity_checker.py` Run `scripts/llms_txt_checker.py` Run `scripts/social_meta.py`

