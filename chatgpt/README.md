# ChatGPT Custom GPT Setup

Create a Custom GPT that runs SEO + GEO audits using the Ultimate SEO + GEO skill.

## Prerequisites

- ChatGPT Plus, Team, or Enterprise account (Custom GPTs require a paid plan)
- Access to [chat.openai.com/gpts/editor](https://chat.openai.com/gpts/editor)

## Step-by-Step Setup

### 1. Create the GPT

1. Go to [chat.openai.com/gpts/editor](https://chat.openai.com/gpts/editor)
2. Click **Create a GPT**
3. Switch to the **Configure** tab

### 2. Set the Instructions

1. Copy the full contents of `instructions.txt` (this directory)
2. Paste into the **Instructions** field

### 3. Upload Knowledge Files

Upload the following files from this repository as **Knowledge** files:

**Required (core instructions):**
- `../SKILL.md` — Routing shell (§0, guardrails, index to procedures)
- All files under `../references/procedures/` — step-by-step §1–§21 (run `bash chatgpt/copy-knowledge-files.sh` to copy into `chatgpt/knowledge/procedures/`)

**Recommended (domain knowledge — upload based on your focus):**
- `../references/ai-search-geo.md` — GEO signals, AI platform data, brand strategy
- `../references/schema-types.md` — All Schema.org types + JSON-LD templates
- `../references/eeat-framework.md` — E-E-A-T scoring framework
- `../references/technical-checklist.md` — CWV fixes, JS SEO, IndexNow
- `../references/core-eeat-framework.md` — 80-item CORE-EEAT content benchmark
- `../references/cite-domain-rating.md` — 40-item CITE domain authority
- `../references/audit-script-matrix.md` — Script-to-audit-step mapping

**Optional (upload if relevant to your use case):**
- `../references/local-seo.md` — GBP, NAP, review strategy
- `../references/keyword-strategy.md` — Keyword research, intent mapping
- `../references/link-building.md` — Backlink strategy, comparison pages
- `../references/site-migration.md` — Migration checklists
- `../references/international-seo.md` — Hreflang, geo-targeting
- `../references/programmatic-seo.md` — Pages at scale, quality gates

Custom GPTs support up to 20 knowledge files (512 MB each).

### 4. Configure Capabilities

Enable:
- **Web Browsing** — required for fetching site pages
- **Code Interpreter** — useful for data analysis

Disable:
- **DALL-E Image Generation** — not needed

### 5. Name and Description

**Name:** Ultimate SEO + GEO Auditor

**Description:** Runs scored SEO audits with health scores, technical checks, Schema.org
JSON-LD, E-E-A-T content scoring, and Generative Engine Optimization (GEO) for AI search
engines. Give it a URL and get a prioritized action plan with executable fixes.

### 6. Save and Test

Click **Save** (publish as "Only me" for personal use, or "Anyone with a link" to share).

Test with: "Audit example.com — we want to improve our AI search visibility"

## Limitations vs. Full Skill

The ChatGPT Custom GPT version has some limitations compared to running the full skill in
Claude Code, Cursor, or Codex:

| Feature | Custom GPT | Full Skill (Claude Code / Codex / Cursor) |
|---|---|---|
| Instruction set | Condensed (8K chars) | SKILL.md shell + `references/procedures/` + topical refs |
| Python audit scripts | Not available | 35 scripts available |
| Progressive reference loading | Via knowledge file retrieval | Direct file reads |
| Mode 3 Execute | Limited (no script verification) | Full execute + verify loop |
| HTML report generation | Not available | `generate_report.py` |

For the full experience with all 35 diagnostic scripts, use the skill with a code-capable
agent (Claude Code, Cursor, OpenAI Codex, Gemini CLI, etc.).

## Updating

When the skill is updated, re-upload the changed files to your Custom GPT's knowledge.
The `instructions.txt` file should be re-pasted into the Instructions field.
