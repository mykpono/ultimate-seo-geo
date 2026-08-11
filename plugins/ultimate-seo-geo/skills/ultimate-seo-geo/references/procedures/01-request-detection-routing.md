> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

## 1. Request Detection & Routing

If the request matches **§ 0 "When not to run Mode 1"**, route to a **narrow** answer or decline the SEO-audit template — even if generic "marketing" vocabulary appears.

**Disambiguation:** When multiple rows match, prefer the most specific. If equally specific, use the first match. If nothing matches, fall back to § 0 Intake Checklist.

This table routes by **topic**. For mode selection (Audit vs. Plan vs. Execute), see **§ 0 Mode Routing**.

| Request Type | Trigger Keywords | Go To |
|---|---|---|
| **Full Audit** | "audit", "analyze my site", "full check", "site review" | § 2 Full Audit |
| **Traffic Drop / Rankings Lost** | "traffic dropped", "lost rankings", "rankings fell", "why did traffic drop", "core update", "algorithm update", "rankings dropped" | § 10 Analytics first, then § 4 Technical / § 6 Content |
| **GEO / AI Search** | "AI Overviews", "ChatGPT", "Perplexity", "AI citations", "GEO", "AI Mode", "SearchGPT", "Gemini", "llms.txt", "AI search" | § 3 GEO |
| **Technical SEO** | "crawl", "robots.txt", "Core Web Vitals", "speed", "indexing", "JS rendering", "mobile", "mobile-friendly", "HTTPS", "security headers", "redirect chain" | § 4 Technical |
| **Schema / Structured Data** | "schema", "JSON-LD", "rich results", "structured data" | § 5 Schema |
| **Content / E-E-A-T** | "content quality", "E-E-A-T", "thin content", "helpful content", "CORE-EEAT" | § 6 Content |
| **Content Scoring** | "CORE-EEAT audit", "content score", "CITE audit", "domain authority score", "GEO score" | § 6 Content |
| **Entity Optimization** | "entity", "knowledge graph", "knowledge panel", "Wikidata", "brand entity" | § 3 GEO |
| **Content Pruning / Refresh** | "old content", "content decay", "delete pages", "refresh", "consolidate" | § 6b Pruning |
| **Keyword Research** | "keywords", "ranking opportunities", "content gaps", "what should I write" | § 7 Keywords |
| **Topic Clusters** | "topic cluster", "content strategy", "pillar page" | § 7b Clusters |
| **AEO / Featured Snippets** | "featured snippet", "PAA", "voice search", "knowledge panel", "speakable" | § 7c AEO |
| **Competitor Analysis** | "competitors", "benchmark", "compare to", "X vs Y page", "alternatives page" | § 8 Competitors |
| **Link Building** | "backlinks", "internal links", "anchor text", "referring domains" | § 9 Links |
| **Analytics / Reporting** | "GA4", "Search Console", "CTR", "rank tracking", "penalty", "manual action" | § 10 Analytics |
| **Crawl & Indexation** | "crawl budget", "sitemap", "canonical", "index bloat", "noindex", "duplicate content", "content cannibalization" | § 11 Crawl |
| **Local SEO** | "local", "Google Business Profile", "GBP", "map pack", "NAP" | § 12 Local |
| **Image SEO** | "images", "alt text", "WebP", "image size" | § 13 Images |
| **International SEO** | "hreflang", "multi-language", "international", "geo-targeting" | § 14 International |
| **Programmatic SEO** | "programmatic", "at scale", "templates", "city pages", "glossary pages" | § 15 Programmatic |
| **Strategy / Roadmap** | "SEO plan", "roadmap", "strategy", "what should I focus on" | § 16 Strategy |
| **Monthly Maintenance** | "what should I check", "monthly SEO", "ongoing", "monitor" | § 17 Maintenance |
| **Site Migration** | "moving domains", "new URL structure", "CMS migration", "redirect map" | § 20 Migration |
| **Myths / Misconceptions** | "does X help SEO?", "is X a ranking factor?" | § 18 Myths |
| **Script Toolbox** | "run a check", "generate a report", "validate schema", "automated audit" | § 21 Scripts |
| **SEO Drift / Change Tracking** | "drift", "what changed", "before/after", "deployment check", "baseline" | § 22 Drift Monitoring |
| **Semantic Clustering** | "topic clusters from SERP data", "SERP overlap", "content hub", "cluster analysis" | § 23 Semantic Clustering |
| **E-commerce SEO** | "product schema", "e-commerce", "product pages", "category pages", "shopping", "merchant" | § 24 E-commerce SEO |
| **Maps / Advanced Local** | "geo-grid", "GBP audit", "review intelligence", "NAP consistency", "local competitors" | § 25 Maps Intelligence |
| **Content Brief** | "content brief", "brief for writers", "writing brief", "outline for article" | § 7 Keywords (content brief section) |
| **Google API / Credentials** | "API tier", "connect GSC", "GA4 data", "CrUX history", "Google credentials" | § 21 Scripts (Google API tier) |
| **No clear match** | Query doesn't match any row above | § 0 Intake Checklist |
| **Paid ads primary** | "Google Ads", "PPC campaign", "ad spend" without organic SEO ask | § 0 — paid scope, not Mode 1 |
| **Scoped technical only** | "only robots.txt", "just the sitemap", "don't audit content" | § 0 + § 4 / § 11 — stay in scope |

---
