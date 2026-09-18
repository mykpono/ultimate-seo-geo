#!/usr/bin/env python3
"""Release alignment helpers: CHANGELOG sections and the tag-vs-CHANGELOG lag check.

Two subcommands, both maintainer-only (excluded from the plugin bundle):

    python3 scripts/release_tools.py section 1.18.1          # print the [1.18.1] CHANGELOG body
    python3 scripts/release_tools.py section 1.18.1 --title  # print a one-line release title
    python3 scripts/release_tools.py lag                     # exit 1 if a CHANGELOG version was never tagged

`section` feeds the GitHub Release that .github/workflows/verify-release-tag.yml creates
after a tag passes verification, so the notes always come from the CHANGELOG at the tagged
commit and can never be empty. `lag` runs on every pull request: the CHANGELOG may be at
most ONE version ahead of the newest tag (the release PR being reviewed). Two or more
means a version was merged and never tagged, which is how 1.16.0 and 1.18.0 shipped without
a tag or a Release.

Why the rule is "one ahead", not "zero": the tag is created after the release PR merges,
so during that PR's CI the CHANGELOG is legitimately one version ahead.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

CHANGELOG = Path("CHANGELOG.md")
_SECTION = re.compile(r"^## \[(\d+\.\d+\.\d+)\][^\n]*\n(.*?)(?=^## \[|\Z)", re.M | re.S)


def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.strip().lstrip("v").split("."))


def changelog_versions(text: str) -> list[str]:
    """Every released version section in CHANGELOG order (newest first). [Unreleased] is skipped."""
    return [m.group(1) for m in _SECTION.finditer(text)]


def changelog_section(text: str, version: str) -> str:
    """The body of the [version] section, without its heading, stripped."""
    for m in _SECTION.finditer(text):
        if m.group(1) == version:
            return m.group(2).strip()
    return ""


def release_title(version: str, section: str, limit: int = 80) -> str:
    """'vX.Y.Z — first sentence of the lead paragraph', truncated at a word boundary."""
    lead = ""
    for para in re.split(r"\n\s*\n", section):
        para = para.strip()
        if para and not para.startswith("#") and not para.startswith("-"):
            lead = " ".join(para.split())
            break
    if not lead:
        return f"v{version}"
    sentence = re.split(r"(?<=[.!?])\s", lead, maxsplit=1)[0].rstrip(".")
    if len(sentence) > limit:
        sentence = sentence[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return f"v{version} — {sentence}"


def untagged_versions(versions: list[str], tags: list[str]) -> list[str]:
    """CHANGELOG versions newer than the newest tag, newest first. Empty when nothing is tagged
    yet and the CHANGELOG has at most one version."""
    tagged = [parse_version(t) for t in tags if re.fullmatch(r"v?\d+\.\d+\.\d+", t.strip())]
    newest = max(tagged) if tagged else None
    return [v for v in versions if newest is None or parse_version(v) > newest]


def lag_problems(versions: list[str], tags: list[str], allowed: int = 1) -> list[str]:
    """Versions that break the 'at most `allowed` ahead of the newest tag' rule (newest first)."""
    ahead = untagged_versions(versions, tags)
    return ahead if len(ahead) > allowed else []


def git_tags() -> list[str]:
    out = subprocess.run(["git", "tag", "--list", "v*"], capture_output=True, text=True, check=False)
    return [t for t in out.stdout.split() if t]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("section", help="print a CHANGELOG version section")
    s.add_argument("version")
    s.add_argument("--title", action="store_true", help="print a one-line release title instead")
    s.add_argument("--changelog", default=str(CHANGELOG))
    lag = sub.add_parser("lag", help="fail if the CHANGELOG is more than one version ahead of the newest tag")
    lag.add_argument("--changelog", default=str(CHANGELOG))
    lag.add_argument("--allowed", type=int, default=1)
    args = parser.parse_args(argv)

    text = Path(args.changelog).read_text(encoding="utf-8")
    if args.cmd == "section":
        version = args.version.lstrip("v")
        body = changelog_section(text, version)
        if not body:
            print(f"CHANGELOG.md has no [{version}] section", file=sys.stderr)
            return 1
        print(release_title(version, body) if args.title else body)
        return 0

    versions = changelog_versions(text)
    tags = git_tags()
    problems = lag_problems(versions, tags, args.allowed)
    newest = max((t for t in tags if re.fullmatch(r"v\d+\.\d+\.\d+", t)), key=parse_version, default="none")
    if problems:
        print(f"CHANGELOG.md is {len(problems)} versions ahead of the newest tag ({newest}); at most {args.allowed} allowed:")
        for v in problems:
            print(f"  [{v}] has no tag")
        print("\nEvery merged release PR must be followed by a tag (RELEASE.md § 6a). Tag the missing")
        print("versions at their bump-merge commits, or fold their notes into the next section.")
        return 1
    ahead = untagged_versions(versions, tags)
    print(f"ok  CHANGELOG {versions[0] if versions else 'empty'} vs newest tag {newest}: {len(ahead)} ahead")
    return 0


if __name__ == "__main__":
    sys.exit(main())
