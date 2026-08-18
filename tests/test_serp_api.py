"""SerpBase-backed live SERP script: contract and degradation tests.

The SerpBase API contract is pinned here on purpose: if the API changes
again, these tests fail loudly in CI instead of the script silently
returning ``count: 0``.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import serp_api  # noqa: E402


class _FakeResp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def _fake_post_factory(resp):
    def fake_post(*args, **kwargs):
        fake_post.calls.append((args, kwargs))
        return resp

    fake_post.calls = []
    return fake_post


def test_success_path_maps_organic(monkeypatch):
    payload = {
        "status": 0,
        "request_id": "req_1",
        "organic": [
            {
                "position": 1,
                "title": "Example",
                "link": "https://example.com/1",
                "snippet": "First result",
            },
            {
                "position": 2,
                "title": "Example 2",
                "url": "https://example.com/2",  # older field name fallback
                "snippet": "Second result",
            },
        ],
    }
    fake = _fake_post_factory(_FakeResp(payload=payload))
    monkeypatch.setattr(serp_api.requests, "post", fake)

    data = serp_api.fetch_serp("hello", api_key="k")

    assert data["count"] == 2
    assert data["organic_results"][0] == {
        "position": 1,
        "title": "Example",
        "link": "https://example.com/1",
        "snippet": "First result",
    }
    assert data["organic_results"][1]["link"] == "https://example.com/2"


def test_request_shape_pins_contract(monkeypatch):
    """POST + JSON body + X-API-Key header — the documented contract."""
    fake = _fake_post_factory(_FakeResp(payload={"status": 0, "organic": []}))
    monkeypatch.setattr(serp_api.requests, "post", fake)

    serp_api.fetch_serp("best seo tools", api_key="secret-key")

    args, kwargs = fake.calls[0]
    assert args[0] == "https://api.serpbase.dev/google/search"
    assert kwargs["json"] == {"q": "best seo tools"}
    assert kwargs["headers"]["X-API-Key"] == "secret-key"
    assert "api_key" not in kwargs.get("params", {})
    assert "api_key" not in kwargs


def test_error_envelope_is_not_silent_empty(monkeypatch):
    payload = {"status": 7, "error": "invalid api key"}
    fake = _fake_post_factory(_FakeResp(payload=payload))
    monkeypatch.setattr(serp_api.requests, "post", fake)

    data = serp_api.fetch_serp("x", api_key="bad")

    assert "error" in data
    assert "invalid api key" in data["error"]


def test_http_error_surfaces(monkeypatch):
    fake = _fake_post_factory(_FakeResp(status_code=500, text="boom"))
    monkeypatch.setattr(serp_api.requests, "post", fake)

    data = serp_api.fetch_serp("x", api_key="k")

    assert "error" in data
    assert "HTTP 500" in data["error"]


def test_network_error_surfaces(monkeypatch):
    import requests as real_requests

    def boom(*args, **kwargs):
        raise real_requests.RequestException("connection refused")

    monkeypatch.setattr(serp_api.requests, "post", boom)

    data = serp_api.fetch_serp("x", api_key="k")

    assert "error" in data
    assert "connection refused" in data["error"]


def test_invalid_json_surfaces(monkeypatch):
    class _BadJson(_FakeResp):
        def json(self):
            raise ValueError("no json")

    monkeypatch.setattr(serp_api.requests, "post", _fake_post_factory(_BadJson()))

    data = serp_api.fetch_serp("x", api_key="k")

    assert "error" in data
    assert "invalid JSON" in data["error"]


def test_num_truncates_client_side(monkeypatch):
    organic = [
        {
            "position": i,
            "title": f"Result {i}",
            "link": f"https://example.com/{i}",
            "snippet": "",
        }
        for i in range(1, 21)
    ]
    payload = {"status": 0, "organic": organic}
    fake = _fake_post_factory(_FakeResp(payload=payload))
    monkeypatch.setattr(serp_api.requests, "post", fake)

    data = serp_api.fetch_serp("x", api_key="k", num=5)

    assert data["count"] == 5
    assert data["organic_results"][-1]["position"] == 5


def test_missing_key_prints_helpful_error(monkeypatch, capsys):
    monkeypatch.delenv("SERPBASE_API_KEY", raising=False)

    code = serp_api.main(["test query"])

    assert code == 1
    out = capsys.readouterr().out
    assert "SERPBASE_API_KEY" in out
    assert "serpbase.dev" in out
