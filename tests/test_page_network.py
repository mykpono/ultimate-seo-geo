"""page_network.py: what a rendered page calls, and which of those calls anyone can make.

Every case here was seen on a live site on 2026-09-25 while the check was built:
  * agent.improvado.io/ask: OPTIONS 204 with Access-Control-Allow-Origin *, GET 404 JSON, no
    auth challenge (Improvado v4.1 F26, the endpoint the site's sandbox widget called);
  * improvado.io/mcp/<source>: HTML marketing pages listed in llms.txt; OPTIONS answers 403 HTML;
  * improvado.io/_tag/...: a server-side tag-manager proxy, not an API;
  * posthog.com: Gatsby page-data JSON readable from any origin, and self-hosted analytics
    ingestion (/e/, /flags/, /i/v0/e/) that reflects any origin by design;
  * developers.cloudflare.com: OneTrust consent files with CORS *; vercel.com: Next.js prefetches.
A first draft flagged all of the posthog, Cloudflare and Vercel calls; only a write call with
no key that any origin may make is a finding now.
"""

import os
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import page_network as pn  # noqa: E402
import render_page as rp  # noqa: E402


def call(url, method="GET", rtype="fetch", cors=None, auth=False, status=200):
    return {"url": url, "method": method, "resource_type": rtype, "has_auth_header": auth,
            "request_content_type": None, "status": status, "cors": cors or {}, "content_type": "application/json"}


def no_probe(*a, **k):
    raise AssertionError("no probe expected")


# --- recording --------------------------------------------------------------------

def test_recorded_entry_keeps_no_query_string_and_no_header_values():
    req = SimpleNamespace(url="https://t.example.com/collect?email=a%40b.com&cid=9#x", method="POST", resource_type="fetch",
                          headers={"Authorization": "Bearer secret", "Content-Type": "application/json"})
    resp = SimpleNamespace(status=204, headers={"Access-Control-Allow-Origin": "*", "Set-Cookie": "sid=1",
                                                "Content-Type": "text/plain"})
    entry = rp.network_entry(req, resp)
    assert entry["url"] == "https://t.example.com/collect"
    assert entry["has_auth_header"] is True
    assert "secret" not in str(entry) and "sid=1" not in str(entry)
    assert entry["cors"] == {"access-control-allow-origin": "*"}
    assert rp.network_entry(req, None)["status"] is None


# --- what counts as a first-party API --------------------------------------------------

def test_sites_and_subdomains():
    assert pn.site_of("agent.improvado.io") == "improvado.io"
    assert pn.site_of("www.bbc.co.uk") == "bbc.co.uk"
    assert pn.site_of("internal-c.posthog.com") == "posthog.com"


@pytest.mark.parametrize("url,api", [
    ("https://improvado.io/_tag/ag/g/c", False),          # server-side tag proxy
    ("https://internal-c.posthog.com/e/", False),         # analytics ingestion
    ("https://internal-c.posthog.com/i/v0/e/", False),
    ("https://internal-c.posthog.com/flags/", False),
    ("https://example.com/cdn-cgi/rum", False),
    ("https://agent.improvado.io/ask", True),
    ("https://posthog.com/api/signup-count", True),
    ("https://www.google.com/ccm/collect", False),        # third party
])
def test_is_api_call(url, api):
    page_site = pn.site_of(pn.urlsplit(url).hostname) if "google" not in url else "improvado.io"
    assert pn.is_api_call(call(url, "POST"), page_site) is api


def test_only_fetch_and_xhr_are_api_calls():
    assert pn.is_api_call(call("https://improvado.io/app.js", rtype="script"), "improvado.io") is False


# --- the finding ---------------------------------------------------------------------

def test_the_improvado_widget_call_is_open():
    network = [call("https://agent.improvado.io/ask", "POST", cors={"access-control-allow-origin": "*"})]
    page = pn.analyse_page("https://improvado.io/ai-sandbox", network, probe=no_probe)
    assert [e["url"] for e in page["open_endpoints"]] == ["https://agent.improvado.io/ask"]
    issue = pn.build_issues([page], None)[0]
    assert issue["code"] == "open_public_endpoint" and issue["lane"] == "Human"
    assert issue["finding"].startswith("One of the site's own API endpoints accepts write calls")


def test_a_key_closes_it():
    network = [call("https://agent.improvado.io/ask", "POST", cors={"access-control-allow-origin": "*"}, auth=True)]
    assert pn.analyse_page("https://improvado.io/", network, probe=no_probe)["open_endpoints"] == []


def test_open_reads_of_public_data_are_not_findings():
    network = [call(f"https://posthog.com/page-data/sq/d/{i}.json", cors={"access-control-allow-origin": "*"}) for i in range(40)]
    network += [call("https://ot.www.cloudflare.com/public/vendor/onetrust/consent/x.json", cors={"access-control-allow-origin": "*"}),
                call("https://vercel.com/pricing", cors={"access-control-allow-origin": "*"})]
    for page_url in ("https://posthog.com/", "https://developers.cloudflare.com/workers/", "https://vercel.com/"):
        page = pn.analyse_page(page_url, network, probe=no_probe)
        assert page["open_endpoints"] == []
        assert pn.build_issues([page], None) == []
    assert len(pn.analyse_page("https://posthog.com/", network, probe=no_probe)["readable_cross_origin"]) == 40


def test_write_calls_without_a_cors_header_are_probed_once_each():
    seen = []

    def probe(url, method):
        seen.append((url, method))
        return {"status": 204, "allow_origin": pn.PROBE_ORIGIN}

    network = [call("https://api.example.com/v1/answer", "POST")] * 3 + [call("https://api.example.com/v1/items")]
    page = pn.analyse_page("https://example.com/", network, probe=probe)
    assert seen == [("https://api.example.com/v1/answer", "POST")]  # a GET is never probed
    assert page["open_endpoints"][0]["cors"] == "reflects any origin"


def test_restricted_preflight_is_not_open():
    page = pn.analyse_page("https://example.com/", [call("https://api.example.com/v1/answer", "POST")],
                           probe=lambda u, m: {"status": 204, "allow_origin": "https://example.com"})
    assert page["open_endpoints"] == [] and page["first_party_apis"][0]["cors"] == "restricted"


# --- tag load ------------------------------------------------------------------------

def test_vendors_and_infrastructure():
    assert pn.vendor_of("https://www.google.com/ccm/collect") == "Google Ads"
    assert pn.vendor_of("https://www.google.com/search") is None  # the path decides for google.com
    assert pn.vendor_of("https://o.clarity.ms/collect") == "Microsoft Clarity"
    assert pn.vendor_of("https://bzr.openai.com/v1/sdk/events") == "OpenAI Ads"
    network = [call("https://fonts.gstatic.com/s/x.woff2", rtype="font"), call("https://get.geojs.io/v1/ip/country.json")]
    page = pn.analyse_page("https://improvado.io/", network, probe=no_probe)
    assert page["infrastructure_hosts"] == ["fonts.gstatic.com"]
    assert page["unrecognised_third_parties"] == ["get.geojs.io"]


def test_tag_load_finding_on_the_improvado_homepage_shape():
    hosts = ["www.googletagmanager.com", "ad.doubleclick.net", "www.google-analytics.com", "connect.facebook.net",
             "px.ads.linkedin.com", "alb.reddit.com", "o.clarity.ms", "bat.bing.com", "js.hs-scripts.com",
             "dev.visualwebsiteoptimizer.com", "bzr.openai.com", "assets.apollo.io", "v2.midbound.ai"]
    page = pn.analyse_page("https://improvado.io/", [call(f"https://{h}/x", rtype="script") for h in hosts], probe=no_probe)
    assert len(page["vendors"]) == 13
    issue = pn.build_issues([page], None)[0]
    assert issue["code"] == "tag_load" and "13 tracking vendors" in issue["finding"]


# --- llms.txt and given endpoints ---------------------------------------------------------

LLMS = """# Improvado
- [MCP](https://improvado.io/mcp): 187 MCP pages
- [Asana MCP](https://improvado.io/mcp/asana)
- Ask the agent: https://agent.improvado.io/ask
- Docs: https://improvado.io/docs/api-reference.md
- Partner: https://api.other.com/v1/x
"""


def test_llms_endpoints_are_api_shaped_first_party_urls():
    assert pn.llms_endpoints(LLMS, "improvado.io") == [
        "https://agent.improvado.io/ask", "https://improvado.io/mcp", "https://improvado.io/mcp/asana"]


class Resp:
    def __init__(self, status, ctype, **headers):
        self.status_code = status
        self.headers = {"content-type": ctype, **headers}


def fake_requests(monkeypatch, get, options):
    import requests
    monkeypatch.setattr(pn, "validate_url", lambda u: SimpleNamespace(ok=True, reason=None))
    monkeypatch.setattr(requests, "get", lambda url, **k: get)
    monkeypatch.setattr(requests, "options", lambda url, **k: options)


def test_an_html_page_is_not_an_endpoint(monkeypatch):
    fake_requests(monkeypatch, Resp(200, "text/html; charset=utf-8"), Resp(403, "text/html"))
    result = pn.probe_endpoint("https://improvado.io/mcp/asana")
    assert result["kind"] == "page" and result["open"] is False and "preflight" not in result


def test_the_agent_endpoint_probe(monkeypatch):
    fake_requests(monkeypatch, Resp(404, "application/json; charset=utf-8", **{"access-control-allow-origin": "*"}),
                  Resp(204, "text/plain", **{"access-control-allow-origin": "*"}))
    result = pn.probe_endpoint("https://agent.improvado.io/ask")
    assert (result["kind"], result["cors"], result["asks_for_auth"], result["open"]) == ("endpoint", "any origin", False, True)


def test_a_403_html_refusal_is_not_auth_but_a_401_is():
    html_refusal = pn.classify_endpoint("u", {"status": 403, "content_type": "text/html"}, {"status": 204, "allow_origin": "*"})
    assert html_refusal["asks_for_auth"] is False and html_refusal["open"] is True
    challenged = pn.classify_endpoint("u", {"status": 401, "content_type": "application/json"}, {"status": 204, "allow_origin": "*"})
    assert challenged["asks_for_auth"] is True and challenged["open"] is False
    json_forbidden = pn.classify_endpoint("u", {"status": 403, "content_type": "application/json"}, {"status": 204, "allow_origin": "*"})
    assert json_forbidden["open"] is False


def test_given_endpoint_feeds_the_finding():
    llms = {"given": [{"url": "https://agent.improvado.io/ask", "open": True, "cors": "any origin", "source": "given with --endpoint"}]}
    issue = pn.build_issues([], llms)[0]
    assert issue["code"] == "open_public_endpoint" and "given with --endpoint" in issue["evidence"]
