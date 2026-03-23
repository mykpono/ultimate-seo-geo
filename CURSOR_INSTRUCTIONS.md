# Cursor Task: Add Claude Code Plugin Structure to ultimate-seo-geo

## What this does
Wraps the existing `ultimate-seo-geo` skill so it can be installed via the
Claude Code plugin marketplace with `/plugin marketplace add mykpono/ultimate-seo-geo`.

**Maintenance:** Canonical sources are repo-root `SKILL.md` and `references/`. After changing them, run `bash setup-plugin.sh`. CI enforces parity and a single version string via `scripts/check-plugin-sync.py`. For releases, follow `RELEASE.md`.

## Files to create (all content provided below)

Create these files exactly as specified. Do not modify any existing files.

---

### 1. `.claude-plugin/marketplace.json`
```json
{
  "name": "ultimate-seo-geo",
  "owner": {
    "name": "Myk Pono",
    "url": "https://mykpono.com"
  },
  "metadata": {
    "description": "SEO + GEO skills for Claude — full site audits, AI search optimization, schema generation, and 20 diagnostic scripts.",
    "homepage": "https://github.com/mykpono/ultimate-seo-geo",
    "version": "1.0.0"
  },
  "plugins": [
    {
      "name": "ultimate-seo-geo",
      "source": "./plugins/ultimate-seo-geo",
      "description": "The definitive SEO + GEO skill for Claude. Full site audits with scored findings (0–100), AI search optimization for Google AI Overviews, ChatGPT Search, and Perplexity, schema markup generation, E-E-A-T assessment, and 20 Python diagnostic scripts. Three modes: Audit → Plan → Execute.",
      "version": "1.0.0",
      "author": {
        "name": "Myk Pono",
        "url": "https://mykpono.com"
      },
      "category": "marketing",
      "tags": [
        "seo",
        "geo",
        "audit",
        "schema",
        "eeat",
        "ai-search",
        "local-seo",
        "technical-seo",
        "content-strategy",
        "perplexity",
        "chatgpt-search",
        "google-ai-overviews"
      ],
      "homepage": "https://github.com/mykpono/ultimate-seo-geo",
      "license": "MIT"
    }
  ]
}
```

---

### 2. `plugins/ultimate-seo-geo/.claude-plugin/plugin.json`
```json
{
  "name": "ultimate-seo-geo",
  "version": "1.0.0",
  "description": "The definitive SEO + GEO skill for Claude. Full site audits with scored findings, AI search optimization (Google AI Overviews, ChatGPT, Perplexity), schema generation, E-E-A-T assessment, and 20 diagnostic scripts. Three modes: Audit → Plan → Execute.",
  "author": {
    "name": "Myk Pono",
    "url": "https://mykpono.com"
  },
  "homepage": "https://github.com/mykpono/ultimate-seo-geo",
  "repository": "https://github.com/mykpono/ultimate-seo-geo",
  "license": "MIT",
  "keywords": [
    "seo",
    "geo",
    "audit",
    "schema",
    "eeat",
    "ai-search",
    "generative-engine-optimization",
    "google-ai-overviews",
    "chatgpt-search",
    "perplexity",
    "technical-seo",
    "local-seo",
    "content-strategy"
  ]
}
```

---

### 3. `plugins/ultimate-seo-geo/skills/ultimate-seo-geo/SKILL.md`

Copy the content of the root-level `SKILL.md` exactly into this path.

In bash:
```bash
cp SKILL.md plugins/ultimate-seo-geo/skills/ultimate-seo-geo/SKILL.md
```

---

### 4. `plugins/ultimate-seo-geo/skills/ultimate-seo-geo/references/` (directory)

Copy the entire `references/` directory from the repo root into the skill folder:
```bash
cp -r references/ plugins/ultimate-seo-geo/skills/ultimate-seo-geo/references/
```

---

### 5. `plugins/ultimate-seo-geo/README.md`

Create with the content provided in `plugins/ultimate-seo-geo/README.md` in this package.

---

## Final repo structure after changes

```
ultimate-seo-geo/
├── .claude-plugin/
│   └── marketplace.json                         ← NEW
├── plugins/
│   └── ultimate-seo-geo/
│       ├── .claude-plugin/
│       │   └── plugin.json                      ← NEW
│       ├── skills/
│       │   └── ultimate-seo-geo/
│       │       ├── SKILL.md                     ← COPIED from root
│       │       └── references/                  ← COPIED from root
│       │           ├── ai-search-geo.md
│       │           ├── analytics-reporting.md
│       │           ├── content-eeat.md
│       │           ├── crawl-indexation.md
│       │           ├── eeat-framework.md
│       │           ├── image-seo.md
│       │           ├── industry-templates.md
│       │           ├── international-seo.md
│       │           ├── keyword-strategy.md
│       │           ├── link-building.md
│       │           ├── local-seo.md
│       │           ├── programmatic-seo.md
│       │           ├── schema-types.md
│       │           ├── site-migration.md
│       │           └── technical-checklist.md
│       └── README.md                            ← NEW
├── .github/
│   └── workflows/
│       └── validate-plugin.yml                  ← NEW
├── evals/                                       ← unchanged
├── references/                                  ← unchanged (kept at root for SKILL.md installs)
├── scripts/                                     ← unchanged
├── .gitignore                                   ← unchanged
├── CHANGELOG.md                                 ← unchanged
├── LICENSE                                      ← unchanged
├── README.md                                    ← UPDATE (add install section — see below)
└── SKILL.md                                     ← unchanged
```

---

## README.md update

In the existing root `README.md`, find the `## Installation` section and **replace it** with:

```markdown
## Installation

### Claude Code — Plugin Marketplace (recommended)

```bash
# Step 1: Add the marketplace (one-time)
/plugin marketplace add mykpono/ultimate-seo-geo

# Step 2: Install the plugin
/plugin install ultimate-seo-geo@ultimate-seo-geo
```

Or install directly without a marketplace:
```bash
/plugin install https://github.com/mykpono/ultimate-seo-geo.git
```

### Claude Code — Manual skill install (global)

```bash
cp -r ultimate-seo-geo ~/.claude/skills/
```

### Claude Desktop / Cowork

Install the `.skill` file from the [Releases](https://github.com/mykpono/ultimate-seo-geo/releases) page.

### Manual (any agent)

Copy the folder into your skills directory:

```
~/.claude/skills/ultimate-seo-geo/
├── SKILL.md
├── references/    (15 files)
├── scripts/       (20 files)
└── evals/         (test cases)
```
```

---

## Git commands to run after Cursor completes

```bash
git add .
git commit -m "feat: add Claude Code plugin marketplace structure

- Add .claude-plugin/marketplace.json
- Add plugins/ultimate-seo-geo/.claude-plugin/plugin.json
- Add plugins/ultimate-seo-geo/skills/ with SKILL.md + references/
- Add plugins/ultimate-seo-geo/README.md with install instructions
- Add GitHub Actions validation workflow
- Update root README.md with plugin marketplace install instructions"

git push origin main
```

---

## Verify locally (before or after push)

From the repo root, run **`CURSOR_VERIFY.md`** (step-by-step checks) or at minimum:

```bash
python3 scripts/check-plugin-sync.py
```

---

## Verify it works (after pushing)

In **Claude Code** (type in the app chat, not in Terminal/zsh):

```text
/plugin marketplace add mykpono/ultimate-seo-geo
/plugin install ultimate-seo-geo@ultimate-seo-geo
```
