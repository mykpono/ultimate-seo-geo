"""The tag/version checker must actually detect a misplaced tag.

`check_version_sync.py` verifies the *working tree* is internally consistent,
which it always is right after a bump. It cannot see the failure that shipped
twice in a row: a tag pointing one merge too early, so the *tagged* tree
self-reports the previous version while the working tree looks fine.

Both v1.12.2 and v1.12.3 landed that way. The published release notes were
correct each time -- they are generated from the CHANGELOG on disk, not from the
tag -- so nothing looked wrong until someone installed from the tag.

These tests drive the extractors directly rather than creating throwaway git
tags, so they run anywhere without mutating the repository.
"""

import importlib.util
import json
import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPT = os.path.join(ROOT, "scripts", "check_tag_matches_version.py")

spec = importlib.util.spec_from_file_location("tagcheck", SCRIPT)
tagcheck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tagcheck)


def test_frontmatter_extractor():
    assert tagcheck._extract("---\nname: x\nversion: 1.12.3\n---\n", "frontmatter") == "1.12.3"
    assert tagcheck._extract("version: '1.2.0'\n", "frontmatter") == "1.2.0"
    assert tagcheck._extract("no version here\n", "frontmatter") is None


def test_table_extractor():
    assert tagcheck._extract("| **Version** | 1.12.3 |\n", "table") == "1.12.3"
    assert tagcheck._extract("| **Name** | thing |\n", "table") is None


def test_json_extractor_handles_nesting_and_list_indexes():
    doc = json.dumps({"metadata": {"version": "1.12.3"}, "plugins": [{"version": "1.12.3"}]})
    assert tagcheck._extract(doc, "json:metadata.version") == "1.12.3"
    assert tagcheck._extract(doc, "json:plugins.0.version") == "1.12.3"
    assert tagcheck._extract(doc, "json:missing.key") is None
    assert tagcheck._extract("{not json", "json:version") is None


@pytest.mark.parametrize(
    "tag,expected",
    [("v1.12.3", "1.12.3"), ("1.12.3", "1.12.3"), ("v0.1.0", "0.1.0")],
)
def test_release_tags_are_recognised(tag, expected):
    import re
    m = re.fullmatch(r"v?(\d+\.\d+\.\d+)", tag)
    assert m and m.group(1) == expected


@pytest.mark.parametrize("tag", ["v1.12", "nightly", "v1.12.3-rc1", "release-1.12.3"])
def test_non_release_tags_are_skipped(tag):
    """A non-release tag must be ignored, not reported as a failure."""
    import re
    assert re.fullmatch(r"v?(\d+\.\d+\.\d+)", tag) is None


def test_every_version_source_is_present_in_the_working_tree():
    """The paths the checker reads must exist, or it silently checks nothing.

    A typo in SOURCES would make the check pass by finding nothing to compare —
    the worst failure mode for a guard, since it looks green.
    """
    missing = [p for p, _ in tagcheck.SOURCES if not os.path.isfile(os.path.join(ROOT, p))]
    assert not missing, f"check_tag_matches_version.py reads paths that do not exist: {missing}"


def test_sources_cover_every_file_that_declares_a_version():
    """If a new file starts declaring the version, the checker must learn about it.

    v1.8.1 shipped with AGENTS.md left on the previous version while every other
    file was bumped — exactly what an incomplete SOURCES list would miss.
    """
    tracked = {p for p, _ in tagcheck.SOURCES}
    expected = {
        "SKILL.md",
        "AGENTS.md",
        ".claude-plugin/marketplace.json",
        "plugins/ultimate-seo-geo/.claude-plugin/plugin.json",
        "plugins/ultimate-seo-geo/skills/ultimate-seo-geo/SKILL.md",
    }
    assert expected <= tracked, f"version-declaring files not checked at tag time: {expected - tracked}"

def test_likely_correct_commit_returns_the_bump_merge_not_a_later_one():
    """The suggested fix must be where the bump landed, not the newest match.

    v1.12.4 exposed both failure modes in turn. Returning the *newest* commit
    declaring the version over-shoots as soon as main moves past the release --
    it suggested the merge after the release-prep one, carrying work the release
    was never meant to include. Walking plain history instead under-shoots into
    the release branch and returns the bump commit, which is not on main and is
    not what you tag.

    Asserted as a property rather than a fixed SHA, so it cannot rot: the commit
    returned must declare the version, and its first parent must not -- that is
    precisely "the merge that introduced it on the main line".
    """
    import subprocess

    def _sh(*args):
        return subprocess.run(["git", *args], capture_output=True, text=True)

    # Pick a version that exists in this repo's history.
    head = _sh("show", "HEAD:SKILL.md").stdout
    version = tagcheck._extract(head, "frontmatter")
    assert version, "could not read the current version from SKILL.md"

    sha = tagcheck._likely_correct_commit(version)
    assert sha, f"helper found no commit introducing {version}"

    at_commit = tagcheck._show(sha, "SKILL.md")
    assert at_commit and tagcheck._extract(at_commit, "frontmatter") == version, (
        f"{sha} does not declare {version}"
    )

    parent = _sh("rev-parse", f"{sha}^1")
    if parent.returncode == 0:
        at_parent = tagcheck._show(parent.stdout.strip(), "SKILL.md")
        parent_version = tagcheck._extract(at_parent, "frontmatter") if at_parent else None
        assert parent_version != version, (
            f"{sha} is not where {version} was introduced — its first parent already "
            f"declares {parent_version}, so the helper is over-shooting."
        )

    # "declares X, parent does not" is true of the branch commit as well as the merge
    # that landed it, so it cannot tell them apart on its own. The commit must also sit
    # on the first-parent path — that is what makes it taggable.
    main_line = _sh("rev-list", "--first-parent", "HEAD")
    if main_line.returncode == 0:
        full = _sh("rev-parse", sha).stdout.strip()
        assert full in main_line.stdout.split(), (
            f"{sha} declares {version} but is not on the first-parent path of HEAD — it is a "
            f"commit inside a release branch, not the merge that put the bump on main. "
            f"Tagging it would point at history that was never on the main line."
        )


def test_likely_correct_commit_walks_first_parent_only():
    """Guard the flag in the actual git call, not merely somewhere in the source.

    The first version of this test searched the whole function body for the string
    "--first-parent". That string also appears in the docstring and a comment, so
    deleting the flag from the `_git(...)` call left the test green — a guard that
    passes by matching its own explanation.
    """
    import inspect

    src = inspect.getsource(tagcheck._likely_correct_commit)
    call = re.search(r'_git\(\s*"log"\s*,(.*?)\)', src, re.S)
    assert call, "_likely_correct_commit no longer calls _git('log', ...)"
    assert '"--first-parent"' in call.group(1), (
        "_likely_correct_commit's git log call no longer passes --first-parent. Without "
        "it the walk descends into the release branch and suggests a commit that is not "
        f"on main.\n  call args: {call.group(1).strip()}"
    )
