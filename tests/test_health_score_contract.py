"""One Health Score: the one generate_report.py computes.

The § 2 audit template used to carry its own formula (a positive/deficit
signal ratio minus Critical −15 / High −8 / Medium −3 / Low −1) and its own
category weights (Content 22%, Technical 18%, ...), while the script computed
a weighted mean over its checks in which Technical carried 36%. An agent that
ran the script and then followed the template reported two different scores
for one site. These tests keep a single definition:

  * the category weights printed in the docs are derived from CHECK_WEIGHTS;
  * the summary's group_scores roll up to exactly the overall score;
  * the worked example obeys the same arithmetic;
  * the retired deduction formula does not come back.
"""

import os
import re
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import generate_report as gr  # noqa: E402

PLUGIN = os.path.join(ROOT, "plugins", "ultimate-seo-geo", "skills", "ultimate-seo-geo")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def weights_table(text):
    section = text[text.index("### SEO Health Score Weights"):]
    section = section[:section.index("\n### ", 5)]
    return {m.group(1).strip(): int(m.group(2))
            for m in re.finditer(r"^\| ([^|]+?) \| (\d+)% \|", section, re.M)}


def expected_by_label():
    return {gr.CHECK_GROUPS[g]: share for g, share in gr.nominal_group_weights().items()}


# --- the documented weights are the script's ----------------------------------------


def test_nominal_group_weights_sum_to_100():
    assert sum(gr.nominal_group_weights().values()) == 100


@pytest.mark.parametrize("doc", [("references", "procedures", "02-full-site-audit.md"), ("AGENTS.md",)])
def test_documented_weights_match_check_weights(doc):
    assert weights_table(read(*doc)) == expected_by_label()


def test_chatgpt_instructions_list_the_same_weights():
    text = read("chatgpt", "instructions.txt")
    short = {"Technical": "technical", "Content/E-E-A-T": "content", "On-Page": "on_page", "Links": "links",
             "CWV": "performance", "Schema": "schema", "GEO": "geo", "Images": "images", "Local": "local"}
    found = {short[m.group(1)]: int(m.group(2))
             for m in re.finditer(r"(Technical|Content/E-E-A-T|On-Page|Links|CWV|Schema|GEO|Images|Local) (\d+)%", text)}
    assert found == gr.nominal_group_weights()


def test_documented_check_lists_match_the_script():
    section = read("references", "procedures", "02-full-site-audit.md")
    for group, label in gr.CHECK_GROUPS.items():
        row = re.search(rf"^\| {re.escape(label)} \| \d+% \| ([^|]+)\|", section, re.M)
        assert row, f"no weights row for {label}"
        listed = set(re.findall(r"[a-z_]+", row.group(1).split("(")[0]))
        weighted = {k for k in gr.CHECK_WEIGHTS if gr.CHECK_GROUP[k] == group}
        assert listed == weighted, f"{label}: docs list {sorted(listed)}, script weights {sorted(weighted)}"


# --- the summary rolls up to one number ----------------------------------------------


def fixture(**sections):
    return {"url": "https://ex.com/", "timestamp": "2026-09-16T10:00:00", "sections": sections}


FULL = fixture(
    security={"score": 90}, social={"score": 40}, robots={"status": 200, "sitemaps": ["s"], "ai_crawler_status": {}},
    broken_links={"summary": {"total": 50, "broken": 2}}, readability={"flesch_reading_ease": 45},
    content_quality={"score": 55}, schema_validation={"score": 30}, sitemap={"score": 100},
    onpage={"title": "t", "meta_description": "m", "h1": ["h"], "canonical": "https://ex.com/"},
    pagespeed={"error": "HTTP 429"},
)


def summary(d):
    return gr.build_summary(d, gr.calculate_overall_score(d))


def test_overall_is_the_share_weighted_mean_of_the_group_scores():
    scores = gr.calculate_overall_score(FULL)
    groups = gr.group_scores(scores)

    exact = sum(g["_value"] * g["_share"] for g in groups.values() if g["_value"] is not None) / 100
    published = sum(g["score"] * g["share"] for g in groups.values() if g["score"] is not None) / 100
    assert round(exact) == scores["overall"]
    assert abs(published - scores["overall"]) <= 1
    assert sum(g["share"] for g in groups.values()) == pytest.approx(100, abs=0.2)


def test_group_scores_in_the_summary():
    groups = summary(FULL)["group_scores"]

    assert groups["performance"] == {"label": "Core Web Vitals", "score": None, "share": 0.0,
                                     "status": "Not measured", "checks": ["pagespeed"],
                                     "unmeasured": ["pagespeed"]}
    assert groups["schema"]["score"] == 30 and groups["schema"]["status"] == "Gap"
    assert set(groups) == set(gr.CHECK_GROUPS)
    assert not any(k.startswith("_") for g in groups.values() for k in g)


def test_a_non_local_site_has_local_seo_not_applicable():
    groups = summary(fixture(security={"score": 90}, local_signals={"likely_local_business": False}))["group_scores"]

    assert groups["local"]["status"] == "Not applicable" and groups["local"]["score"] is None


def test_a_check_that_does_not_apply_is_not_reported_as_unmeasured():
    """python.org: hreflang (one language) was listed as an unmeasured Technical check."""
    d = fixture(security={"score": 90}, hreflang={"hreflang_tags_found": 0}, pagespeed={"error": "HTTP 429"})
    s = summary(d)

    assert "hreflang" not in s["unmeasured"]
    assert "hreflang" not in s["group_scores"]["technical"]["unmeasured"]
    assert "robots" in s["group_scores"]["technical"]["unmeasured"]  # never ran: a real gap
    assert s["group_scores"]["performance"]["unmeasured"] == ["pagespeed"]


def test_an_empty_run_scores_nothing():
    groups = summary(fixture())["group_scores"]

    assert all(g["score"] is None and g["share"] == 0 for g in groups.values())


# --- the worked example obeys the same arithmetic --------------------------------------------


def test_worked_example_rolls_up_to_its_headline():
    text = read("references", "audit-output-example.md")
    headline = int(re.search(r"## SEO Health Score: (\d+)/100", text).group(1))
    rows = re.findall(r"^\| ([^|]+?) \| (\d+)/100 \| ([\d.]+)% \| ([^|]+?) \|$", text, re.M)

    assert {label for label, *_ in rows} <= set(gr.CHECK_GROUPS.values())
    assert sum(float(share) for _, _, share, _ in rows) == pytest.approx(100, abs=0.2)
    assert round(sum(int(score) * float(share) for _, score, share, _ in rows) / 100) == headline
    for label, score, _, status in rows:
        score = int(score)
        expected = "Strong" if score >= 80 else "Needs work" if score >= 50 else "Gap"
        assert status == expected, f"{label}: {score}/100 is {expected}, example says {status}"


# --- the retired formula stays retired ------------------------------------------------------


RETIRED = re.compile(r"positive_signals|deficit_signals|Critical\s*[−-]15|Deduct:")
DOCS = ["SKILL.md", "AGENTS.md", "GEMINI.md", "chatgpt/instructions.txt", ".github/copilot-instructions.md",
        "agents/PARALLEL-AUDIT.md", "agents/README.md", "references/audit-output-example.md"]


@pytest.mark.parametrize("tree", [ROOT, PLUGIN], ids=["root", "plugin"])
def test_no_doc_teaches_the_retired_deduction_formula(tree):
    paths = [os.path.join(tree, p) for p in DOCS]
    procedures = os.path.join(tree, "references", "procedures")
    paths += [os.path.join(procedures, f) for f in os.listdir(procedures)]
    offenders = []
    for path in paths:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            offenders += [f"{os.path.relpath(path, tree)}: {line.strip()[:100]}"
                          for line in fh if RETIRED.search(line)]
    assert not offenders, "The Health Score comes only from generate_report.py:\n" + "\n".join(offenders)
