"""generate_report.py --quick: a homepage snapshot, never a Health Score.

--quick skips every crawl, PageSpeed and the backlink sample, so its number
leaves out about a third of the weight and is not comparable with a full run.
These tests pin that nothing downstream can mistake it for the Health Score:
the summary says scope "quick", the digest says "NOT a Health Score", no report
file is written, the skipped checks become one open question rather than ten,
and report_lint rejects a score copied from it (tests/test_report_lint.py).

No network: run_script, fetch_page and build_site_graph are replaced.
"""

import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import generate_report as gr  # noqa: E402


@pytest.fixture
def offline(tmp_path):
    """collect_data with every script answering {"score": 80} and a saved homepage."""
    page = tmp_path / "page.html"
    page.write_text("<html><head><title>t</title></head><body><h1>h</h1></body></html>", encoding="utf-8")
    ran = []

    def fake_run(script, args, timeout=None):
        ran.append(script)
        return {"score": 80}

    def fake_fetch(url, render="never"):
        copy = tmp_path / f"copy-{len(ran)}.html"
        copy.write_text(page.read_text(), encoding="utf-8")
        return str(copy), None

    graph = patch.object(gr, "build_site_graph", side_effect=AssertionError("--quick must not crawl"))
    with patch.object(gr, "run_script", side_effect=fake_run), \
         patch.object(gr, "fetch_page", side_effect=fake_fetch):
        yield ran, graph


def test_quick_skips_every_crawl_and_marks_the_scope(offline):
    ran, graph = offline
    with graph:
        data = gr.collect_data("https://ex.com/", quick=True)

    assert data["scope"] == "quick"
    for name in gr.QUICK_SKIPPED_CHECKS:
        assert data["sections"][name]["skipped"] is True
    skipped_scripts = {"broken_links.py", "internal_links.py", "pagespeed.py", "link_profile.py",
                       "duplicate_content.py", "programmatic_seo_auditor.py", "site_architecture.py",
                       "navigation_checker.py", "page_type_classifier.py", "article_seo.py"}
    assert not skipped_scripts & set(ran)
    assert {"robots_checker.py", "security_headers.py", "parse_html.py", "validate_schema.py"} <= set(ran)


def test_skipped_checks_drop_out_of_the_score_and_become_one_open_question(offline):
    ran, graph = offline
    with graph:
        data = gr.collect_data("https://ex.com/", quick=True)
    scores = gr.calculate_overall_score(data)
    summary = gr.build_summary(data, scores)

    weighted_skips = [k for k in gr.QUICK_SKIPPED_CHECKS if gr.CHECK_WEIGHTS.get(k)]
    assert sorted(summary["skipped"]) == sorted(weighted_skips)
    assert summary["scope"] == "quick"
    ids = [q["id"] for q in summary["open_questions"]]
    assert ids.count("Q-quick") == 1
    assert not any(f"Q-{k}" in ids for k in weighted_skips)


def test_the_digest_says_it_is_not_a_health_score():
    summary = {"scope": "quick", "overall": 88, "measured_categories": 12, "skipped": ["pagespeed"],
               "unmeasured": ["pagespeed", "hreflang"], "findings": [], "counts": {}}
    digest = gr.build_digest(summary)

    assert "Quick check: 88/100 from 12 homepage checks" in digest
    assert "NOT a Health Score" in digest
    assert "Health Score: 88" not in digest
    assert "Skipped by --quick: pagespeed" in digest
    assert "Not measured (left out of the score): hreflang" in digest


def test_a_full_run_is_labelled_full_with_nothing_skipped():
    data = {"url": "https://ex.com/", "timestamp": "t", "sections": {"security": {"score": 90}}}
    summary = gr.build_summary(data, gr.calculate_overall_score(data))
    assert summary["scope"] == "full" and summary["skipped"] == []


def run_main(argv, monkeypatch, tmp_path, fixture):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["generate_report.py", "https://ex.com/", *argv])
    with patch.object(gr, "collect_data", return_value=fixture) as collect:
        gr.main()
    return collect


def quick_fixture():
    sections = {"security": {"score": 90}, "social": {"score": 80}, "robots": {"status": 200, "sitemaps": [],
                "ai_crawler_status": {}}, "onpage": {"title": "t"}, "schema_validation": {"score": 100},
                "sitemap": {"score": 100}}
    sections.update({k: {"error": gr.QUICK_SKIP_REASON, "measured": False, "skipped": True}
                     for k in gr.QUICK_SKIPPED_CHECKS})
    return {"url": "https://ex.com/", "timestamp": "t", "scope": "quick", "sections": sections}


def test_quick_alone_prints_the_digest_and_writes_no_report_file(monkeypatch, tmp_path, capsys):
    collect = run_main(["--quick"], monkeypatch, tmp_path, quick_fixture())

    assert collect.call_args.kwargs["quick"] is True
    out = capsys.readouterr()
    assert out.out.startswith("# Audit digest: https://ex.com/")
    assert "NOT a Health Score" in out.out
    assert "not a Health Score" in out.err
    assert not list(tmp_path.glob("seo-report-*"))


def test_quick_with_json_writes_a_quick_summary(monkeypatch, tmp_path):
    run_main(["--quick", "--json", "s.json"], monkeypatch, tmp_path, quick_fixture())
    summary = json.loads((tmp_path / "s.json").read_text())
    assert summary["scope"] == "quick" and "pagespeed" in summary["skipped"]


@pytest.mark.parametrize("extra", [["--format", "html"], ["--format", "pdf"], ["--crawl-deep"],
                                   ["--fail-under", "70"]])
def test_quick_refuses_options_that_need_a_full_run(monkeypatch, tmp_path, extra):
    with pytest.raises(SystemExit) as exit_info:
        run_main(["--quick", *extra], monkeypatch, tmp_path, quick_fixture())
    assert exit_info.value.code == 2


def test_without_quick_the_default_format_is_still_html(monkeypatch, tmp_path):
    full = dict(quick_fixture(), scope="full")
    full["sections"] = {k: v for k, v in full["sections"].items() if not v.get("skipped")}
    with patch.object(gr, "generate_html", return_value="<html></html>"):
        run_main([], monkeypatch, tmp_path, full)
    assert (tmp_path / "seo-report-ex_com.html").exists()
