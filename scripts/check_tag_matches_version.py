#!/usr/bin/env python3
"""Verify a git tag points at a tree that actually declares that version.

WHY THIS EXISTS
---------------
Both v1.12.2 and v1.12.3 were tagged against a local `main` that had not yet
pulled the release-prep merge. Each tag therefore pointed one merge too early,
and the tagged tree self-reported the *previous* version:

    tag v1.12.3  ->  SKILL.md says 1.12.2, no [1.12.3] section in CHANGELOG

The release notes were correct both times, because they are generated from the
CHANGELOG on disk rather than from the tag -- so nothing looked wrong until
someone installed from the tag. `check_version_sync.py` cannot catch this: it
checks the *working tree*, which is fine. The defect is in what the tag points at.

WHAT IT CHECKS
--------------
For tag `vX.Y.Z`, every version declaration in the tree at that tag must equal
`X.Y.Z`, and CHANGELOG.md must contain a `## [X.Y.Z]` section. A mismatch is
almost always the tag sitting on the wrong commit rather than a genuine version
error, so the failure output says where the correct commit probably is.

USAGE
-----
    python3 scripts/check_tag_matches_version.py v1.12.3   # explicit tag
    python3 scripts/check_tag_matches_version.py           # uses GITHUB_REF_NAME

Exit 0 = tag and tree agree.  Exit 1 = mismatch, or the tag does not exist.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

# path -> how to pull the version out of that file's contents at the tagged rev
SOURCES: list[tuple[str, str]] = [
    ("SKILL.md", "frontmatter"),
    ("SKILL.md", "table"),
    ("AGENTS.md", "table"),
    ("plugins/ultimate-seo-geo/skills/ultimate-seo-geo/SKILL.md", "frontmatter"),
    ("plugins/ultimate-seo-geo/skills/ultimate-seo-geo/SKILL.md", "table"),
    (".claude-plugin/marketplace.json", "json:metadata.version"),
    (".claude-plugin/marketplace.json", "json:plugins.0.version"),
    ("plugins/ultimate-seo-geo/.claude-plugin/plugin.json", "json:version"),
]


def _git(*args: str) -> tuple[int, str]:
    p = subprocess.run(["git", *args], capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


def _show(rev: str, path: str) -> str | None:
    code, out = _git("show", f"{rev}:{path}")
    return out if code == 0 else None


def _extract(text: str, how: str) -> str | None:
    if how == "frontmatter":
        m = re.search(r"^version:\s*(.+)$", text, re.M)
        return m.group(1).strip().strip("'\"") if m else None
    if how == "table":
        m = re.search(r"\*\*Version\*\*\s*\|\s*(.+?)(?:\s*\||\s*$)", text, re.M)
        return m.group(1).strip() if m else None
    if how.startswith("json:"):
        try:
            data = json.loads(text)
            for key in how[5:].split("."):
                data = data[int(key)] if isinstance(data, list) else data[key]
            return str(data).strip()
        except (KeyError, IndexError, ValueError):
            return None
    raise ValueError(f"unknown extractor: {how}")


def _likely_correct_commit(expected: str) -> str | None:
    """Find the commit where `expected` was introduced — the release-prep merge.

    Walking newest-first and returning the first match finds the *newest* commit
    declaring the version, which over-shoots as soon as `main` moves past the
    release. That is what happened on v1.12.4: the checker suggested the merge
    after the release-prep one, which carried work the release was never meant
    to include.

    Instead, walk the **first-parent** history back through the contiguous run of
    commits declaring `expected`, and return the oldest of them — the merge that
    put the bump on main. First-parent matters: a plain walk descends into the
    release branch and returns the bump commit itself, which is not what you tag.
    """
    # --first-parent keeps us on the main line. Without it the walk descends into
    # the release branch and returns the bump commit itself (e.g. 432e14d) rather
    # than the merge that put it on main (db531ae) — which is what you tag.
    code, out = _git("log", "--first-parent", "--format=%H", "-80", "HEAD")
    if code != 0:
        return None

    candidate = None
    for sha in out.splitlines():
        text = _show(sha, "SKILL.md")
        declares = bool(text) and _extract(text, "frontmatter") == expected
        if declares:
            candidate = sha          # keep walking back through the run
        elif candidate is not None:
            break                    # walked past the bump; candidate is its first commit

    if candidate is None:
        return None
    code2, short = _git("rev-parse", "--short", candidate)
    return short if code2 == 0 else candidate[:7]


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_REF_NAME", "")
    if not tag:
        print("usage: check_tag_matches_version.py <tag>   (or set GITHUB_REF_NAME)")
        return 1

    m = re.fullmatch(r"v?(\d+\.\d+\.\d+)", tag)
    if not m:
        print(f"'{tag}' is not a vX.Y.Z release tag — nothing to check.")
        return 0
    expected = m.group(1)

    code, _ = _git("rev-parse", "--verify", f"{tag}^{{commit}}")
    if code != 0:
        print(f"FAIL: tag '{tag}' does not exist locally. Fetch tags first: git fetch --tags")
        return 1
    _, tagged_sha = _git("rev-parse", "--short", f"{tag}^{{commit}}")

    print(f"Tag {tag} -> {tagged_sha}; expecting every version declaration to read {expected}")

    mismatches: list[str] = []
    missing: list[str] = []
    for path, how in SOURCES:
        text = _show(tag, path)
        if text is None:
            missing.append(f"{path} (not present at {tag})")
            continue
        found = _extract(text, how)
        label = f"{path} [{how}]"
        if found is None:
            missing.append(f"{label} — no version found")
        elif found != expected:
            mismatches.append(f"{label} = {found}")
        else:
            print(f"  ok  {label} = {found}")

    changelog = _show(tag, "CHANGELOG.md") or ""
    if re.search(rf"^## \[{re.escape(expected)}\]", changelog, re.M):
        print(f"  ok  CHANGELOG.md has a [{expected}] section")
    else:
        mismatches.append(f"CHANGELOG.md has no [{expected}] section")

    if missing:
        print("\nWARNING — could not read:")
        for item in missing:
            print(f"  {item}")

    if not mismatches:
        print(f"\nTag {tag} and its tree agree at {expected} ✓")
        return 0

    print(f"\nFAIL: tag {tag} points at a tree that does not declare {expected}:")
    for item in mismatches:
        print(f"  {item}")

    hint = _likely_correct_commit(expected)
    print(
        "\nThis is almost always the tag sitting on the wrong commit — tagged before the\n"
        "release-prep merge was pulled. It is what happened to v1.12.2 and v1.12.3."
    )
    if hint:
        print(f"\nThe {expected} version bump landed at {hint} — that is almost certainly the\nrelease-prep merge and the correct target:")
        print(f"    git tag -f {tag} {hint} && git push origin -f {tag}")
    else:
        print("\nFind the commit that carries the version bump, then move the tag onto it.")
    print(f"\nVerify with: git rev-parse --short {tag}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
