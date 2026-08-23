"""Commands printed in the references must actually run.

`references/schema-types.md` told readers -- four separate times across this
session's PRs -- to settle the FAQ API question by running `gsc_query.py`
"grouped by searchAppearance". The script's `--dimension` choices were
`query, page, country, device, date`. `searchAppearance` was not among them, so
the recommended command died on an argparse error before touching the network.

Nothing caught it because the advice was never run: it needs credentials, and
"needs credentials" reads the same as "blocked" whether or not the command is
even valid. A documented command that cannot parse is worse than no command --
it sends the reader looking for a credentials problem that isn't there.

These checks are static: they compare what the docs invoke against what the
scripts declare, without executing anything or requiring network access.
"""

import glob
import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPTS = os.path.join(ROOT, "scripts")

DOC_FILES = sorted(glob.glob(os.path.join(ROOT, "references", "**", "*.md"), recursive=True)) + [
    os.path.join(ROOT, "AGENTS.md"),
    os.path.join(ROOT, "SKILL.md"),
]

# `python scripts/foo.py ...` up to end of line or a closing backtick.
INVOCATION = re.compile(r"python3?\s+scripts/([\w-]+\.py)((?:\s+[^\n`]*)?)")


def _iter_invocations():
    for path in DOC_FILES:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                for m in INVOCATION.finditer(line):
                    yield os.path.relpath(path, ROOT), n, m.group(1), m.group(2)


def _script_source(name):
    p = os.path.join(SCRIPTS, name)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def test_documented_scripts_exist():
    """Every `python scripts/X.py` in the docs must name a real script."""
    missing = {
        f"{doc}:{line} -> {script}"
        for doc, line, script, _ in _iter_invocations()
        if _script_source(script) is None
    }
    assert not missing, "documented commands reference scripts that do not exist:\n  " + "\n  ".join(sorted(missing))


def test_documented_flags_are_accepted_by_the_script():
    """Every `--flag` in a documented command must be declared by that script."""
    bad = []
    for doc, line, script, args in _iter_invocations():
        src = _script_source(script)
        if src is None:
            continue
        declared = set(re.findall(r'"(--[\w-]+)"', src)) | set(re.findall(r"'(--[\w-]+)'", src))
        for flag in re.findall(r"(?<![\w-])(--[\w-]+)", args):
            if flag not in declared:
                bad.append(f"{doc}:{line} -> {script} does not accept {flag}")
    assert not bad, "documented commands use flags the script does not declare:\n  " + "\n  ".join(bad)


def test_documented_choice_values_are_valid():
    """A documented `--flag value` must be in that flag's `choices`, when it has any.

    This is the check that would have caught `--dimension searchAppearance`.
    """
    bad = []
    for doc, line, script, args in _iter_invocations():
        src = _script_source(script)
        if src is None:
            continue
        for flag, value in re.findall(r"(?<![\w-])(--[\w-]+)[= ]([\w-]+)", args):
            # Find a choices=[...] within the add_argument block that declares this flag.
            m = re.search(
                rf'["\']{re.escape(flag)}["\'][^)]*?choices=\[([^\]]*)\]',
                src,
                re.S,
            )
            if not m:
                continue
            choices = set(re.findall(r"[\"']([\w-]+)[\"']", m.group(1)))
            if value.isupper() or value.startswith("["):
                continue  # placeholder like URL / N, not a literal value
            if value not in choices:
                bad.append(
                    f"{doc}:{line} -> {script} {flag}={value} not in {sorted(choices)}"
                )
    assert not bad, "documented commands pass values outside the flag's choices:\n  " + "\n  ".join(bad)


@pytest.mark.parametrize("dimension", ["searchAppearance", "query", "page", "date"])
def test_gsc_query_accepts_the_api_dimensions(dimension):
    """gsc_query.py must accept the dimensions the Search Analytics API defines.

    searchAppearance is the one that matters: it is the only way to ask whether a
    given rich-result type still returns data, which is exactly the open FAQ
    question in references/schema-types.md.
    """
    src = _script_source("gsc_query.py")
    m = re.search(r'"--dimension",.*?choices=\[([^\]]*)\]', src, re.S)
    assert m, "gsc_query.py no longer declares --dimension choices"
    choices = set(re.findall(r'"([\w-]+)"', m.group(1)))
    assert dimension in choices, (
        f"gsc_query.py --dimension does not accept '{dimension}'. "
        f"Declared: {sorted(choices)}"
    )
