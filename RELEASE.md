# Release checklist

Use this before tagging or publishing a new version.

1. **Bump the version** (same value in every place):
   - `SKILL.md` frontmatter → `metadata.version`
   - `.claude-plugin/marketplace.json` → `metadata.version` **and** `plugins[0].version`
   - `plugins/ultimate-seo-geo/.claude-plugin/plugin.json` → `version`
   - Optional: `README.md` and `plugins/ultimate-seo-geo/README.md` version badges
   - `CHANGELOG.md` entry for the release

2. **Sync the plugin bundle** from the canonical root skill (always run after editing root `SKILL.md` or `references/`):

   ```bash
   bash setup-plugin.sh
   ```

3. **Validate locally** (same checks as CI):

   ```bash
   python3 scripts/check-plugin-sync.py
   ```

   Broader manual checklist: **`CURSOR_VERIFY.md`**.

4. Commit, push, and tag as needed.

CI fails if root `SKILL.md` / `references/` disagree with `plugins/ultimate-seo-geo/skills/ultimate-seo-geo/` or if any version field above diverges.
