"""Three crashes and one false finding, found by running v1.12.6 on a live site.

Each test below fails against the code as it stood before the accompanying fix.

  * ``broken_links.py``   -- every non-redirected link carries ``"redirect": None``,
    so ``.get("redirect", {})`` returned None rather than the default and the
    crawl aborted on the first healthy link.
  * ``validate_schema.py`` / ``parse_html.py`` / ``article_seo.py`` -- ``@type``
    may be a list. Testing it against a dict of retired types raised
    ``TypeError: unhashable type: 'list'``, dropping the whole page from the audit.
  * ``parse_html.py`` / ``article_seo.py`` -- a JSON-LD block may hold a top-level
    *array* of nodes. Both called ``.get()`` straight on ``json.loads()`` output and
    raised ``AttributeError`` on the array form; ``validate_schema.py`` already
    branched on it correctly.
  * ``faq_parity.py`` / ``local_signals_checker.py`` -- the same list ``@type``, in two
    more consumers that never raised: FAQ parity skipped every multi-typed FAQ page,
    and a multi-typed LocalBusiness was told at high severity to add the schema it
    already had.
  * ``internal_links.py`` -- link extraction stripped trailing slashes, the crawler
    then requested a URL the page never linked to, and the site's canonical 301
    back was reported as an internal link pointing to a redirect.
  * ``entity_checker.py`` / ``generate_report.py`` -- the same list ``@type``, one
    layer out. Neither crashed: they compared the raw value against a tuple or
    stringified it, matched nothing, and returned a quietly empty result.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from bs4 import BeautifulSoup  # noqa: E402

import article_seo  # noqa: E402
import faq_parity  # noqa: E402
import local_signals_checker  # noqa: E402
import entity_checker  # noqa: E402
import generate_report  # noqa: E402
import parse_html  # noqa: E402
from broken_links import is_redirect_chain  # noqa: E402
from internal_links import extract_internal_links  # noqa: E402
import validate_schema  # noqa: E402
from validate_schema import validate_jsonld  # noqa: E402


# --- broken_links: a None redirect is not an empty dict ---------------------

def test_healthy_link_is_not_a_redirect_chain():
    """check_link() seeds every result with redirect=None."""
    assert is_redirect_chain({"url": "https://e.com/", "redirect": None}) is False


def test_missing_redirect_key_is_not_a_redirect_chain():
    assert is_redirect_chain({"url": "https://e.com/"}) is False


@pytest.mark.parametrize("hops,expected", [(1, False), (2, True), (3, True)])
def test_redirect_chain_needs_more_than_one_hop(hops, expected):
    result = {"redirect": {"from": "a", "to": "b", "hops": hops}}
    assert is_redirect_chain(result) is expected


# --- @type may be a list ----------------------------------------------------

def _page(type_value, extra=""):
    return (
        '<html><head><script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": ' + type_value + extra + "}"
        "</script></head><body></body></html>"
    )


MULTI = '["WebPage", "FAQPage"]'


def test_validate_schema_survives_list_type():
    errors = validate_jsonld(_page(MULTI))
    assert not any("Missing @type" in e for e in errors)


def test_validate_schema_still_flags_a_retired_type_inside_a_list():
    errors = validate_jsonld(_page('["WebPage", "ClaimReview"]'))
    assert any("ClaimReview" in e and "retired" in e for e in errors)


def test_validate_schema_reports_no_rich_results_type_inside_a_list():
    """The note text carries the finding; it does not repeat the type name."""
    errors = validate_jsonld(_page(MULTI))
    note = validate_schema.NO_RICH_RESULTS_TYPES["FAQPage"]
    assert any(e.startswith("[info]") and note in e for e in errors)


def test_parse_html_survives_list_type():
    blocks = parse_html.parse_html(_page('["WebPage", "ClaimReview"]'))["schema"]
    assert blocks[0]["@type"] == ["WebPage", "ClaimReview"]
    assert blocks[0]["status"] == "deprecated"
    assert "ClaimReview" in blocks[0]["note"]


def test_parse_html_list_type_precedence_matches_single_type():
    """A retired type anywhere in the list outranks a no-rich-results one."""
    blocks = parse_html.parse_html(_page('["FAQPage", "ClaimReview"]'))["schema"]
    assert blocks[0]["status"] == "deprecated"


def test_parse_html_plain_list_type_stays_active():
    blocks = parse_html.parse_html(_page('["WebPage", "Article"]'))["schema"]
    assert blocks[0]["status"] == "active"


def test_article_seo_survives_list_type():
    soup = BeautifulSoup(_page(MULTI), "html.parser")
    blocks = article_seo.extract_structured_data(soup)
    assert blocks[0]["status"] == "no_rich_results"
    assert "FAQPage" in blocks[0]["note"]


# --- internal_links: don't invent the redirect you then report --------------

DOMAIN = "example.com"
PAGE = "https://example.com/"


def _links(*hrefs):
    html = "<html><body>" + "".join(
        f'<a href="{h}">link</a>' for h in hrefs
    ) + "</body></html>"
    return extract_internal_links(html, PAGE, DOMAIN)


def test_trailing_slash_is_preserved():
    """The URL reported is the one the page actually linked to."""
    assert [l["url"] for l in _links("/gallery/")] == ["https://example.com/gallery/"]


def test_slashless_href_stays_slashless():
    assert [l["url"] for l in _links("/gallery")] == ["https://example.com/gallery"]


def test_slash_variants_still_deduplicate():
    assert len(_links("/gallery/", "/gallery")) == 1


def test_localised_path_keeps_its_slash():
    assert [l["url"] for l in _links("/es/galeria/")] == [
        "https://example.com/es/galeria/"
    ]


def test_root_href_is_requestable():
    assert [l["url"] for l in _links("https://example.com")] == ["https://example.com/"]


def test_query_and_fragment_are_still_dropped():
    assert [l["url"] for l in _links("/about/?utm_source=x#top")] == [
        "https://example.com/about/"
    ]


# --- a JSON-LD block may be a top-level array -------------------------------

ARRAY = (
    '<html><head><script type="application/ld+json">'
    '[{"@context": "https://schema.org", "@type": "Article", "headline": "x"},'
    ' {"@context": "https://schema.org", "@type": "BreadcrumbList"}]'
    "</script></head><body></body></html>"
)


def test_parse_html_survives_a_top_level_array():
    blocks = parse_html.parse_html(ARRAY)["schema"]
    assert [b["@type"] for b in blocks] == ["Article", "BreadcrumbList"]
    assert all(b["status"] == "active" for b in blocks)


def test_article_seo_survives_a_top_level_array():
    blocks = article_seo.extract_structured_data(BeautifulSoup(ARRAY, "html.parser"))
    assert [b["@type"] for b in blocks] == ["Article", "BreadcrumbList"]


def test_retired_type_buried_in_an_array_is_still_flagged():
    html = (
        '<html><head><script type="application/ld+json">'
        '[{"@type": "Article"}, {"@type": "ClaimReview"}]'
        "</script></head><body></body></html>"
    )
    blocks = parse_html.parse_html(html)["schema"]
    assert [b["status"] for b in blocks] == ["active", "deprecated"]


def test_validate_schema_still_validates_every_array_member():
    html = (
        '<html><head><script type="application/ld+json">'
        '[{"@context": "https://schema.org", "@type": "Article"}, {"@type": "Thing"}]'
        "</script></head><body></body></html>"
    )
    errors = validate_jsonld(html)
    assert any("Missing @context" in e for e in errors)


@pytest.mark.parametrize("payload", ["[]", '"just a string"', "[1, 2, 3]", "null"])
def test_object_free_block_is_reported_not_dropped(payload):
    """Valid JSON carrying no nodes is surfaced, not silently swallowed."""
    html = (
        '<html><head><script type="application/ld+json">'
        + payload
        + "</script></head><body></body></html>"
    )
    blocks = parse_html.parse_html(html)["schema"]
    assert [b["error"] for b in blocks] == ["not_an_object"]

    seo_blocks = article_seo.extract_structured_data(BeautifulSoup(html, "html.parser"))
    assert [b["error"] for b in seo_blocks] == ["not_an_object"]


def test_invalid_json_still_reports_invalid_json():
    html = (
        '<html><head><script type="application/ld+json">{not json'
        "</script></head><body></body></html>"
    )
    assert parse_html.parse_html(html)["schema"][0]["error"] == "invalid_json"


# --- a list @type must not silently empty out its consumers ------------------

def _entities(type_value):
    html = (
        '<html><head><script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": ' + type_value + ','
        ' "name": "Acme", "sameAs": ["https://x.com/acme"]}'
        "</script></head><body></body></html>"
    )
    return entity_checker.extract_entities_from_schema(
        BeautifulSoup(html, "html.parser")
    )


def test_entity_survives_list_type():
    """A multi-typed Organization is an entity, not a non-entity."""
    entities = _entities('["LocalBusiness", "Organization"]')
    assert [e["name"] for e in entities] == ["Acme"]


def test_entity_type_is_the_matched_name_not_the_list():
    """check_nap_consistency() does `e["type"] in (...)` and prints it."""
    entity = _entities('["LocalBusiness", "Organization"]')[0]
    assert entity["type"] == "LocalBusiness"


def test_entity_string_type_is_unchanged():
    assert [e["type"] for e in _entities('"Organization"')] == ["Organization"]


def test_non_entity_list_type_is_still_ignored():
    assert _entities('["WebPage", "BreadcrumbList"]') == []


def test_entity_survives_a_top_level_array():
    html = (
        '<html><head><script type="application/ld+json">'
        '[{"@type": "WebPage"}, {"@type": ["NewsMediaOrganization", "Organization"],'
        ' "name": "Acme"}]'
        "</script></head><body></body></html>"
    )
    entities = entity_checker.extract_entities_from_schema(
        BeautifulSoup(html, "html.parser")
    )
    assert [e["type"] for e in entities] == ["Organization"]


def _publisher_fix_titles(type_value):
    """Titles of the fixes build_environment_fixes() raises for a publisher."""
    data = {
        "environment": {},
        "sections": {
            "onpage": {"schema": [{"@type": type_value}]},
            "preferred_sources": {"implemented": False, "integration": {}},
        },
    }
    return [f["title"] for f in generate_report.build_environment_fixes(data)]


PREFERRED_SOURCES_FIX = "No preferred sources opt-in found"


def test_publisher_gate_survives_list_type():
    """str() on the list matched nothing, so the finding never fired."""
    assert PREFERRED_SOURCES_FIX in _publisher_fix_titles(["NewsArticle", "Article"])


def test_publisher_gate_string_type_is_unchanged():
    assert PREFERRED_SOURCES_FIX in _publisher_fix_titles("NewsArticle")


def test_non_publisher_is_still_not_gated_in():
    assert PREFERRED_SOURCES_FIX not in _publisher_fix_titles(["WebPage", "Article"])


# --- faq_parity: a page that is both a WebPage and an FAQPage ---------------

FAQ_ANSWER = "Yes, we deliver across the metro area on the same working day."


def _faq(type_value, question_type="Question"):
    return {
        "@context": "https://schema.org",
        "@type": type_value,
        "mainEntity": [{
            "@type": question_type,
            "name": "Do you deliver same day?",
            "acceptedAnswer": {"@type": "Answer", "text": FAQ_ANSWER},
        }],
    }


def test_multi_typed_faqpage_is_still_checked_for_parity():
    """["WebPage", "FAQPage"] is the ordinary shape and was skipped entirely."""
    missing = faq_parity.missing_answers(
        _faq(["WebPage", "FAQPage"]), faq_parity.visible_text("<p>Nothing here.</p>")
    )
    assert missing == ["Do you deliver same day?"]


def test_multi_typed_faqpage_with_visible_answer_reports_nothing():
    missing = faq_parity.missing_answers(
        _faq(["WebPage", "FAQPage"]),
        faq_parity.visible_text(f"<p>{FAQ_ANSWER}</p>"),
    )
    assert missing == []


def test_multi_typed_question_node_is_still_read():
    missing = faq_parity.missing_answers(
        _faq("FAQPage", question_type=["Question", "Thing"]),
        faq_parity.visible_text("<p>Nothing here.</p>"),
    )
    assert missing == ["Do you deliver same day?"]


def test_non_faq_page_is_still_skipped():
    assert faq_parity.missing_answers(_faq(["WebPage", "AboutPage"]), "") == []


# --- local_signals_checker: a multi-typed LocalBusiness is not missing ------

def test_list_type_localbusiness_is_detected():
    html = '<script type="application/ld+json">{"@type": ["LocalBusiness", "Store"]}</script>'
    assert local_signals_checker._declares_type(html, "LocalBusiness") is True


def test_string_type_localbusiness_still_detected():
    html = '<script type="application/ld+json">{"@type": "LocalBusiness"}</script>'
    assert local_signals_checker._declares_type(html, "LocalBusiness") is True


def test_absent_type_is_not_detected():
    html = '<script type="application/ld+json">{"@type": ["Store", "Organization"]}</script>'
    assert local_signals_checker._declares_type(html, "LocalBusiness") is False


@pytest.mark.parametrize("payload", [
    '{"@type":["LocalBusiness","Store"]}',
    '{"@type": [ "Store" , "LocalBusiness" ]}',
    '{"@type":"LocalBusiness"}',
])
def test_spacing_variants_all_detected(payload):
    assert local_signals_checker._declares_type(payload, "LocalBusiness") is True
