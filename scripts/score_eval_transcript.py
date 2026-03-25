#!/usr/bin/env python3
"""
Score a saved model transcript against assertions in evals/evals.json.

Usage:
  python scripts/score_eval_transcript.py --eval-id 1 --text-file path/to/transcript.txt
  python scripts/score_eval_transcript.py --eval-id 1 --stdin < transcript.txt
  python scripts/score_eval_transcript.py --all-fixtures

Example transcript (synthetic pass): evals/fixtures/eval1_pass.txt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_evals(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_assertion(assertion: dict, text: str) -> tuple[bool, str]:
    """Return (passed, detail)."""
    at = assertion.get("type")
    aid = assertion.get("id", "?")

    if at == "contains_pattern":
        pat = assertion.get("pattern", "")
        try:
            ok = bool(re.search(pat, text, re.IGNORECASE | re.DOTALL))
        except re.error as e:
            return False, f"{aid}: invalid regex: {e}"
        return ok, f"{aid}: pattern {pat!r} -> {ok}"

    if at == "contains_any":
        vals = assertion.get("values") or []
        ok = any(v in text for v in vals)
        return ok, f"{aid}: any of {len(vals)} literals -> {ok}"

    if at == "contains_all":
        vals = assertion.get("values") or []
        ok = all(v in text for v in vals)
        return ok, f"{aid}: all of {len(vals)} literals -> {ok}"

    if at == "not_contains_any":
        vals = assertion.get("values") or []
        hits = [v for v in vals if v in text]
        ok = len(hits) == 0
        return ok, f"{aid}: not any literals (hits={hits!r}) -> {ok}"

    if at == "not_contains_pattern":
        pat = assertion.get("pattern", "")
        try:
            ok = re.search(pat, text, re.IGNORECASE | re.DOTALL) is None
        except re.error as e:
            return False, f"{aid}: invalid regex: {e}"
        return ok, f"{aid}: not pattern {pat!r} -> {ok}"

    return False, f"{aid}: unknown assertion type {at!r}"


def score_eval(eval_obj: dict, text: str) -> dict:
    results = []
    all_pass = True
    for a in eval_obj.get("assertions") or []:
        passed, detail = check_assertion(a, text)
        all_pass = all_pass and passed
        results.append(
            {
                "id": a.get("id"),
                "description": a.get("description"),
                "passed": passed,
                "detail": detail,
            }
        )
    return {
        "eval_id": eval_obj.get("id"),
        "is_negative": bool(eval_obj.get("is_negative")),
        "all_passed": all_pass,
        "assertions": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score transcript vs evals.json assertions")
    parser.add_argument("--evals", type=Path, default=None, help="Path to evals.json")
    parser.add_argument("--eval-id", type=int, help="Eval id from evals.json")
    parser.add_argument("--text-file", type=Path, help="Transcript text file")
    parser.add_argument("--stdin", action="store_true", help="Read transcript from stdin")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    parser.add_argument(
        "--all-fixtures",
        action="store_true",
        help="Run bundled evals/fixtures/*.txt against matching eval id (filename eval{N}_pass.txt)",
    )
    args = parser.parse_args()

    evals_path = args.evals or _root() / "evals" / "evals.json"
    data = load_evals(evals_path)
    evals_list = {e["id"]: e for e in data.get("evals", [])}

    if args.all_fixtures:
        fix_dir = _root() / "evals" / "fixtures"
        if not fix_dir.is_dir():
            print(f"No fixtures dir: {fix_dir}", file=sys.stderr)
            return 2
        outcomes = []
        for fp in sorted(fix_dir.glob("eval*_pass.txt")):
            m = re.match(r"eval(\d+)_pass\.txt$", fp.name)
            if not m:
                continue
            eid = int(m.group(1))
            ev = evals_list.get(eid)
            if not ev:
                print(f"Skip {fp.name}: no eval id {eid}", file=sys.stderr)
                continue
            text = fp.read_text(encoding="utf-8")
            out = score_eval(ev, text)
            outcomes.append({"fixture": fp.name, **out})
        summary = {"fixtures": outcomes, "all_passed": all(o["all_passed"] for o in outcomes)}
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            for o in outcomes:
                st = "PASS" if o["all_passed"] else "FAIL"
                print(f"{st}  {o['fixture']}  eval_id={o['eval_id']}")
                if not o["all_passed"]:
                    for a in o["assertions"]:
                        if not a["passed"]:
                            print(f"    x {a['id']}: {a['detail']}")
        return 0 if summary["all_passed"] else 1

    if args.eval_id is None:
        parser.error("--eval-id is required unless --all-fixtures")
    ev = evals_list.get(args.eval_id)
    if not ev:
        print(f"Unknown eval id {args.eval_id}", file=sys.stderr)
        return 2

    if args.stdin:
        text = sys.stdin.read()
    elif args.text_file:
        tf = args.text_file.expanduser()
        if not tf.is_file():
            print(
                f"Error: transcript file not found: {tf}\n"
                "  Create it with your model reply, or try:\n"
                "    python3 scripts/score_eval_transcript.py --eval-id 1 "
                "--text-file evals/fixtures/eval1_pass.txt\n"
                "  Or pipe: python3 scripts/score_eval_transcript.py --eval-id 1 --stdin < my.txt",
                file=sys.stderr,
            )
            return 2
        text = tf.read_text(encoding="utf-8")
    else:
        parser.error("Provide --text-file or --stdin")

    out = score_eval(ev, text)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"Eval {args.eval_id} (negative={out['is_negative']}): ", end="")
        print("PASS" if out["all_passed"] else "FAIL")
        for a in out["assertions"]:
            sym = "✓" if a["passed"] else "✗"
            print(f"  {sym} {a['id']}: {a['detail']}")

    return 0 if out["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
