# Parallel audit workers (subagent scopes)

Platform-neutral definitions for delegating independent audit slices. Same routing and scripts as `references/procedures/` and `AGENTS.md` — this file only names **who runs what** when using a Task/subagent tool.

Orchestration: run `site_mapper.py` if needed → spawn workers in parallel → merge JSON → `finding_verifier.py` → report. Workers do not produce a /100: only `generate_report.py` computes the Health Score, so a parallel-only audit reports "not scored" with category status (§ 2). Do **not** run `generate_report.py` and the same per-script workers on the same URL simultaneously.

---

## seo-technical

Analyzes crawlability, indexability, security, redirects, and Core Web Vitals.

**Scope:** robots.txt + AI crawlers, security headers, CWV via PSI, redirects, canonicals, IndexNow, sitemaps, mobile readiness.

| Script | Purpose |
|--------|---------|
| `robots_checker.py` | robots.txt + AI crawler status |
| `security_headers.py` | Response headers |
| `pagespeed.py` | PageSpeed Insights (CWV) |
| `redirect_checker.py` | Redirect chains |
| `canonical_checker.py` | Canonical validation |
| `indexnow_checker.py` | IndexNow key |
| `sitemap_checker.py` | Sitemap health |

**References:** `references/technical-checklist.md`, `references/crawl-indexation.md`

---

## seo-content

Content quality, E-E-A-T, readability, duplicates, meta lengths, programmatic quality gates.

| Script | Purpose |
|--------|---------|
| `article_seo.py` | Article structure + keywords |
| `readability.py` | Readability |
| `duplicate_content.py` | Near-duplicates |
| `meta_lengths_checker.py` | Title / meta / H1 lengths |
| `programmatic_seo_auditor.py` | Template pages at scale |

**References:** `references/eeat-framework.md`, `references/core-eeat-framework.md`, `references/content-eeat.md`

---

## seo-schema

JSON-LD detection, validation, generation. Rules: JSON-LD only; HowTo still valid; FAQ restrictions; retired types per `references/procedures/19-quality-gates-hard-rules.md`.

| Script | Purpose |
|--------|---------|
| `validate_schema.py` | Validation + scoring |

**References:** `references/schema-types.md`

---

## seo-geo

AI search citation: crawlers, llms.txt, entities, social meta, citability signals.

| Script | Purpose |
|--------|---------|
| `robots_checker.py` | AI crawler access |
| `llms_txt_checker.py` | llms.txt |
| `entity_checker.py` | Entity signals |
| `social_meta.py` | OG + Twitter Card |

**References:** `references/ai-search-geo.md`, `references/entity-optimization.md`

---

## seo-performance

CWV and load performance (field/lab). INP not FID.

| Script | Purpose |
|--------|---------|
| `pagespeed.py` | PSI API |
| `image_checker.py` | Image SEO signals |

**References:** `references/technical-checklist.md`, `references/image-seo.md`

---

## seo-links

Internal graph, broken links, backlink profile (when data available).

| Script | Purpose |
|--------|---------|
| `internal_links.py` | Link graph, redirected internal links |
| `broken_links.py` | 4xx/5xx |
| `link_profile.py` | Link equity, orphans (only from a complete crawl) |
| `backlink_analyzer.py` | Backlink audit (CSV/API) |

**References:** `references/link-building.md`, `references/backlink-quality.md`
