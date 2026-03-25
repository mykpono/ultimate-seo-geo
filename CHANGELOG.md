# Changelog

## [1.1.1] - 2026-03-24

### Changed

- Skill YAML `description` tightened to stay within common 1024-character limits while preserving trigger terms.
- Plugin bundle (`setup-plugin.sh`) now copies **`scripts/`** (all audit `.py` files except `check-plugin-sync.py`) and **`evals/`** into `plugins/.../skills/ultimate-seo-geo/` so Claude Code plugin installs can run `python scripts/...` as documented.

## [1.1.0] - 2026-03-24

### Added

- Reference library expanded: `core-eeat-framework.md`, `cite-domain-rating.md`, `entity-optimization.md` (CORE-EEAT, CITE domain authority, entity / Knowledge Graph signals).
- Credits updated for CORE-EEAT benchmark, CITE Domain Rating, Entity Optimizer, and AI SEO / GEO content optimizer sources.
- Skill routing extended for CORE-EEAT / CITE scoring, entity optimization, and related triggers.

### Changed

- Documentation alignment: `generate_report.py` wording reflects the bundled pipeline (not a literal “19 scripts” count); §21 clarifies orchestration vs optional parallel subagents.

## [1.0.0] - 2026-03-23

### Initial Public Release

**Core Capabilities**
- 3-mode architecture: Audit (scored findings) → Plan (phased roadmap) → Execute (deliverable fixes with verification)
- SEO Health Score (0–100) across 9 weighted categories
- GEO optimization for Google AI Overviews, AI Mode, ChatGPT Search, and Perplexity
- Schema markup generation for all active Schema.org types (deprecation-aware)
- E-E-A-T assessment aligned with December 2025 universal policy
- 21 audit modules covering technical SEO, content quality, links, local, international, programmatic, and more

**Scripts & Automation**
- 20 Python diagnostic scripts including full-site HTML report generator
- Scripts cover: Core Web Vitals, robots.txt, schema validation, hreflang, internal links, broken links, readability, duplicate content, entity checking, IndexNow, social meta, and more

**Reference Library**
- 15 reference files (4,300+ lines) covering all SEO and GEO domains
- Loaded on demand — only the relevant reference file enters context per task

**Testing**
- 6 eval test cases with 26 assertions (including 1 negative test)
- Benchmarked: 100% pass rate with skill vs. 87% baseline

### Credits
- [Bhanunamikaze/Agentic-SEO-Skill](https://github.com/Bhanunamikaze/Agentic-SEO-Skill) — SEO analysis toolkit architecture
- [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo) — GEO platform citation data, DataForSEO patterns
