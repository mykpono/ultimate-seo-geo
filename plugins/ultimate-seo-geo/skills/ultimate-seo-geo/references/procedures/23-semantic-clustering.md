> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

## 23. Semantic Topic Clustering (SERP-Overlap Method)

Traditional text-similarity clustering groups keywords that *look* alike. SERP-overlap clustering groups keywords that *rank* alike — if two keywords share most of the same top-10 results, Google treats them as the same topic and a single page can target both.

### Why SERP Overlap > Text Similarity

| Method | Signal | Weakness |
|---|---|---|
| Text similarity (TF-IDF, embeddings) | Lexical/semantic closeness | "best CRM" and "CRM comparison" look different but satisfy the same intent |
| SERP overlap (Jaccard of top-10 URLs) | Google's own intent mapping | Requires SERP data (DataForSEO, Ahrefs, or manual collection) |

SERP overlap is the gold standard because it reflects how the search engine *actually* groups intent. A Jaccard similarity ≥ 0.3 between two keywords' top-10 URL sets strongly suggests a shared SERP intent; ≥ 0.5 means a single page should target both.

### Data Requirements

You need SERP ranking data in one of these formats:

| Source | Format | Notes |
|---|---|---|
| DataForSEO extension | CSV via `keyword,rank,url` | Automated — see `references/optional-extensions-mcp.md` |
| Ahrefs / Semrush export | CSV export → reformat to `keyword,rank,url` | Most SEO tools export this |
| Manual collection | Search each keyword, record top-10 URLs | Only practical for < 30 keywords |
| `scripts/topic_cluster.py --format keyword_list` | Keywords only (no URLs) | Produces guidance for manual clustering — no automated overlap |

### Step-by-Step Process

#### 1. Collect SERP Data

For each target keyword, record the top-10 ranking URLs. Format as CSV:

```csv
keyword,rank,url
best crm software,1,https://example.com/crm-review
best crm software,2,https://another.com/top-crms
crm comparison,1,https://example.com/crm-review
crm comparison,2,https://different.com/crm-guide
```

#### 2. Compute SERP Overlap (Jaccard Similarity)

For each keyword pair, compute:

```
Jaccard(A, B) = |URLs_A ∩ URLs_B| / |URLs_A ∪ URLs_B|
```

Where `URLs_A` is the set of top-10 ranking URLs for keyword A.

Run the clustering script:

```bash
python scripts/topic_cluster.py --input serp_data.csv --format serp_overlap --min-overlap 0.3
```

#### 3. Review Clusters

The script outputs:
- **Cluster assignments** — which keywords belong together
- **Pillar identification** — the broadest/highest-volume keyword per cluster becomes the pillar topic
- **Internal link matrix** — which cluster pages should cross-link

#### 4. Build Hub-and-Spoke Architecture

Each cluster maps to a hub-and-spoke content structure:

```
                    ┌──────────────┐
                    │  Pillar Page │  (broadest keyword, 3,000–5,000 words)
                    │  Hub Topic   │
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │ Cluster Post │  │ Cluster Post │  │ Cluster Post │
   │ (spoke)      │  │ (spoke)      │  │ (spoke)      │
   └─────────────┘  └─────────────┘  └─────────────┘
```

**Pillar page** — covers the cluster topic broadly, links to every spoke.
**Spoke posts** — cover subtopics in depth (1,500–2,500 words each), link back to pillar and to adjacent spokes.

#### 5. Generate Internal Link Matrix

For each cluster, the link matrix specifies:

| From | To | Link Type | Anchor Strategy |
|---|---|---|---|
| Pillar → Spoke | Every spoke in cluster | Contextual body link | Descriptive anchor with spoke's target keyword |
| Spoke → Pillar | The pillar page | Contextual body link + breadcrumb | Pillar's primary keyword |
| Spoke → Spoke | Related spokes in same cluster | Contextual body link (2–3 per post) | Natural variation of target keyword |

Cross-cluster links (pillar ↔ pillar) should be added when topics are related but not overlapping.

#### 6. Overlap Thresholds

| Jaccard Score | Interpretation | Action |
|---|---|---|
| ≥ 0.5 | Strong overlap — same intent | Target on a single page |
| 0.3 – 0.5 | Moderate overlap — related intent | Same cluster, separate pages, strong internal links |
| 0.1 – 0.3 | Weak overlap — adjacent topics | Different clusters, consider cross-cluster links |
| < 0.1 | No meaningful overlap | Separate topics entirely |

### Cannibalization Detection

When two existing pages target keywords with Jaccard ≥ 0.5, you likely have keyword cannibalization. Resolution:

1. **Merge** — Combine both pages into the stronger URL, 301-redirect the weaker one.
2. **Differentiate** — Rewrite one page to target a distinct sub-intent (e.g., "X vs Y" vs. "best X for [use case]").
3. **Canonical** — If both pages must exist (e.g., category + product), use internal linking hierarchy to signal the primary.

### Script Reference

```bash
# Full SERP-overlap clustering with URL data
python scripts/topic_cluster.py --input serp_data.csv --format serp_overlap --min-overlap 0.3 --json

# Keyword-only mode (guidance output, no automated clustering)
python scripts/topic_cluster.py --input keywords.csv --format keyword_list

# Stricter clustering (fewer, tighter clusters)
python scripts/topic_cluster.py --input serp_data.csv --format serp_overlap --min-overlap 0.5
```

### Content Brief Integration

Once clusters are defined, generate briefs for each page using `scripts/content_brief.py`:

```bash
python scripts/content_brief.py "target keyword" --competitors https://competitor1.com/page --site https://mysite.com
```

Brief output includes target + secondary keywords, H2/H3 outline derived from competitor analysis, word count targets, schema recommendations, AI citation opportunities, and internal link suggestions. See § 7 for keyword research context.
