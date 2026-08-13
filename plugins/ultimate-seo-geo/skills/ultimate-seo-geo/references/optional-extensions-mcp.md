# Optional extensions and MCP (Firecrawl, DataForSEO)

**MCP and these extensions are optional.** All bundled audit scripts run with only `requests` and `beautifulsoup4` (`pip install -r requirements.txt`). Extensions add richer crawling and live SERP/backlink data when you configure them in your environment.

## What each extension adds

| Extension | What it adds | Typical free tier |
|-----------|----------------|-------------------|
| **Firecrawl** | JavaScript-rendered crawling (full-site / dynamic pages) | Vendor plan (e.g. monthly credits) |
| **DataForSEO** | Live SERP, keywords, backlinks, on-page/Lighthouse via MCP | Trial credits |

When MCP tools from DataForSEO are available, use them per `references/procedures/21-script-toolbox.md` (DataForSEO MCP table) and `references/ai-search-geo.md` (GEO visibility checks).

## Claude Code plugin installs (no monorepo checkout)

The plugin bundle includes `scripts/` and `references/` but **not** the `extensions/` shell installers. Use a full clone of the repository to run install scripts, or copy commands from the paths below.

**Repository:** [github.com/mykpono/ultimate-seo-geo](https://github.com/mykpono/ultimate-seo-geo)

After cloning:

```bash
# Firecrawl — env vars only (any host)
bash extensions/firecrawl/install-generic.sh

# Firecrawl — Claude Code MCP config
bash extensions/firecrawl/install-claude.sh

# Firecrawl — Cursor MCP config
bash extensions/firecrawl/install-cursor.sh
```

```bash
# DataForSEO — same pattern
bash extensions/dataforseo/install-generic.sh
bash extensions/dataforseo/install-claude.sh
bash extensions/dataforseo/install-cursor.sh
```

Each extension folder contains `README.md`, `extension.json` (MCP package name and env vars), and the install scripts above.

## Additional Extensions (Community / Third-Party)

These extensions connect to external SEO data platforms. Each requires its own API credentials.

| Extension | What It Adds | Data Types | Env Var |
|-----------|-------------|------------|---------|
| **Ahrefs** | Backlink data, keyword rankings, content gap analysis | Referring domains, DR, keyword difficulty, SERP features | `AHREFS_API_KEY` |
| **SerpBase** | Live Google organic results via REST API — titles, URLs, snippets, positions for any keyword (`scripts/serp_api.py`) | Organic results, SERP positions, featured snippets | `SERPBASE_API_KEY` |
| **SE Ranking** | AI Share-of-Voice, GEO visibility tracking | AI citation share, visibility scores, rank tracking | `SE_RANKING_API_KEY` |
| **Profound** | LLM citation tracking across AI search engines | Citation frequency in ChatGPT, Perplexity, Claude, Gemini | `PROFOUND_API_KEY` |
| **Bing Webmaster + IndexNow** | Bing-specific indexation and instant submission | Bing crawl stats, indexed pages, URL submission | `BING_WEBMASTER_API_KEY` |
| **Unlighthouse** | Multi-page Lighthouse audits at scale | Per-page CWV scores, accessibility, best practices | Runs locally via npx |
| **Banana/Browserless** | Headless rendering as a service | JS-rendered HTML for SPA/CSR sites | `BROWSERLESS_API_KEY` |

### Extension Integration Pattern

All extensions follow the same pattern:
1. **Graceful degradation** — Core scripts work without any extensions. Extensions add richer data.
2. **Env-var detection** — Scripts check for the relevant env var. If absent, skip with a note.
3. **No vendor lock-in** — Data flows through the same Finding format regardless of source.
4. **MCP routing** — When MCP tools from these providers are available, the agent uses them per §21 (Script Toolbox).

### Using Extensions with the Agent

When an extension's MCP server is connected, the agent can:
- Pull live SERP data instead of relying on manual CSV input
- Cross-reference backlink data with content recommendations
- Track AI citation share across platforms (Profound + SE Ranking)
- Submit URLs for instant indexation (Bing IndexNow)

### Extension Install Pattern

Each extension (when available in the monorepo `extensions/` directory) follows:

```
extensions/<name>/
├── README.md           # Setup guide
├── extension.json      # MCP package name + env vars
├── install-generic.sh  # Env-var-only setup
├── install-claude.sh   # Claude Code MCP config
└── install-cursor.sh   # Cursor MCP config
```

For extensions not yet packaged, configure the MCP server directly in your IDE settings using the provider's official MCP package.

## Monorepo users

If you already have the full repo at disk, see **`extensions/README.md`** for the same install flow and design principles (graceful degradation, no vendor lock-in).
