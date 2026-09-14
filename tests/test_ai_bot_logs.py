"""ai_bot_logs.py: what real AI crawlers requested, from server access logs.

Log lines are synthetic and use documentation IP ranges (RFC 5737), so nothing
here touches the network. The guards that matter most:

  * a firewall correctly refusing *spoofed* crawlers must not read as the site
    turning the real crawler away, once IPs are verified;
  * similar tokens (Claude-User / ClaudeBot, Amzn-SearchBot / Amazonbot) must
    not be counted as each other;
  * "not seen" is reported as information about a window, never as a defect;
  * IP addresses never appear in the output.
"""

import gzip
import ipaddress
import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import ai_bot_logs  # noqa: E402

REAL_IP = "192.0.2.10"      # inside the "published" range used below
SPOOF_IP = "198.51.100.7"   # outside it
RANGES = {
    "OAI-SearchBot": [ipaddress.ip_network("192.0.2.0/24")],
    "Claude-SearchBot": [ipaddress.ip_network("192.0.2.0/24")],
}
UA = {
    "OAI-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.4; +https://openai.com/searchbot",
    "Claude-User": "Mozilla/5.0 (compatible; Claude-User/1.0; +Claude-User@anthropic.com)",
    "Amzn-SearchBot": "Mozilla/5.0 (compatible; Amzn-SearchBot/0.1)",
    "browser": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
}


def combined(ua, path="/", status=200, ip=REAL_IP, when="14/Sep/2026:10:00:00 +0000"):
    return f'{ip} - - [{when}] "GET {path} HTTP/1.1" {status} 512 "-" "{ua}"'


def warnings(result):
    return [i for i in result["issues"] if i.startswith("⚠️")]


# --- parsing ---------------------------------------------------------------


def test_combined_format_is_parsed():
    entry = ai_bot_logs.parse_line(combined(UA["OAI-SearchBot"], path="/guide?utm=x", status=301))

    assert entry["ip"] == REAL_IP and entry["status"] == 301 and entry["path"] == "/guide"
    assert entry["time"].isoformat() == "2026-09-14T10:00:00+00:00"
    assert "OAI-SearchBot" in entry["ua"]


def test_escaped_quotes_inside_the_user_agent_do_not_break_parsing():
    line = f'{REAL_IP} - - [14/Sep/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 5 "-" "odd \\"quoted\\" OAI-SearchBot/1.4"'

    assert ai_bot_logs.match_crawler(ai_bot_logs.parse_line(line)["ua"]) == "OAI-SearchBot"


def test_nginx_json_lines_are_parsed():
    line = json.dumps({"remote_addr": REAL_IP, "http_user_agent": UA["OAI-SearchBot"], "status": "404",
                       "request": "GET /missing HTTP/2.0", "time": "2026-09-14T10:00:00Z"})
    entry = ai_bot_logs.parse_line(line)

    assert (entry["status"], entry["path"]) == (404, "/missing")


def test_cloudflare_logpush_fields_and_nanosecond_timestamps_are_parsed():
    line = json.dumps({"ClientIP": REAL_IP, "ClientRequestUserAgent": UA["OAI-SearchBot"],
                       "EdgeResponseStatus": 403, "ClientRequestURI": "/pricing",
                       "EdgeStartTimestamp": 1789380000000000000})
    entry = ai_bot_logs.parse_line(line)

    assert entry["status"] == 403 and entry["path"] == "/pricing"
    assert entry["time"].year == 2026


@pytest.mark.parametrize("ua,expected", [
    (UA["Claude-User"], "Claude-User"),
    (UA["Amzn-SearchBot"], "Amzn-SearchBot"),
    ("Mozilla/5.0 (compatible; ClaudeBot/1.0)", "ClaudeBot"),
    ("Mozilla/5.0 (compatible; Perplexity-User/1.0)", "Perplexity-User"),
    ("Mozilla/5.0 (compatible; SuperGPTBotX/2.0)", None),
    (UA["browser"], None),
])
def test_tokens_match_only_as_whole_tokens(ua, expected):
    assert ai_bot_logs.match_crawler(ua) == expected


# --- aggregation -----------------------------------------------------------


def test_requests_are_counted_by_crawler_status_and_path():
    lines = [
        combined(UA["OAI-SearchBot"], "/robots.txt"),
        combined(UA["OAI-SearchBot"], "/a"),
        combined(UA["OAI-SearchBot"], "/a?x=1", status=304),
        combined(UA["OAI-SearchBot"], "/b", status=404),
        combined(UA["browser"], "/a"),
        "not a log line",
    ]
    result = ai_bot_logs.analyze(lines)
    bot = result["crawlers"]["OAI-SearchBot"]

    assert bot["hits"] == 4 and bot["robots_txt_requests"] == 1
    assert bot["status_classes"] == {"2xx": 2, "3xx": 1, "4xx": 1}
    assert bot["top_paths"][0] == ("/a", 2)
    assert result["lines_skipped"] == 1 and result["lines_parsed"] == 5


def test_an_unverified_search_crawler_refused_by_majority_is_a_warning_with_a_caveat():
    lines = [combined(UA["OAI-SearchBot"], status=403) for _ in range(8)] + [combined(UA["OAI-SearchBot"]) for _ in range(2)]
    result = ai_bot_logs.analyze(lines)

    [warning] = warnings(result)
    assert "OAI-SearchBot" in warning and "80.0%" in warning
    assert "unverified" in warning and "--verify-ips" in warning


def test_a_firewall_refusing_only_spoofers_is_not_a_warning_once_verified():
    """The case verification exists for: blocking fake crawlers is correct behaviour."""
    lines = (
        [combined(UA["OAI-SearchBot"], status=403, ip=SPOOF_IP) for _ in range(10)]
        + [combined(UA["OAI-SearchBot"], ip=REAL_IP) for _ in range(10)]
    )
    result = ai_bot_logs.analyze(lines, ranges=RANGES)
    bot = result["crawlers"]["OAI-SearchBot"]

    assert (bot["verified_hits"], bot["unverified_hits"], bot["refused_share"]) == (10, 10, 0.0)
    assert not warnings(result)
    assert any("likely spoofed" in i for i in result["issues"])


def test_a_verified_search_crawler_refused_by_majority_is_a_warning():
    lines = [combined(UA["OAI-SearchBot"], status=403, ip=REAL_IP) for _ in range(6)]
    result = ai_bot_logs.analyze(lines, ranges=RANGES)

    [warning] = warnings(result)
    assert "6 verified requests" in warning and "unverified" not in warning


def test_spoofed_successes_do_not_dilute_a_verified_refusal():
    """Refusal share is judged on verified requests only, in both directions.

    A mutation that divided verified refusals by *all* requests passed every
    other test here: 20 served spoofers would hide 6 refused real crawls.
    """
    lines = (
        [combined(UA["OAI-SearchBot"], status=403, ip=REAL_IP) for _ in range(6)]
        + [combined(UA["OAI-SearchBot"], ip=SPOOF_IP) for _ in range(20)]
    )
    result = ai_bot_logs.analyze(lines, ranges=RANGES)

    assert result["crawlers"]["OAI-SearchBot"]["refused_share"] == 100.0
    [warning] = warnings(result)
    assert "6 verified requests" in warning


def test_too_few_requests_are_not_judged():
    lines = [combined(UA["OAI-SearchBot"], status=403) for _ in range(ai_bot_logs.MIN_REQUESTS - 1)]

    assert not warnings(ai_bot_logs.analyze(lines))


def test_a_refused_user_fetcher_is_info_not_warning():
    lines = [combined(UA["Claude-User"], status=403) for _ in range(6)]
    result = ai_bot_logs.analyze(lines)

    assert not warnings(result)
    assert any(i.startswith("ℹ️ Claude-User was refused") for i in result["issues"])


def test_absent_search_crawlers_are_info_about_the_window_not_a_defect():
    result = ai_bot_logs.analyze([combined(UA["OAI-SearchBot"])])

    assert "Claude-SearchBot" in result["not_seen"]["search"]
    [note] = [i for i in result["issues"] if i.startswith("ℹ️ No requests from AI search crawlers")]
    assert "not proof" in note and "2026-09-14" in note
    assert not warnings(result)


def test_ip_addresses_never_appear_in_the_output():
    lines = [combined(UA["OAI-SearchBot"], ip=SPOOF_IP), combined(UA["OAI-SearchBot"], ip=REAL_IP)]
    text = json.dumps(ai_bot_logs.analyze(lines, ranges=RANGES))

    assert SPOOF_IP not in text and REAL_IP not in text


def test_mixed_naive_and_aware_timestamps_do_not_crash():
    lines = [
        json.dumps({"ip": REAL_IP, "ua": UA["OAI-SearchBot"], "status": 200, "path": "/", "time": "2026-09-14T09:00:00"}),
        combined(UA["OAI-SearchBot"], when="14/Sep/2026:11:00:00 +0200"),
    ]
    result = ai_bot_logs.analyze(lines)

    assert result["window"]["first"].startswith("2026-09-14T09:00:00")


def test_logs_with_nothing_parseable_are_an_error():
    result = ai_bot_logs.analyze(["garbage", "more garbage"])

    assert result["error"] and result["lines_read"] == 2


def test_gzipped_and_plain_logs_are_read_in_order(tmp_path):
    plain = tmp_path / "access.log"
    plain.write_text(combined(UA["OAI-SearchBot"]) + "\n")
    packed = tmp_path / "access.log.1.gz"
    with gzip.open(packed, "wt") as fh:
        fh.write(combined(UA["OAI-SearchBot"], "/old") + "\n")

    result = ai_bot_logs.analyze(ai_bot_logs.iter_lines([str(plain), str(packed)]))

    assert result["crawlers"]["OAI-SearchBot"]["hits"] == 2


# --- published IP ranges -----------------------------------------------------


def test_vendor_range_files_are_parsed_including_ipv6():
    doc = {"creationTime": "2026-09-14T00:00:00Z",
           "prefixes": [{"ipv4Prefix": "192.0.2.0/28"}, {"ipv6Prefix": "2001:db8::/32"}, {"ipv4Prefix": "junk"}]}

    assert [str(n) for n in ai_bot_logs.parse_prefixes(doc)] == ["192.0.2.0/28", "2001:db8::/32"]


class FakeJSONResponse:
    def __init__(self, url, payload=None, status_code=200):
        self.url = url
        self.status_code = status_code
        self.headers = {}
        self.is_redirect = False
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ai_bot_logs.requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_each_published_list_is_fetched_once_and_failures_are_recorded():
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if "perplexity" in url:
            return FakeJSONResponse(url, status_code=503)
        return FakeJSONResponse(url, {"prefixes": [{"ipv4Prefix": "192.0.2.0/24"}]})

    with (
        patch("ai_bot_logs.requests.get", side_effect=fake_get),
        patch("url_safety.socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]),
    ):
        ranges, errors = ai_bot_logs.fetch_ip_ranges()

    assert len(calls) == len(set(ai_bot_logs.IP_RANGE_URLS.values()))
    assert {"ClaudeBot", "Claude-SearchBot", "Claude-User", "OAI-SearchBot"} <= set(ranges)
    assert set(errors) == {"PerplexityBot", "Perplexity-User"}


def test_every_verifiable_crawler_is_a_known_role():
    assert set(ai_bot_logs.IP_RANGE_URLS) <= set(ai_bot_logs.AI_CRAWLER_ROLES)
