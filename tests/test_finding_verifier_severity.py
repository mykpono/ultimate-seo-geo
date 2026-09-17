"""finding_verifier.py ranks every severity on the report scale.

It used to know only Critical/Warning/Info/Pass, so a "High" finding (the
audit template's own label) ranked below Info: merged with an Info duplicate
it was downgraded to Info, and it sorted after every Info finding.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import finding_verifier as fv  # noqa: E402


def test_a_high_finding_keeps_its_severity_when_merged_with_an_info_duplicate():
    result = fv.verify_findings([
        {"severity": "High", "finding": "Canonical points to a redirect", "source": "a"},
        {"severity": "Info", "finding": "Canonical points to a redirect", "source": "b"},
    ])

    [finding] = result["findings"]
    assert finding["severity"] == "High"
    assert finding["sources"] == ["a", "b"]


def test_findings_sort_on_the_full_scale_whatever_the_case():
    labels = ["info", "Low", "medium", "HIGH", "Critical", "Warning", "Pass"]
    findings = [{"severity": s, "finding": f"finding {i}"} for i, s in enumerate(labels)]

    ordered = [f["severity"] for f in fv.verify_findings(findings)["findings"]]

    assert ordered == ["Critical", "HIGH", "medium", "Warning", "Low", "info", "Pass"]


@pytest.mark.parametrize("stronger,weaker", [("critical", "high"), ("high", "medium"), ("medium", "low"),
                                             ("low", "info"), ("warning", "low")])
def test_rank_order(stronger, weaker):
    assert fv._sev_rank(stronger) < fv._sev_rank(weaker)
