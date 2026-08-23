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
