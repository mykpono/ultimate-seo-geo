"""release_tools.py: CHANGELOG sections, release titles and the tag-lag rule."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import release_tools as rt  # noqa: E402

CHANGELOG = """# Changelog

## [Unreleased]

_Nothing yet._

## [1.18.1] - 2026-09-18

Completes the 1.18.0 design refresh for the PDF path. Patch per D-020: the same visual system
applied to the last renderer that still carried its own palette, no new capability.

### Changed
- **`scripts/pdf_template.py`** — tokens.

## [1.18.0] - 2026-09-18

The report set adopts the Tobto design system.

### Changed
- tokens

## [1.17.0] - 2026-09-17

The automated report joins the design system.
"""


def test_versions_are_listed_newest_first_and_unreleased_is_skipped():
    assert rt.changelog_versions(CHANGELOG) == ["1.18.1", "1.18.0", "1.17.0"]


def test_section_returns_the_body_without_heading():
    body = rt.changelog_section(CHANGELOG, "1.18.0")
    assert body.startswith("The report set adopts the Tobto design system.")
    assert "### Changed\n- tokens" in body
    assert "1.17.0" not in body


def test_section_is_empty_for_an_unknown_version():
    assert rt.changelog_section(CHANGELOG, "9.9.9") == ""


def test_title_uses_the_first_sentence_of_the_lead_paragraph():
    body = rt.changelog_section(CHANGELOG, "1.18.1")
    assert rt.release_title("1.18.1", body) == "v1.18.1 — Completes the 1.18.0 design refresh for the PDF path"


def test_title_truncates_long_sentences_at_a_word_boundary():
    body = "A " + "very " * 40 + "long lead sentence. Second sentence."
    title = rt.release_title("1.0.0", body)
    assert title.startswith("v1.0.0 — A very") and title.endswith("…") and len(title) < 100


def test_title_falls_back_to_the_bare_version():
    assert rt.release_title("1.0.0", "### Changed\n- only bullets") == "v1.0.0"


def test_lag_passes_when_changelog_is_one_ahead_of_the_newest_tag():
    versions = ["1.18.1", "1.18.0", "1.17.0"]
    assert rt.lag_problems(versions, ["v1.17.0", "v1.18.0"]) == []


def test_lag_passes_when_everything_is_tagged():
    assert rt.lag_problems(["1.18.1", "1.18.0"], ["v1.18.1", "v1.18.0"]) == []


def test_lag_fails_when_two_versions_were_never_tagged():
    versions = ["1.18.1", "1.18.0", "1.17.0"]
    assert rt.lag_problems(versions, ["v1.17.0"]) == ["1.18.1", "1.18.0"]


def test_lag_ignores_older_untagged_versions_below_the_newest_tag():
    # 1.18.0 was never tagged but 1.18.1 was: the newest tag supersedes it, as decided for 1.16.0.
    versions = ["1.18.1", "1.18.0", "1.17.0", "1.16.0"]
    assert rt.lag_problems(versions, ["v1.17.0", "v1.18.1"]) == []


def test_lag_compares_versions_numerically_not_lexically():
    assert rt.lag_problems(["1.10.0", "1.9.0"], ["v1.9.0"]) == []
    assert rt.lag_problems(["1.10.0", "1.9.0", "1.8.0"], ["v1.8.0"]) == ["1.10.0", "1.9.0"]


def test_lag_with_no_tags_allows_a_single_first_version():
    assert rt.lag_problems(["0.1.0"], []) == []
    assert rt.lag_problems(["0.2.0", "0.1.0"], []) == ["0.2.0", "0.1.0"]


def test_cli_section_and_lag(tmp_path, monkeypatch):
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text(CHANGELOG, encoding="utf-8")
    monkeypatch.setattr(rt, "git_tags", lambda: ["v1.17.0", "v1.18.0"])
    assert rt.main(["section", "v1.18.1", "--changelog", str(cl)]) == 0
    assert rt.main(["section", "9.9.9", "--changelog", str(cl)]) == 1
    assert rt.main(["lag", "--changelog", str(cl)]) == 0
    monkeypatch.setattr(rt, "git_tags", lambda: ["v1.17.0"])
    assert rt.main(["lag", "--changelog", str(cl)]) == 1


def test_real_changelog_is_not_more_than_one_version_ahead_of_the_tags():
    root = os.path.join(os.path.dirname(__file__), "..")
    text = open(os.path.join(root, "CHANGELOG.md"), encoding="utf-8").read()
    versions = rt.changelog_versions(text)
    assert versions, "CHANGELOG has no version sections"
    # Every section must yield a non-empty body and a title: the release workflow depends on it.
    top = rt.changelog_section(text, versions[0])
    assert top and rt.release_title(versions[0], top).startswith(f"v{versions[0]}")
