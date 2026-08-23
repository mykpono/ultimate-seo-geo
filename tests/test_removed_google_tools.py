"""Never send a user to a Google tool that no longer exists.

Advice pointing at a removed tool is worse than no advice: the reader follows it,
finds nothing, and has no way to tell whether they are looking in the wrong place
or the guidance is stale. Four such pointers shipped in the reference set, the
oldest naming a tool retired seven years earlier:

  * Search Console **preferred domain** setting -- retired 2019
  * Search Console **URL Parameters** tool -- removed 28 April 2022
  * Search Console **International Targeting** report -- removed 22 September 2022
  * Search Console **crawl rate limiter** -- removed 8 January 2024

Plus ``Crawl-delay`` presented as a way to control Googlebot, which has never
honoured it.

None of these carried a date or a suspicious number, so every freshness sweep
passed over them. They are only visible if you know the tool is gone.

The patterns below match *instructions to use* the tool, not mentions of it. A
file is free -- encouraged -- to say "this was removed in 2022"; that is how a
reader learns the tool is gone. What is barred is a navigation path or an
imperative pointing at it.
"""

import glob
import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")

# (label, pattern) -- each matches a directive to go and use the tool.
REMOVED_TOOL_DIRECTIVES = [
    (
        "Search Console preferred domain setting (retired 2019)",
        r"set (?:the )?preferred domain in (?:GSC|Search Console)",
    ),
    (
        "Search Console URL Parameters tool (removed 2022-04-28)",
        r"configure URL parameters in (?:GSC|Search Console)",
    ),
    (
        "Search Console International Targeting report (removed 2022-09-22)",
        r"(?<!\")GSC\s*(?:→|->)\s*Legacy Tools\s*(?:→|->)\s*International Targeting",
    ),
    (
        "Search Console crawl rate limiter (removed 2024-01-08)",
        r'"Crawl rate" setting \(legacy',
    ),
    (
        "Crawl-delay as a Googlebot control (never supported)",
        r"`Crawl-delay` in robots\.txt \(use sparingly",
    ),
    (
        "disavow tool under a Search Console menu path (it is standalone)",
        r"Search Console\s*(?:>|→|->)\s*(?:Legacy Tools|Security & Manual Actions)\s*(?:>|→|->)\s*Disavow",
    ),
]

MARKDOWN = sorted(
    glob.glob(os.path.join(ROOT, "references", "**", "*.md"), recursive=True)
) + [os.path.join(ROOT, "AGENTS.md"), os.path.join(ROOT, "SKILL.md")]


@pytest.mark.parametrize("label,pattern", REMOVED_TOOL_DIRECTIVES, ids=lambda x: x if isinstance(x, str) and " " not in x[:6] else None)
def test_no_directive_to_removed_google_tool(label, pattern):
    """No file may instruct a reader to use a tool Google has removed."""
    offenders = []
    for path in MARKDOWN:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                # A line explaining that the tool is gone is the fix, not the bug.
                if re.search(r"removed|retired|deprecat|no longer|does not exist|not supported", line, re.I):
                    continue
                if re.search(pattern, line, re.I):
                    offenders.append(f"{os.path.relpath(path, ROOT)}:{n}")
    assert not offenders, f"Directive to use a removed tool — {label}\n  " + "\n  ".join(offenders)


def test_disavow_guidance_is_gated():
    """Disavow must be gated on manual action or negative SEO, not a toxicity score.

    Google's position is that most sites never need the tool, and that disavowing
    on a vendor "toxic" score strips credit from borderline-but-legitimate links
    that were still counting. Both files that describe the workflow must say so.
    """
    for rel in ("link-building.md", "backlink-quality.md"):
        path = os.path.join(ROOT, "references", rel)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if "disavow" not in text.lower():
            continue
        assert re.search(r"manual action", text, re.I), (
            f"{rel} describes disavowing without gating it on a manual action."
        )
        assert re.search(r"most sites (?:never|will not|do not)", text, re.I), (
            f"{rel} describes disavowing without stating that most sites never need it."
        )


def test_toxic_links_labelled_as_vendor_metric():
    """Wherever a "toxic" score drives advice, say Google does not use the term."""
    for rel in ("link-building.md", "backlink-quality.md"):
        path = os.path.join(ROOT, "references", rel)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if not re.search(r"toxic", text, re.I):
            continue
        assert re.search(r"(vendor metric|not a Google concept|does not use the term)", text, re.I), (
            f"{rel} uses 'toxic' scoring without noting it is a vendor metric Google does not "
            f"recognise. Presenting it as a Google signal is how it ends up driving disavows."
        )
