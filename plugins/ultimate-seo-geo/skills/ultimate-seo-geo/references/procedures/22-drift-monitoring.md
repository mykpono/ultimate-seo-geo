> **Progressive disclosure:** Load this file only when the current task maps to this section (see `SKILL.md` §0). Do not load all procedure files for narrow tasks.

## 22. SEO Drift Monitoring

Track changes to SEO-critical page elements over time. Detect regressions before they impact rankings.

### Use Cases

1. **Pre/post deployment** — Baseline before deploy, compare after to catch unintended changes
2. **Ongoing monitoring** — Regular snapshots to detect configuration drift
3. **Traffic drop investigation** — Query history to correlate element changes with traffic events
4. **Migration validation** — Verify critical elements survived a CMS/domain migration

### Quick Start

```bash
# Take a baseline snapshot
python scripts/drift_monitor.py baseline https://example.com

# Compare current state to last baseline
python scripts/drift_monitor.py compare https://example.com

# View snapshot history
python scripts/drift_monitor.py history https://example.com

# Generate a drift report
python scripts/drift_monitor.py report https://example.com

# JSON output for any command
python scripts/drift_monitor.py report https://example.com --json
```

### 17 Comparison Rules

| # | Severity | Field | Trigger |
|---|----------|-------|---------|
| 1 | Critical | status_code | Changed from 200 to 4xx/5xx |
| 2 | Critical | canonical | Canonical URL changed |
| 3 | Critical | robots | Robots meta changed (especially to noindex) |
| 4 | Critical | status_code | Page returns 3xx redirect when it was 200 |
| 5 | Critical | title | Title tag removed entirely |
| 6 | Critical | schema_count | All schema markup removed |
| 7 | Warning | title | Title changed significantly (>50% different) |
| 8 | Warning | meta_description | Meta description changed significantly (>50% different) |
| 9 | Warning | h1 | H1 tag(s) changed |
| 10 | Warning | headings_hash | Heading structure changed (H1/H2/H3 hash differs) |
| 11 | Warning | schema_count | Schema type or count changed (but not fully removed) |
| 12 | Warning | word_count | Word count dropped >20% |
| 13 | Warning | internal_link_count | Internal link count changed >30% |
| 14 | Info | title | Minor title tweak (<50% change) |
| 15 | Info | meta_description | Minor meta description tweak (<50% change) |
| 16 | Info | internal_link_count | Internal link count changed 10–30% |
| 17 | Info | word_count | Word count changed but within 20% |

### Severity Levels

| Level | Meaning | Response |
|-------|---------|----------|
| **Critical** | SEO-breaking change | Fix immediately — can cause deindexing, traffic loss, or redirect loops |
| **Warning** | Potentially harmful | Investigate this week — may signal unintended content or structural changes |
| **Info** | Cosmetic or minor | Monitor — no immediate action, but track for patterns |

### Elements Tracked

| Element | Source | Field |
|---------|--------|-------|
| Title tag | `<title>` | `title` |
| Meta description | `<meta name="description">` | `meta_description` |
| Canonical URL | `<link rel="canonical">` | `canonical` |
| Robots meta | `<meta name="robots">` | `robots` |
| H1 tags | All `<h1>` elements | `h1` |
| Heading structure | Hash of all H1/H2/H3 text | `headings_hash` |
| Schema markup | Count and hash of JSON-LD blocks | `schema_count`, `schema_hash` |
| Internal link count | Links to same domain | `internal_link_count` |
| Word count | Body text word count | `word_count` |
| Open Graph title | `<meta property="og:title">` | `og_title` |
| Open Graph description | `<meta property="og:description">` | `og_description` |
| Open Graph image | `<meta property="og:image">` | `og_image` |
| HTTP status | Response status code | `status_code` |

### Integration with Audits

- During **Mode 1 audits**, run `drift_monitor.py compare` if a baseline exists for the URL
- During **traffic drop investigations** (§10), query `drift_monitor.py history` to correlate changes with traffic events
- After **Mode 3 executions**, take a new baseline to track the fix
- During **migrations** (§20), baseline all critical URLs pre-migration, compare post-migration

### Workflows

#### Pre/Post Deployment

```bash
# Before deploy
python scripts/drift_monitor.py baseline https://example.com --db deploy-checks.sqlite3

# After deploy
python scripts/drift_monitor.py report https://example.com --db deploy-checks.sqlite3
```

#### Ongoing Monitoring (cron/CI)

```bash
# Compare against last baseline; exit code 1 if critical changes detected
python scripts/drift_monitor.py compare https://example.com --json
```

#### Traffic Drop Investigation

```bash
# Check what changed recently
python scripts/drift_monitor.py history https://example.com --json

# Full report against last known-good baseline
python scripts/drift_monitor.py report https://example.com
```

### Storage

Snapshots stored in SQLite (default: `.seo-drift.sqlite3` in working directory). Use `--db /path/to/db` for custom location. Each snapshot records all tracked elements plus a UTC timestamp. The `history` command returns the 20 most recent snapshots.
