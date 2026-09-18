"""Every in-page link in the report lands on something.

A link to an id that is not on the page does nothing when clicked, and string
tests of the HTML never click. So each report shape below is rendered and every
href="#..." is checked against the ids on the same page: an empty audit, a
clean run, a run with agent-fixable work, one without, and runs compared with a
previous summary with and without anything fixed.
"""

import os
import re
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import generate_report as gr  # noqa: E402


def _data(**sections):
    base = {
        "security": {"score": 90}, "social": {"score": 40},
        "robots": {"status": 200, "sitemaps": ["s"], "ai_crawler_status": {}},
        "broken_links": {"summary": {"total": 50, "broken": 0}}, "readability": {"flesch_reading_ease": 45},
        "content_quality": {"score": 55}, "schema_validation": {"score": 30}, "sitemap": {"score": 100},
        "onpage": {"title": "t", "meta_description": "m", "h1": ["h"], "canonical": "https://ex.com/"},
    }
    base.update(sections)
    return {"url": "https://ex.com/", "domain": "ex.com", "timestamp": "2026-09-18T10:00:00",
            "environment": {"primary": "Webflow", "runtime": "Unknown", "confidence": "low", "signals": [], "alternatives": []},
            "environment_fixes": [], "sections": base}


# Work an agent can do alone (on-page), work that needs a person (entity), an
# opportunity, an open question and a check that failed to run.
MIXED = dict(
    onpage={"title": "t", "meta_description": "", "h1": ["h"], "canonical": "https://ex.com/", "issues": [
        {"severity": "high", "finding": "Meta description missing.", "fix": "Write a 150-character description."}]},
    entity={"issues": [
        {"severity": "medium", "finding": "Missing sameAs link to Wikidata.", "fix": "Add the wikidata.org URL to sameAs."}]},
    page_types={"issues": [
        {"severity": "medium", "finding": "No comparison pages found.", "fix": "Create /vs/ pages.", "tags": ["opportunity"]}]},
    architecture={"issues": [
        {"severity": "info", "finding": "Link equity by section was not measured.", "evidence": "crawl stopped at max_pages=80",
         "fix": "Re-run `site_graph.py` with a higher --max-pages."}]},
    pagespeed={"error": "HTTP 429: rate limited"},
)

# Findings, but none an agent can finish alone: the Auto lane is empty.
NO_AUTO = dict(entity=MIXED["entity"])


def _summary(data):
    return gr.build_summary(data, gr.calculate_overall_score(data))


def _html(data, previous=None):
    return gr.generate_html(data, gr.calculate_overall_score(data), previous_summary=previous)


def _previous(data):
    prev = _summary(data)
    prev["timestamp"] = "2026-08-17T10:00:00"
    return prev


def dangling(html):
    """Fragment links whose target id is not on the page. Script text is ignored."""
    markup = re.sub(r"<script\b.*?</script>", "", html, flags=re.S)
    ids = set(re.findall(r'\bid="([^"]+)"', markup))
    return sorted({h for h in re.findall(r'href="#([^"]*)"', markup) if h not in ids})


CASES = {
    "empty audit": lambda: _html({"url": "https://ex.com/", "domain": "ex.com", "timestamp": "2026-09-18T10:00:00",
                                  "environment": {}, "environment_fixes": [], "sections": {}}),
    "clean run": lambda: _html(_data()),
    "mixed findings": lambda: _html(_data(**MIXED)),
    "no agent-fixable work": lambda: _html(_data(**NO_AUTO)),
    "previous run, nothing fixed": lambda: _html(_data(**MIXED), _previous(_data())),
    "previous run, something fixed": lambda: _html(_data(**NO_AUTO), _previous(_data(**MIXED))),
    "previous run, all fixed": lambda: _html(_data(), _previous(_data(**MIXED))),
}


@pytest.mark.parametrize("case", CASES)
def test_every_in_page_link_has_a_target(case):
    html = CASES[case]()
    assert 'href="#' in html
    assert dangling(html) == []


def test_the_checker_catches_a_missing_target():
    assert dangling('<a href="#F09">F09</a><div id="F01"></div>') == ["F09"]
    assert dangling('<div id="x"></div><script>var s = \'<a href="#nope">\';</script><a href="#x">x</a>') == []


def test_ai_can_fix_now_points_at_the_plan_when_its_lane_is_empty():
    empty = _html(_data(**NO_AUTO))
    assert 'id="lane-auto"' not in empty
    assert re.search(r'<a class="label" href="#plan">AI can fix now</a>', empty)
    full = _html(_data(**MIXED))
    assert 'id="lane-auto"' in full and '<a class="label" href="#lane-auto">AI can fix now</a>' in full


def test_see_what_cleared_appears_only_when_something_cleared():
    none_fixed = _html(_data(**MIXED), _previous(_data()))
    assert 'href="#fixed"' not in none_fixed and 'id="fixed"' not in none_fixed
    some_fixed = _html(_data(**NO_AUTO), _previous(_data(**MIXED)))
    assert 'href="#fixed">See what cleared</a>' in some_fixed and 'id="fixed"' in some_fixed


def test_link_handler_clears_the_severity_filter_before_scrolling():
    js = gr._REPORT_JS
    handler = js[js.index("In-page links scroll by script"):]
    assert "applyFilter('all')" in handler.split("scrollIntoView")[0]


def test_footer_says_what_to_do_when_links_go_nowhere():
    footer = re.search(r"<footer.*?</footer>", _html(_data()), re.S).group(0)
    assert "open the file in a web browser" in footer
