#!/usr/bin/env python3
"""
Turn repeated AI-answer checks into citation rates with confidence intervals.

AI answers change from run to run. One ChatGPT search that cites a competitor
and not you is an anecdote; the same prompt run ten times, with the site cited
in two of them, is a rate with a known margin of error. This script does the
arithmetic on runs you record, by hand or from any tool you already use. It
calls no AI engine and needs no API key.

Workflow:
  1. Write a grid to fill in:
       python citation_sampling.py --template --prompts prompts.txt \
           --engines chatgpt,perplexity,google-ai-mode --runs 5 --output runs.csv
  2. Run each prompt in a fresh session. For each run record whether the site
     was cited as a source, whether the brand was named, and every domain cited
     (semicolon-separated).
  3. Score it:
       python citation_sampling.py runs.csv --domain example.com --json

CSV columns: date, engine, prompt, run, cited, mentioned, cited_domains.
`cited` may be left blank when cited_domains is filled; it is then derived
from --domain.

Verdicts use a 95% Wilson score interval on the citation rate:
  cited in most runs      lower bound above 50%
  rarely or never cited   upper bound below 30%
  inconsistent            anything between: add runs, or the engine varies
  too few runs            fewer than 5 runs
Two rates whose intervals overlap show no demonstrated difference.

Usage:
    python citation_sampling.py runs.csv --domain example.com
    python citation_sampling.py --template --prompts prompts.txt --engines chatgpt,perplexity --runs 5
"""

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict

Z_95 = 1.959964
MIN_RUNS = 5
MOST_RUNS_LOWER = 0.5
RARELY_UPPER = 0.3
COLUMNS = ["date", "engine", "prompt", "run", "cited", "mentioned", "cited_domains"]
TRUE_VALUES = {"yes", "y", "true", "1", "x"}
FALSE_VALUES = {"no", "n", "false", "0"}

LIMITS = [
    "Every run must be a fresh session (logged out or history off), with location and search mode "
    "noted. Personalised answers are not comparable.",
    "Rates describe the prompts sampled, not every query. Write prompts the way users ask, across "
    "intents, and keep the set fixed between measurements.",
    "The 95% interval is the margin of error of this sample. Engines or months whose intervals overlap "
    "show no demonstrated difference.",
]


def wilson_interval(successes: int, n: int, z: float = Z_95):
    """95% Wilson score interval for a proportion, or None when n is 0."""
    if n <= 0:
        return None
    p = successes / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def verdict(successes: int, n: int) -> str:
    if n < MIN_RUNS:
        return "too few runs"
    low, high = wilson_interval(successes, n)
    if low > MOST_RUNS_LOWER:
        return "cited in most runs"
    if high < RARELY_UPPER:
        return "rarely or never cited"
    return "inconsistent"


def normalize_domain(value: str) -> str:
    host = (value or "").strip().lower()
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split("/", 1)[0].split(":", 1)[0].rstrip(".")
    return host[4:] if host.startswith("www.") else host


def domain_matches(candidate: str, domain: str) -> bool:
    """True for the domain itself or a subdomain of it, never a lookalike."""
    c, d = normalize_domain(candidate), normalize_domain(domain)
    return bool(c) and bool(d) and (c == d or c.endswith("." + d))


def parse_flag(value):
    text = (value or "").strip().lower()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return None


def _pct(interval) -> str:
    return f"{interval[0] * 100:.0f}–{interval[1] * 100:.0f}%"


def _summary(group: list) -> dict:
    n = len(group)
    cited = sum(r["cited"] for r in group)
    interval = wilson_interval(cited, n)
    mentions = [r["mentioned"] for r in group if r["mentioned"] is not None]
    return {
        "runs": n,
        "cited_runs": cited,
        "citation_rate": round(cited / n, 3),
        "ci95": [round(interval[0], 3), round(interval[1], 3)],
        "verdict": verdict(cited, n),
        "mention_rate": round(sum(mentions) / len(mentions), 3) if mentions else None,
    }


def score(rows, domain: str) -> dict:
    """Score recorded runs for `domain`. `rows` are dicts keyed by COLUMNS."""
    runs, skipped, unfilled = [], [], 0
    for line, row in enumerate(rows, start=2):  # line 1 is the CSV header
        engine = (row.get("engine") or "").strip().lower()
        prompt = (row.get("prompt") or "").strip()
        raw_domains = row.get("cited_domains") or ""
        domains = sorted({normalize_domain(d) for d in raw_domains.split(";") if normalize_domain(d)})
        cited_text = (row.get("cited") or "").strip()
        mentioned_text = (row.get("mentioned") or "").strip()

        if not cited_text and not domains and not mentioned_text:
            unfilled += 1
            continue
        cited = parse_flag(cited_text) if cited_text else any(domain_matches(d, domain) for d in domains)
        if not engine or not prompt or cited is None:
            skipped.append(line)
            continue
        runs.append({
            "engine": engine,
            "prompt": prompt,
            "cited": cited,
            "mentioned": parse_flag(mentioned_text),
            "domains": domains,
        })

    if not runs:
        return {
            "error": "no recorded runs to score: fill in cited or cited_domains for at least one row",
            "unfilled_rows": unfilled,
            "skipped_rows": skipped,
        }

    by_engine, by_prompt = defaultdict(list), defaultdict(list)
    for r in runs:
        by_engine[r["engine"]].append(r)
        by_prompt[(r["engine"], r["prompt"])].append(r)

    engines, competitors, share_of_voice, issues = {}, {}, {}, []
    for engine, group in by_engine.items():
        engines[engine] = _summary(group)
        with_domains = [r for r in group if r["domains"]]
        counts = Counter(d for r in with_domains for d in r["domains"] if not domain_matches(d, domain))
        competitors[engine] = [
            [d, k, round(k / len(with_domains), 3)] for d, k in counts.most_common(10)
        ] if with_domains else []
        site_citations = sum(1 for r in with_domains if any(domain_matches(d, domain) for d in r["domains"]))
        total_citations = site_citations + sum(counts.values())
        share_of_voice[engine] = round(site_citations / total_citations, 3) if total_citations else None

        summary = engines[engine]
        interval = summary["ci95"]
        if summary["verdict"] == "rarely or never cited":
            leaders = [d for d, _, rate in competitors[engine] if rate >= 0.5]
            if leaders:
                issues.append(
                    f"⚠️ {normalize_domain(domain)} was rarely or never cited on {engine} "
                    f"({summary['cited_runs']}/{summary['runs']} runs, 95% interval {_pct(interval)}) "
                    f"while {', '.join(leaders[:5])} were cited in at least half of the runs that recorded sources"
                )
            else:
                issues.append(
                    f"ℹ️ {normalize_domain(domain)} was rarely or never cited on {engine} "
                    f"({summary['cited_runs']}/{summary['runs']} runs, 95% interval {_pct(interval)}); "
                    "record cited_domains to see who is cited instead"
                )
        elif summary["verdict"] == "inconsistent":
            issues.append(
                f"ℹ️ Citation on {engine} is inconsistent ({summary['cited_runs']}/{summary['runs']} runs, "
                f"95% interval {_pct(interval)}); add runs before drawing conclusions"
            )

    prompts = [
        {"engine": engine, "prompt": prompt, **_summary(group)}
        for (engine, prompt), group in sorted(by_prompt.items())
    ]
    thin = [p for p in prompts if p["verdict"] == "too few runs"]
    if thin:
        issues.append(
            f"ℹ️ {len(thin)} prompt/engine pair(s) have fewer than {MIN_RUNS} runs and get no verdict"
        )
    if skipped:
        shown = ", ".join(str(n) for n in skipped[:10])
        issues.append(
            f"ℹ️ {len(skipped)} row(s) skipped (missing engine or prompt, or an unreadable cited value) "
            f"on CSV line(s) {shown}"
        )

    return {
        "domain": normalize_domain(domain),
        "runs_scored": len(runs),
        "unfilled_rows": unfilled,
        "skipped_rows": skipped,
        "engines": engines,
        "share_of_voice": share_of_voice,
        "top_cited_domains": competitors,
        "prompts": prompts,
        "issues": issues,
        "limits": LIMITS,
        "error": None,
    }


def template_rows(prompts: list, engines: list, runs: int):
    for prompt in prompts:
        for engine in engines:
            for run in range(1, runs + 1):
                yield {"date": "", "engine": engine, "prompt": prompt, "run": run,
                       "cited": "", "mentioned": "", "cited_domains": ""}


def read_rows(path: str):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fields = set(reader.fieldnames or [])
        missing = {"engine", "prompt"} - fields
        if missing or not ({"cited", "cited_domains"} & fields):
            raise ValueError(
                f"CSV needs engine, prompt and cited or cited_domains columns; found {sorted(fields)}"
            )
        return list(reader)


def main():
    parser = argparse.ArgumentParser(description="Citation rates with confidence intervals from recorded AI-answer runs")
    parser.add_argument("csv", nargs="?", help="Recorded runs (CSV with engine, prompt, cited / cited_domains)")
    parser.add_argument("--domain", help="The site's domain, e.g. example.com (required to score)")
    parser.add_argument("--template", action="store_true", help="Write an empty prompt × engine × run grid instead of scoring")
    parser.add_argument("--prompts", help="With --template: text file, one prompt per line")
    parser.add_argument("--engines", help="With --template: comma-separated engine names, e.g. chatgpt,perplexity")
    parser.add_argument("--runs", type=int, default=MIN_RUNS, help=f"With --template: runs per prompt and engine (default: {MIN_RUNS})")
    parser.add_argument("--output", "-o", help="With --template: write the grid here instead of stdout")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.template:
        if not args.prompts or not args.engines:
            parser.error("--template needs --prompts and --engines")
        if args.runs < 1:
            parser.error("--runs must be at least 1")
        with open(args.prompts, encoding="utf-8") as fh:
            prompts = [line.strip() for line in fh if line.strip()]
        engines = [e.strip().lower() for e in args.engines.split(",") if e.strip()]
        out = open(args.output, "w", newline="", encoding="utf-8") if args.output else sys.stdout
        try:
            writer = csv.DictWriter(out, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(template_rows(prompts, engines, args.runs))
        finally:
            if args.output:
                out.close()
        if args.output:
            print(f"Wrote {len(prompts) * len(engines) * args.runs} rows to {args.output}", file=sys.stderr)
        return

    if not args.csv or not args.domain:
        parser.error("scoring needs a CSV file and --domain")
    try:
        result = score(read_rows(args.csv), args.domain)
    except (OSError, ValueError) as exc:
        result = {"error": str(exc)}

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get("error"):
            sys.exit(1)
        return
    if result.get("error"):
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"AI citation sampling — {result['domain']} ({result['runs_scored']} runs)")
    print("=" * 60)
    for engine, s in result["engines"].items():
        sov = result["share_of_voice"].get(engine)
        sov_text = f", share of voice {sov * 100:.0f}%" if sov is not None else ""
        print(f"  {engine}: cited {s['cited_runs']}/{s['runs']} ({_pct(s['ci95'])} 95% CI) -> {s['verdict']}{sov_text}")
        for d, k, rate in result["top_cited_domains"].get(engine, [])[:5]:
            print(f"      {d}: {k} runs ({rate * 100:.0f}%)")
    if result["issues"]:
        print(f"\nIssues ({len(result['issues'])}):")
        for issue in result["issues"]:
            print(f"  {issue}")
    print("\nLimits:")
    for limit in result["limits"]:
        print(f"  - {limit}")


if __name__ == "__main__":
    main()
