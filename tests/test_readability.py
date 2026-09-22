"""Readability advice must come from the page it describes.

Found auditing alwayshired.com/resources/sdr-salary-guide (2026-09-21): the one
30-word sentence on the page was discarded as a "keyword list", so the script
fell back to two canned "homepage hero" rewrites on a salary guide; the
suggested rewrite split "described by that publisher" after "that"; and every
heading, list item and stat card counted as a paragraph (69 at 0.5 sentences).
Each test below fails against the code as it stood before the fix, except
test_easy_text_gets_no_rewrites, which guards the other direction.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import readability  # noqa: E402

needs_bs4 = pytest.mark.skipif(not readability.HAS_BS4, reason="needs BeautifulSoup")

LONG_REAL_SENTENCE = (
    "Where a source is listed, it supports only the specific factual context "
    "described by that publisher; organizations should validate benchmarks and "
    "live product terms for their own market and plan."
)

KEYWORD_DUMP = (
    "seo agency london seo services cheap seo best seo company uk seo consultant "
    "local seo expert seo audit link building technical seo content marketing ppc "
    "agency web design digital marketing agency london."
)


# --- long real sentences are rewritten, keyword dumps are not ---------------

def test_a_long_real_sentence_is_not_navigation_noise():
    assert not readability.is_navigation_noise(LONG_REAL_SENTENCE)


def test_a_keyword_dump_is_navigation_noise():
    assert readability.is_navigation_noise(KEYWORD_DUMP)


def test_the_long_sentence_on_the_page_is_the_one_rewritten():
    text = (
        "Compensation is more than a salary figure. " + LONG_REAL_SENTENCE
        + " Review each offer's terms carefully."
    )
    rewrites = readability.analyze_readability(text)["sentence_rewrites"]

    assert [r["current"] for r in rewrites] == [LONG_REAL_SENTENCE]
    assert rewrites[0]["current_word_count"] == 30


# --- the rewrite itself ------------------------------------------------------

def test_rewrite_splits_at_the_semicolon_not_after_that():
    rewrite = readability.suggest_sentence_rewrite(LONG_REAL_SENTENCE)

    assert rewrite == (
        "Where a source is listed, it supports only the specific factual context "
        "described by that publisher. Organizations should validate benchmarks and "
        "live product terms for their own market and plan."
    )


def test_rewrite_splits_before_but_after_a_comma():
    # developer.mozilla.org/en-US/docs/Web/HTML/Element/p
    sentence = (
        "Paragraphs are usually represented in visual media as blocks of text "
        "separated from adjacent blocks by blank lines and/or first-line indentation, "
        "but HTML paragraphs can be any structural grouping of related content, "
        "such as images or form fields."
    )
    assert readability.suggest_sentence_rewrite(sentence) == (
        "Paragraphs are usually represented in visual media as blocks of text "
        "separated from adjacent blocks by blank lines and/or first-line indentation. "
        "HTML paragraphs can be any structural grouping of related content, "
        "such as images or form fields."
    )


@pytest.mark.parametrize(
    "sentence",
    [
        # en.wikipedia.org/wiki/Sales_development_representative: "and" joins
        # nouns, and the commas separate list items.
        "Once an SDR gathers enough information to meet the criteria in the SQL "
        "definition, and the lead agrees to take the next step in the sales process, "
        "an SDR will schedule the next meeting between the lead and a salesperson "
        "and hand ownership off to that salesperson, who then conducts the rest of "
        "the sales process.",
        "Throughout the 1980s and 1990s, it has been one of the key organizational "
        "strategies for most famous B2B technology companies, including Sun "
        "Microsystems, and Cisco, which built large inside sales teams of their own.",
        # posthog.com: ", but not" starts no clause, and ", but it doesn't" sits
        # inside an "either ... or".
        "If people are repeatedly using your product, but not willing to pay, it's "
        "either (i) they have a bad problem and wish your product could solve it, "
        "but it doesn't or (ii) the problem is there but not very high value.",
        "If people are repeatedly using your product, but not willing to pay, it is "
        "either because they have a bad problem and wish your product could solve it "
        "or because the problem is not very high value.",
    ],
)
def test_no_split_without_a_certain_sentence_boundary(sentence):
    suggestion = readability.suggest_sentence_rewrite(sentence)

    assert suggestion.startswith("Split this into two or three sentences")
    assert str(len(sentence.split())) in suggestion


# --- no canned advice --------------------------------------------------------

def test_no_page_ever_gets_the_canned_homepage_rewrites():
    # Short sentences full of long words: hard to read, nothing over 25 words.
    text = " ".join(
        [
            "Compensation variability materially affects organizational attractiveness.",
            "Territory configuration influences opportunity availability considerably.",
            "Quota attainment probability depends on enablement infrastructure.",
            "Remuneration philosophy determines geographical differentiation.",
        ]
    )
    result = readability.analyze_readability(text)

    assert result["flesch_reading_ease"] < 40
    rewrites = result["sentence_rewrites"]
    assert rewrites, "hard vocabulary should still get page-specific guidance"
    for item in rewrites:
        assert item["current"] in text
        assert "hero" not in item["suggested"].lower()
        assert isinstance(item["current_word_count"], int)


def test_easy_text_gets_no_rewrites():
    text = "The cat sat on the mat. It was a warm day. We had tea in the sun."
    assert readability.analyze_readability(text)["sentence_rewrites"] == []


# --- paragraphs are prose, not every block element ---------------------------

@needs_bs4
def test_headings_list_items_and_stat_cards_are_not_paragraphs():
    html = (
        "<main><h1>SDR Salary Guide</h1>"
        "<h2>How to Read an SDR Offer</h2>"
        "<p>Compensation is more than a salary figure. Compare the fixed base and "
        "the variable opportunity before you decide.</p>"
        "<div>$60,000</div><div>Median base salary</div>"
        "<h3>Health &amp; wellness</h3>"
        "<ul><li>Medical, dental, and vision coverage</li><li>Mental-health support</li></ul>"
        "<p>OTE is a target, not a guarantee for anyone. Ask what performance and "
        "plan conditions are needed to earn it.</p></main>"
    )
    result = readability.analyze_readability(readability.extract_text(html))

    assert result["paragraph_count"] == 2
    assert result["avg_paragraph_length"] == 2.0


@needs_bs4
def test_a_wall_of_text_among_headings_is_still_flagged():
    wall = " ".join(f"This is sentence number {n} of one very long paragraph." for n in range(8))
    html = (
        "<main><h2>Section one</h2><h2>Section two</h2><h2>Section three</h2>"
        f"<p>{wall}</p></main>"
    )
    result = readability.analyze_readability(readability.extract_text(html))

    assert result["paragraph_count"] == 1
    assert result["avg_paragraph_length"] == 8.0
    assert any("paragraph length" in issue for issue in result["issues"])
