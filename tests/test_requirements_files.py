"""A `pip install -r <file>` printed by this repo must point at a real, complete file.

`requirements-gsc.txt` was referenced by four scripts -- `gsc_export.py` and
`gsc_query.py`, plus their plugin-bundle copies -- and was **never committed**.
It existed only on the maintainer's machine. Anyone cloning the repo and hitting
the "Missing Google auth libraries" error was sent to a file that wasn't there.

It was also incomplete. `gsc_export.py` needs `google-auth` and
`google-auth-oauthlib`; `gsc_query.py` additionally needs
`google-api-python-client` for `googleapiclient.discovery`. Only the first two
were listed, so `pip install -r requirements-gsc.txt` satisfied one script and
left the other failing on ImportError -- with an error message pointing back at
the same incomplete file.

Same shape as the removed-Google-tools defects: instructions pointing at
something that does not exist. Untracked files are invisible to every check that
reads the working tree, which is why nothing caught it.
"""

import glob
import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")

# Import prefix -> distribution that provides it.
IMPORT_TO_PACKAGE = {
    "googleapiclient": "google-api-python-client",
    "google_auth_oauthlib": "google-auth-oauthlib",
    "google.oauth2": "google-auth",
    "google.auth": "google-auth",
    "bs4": "beautifulsoup4",
    "requests": "requests",
    "openpyxl": "openpyxl",
}

SEARCH_ROOTS = ["scripts", "references", "AGENTS.md", "SKILL.md", "README.md"]


def _files():
    for root in SEARCH_ROOTS:
        p = os.path.join(ROOT, root)
        if os.path.isfile(p):
            yield p
        else:
            yield from (f for f in glob.glob(os.path.join(p, "**", "*"), recursive=True)
                        if os.path.isfile(f) and f.endswith((".py", ".md", ".sh", ".txt")))


def test_referenced_requirements_files_exist():
    """Every `pip install -r X` in the repo must name a file that is present."""
    missing = []
    for path in _files():
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for req in re.findall(r"pip install\s+-r\s+([\w./-]+\.txt)", line):
                target = os.path.join(ROOT, req)
                if not os.path.isfile(target):
                    missing.append(f"{os.path.relpath(path, ROOT)}:{n} -> {req}")
    assert not missing, (
        "scripts tell users to install from requirements files that do not exist:\n  "
        + "\n  ".join(sorted(set(missing)))
    )


def test_referenced_requirements_files_are_tracked_by_git():
    """Existing is not enough — an untracked file is absent for everyone else.

    This is the check that would have caught it: `requirements-gsc.txt` was on
    disk and passed every working-tree check, while being invisible in a clone.
    """
    import subprocess

    tracked = set(
        subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    )
    if not tracked:
        pytest.skip("not a git checkout")

    referenced = set()
    for path in _files():
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (UnicodeDecodeError, OSError):
            continue
        referenced |= set(re.findall(r"pip install\s+-r\s+([\w./-]+\.txt)", text))

    untracked = sorted(r for r in referenced if r not in tracked)
    assert not untracked, (
        "requirements files are referenced but not tracked by git — they exist locally "
        f"and are absent in a clone: {untracked}"
    )


@pytest.mark.parametrize("script", ["gsc_query.py", "gsc_export.py"])
def test_gsc_requirements_cover_what_the_scripts_import(script):
    """`requirements-gsc.txt` must cover every third-party import in both scripts.

    Listing only what one script needs is how `gsc_query.py` ended up failing on
    ImportError after a successful `pip install -r requirements-gsc.txt`.
    """
    req_path = os.path.join(ROOT, "requirements-gsc.txt")
    assert os.path.isfile(req_path), "requirements-gsc.txt is missing"
    with open(req_path, encoding="utf-8") as fh:
        provided = {
            re.split(r"[><=~!\[]", line.strip())[0].strip()
            for line in fh
            if line.strip() and not line.startswith("#")
        }

    with open(os.path.join(ROOT, "scripts", script), encoding="utf-8") as fh:
        src = fh.read()

    missing = set()
    for prefix, package in IMPORT_TO_PACKAGE.items():
        if not package.startswith("google"):
            continue  # requirements-gsc.txt is scoped to the Google stack
        if re.search(rf"\b(?:from|import)\s+{re.escape(prefix)}\b", src) and package not in provided:
            missing.add(f"{prefix} -> {package}")

    assert not missing, (
        f"scripts/{script} imports packages that requirements-gsc.txt does not list: "
        f"{sorted(missing)}\n  listed: {sorted(provided)}"
    )
