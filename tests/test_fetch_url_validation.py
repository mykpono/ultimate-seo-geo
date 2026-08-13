"""Both fetchers must validate URLs they did not choose themselves.

link_profile fetches the <loc> entries of the audited site's sitemap and the
hrefs of its pages. redirect_checker follows the Location header of whatever it
just fetched. In both cases the audited host picks the next URL, so the guard
has to run on every request rather than only on the seed.
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import link_profile  # noqa: E402
import redirect_checker  # noqa: E402


@pytest.fixture
def secret_file():
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("SUPER_SECRET_CONTENTS")
        path = fh.name
    yield path
    os.unlink(path)


# --- link_profile.fetch_page ------------------------------------------------

def test_file_scheme_is_refused(secret_file):
    """A sitemap <loc> of file:///... must not read local disk."""
    _, body = link_profile.fetch_page(f"file://{secret_file}")

    assert "SUPER_SECRET_CONTENTS" not in body
    assert body == ""


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/x",
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8080/admin",
        "http://localhost/admin",
        "http://[::1]/admin",
        "http://10.0.0.5/internal",
        "http://user:pass@example.com/",
        "http://2130706433/",  # decimal-encoded 127.0.0.1
    ],
)
def test_unsafe_targets_return_empty(url):
    final_url, body = link_profile.fetch_page(url)

    assert body == "", f"{url} should not have been fetched"
    assert final_url == url


def test_ordinary_https_url_is_not_rejected_by_the_guard(monkeypatch):
    """The guard must not block normal targets; network itself is stubbed."""
    seen = {}

    class FakeResponse:
        url = "https://example.com/"

        def read(self):
            return b"<html>ok</html>"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        return FakeResponse()

    monkeypatch.setattr(link_profile.urllib.request, "urlopen", fake_urlopen)

    final_url, body = link_profile.fetch_page("https://example.com/")

    assert body == "<html>ok</html>"
    assert seen["url"].startswith("https://example.com")


# --- redirect_checker per-hop validation ------------------------------------

class FakeHeadResponse:
    def __init__(self, status_code, location=None):
        self.status_code = status_code
        self.headers = {"Location": location} if location else {}
        self.elapsed = __import__("datetime").timedelta(milliseconds=5)


def test_redirect_to_metadata_endpoint_is_refused(monkeypatch):
    """One 302 must not walk the checker into cloud metadata."""
    responses = [
        FakeHeadResponse(302, "http://169.254.169.254/latest/meta-data/"),
        FakeHeadResponse(200),
    ]
    calls = []

    def fake_head(url, **kwargs):
        calls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(redirect_checker.requests, "head", fake_head)

    result = redirect_checker.check_redirects("https://example.com/")

    assert not any("169.254.169.254" in c for c in calls), (
        f"followed the hop into link-local space: {calls}"
    )
    assert any("Refused to follow" in i for i in result["issues"]), result["issues"]


def test_ordinary_redirect_chain_still_followed(monkeypatch):
    responses = [
        FakeHeadResponse(301, "https://example.com/new"),
        FakeHeadResponse(200),
    ]

    monkeypatch.setattr(
        redirect_checker.requests, "head", lambda url, **kw: responses.pop(0)
    )

    result = redirect_checker.check_redirects("https://example.com/old")

    assert result["final_url"] == "https://example.com/new"
    assert not result["issues"], result["issues"]
