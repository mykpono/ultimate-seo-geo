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


# --- Brand facts (--facts): are AI answers right about the brand? ---------------------------

import json  # noqa: E402

FACTS = {
    "brand": "Acme Analytics", "aliases": ["Acme"],
    "others": ["Mixpanel", "Amplitude", "Heap"],
    "facts": [
        {"field": "founding year", "type": "year", "value": 2016, "source": "https://acme.example/about"},
        {"field": "headquarters", "type": "place", "value": "Austin", "aliases": ["Austin, TX"]},
        {"field": "founders", "type": "people", "value": ["Jane Doe", "Raj Patel"]},
        {"field": "pricing", "type": "money", "value": [0, 29, 99], "source": "https://acme.example/pricing"},
        {"field": "free plan", "type": "claim", "value": True, "true_phrases": ["free plan", "free tier"]},
    ],
    "false_claims": [{"phrase": "acquired by"}],
}


def facts_for(answer, engine="chatgpt"):
    result = cs.check_brand_facts([{"engine": engine, "prompt": "p", "run": "1", "answer": answer}], FACTS)
    return {f["field"]: (f["stated_in"], f["wrong"]) for f in result["facts"]}


def test_a_correct_answer_states_every_fact_right():
    answer = ("Acme Analytics was founded in 2016 by Jane Doe and Raj Patel and is headquartered in Austin, Texas. "
              "It offers a free plan, and paid plans start at $29/month.")
    got = facts_for(answer)
    assert got["founding year"] == (1, 0) and got["headquarters"] == (1, 0) and got["founders"] == (1, 0)
    assert got["pricing"] == (1, 0) and got["free plan"] == (1, 0) and got["false claim: acquired by"] == (0, 0)


def test_wrong_facts_are_caught_with_the_sentence_quoted():
    answer = "Founded in 2018, Acme Analytics helps SaaS teams. Acme is based in San Francisco."
    result = cs.check_brand_facts([{"engine": "chatgpt", "prompt": "what is acme", "run": "2", "answer": answer}], FACTS)
    by = {f["field"]: f for f in result["facts"]}
    assert by["founding year"]["wrong"] == 1 and by["founding year"]["wrong_examples"][0]["stated"] == "2018"
    assert by["headquarters"]["wrong_examples"][0]["sentence"] == "Acme is based in San Francisco."
    issue = next(i for i in result["issues"] if i["code"] == "brand_fact.founding-year")
    assert "https://acme.example/about" in issue["fix"] and issue["confidence"] == "Likely" and issue["lane"] == "Human"


def test_a_competitors_facts_in_the_same_sentence_are_not_the_brands():
    """Listicle answers name several companies in one sentence."""
    answer = ("Acme Analytics and Mixpanel (founded 2009) both offer funnels. "
              "Unlike Amplitude, which is based in San Francisco, Acme Analytics focuses on small teams. "
              "Acme Analytics plans start at $29, compared to Mixpanel's $49.")
    got = facts_for(answer)
    assert got["founding year"] == (0, 0)
    assert got["headquarters"] == (0, 0)
    assert got["pricing"] == (1, 0)


def test_a_pronoun_sentence_after_the_brand_is_read_as_the_brand():
    got = facts_for("Acme Analytics was acquired by Oracle in 2023. It was founded in 2019. Its Growth plan costs $99 a month.")
    assert got["founding year"] == (1, 1) and got["pricing"] == (1, 0) and got["false claim: acquired by"] == (1, 1)


def test_a_pronoun_after_a_sentence_naming_a_competitor_is_not_carried():
    assert facts_for("Acme Analytics and Heap are both popular. It was founded in 2013.")["founding year"] == (0, 0)


def test_a_negated_claim_is_the_opposite_claim():
    assert facts_for("Acme Analytics does not have a free plan.")["free plan"] == (1, 1)
    assert facts_for("Acme Analytics has a generous free tier.")["free plan"] == (1, 0)


def test_founded_when_is_not_founded_by_whom():
    assert facts_for("Acme Analytics was founded in 2016 in Austin.")["founders"] == (0, 0)
    assert facts_for("Maria Lopez, founder of Acme Analytics, runs sales.")["founders"] == (1, 1)
    assert facts_for("Acme Analytics was co-founded by Raj Patel.")["founders"] == (1, 0)  # a surname or full name counts


def test_an_unofficial_price_is_a_hypothesis():
    result = cs.check_brand_facts([{"engine": "perplexity", "prompt": "p", "run": "1",
                                    "answer": "Acme Analytics pricing starts at $49 per month."}], FACTS)
    issue = next(i for i in result["issues"] if i["code"] == "brand_fact.pricing")
    assert issue["confidence"] == "Hypothesis"


def test_answers_that_do_not_name_the_brand_or_are_empty_are_skipped():
    rows = [{"engine": "chatgpt", "prompt": "p", "answer": "Heap was founded in 2013."},
            {"engine": "chatgpt", "prompt": "p", "answer": ""}]
    result = cs.check_brand_facts(rows, FACTS)
    assert (result["answers_recorded"], result["answers_naming_brand"]) == (1, 0)
    assert all(f["stated_in"] == 0 for f in result["facts"]) and result["issues"] == []


def test_wrong_rates_carry_a_wilson_interval_and_count_by_engine():
    rows = [{"engine": e, "prompt": "p", "run": str(i), "answer": a} for i, (e, a) in enumerate([
        ("chatgpt", "Acme Analytics was founded in 2016."), ("chatgpt", "Acme Analytics was founded in 2018."),
        ("perplexity", "Acme Analytics was founded in 2016."), ("perplexity", "Acme Analytics was founded in 2016."),
    ])]
    year = next(f for f in cs.check_brand_facts(rows, FACTS)["facts"] if f["field"] == "founding year")
    assert (year["stated_in"], year["wrong"], year["wrong_rate"]) == (4, 1, 0.25)
    assert year["wrong_ci95"] == [pytest.approx(v, abs=1e-3) for v in cs.wilson_interval(1, 4)]
    assert year["by_engine"] == {"chatgpt": {"stated": 2, "wrong": 1}, "perplexity": {"stated": 2, "wrong": 0}}


@pytest.mark.parametrize("bad,message", [
    ({"facts": []}, "brand"),
    ({"brand": "Acme", "facts": [{"field": "x", "type": "colour", "value": 1}]}, "type"),
    ({"brand": "Acme", "facts": [{"field": "free plan", "type": "claim", "value": "yes", "true_phrases": ["free"]}]}, "true/false"),
    ({"brand": "Acme", "facts": [{"field": "founded", "type": "year"}]}, "no \"value\""),
])
def test_a_malformed_facts_file_fails_loudly(tmp_path, bad, message):
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match=message):
        cs.load_facts(str(path))


def test_template_has_an_answer_column():
    assert cs.COLUMNS[-1] == "answer"


def test_cli_facts_only_and_combined_with_scoring(tmp_path):
    facts = tmp_path / "facts.json"
    facts.write_text(json.dumps(FACTS))
    runs = tmp_path / "runs.csv"
    with open(runs, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["engine", "prompt", "run", "cited_domains", "answer"])
        w.writerow(["chatgpt", "what is acme", "1", "acme.example", "Founded in 2018, Acme Analytics helps teams."])
    only = _cli(str(runs), "--facts", str(facts), "--json")
    assert only.returncode == 0, only.stderr
    out = json.loads(only.stdout)
    assert "engines" not in out and out["brand_facts"]["answers_naming_brand"] == 1
    assert [i["code"] for i in out["issues"]] == ["brand_fact.founding-year"]
    both = json.loads(_cli(str(runs), "--domain", "acme.example", "--facts", str(facts), "--json").stdout)
    assert "engines" in both and "brand_facts" in both
    human = _cli(str(runs), "--facts", str(facts))
    assert human.returncode == 0 and "founding year: wrong in 1/1" in human.stdout


def test_cli_facts_only_needs_an_answer_column(tmp_path):
    facts = tmp_path / "facts.json"
    facts.write_text(json.dumps(FACTS))
    runs = tmp_path / "runs.csv"
    runs.write_text("engine,prompt,cited\nchatgpt,p,yes\n")
    proc = _cli(str(runs), "--facts", str(facts), "--json")
    assert proc.returncode == 1 and "answer column" in json.loads(proc.stdout)["error"]


def test_a_parenthesis_about_an_unlisted_company_is_not_the_brands():
    """Zendesk is not in "others": only the parenthesis rule keeps its year out."""
    assert facts_for("Acme Analytics and Zendesk (founded 2007) both have help centres.")["founding year"] == (0, 0)


def test_a_listed_competitor_between_the_brand_and_the_keyword_takes_the_fact():
    assert facts_for("Acme Analytics partners with Heap, which was founded in 2013.")["founding year"] == (0, 0)


def test_every_quoted_price_must_be_official():
    assert facts_for("Acme Analytics plans cost $29 and $59 per month.")["pricing"] == (1, 1)
