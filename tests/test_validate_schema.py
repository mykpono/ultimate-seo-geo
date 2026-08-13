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
