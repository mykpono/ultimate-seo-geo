> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

## 9. Link Building & Internal Linking

**Internal linking first** — highest leverage, zero cost. Always audit before recommending external acquisition.

### Internal Link Audit — Step by Step

1. **Identify pillar pages** — Verify they receive the most internal links from cluster posts.
2. **Find orphan pages** — Zero internal links pointing to them. Fix: add 1+ contextual link from a related page.
2b. **Point existing pages at a money page** — `python scripts/link_opportunities.py --graph site_graph.json --target <money page> --terms "<its main query>" --queries rows.json --gsc-pages Pages.csv`. It lists pages that name the topic in their own content but do not link to the target from it (a navigation-only link does not count as done), quotes the sentence to link from, and proposes the anchor: a Search Console query for the target when one is in the sentence (`--queries` takes a `gsc_insights.py --save-rows` file), else the term. Breadcrumbs, pipe bars, headings and product names that contain the term ("Workers AI" for `/workers`) are not sentences to link from. Add the top 10, then re-check the target's positions in four weeks.
3. **Audit anchor text** — Replace "click here"/"read more" with descriptive, keyword-rich anchors. Measure it with `python scripts/internal_links.py URL --graph site_graph.json`: it reads in-content links only (header, nav, footer, breadcrumb and links on 80% of pages are left out) and lists vague anchors and pages reached only through them. A generic word that is the target's own path word ("Go" → `/docs/go`) is not vague. It reports each page's anchor mix but never flags a repeated anchor: Google does not penalise repeated internal anchors, and on real sites the most repeated ones are template calls to action.
4. **Check crawl depth** — Key pages within 3 clicks from homepage.

### Standards

| Rule | Standard |
|---|---|
| Orphan pages | Zero allowed — every indexed page needs 1+ internal link |
| Anchor text distribution | 40–50% branded, 15–20% naked URL, 5–10% exact match. >20% exact match = over-optimization |
| Internal nofollow | Remove — nofollow on internal links blocks PageRank flow |
| Link density | 3–5 contextual internal links per 1,000 words |

### External Link Quality Hierarchy

1. Editorial links from authoritative publications
2. Digital PR / original research
3. Partner/supplier/testimonial links
4. Broken link building, resource page outreach
5. Industry directories (supplementary)

**Don't**: Recommend paid link schemes — violates Google's spam policy.

→ See `references/link-building.md` (CommonCrawl backlink API, comparison page requirements) | Run `scripts/internal_links.py` Run `scripts/broken_links.py` Run `scripts/link_profile.py`

