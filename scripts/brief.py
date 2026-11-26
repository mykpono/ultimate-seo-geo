#!/usr/bin/env python3
"""Run one audit script and print a short view of its output; keep the full output in a file.

Most scripts print a few KB, but some print far more than an agent needs to
read: site_graph.py --json writes the whole crawl graph (megabytes on a real
site), and the link checkers list every link. This wrapper runs the script,
saves its full stdout to a file, and prints a compacted copy: long lists are
cut to their first items with a note of how many were left out, long strings
are cut, and deep nesting is folded. The agent reads the short view and opens
the saved file only for the detail it needs.

    python scripts/brief.py internal_links.py https://example.com --json
    python scripts/brief.py --max-items 5 --save out/graph.json site_graph.py https://example.com --json

Only scripts in this directory can be run, by file name. The script's exit
code is passed through, so a failing check still fails.
"""

import argparse
import json
import os
import re
import subprocess
import sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_NAME = re.compile(r"^[A-Za-z0-9_-]+\.py$")
DEFAULT_MAX_ITEMS = 8
DEFAULT_MAX_CHARS = 300
DEFAULT_MAX_DEPTH = 6
# A dict this wide is data, not a record, and is cut like a list.
MAX_RECORD_KEYS = 60
_DATA_KEY = re.compile(r"^(https?://|/)")
# Non-JSON output: lines kept from the start and the end.
TEXT_HEAD_LINES = 60
TEXT_TAIL_LINES = 20


def _is_data_map(value: dict, max_items: int) -> bool:
    """A dict keyed by URLs or paths (pages, links), or one too wide to be a record."""
    if len(value) <= max_items:
        return False
    if len(value) > MAX_RECORD_KEYS:
        return True
    keys = [k for k in value if isinstance(k, str)]
    return bool(keys) and sum(1 for k in keys if _DATA_KEY.match(k)) * 2 > len(keys)


def compact(value, max_items: int = DEFAULT_MAX_ITEMS, max_chars: int = DEFAULT_MAX_CHARS,
            max_depth: int = DEFAULT_MAX_DEPTH, _depth: int = 0):
    """A smaller copy of a JSON value: same keys and order, lists and strings cut, deep levels folded.

    Every cut says what it cut, so a reader never mistakes a shortened list for
    the whole one.
    """
    if isinstance(value, str):
        return value if len(value) <= max_chars else f"{value[:max_chars]}… [{len(value) - max_chars} more chars]"
    if isinstance(value, dict):
        if _depth >= max_depth and value:
            return f"{{… {len(value)} keys}}"
        items = list(value.items())
        cut = _is_data_map(value, max_items)
        kept = {k: compact(v, max_items, max_chars, max_depth, _depth + 1)
                for k, v in (items[:max_items] if cut else items)}
        if cut:
            kept["…"] = f"{len(items) - max_items} more keys"
        return kept
    if isinstance(value, list):
        if _depth >= max_depth and value:
            return f"[… {len(value)} items]"
        kept = [compact(v, max_items, max_chars, max_depth, _depth + 1) for v in value[:max_items]]
        if len(value) > max_items:
            kept.append(f"… {len(value) - max_items} more items")
        return kept
    return value


def compact_text(text: str, head: int = TEXT_HEAD_LINES, tail: int = TEXT_TAIL_LINES,
                 max_chars: int = DEFAULT_MAX_CHARS) -> str:
    lines = [line if len(line) <= max_chars else line[:max_chars] + "…" for line in text.splitlines()]
    if len(lines) <= head + tail:
        return "\n".join(lines)
    return "\n".join(lines[:head] + [f"… {len(lines) - head - tail} lines left out …"] + lines[-tail:])


def default_save_path(script: str) -> str:
    return f"{script[:-3]}.full.out"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an audit script, save its full output to a file, and print a short view.",
        usage="brief.py [options] SCRIPT.py [script arguments ...]",
    )
    parser.add_argument("--max-items", type=int, default=DEFAULT_MAX_ITEMS, metavar="N",
                        help=f"Items kept from each list (default: {DEFAULT_MAX_ITEMS})")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS, metavar="N",
                        help=f"Characters kept from each string (default: {DEFAULT_MAX_CHARS})")
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH, metavar="N",
                        help=f"Nesting levels shown before folding (default: {DEFAULT_MAX_DEPTH})")
    parser.add_argument("--save", metavar="PATH",
                        help="Where to write the full output (default: SCRIPT.full.out in the current directory)")
    parser.add_argument("script", help="Script file name in scripts/, e.g. internal_links.py")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the script unchanged")
    opts = parser.parse_args(argv)

    if not SCRIPT_NAME.match(opts.script) or opts.script == os.path.basename(__file__):
        parser.error(f"{opts.script!r} is not a script file name (expected something like internal_links.py)")
    path = os.path.join(SCRIPTS_DIR, opts.script)
    if not os.path.isfile(path):
        parser.error(f"no script named {opts.script} in {SCRIPTS_DIR}")
    for name in ("max_items", "max_chars", "max_depth"):
        if getattr(opts, name) < 1:
            parser.error(f"--{name.replace('_', '-')} must be at least 1")

    proc = subprocess.run([sys.executable, path, *opts.args], stdout=subprocess.PIPE, text=True,
                          encoding="utf-8", errors="replace")
    out = proc.stdout
    save = opts.save or default_save_path(opts.script)
    save_dir = os.path.dirname(save)
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
    with open(save, "w", encoding="utf-8") as fh:
        fh.write(out)

    try:
        data = json.loads(out)
    except ValueError:
        shown = compact_text(out, max_chars=opts.max_chars)
        kind = "text"
    else:
        shown = json.dumps(compact(data, opts.max_items, opts.max_chars, opts.max_depth), indent=1,
                           ensure_ascii=False)
        kind = "json"
    print(shown)
    print(f"[brief.py: {opts.script} exit {proc.returncode}; showed {len(shown):,} of {len(out):,} chars "
          f"({kind}); full output in {os.path.abspath(save)}]", file=sys.stderr)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
