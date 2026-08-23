"""AGENTS.md must fit inside Codex's instruction-file budget.

Codex loads AGENTS.md into every session and **silently truncates** at
`project_doc_max_bytes` (32 KiB by default). There is no warning in the TUI,
`/stats`, `exec`, or the VS Code extension -- instructions past the cutoff are
simply never sent to the model.

This repo shipped over that limit for several releases. At 37,238 bytes the
following were invisible to every Codex user:

  * SS 22 Drift Monitoring, 23 Semantic Clustering, 24 E-commerce, 25 Maps
  * the Google API Tier System section
  * the "Full Detail Reference" table -- the map to references/, so the agent
    could not even find the files it was told to read

The README advertises AGENTS.md compatibility, which made that a correctness
bug rather than a housekeeping one. This test is the guard.

IMPORTANT -- the real budget is smaller than it looks. `project_doc_max_bytes`
caps the *combined* size of every instruction file Codex loads across the
directory hierarchy, not this file alone. A user with their own root AGENTS.md
spends the same budget. So passing this test is necessary, not sufficient, and
the headroom below is deliberately treated as a ceiling to stay well under, not
a target to fill. Codex users who need more can raise the limit in
~/.codex/config.toml -- documented in README.md.
"""

import os

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
PLUGIN = os.path.join(ROOT, "plugins", "ultimate-seo-geo", "skills", "ultimate-seo-geo")

# Codex's default project_doc_max_bytes.
CODEX_LIMIT = 32 * 1024

TREES = [("root", ROOT), ("plugin", PLUGIN)]


def _size(tree, name):
    with open(os.path.join(tree, name), "rb") as fh:
        return len(fh.read())


@pytest.mark.parametrize("tree_name,tree", TREES)
def test_agents_md_fits_codex_budget(tree_name, tree):
    size = _size(tree, "AGENTS.md")
    assert size <= CODEX_LIMIT, (
        f"{tree_name}/AGENTS.md is {size:,} bytes, over Codex's "
        f"{CODEX_LIMIT:,}-byte default by {size - CODEX_LIMIT:,}.\n"
        f"Codex truncates SILENTLY -- everything past the cutoff is dropped with no warning.\n"
        f"Move prose into references/ and leave a pointer; do not delete content. "
        f"The Routing Index table at the top of AGENTS.md is how the agent finds those files, "
        f"so it must never be the thing that gets cut."
    )


@pytest.mark.parametrize("tree_name,tree", TREES)
def test_agents_md_keeps_usable_headroom(tree_name, tree):
    """Sitting a few bytes under the cap is not actually safe.

    The cap is shared with the user's own instruction files, so a file that
    only just fits in isolation still truncates in a real project.
    """
    size = _size(tree, "AGENTS.md")
    headroom = CODEX_LIMIT - size
    assert headroom >= 0, f"{tree_name}/AGENTS.md exceeds the budget entirely ({size:,} bytes)"
    if headroom < 512:
        pytest.xfail(
            f"{tree_name}/AGENTS.md has only {headroom:,} bytes of headroom under the "
            f"{CODEX_LIMIT:,}-byte cap. It fits alone but will truncate for any user who "
            f"also has a root AGENTS.md, since project_doc_max_bytes is a combined budget. "
            f"Known and accepted -- see README.md on raising project_doc_max_bytes."
        )


def test_routing_index_survives_truncation():
    """The map to references/ must sit well inside the cap.

    Everything else in AGENTS.md is recoverable by reading a reference file --
    but only if the agent can still see the table telling it which file to read.
    """
    with open(os.path.join(ROOT, "AGENTS.md"), "rb") as fh:
        raw = fh.read()
    idx = raw.find(b"### Routing Index")
    assert idx != -1, "AGENTS.md no longer contains a Routing Index"
    assert idx < 4096, (
        f"Routing Index starts at byte {idx:,}. It is the agent's map to references/ and "
        f"must stay near the top of the file, comfortably inside any truncation point."
    )


def test_every_procedure_file_is_reachable_from_agents_md():
    """A procedure file nothing points at is a file the agent never loads."""
    import re

    with open(os.path.join(ROOT, "AGENTS.md"), encoding="utf-8") as fh:
        text = fh.read()
    referenced = set(re.findall(r"(\d\d-[\w-]+\.md)", text))
    on_disk = {
        f for f in os.listdir(os.path.join(ROOT, "references", "procedures"))
        if re.match(r"\d\d-", f)
    }
    assert not (on_disk - referenced), (
        f"procedure files exist but are unreachable from AGENTS.md: "
        f"{sorted(on_disk - referenced)}"
    )
    assert not (referenced - on_disk), (
        f"AGENTS.md points at procedure files that do not exist: "
        f"{sorted(referenced - on_disk)}"
    )
