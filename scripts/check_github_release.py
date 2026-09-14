#!/usr/bin/env python3
"""
Check that the current plugin version has a correct, published GitHub Release.

The Claude.ai web app Marketplace reads from GitHub Releases, NOT from commits or
tags alone. A published Release is required for the Marketplace Update button to
serve the new version to web app users.

"Published" is not enough. v1.13.0 was published as Latest while its tag sat on
the commit before the version bump (the tagged tree still declared 1.12.9) and
its notes were empty: the CHANGELOG extraction ran before the release PR merged
and found no [1.13.0] section. The old check reported that release as fine.
This one verifies, through the GitHub API rather than local git refs (a local
tag can disagree with the pushed one):

  * the release exists and is not a draft
  * its notes are not empty
  * the tag's commit on GitHub declares the version everywhere
    check_tag_matches_version.py looks, and CHANGELOG.md has its section
  * (warning only) the notes contain the CHANGELOG section's first line

A check that cannot be completed (API error, rate limit) is a problem, not a
pass. Set GITHUB_TOKEN or GH_TOKEN to raise the unauthenticated rate limit.

Usage:
    python3 scripts/check_github_release.py              # auto-detect repo + version
    python3 scripts/check_github_release.py --version 1.5.4
    python3 scripts/check_github_release.py --repo mykpono/ultimate-seo-geo
    python3 scripts/check_github_release.py --warn       # exit 0 even on problems (CI mode)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_tag_matches_version as tagcheck  # noqa: E402  (SOURCES and _extract: one definition of "declares")


class ApiError(Exception):
    """A GitHub API call that did not return usable data."""


def _get_version() -> str:
    p = ROOT / "plugins/ultimate-seo-geo/.claude-plugin/plugin.json"
    return json.loads(p.read_text(encoding="utf-8"))["version"]


def _get_repo() -> str:
    """Read remote.origin.url from .git/config and normalise to owner/repo."""
    git_config = ROOT / ".git/config"
    if not git_config.is_file():
        return ""
    for line in git_config.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("url = "):
            url = line[6:].strip().rstrip("/")
            if url.endswith(".git"):
                url = url[:-4]
            if "github.com/" in url:
                return url.split("github.com/")[-1]
            if "github.com:" in url:
                return url.split("github.com:")[-1]
    return ""


def _api_get(path: str, raw: bool = False):
    """GET a GitHub API path: parsed JSON (or text when raw), None on 404, ApiError otherwise."""
    headers = {
        "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ultimate-seo-geo-release-checker",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        hint = " (rate limited? set GITHUB_TOKEN or GH_TOKEN)" if e.code in (403, 429) else ""
        raise ApiError(f"GitHub API {e.code} {e.reason} for {path}{hint}") from e
    except (urllib.error.URLError, OSError) as e:
        raise ApiError(f"could not reach the GitHub API for {path}: {e}") from e
    if raw:
        return body
    try:
        return json.loads(body)
    except ValueError as e:
        raise ApiError(f"GitHub API returned invalid JSON for {path}") from e


def resolve_tag_commit(repo: str, tag: str) -> str | None:
    """The commit SHA a tag points at on GitHub, following annotated tags; None if the tag is absent."""
    ref = _api_get(f"/repos/{repo}/git/ref/tags/{urllib.parse.quote(tag)}")
    if ref is None:
        return None
    obj = ref.get("object") or {}
    for _ in range(5):
        if obj.get("type") != "tag":
            break
        tag_object = _api_get(f"/repos/{repo}/git/tags/{obj.get('sha')}")
        obj = (tag_object or {}).get("object") or {}
    return obj.get("sha") if obj.get("type") == "commit" else None


def read_file_at(repo: str, sha: str, path: str) -> str | None:
    return _api_get(f"/repos/{repo}/contents/{urllib.parse.quote(path)}?ref={sha}", raw=True)


def check_tag_tree(repo: str, sha: str, version: str) -> tuple[list, list, str]:
    """Version declarations at the tagged commit: (mismatches, unreadable, CHANGELOG text)."""
    files, mismatches, unreadable = {}, [], []
    for path, how in tagcheck.SOURCES:
        if path not in files:
            files[path] = read_file_at(repo, sha, path)
        text = files[path]
        found = tagcheck._extract(text, how) if text is not None else None
        label = f"{path} [{how}]"
        if found is None:
            unreadable.append(label)
        elif found != version:
            mismatches.append(f"{label} = {found}")
    changelog = read_file_at(repo, sha, "CHANGELOG.md") or ""
    if not re.search(rf"^## \[{re.escape(version)}\]", changelog, re.M):
        mismatches.append(f"CHANGELOG.md has no [{version}] section")
    return mismatches, unreadable, changelog


def changelog_section(changelog: str, version: str) -> str:
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", changelog, re.M | re.S)
    return m.group(1).strip() if m else ""


def verify_release(repo: str, version: str) -> dict:
    """Check the release for `version`: {"tag", "release_name", "passed", "warnings", "problems"}."""
    tag = f"v{version}"
    result = {"tag": tag, "release_name": None, "passed": [], "warnings": [], "problems": []}

    try:
        release = _api_get(f"/repos/{repo}/releases/tags/{urllib.parse.quote(tag)}")
    except ApiError as e:
        result["problems"].append(f"Could not read the release: {e}")
        return result
    if release is None:
        result["problems"].append(
            f"No GitHub Release found for tag {tag}.\n"
            f"  Create one: https://github.com/{repo}/releases/new?tag={tag}"
        )
        return result

    name = release.get("name") or tag
    result["release_name"] = name
    if release.get("draft"):
        result["problems"].append(f"Release '{name}' exists but is a DRAFT — publish it to update the Marketplace.")
    else:
        result["passed"].append(f"Release '{name}' is published")

    body = (release.get("body") or "").strip()
    if not body:
        result["problems"].append(
            f"Release '{name}' has EMPTY notes. The CHANGELOG extraction most likely ran before the release PR "
            f"merged. Fix, from an up-to-date main:\n"
            f"    gh release edit {tag} --notes \"$(sed -n '/^## \\[{version}\\]/,/^## \\[/p' CHANGELOG.md | sed '1d;$d')\""
        )

    try:
        sha = resolve_tag_commit(repo, tag)
        if sha is None:
            result["problems"].append(f"Tag {tag} does not exist on GitHub, or does not point at a commit.")
            return result
        mismatches, unreadable, changelog = check_tag_tree(repo, sha, version)
    except ApiError as e:
        result["problems"].append(f"Could not verify what tag {tag} points at: {e}")
        return result

    short = sha[:7]
    if mismatches:
        result["problems"].append(
            f"Tag {tag} on GitHub points at {short}, whose tree does not declare {version}:\n    "
            + "\n    ".join(mismatches)
            + "\n  The tag was almost certainly pushed before the release PR merged. Move it onto the release merge:\n"
            f"    git tag -f {tag} <release-merge-sha> && git push origin -f {tag}\n"
            f"  check_tag_matches_version.py {tag} prints the likely SHA."
        )
    else:
        result["passed"].append(f"Tag {tag} on GitHub -> {short} declares {version} everywhere, with a CHANGELOG section")
    if unreadable:
        result["warnings"].append(f"Could not read a version at {short} from: {', '.join(unreadable)}")

    if body:
        section = changelog_section(changelog, version)
        first_line = next((line.strip() for line in section.splitlines() if line.strip()), "")
        if first_line and first_line not in body:
            result["warnings"].append(
                f"Release notes do not contain the first line of the CHANGELOG [{version}] section "
                f"({first_line[:80]!r}); confirm they are this release's notes"
            )
        else:
            result["passed"].append("Release notes are present" + (" and match the CHANGELOG section" if first_line else ""))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the current plugin version has a correct, published GitHub Release.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--version", help="Version to check (default: read from plugin.json)")
    parser.add_argument("--repo", help="GitHub repo in owner/repo format (default: auto-detect from .git/config)")
    parser.add_argument(
        "--warn",
        action="store_true",
        help="Exit 0 even when a problem is found (use in CI to warn without blocking)",
    )
    args = parser.parse_args()

    version = args.version or _get_version()
    repo = args.repo or _get_repo()
    tag = f"v{version}"

    if not repo:
        print("⚠  Could not detect GitHub repo — pass --repo owner/repo")
        return 0 if args.warn else 1

    print(f"Checking GitHub Release: {repo} @ {tag} ...")
    result = verify_release(repo, version)
    for line in result["passed"]:
        print(f"✓ {line}")
    for line in result["warnings"]:
        print(f"⚠ {line}")

    if not result["problems"]:
        print(f"  Claude.ai web app Marketplace will serve {tag} after Anthropic cache refresh.")
        print(f"  URL: https://github.com/{repo}/releases/tag/{tag}")
        return 0

    prefix = "⚠ " if args.warn else "✗ "
    for problem in result["problems"]:
        print(f"{prefix}{problem}")
    print()
    print("  Why this matters:")
    print("    The Claude.ai web app Marketplace reads from GitHub Releases, not from commits.")
    print("    A missing or draft Release serves nothing new; a Release whose tag sits on the")
    print("    wrong commit serves the wrong code under the new version number.")
    return 0 if args.warn else 1


if __name__ == "__main__":
    raise SystemExit(main())
