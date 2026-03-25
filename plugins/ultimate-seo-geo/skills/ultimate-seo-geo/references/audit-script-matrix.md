# Audit steps ↔ diagnostic scripts

Each major automated check has a **script** you can run alone (usually with `--json`). The full-site dashboard runs the **bundled pipeline** in `scripts/generate_report.py`, which executes the same tools in one pass.

| Audit area | SKILL § | Script | CLI example |
|------------|---------|--------|-------------|
| Full bundled report | §2, §21 | `generate_report.py` | `python scripts/generate_report.py https://example.com -o report.html` |
| Robots.txt + AI crawlers | §4, §3 | `robots_checker.py` | `python scripts/robots_checker.py URL --json` |
| Security headers | §4 | `security_headers.py` | `python scripts/security_headers.py URL --json` |
| Open Graph / Twitter | §4 | `social_meta.py` | `python scripts/social_meta.py URL --json` |
| Redirect chains | §4, §20 | `redirect_checker.py` | `python scripts/redirect_checker.py URL --json` |
| llms.txt | §3 | `llms_txt_checker.py` | `python scripts/llms_txt_checker.py URL --json` |
| Broken links | §9 | `broken_links.py` | `python scripts/broken_links.py URL --json` |
| Internal links / orphans | §9 | `internal_links.py` | `python scripts/internal_links.py URL --depth 1 --json` |
| Core Web Vitals (PSI) | §4 | `pagespeed.py` | `python scripts/pagespeed.py URL --strategy mobile --json` |
| Entity / Wikidata | §3 | `entity_checker.py` | `python scripts/entity_checker.py URL --json` |
| Link equity / graph | §9 | `link_profile.py` | `python scripts/link_profile.py URL --json` |
| Hreflang | §14 | `hreflang_checker.py` | `python scripts/hreflang_checker.py URL --json` |
| Near-duplicate / thin | §6 | `duplicate_content.py` | `python scripts/duplicate_content.py URL --json` |
| Sitemap discovery | §11 | `sitemap_checker.py` | `python scripts/sitemap_checker.py URL --json` |
| Local surface signals | §12 | `local_signals_checker.py` | `python scripts/local_signals_checker.py URL --json` |
| IndexNow (full key validation) | §4 | `indexnow_checker.py` | `python scripts/indexnow_checker.py URL --key KEY --json` |
| IndexNow (probe, no key) | §4 | `indexnow_checker.py` | `python scripts/indexnow_checker.py URL --probe --json` |
| On-page extract | §2, §4 | `parse_html.py` | `python scripts/parse_html.py file.html --url URL --json` |
| Readability | §6 | `readability.py` | `python scripts/readability.py file.html --json` |
| Article / CMS patterns | §6 | `article_seo.py` | `python scripts/article_seo.py URL --json` |
| JSON-LD validation | §5 | `validate_schema.py` | `python scripts/validate_schema.py file.html --json` |
| Image alt coverage | §13 | `image_checker.py` | `python scripts/image_checker.py page.html --base-url URL --json` |
| Finding deduplication | §2 | `finding_verifier.py` | Pipe structured findings JSON (post-audit merge; not URL-scoped) |

## Utilities (supporting tools)

| Script | Role |
|--------|------|
| `fetch_page.py` | Fetch HTML to disk for manual inspection |
| `check-plugin-sync.py` | CI / release: verify plugin bundle matches repo root |

## Reference-only areas (no dedicated `.py` checker)

LLM + checklist work uses these references; there is **no separate script** by design:

| Area | SKILL § | Reference |
|------|---------|-----------|
| Programmatic SEO gates | §15 | `references/programmatic-seo.md` |
| Keyword / topic strategy | §7 | `references/keyword-strategy.md` |
| Analytics / GSC / GA4 | §10 | `references/analytics-reporting.md` |
| AI search narrative / GEO | §3 | `references/ai-search-geo.md` |
| CORE-EEAT scoring | §6 | `references/core-eeat-framework.md` |
| CITE domain rating | §6 | `references/cite-domain-rating.md` |
| Entity optimization depth | §3 | `references/entity-optimization.md` |

## Progressive checks

1. **Fast baseline:** `generate_report.py` (one command, all wired checks).  
2. **Deep dive:** run any row’s script alone for that dimension.  
3. **Schema after edits:** `validate_schema.py` on saved HTML.  
4. **IndexNow with key:** use `--key` when you have an IndexNow key (probe mode is keyless).
