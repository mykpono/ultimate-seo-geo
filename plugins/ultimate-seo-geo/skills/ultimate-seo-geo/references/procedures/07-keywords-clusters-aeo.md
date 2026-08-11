> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

## 7. Keyword Research & Content Gaps

### Step by Step

1. **Establish seed keywords** — What are the 3–5 core topics this site covers?
2. **Classify existing content by intent** — Informational / Commercial / Transactional / Navigational.
3. **Identify funnel gaps** — Which stages (TOFU / MOFU / BOFU) have no content?
4. **Prioritize missing content** — For each gap: target keyword, intent, format, difficulty.
5. **Output a prioritized content plan** — Up to 10 recommended pages by Opportunity Score: `(Volume × Intent Value) / Difficulty` — see `references/keyword-strategy.md` for the full formula with intent-weighted values and priority scoring matrix.

### Keyword Selection: Good vs. Bad

| ✅ Good Target | ❌ Poor Target | Why |
|---|---|---|
| "project management software for remote teams" | "project management" | Too broad — DA 80+ players dominate |
| "best CRM for small business 2026" | "CRM software" | Specific + high commercial intent |
| "Salesforce alternatives for nonprofits" | "Salesforce" | Navigational — won't convert |
| "email marketing open rate benchmarks" | "email marketing" | Data opportunity vs. unreachable head term |

### Intent + Funnel Gap Detection

| Intent | Pattern | Content Format |
|---|---|---|
| **Informational (TOFU)** | "what is X", "how to X" | Pillar guide, how-to — create definitional anchor if missing |
| **Commercial (MOFU/BOFU)** | "best X", "X vs Y", "X alternatives" | Comparison, roundup — high commercial intent, often faster to rank |
| **Transactional (BOFU)** | "buy X", "X pricing", "free trial" | Landing page, pricing |

→ See `references/keyword-strategy.md`

---

## 7b. Topic Cluster Building

### Step by Step

1. **Identify pillar topic** — Broad term with high volume. Pillar page: 3,000–5,000 words, covers the topic broadly, links to every cluster post.
2. **Map cluster posts** — Find subtopics via PAA boxes, GSC queries. Pattern: "what is [topic]", "how to [topic]", "best [topic] tools", "[topic] vs [alternative]".
3. **Assign funnel intent** — TOFU / MOFU / BOFU. Aim for a mix.
4. **Build pillar first**, then cluster posts (1,500–2,500 words each).
5. **Enforce bidirectional linking** — Pillar → all cluster posts. All cluster posts → pillar.

### Example Structure

**Pillar**: "Project Management Software" (3,500 words)
- TOFU: "What is project management?", "Agile vs. Waterfall"
- MOFU: "How to choose PM software", "Project management templates"
- BOFU: "Best PM software for small teams", "Asana vs. Monday vs. Trello"

### Cluster Health Check

| Check | Status |
|---|---|
| Pillar receives most internal links from cluster? | ✅ Required |
| All cluster posts indexed? | ✅ Required |
| No two posts targeting the same primary keyword? | ✅ Required (cannibalization) |

---

## 7c. AEO — Answer Engine Optimization

AEO covers zero-click SERP features: Featured Snippets, PAA, Knowledge Panel, voice/speakable. Winning these directly feeds AI Overview and AI Mode citations.

### Featured Snippet Optimization

1. **Identify candidates** — Pages ranking 2–10 for informational queries (high impressions in GSC).
2. **Identify the snippet format** — Search the query. Paragraph, list, or table?
3. **Structure the answer:**
   - **Paragraph**: 40–60 words immediately after a question-format H2/H3. Google truncates paragraph snippets beyond ~60 words, so staying under preserves the complete answer.
   - **List**: 5–9 items, each < 15 words. Lists >9 items get truncated.
   - **Table**: ≤4 columns, labeled headers.
4. **Lead with the direct answer** — "It depends" before the actual answer loses the snippet to a competitor who answers directly. Google selects the most concise, self-contained response.

### PAA Optimization

1. Find PAA questions for the target keyword.
2. Add a dedicated H2/H3 using the exact question wording.
3. Answer immediately in **40–60 words** — direct, no preamble.
4. Aim for 3–5 PAA answers per page (each answer surfaces more questions).

### Content Format Pattern

```
## What is [Topic]?
[Topic] is [definition in 1 sentence]. It works by [mechanism in 1 sentence].
[1–2 sentences context. Total: 40–60 words.]

## How does [Topic] work?
[Direct answer in 40–60 words starting with the subject.]
```

For Knowledge Panel (sameAs schema), Sitelinks Searchbox (SearchAction code), Speakable schema, and voice search platform breakdown (Siri/Alexa use Bing, not Google), see `references/schema-types.md` → "AEO Schema" section.

---

### Content Brief Generation

For structured briefs to hand to writers, use `scripts/content_brief.py`:

```bash
python scripts/content_brief.py "target keyword" --competitors https://competitor1.com/page https://competitor2.com/page --site https://mysite.com
```

Brief output includes: target + secondary keywords, H2/H3 outline derived from competitor analysis, word count targets, schema recommendations, AI citation opportunities, and internal link suggestions. See `references/procedures/23-semantic-clustering.md` for topic cluster context.

