"""OpenAI's three crawlers must not be conflated.

OpenAI runs three separate agents with independent robots.txt controls:

  * ``GPTBot``        -- model training
  * ``OAI-SearchBot`` -- the ChatGPT Search index
  * ``ChatGPT-User``  -- user-triggered live fetches

Blocking one has no effect on the others. The repo carried the opposite claim as
a **§ 19 hard rule** -- "GPTBot ≠ training only. Blocking it also limits ChatGPT
Search citation. Users who block GPTBot expecting only training-opt-out lose live
search visibility" -- while `04-technical-seo.md` stated the correct distinction
a few files away.

That is not a cosmetic inconsistency. A site owner choosing to opt out of model
training while keeping search visibility is making a real licensing decision, and
the rule told them it was impossible. Guidance that forecloses a legitimate choice
on a false premise is worse than no guidance.

It survived because it lived in the *myths* section -- the place a reader goes
specifically to have misconceptions corrected.
"""

import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
PLUGIN = os.path.join(ROOT, "plugins", "ultimate-seo-geo", "skills", "ultimate-seo-geo")
TREES = [("root", ROOT), ("plugin", PLUGIN)]

# Files that make crawler claims. Kept explicit rather than globbed so a new file
# making the same mistake is a deliberate addition here, not a silent pass.
CLAIM_FILES = [
    "AGENTS.md",
    os.path.join("references", "ai-search-geo.md"),
    os.path.join("references", "entity-optimization.md"),
    os.path.join("references", "technical-checklist.md"),
    os.path.join("references", "procedures", "04-technical-seo.md"),
    os.path.join("references", "procedures", "19-quality-gates-hard-rules.md"),
]

# Phrasings that assert blocking GPTBot costs ChatGPT Search visibility.
FALSE_CLAIMS = [
    r"GPTBot\s*(?:≠|!=|is not|isn'?t)\s*training[- ]only",
    r"blocking\s+(?:it|GPTBot)[^.]{0,60}\b(?:also\s+)?limits?\s+ChatGPT\s+Search",
    r"block\w*\s+GPTBot[^.]{0,80}lose\s+(?:live\s+)?search\s+visibility",
]


def _read(tree, rel):
    with open(os.path.join(tree, rel), encoding="utf-8") as fh:
        return fh.read()


@pytest.mark.parametrize("tree_name,tree", TREES)
@pytest.mark.parametrize("rel", CLAIM_FILES)
def test_no_false_gptbot_search_claim(tree_name, tree, rel):
    """Nothing may claim that blocking GPTBot costs ChatGPT Search citations."""
    path = os.path.join(tree, rel)
    if not os.path.isfile(path):
        pytest.skip(f"{tree_name}/{rel} not present")
    text = _read(tree, rel)
    hits = [p for p in FALSE_CLAIMS if re.search(p, text, re.I)]
    assert not hits, (
        f"{tree_name}/{rel} claims blocking GPTBot affects ChatGPT Search citations. "
        f"It does not -- GPTBot is training-only; OAI-SearchBot governs ChatGPT Search and "
        f"ChatGPT-User handles live fetches, and the three are independent. Matched: {hits}"
    )


@pytest.mark.parametrize("tree_name,tree", TREES)
def test_hard_rule_names_the_search_crawler(tree_name, tree):
    """The § 19 rule must name OAI-SearchBot, not just warn about GPTBot.

    Naming the wrong crawler is how the original bug did damage: a reader following
    it would allow GPTBot for a benefit it does not provide, and could still be
    invisible in ChatGPT Search because OAI-SearchBot was blocked.
    """
    text = _read(tree, os.path.join("references", "procedures", "19-quality-gates-hard-rules.md"))
    assert "OAI-SearchBot" in text, (
        f"{tree_name}/19-quality-gates-hard-rules.md discusses AI crawler blocking without naming "
        f"OAI-SearchBot, the crawler that actually governs ChatGPT Search visibility."
    )
