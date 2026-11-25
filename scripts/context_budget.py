#!/usr/bin/env python3
"""How much an agent reads before it starts work, per task in SKILL.md's routing table.

Maintainer tool (not shipped in the plugin). The skill's cost to a user is
mostly what the agent reads: SKILL.md on every use, then the files the routing
table names for the task. This script reads that table, resolves each row's
files under references/, and reports the bytes (and approximate tokens) each
task loads. With --check it compares every route against the ceilings in
tests/context_budget.json and fails when one grows past its ceiling, so a
change that quietly makes the skill more expensive is caught in CI.

    python3 scripts/context_budget.py              # table of every route
    python3 scripts/context_budget.py --json       # the same, machine-readable
    python3 scripts/context_budget.py --check      # exit 1 if a route exceeds its ceiling

A row's Read cell may name alternatives ("a or b"); the larger is counted, so
the figure is what the task can cost, not what it usually costs. Shorthand
procedure names ("13-…") resolve to the one procedure file with that number.
Tokens are bytes / 4, a rough figure for English Markdown.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUDGET_FILE = ROOT / "tests" / "context_budget.json"
BYTES_PER_TOKEN = 4
_ROW = re.compile(r"^\|(?P<goal>[^|]+)\|(?P<read>[^|]*)\|(?P<run>[^|]*)\|\s*$")
_TICKED = re.compile(r"`([^`]+)`")
_SHORTHAND = re.compile(r"^(?:procedures/)?(\d{2})-…$")


def routing_rows(skill_text: str) -> list[tuple[str, str]]:
    """(goal, read cell) for each row of the "Goal | Read | Run" table under ### Routing."""
    rows, in_table = [], False
    for line in skill_text.splitlines():
        if line.startswith("| Goal | Read | Run"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            break
        m = _ROW.match(line)
        if not m or set(m.group("goal").strip()) <= {"-"}:
            continue
        rows.append((m.group("goal").strip(), m.group("read").strip()))
    return rows


def resolve(name: str, root: Path = ROOT) -> Path | None:
    """A file named in the Read column, relative to references/."""
    m = _SHORTHAND.match(name)
    if m:
        hits = sorted((root / "references" / "procedures").glob(f"{m.group(1)}-*.md"))
        return hits[0] if len(hits) == 1 else None
    for candidate in (root / "references" / name, root / "references" / "procedures" / name):
        if candidate.is_file():
            return candidate
    return None


def route_files(read_cell: str, root: Path = ROOT) -> tuple[list[Path], list[str]]:
    """Files a row loads: for "a or b", the larger one. Returns (files, names that did not resolve)."""
    files, missing = [], []
    # Split on commas and "with" so each group is one choice; "or" inside a group means alternatives.
    for group in re.split(r",|\bwith\b|·", read_cell):
        names = _TICKED.findall(group)
        if not names:
            continue
        options = [(n, resolve(n, root)) for n in names]
        missing += [n for n, p in options if p is None]
        found = [p for _, p in options if p is not None]
        if found:
            pick = max(found, key=lambda p: p.stat().st_size) if " or " in group else None
            files += [pick] if pick else found
    seen, unique = set(), []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique, missing


def measure(root: Path = ROOT) -> dict:
    skill = root / "SKILL.md"
    skill_bytes = skill.stat().st_size
    routes = []
    for goal, read in routing_rows(skill.read_text(encoding="utf-8")):
        files, missing = route_files(read, root)
        total = skill_bytes + sum(f.stat().st_size for f in files)
        routes.append({
            "goal": goal,
            "files": [str(f.relative_to(root)) for f in files],
            "unresolved": missing,
            "bytes": total,
            "tokens": total // BYTES_PER_TOKEN,
        })
    return {"skill_md_bytes": skill_bytes, "bytes_per_token": BYTES_PER_TOKEN, "routes": routes}


def check(result: dict, budget: dict) -> list[str]:
    """Every way the measured result breaks the recorded ceilings."""
    problems = []
    if result["skill_md_bytes"] > budget["skill_md_max_bytes"]:
        problems.append(f"SKILL.md is {result['skill_md_bytes']:,} bytes; ceiling {budget['skill_md_max_bytes']:,}")
    ceilings = budget.get("routes", {})
    for route in result["routes"]:
        if route["unresolved"]:
            problems.append(f"{route['goal']}: cannot find {', '.join(route['unresolved'])} under references/")
        ceiling = ceilings.get(route["goal"], budget["default_route_max_bytes"])
        if route["bytes"] > ceiling:
            problems.append(f"{route['goal']}: {route['bytes']:,} bytes; ceiling {ceiling:,}")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="What each SKILL.md route makes the agent read")
    parser.add_argument("--json", action="store_true", help="Print the measurement as JSON")
    parser.add_argument("--check", action="store_true",
                        help=f"Exit 1 when a route exceeds its ceiling in {BUDGET_FILE.relative_to(ROOT)}")
    args = parser.parse_args(argv)

    result = measure()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"SKILL.md: {result['skill_md_bytes']:,} bytes (~{result['skill_md_bytes'] // BYTES_PER_TOKEN:,} tokens), "
              "read on every use\n")
        width = max(len(r["goal"]) for r in result["routes"])
        for r in result["routes"]:
            print(f"{r['goal']:<{width}}  {r['bytes']:>7,} B  ~{r['tokens']:>6,} tok  {len(r['files'])} file(s)")
    if args.check:
        budget = json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
        problems = check(result, budget)
        for p in problems:
            print(f"OVER BUDGET: {p}", file=sys.stderr)
        if problems:
            print("Trim the files, or raise the ceiling in tests/context_budget.json in the same PR and say why.",
                  file=sys.stderr)
            return 1
        print("\nAll routes within their ceilings.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
