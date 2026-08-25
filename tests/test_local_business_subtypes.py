"""A LocalBusiness subtype *is* a LocalBusiness.

`local_signals_checker.py` matched the exact string "LocalBusiness" and nothing
else, so a restaurant, dentist or bookshop carrying correct, specific schema was
told at **high** severity to add the markup it already had — the worst kind of
finding, because it reads as authoritative and sends the user to break a working
page. `maps_checker.py` had known the subtype list all along; the two scripts
simply disagreed about what counts as a local business.

The taxonomy now lives once in `scripts/jsonld.py` and both scripts read it.

Same defect family as `test_audit_script_crashes.py`: a script assuming the one
shape it happened to see first. This one never raised — it returned a confident
wrong answer.
"""

import json
import os
import re
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import jsonld  # noqa: E402
import local_signals_checker  # noqa: E402
import maps_checker  # noqa: E402

DOC = os.path.join(ROOT, "references", "local-seo.md")


def _page(type_value, *, tel=True, address=True):
    """A page with real local indicators and one JSON-LD block."""
    block = json.dumps({"@context": "https://schema.org", "@type": type_value,
                        "name": "Acme"})
    parts = [f'<script type="application/ld+json">{block}</script>']
    if tel:
        parts.append('<a href="tel:+15555550123">Call us</a>')
    if address:
        parts.append('<span itemprop="streetAddress">1 Main St</span>')
    return "<html><body>" + "".join(parts) + "</body></html>"


# --- the taxonomy itself ----------------------------------------------------

def test_localbusiness_itself_is_in_the_set():
    assert "localbusiness" in jsonld.LOCAL_BUSINESS_TYPES


def test_set_is_lowercase_for_case_insensitive_matching():
    assert all(t == t.lower() for t in jsonld.LOCAL_BUSINESS_TYPES)


def test_organization_is_not_a_local_business():
    """Organization is LocalBusiness's *parent*, not a subtype."""
    for parent in ("organization", "corporation", "person", "webpage",
                   "product", "article"):
        assert parent not in jsonld.LOCAL_BUSINESS_TYPES


@pytest.mark.parametrize("subtype", [
    "Restaurant", "Dentist", "Plumber", "BookStore", "Hotel", "Attorney",
    "Bakery", "HairSalon", "AutoRepair", "Pharmacy", "Store", "Electrician",
])
def test_common_subtypes_are_recognised(subtype):
    assert subtype.lower() in jsonld.LOCAL_BUSINESS_TYPES


def test_reference_doc_and_code_agree():
    """The five subtypes named in references/local-seo.md must all be known.

    Docs and code drift silently otherwise; this is the same pinning the
    retired-type sets get in test_schema_status_parity.py (D-017).
    """
    with open(DOC, encoding="utf-8") as fh:
        line = [ln for ln in fh if "more specific than generic" in ln]
    assert line, f"subtype line not found in {DOC}"
    named = re.findall(r"`([A-Za-z]+)`", line[0].split("→")[0])
    assert len(named) >= 5, named
    for t in named:
        assert t.lower() in jsonld.LOCAL_BUSINESS_TYPES, f"{t} documented but unknown"


# --- detection helpers ------------------------------------------------------

def test_declared_types_reads_both_shapes():
    html = ('<script type="application/ld+json">{"@type": "Restaurant"}</script>'
            '<script type="application/ld+json">{"@type": ["WebPage", "Dentist"]}</script>')
    assert jsonld.declared_types(html) == ["Restaurant", "WebPage", "Dentist"]


def test_declared_types_dedupes_case_insensitively():
    html = '{"@type":"Store"} {"@type":"store"} {"@type":"Store"}'
    assert jsonld.declared_types(html) == ["Store"]


def test_local_business_types_in_filters_to_the_taxonomy():
    html = '{"@type": ["WebPage", "Restaurant", "Organization"]}'
    assert jsonld.local_business_types_in(html) == ["Restaurant"]


def test_local_business_types_in_returns_empty_for_a_saas_page():
    html = '{"@type": ["WebSite", "Organization", "SoftwareApplication"]}'
    assert jsonld.local_business_types_in(html) == []


def test_is_local_business_on_a_parsed_node():
    assert jsonld.is_local_business({"@type": "Restaurant"}) is True
    assert jsonld.is_local_business({"@type": ["WebPage", "Bakery"]}) is True
    assert jsonld.is_local_business({"@type": "Organization"}) is False
    assert jsonld.is_local_business("not a node") is False
    assert jsonld.is_local_business({}) is False


def test_declares_type_stays_exact():
    """The generic helper must NOT gain subtype awareness.

    Callers asking for a literal @type (retired-type checks, FAQPage parity)
    depend on it meaning exactly what it says.
    """
    html = '{"@type": "Restaurant"}'
    assert jsonld.declares_type(html, "LocalBusiness") is False


# --- the finding that started this -----------------------------------------

@pytest.mark.parametrize("type_value", [
    "Restaurant",
    "Dentist",
    "Plumber",
    ["WebPage", "Restaurant"],
    ["Store", "Organization"],
])
def test_subtype_page_is_not_told_to_add_schema(type_value, monkeypatch):
    result = _check(monkeypatch, _page(type_value))
    assert result["localbusiness_jsonld"] is True
    findings = [i["finding"] for i in result["issues"]]
    assert not any("no LocalBusiness JSON-LD" in f for f in findings), findings
    assert not any("add LocalBusiness schema" in r for r in result["recommendations"])


def test_subtype_is_named_in_the_output(monkeypatch):
    result = _check(monkeypatch, _page("Restaurant"))
    assert result["localbusiness_types"] == ["Restaurant"]
    assert any("Restaurant" in r for r in result["recommendations"])


def test_plain_localbusiness_still_detected(monkeypatch):
    result = _check(monkeypatch, _page("LocalBusiness"))
    assert result["localbusiness_jsonld"] is True
    assert result["localbusiness_types"] == ["LocalBusiness"]


def test_local_indicators_without_any_schema_still_flagged(monkeypatch):
    """The real finding must survive: this is the case it exists for."""
    html = '<html><body><a href="tel:+15555550123">Call</a>'\
           '<span>streetAddress</span></body></html>'
    result = _check(monkeypatch, html)
    assert result["localbusiness_jsonld"] is False
    assert result["localbusiness_types"] == []
    assert any(i["severity"] == "high" for i in result["issues"])


def test_saas_page_is_still_not_a_local_business(monkeypatch):
    html = ('<html><body><script type="application/ld+json">'
            '{"@type": ["WebSite", "Organization"]}</script></body></html>')
    result = _check(monkeypatch, html)
    assert result["likely_local_business"] is False
    assert result["score"] is None
    assert result["issues"] == []


# --- non-standard spellings: widening must not narrow -----------------------

# Exactly what maps_checker.py's private set matched before the taxonomy moved
# into jsonld.py. Every one of these must still be detected, or this "fix"
# quietly removed coverage from the one script that already had it.
MAPS_CHECKER_SET_BEFORE = frozenset({
    "localbusiness", "restaurant", "dentist", "attorney", "autobody",
    "autorepair", "bakery", "barorsalon", "beautysalon", "cafe",
    "drycleaningorlaundry", "electrician", "florist", "gym", "hairsalon",
    "healthclub", "hotel", "insuranceagency", "legalservice", "library",
    "locksmith", "medicalclinic", "motel", "movingcompany", "notary",
    "optician", "petstore", "pharmacy", "physician", "plumber",
    "realestateagent", "recyclingcenter", "selfstorge", "shoppingcenter",
    "sportsclub", "store", "travelagency", "veterinarycare",
})


@pytest.mark.parametrize("old_type", sorted(MAPS_CHECKER_SET_BEFORE))
def test_nothing_maps_checker_used_to_match_is_lost(old_type):
    assert jsonld.is_local_business({"@type": old_type}) is True


def test_aliases_are_kept_out_of_the_schema_org_set():
    """LOCAL_BUSINESS_TYPES must stay an honest mirror of schema.org."""
    for bad in jsonld.LOCAL_BUSINESS_ALIASES:
        assert bad not in jsonld.LOCAL_BUSINESS_TYPES


def test_every_alias_points_at_a_real_type():
    for bad, correction in jsonld.LOCAL_BUSINESS_ALIASES.items():
        assert correction.lower() in jsonld.LOCAL_BUSINESS_TYPES, bad


def test_alias_is_detected_but_reported_as_invalid(monkeypatch):
    result = _check(monkeypatch, _page("Cafe"))
    assert result["localbusiness_jsonld"] is True
    fixes = [i["fix"] for i in result["issues"]]
    assert any("CafeOrCoffeeShop" in f for f in fixes), result["issues"]


def test_valid_subtype_gets_no_invalid_type_issue(monkeypatch):
    result = _check(monkeypatch, _page("Restaurant"))
    assert not any("not a schema.org type" in i["finding"] for i in result["issues"])


# --- the two scripts must not disagree again --------------------------------

@pytest.mark.parametrize("subtype", ["Restaurant", "Dentist", "Store", "Hotel"])
def test_maps_checker_and_local_signals_agree(subtype):
    """Both scripts read the same taxonomy, so they cannot drift apart."""
    node = {"@type": subtype, "name": "Acme"}
    assert bool(maps_checker._find_local_schemas([node])) is True
    assert jsonld.is_local_business(node) is True


def test_maps_checker_reads_the_shared_taxonomy():
    assert maps_checker.LOCAL_BUSINESS_TYPES is jsonld.LOCAL_BUSINESS_TYPES


# --- helper -----------------------------------------------------------------

class _Resp:
    status_code = 200

    def __init__(self, text):
        self.text = text


def _check(monkeypatch, html):
    monkeypatch.setattr(
        local_signals_checker.requests, "get",
        lambda *a, **k: _Resp(html),
    )
    return local_signals_checker.check_local_signals("https://example.com")
