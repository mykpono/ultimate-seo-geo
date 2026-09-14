"""ai_bot_access.py: robots.txt can allow a crawler that the firewall refuses.

Every test serves canned responses keyed by user agent, so nothing touches the
network. The guards that matter most are the negative ones: a bot-management
script injected into every page, a rate limit, and a browser that is itself
refused must never read as "the firewall blocks AI crawlers".
"""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import ai_bot_access  # noqa: E402
from robots_checker import AI_CRAWLER_ROLES  # noqa: E402

PUBLIC_IP = [(None, None, None, None, ("93.184.216.34", 0))]
PAGE = b"<html><head><title>Example</title></head><body>" + b"content " * 200 + b"</body></html>"


class FakeResponse:
    def __init__(self, url, status_code=200, body=PAGE, headers=None):
        self.url = url
        self.status_code = status_code
        self.headers = headers or {}
        self.is_redirect = status_code in {301, 302, 303, 307, 308}
        self._body = body

    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        pass


class FakeSession:
    created = 0

    def __init__(self, responder):
        FakeSession.created += 1
        self.responder = responder

    def get(self, url, headers=None, **kwargs):
        return self.responder(url, headers["User-Agent"])

    def close(self):
        pass


def run(responder, roles=("search", "user")):
    FakeSession.created = 0
    with (
        patch("ai_bot_access.requests.Session", side_effect=lambda: FakeSession(responder)),
        patch("url_safety.socket.getaddrinfo", return_value=PUBLIC_IP),
    ):
        return ai_bot_access.check_access("https://example.com/", roles=roles)


def refuse(token, **response):
    """A firewall that answers one crawler token with `response` and serves everyone else."""
    def responder(url, ua):
        if token in ua:
            return FakeResponse(url, **response)
        return FakeResponse(url)
    return responder


def warnings(result):
    return [i for i in result["issues"] if i.startswith("⚠️")]


def test_every_crawler_served_like_the_browser_is_allowed():
    result = run(lambda url, ua: FakeResponse(url))

    assert result["status"] == "ok"
    assert {b["verdict"] for b in result["bots"].values()} == {"allowed"}
    assert result["score"] == 100
    assert not warnings(result)


def test_a_403_for_a_search_crawler_is_a_suspected_block():
    result = run(refuse("OAI-SearchBot", status_code=403, body=b"Forbidden"))

    assert result["bots"]["OAI-SearchBot"]["verdict"] == "blocked"
    assert result["refused_search"] == ["OAI-SearchBot"]
    assert result["score"] < 100
    assert any("OAI-SearchBot (HTTP 403)" in w for w in warnings(result))
    assert result["bots"]["PerplexityBot"]["verdict"] == "allowed"


def test_a_cloudflare_challenge_header_is_recognised():
    result = run(refuse("Claude-SearchBot", status_code=403, headers={"cf-mitigated": "challenge"}))

    bot = result["bots"]["Claude-SearchBot"]
    assert (bot["verdict"], bot["challenge_vendor"]) == ("challenged", "Cloudflare")
    assert any("Cloudflare challenge" in w for w in warnings(result))


def test_a_challenge_page_served_with_200_is_still_recognised():
    challenge = b"<html><title>Just a moment...</title><script>window._cf_chl_opt={}</script></html>"
    result = run(refuse("PerplexityBot", status_code=200, body=challenge))

    assert result["bots"]["PerplexityBot"]["verdict"] == "challenged"


def test_a_marker_the_browser_also_gets_is_not_a_challenge():
    """Bot-management scripts are injected into ordinary pages as well."""
    injected = PAGE + b'<script src="/cdn-cgi/challenge-platform/scripts/jsd/main.js"></script>'
    result = run(lambda url, ua: FakeResponse(url, body=injected))

    assert {b["verdict"] for b in result["bots"].values()} == {"allowed"}
    assert not warnings(result)


@pytest.mark.parametrize("status", [429, 503])
def test_rate_limits_and_outages_are_inconclusive_not_blocks(status):
    result = run(refuse("OAI-SearchBot", status_code=status, body=b"slow down"))

    assert result["bots"]["OAI-SearchBot"]["verdict"] == "inconclusive"
    assert result["refused_search"] == []
    assert not warnings(result)


def test_a_refused_browser_makes_the_whole_check_inconclusive():
    def responder(url, ua):
        return FakeResponse(url, status_code=403, body=b"Forbidden")

    result = run(responder)

    assert result["status"] == "inconclusive"
    assert {b["verdict"] for b in result["bots"].values()} == {"inconclusive"}
    assert result["score"] is None
    assert not warnings(result)


def test_user_fetchers_are_reported_at_info_not_warning():
    result = run(refuse("Claude-User", status_code=403, body=b"Forbidden"))

    assert result["refused_user"] == ["Claude-User"]
    assert not warnings(result)
    assert any("Claude-User" in i for i in result["issues"])


def test_each_request_uses_a_fresh_session():
    """A challenge cookie earned by the browser must not let a crawler through."""
    result = run(lambda url, ua: FakeResponse(url))

    assert FakeSession.created == 1 + len(result["bots"])


def test_roles_limit_which_crawlers_are_tested():
    result = run(lambda url, ua: FakeResponse(url), roles=("search",))

    assert set(result["bots"]) == {c for c, r in AI_CRAWLER_ROLES.items() if r == "search"}


def test_a_redirect_to_a_private_address_is_not_followed():
    def responder(url, ua):
        return FakeResponse(url, status_code=302, headers={"Location": "http://127.0.0.1/admin"})

    result = run(responder)

    assert "URL safety check failed" in result["baseline"]["error"]
    assert result["status"] == "inconclusive"


def test_access_check_is_shown_but_never_weighted():
    import generate_report

    section = run(refuse("OAI-SearchBot", status_code=403, body=b"Forbidden"))
    scores = generate_report.calculate_overall_score({"sections": {"ai_bot_access": section}})

    assert "ai_bot_access" not in scores["weights"]
    assert scores["categories"]["ai_bot_access"] == section["score"]


def test_report_status_separates_suspected_blocks_from_unmeasured_runs():
    import generate_report

    blocked = run(refuse("OAI-SearchBot", status_code=403, body=b"Forbidden"))
    assert generate_report._check_status("ai_bot_access", blocked, blocked["score"]) == ("flag", "Suspected block")

    refused_browser = run(lambda url, ua: FakeResponse(url, status_code=403, body=b"Forbidden"))
    assert generate_report._check_status("ai_bot_access", refused_browser, 0) == ("deferred", "Not measured")

    clean = run(lambda url, ua: FakeResponse(url))
    assert generate_report._check_status("ai_bot_access", clean, clean["score"]) == ("ok", "Strong")


def test_a_suspected_block_reaches_the_findings_ledger_once_as_a_warning():
    import generate_report

    section = run(refuse("OAI-SearchBot", status_code=403, body=b"Forbidden"))
    data = {"sections": {"ai_bot_access": section}}
    data["environment_fixes"] = generate_report.build_environment_fixes(data)
    findings = [i for i in generate_report._collect_issues(data) if "OAI-SearchBot" in i["finding"]]

    assert [f["severity"] for f in findings] == ["warning"]


def test_report_panel_lists_crawlers_and_states_the_limits():
    import generate_report

    section = run(refuse("OAI-SearchBot", status_code=403, body=b"Forbidden"))
    html = generate_report._check_panels({"sections": {"ai_bot_access": section}})["ai_bot_access"]

    assert "Suspected, not proven." in html
    oai_row = next(row for row in html.split("<tr>") if "OAI-SearchBot" in row)
    assert "chip-flag" in oai_row and "Refused" in oai_row


def test_documented_user_agents_are_used_and_others_carry_their_token():
    ua, source = ai_bot_access.user_agent_for("OAI-SearchBot")
    assert source == "documented" and "OAI-SearchBot/1.4" in ua

    ua, source = ai_bot_access.user_agent_for("Claude-SearchBot")
    assert source == "token" and "Claude-SearchBot" in ua
