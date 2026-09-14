"""AI crawler roles, robots scoring and llms.txt weighting.

Three defects, found by comparing the skill against another GEO auditor:

  * generate_report.py gave +2 robots score to every AI crawler with *any*
    rule, a full block included, so disallowing OAI-SearchBot scored higher
    than allowing it, and `User-agent: *` / `Disallow: /` scored 100.
  * llms.txt kept weight 5 and scored 0 when absent, although the references
    have said since 1.12.0 that it must not be scored: Google Search ignores it.
  * robots_checker.py did not know Claude-SearchBot, Claude-User or
    Perplexity-User, so a site blocking Claude's search crawler got no finding,
    and it scored anthropic-ai and FacebookBot, which their vendors no longer
    document.

Scores are read through calculate_overall_score rather than _robots_score so
the same tests run against the pre-fix code.
"""

import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
PLUGIN = os.path.join(ROOT, "plugins", "ultimate-seo-geo", "skills", "ultimate-seo-geo")
TREES = [("root", ROOT), ("plugin", PLUGIN)]
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import generate_report  # noqa: E402
from robots_checker import (  # noqa: E402
    AI_CRAWLER_ROLES,
    AI_CRAWLERS,
    LEGACY_AI_TOKENS,
    _parse_robots,
)

SITEMAP = "Sitemap: https://example.com/sitemap.xml\n"
SEARCH = [c for c, role in AI_CRAWLER_ROLES.items() if role == "search"]
TRAINING = ["GPTBot", "ClaudeBot", "Google-Extended", "CCBot"]


def robots_section(content, status=200):
    result = {
        "status": status,
        "user_agents": {},
        "sitemaps": [],
        "crawl_delays": {},
        "ai_crawler_status": {},
        "issues": [],
    }
    _parse_robots(content, result)
    return result


def robots_score(section):
    scores = generate_report.calculate_overall_score({"sections": {"robots": section}})
    return scores["categories"]["robots"]


def score_of(content):
    return robots_score(robots_section(content))


# --- roles -----------------------------------------------------------------


def test_every_crawler_has_a_known_role():
    assert set(AI_CRAWLER_ROLES.values()) <= {"search", "user", "training"}
    assert AI_CRAWLERS == list(AI_CRAWLER_ROLES)


@pytest.mark.parametrize("crawler,role", [
    ("OAI-SearchBot", "search"),
    ("Claude-SearchBot", "search"),
    ("PerplexityBot", "search"),
    ("ChatGPT-User", "user"),
    ("Claude-User", "user"),
    ("Perplexity-User", "user"),
    ("GPTBot", "training"),
    ("ClaudeBot", "training"),
    ("Google-Extended", "training"),
    ("Applebot-Extended", "training"),
])
def test_search_user_and_training_crawlers_are_not_conflated(crawler, role):
    """Each vendor documents these as separate tokens with separate effects."""
    assert AI_CRAWLER_ROLES.get(crawler) == role


@pytest.mark.parametrize("token", sorted(LEGACY_AI_TOKENS))
def test_legacy_tokens_are_not_scored(token):
    assert token not in AI_CRAWLERS


def test_legacy_token_gets_a_note_naming_the_current_tokens():
    result = robots_section("User-agent: anthropic-ai\nDisallow: /\n")

    notes = [i for i in result["issues"] if "anthropic-ai" in i]
    assert notes and "Claude-SearchBot" in notes[0]
    assert result["ai_crawler_status"]["ClaudeBot"] == "not managed (allowed by default)"


# --- robots score ----------------------------------------------------------


@pytest.mark.parametrize("crawler", SEARCH)
def test_blocking_a_search_crawler_lowers_the_robots_score(crawler):
    allowed = score_of(f"User-agent: {crawler}\nAllow: /\n" + SITEMAP)
    blocked = score_of(f"User-agent: {crawler}\nDisallow: /\n" + SITEMAP)

    assert blocked < allowed, (
        f"Blocking {crawler} scored {blocked}, allowing it scored {allowed}. A search "
        f"crawler that cannot fetch the site takes it out of that engine's AI answers."
    )


@pytest.mark.parametrize("crawler", TRAINING)
def test_blocking_a_training_crawler_costs_nothing(crawler):
    allowed = score_of(f"User-agent: {crawler}\nAllow: /\n" + SITEMAP)
    blocked = score_of(f"User-agent: {crawler}\nDisallow: /\n" + SITEMAP)

    assert blocked == allowed, "Opting out of model training is a licensing choice, not a defect"


def test_blocking_everything_through_the_wildcard_scores_zero():
    assert score_of("User-agent: *\nDisallow: /\n" + SITEMAP) == 0


def test_a_missing_robots_txt_scores_like_an_empty_one():
    """RFC 9309 sec 2.3.1.3: an unavailable robots.txt allows every crawler."""
    missing = {
        "status": 404,
        "sitemaps": [],
        "ai_crawler_status": {c: "allowed (no robots.txt)" for c in AI_CRAWLERS},
    }

    assert robots_score(missing) == score_of("")


def test_blocked_search_crawler_raises_an_issue_and_a_report_finding():
    section = robots_section("User-agent: Claude-SearchBot\nDisallow: /\n" + SITEMAP)

    assert any("Claude-SearchBot" in i for i in section["issues"])
    fixes = generate_report.build_environment_fixes({"sections": {"robots": section}})
    titles = [f["title"] for f in fixes if "AI search crawler" in f["title"]]
    assert titles, "a blocked search crawler must reach the report as a finding"


def test_blocked_training_crawler_raises_no_finding():
    section = robots_section("User-agent: GPTBot\nUser-agent: ClaudeBot\nDisallow: /\n" + SITEMAP)

    fixes = generate_report.build_environment_fixes({"sections": {"robots": section}})
    assert not [f for f in fixes if "AI search crawler" in f["title"]]


def test_report_table_names_roles_and_does_not_flag_training_blocks():
    section = robots_section(
        "User-agent: GPTBot\nDisallow: /\n\nUser-agent: OAI-SearchBot\nDisallow: /\n" + SITEMAP
    )
    html = generate_report._check_panels({"sections": {"robots": section}})["robots"]

    rows = {row.split("</td>")[0].split("<td>")[-1]: row for row in html.split("<tr>")[1:]}
    assert "training" in rows["GPTBot"] and "chip-flag" not in rows["GPTBot"]
    assert "search" in rows["OAI-SearchBot"] and "chip-flag" in rows["OAI-SearchBot"]


# --- llms.txt --------------------------------------------------------------


def test_llms_txt_does_not_move_the_overall_score():
    base = {"robots": robots_section(SITEMAP)}
    without = generate_report.calculate_overall_score(
        {"sections": {**base, "llms_txt": {"exists": False}}}
    )
    with_file = generate_report.calculate_overall_score(
        {"sections": {**base, "llms_txt": {"exists": True, "quality": {"score": 100}}}}
    )

    assert "llms_txt" not in without["weights"]
    assert without["overall"] == with_file["overall"]


# --- docs ------------------------------------------------------------------


@pytest.mark.parametrize("tree_name,tree", TREES)
def test_reference_table_lists_every_scored_crawler(tree_name, tree):
    with open(os.path.join(tree, "references", "ai-search-geo.md"), encoding="utf-8") as fh:
        text = fh.read()

    missing = [c for c in AI_CRAWLERS if f"| {c} |" not in text]
    assert not missing, f"{tree_name}/ai-search-geo.md crawler table lacks: {missing}"
    stale = [t for t in LEGACY_AI_TOKENS if f"| {t} |" in text]
    assert not stale, f"{tree_name}/ai-search-geo.md still recommends legacy tokens: {stale}"


# Files that tell a reader which crawlers must be allowed. Wherever ChatGPT's
# search crawler is named, Claude's must be too, or the reader allows ClaudeBot
# (training) and leaves Claude-SearchBot blocked.
CRAWLER_LIST_FILES = [
    "AGENTS.md",
    os.path.join("references", "procedures", "03-geo-ai-search.md"),
    os.path.join("references", "entity-optimization.md"),
    os.path.join("references", "technical-checklist.md"),
    os.path.join("references", "site-migration.md"),
    os.path.join("references", "audit-output-example.md"),
    os.path.join("chatgpt", "instructions.txt"),
]


@pytest.mark.parametrize("tree_name,tree", TREES)
@pytest.mark.parametrize("rel", CRAWLER_LIST_FILES)
def test_claude_search_crawler_named_alongside_openai_search_crawler(tree_name, tree, rel):
    path = os.path.join(tree, rel)
    if not os.path.isfile(path):
        pytest.skip(f"{tree_name}/{rel} not present")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if "OAI-SearchBot" in text:
        assert "Claude-SearchBot" in text, f"{tree_name}/{rel} names OAI-SearchBot but not Claude-SearchBot"
