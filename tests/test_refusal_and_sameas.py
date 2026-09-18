"""Two follow-ups to the 1.19.0 report work.

* One rule for "the server refused the crawler" (url_safety.is_refusal), shared by
  broken_links.py and navigation_checker.py, so the same link is never a Critical in
  one check and a note in the other.
* entity_checker.py raises one sameAs finding, not one per platform, and the entity
  score counts defects only, so how findings are itemised cannot move the score.
"""

import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import broken_links  # noqa: E402
import entity_checker  # noqa: E402
import generate_report as gr  # noqa: E402
import url_safety  # noqa: E402


# --- one refusal rule -------------------------------------------------------------------

@pytest.mark.parametrize("status", [401, 403, 429, 999])
def test_another_host_refusing_is_unverified(status):
    assert url_safety.is_refusal(status, internal=False)


@pytest.mark.parametrize("status,refused", [(401, True), (429, True), (403, False), (999, False), (404, False), (500, False)])
def test_the_audited_site_gets_the_benefit_of_the_doubt_only_for_login_and_throttling(status, refused):
    assert url_safety.is_refusal(status, internal=True) is refused


@pytest.mark.parametrize("status", [200, 301, 404, 410, 500, 503, None])
def test_everything_else_is_not_a_refusal(status):
    assert not url_safety.is_refusal(status, internal=False) and not url_safety.is_refusal(status, internal=True)


def test_broken_links_uses_the_shared_rule():
    assert broken_links.is_refused({"is_internal": True, "status": 401})
    assert not broken_links.is_refused({"is_internal": True, "status": 403})
    assert broken_links.is_refused({"is_internal": False, "status": 403})
    assert broken_links.REFUSAL_STATUSES is url_safety.REFUSAL_STATUSES


@pytest.mark.parametrize("script", ["broken_links", "navigation_checker"])
def test_neither_checker_keeps_a_private_status_list(script):
    with open(os.path.join(ROOT, "scripts", f"{script}.py"), encoding="utf-8") as fh:
        source = fh.read()
    assert "is_refusal(" in source and "frozenset({401" not in source


# --- one sameAs finding --------------------------------------------------------------------

def _missing(*names):
    table = {info["name"]: {"domain": domain, "priority": info["priority"], "kg_signal": info["kg_signal"]}
             for domain, info in entity_checker.SAMEAS_PLATFORMS.items()}
    return {name: table[name] for name in names}


def test_every_missing_profile_is_one_finding():
    issue = entity_checker.sameas_gap_issue(_missing("Wikipedia", "Wikidata", "LinkedIn"), True, True)
    assert issue["finding"].startswith("Entity schema sameAs is missing 3 profile link(s)")
    assert issue["platforms"] == ["Wikipedia", "Wikidata", "LinkedIn"] and issue["severity"] == "Warning"
    assert issue["code"] == "entity.sameas_missing" and issue["lane"] == "Human" and "dependency" not in issue


def test_a_link_is_not_asked_for_when_its_target_does_not_exist():
    issue = entity_checker.sameas_gap_issue(_missing("Wikipedia", "Wikidata", "LinkedIn"), False, False)
    assert issue["platforms"] == ["LinkedIn"] and issue["severity"] == "Info"
    assert "Wikipedia and Wikidata left out" in issue["dependency"]
    assert entity_checker.sameas_gap_issue(_missing("Wikipedia"), True, False) is None
    assert entity_checker.sameas_gap_issue({}, True, True) is None


def test_the_finding_keeps_one_identity_as_the_list_shrinks():
    before = entity_checker.sameas_gap_issue(_missing("Wikidata", "LinkedIn", "Twitter/X"), True, True)
    after = entity_checker.sameas_gap_issue(_missing("LinkedIn"), True, True)
    assert gr.finding_code("entity", before, before["finding"])[1] == gr.finding_code("entity", after, after["finding"])[1]


def test_the_report_places_it_with_the_owner_not_the_agent():
    issue = entity_checker.sameas_gap_issue(_missing("LinkedIn"), True, True)
    [collected] = gr._collect_issues({"sections": {"entity": {"issues": [issue]}}})
    assert collected["lane"] == "Human" and "only the owner knows" in collected["lane_reason"]


# --- the entity score counts defects, not notes --------------------------------------------------

def _entity_score(issues):
    data = {"sections": {"entity": {"sameas_analysis": {"total_found": 4}, "wikidata": {"found": True},
                                     "wikipedia": {"found": False}, "issues": issues}}}
    return gr.calculate_overall_score(data)["categories"]["entity"]


NOTE = {"severity": "Info", "finding": "Could not verify sameAs URL: https://yelp.com/biz/x"}
DEFECT = {"severity": "Warning", "finding": "sameAs URL returns HTTP 404: https://x.com/gone"}


def test_notes_and_data_gaps_cost_nothing():
    assert _entity_score([]) == _entity_score([NOTE, NOTE, NOTE]) == 85


def test_a_defect_still_costs_ten():
    assert _entity_score([DEFECT]) == 75 and _entity_score([DEFECT, NOTE]) == 75
    assert _entity_score(["⚠️ plain-string issue"]) == 75  # a string issue is judged as before
