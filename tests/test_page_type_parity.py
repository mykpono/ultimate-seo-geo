"""references/page-types.md and page_type_classifier.py must agree.

Same mechanism as tests/test_schema_status_parity.py (D-017): the doc is what
the agent reads to explain a label to the user, the script is what produced
it. If a label, its funnel stage, or an expected-types row changes in one
place only, this fails.
"""

import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import page_type_classifier as ptc  # noqa: E402

DOC = os.path.join(ROOT, "references", "page-types.md")


def _section(name):
    with open(DOC, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    out, capturing = [], False
    for line in lines:
        if line.startswith("## "):
            if capturing:
                break
            capturing = line.startswith("## " + name)
            continue
        if capturing:
            out.append(line)
    assert out, f"section '{name}' not found in {DOC}"
    return out


def _rows(section_name):
    """{first bold cell: [other cells]} for each table row."""
    rows = {}
    for line in _section(section_name):
        if not line.startswith("| **"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        m = re.match(r"\*\*(.+?)\*\*", cells[0])
        if m:
            rows[m.group(1)] = cells[1:]
    return rows


DOC_TYPES = _rows("Page type taxonomy")
DOC_EXPECTED = _rows("Expected page types by site type")


def test_every_script_label_is_documented_and_vice_versa():
    assert set(DOC_TYPES) == set(ptc.LABELS)


def test_doc_table_order_matches_rule_order():
    """First match wins, so the order the doc shows is the order that applies."""
    assert list(DOC_TYPES) == list(ptc.LABELS)


def test_intent_stage_matches_per_label():
    for t in ptc.PAGE_TYPES:
        assert DOC_TYPES[t["label"]][0] == t["intent"], t["label"]


def test_intent_stages_are_the_documented_set():
    for t in ptc.PAGE_TYPES:
        assert t["intent"] in ptc.INTENT_STAGES, t["label"]


def test_expected_types_per_site_type_match():
    doc = {k: [x.strip() for x in v[0].split(",")] if v[0] != "—" else [] for k, v in DOC_EXPECTED.items()}
    assert doc == ptc.EXPECTED_BY_SITE_TYPE


def test_expected_types_are_known_labels():
    for st, labels in ptc.EXPECTED_BY_SITE_TYPE.items():
        unknown = set(labels) - set(ptc.LABELS)
        assert not unknown, f"{st}: {unknown}"


def test_site_type_choices_cover_expected_table():
    assert set(ptc.EXPECTED_BY_SITE_TYPE) | {"auto"} == set(ptc.SITE_TYPES)


def test_money_types_are_known_labels():
    assert ptc.MONEY_TYPES <= set(ptc.LABELS)


def test_documented_money_types_match():
    text = "\n".join(_section("Expected page types by site type"))
    m = re.search(r"money\*\* type \((.+?)\)", text)
    assert m, "money-type list missing from the doc"
    assert set(x.strip() for x in m.group(1).split(",")) == set(ptc.MONEY_TYPES)


def test_word_floors_are_known_labels():
    assert set(ptc.WORD_FLOORS) <= set(ptc.LABELS)
