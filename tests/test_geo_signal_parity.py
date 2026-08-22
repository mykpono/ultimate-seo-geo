"""The GEO scoring rubrics must not award credit for signals Google ignores.

Google confirmed in June 2026 that Search ignores `llms.txt` entirely -- it
neither helps nor hurts visibility, including in AI Overviews and AI Mode. The
prose in `references/ai-search-geo.md` and `references/procedures/03-geo-ai-search.md`
said so, while the GEO Health Score rubric in *both* files still listed
"llms.txt present" as a Technical Accessibility signal, `generate_report.py`
still raised its absence as a `warning`, and `llms_txt_checker.py` printed a red
failure marker for a file that costs nothing to omit.

That is the same failure mode `test_schema_status_parity.py` guards for schema
status: `check-plugin-sync.py` proves the two trees are *identical*, never that
either is *correct*, so a green sync check sat on top of every drift below.

Guarded here:

  * llms.txt named as a scoring signal in either GEO rubric
  * the "Google ignores llms.txt" disclaimer going missing from either file
  * generate_report.py raising llms.txt above `info`
  * root tree and plugin bundle disagreeing on any of the above
"""

import os
import re
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
PLUGIN = os.path.join(ROOT, "plugins", "ultimate-seo-geo", "skills", "ultimate-seo-geo")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# (label, path relative to a tree root) for the files carrying a GEO rubric.
RUBRIC_FILES = [
    ("ai-search-geo", os.path.join("references", "ai-search-geo.md")),
    ("03-geo-ai-search", os.path.join("references", "procedures", "03-geo-ai-search.md")),
]

TREES = [("root", ROOT), ("plugin", PLUGIN)]

# A rubric row is a markdown table row naming a GEO dimension and its weight.
TECHNICAL_ACCESSIBILITY_ROW = re.compile(
    r"^\|\s*\**Technical Accessibility\**\s*\|.*$", re.M
)

# Phrasing that establishes Google ignores the file. Any one of these satisfies
# the requirement -- the point is that the claim is present, not its wording.
DISCLAIMER_PATTERNS = [
    r"Google Search ignores llms\.txt",
    r"Search ignores llms\.txt",
    r"Google Search does not use llms\.txt",
]


def _read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


@pytest.mark.parametrize("tree_name,tree", TREES)
@pytest.mark.parametrize("label,rel", RUBRIC_FILES)
def test_llms_txt_is_not_a_scoring_signal(tree_name, tree, label, rel):
    """The Technical Accessibility rubric row must not name llms.txt.

    Listing it there awards up to 20% of the GEO Health Score for a file Google
    does not read, and contradicts the prose in the same document.
    """
    text = _read(tree, rel)
    rows = TECHNICAL_ACCESSIBILITY_ROW.findall(text)
    assert rows, f"{tree_name}/{label}: no Technical Accessibility rubric row found"
    for row in rows:
        assert "llms.txt" not in row.lower(), (
            f"{tree_name}/{label}: llms.txt is listed as a Technical Accessibility "
            f"scoring signal, but Google Search ignores it (June 2026).\nRow: {row}"
        )


@pytest.mark.parametrize("tree_name,tree", TREES)
@pytest.mark.parametrize("label,rel", RUBRIC_FILES)
def test_llms_txt_carries_the_google_disclaimer(tree_name, tree, label, rel):
    """Wherever llms.txt is discussed, the Google position must travel with it."""
    text = _read(tree, rel)
    if "llms.txt" not in text:
        pytest.skip(f"{tree_name}/{label} does not mention llms.txt")
    assert any(re.search(p, text, re.I) for p in DISCLAIMER_PATTERNS), (
        f"{tree_name}/{label}: mentions llms.txt without stating that Google Search "
        f"ignores it. Readers will infer a Google benefit that does not exist."
    )


@pytest.mark.parametrize("tree_name,tree", TREES)
def test_report_does_not_raise_llms_txt_above_info(tree_name, tree):
    """A missing llms.txt costs nothing on Google, so it cannot be a warning."""
    text = _read(tree, "scripts", "generate_report.py")
    match = re.search(
        r'if not llm\.get\("exists"\):\s*\n\s*add\(\s*\n\s*"(?P<severity>\w+)"',
        text,
    )
    assert match, f"{tree_name}: could not locate the llms.txt finding in generate_report.py"
    assert match.group("severity") == "info", (
        f"{tree_name}: the llms.txt finding is raised at "
        f"'{match.group('severity')}'. Google ignores llms.txt (June 2026), so its "
        f"absence is informational only and must not consume Health Score."
    )


@pytest.mark.parametrize("tree_name,tree", TREES)
def test_llms_checker_states_it_is_not_a_google_signal(tree_name, tree):
    """The checker's own output must be unmisreadable in isolation.

    Script output is routinely pasted into reports without the surrounding
    reference docs, so the disclaimer has to live in the script too.
    """
    text = _read(tree, "scripts", "llms_txt_checker.py")
    assert any(re.search(p, text, re.I) for p in DISCLAIMER_PATTERNS), (
        f"{tree_name}: llms_txt_checker.py does not state that Google Search ignores "
        f"llms.txt. Its output can then be read as a Google SEO defect."
    )
    assert "🔴" not in text, (
        f"{tree_name}: llms_txt_checker.py uses a critical-failure marker for a file "
        f"whose absence has no Google Search effect."
    )


def test_both_trees_agree_on_geo_signal_files():
    """Root and plugin bundle must be byte-identical for every file guarded here."""
    guarded = [rel for _, rel in RUBRIC_FILES] + [
        os.path.join("scripts", "generate_report.py"),
        os.path.join("scripts", "llms_txt_checker.py"),
    ]
    for rel in guarded:
        assert _read(ROOT, rel) == _read(PLUGIN, rel), (
            f"{rel} differs between root and plugin bundle. Fix: bash setup-plugin.sh"
        )
