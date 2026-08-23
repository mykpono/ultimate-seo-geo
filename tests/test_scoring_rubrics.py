"""Every scoring rubric's arithmetic must land inside its own bands.

Three rubrics shipped with maths that could not produce their own top grades:

  * `keyword-strategy.md` divided the weighted sum by 5, capping the maximum at
    1.00 -- which its own table calls "P3, track but don't prioritize".
  * `cite-domain-rating.md` and `core-eeat-framework.md` scored items 0/5/10 and
    banded grades 0-100 with no normalisation stated, so a perfect score read
    "Poor".

None of these contained a date or an out-of-range number, so the freshness sweep
that cleared those files saw nothing. They are only visible if you run the maths.

This file runs the maths. It checks the two mechanical properties that hold for
every weighted rubric in the repo:

  1. Weight columns sum to 100%. A column that does not is either missing a row
     or double-counting one.
  2. Worked examples agree with their own stated weights. An example is what a
     reader copies, so an example that contradicts its rubric propagates further
     than the rubric does.
"""

import glob
import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")

PCT = re.compile(r"(\d{1,3})\s*%")


def _tables(text):
    """Yield (header_cells, row_cells, line_no) for each markdown table."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        is_row = lines[i].strip().startswith("|")
        has_sep = i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1])
        if is_row and has_sep:
            hdr = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            rows, j = [], i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                j += 1
            yield hdr, rows, i + 1
            i = j
        else:
            i += 1


def _weight_columns(text):
    """Yield (column_name, line_no, [percentages]) for columns that are all percentages."""
    for hdr, rows, ln in _tables(text):
        if not rows:
            continue
        ncol = max(len(r) for r in rows)
        for c in range(ncol):
            filled = [r[c].replace("**", "").strip() for r in rows if c < len(r) and r[c].strip()]
            vals = [int(m.group(1)) for m in (PCT.fullmatch(v) for v in filled) if m]
            # Every filled cell is a bare percentage, and enough of them to be a rubric.
            if len(vals) >= 3 and len(vals) == len(filled):
                yield (hdr[c] if c < len(hdr) else f"col{c}"), ln, vals


REFERENCE_FILES = sorted(
    glob.glob(os.path.join(ROOT, "references", "**", "*.md"), recursive=True)
) + [os.path.join(ROOT, "AGENTS.md")]


@pytest.mark.parametrize("path", REFERENCE_FILES, ids=lambda p: os.path.basename(p))
def test_weight_columns_sum_to_100(path):
    """A weight column that does not total 100% cannot produce a score in its bands."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    bad = [
        (name, ln, vals, sum(vals))
        for name, ln, vals in _weight_columns(text)
        if sum(vals) != 100
    ]
    assert not bad, (
        f"{os.path.relpath(path, ROOT)}: weight column(s) do not sum to 100%: "
        + "; ".join(f"'{n}' at line {ln} = {s}% {v}" for n, ln, v, s in bad)
    )


def test_geo_worked_example_matches_its_weights():
    """The GEO example in audit-output-example.md must equal its own arithmetic.

    This example carried a Technical Accessibility score docked for a missing
    llms.txt -- a fourth copy of the scoring contradiction -- and a headline that
    disagreed with its own rows by 1.5 points.
    """
    path = os.path.join(ROOT, "references", "audit-output-example.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    m = re.search(r"## GEO Score: (\d+)/100", text)
    assert m, "GEO worked example not found"
    stated = int(m.group(1))

    section = text[m.end():]
    rows = re.findall(r"^\|\s*([\w &-]+?)\s*\|\s*(\d{1,3})%\s*\|\s*(\d{1,3})\s*\|", section, re.M)
    assert len(rows) >= 5, f"expected the 5 GEO dimension rows, found {len(rows)}"

    weights = [int(w) for _, w, _ in rows]
    assert sum(weights) == 100, f"GEO example weights sum to {sum(weights)}%, not 100%"

    computed = sum(int(w) * int(s) for _, w, s in rows) / 100
    assert abs(computed - stated) < 1, (
        f"GEO worked example states {stated}/100 but its own rows compute to {computed:.2f}. "
        f"A reader copying this example inherits the discrepancy."
    )


def test_geo_example_does_not_dock_for_llms_txt():
    """Google ignores llms.txt, so no worked example may deduct for its absence."""
    path = os.path.join(ROOT, "references", "audit-output-example.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    offenders = [
        line for line in text.splitlines()
        if re.search(r"no llms\.txt|llms\.txt\s*❌", line, re.I)
    ]
    assert not offenders, (
        f"audit-output-example.md deducts for a missing llms.txt, which Google ignores "
        f"(June 2026). Worked examples are copied verbatim.\nOffending: {offenders}"
    )


def test_health_score_example_matches_its_own_deductions():
    """The Health Score example must apply the deduction schedule it prints.

    It previously computed 51 and then reported 61 -- the pre-deduction base --
    with an unexplained "adjusted" step, so it demonstrated a procedure and then
    did not follow it.
    """
    path = os.path.join(ROOT, "references", "audit-output-example.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    m = re.search(
        r"## SEO Health Score: (\d+)/100\s*\n"
        r"positive_signals=(\d+), deficit_signals=(\d+), base=(\d+);?\s*"
        r"(?:deductions:)?\s*Critical −15×(\d+), High −8×(\d+), Medium −3×(\d+), Low −1×(\d+)\s*=\s*(\d+)",
        text,
    )
    assert m, "Health Score worked example not found in the expected four-severity form"
    stated, pos, deficit, base, crit, high, med, low, final = (int(g) for g in m.groups())

    assert round(pos / (pos + deficit) * 100) == base, (
        f"base_score should be {pos}/({pos}+{deficit})×100 = {pos/(pos+deficit)*100:.1f}, example says {base}"
    )
    expected = base - 15 * crit - 8 * high - 3 * med - 1 * low
    assert expected == final == stated, (
        f"Health Score example: base {base} minus its own deductions = {expected}, "
        f"but the line ends at {final} and the headline says {stated}."
    )
