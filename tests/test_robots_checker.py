"""Tests for robots.txt group parsing and user-agent matching.

Covers RFC 9309 sec 2.2.1: consecutive User-agent lines form one group that
shares the rules following them, and user-agent tokens match case-insensitively.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from robots_checker import _parse_robots  # noqa: E402


def parse(content):
    result = {
        "user_agents": {},
        "sitemaps": [],
        "crawl_delays": {},
        "ai_crawler_status": {},
        "issues": [],
        "recommendations": [],
    }
    _parse_robots(content, result)
    return result


def test_consecutive_user_agents_share_following_rules():
    """The canonical AI-blocking block: one Disallow under stacked agents."""
    result = parse(
        "User-agent: GPTBot\n"
        "User-agent: CCBot\n"
        "User-agent: ClaudeBot\n"
        "Disallow: /\n"
    )

    for agent in ("GPTBot", "CCBot", "ClaudeBot"):
        assert result["user_agents"][agent]["disallow"] == ["/"], (
            f"{agent} lost its Disallow; consecutive User-agent lines must "
            f"form one group"
        )
        assert result["ai_crawler_status"][agent] == "fully blocked"


def test_rule_directive_closes_the_group():
    """A new User-agent after a rule starts a fresh group, not an addition."""
    result = parse(
        "User-agent: GPTBot\n"
        "Disallow: /private\n"
        "User-agent: CCBot\n"
        "Disallow: /other\n"
    )

    assert result["user_agents"]["GPTBot"]["disallow"] == ["/private"]
    assert result["user_agents"]["CCBot"]["disallow"] == ["/other"]


def test_crawl_delay_applies_to_every_agent_in_the_group():
    result = parse("User-agent: GPTBot\nUser-agent: CCBot\nCrawl-delay: 10\n")

    assert result["crawl_delays"]["GPTBot"] == 10.0
    assert result["crawl_delays"]["CCBot"] == 10.0


def test_repeated_agent_in_one_group_is_not_duplicated():
    result = parse("User-agent: GPTBot\nUser-agent: GPTBot\nDisallow: /\n")

    assert result["user_agents"]["GPTBot"]["disallow"] == ["/"]


@pytest.mark.parametrize("declared", ["gptbot", "GPTBOT", "GptBot"])
def test_user_agent_matching_is_case_insensitive(declared):
    """RFC 9309: user-agent tokens are matched case-insensitively."""
    result = parse(f"User-agent: {declared}\nDisallow: /\n")

    assert result["ai_crawler_status"]["GPTBot"] == "fully blocked"


def test_wildcard_group_still_resolves_for_undeclared_crawlers():
    result = parse("User-agent: *\nDisallow: /\n")

    assert result["ai_crawler_status"]["GPTBot"] == "blocked by wildcard (*)"


def test_sitemap_does_not_break_an_open_agent_group():
    """Sitemap is a non-group directive and must not split stacked agents."""
    result = parse(
        "User-agent: GPTBot\n"
        "Sitemap: https://example.com/sitemap.xml\n"
        "User-agent: CCBot\n"
        "Disallow: /\n"
    )

    assert result["sitemaps"] == ["https://example.com/sitemap.xml"]
    assert result["user_agents"]["GPTBot"]["disallow"] == ["/"]
    assert result["user_agents"]["CCBot"]["disallow"] == ["/"]
