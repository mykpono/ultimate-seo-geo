"""citation_sampling.py: citation rates with honest margins of error.

The script calls no AI engine; it scores runs a person or tool recorded. What
must not regress is the statistics and the restraint: an interval that spans
the middle is "inconsistent", not a verdict; too few runs get no verdict; a
lookalike domain is never counted as the site.
"""

import csv
import os
import subprocess
import sys

import pytest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS)

import citation_sampling as cs  # noqa: E402


def run(engine="chatgpt", prompt="best crm for startups", cited="", mentioned="", domains=""):
    return {"date": "2026-09-14", "engine": engine, "prompt": prompt, "run": "1",
            "cited": cited, "mentioned": mentioned, "cited_domains": domains}


# --- statistics --------------------------------------------------------------


@pytest.mark.parametrize("k,n,low,high", [
    (0, 10, 0.0, 0.278),
    (5, 10, 0.237, 0.763),
    (10, 10, 0.722, 1.0),
    (2, 20, 0.028, 0.301),
])
def test_wilson_interval_matches_known_values(k, n, low, high):
    lo, hi = cs.wilson_interval(k, n)

    assert lo == pytest.approx(low, abs=0.002)
    assert hi == pytest.approx(high, abs=0.002)


def test_no_runs_has_no_interval():
    assert cs.wilson_interval(0, 0) is None


@pytest.mark.parametrize("k,n,expected", [
    (4, 4, "too few runs"),
    (9, 10, "cited in most runs"),
    (0, 10, "rarely or never cited"),
    (5, 10, "inconsistent"),
    (0, 5, "inconsistent"),
])
def test_verdicts_follow_the_interval_not_the_point_estimate(k, n, expected):
    """0 of 5 is not yet 'never cited': its interval still reaches 43%."""
    assert cs.verdict(k, n) == expected


# --- domains -----------------------------------------------------------------


@pytest.mark.parametrize("candidate,expected", [
    ("example.com", True),
    ("www.example.com", True),
    ("https://blog.example.com/post?x=1", True),
    ("EXAMPLE.COM", True),
    ("notexample.com", False),
    ("example.com.evil.net", False),
    ("", False),
])
def test_site_citations_match_the_domain_and_its_subdomains_only(candidate, expected):
    assert cs.domain_matches(candidate, "example.com") is expected


# --- scoring -----------------------------------------------------------------


def test_cited_is_derived_from_cited_domains_when_left_blank():
    result = cs.score([run(domains="www.example.com; rival.io"), run(domains="rival.io")], "example.com")

    assert result["engines"]["chatgpt"]["cited_runs"] == 1


def test_an_explicit_cited_value_overrides_the_domain_list():
    result = cs.score([run(cited="no", domains="example.com")], "example.com")

    assert result["engines"]["chatgpt"]["cited_runs"] == 0


def test_unfilled_template_rows_are_ignored_and_unreadable_rows_are_reported():
    rows = [run(cited="yes"), run(), run(engine="", cited="yes"), run(cited="maybe")]
    result = cs.score(rows, "example.com")

    assert result["runs_scored"] == 1
    assert result["unfilled_rows"] == 1
    assert result["skipped_rows"] == [4, 5]
    assert any("CSV line(s) 4, 5" in i for i in result["issues"])


def test_rarely_cited_while_competitors_lead_is_a_warning_naming_them():
    rows = [run(domains="rival.io; other.org") for _ in range(12)]
    result = cs.score(rows, "example.com")

    [warning] = [i for i in result["issues"] if i.startswith("⚠️")]
    assert "0/12 runs" in warning and "rival.io" in warning
    assert result["top_cited_domains"]["chatgpt"][0] == ["other.org", 12, 1.0]
    assert result["share_of_voice"]["chatgpt"] == 0.0


def test_an_inconsistent_result_is_never_a_warning():
    rows = [run(cited="yes") for _ in range(4)] + [run(cited="no") for _ in range(4)]
    result = cs.score(rows, "example.com")

    assert result["engines"]["chatgpt"]["verdict"] == "inconsistent"
    assert not [i for i in result["issues"] if i.startswith("⚠️")]
    assert any("add runs" in i for i in result["issues"])


def test_engines_and_prompts_are_scored_separately():
    rows = (
        [run(engine="ChatGPT", prompt="a", cited="yes") for _ in range(6)]
        + [run(engine="perplexity", prompt="a", cited="no") for _ in range(6)]
        + [run(engine="perplexity", prompt="b", cited="no") for _ in range(2)]
    )
    result = cs.score(rows, "example.com")

    assert set(result["engines"]) == {"chatgpt", "perplexity"}
    assert result["engines"]["chatgpt"]["verdict"] == "cited in most runs"
    thin = [p for p in result["prompts"] if p["verdict"] == "too few runs"]
    assert [(p["engine"], p["prompt"]) for p in thin] == [("perplexity", "b")]


def test_share_of_voice_counts_one_citation_per_domain_per_run():
    rows = [run(domains="example.com; rival.io"), run(domains="rival.io; rival.io")]
    result = cs.score(rows, "example.com")

    assert result["share_of_voice"]["chatgpt"] == pytest.approx(1 / 3, abs=0.001)


def test_mention_rate_uses_only_rows_that_recorded_it():
    rows = [run(cited="no", mentioned="yes"), run(cited="no", mentioned="no"), run(cited="no")]
    result = cs.score(rows, "example.com")

    assert result["engines"]["chatgpt"]["mention_rate"] == 0.5


def test_nothing_recorded_is_an_error():
    result = cs.score([run(), run()], "example.com")

    assert result["error"] and result["unfilled_rows"] == 2


# --- template and CLI ----------------------------------------------------------


def _cli(*args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "citation_sampling.py"), *args],
                          capture_output=True, text=True, timeout=30)


def test_template_round_trips_through_scoring(tmp_path):
    prompts = tmp_path / "prompts.txt"
    prompts.write_text("best crm for startups\n\ncrm for agencies\n")
    grid = tmp_path / "runs.csv"

    made = _cli("--template", "--prompts", str(prompts), "--engines", "chatgpt, Perplexity",
                "--runs", "3", "--output", str(grid))
    assert made.returncode == 0

    with open(grid, newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2 * 2 * 3
    assert list(rows[0]) == cs.COLUMNS
    assert {r["engine"] for r in rows} == {"chatgpt", "perplexity"}

    rows[0]["cited_domains"] = "example.com"
    with open(grid, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cs.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    scored = _cli(str(grid), "--domain", "example.com", "--json")
    assert scored.returncode == 0, scored.stdout + scored.stderr
    assert '"runs_scored": 1' in scored.stdout


def test_scoring_without_a_domain_is_a_usage_error(tmp_path):
    grid = tmp_path / "runs.csv"
    grid.write_text("engine,prompt,cited\nchatgpt,a,yes\n")

    assert _cli(str(grid)).returncode == 2


def test_a_csv_without_the_needed_columns_is_an_error(tmp_path):
    grid = tmp_path / "runs.csv"
    grid.write_text("engine,question,result\nchatgpt,a,yes\n")

    proc = _cli(str(grid), "--domain", "example.com", "--json")
    assert proc.returncode == 1 and "needs engine, prompt" in proc.stdout
