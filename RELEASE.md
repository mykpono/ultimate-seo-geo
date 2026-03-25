# Release checklist

Use this before tagging or publishing a new version. Run everything from the **repository root** (where `SKILL.md` and `setup-plugin.sh` live).

---

## 1. Bump the version (same value everywhere)

- `SKILL.md` frontmatter → `metadata.version`
- `.claude-plugin/marketplace.json` → `metadata.version` **and** `plugins[0].version`
- `plugins/ultimate-seo-geo/.claude-plugin/plugin.json` → `version`
- Optional: `README.md` and `plugins/ultimate-seo-geo/README.md` version badges
- `CHANGELOG.md` entry for the release

---

## 2. Sync the plugin bundle

Always run after editing root `SKILL.md` or `references/`:

```bash
bash setup-plugin.sh
```

---

## 3. Validate (required)

Same expectations as CI:

```bash
python3 scripts/check-plugin-sync.py
```

This verifies:

- Root `SKILL.md` matches `plugins/ultimate-seo-geo/skills/ultimate-seo-geo/SKILL.md`
- Root `references/` matches the plugin copy (filenames + contents)
- Root `scripts/*.py` (except `check-plugin-sync.py`) matches `plugins/.../skills/.../scripts/`
- Root `evals/` matches `plugins/.../skills/.../evals/`
- `metadata.version`, both marketplace version fields, and `plugin.json` use one **identical** version string

**Fix failures:** `bash setup-plugin.sh`, then re-run the script.

CI fails if root skill/references/scripts/evals disagree with the plugin tree or versions diverge.

**Audit script map:** `references/audit-script-matrix.md` (each automated step ↔ script). **Smoke all tools (truncated JSON):** `bash scripts/run_individual_checks.sh https://example.com`.

---

## 4. Pre-release verification (optional, deeper checks)

Use these for extra confidence before you tag.

### 4a — File existence

```bash
files=(
  ".claude-plugin/marketplace.json"
  "plugins/ultimate-seo-geo/.claude-plugin/plugin.json"
  "plugins/ultimate-seo-geo/skills/ultimate-seo-geo/SKILL.md"
  "plugins/ultimate-seo-geo/README.md"
  ".github/workflows/validate-plugin.yml"
  "scripts/check-plugin-sync.py"
)

missing=0
for f in "${files[@]}"; do
  if [ -f "$f" ]; then
    echo "✓ $f"
  else
    echo "✗ MISSING: $f"
    missing=$((missing + 1))
  fi
done

ref_dir="plugins/ultimate-seo-geo/skills/ultimate-seo-geo/references"
if [ -d "$ref_dir" ]; then
  count=$(find "$ref_dir" -maxdepth 1 -type f | wc -l | tr -d ' ')
  echo "✓ $ref_dir/ ($count files)"
  if [ "$count" -lt 18 ]; then
    echo "  WARNING: expected 18 reference files, found $count"
  fi
else
  echo "✗ MISSING: $ref_dir/"
  missing=$((missing + 1))
fi

echo ""
echo "Missing files: $missing"
[ "$missing" -eq 0 ]
```

### 4b — JSON shape (version-agnostic)

```bash
python3 - <<'EOF'
import json, re, sys

errors = []

try:
    with open(".claude-plugin/marketplace.json") as f:
        m = json.load(f)
    for field in ["name", "owner", "plugins"]:
        if field not in m:
            errors.append(f"marketplace.json missing: '{field}'")
    if "plugins" in m and m["plugins"]:
        p0 = m["plugins"][0]
        for pf in ["name", "source", "description", "version"]:
            if pf not in p0:
                errors.append(f"marketplace.json plugins[0] missing: '{pf}'")
        if p0.get("name") != "ultimate-seo-geo":
            errors.append("marketplace plugin name must be 'ultimate-seo-geo'")
        if p0.get("source") != "./plugins/ultimate-seo-geo":
            errors.append("marketplace source must be './plugins/ultimate-seo-geo'")
    print("✓ marketplace.json shape OK")
except FileNotFoundError:
    errors.append("marketplace.json not found")
except json.JSONDecodeError as e:
    errors.append(f"marketplace.json JSON error: {e}")

try:
    with open("plugins/ultimate-seo-geo/.claude-plugin/plugin.json") as f:
        p = json.load(f)
    for field in ["name", "version", "description", "author", "license"]:
        if field not in p:
            errors.append(f"plugin.json missing: '{field}'")
    if not re.match(r"^[a-z0-9-]+$", p.get("name", "")):
        errors.append("plugin.json name must be kebab-case")
    print("✓ plugin.json shape OK")
except FileNotFoundError:
    errors.append("plugin.json not found")
except json.JSONDecodeError as e:
    errors.append(f"plugin.json JSON error: {e}")

if errors:
    print(f"\n✗ {len(errors)} error(s):")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
print("\nAll JSON shape checks passed ✓")
EOF
```

### 4c — Root trees intact

```bash
python3 - <<'EOF'
import os, sys
errors = []
checks = {
    "SKILL.md": (100, "root SKILL.md"),
    "README.md": (50, "root README.md"),
    "CHANGELOG.md": (1, "CHANGELOG.md"),
    "LICENSE": (1, "LICENSE"),
}
for path, (min_lines, label) in checks.items():
    if not os.path.isfile(path):
        errors.append(f"missing {path}")
        continue
    n = len(open(path, encoding="utf-8").readlines())
    if n < min_lines:
        errors.append(f"{path} too short ({n} lines)")
    else:
        print(f"✓ {label} ({n} lines)")
for d in ["references", "scripts", "evals"]:
    if os.path.isdir(d):
        print(f"✓ {d}/ ({len(os.listdir(d))} entries)")
    else:
        errors.append(f"missing {d}/")
if errors:
    for e in errors:
        print("✗", e)
    sys.exit(1)
print("\nRoot trees OK ✓")
EOF
```

### 4d — README install strings

```bash
python3 - <<'EOF'
import sys
text = open("README.md", encoding="utf-8").read()
need = [
    "/plugin marketplace add mykpono/ultimate-seo-geo",
    "/plugin install ultimate-seo-geo@ultimate-seo-geo",
]
bad = [s for s in need if s not in text]
if bad:
    print("✗ README.md missing:", bad)
    sys.exit(1)
print("✓ README.md has marketplace install lines")
EOF
```

### 4e — Workflow file present and sane

```bash
python3 - <<'EOF'
import sys
p = ".github/workflows/validate-plugin.yml"
text = open(p, encoding="utf-8").read()
for s in ["Validate Plugin", "marketplace.json", "check-plugin-sync.py"]:
    if s not in text:
        print(f"✗ {p} missing expected fragment: {s!r}")
        sys.exit(1)
print(f"✓ {p} looks sane (basic check)")
EOF
```

Optional (if PyYAML is installed): `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/validate-plugin.yml'))"` — must not raise.

### 4f — Plugin file tree snapshot

```bash
echo "=== Plugin-related files ==="
find .claude-plugin plugins .github/workflows/validate-plugin.yml \
  -type f 2>/dev/null | sort | while read -r f; do
  printf "  %s  (%s lines)\n" "$f" "$(wc -l < "$f" | tr -d ' ')"
done
```

---

## 5. Smoke test (Claude Code)

In **Claude Code**, use **chat slash commands** (not Terminal/zsh):

```text
/plugin marketplace add mykpono/ultimate-seo-geo
/plugin install ultimate-seo-geo@ultimate-seo-geo
```

---

## 6. Ship

```bash
git status
```

Commit, push, and tag as needed.

---

## Optional: bootstrap bundle for another machine

Canonical plugin files live at the repo root. To share a minimal starter, zip **`setup-plugin.sh`** plus the paths it copies (see `setup-plugin.sh` — sources sit beside that script in this repo).
