#!/usr/bin/env python3
"""Run generate_report.py for the GitHub Action in action.yml.

CI-only (not shipped in the plugin). The action's inputs arrive as SEO_*
environment variables, never interpolated into a shell, so a URL or path
cannot inject commands. This script turns them into generate_report.py
arguments, runs the audit, writes the digest to the job summary, sets the
step outputs, and decides the exit code:

  0  gate passed, or no gate set
  1  gate failed (--fail-under / --fail-on)
  3  gate inconclusive (too few checks measured, or the site answered 429);
     with SEO_INCONCLUSIVE=warn (the default) this is a warning and exit 0
  2  bad input, or the audit did not produce a summary

Run locally to see what the action would do:

    SEO_URL=https://example.com SEO_FAIL_ON=critical python3 scripts/github_action.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
EXIT_BAD_INPUT = 2
EXIT_INCONCLUSIVE = 3
# Must equal generate_report.MIN_MEASURED_FOR_GATE (a test checks it).
MIN_MEASURED = 5
# GitHub caps one step's job summary at 1 MiB.
STEP_SUMMARY_LIMIT = 1024 * 1024 - 4096


class InputError(ValueError):
    pass


def _flag(env: dict, name: str) -> bool:
    value = (env.get(name) or "").strip().lower()
    if value in ("", "false", "0", "no"):
        return False
    if value in ("true", "1", "yes"):
        return True
    raise InputError(f"{name} must be true or false, got {value!r}")


def build_args(env: dict) -> tuple[list[str], dict]:
    """generate_report.py arguments from the action inputs, plus the paths it will write."""
    url = (env.get("SEO_URL") or "").strip()
    if not url.startswith(("http://", "https://")):
        raise InputError(f"url must start with http:// or https://, got {url!r}")
    out_dir = Path(env.get("SEO_OUTPUT_DIR") or "seo-report")
    paths = {"summary": out_dir / "summary.json", "digest": out_dir / "digest.md", "report": None}
    args = [url, "--json", str(paths["summary"]), "--digest", str(paths["digest"])]

    quick = _flag(env, "SEO_QUICK")
    if quick:
        args.append("--quick")
    if _flag(env, "SEO_REPORT"):
        if quick:
            raise InputError("report: true cannot be combined with quick: true (a quick check is not a Health Score)")
        paths["report"] = out_dir / "report.html"
        args += ["--format", "html", "--output", str(paths["report"])]
    else:
        args += ["--format", "none"]

    fail_under = (env.get("SEO_FAIL_UNDER") or "").strip()
    if fail_under:
        if quick:
            raise InputError("fail-under cannot be combined with quick: true; use fail-on, or run the full audit")
        if not fail_under.isdigit() or not 0 <= int(fail_under) <= 100:
            raise InputError(f"fail-under must be a whole number from 0 to 100, got {fail_under!r}")
        args += ["--fail-under", fail_under]
    fail_on = (env.get("SEO_FAIL_ON") or "").strip().lower()
    if fail_on:
        if fail_on not in ("critical", "warning"):
            raise InputError(f"fail-on must be critical or warning, got {fail_on!r}")
        args += ["--fail-on", fail_on]

    delay = (env.get("SEO_DELAY") or "").strip()
    if delay:
        try:
            if not 0 <= float(delay) <= 30:
                raise ValueError
        except ValueError:
            raise InputError(f"delay must be a number of seconds from 0 to 30, got {delay!r}") from None
        args += ["--delay", delay]
    elif _flag(env, "SEO_POLITE"):
        args.append("--polite")

    previous = (env.get("SEO_PREVIOUS") or "").strip()
    if previous:
        if Path(previous).is_file():
            args += ["--previous", previous]
        else:
            # The first scheduled run has nothing to compare with; that is not an error.
            print(f"::notice::No previous summary at {previous}; this run has no comparison.")

    max_findings = (env.get("SEO_DIGEST_MAX_FINDINGS") or "").strip()
    if max_findings:
        if not max_findings.isdigit() or int(max_findings) < 1:
            raise InputError(f"digest-max-findings must be a positive whole number, got {max_findings!r}")
        args += ["--digest-max-findings", max_findings]

    if _flag({"v": env.get("SEO_ANNOTATIONS", "true")}, "v"):
        args.append("--github-annotations")

    inconclusive = (env.get("SEO_INCONCLUSIVE") or "warn").strip().lower()
    if inconclusive not in ("warn", "fail"):
        raise InputError(f"inconclusive must be warn or fail, got {inconclusive!r}")
    paths["inconclusive"] = inconclusive
    paths["out_dir"] = out_dir
    return args, paths


def read_summary(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def score_text(summary: dict) -> str:
    """The score as the summary states it; never a number the summary did not give."""
    if summary.get("scope") == "quick":
        return f"{summary.get('overall')} (quick check, not a Health Score)"
    measured = summary.get("measured_categories") or 0
    if measured < MIN_MEASURED or summary.get("overall") is None:
        return "not scored"
    return str(summary["overall"])


def write_outputs(env: dict, values: dict) -> None:
    target = env.get("GITHUB_OUTPUT")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as fh:
        for key, value in values.items():
            text = "" if value is None else str(value).replace("\r", " ").replace("\n", " ")
            fh.write(f"{key}={text}\n")


def write_step_summary(env: dict, digest_path: Path, result: str) -> None:
    target = env.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    try:
        digest = digest_path.read_text(encoding="utf-8")
    except OSError:
        digest = "_The audit wrote no digest; see the step log._\n"
    if len(digest.encode("utf-8")) > STEP_SUMMARY_LIMIT:
        digest = digest.encode("utf-8")[:STEP_SUMMARY_LIMIT].decode("utf-8", "ignore") + "\n\n… cut to fit the job summary\n"
    with open(target, "a", encoding="utf-8") as fh:
        fh.write(f"## SEO audit: gate {result}\n\n{digest}\n")


def run(env: dict | None = None) -> int:
    env = dict(os.environ if env is None else env)
    try:
        args, paths = build_args(env)
    except InputError as err:
        print(f"::error::{err}")
        return EXIT_BAD_INPUT
    paths["out_dir"].mkdir(parents=True, exist_ok=True)
    print("generate_report.py " + " ".join(args), flush=True)
    code = subprocess.call([sys.executable, str(SCRIPTS / "generate_report.py"), *args])

    summary = read_summary(paths["summary"])
    if summary is None:
        print(f"::error::The audit exited {code} without writing {paths['summary']}.")
        write_outputs(env, {"result": "error", "exit-code": code or EXIT_BAD_INPUT})
        return code or EXIT_BAD_INPUT

    gate = summary.get("gate") or {}
    result = gate.get("result") or "not set"
    write_step_summary(env, paths["digest"], result)
    final = code
    if code == EXIT_INCONCLUSIVE and paths["inconclusive"] == "warn":
        reasons = "; ".join(gate.get("reasons") or []) or "too few checks were measured"
        print(f"::warning::SEO gate inconclusive, not failing the build: {reasons}")
        final = 0
    write_outputs(env, {
        "score": score_text(summary),
        "result": result,
        "summary-path": paths["summary"],
        "digest-path": paths["digest"],
        "report-path": paths["report"] or "",
        "exit-code": code,
    })
    return final


if __name__ == "__main__":
    sys.exit(run())
