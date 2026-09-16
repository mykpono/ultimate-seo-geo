# Subagent capability definitions

Parallel workers for SEO audits are documented in **[`PARALLEL-AUDIT.md`](PARALLEL-AUDIT.md)** (single file: scopes, scripts, references).

## How platforms use this

| Platform | Interpretation |
|----------|----------------|
| **Cursor** | Host AI uses Task tool to spawn parallel subagents from `PARALLEL-AUDIT.md` |
| **Claude Code** | Can install excerpts under `~/.claude/agents/` with YAML frontmatter if desired |
| **Copilot / Gemini / others** | Host reads as context for how to parallelize script runs |

## Orchestration pattern

1. Run `site_mapper.py` to discover URLs when needed.
2. Spawn workers per row in `PARALLEL-AUDIT.md` (independent script groups only).
3. Merge results; deduplicate with `finding_verifier.py`.
4. Produce the unified report. The Health Score comes only from `generate_report.py`; without it, report "not scored" (§ 2).

See also `references/procedures/21-script-toolbox.md` (orchestrator-workers pattern, context compaction).
