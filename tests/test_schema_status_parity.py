"""Docs and code must agree about which schema types are retired.

`scripts/check-plugin-sync.py` verifies the root tree and the plugin bundle are
byte-identical. It says nothing about whether either is *correct* — a green sync
check sat on top of every bug this file now guards against:

  * `Dataset` marked retired in code while `AGENTS.md` said "NOT discontinued"
  * `FAQPage`/`HowTo` in the deprecated set while §19 said never recommend removal
  * `PracticeProblem` vs `PracticeProblems` disagreeing between scripts
  * `EnergyConsumptionDetails` documented as retired but present in no script

Docs and code can now only drift by failing CI.
"""

import os
import re
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import article_seo  # noqa: E402
import parse_html  # noqa: E402
import validate_schema  # noqa: E402

DOC = os.path.join(ROOT, "references", "schema-types.md")

# Rows in the reference tables that name a Google *search feature* rather than a
# schema.org @type. Scripts key on @type, so these are legitimately absent.
NOT_A_SCHEMA_TYPE = {"Sitelinks Search Box"}


def _section(name):
    """Return the markdown lines of the `## <name>...` section."""
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


def _types_in(section_name):
    """First bolded cell of each table row is the type name."""
    types = set()
    for line in _section(section_name):
        if not line.startswith("| **"):
            continue
        first_cell = line.split("|")[1].strip()
        match = re.match(r"\*\*(.+?)\*\*", first_cell)
        if match:
            name = match.group(1).strip()
            if name not in NOT_A_SCHEMA_TYPE:
                types.add(name)
    return types


DOC_RETIRED = _types_in("RETIRED")
DOC_NO_RICH = _types_in("NO GOOGLE RICH RESULTS")

# (label, retired-set, no-rich-results-set) for each script.
SCRIPTS = [
    ("validate_schema.py",
     set(validate_schema.RETIRED_TYPES), set(validate_schema.NO_RICH_RESULTS_TYPES)),
    ("article_seo.py",
     set(article_seo.DEPRECATED_SCHEMA), set(article_seo.NO_RICH_RESULTS)),
    ("parse_html.py",
     set(parse_html.DEPRECATED_SCHEMA), set(parse_html.NO_RICH_RESULTS)),
]


def test_doc_buckets_are_mutually_exclusive():
    """A type cannot be both retired and merely rich-results-removed.

    `Dataset` was listed in both tables before Task 1.
    """
    assert DOC_RETIRED & DOC_NO_RICH == set()


@pytest.mark.parametrize("label,retired,no_rich", SCRIPTS)
def test_script_sets_are_mutually_exclusive(label, retired, no_rich):
    assert retired & no_rich == set(), label


@pytest.mark.parametrize("label,retired,no_rich", SCRIPTS)
def test_script_retired_matches_doc(label, retired, no_rich):
    """Every type a script calls retired must be in the doc's RETIRED table."""
    assert retired == DOC_RETIRED, (
        f"{label} retired set differs from {DOC}\n"
        f"  in script only: {sorted(retired - DOC_RETIRED)}\n"
        f"  in doc only:    {sorted(DOC_RETIRED - retired)}"
    )


@pytest.mark.parametrize("label,retired,no_rich", SCRIPTS)
def test_script_no_rich_results_matches_doc(label, retired, no_rich):
    assert no_rich == DOC_NO_RICH, (
        f"{label} no-rich-results set differs from {DOC}\n"
        f"  in script only: {sorted(no_rich - DOC_NO_RICH)}\n"
        f"  in doc only:    {sorted(DOC_NO_RICH - no_rich)}"
    )


def test_all_three_scripts_agree_with_each_other():
    """Catches the PracticeProblem/PracticeProblems split directly."""
    retired = {label: r for label, r, _ in SCRIPTS}
    no_rich = {label: n for label, _, n in SCRIPTS}
    assert len(set(map(frozenset, retired.values()))) == 1, retired
    assert len(set(map(frozenset, no_rich.values()))) == 1, no_rich


def test_no_script_flags_a_nonexistent_practice_problem_type():
    """Neither spelling is a schema.org type; the real markup is @type Quiz."""
    for label, retired, no_rich in SCRIPTS:
        assert "PracticeProblem" not in retired | no_rich, label
        assert "PracticeProblems" not in retired | no_rich, label
        assert "Quiz" in no_rich, label
