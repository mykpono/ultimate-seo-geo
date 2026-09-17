"""citability_checker.py: structural citability proxies, and the real pages that shaped them.

The first version was run against 13 real pages before commit and got four
things wrong. Each case below reproduces one in a small fixture:

  * paulgraham.com essays: prose in nested layout tables, paragraphs split by
    <br><br>, parsed as a single 11,802-word "table";
  * python.org and the Guardian's Technology front were scored as articles;
  * Wikipedia lost its H1 (the article <header> was stripped) and then its lead
    (the infobox table sits before the first paragraph in the HTML);
  * the SRE book put a table of contents and a series <h2> above the H1, and an
    RFC puts its summary under an "Abstract" heading; both read as "no lead".
"""

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import citability_checker as cc  # noqa: E402
import generate_report as gr  # noqa: E402


def sentence(n, word="word"):
    return " ".join([word] * (n - 1)) + " end."


def para(n):
    return f"<p>{sentence(n)}</p>"


def article(*sections, lead=40, h1="Guide", wrap="main", before_h1=""):
    body = "".join(f"<h2>{title}</h2>{content}" for title, content in sections)
    return (f"<html><body><nav>{sentence(50, 'menu')}</nav><{wrap}>{before_h1}<h1>{h1}</h1>"
            f"{para(lead) if lead else ''}{body}</{wrap}><footer>{sentence(40, 'foot')}</footer></body></html>")


GOOD = article(*[(f"Section {i}", para(60) + "<ul><li>one item here</li><li>two</li></ul>" + para(50))
                 for i in range(5)])


def result(html):
    return cc.analyze(html)


# --- scoring --------------------------------------------------------------------------


def test_a_well_structured_article_scores_high_with_no_findings():
    r = result(GOOD)

    assert r["applicable"] and r["issues"] == []
    assert r["score"] >= 90
    assert set(r["components"]) == set(cc.WEIGHTS)
    assert sum(cc.WEIGHTS.values()) == 100


def test_a_prose_wall_is_a_medium_finding():
    html = article(("Background", "".join(para(100) for _ in range(4))), ("Next", para(80)), ("More", para(80)))
    r = result(html)

    [wall] = [i for i in r["issues"] if "prose" in i["finding"]]
    assert wall["severity"] == "medium" and "Background (400 words)" in wall["evidence"]
    assert r["components"]["passage_shape"]["walls"] == 1


def test_a_long_section_broken_by_a_list_is_not_a_wall():
    html = article(("Steps", para(200) + "<ol><li>do this</li></ol>" + para(200)), ("Next", para(300)))

    assert result(html)["components"]["passage_shape"]["walls"] == 0


def test_missing_lead_is_a_low_finding_and_not_scored():
    """An opening of short lines (dateline, byline, captions) with no real paragraph in the first 60 words."""
    fragments = "".join(para(8) for _ in range(9))
    html = article(("S0", fragments + para(150)), *[(f"S{i}", para(150)) for i in range(1, 4)], lead=0)
    r = result(html)

    assert not r["lead"]["present"]
    assert "lead" not in r["components"]
    assert any(i["severity"] == "low" and "summary paragraph" in i["finding"] for i in r["issues"])


def test_long_paragraphs_and_skipped_levels():
    html = article(("A", para(130) + para(130) + para(20)), ("B", "<h4>Deep</h4>" + para(130)), ("C", para(60)))
    r = result(html)

    findings = " ".join(i["finding"] for i in r["issues"])
    assert "exceed 120 words" in findings and "Heading levels skip" in findings
    assert "H2 → H4" in r["components"]["heading_structure"]["skipped_levels"][0]


def test_every_finding_is_medium_or_lower():
    html = article(("Wall", para(500)), ("Deep", "<h5>x</h5>" + para(400)), lead=0)

    assert {i["severity"] for i in result(html)["issues"]} <= {"medium", "low"}


def test_long_openings_are_reported_not_scored():
    short = "<p>" + " ".join(sentence(12) for _ in range(15)) + "</p>"
    long_first = f"<p>{sentence(55)} Then more.</p>" + short
    html = article(("Slow", long_first), ("Fast", short), ("Other", short))
    r = result(html)

    assert r["long_openings"]["count"] == 1 and "Slow (55 words)" in r["long_openings"]["examples"][0]
    assert "section_openings" not in r["components"]


# --- not applicable ---------------------------------------------------------------------


def test_short_page_like_python_org_homepage_is_not_applicable():
    html = article(*[(f"Widget {i}", para(60)) for i in range(4)], lead=20)
    r = result(html)

    assert (r["applicable"], r["score"]) == (False, None)
    assert "not" not in r["reason"][:3] and "500 words" in r["reason"]


def test_section_front_like_the_guardian_technology_page_is_not_applicable():
    cards = "".join(f"<h3><a href='/a{i}'>{sentence(12, 'headline')}</a></h3><ul><li>{sentence(40, 'link')}</li></ul>"
                    for i in range(20))
    r = result(f"<html><body><main><h1>Technology</h1>{cards}</main></body></html>")

    assert r["applicable"] is False and "paragraphs" in r["reason"]


# --- real-page parsing cases ---------------------------------------------------------------


def test_paul_graham_nested_layout_tables_and_br_paragraphs():
    prose = "<br><br>".join(sentence(40) for _ in range(30))
    html = (f"<html><body><table><tr><td><img src=x></td><td><table><tr><td>"
            f"<font size=2 face=verdana>{prose}</font></td></tr></table></td></tr></table></body></html>")
    blocks, source, _ = cc.extract_blocks(html)
    r = result(html)

    assert source == "body+text"
    assert len([b for b in blocks if b["tag"] == "p"]) == 30
    assert r["applicable"] and r["components"]["passage_shape"]["walls"] == 1
    assert r["components"]["paragraph_length"]["score"] == 100


def test_a_data_table_is_not_unwrapped():
    table = "<table><tr><th>Plan</th><th>Price</th></tr>" + "".join(
        f"<tr><td>{sentence(160)}</td><td>9</td></tr>" for _ in range(1)) + "</table>"
    blocks, _, _ = cc.extract_blocks(f"<html><body><main><h1>x</h1>{table}{para(30)}</main></body></html>")

    assert [b["tag"] for b in blocks if b["level"] is None][0] == "table"


def test_wikipedia_h1_in_article_header_and_infobox_before_the_lead():
    infobox = "<table class='infobox'><tr><th>Kingdom</th><td>" + sentence(90) + "</td></tr></table>"
    html = ("<html><body><header>site chrome</header><main><header><h1>Photosynthesis</h1></header>"
            f"<div>From Wikipedia, the free encyclopedia</div>{infobox}{para(80)}"
            + "".join(f"<h2>S{i}</h2>{para(120)}" for i in range(4)) + "</main></body></html>")
    r = result(html)

    assert r["components"]["heading_structure"]["h1"] == 1
    assert r["lead"]["present"]


def test_sre_book_table_of_contents_above_the_h1_is_ignored():
    toc = "<h2>Chapter 3 - Embracing Risk</h2><ol>" + "".join(f"<li>{sentence(10)}</li>" for _ in range(20)) + "</ol>"
    html = article(*[(f"S{i}", para(120)) for i in range(4)], lead=0, before_h1=toc).replace(
        "<h1>Guide</h1>", f"<h1>Embracing Risk</h1><p>Written by A. Author</p>{para(180)}")
    r = result(html)

    assert r["lead"]["present"]
    assert r["sections"] == 4  # the TOC's "Chapter 3" heading is not a section


def test_an_h1_inside_an_article_header_still_anchors_the_page():
    """Stripping <header> inside <main> removed the H1 block, so a series heading above it became a section."""
    series = "<h2>Part of a series</h2><ol>" + "".join(f"<li>{sentence(10)}</li>" for _ in range(8)) + "</ol>"
    html = ("<html><body><main>" + series + "<header><h1>Title</h1></header>" + para(80)
            + "".join(f"<h2>S{i}</h2>{para(150)}" for i in range(4)) + "</main></body></html>")

    assert result(html)["sections"] == 4


def test_rfc_summary_under_an_abstract_heading_is_a_lead():
    html = article(("Abstract", para(56)), *[(f"{i}. Section", para(150)) for i in range(4)], lead=0)

    assert result(html)["lead"]["present"]


def test_h1_outside_main_still_counts():
    html = GOOD.replace("<main><h1>Guide</h1>", "<h1>Guide</h1><main>")

    assert result(html)["components"]["heading_structure"]["h1"] == 1


# --- report integration --------------------------------------------------------------------


def report_data(citability):
    return {"url": "https://ex.com/", "sections": {"security": {"score": 90}, "citability": citability}}


def test_the_report_shows_it_under_geo_but_does_not_weight_it():
    good = report_data(result(GOOD))
    bad = report_data(result(article(("Wall", para(900)), ("B", para(80)), lead=0)))
    good_scores, bad_scores = gr.calculate_overall_score(good), gr.calculate_overall_score(bad)

    assert "citability" not in gr.CHECK_WEIGHTS
    assert good_scores["overall"] == bad_scores["overall"]
    assert gr.CHECK_GROUP["citability"] == "geo"
    summary = gr.build_summary(bad, bad_scores)
    assert summary["categories"]["citability"]["score"] < 80
    assert any(f["section"] == "citability" and f["severity"] == "medium" for f in summary["findings"])


def test_not_applicable_in_the_report():
    data = report_data(result("<html><body><main><h1>Home</h1><p>Welcome to our site.</p></main></body></html>"))
    scores = gr.calculate_overall_score(data)
    summary = gr.build_summary(data, scores)

    assert summary["categories"]["citability"]["status"] == "Not applicable"
    assert summary["categories"]["citability"]["score"] is None
    assert "Not an article-style page" in gr._check_panels(data)["citability"]


def test_the_report_runs_it_on_the_fetched_page():
    import inspect

    assert '("citability", "citability_checker.py", [html_path])' in inspect.getsource(gr.collect_data)


# --- CLI -------------------------------------------------------------------------------------


def test_cli_on_a_saved_file(tmp_path):
    page = tmp_path / "page.html"
    page.write_text(GOOD, encoding="utf-8")
    out = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "citability_checker.py"), str(page), "--json"],
                         capture_output=True, text=True)

    assert out.returncode == 0
    assert json.loads(out.stdout)["applicable"] is True


def test_cli_requires_input():
    out = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "citability_checker.py")],
                         capture_output=True, text=True)

    assert out.returncode == 2
