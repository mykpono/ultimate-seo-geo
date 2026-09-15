"""check_github_release.py must fail the release that shipped as v1.13.0.

That release was published as Latest while its tag sat on the commit before the
version bump -- the tagged tree still declared 1.12.9 -- and its notes were
empty. The old checker only asked whether a non-draft release existed, and said
"published ✓". These tests replay that release through a fake GitHub API and
pin every check, including the ones that must NOT fail: annotated tags, files
an old tag never had, and hand-written notes.
"""

import io
import json
import os
import sys
import urllib.error
import urllib.parse
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import check_github_release as cgr  # noqa: E402

REPO = "owner/repo"
GOOD = "b4dd102" + "0" * 33
BAD = "fb6e7a0" + "0" * 33
FIRST_LINE = "Every change here comes from reviewing the skill against another GEO auditor,"


def tree(version, with_section=True, drop=()):
    skill = f"---\nname: x\nversion: {version}\n---\n\n| **Version** | {version} |\n"
    files = {
        "SKILL.md": skill,
        "AGENTS.md": f"| **Version** | {version} |\n",
        "plugins/ultimate-seo-geo/skills/ultimate-seo-geo/SKILL.md": skill,
        ".claude-plugin/marketplace.json": json.dumps({"metadata": {"version": version},
                                                       "plugins": [{"version": version}]}),
        "plugins/ultimate-seo-geo/.claude-plugin/plugin.json": json.dumps({"version": version}),
        "CHANGELOG.md": (
            f"# Changelog\n\n## [Unreleased]\n\n_Nothing yet._\n\n## [{version}] - 2026-09-14\n\n"
            f"{FIRST_LINE}\nmore\n\n### Added\n\n- x\n\n## [1.12.8] - 2026-08-25\n\n- old\n"
            if with_section else "# Changelog\n\n## [Unreleased]\n\n- pending\n\n## [1.12.9] - 2026-09-14\n\n- old\n"
        ),
    }
    for path in drop:
        files.pop(path)
    return files


def release(body=f"{FIRST_LINE}\nmore\n\n### Added\n\n- x", draft=False):
    return {"name": "v1.13.0 — AI visibility checks and scoring fixes", "draft": draft, "body": body}


def commit_ref(sha):
    return {"object": {"type": "commit", "sha": sha}}


class FakeGitHub:
    def __init__(self, release=None, ref=None, tag_objects=None, trees=None, errors=None):
        self.release, self.ref = release, ref
        self.tag_objects, self.trees, self.errors = tag_objects or {}, trees or {}, errors or {}
        self.paths = []

    def __call__(self, path, raw=False):
        self.paths.append(path)
        for prefix, message in self.errors.items():
            if path.startswith(prefix):
                raise cgr.ApiError(message)
        base = f"/repos/{REPO}"
        if path.startswith(f"{base}/releases/tags/"):
            return self.release
        if path.startswith(f"{base}/git/ref/tags/"):
            return self.ref
        if path.startswith(f"{base}/git/tags/"):
            return self.tag_objects.get(path.rsplit("/", 1)[1])
        if path.startswith(f"{base}/contents/"):
            file_path, _, sha = path[len(f"{base}/contents/"):].partition("?ref=")
            return self.trees.get(sha, {}).get(urllib.parse.unquote(file_path))
        raise AssertionError(f"unexpected API path {path}")


def verify(fake, version="1.13.0"):
    with patch.object(cgr, "_api_get", side_effect=fake):
        return cgr.verify_release(REPO, version)


# --- the release as it should be ----------------------------------------------------------


def test_a_correct_release_passes():
    result = verify(FakeGitHub(release=release(), ref=commit_ref(GOOD), trees={GOOD: tree("1.13.0")}))

    assert result["problems"] == [] and result["warnings"] == []
    assert any("b4dd102 declares 1.13.0 everywhere" in p for p in result["passed"])
    assert any("match the CHANGELOG section" in p for p in result["passed"])


def test_an_annotated_tag_is_followed_to_its_commit():
    fake = FakeGitHub(release=release(), ref={"object": {"type": "tag", "sha": "tagobj1"}},
                      tag_objects={"tagobj1": {"object": {"type": "commit", "sha": GOOD}}},
                      trees={GOOD: tree("1.13.0")})

    assert verify(fake)["problems"] == []


# --- the release that shipped as v1.13.0 -----------------------------------------------------


def test_the_v1_13_0_release_fails_on_both_the_tag_and_the_notes():
    fake = FakeGitHub(release=release(body=""), ref=commit_ref(BAD), trees={BAD: tree("1.12.9", with_section=False)})
    result = verify(fake)

    assert len(result["problems"]) == 2
    empty, tag = result["problems"]
    assert "EMPTY notes" in empty and "gh release edit v1.13.0" in empty
    assert "points at fb6e7a0" in tag and "plugin.json [json:version] = 1.12.9" in tag
    assert "CHANGELOG.md has no [1.13.0] section" in tag
    assert not any("declares 1.13.0" in p for p in result["passed"])


@pytest.mark.parametrize("body", ["", "   \n\n  ", None])
def test_blank_notes_count_as_empty(body):
    fake = FakeGitHub(release=release(body=body), ref=commit_ref(GOOD), trees={GOOD: tree("1.13.0")})

    assert any("EMPTY notes" in p for p in verify(fake)["problems"])


def test_a_single_wrong_declaration_is_enough_to_fail():
    files = tree("1.13.0")
    files["plugins/ultimate-seo-geo/.claude-plugin/plugin.json"] = json.dumps({"version": "1.12.9"})
    fake = FakeGitHub(release=release(), ref=commit_ref(GOOD), trees={GOOD: files})

    [problem] = verify(fake)["problems"]
    assert "plugin.json [json:version] = 1.12.9" in problem


# --- existing checks keep working -----------------------------------------------------------


def test_a_draft_release_is_a_problem():
    fake = FakeGitHub(release=release(draft=True), ref=commit_ref(GOOD), trees={GOOD: tree("1.13.0")})

    assert any("DRAFT" in p for p in verify(fake)["problems"])


def test_a_missing_release_stops_before_checking_the_tag():
    fake = FakeGitHub(release=None)
    result = verify(fake)

    assert "No GitHub Release found for tag v1.13.0" in result["problems"][0]
    assert not any("/git/ref/" in p for p in fake.paths)


def test_a_tag_missing_on_github_is_a_problem():
    fake = FakeGitHub(release=release(), ref=None)

    assert any("does not exist on GitHub" in p for p in verify(fake)["problems"])


def test_an_api_failure_is_a_problem_not_a_pass():
    fake = FakeGitHub(release=release(), errors={f"/repos/{REPO}/git/ref/": "GitHub API 403 rate limit exceeded"})
    result = verify(fake)

    assert any("Could not verify what tag v1.13.0 points at" in p for p in result["problems"])


# --- things that must not fail --------------------------------------------------------------


def test_hand_written_notes_are_a_warning_not_a_problem():
    fake = FakeGitHub(release=release(body="Highlights: new AI checks."), ref=commit_ref(GOOD),
                      trees={GOOD: tree("1.13.0")})
    result = verify(fake)

    assert result["problems"] == []
    assert any("do not contain the first line" in w for w in result["warnings"])


def test_a_file_an_old_tag_never_had_is_a_warning_not_a_problem():
    fake = FakeGitHub(release=release(), ref=commit_ref(GOOD), trees={GOOD: tree("1.13.0", drop=("AGENTS.md",))})
    result = verify(fake)

    assert result["problems"] == []
    assert any("AGENTS.md [table]" in w for w in result["warnings"])


# --- CLI and HTTP ---------------------------------------------------------------------------


def run_main(fake, *argv):
    with patch.object(cgr, "_api_get", side_effect=fake), patch.object(sys, "argv", ["check_github_release.py", *argv]):
        return cgr.main()


def test_exit_codes(capsys):
    bad = FakeGitHub(release=release(body=""), ref=commit_ref(BAD), trees={BAD: tree("1.12.9", with_section=False)})
    good = FakeGitHub(release=release(), ref=commit_ref(GOOD), trees={GOOD: tree("1.13.0")})

    assert run_main(bad, "--repo", REPO, "--version", "1.13.0") == 1
    assert "✗ Release" in capsys.readouterr().out
    assert run_main(bad, "--repo", REPO, "--version", "1.13.0", "--warn") == 0
    assert run_main(good, "--repo", REPO, "--version", "1.13.0") == 0


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_api_get_sends_the_token_and_explains_rate_limits(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "t0ken")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    seen = {}

    def ok(req, timeout):
        seen["auth"] = req.get_header("Authorization")
        return FakeResponse(b'{"name": "v1"}')

    with patch.object(cgr.urllib.request, "urlopen", side_effect=ok):
        assert cgr._api_get("/repos/x/y/releases/tags/v1") == {"name": "v1"}
    assert seen["auth"] == "Bearer t0ken"

    def limited(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

    with patch.object(cgr.urllib.request, "urlopen", side_effect=limited):
        with pytest.raises(cgr.ApiError, match="set GITHUB_TOKEN or GH_TOKEN"):
            cgr._api_get("/repos/x/y/releases/tags/v1")

    def missing(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    with patch.object(cgr.urllib.request, "urlopen", side_effect=missing):
        assert cgr._api_get("/repos/x/y/releases/tags/v9") is None
