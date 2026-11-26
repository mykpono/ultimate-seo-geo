"""generate_report.py: a site that answers HTTP 429 must not poison the audit.

A live audit of a rate-limited site (nginx answering 429 within seconds of the
report and a crawl running together) scored 85/100 with 429 refusals written
up as findings, and gave no warning; the same site re-run one request at a
time scored 93 with no 429s. These tests pin the fix:

  * any check whose output reports a 429 from the audited site is discarded:
    unmeasured, out of the score, its findings gone, listed under "throttled";
  * the checks that read the shared site graph inherit the graph's 429s;
  * the throttled checks are one open question (Q-throttled), the digest and
    console say THROTTLED, and a --fail-under gate is inconclusive, not a fail;
  * Google API quotas (PageSpeed, Search Console) are not the site throttling;
  * --polite runs one check at a time with one worker per crawler and a delay.

No network: run_script, fetch_page and build_site_graph are replaced.
"""

import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import generate_report as gr  # noqa: E402


# --- detection ------------------------------------------------------------------


@pytest.mark.parametrize("value, expected", [
    ({"status": 429}, 1),
    ({"status_code": 429, "url": "https://ex.com/a"}, 1),
    ({"broken": [{"url": "u", "status": 429}, {"url": "v", "status": 404}]}, 1),
    ({"issues": ["🔴 /pricing returned HTTP 429", "🔴 /about returned HTTP 429"]}, 2),
    ({"error": "429 Client Error: Too Many Requests for url: https://ex.com/"}, 1),
    ({"error": "Too Many Requests"}, 1),
    ({"count": 429, "words": 429, "status": 200}, 0),     # a number that is not a status
    ({"title": "Product 4290 review", "status": 200}, 0),
    ({"is_429": True}, 0),
])
def test_a_429_is_counted_from_status_fields_and_wording(value, expected):
    assert gr.count_throttle_signals(value) == expected


def test_graph_throttling_is_read_from_its_failed_fetches(tmp_path):
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"crawl": {"failed": [{"url": "a", "status": 429, "error": "HTTP 429"},
                                                      {"url": "b", "status": 500, "error": "HTTP 500"}]},
                                 "pages": {"x": {"title": "Too Many Requests in our FAQ"}}}))
    assert gr.graph_throttle_count(str(graph)) == 1      # one refusal (status + its error), never page text
    assert gr.graph_throttle_count(None) == 0


# --- discarding -----------------------------------------------------------------


def sections():
    return {
        "security": {"score": 90},
        "social": {"score": 80},
        "robots": {"status": 200, "sitemaps": ["https://ex.com/sitemap.xml"], "ai_crawler_status": {}},
        "onpage": {"title": "t", "meta_description": "m", "h1": ["h"], "canonical": "https://ex.com/"},
        "readability": {"flesch_reading_ease": 65},
        "content_quality": {"score": 70},
        "schema_validation": {"score": 100},
        "sitemap": {"score": 100},
        "broken_links": {"summary": {"total": 10, "broken": 4},
                         "broken": [{"url": f"https://ex.com/{i}", "status": 429} for i in range(4)]},
        "pagespeed": {"error": "Rate limited by Google API (HTTP 429). Add an API key."},
    }


def data():
    return {"url": "https://ex.com/", "timestamp": "t", "sections": sections()}


def test_a_throttled_check_is_discarded_and_leaves_the_score():
    d = data()
    hits = gr.discard_throttled(d)

    assert hits == {"broken_links": 4}
    assert d["sections"]["broken_links"]["throttled"] is True
    scores = gr.calculate_overall_score(d)
    assert "broken_links" in scores["unmeasured"]
    summary = gr.build_summary(d, scores)
    assert summary["throttled"] == ["broken_links"]
    assert not [f for f in summary["findings"] if f["section"] == "broken_links"]


def test_google_api_quotas_are_not_the_site_throttling():
    d = data()
    gr.discard_throttled(d)
    assert "pagespeed" not in d["throttled"]
    assert not d["sections"]["pagespeed"].get("throttled")


def test_checks_reading_the_site_graph_inherit_its_throttling():
    d = data()
    d["sections"]["internal_links"] = {"score": 90}
    d["sections"]["navigation"] = {"findings": []}
    hits = gr.discard_throttled(d, graph_hits=3)

    assert hits["internal_links"] == 3 and hits["navigation"] == 3 and hits["sitemap"] == 3
    assert "security" not in hits


def test_quick_skipped_sections_are_left_alone():
    d = data()
    d["sections"]["broken_links"] = {"error": gr.QUICK_SKIP_REASON, "measured": False, "skipped": True}
    assert gr.discard_throttled(d, graph_hits=2).get("broken_links") is None


def test_a_clean_run_reports_nothing():
    d = data()
    d["sections"].pop("broken_links")
    assert gr.discard_throttled(d) == {}
    summary = gr.build_summary(d, gr.calculate_overall_score(d))
    assert summary["throttled"] == [] and "Q-throttled" not in [q["id"] for q in summary["open_questions"]]


def test_throttled_checks_are_one_open_question_with_the_fix():
    d = data()
    d["sections"]["internal_links"] = {"status": 429}
    gr.discard_throttled(d)
    summary = gr.build_summary(d, gr.calculate_overall_score(d))
    ids = [q["id"] for q in summary["open_questions"]]

    assert ids.count("Q-throttled") == 1
    assert "Q-broken_links" not in ids and "Q-internal_links" not in ids
    question = next(q for q in summary["open_questions"] if q["id"] == "Q-throttled")
    assert "--polite" in question["close"]


def test_the_digest_leads_with_the_throttling_warning():
    d = data()
    gr.discard_throttled(d)
    digest = gr.build_digest(gr.build_summary(d, gr.calculate_overall_score(d)))

    warning = next(line for line in digest.splitlines() if line.startswith("⚠ THROTTLED"))
    assert "broken_links" in warning and "--polite" in warning
    assert digest.index("⚠ THROTTLED") < digest.index("## Groups")
    not_measured = [line for line in digest.splitlines() if line.startswith("Not measured")]
    assert not_measured and "broken_links" not in not_measured[0]   # listed once, as throttled


def test_a_score_gate_on_a_throttled_run_is_inconclusive_but_fail_on_still_fails():
    d = data()
    gr.discard_throttled(d)
    summary = gr.build_summary(d, gr.calculate_overall_score(d))

    gate = gr.evaluate_gate(summary, fail_under=99)
    assert gate["result"] == "inconclusive" and gate["exit_code"] == gr.EXIT_GATE_INCONCLUSIVE
    summary["findings"].append({"id": "F99", "severity": "critical", "level": "critical", "section": "security",
                                "finding": "x"})
    assert gr.evaluate_gate(summary, fail_under=99, fail_on="critical")["result"] == "fail"


# --- polite mode ----------------------------------------------------------------


@pytest.fixture
def offline(tmp_path):
    calls = []
    graph_calls = []
    pool_sizes = []

    def fake_run(script, args, timeout=None):
        calls.append((script, list(args)))
        return {"score": 80}

    def fake_fetch(url, render="never"):
        page = tmp_path / f"p{len(calls)}.html"
        page.write_text("<html><head><title>t</title></head><body><h1>h</h1></body></html>")
        return str(page), None

    def fake_graph(url, **kwargs):
        graph_calls.append(kwargs)
        return None

    real_pool = gr.ThreadPoolExecutor

    def sized_pool(max_workers=None):
        pool_sizes.append(max_workers)
        return real_pool(max_workers=max_workers)

    with patch.object(gr, "run_script", side_effect=fake_run), \
         patch.object(gr, "fetch_page", side_effect=fake_fetch), \
         patch.object(gr, "build_site_graph", side_effect=fake_graph), \
         patch.object(gr, "ThreadPoolExecutor", side_effect=sized_pool):
        yield calls, graph_calls, pool_sizes


def args_of(calls, script):
    return next(a for s, a in calls if s == script)


def test_polite_runs_one_check_at_a_time_with_one_worker_per_crawler(offline):
    calls, graph_calls, pool_sizes = offline
    gr.collect_data("https://ex.com/", polite=True, delay=3.0)

    assert pool_sizes == [1]
    assert graph_calls == [{"polite": True, "delay": 3.0}]
    broken = args_of(calls, "broken_links.py")
    assert broken[broken.index("--workers") + 1] == "1"
    canonical = args_of(calls, "canonical_checker.py")
    assert canonical[canonical.index("--workers") + 1] == "1"


def test_without_polite_the_run_stays_parallel(offline):
    calls, graph_calls, pool_sizes = offline
    gr.collect_data("https://ex.com/")

    assert pool_sizes == [gr._MAX_PARALLEL_SCRIPTS]
    assert graph_calls == [{}]
    assert "--workers" not in args_of(calls, "canonical_checker.py")


def test_polite_site_graph_gets_one_worker_and_the_delay(tmp_path):
    seen = {}

    def fake_run(script, args, timeout=None):
        seen["args"], seen["timeout"] = args, timeout
        return {"error": "offline"}

    with patch.object(gr, "run_script", side_effect=fake_run):
        gr.build_site_graph("https://ex.com/", polite=True, delay=2.5)
    a = seen["args"]
    assert a[a.index("--workers") + 1] == "1" and a[a.index("--delay") + 1] == "2.5"
    assert seen["timeout"] > gr._SCRIPT_TIMEOUT_CRAWL


def run_main(argv, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["generate_report.py", "https://ex.com/", "--format", "none", *argv])
    with patch.object(gr, "collect_data", return_value=data()) as collect:
        gr.main()
    return collect


def test_delay_implies_polite(monkeypatch, tmp_path):
    collect = run_main(["--delay", "4"], monkeypatch, tmp_path)
    assert collect.call_args.kwargs["polite"] is True and collect.call_args.kwargs["delay"] == 4.0


def test_polite_defaults_to_the_standard_delay(monkeypatch, tmp_path):
    collect = run_main(["--polite"], monkeypatch, tmp_path)
    assert collect.call_args.kwargs["delay"] == gr.POLITE_DELAY_DEFAULT


@pytest.mark.parametrize("value", ["-1", "31"])
def test_delay_out_of_range_is_refused(monkeypatch, tmp_path, value):
    with pytest.raises(SystemExit) as exit_info:
        run_main(["--delay", value], monkeypatch, tmp_path)
    assert exit_info.value.code == 2


def test_collect_data_discards_a_check_the_site_throttled(tmp_path):
    """End to end through collect_data: the 429s a script reports never reach the score."""
    def fake_run(script, args, timeout=None):
        if script == "broken_links.py":
            return {"summary": {"total": 3, "broken": 3}, "broken": [{"url": "u", "status": 429}] * 3}
        return {"score": 80}

    def fake_fetch(url, render="never"):
        page = tmp_path / "p.html"
        page.write_text("<html><head><title>t</title></head><body><h1>h</h1></body></html>")
        return str(page), None

    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"crawl": {"failed": [{"url": "x", "status": 429}]}}))
    with patch.object(gr, "run_script", side_effect=fake_run), \
         patch.object(gr, "fetch_page", side_effect=fake_fetch), \
         patch.object(gr, "build_site_graph", return_value=str(graph)):
        d = gr.collect_data("https://ex.com/")

    assert d["throttled"]["broken_links"] == 3
    assert d["throttled"]["internal_links"] == 1          # read the throttled graph
    assert "security" not in d["throttled"]
    assert d["sections"]["broken_links"]["throttled"] is True
