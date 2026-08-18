"""Tests for JSON-LD extraction and placeholder detection.

Each test below fails against the code as it stood before the accompanying fix.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from validate_schema import validate_jsonld  # noqa: E402


def page(script_tag_attrs, payload):
    return (
        f"<html><head><script {script_tag_attrs}>"
        f"{json.dumps(payload)}"
        f"</script></head><body></body></html>"
    )


VALID = {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "A perfectly ordinary headline",
}

BROKEN = {"@context": "https://schema.org"}  # no @type


# --- extraction: `type` is rarely the only attribute ------------------------

@pytest.mark.parametrize(
    "attrs",
    [
        'type="application/ld+json"',
        'type="application/ld+json" id="schema"',
        'id="schema" type="application/ld+json"',
        'type="application/ld+json" class="yoast-schema-graph"',
        "type='application/ld+json' data-nscript='beforeInteractive'",
        'type = "application/ld+json"',
    ],
)
def test_blocks_are_extracted_regardless_of_other_attributes(attrs):
    """A missed block reports zero errors, which reads as a clean site."""
    errors = validate_jsonld(page(attrs, BROKEN))

    assert any("Missing @type" in e for e in errors), (
        f"schema in <script {attrs}> was not extracted, so its defect was "
        f"invisible; got {errors}"
    )


def test_valid_schema_still_produces_no_errors():
    assert validate_jsonld(page('type="application/ld+json" id="x"', VALID)) == []


def test_non_jsonld_script_tags_are_ignored():
    html = '<html><script type="text/javascript">var x = 1;</script></html>'

    assert validate_jsonld(html) == []


# --- @graph members inherit the wrapper's @context --------------------------

def test_graph_members_do_not_each_need_a_context():
    """The Yoast/WordPress shape: one wrapper context, many member nodes."""
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "name": "Example"},
            {"@type": "WebSite", "name": "Example"},
            {"@type": "WebPage", "name": "Home"},
        ],
    }

    errors = validate_jsonld(page('type="application/ld+json"', graph))

    assert errors == [], f"graph members were each asked for @context: {errors}"


def test_graph_wrapper_without_context_is_still_reported_once():
    graph = {"@graph": [{"@type": "Organization", "name": "Example"}]}

    errors = validate_jsonld(page('type="application/ld+json"', graph))

    assert [e for e in errors if "Missing @context" in e] == [
        "Block 1: Missing @context"
    ], errors


# --- placeholder detection must not fire on ordinary prose ------------------

@pytest.mark.parametrize(
    "headline",
    [
        "How to Replace a Faucet",
        "When to replace your roof",
        "Replace vs. repair: a buyer's guide",
    ],
)
def test_ordinary_prose_containing_replace_is_not_a_placeholder(headline):
    """Placeholder findings are critical and exit 2, so a false one blocks."""
    payload = dict(VALID, headline=headline)

    errors = validate_jsonld(page('type="application/ld+json"', payload))

    assert errors == [], f"'{headline}' was flagged as placeholder text: {errors}"


@pytest.mark.parametrize(
    "value",
    ["[REPLACE with your business name]", "REPLACE_ME", "REPLACE WITH YOUR URL"],
)
def test_real_placeholder_scaffolding_is_still_caught(value):
    payload = dict(VALID, headline=value)

    errors = validate_jsonld(page('type="application/ld+json"', payload))

    assert any("placeholder" in e.lower() for e in errors), errors


def test_bracketed_placeholders_still_caught():
    payload = dict(VALID, publisher={"@type": "Organization", "name": "[Business Name]"})

    errors = validate_jsonld(page('type="application/ld+json"', payload))

    assert any("placeholder" in e.lower() for e in errors), errors


# --- schema status correctness (Task 1) -------------------------------------
# Google retired several rich-result *features* without retiring the underlying
# schema.org *types*. Conflating the two made the validator recommend deleting
# valid markup, and made Dataset hard-block edits. Each test below fails against
# the code as it stood before the accompanying fix.

from validate_schema import _is_critical  # noqa: E402

# Rich result gone, schema.org type still valid — must never block, never
# advise removal. "Quiz" is the real @type behind Google's "practice problem"
# feature; "PracticeProblem"/"PracticeProblems" are not schema.org types at all.
KEEP_TYPES = ["FAQPage", "HowTo", "Quiz", "Dataset"]

# Truly retired — Google no longer processes these, so blocking is correct.
RETIRED_TYPES = ["SpecialAnnouncement", "EnergyConsumptionDetails"]


def _errors_for(schema_type):
    return validate_jsonld(page(
        'type="application/ld+json"',
        {"@context": "https://schema.org", "@type": schema_type, "name": "A real name"},
    ))


@pytest.mark.parametrize("schema_type", KEEP_TYPES)
def test_keep_types_are_informational_only(schema_type):
    """Valid-but-no-rich-result types must not be critical (exit code 2)."""
    errors = _errors_for(schema_type)
    assert errors, f"{schema_type} should still produce an informational note"
    assert all(e.startswith("[info]") for e in errors), errors
    assert not any(_is_critical(e) for e in errors), errors


@pytest.mark.parametrize("schema_type", KEEP_TYPES)
def test_keep_types_advise_keeping(schema_type):
    """§19 hard rule 10: the note must tell the user to keep the markup.

    Asserted positively on purpose. These notes legitimately contain the words
    "removed"/"retired" when describing what Google did to the *rich result*
    ("Google removed HowTo rich results", "do not remove"), so a bare substring
    ban cannot separate description from advice.
    """
    joined = " ".join(_errors_for(schema_type)).lower()
    assert "keep" in joined, joined
    assert "still valid" in joined or "still supported" in joined, joined


@pytest.mark.parametrize("schema_type", KEEP_TYPES)
def test_keep_types_survive_retired_keyword_matching(schema_type):
    """The [info] prefix short-circuits _is_critical() before keyword matching.

    Guards the Dataset/Quiz regression specifically: a note may describe a
    retirement without the message itself being treated as critical.
    """
    for err in _errors_for(schema_type):
        assert err.startswith("[info]")
        assert _is_critical(err) is False


def test_faqpage_has_no_government_healthcare_restriction():
    """The Aug 2023 gov/health restriction was superseded on May 7, 2026."""
    joined = " ".join(_errors_for("FAQPage")).lower()
    assert "government" not in joined and "healthcare" not in joined, joined
    assert "verify site qualifies" not in joined, joined


def test_dataset_does_not_block_edits():
    """Dataset was never retired — it is scope-limited to Dataset Search."""
    assert not any(_is_critical(e) for e in _errors_for("Dataset"))


@pytest.mark.parametrize("schema_type", RETIRED_TYPES)
def test_truly_retired_types_still_block(schema_type):
    """The fix must not blunt detection of genuinely retired types."""
    assert any(_is_critical(e) for e in _errors_for(schema_type))


@pytest.mark.parametrize("bogus", ["PracticeProblem", "PracticeProblems"])
def test_nonexistent_practice_problem_types_are_not_flagged(bogus):
    """Neither spelling is a real schema.org type; both 404. Only Quiz is real."""
    assert not any(_is_critical(e) for e in _errors_for(bogus))


# --- visible-HTML parity for FAQ answers (Task 2.4) -------------------------
# FAQ answer text present in JSON-LD but absent from the rendered HTML satisfies
# a parser while users and AI crawlers see nothing. Comparison must survive the
# tag/entity/whitespace differences that JSON-LD routinely carries.

import subprocess  # noqa: E402

import faq_parity  # noqa: E402

ANSWER = "Standard shipping takes three to five business days after dispatch."


def faq_page(answer_text, rendered=None):
    """FAQPage JSON-LD, optionally with the answer also rendered in the body."""
    payload = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{
            "@type": "Question",
            "name": "How long does shipping take?",
            "acceptedAnswer": {"@type": "Answer", "text": answer_text},
        }],
    }
    body = f"<h1>Shipping</h1><p>{rendered}</p>" if rendered else "<h1>Shipping</h1>"
    return (
        f'<html><head><script type="application/ld+json">{json.dumps(payload)}'
        f"</script></head><body>{body}</body></html>"
    )


def parity_errors(content):
    return [e for e in validate_jsonld(content, check_html_parity=True)
            if "not in the rendered HTML" in e]


def test_parity_match_does_not_flag():
    assert parity_errors(faq_page(ANSWER, rendered=ANSWER)) == []


def test_parity_miss_flags():
    errors = parity_errors(faq_page(ANSWER))
    assert len(errors) == 1
    assert "How long does shipping take?" in errors[0]


def test_parity_finding_is_never_blocking():
    """validate_schema.py has no High vocabulary; parity must stay [info]."""
    for err in parity_errors(faq_page(ANSWER)):
        assert err.startswith("[info]")
        assert _is_critical(err) is False


def test_parity_survives_tags_entities_and_whitespace():
    """JSON-LD carries <p>, entities and &nbsp; the rendered DOM does not."""
    marked_up = f"<p>{ANSWER.replace(' ', '&nbsp;', 1)}</p>"
    rendered = f"  {ANSWER}\n\n  "
    assert parity_errors(faq_page(marked_up, rendered=rendered)) == []


def test_parity_is_containment_not_equality():
    """The answer inside a longer paragraph is present, not missing."""
    rendered = f"We ship worldwide. {ANSWER} Tracking is included."
    assert parity_errors(faq_page(ANSWER, rendered=rendered)) == []


def test_parity_ignores_jsonld_self_containment():
    """Script contents are stripped, so markup cannot 'contain' its own answer."""
    assert parity_errors(faq_page(ANSWER)) != []


def test_parity_off_by_default():
    """Existing callers must be unaffected."""
    assert [e for e in validate_jsonld(faq_page(ANSWER))
            if "not in the rendered HTML" in e] == []


def test_short_answers_are_skipped():
    """Very short strings match incidentally; containment would be meaningless."""
    assert parity_errors(faq_page("Yes.")) == []


@pytest.mark.parametrize("ext", [".jsx", ".tsx", ".vue", ".svelte", ".php"])
def test_framework_files_are_not_parity_checked(tmp_path, ext):
    """Answer text legitimately lives in props, a .map() or a CMS fetch."""
    target = tmp_path / f"component{ext}"
    target.write_text(faq_page(ANSWER), encoding="utf-8")
    out = subprocess.run(
        [sys.executable,
         os.path.join(os.path.dirname(__file__), "..", "scripts", "validate_schema.py"),
         str(target), "--json"],
        capture_output=True, text=True,
    )
    assert "not in the rendered HTML" not in out.stdout, out.stdout


def test_html_files_are_parity_checked(tmp_path):
    """The same content in a .html file must flag — proves the gate, not silence."""
    target = tmp_path / "page.html"
    target.write_text(faq_page(ANSWER), encoding="utf-8")
    out = subprocess.run(
        [sys.executable,
         os.path.join(os.path.dirname(__file__), "..", "scripts", "validate_schema.py"),
         str(target), "--json"],
        capture_output=True, text=True,
    )
    assert "not in the rendered HTML" in out.stdout, out.stdout


def test_normalize_collapses_entities_and_case():
    assert faq_parity.normalize("<p>Hello&nbsp;&amp;  WORLD</p>") == "hello & world"
