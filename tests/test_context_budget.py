"""What each SKILL.md route makes an agent read, held under recorded ceilings.

1.23.0 cut a full audit's instructions from about 89 KB to 34 KB and SKILL.md
from about 20 KB to 15 KB. Nothing stopped them growing back one paragraph at
a time. scripts/context_budget.py measures every route in SKILL.md's routing
table (SKILL.md plus the files its Read column names); these tests fail when a
route passes its ceiling in tests/context_budget.json, when a route names a
file that does not exist, or when the routing table cannot be read at all.

Raising a ceiling is allowed, but only on purpose: in the PR that grows the
route, with the reason in the PR body.
"""

import json
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import context_budget as cb  # noqa: E402
import generate_report as gr  # noqa: E402

BUDGET = json.loads(open(os.path.join(ROOT, "tests", "context_budget.json"), encoding="utf-8").read())


@pytest.fixture(scope="module")
def measured():
    return cb.measure()


def test_every_route_is_within_its_ceiling(measured):
    problems = cb.check(measured, BUDGET)
    assert not problems, "\n".join(problems) + "\nTrim the files, or raise the ceiling on purpose."


def test_the_routing_table_is_found_and_has_the_full_audit_route(measured):
    goals = [r["goal"] for r in measured["routes"]]
    assert len(goals) >= 15
    assert "Full scored audit" in goals


def test_every_route_in_skill_md_has_a_recorded_ceiling(measured):
    """A new route gets the default ceiling; recording its own keeps the table honest."""
    missing = [r["goal"] for r in measured["routes"] if r["goal"] not in BUDGET["routes"]]
    assert not missing, f"add ceilings for: {missing}"


def test_no_ceiling_is_left_for_a_route_that_no_longer_exists(measured):
    goals = {r["goal"] for r in measured["routes"]}
    stale = [g for g in BUDGET["routes"] if g not in goals]
    assert not stale, f"remove ceilings for routes SKILL.md no longer has: {stale}"


def test_a_full_audit_reads_only_skill_md_and_its_playbook(measured):
    audit = next(r for r in measured["routes"] if r["goal"] == "Full scored audit")
    assert audit["files"] == ["references/procedures/02-full-site-audit.md"]


def test_alternatives_count_the_larger_file(tmp_path):
    refs = tmp_path / "references" / "procedures"
    refs.mkdir(parents=True)
    (tmp_path / "references" / "small.md").write_text("x" * 10)
    (tmp_path / "references" / "big.md").write_text("x" * 100)
    (refs / "07-keywords.md").write_text("x" * 5)
    files, missing = cb.route_files("`procedures/07-keywords.md`, `small.md` or `big.md`", tmp_path)
    assert [f.name for f in files] == ["07-keywords.md", "big.md"] and missing == []


def test_shorthand_procedure_names_resolve_and_unknown_files_are_reported(tmp_path):
    refs = tmp_path / "references" / "procedures"
    refs.mkdir(parents=True)
    (refs / "13-image-seo.md").write_text("x")
    files, missing = cb.route_files("`procedures/13-…`, `nope.md`", tmp_path)
    assert [f.name for f in files] == ["13-image-seo.md"] and missing == ["nope.md"]


def test_check_reports_an_oversized_route_and_skill_md():
    result = {"skill_md_bytes": 20_000, "routes": [{"goal": "A", "bytes": 50_000, "unresolved": []},
                                                     {"goal": "B", "bytes": 10, "unresolved": ["x.md"]}]}
    budget = {"skill_md_max_bytes": 16_000, "default_route_max_bytes": 60_000, "routes": {"A": 40_000}}
    problems = cb.check(result, budget)
    assert len(problems) == 3
    assert any("SKILL.md" in p for p in problems) and any(p.startswith("A:") for p in problems)
    assert any("x.md" in p for p in problems)


def test_the_cli_check_passes_on_this_tree(capsys):
    assert cb.main(["--check"]) == 0


def test_the_digest_stays_small_however_many_findings_a_run_has():
    """The digest is the other half of an audit's reading: bounded by its finding cap, not by the site."""
    findings = [{"id": f"F{i:03d}", "severity": "medium", "section": "onpage", "lane": "Auto", "kind": "defect",
                 "finding": "A finding of ordinary length that names a page and what is wrong " * 2,
                 "fix": "Change the element on that page to say what it should " * 2} for i in range(300)]
    findings += [{"id": f"I{i:03d}", "severity": "info", "section": "onpage", "finding": "note"} for i in range(200)]
    summary = {"url": "https://ex.com/", "overall": 70, "measured_categories": 15, "findings": findings,
               "counts": {}, "action_plan": {"Auto": [f["id"] for f in findings[:300]]}, "open_questions": []}
    digest = gr.build_digest(summary)
    # 15 full lines, then IDs only: about 10 KB even for 500 findings.
    assert len(digest.encode()) < 12_000, len(digest.encode())
