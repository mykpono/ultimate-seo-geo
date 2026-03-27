#!/usr/bin/env bash
# setup-plugin.sh
# Run this from the root of the ultimate-seo-geo repo.
# It wires up all the plugin files in place.

set -e

# Avoid cp failing when source and destination are the same path (already laid out at repo root).
copy_unless_same() {
  local src="$1" dst="$2"
  local abs_src abs_dst
  abs_src="$(cd "$(dirname "$src")" && pwd)/$(basename "$src")"
  abs_dst="$(cd "$(dirname "$dst")" && pwd)/$(basename "$dst")"
  if [ "$abs_src" = "$abs_dst" ]; then
    return 0
  fi
  cp "$src" "$dst"
}

echo "Setting up Claude Code plugin structure..."

# ── 1. Create directories ───────────────────────────────────────────────────
mkdir -p .claude-plugin
mkdir -p plugins/ultimate-seo-geo/.claude-plugin
mkdir -p plugins/ultimate-seo-geo/skills/ultimate-seo-geo
mkdir -p .github/workflows

echo "  Directories created ✓"

# ── 2. Copy JSON + workflow from repo root (canonical source lives beside this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

copy_unless_same "$SCRIPT_DIR/.claude-plugin/marketplace.json"                      .claude-plugin/marketplace.json
copy_unless_same "$SCRIPT_DIR/plugins/ultimate-seo-geo/.claude-plugin/plugin.json"  plugins/ultimate-seo-geo/.claude-plugin/plugin.json
copy_unless_same "$SCRIPT_DIR/plugins/ultimate-seo-geo/README.md"                   plugins/ultimate-seo-geo/README.md
copy_unless_same "$SCRIPT_DIR/.github/workflows/validate-plugin.yml"                .github/workflows/validate-plugin.yml

echo "  Config files copied ✓"

# ── 3. Copy SKILL.md from repo root into plugin skill directory ─────────────
if [ -f "SKILL.md" ]; then
  cp SKILL.md plugins/ultimate-seo-geo/skills/ultimate-seo-geo/SKILL.md
  echo "  SKILL.md copied ✓"
else
  echo "  ERROR: SKILL.md not found at repo root. Are you running this from the repo root?"
  exit 1
fi

# ── 4. Copy references/ into plugin skill directory ─────────────────────────
if [ -d "references" ]; then
  cp -r references/ plugins/ultimate-seo-geo/skills/ultimate-seo-geo/references/
  REF_COUNT=$(ls references/ | wc -l | tr -d ' ')
  echo "  references/ copied ($REF_COUNT files) ✓"
else
  echo "  ERROR: references/ directory not found at repo root."
  exit 1
fi

# ── 5. Copy audit scripts + evals (exclude maintainer-only scripts) ─────────
# check-plugin-sync.py   — CI/repo health tool, not useful to plugin users
# check_github_release.py — requires gh CLI + network; maintainer deployment tool
SCRIPT_EXCLUDE_LIST="check-plugin-sync.py check_github_release.py"

mkdir -p plugins/ultimate-seo-geo/skills/ultimate-seo-geo/scripts
rm -f plugins/ultimate-seo-geo/skills/ultimate-seo-geo/scripts/*.py 2>/dev/null || true
SCRIPT_N=0
for f in scripts/*.py; do
  [ -f "$f" ] || continue
  base=$(basename "$f")
  excluded=0
  for ex in $SCRIPT_EXCLUDE_LIST; do
    [ "$base" = "$ex" ] && excluded=1 && break
  done
  if [ "$excluded" = "1" ]; then
    continue
  fi
  cp "$f" plugins/ultimate-seo-geo/skills/ultimate-seo-geo/scripts/
  SCRIPT_N=$((SCRIPT_N + 1))
done
if [ -f scripts/run_individual_checks.sh ]; then
  cp scripts/run_individual_checks.sh plugins/ultimate-seo-geo/skills/ultimate-seo-geo/scripts/
fi
echo "  scripts/ copied ($SCRIPT_N .py files + optional shell runner) ✓"

if [ -d "evals" ]; then
  rm -rf plugins/ultimate-seo-geo/skills/ultimate-seo-geo/evals
  cp -r evals/ plugins/ultimate-seo-geo/skills/ultimate-seo-geo/evals/
  EVAL_N=$(find evals -type f | wc -l | tr -d ' ')
  echo "  evals/ copied ($EVAL_N files) ✓"
else
  echo "  ERROR: evals/ directory not found at repo root."
  exit 1
fi

# ── 6. Validate JSON ────────────────────────────────────────────────────────
echo ""
echo "Validating JSON..."
python3 -c "
import json
for path in ['.claude-plugin/marketplace.json', 'plugins/ultimate-seo-geo/.claude-plugin/plugin.json']:
    with open(path) as f:
        json.load(f)
    print(f'  {path} ✓')
"

# ── 7. Done ─────────────────────────────────────────────────────────────────
echo ""
echo "========================================================"
echo "Plugin setup complete!"
echo ""
echo "New files added:"
echo "  .claude-plugin/marketplace.json"
echo "  plugins/ultimate-seo-geo/.claude-plugin/plugin.json"
echo "  plugins/ultimate-seo-geo/skills/ultimate-seo-geo/SKILL.md"
echo "  plugins/ultimate-seo-geo/skills/ultimate-seo-geo/references/"
echo "  plugins/ultimate-seo-geo/skills/ultimate-seo-geo/scripts/"
echo "  plugins/ultimate-seo-geo/skills/ultimate-seo-geo/evals/"
echo "  plugins/ultimate-seo-geo/README.md"
echo "  .github/workflows/validate-plugin.yml"
echo ""
echo "Next steps:"
echo "  1. python3 scripts/check-plugin-sync.py   # same checks as CI"
echo "  2. See RELEASE.md for version bumps before you tag"
echo "  3. git add . && git commit && git push"
echo ""
echo "Test install after pushing (type these in Claude Code chat, not in Terminal):"
echo "  /plugin marketplace add mykpono/ultimate-seo-geo"
echo "  /plugin install ultimate-seo-geo@ultimate-seo-geo"
echo "========================================================"
