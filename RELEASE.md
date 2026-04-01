# Release checklist

Use this before tagging or publishing a new version. Run everything from the **repository root** (where `SKILL.md` and `setup-plugin.sh` live).

> **Quick order:** Bump version → Sync bundle → Validate → Commit + Push → **Create GitHub Release** → Verify release

---

## ⚠️ REQUIRED: GitHub Release must be created every time

The Claude Code Marketplace reads from **GitHub Releases**, not commits. If you push code without creating a release, users will not receive the update.

**Never skip this command:**
```bash
gh release create vX.Y.Z \
  --title "vX.Y.Z — short summary" \
  --notes "release notes" \
  --target main
```

**Verify immediately after:**
```bash
python3 scripts/check_github_release.py   # must exit 0
gh release list --limit 3                 # v1.8.0 must appear as Latest
```

---

## 1. Bump the version (same value everywhere)

- `SKILL.md` frontmatter → top-level `version:` and `updated:` (must match marketplace + `plugin.json`)
- `SKILL.md` body → **Skill at a glance** table: keep **Version** / **Updated** in sync with frontmatter
- `.claude-plugin/marketplace.json` → `metadata.version` **and** `plugins[0].version`
- `plugins/ultimate-seo-geo/.claude-plugin/plugin.json` → `version`
- Optional: `README.md` and `plugins/ultimate-seo-geo/README.md` version badges
- `CHANGELOG.md` entry for the release

---

## 1b. Review README.md before every release

Check these sections manually — they contain counts and metrics that drift when evals or features change:

- **Eval Results table** (`## Eval Results`) — update prompt count and assertion count to match `evals/evals.json`:
  ```bash
  python3 -c "
  import json; d=json.load(open('evals/evals.json'))
  e=d['evals']; a=sum(len(x.get('assertions',[])) for x in e)
  print(f'Prompts: {len(e)}  Assertions: {a}')
  "
  ```
  Then confirm `README.md` line `**N** prompts, **N** assertions` matches.

- **File tree comment** (`└── evals/ ← N scenarios`) — must match the prompt count above.

- **Script count** (`scripts/` description) — verify the stated `.py` count matches `ls scripts/*.py | wc -l`.

- **Feature bullets / capability claims** — skim for anything that references a number (e.g., "24 scripts", "21 reference files") and confirm it's still accurate.

Run this quick README sanity check:
```bash
python3 - << 'EOF'
import json, os, re

errors = []

# Eval counts
d = json.load(open("evals/evals.json"))
ev = d["evals"]
n_prompts = len(ev)
n_assert = sum(len(e.get("assertions", [])) for e in ev)

readme = open("README.md", encoding="utf-8").read()

pat = re.search(r'\*\*(\d+)\*\* prompts.*?\*\*(\d+)\*\* assertions', readme)
if pat:
    rp, ra = int(pat.group(1)), int(pat.group(2))
    if rp != n_prompts: errors.append(f"README prompt count {rp} != actual {n_prompts}")
    if ra != n_assert:  errors.append(f"README assertion count {ra} != actual {n_assert}")
    if not errors: print(f"✓ Eval counts match: {n_prompts} prompts, {n_assert} assertions")
else:
    errors.append("README missing eval counts pattern")

# Script count
py_scripts = len([f for f in os.listdir("scripts") if f.endswith(".py") and f != "check-plugin-sync.py"])
for pat_str in [r"(\d+) bundled \.py", r"(\d+).*\.py.*scripts"]:
    m = re.search(pat_str, readme)
    if m and int(m.group(1)) != py_scripts:
        errors.append(f"README script count {m.group(1)} != actual {py_scripts}")
        break
else:
    print(f"✓ Script count looks fine ({py_scripts} .py scripts)")

if errors:
    for e in errors: print(f"✗ {e}")
    raise SystemExit(1)
print("README sanity check passed ✓")
EOF
```

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

After pushing and creating the GitHub Release, also run:

```bash
python3 scripts/check_github_release.py
```

This verifies:

- Root `SKILL.md` matches `plugins/ultimate-seo-geo/skills/ultimate-seo-geo/SKILL.md`
- Root `references/` matches the plugin copy (filenames + contents)
- Root `scripts/*.py` (except `check-plugin-sync.py`) matches `plugins/.../skills/.../scripts/`
- Root `evals/` matches `plugins/.../skills/.../evals/`
- `SKILL.md` `version:`, both marketplace version fields, and `plugin.json` use one **identical** version string

**Fix failures:** `bash setup-plugin.sh`, then re-run the script.

CI fails if root skill/references/scripts/evals disagree with the plugin tree or versions diverge.

**Audit script map:** `references/audit-script-matrix.md` (each automated step ↔ script). **Dependencies:** after `pip install -r requirements.txt`, `python3 scripts/requirements-check.py` should print OK. **Eval fixtures:** `python3 scripts/score_eval_transcript.py --all-fixtures` (exit 0). **Smoke all tools (truncated JSON):** `bash scripts/run_individual_checks.sh https://example.com` (starts with requirements check).

> **Eval growth rule:** Every bug fixed in SKILL.md must have a corresponding new eval fixture (assertion) before the fix merges. No exceptions. Target: suite grows from 10 → 25 scenarios over 6 months, driven by real failures — no dedicated sprint required. See `_local/strategy-directives/monthly-review-template.md` for the review cadence.

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

## 6. Ship (commit + push + release — all three required)

```bash
git add -A && git commit -m "vX.Y.Z — summary"
git push origin main
```

### 6a. Create GitHub Release (REQUIRED — never skip)

The Claude.ai web app Marketplace reads from GitHub Releases, not commits or tags alone. **Without a published Release, the Marketplace will NOT serve the new version.**

```bash
gh release create vX.Y.Z \
  --title "vX.Y.Z — summary" \
  --notes "release notes" \
  --target main
```

**Verify immediately (must exit 0):**
```bash
python3 scripts/check_github_release.py
gh release list --limit 3   # confirm vX.Y.Z appears as Latest
```

> If you pushed and forgot the release: run the `gh release create` command above now. The Marketplace will pick it up within minutes.

### 6b. Push update to local Claude terminal install (always do this)

After every GitHub push, sync the plugin into Claude's local install directory:

```bash
bash setup-plugin.sh && \
cp -r plugins/ultimate-seo-geo/. \
  ~/.claude/plugins/marketplaces/ultimate-seo-geo/plugins/ultimate-seo-geo/
echo "✓ Claude terminal plugin updated — restart claude to reload"
```

Then restart Claude Code (type `exit`, reopen terminal, run `claude`).

### 6c. Reinstall marketplace cache (always do this)

The Claude Code marketplace cache is a local git clone. It does **not** auto-pull — you must update it manually after every push:

```bash
cd ~/.claude/plugins/marketplaces/ultimate-seo-geo && \
  git fetch origin && git reset --hard origin/main && \
  echo "✓ Marketplace cache updated to $(git log --oneline -1)"
```

Then restart Claude Code to reload the plugin.

**Verify version matches:**
```bash
python3 -c "
import json
p = json.load(open('plugins/ultimate-seo-geo/.claude-plugin/plugin.json'))
print(f'Marketplace cache version: {p[\"version\"]}')
"
```

### 6d. Verify release

```bash
python3 scripts/check_github_release.py
```

- **Exit 0** = GitHub Release is published → Marketplace is live.
- **Exit 1** = Release missing → go back to step 6a.

---

## 7. Update instructions per surface

### Claude.ai web app
After publishing the GitHub Release, users must remove + re-add the plugin to get the update. The Update button triggers Anthropic's server-side cache refresh, which may take time.

1. **Customize → Ultimate seo geo → `...` → Remove**
2. **Marketplace → search `ultimate-seo-geo` → Add**
3. Start a new chat

### Claude Code (terminal)
Run step 6b above after every push (it's the canonical update path).

For a fresh install on a new machine:
```bash
git clone https://github.com/mykpono/ultimate-seo-geo.git \
  ~/.claude/plugins/marketplaces/ultimate-seo-geo
```

Then inside Claude Code:
```
/plugin marketplace add mykpono/ultimate-seo-geo
/plugin install ultimate-seo-geo@ultimate-seo-geo
```

### Cursor IDE (local skills)
```bash
rsync -a --delete --exclude='.git/' \
  "/path/to/ultimate-seo-geo/" ~/.claude/skills/seo/
```

---

## Optional: bootstrap bundle for another machine

Canonical plugin files live at the repo root. To share a minimal starter, zip **`setup-plugin.sh`** plus the paths it copies (see `setup-plugin.sh` — sources sit beside that script in this repo).
