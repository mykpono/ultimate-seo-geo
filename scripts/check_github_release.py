#!/usr/bin/env python3
"""
Check that the current plugin version has a published GitHub Release.

The Claude.ai web app Marketplace reads from GitHub Releases, NOT from commits or
tags alone. A published Release is required for the Marketplace Update button to
serve the new version to web app users.

Run after 'git push origin main --tags' to verify the Marketplace is up to date.

Usage:
    python3 scripts/check_github_release.py              # auto-detect repo + version
    python3 scripts/check_github_release.py --version 1.5.4
    python3 scripts/check_github_release.py --repo mykpono/ultimate-seo-geo
    python3 scripts/check_github_release.py --warn       # exit 0 even if missing (CI mode)
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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


def check_release(repo: str, tag: str) -> tuple[bool, str]:
    """Return (is_published, human_message). Uses GitHub public API — no auth needed."""
    url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ultimate-seo-geo-release-checker",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        name = data.get("name") or tag
        if data.get("draft", False):
            return (
                False,
                f"Release '{name}' exists but is a DRAFT — publish it to update the Marketplace.",
            )
        return True, f"GitHub Release '{name}' is published ✓"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return (
                False,
                f"No GitHub Release found for tag {tag}.\n"
                f"  Create one: https://github.com/{repo}/releases/new?tag={tag}\n"
                f"  Or via CLI: gh release create {tag} --title \"{tag} — <summary>\" --generate-notes",
            )
        return False, f"GitHub API error {e.code}: {e.reason}"
    except Exception as e:  # noqa: BLE001
        return False, f"Could not reach GitHub API: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the current plugin version has a published GitHub Release.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--version", help="Version to check (default: read from plugin.json)")
    parser.add_argument("--repo", help="GitHub repo in owner/repo format (default: auto-detect from .git/config)")
    parser.add_argument(
        "--warn",
        action="store_true",
        help="Exit 0 even if release is missing (use in CI to warn without blocking)",
    )
    args = parser.parse_args()

    version = args.version or _get_version()
    repo = args.repo or _get_repo()
    tag = f"v{version}"

    if not repo:
        print("⚠  Could not detect GitHub repo — pass --repo owner/repo")
        return 0 if args.warn else 1

    print(f"Checking GitHub Release: {repo} @ {tag} ...")
    is_published, message = check_release(repo, tag)

    if is_published:
        print(f"✓ {message}")
        print(f"  Claude.ai web app Marketplace will serve v{version} after Anthropic cache refresh.")
        print(f"  URL: https://github.com/{repo}/releases/tag/{tag}")
        return 0

    prefix = "⚠ " if args.warn else "✗ "
    print(f"{prefix}{message}")
    print()
    print("  Why this matters:")
    print("    The Claude.ai web app Marketplace reads from GitHub Releases, not from")
    print("    commits or tags alone. Without a published Release, the Marketplace")
    print("    Update button will NOT serve the new version to web app users.")
    return 0 if args.warn else 1


if __name__ == "__main__":
    raise SystemExit(main())
