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

CSV columns: date, engine, prompt, run, cited, mentioned, cited_domains, answer.
`cited` may be left blank when cited_domains is filled; it is then derived
from --domain. `answer` (optional) holds the answer text, pasted whole.

Brand facts: with --facts brand.json and an answer column, each answer that
names the brand is checked against the official facts (founding year, HQ,
founders, prices, yes/no claims, known-false phrases). Only sentences that name
the brand are read, and a value counts only when it closely follows its keyword
("founded in 2016", "headquartered in Austin"); a statement in parentheses that
do not name the brand, or with another listed brand between the brand and the
keyword, is left out. What it cannot read, it does not judge: a fact the answer
states through a pronoun ("It was founded in...") counts as not stated.

Verdicts use a 95% Wilson score interval on the citation rate:
  cited in most runs      lower bound above 50%
  rarely or never cited   upper bound below 30%
  inconsistent            anything between: add runs, or the engine varies
  too few runs            fewer than 5 runs
Two rates whose intervals overlap show no demonstrated difference.

Usage:
    python citation_sampling.py runs.csv --domain example.com
    python citation_sampling.py runs.csv --facts brand.json --json
    python citation_sampling.py --template --prompts prompts.txt --engines chatgpt,perplexity --runs 5
"""

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict

Z_95 = 1.959964
MIN_RUNS = 5
MOST_RUNS_LOWER = 0.5
RARELY_UPPER = 0.3
COLUMNS = ["date", "engine", "prompt", "run", "cited", "mentioned", "cited_domains", "answer"]
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


# ---------------------------------------------------------------------------
# Brand facts: are AI answers right about the brand?
# ---------------------------------------------------------------------------

FACT_KEYWORDS = {
    "year": ("founded", "established", "launched", "started", "incorporated", "created in", "since"),
    "place": ("headquartered", "headquarters", "based in", "hq", "located in", "offices in"),
    "people": ("co-founded", "cofounded", "founded", "co-founder", "cofounder", "founder", "created", "started"),
    "money": ("price", "pricing", "costs", "cost", "starts at", "starting at", "per month", "/month", "a month",
              "per user", "plan", "plans", "subscription"),
}
FACT_TYPES = ("year", "place", "people", "money", "claim")
VALUE_WINDOW = 60  # characters after a keyword in which its value must appear
YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
MONEY_RE = re.compile(r"(?:[$€£]\s?(\d[\d,]*(?:\.\d+)?)|(\d[\d,]*(?:\.\d+)?)\s?(?:USD|EUR|GBP|dollars))", re.I)
FREE_RE = re.compile(r"\bfree\b", re.I)
# Where a value stops belonging to the keyword: a contrast, a new clause about someone else.
WINDOW_STOP = re.compile(r";|\bcompared\b|\bwhile\b|\bwhereas\b|\bvs\.?\b|\bversus\b|\bunlike\b|\bbut\b|\bthan\b", re.I)
NEGATION = re.compile(r"\b(?:no|not|never|without|lacks?|n't|doesn't|does not|isn't|is not|don't|do not)\b[^.;,]{0,25}$", re.I)
OPENER_MAX = 15  # "Originally founded in 2016, Acme ...": a keyword may open the sentence before the brand
PEOPLE_VERBS = ("co-founded", "cofounded", "founded", "created", "started")  # names follow "by"
PRONOUN_OPENER = re.compile(r"^(?:It|Its|It's|The company|The company's|The platform|The tool|The startup)\b")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])|\n+")


def load_facts(path: str) -> dict:
    """Read and validate a brand facts file. Raises ValueError on anything malformed."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or not str(data.get("brand") or "").strip():
        raise ValueError(f"{path}: needs a \"brand\" name")
    facts = data.get("facts") or []
    if not isinstance(facts, list) or not (facts or data.get("false_claims")):
        raise ValueError(f"{path}: needs a \"facts\" list or \"false_claims\"")
    for i, fact in enumerate(facts):
        if not isinstance(fact, dict) or fact.get("type") not in FACT_TYPES or not fact.get("field"):
            raise ValueError(f"{path}: fact {i + 1} needs \"field\" and a \"type\" of {', '.join(FACT_TYPES)}")
        if fact["type"] == "claim":
            if not isinstance(fact.get("value"), bool) or not (fact.get("true_phrases") or fact.get("false_phrases")):
                raise ValueError(f"{path}: claim \"{fact['field']}\" needs a true/false \"value\" and true_phrases or false_phrases")
        elif fact.get("value") in (None, "", []):
            raise ValueError(f"{path}: fact \"{fact['field']}\" has no \"value\"")
    return data


def _names(data: dict) -> list:
    return [n for n in [data["brand"], *(data.get("aliases") or [])] if str(n).strip()]


def _find(text: str, phrase: str):
    return re.search(r"(?<![\w])" + re.escape(phrase) + r"(?![\w])", text, re.I)


def brand_sentences(answer: str, names: list, others=()) -> list:
    """[(text to match, text to quote)] for sentences about the brand.

    A sentence that names the brand, and the one right after it when that opens
    with a pronoun ("It was founded in 2019") and the brand sentence names no
    other listed company. The pronoun is read as the brand for matching; the
    quote keeps the answer's own words.
    """
    parts = [x.strip() for x in SENTENCE_RE.split(answer or "") if x.strip()]
    out = []
    for i, sentence in enumerate(parts):
        if any(_find(sentence, n) for n in names):
            out.append((sentence, sentence))
            continue
        # Only straight after a sentence already read as the brand's (which may itself be a
        # carried pronoun sentence), and never after one that also names a competitor.
        m = PRONOUN_OPENER.match(sentence)
        if m and i and out and out[-1][1] == parts[i - 1] and not any(_find(out[-1][0], o) for o in others):
            out.append((names[0] + sentence[m.end():], sentence))
    return out


def _attached(sentence: str, start: int, names: list, others: list) -> bool:
    """Is the keyword at `start` about the brand, not a neighbour in the same sentence?

    Not when it sits in parentheses that do not name the brand ("Mixpanel
    (founded 2009)"), nor when another listed brand stands between the nearest
    brand mention before it and the keyword.
    """
    open_paren = sentence.rfind("(", 0, start)
    if open_paren > sentence.rfind(")", 0, start):
        close = sentence.find(")", start)
        inside = sentence[open_paren:close if close != -1 else len(sentence)]
        if not any(_find(inside, n) for n in names):
            return False
    before = [m.end() for n in names for m in re.finditer(r"(?<![\w])" + re.escape(n) + r"(?![\w])", sentence[:start], re.I)]
    if not before:
        # The brand comes later: only an opening phrase ("Founded in 2016, Acme ...") is about it.
        # "Unlike Amplitude, which is based in San Francisco, Acme ..." is not.
        return start <= OPENER_MAX
    last_brand = max(before)
    between = sentence[last_brand:start]
    return not any(_find(between, o) for o in others)


def _amount(text: str) -> float:
    return float(text.replace(",", ""))


def check_fact(fact: dict, sentences: list, names: list, others: list) -> list:
    """[(status, sentence, stated)] for every statement of this fact; status is correct or wrong."""
    kind = fact["type"]
    out = []
    if kind == "claim":
        for sentence, quote in sentences:
            false_hit = next((p for p in fact.get("false_phrases") or [] if _find(sentence, p)), None)
            true_hit = None if false_hit else next((p for p in fact.get("true_phrases") or [] if _find(sentence, p)), None)
            hit = false_hit or true_hit
            if not hit or not _attached(sentence, _find(sentence, hit).start(), names, others):
                continue
            # "does not have a free plan" states the claim's opposite without being listed.
            negated = bool(NEGATION.search(sentence[:_find(sentence, hit).start()]))
            says = bool(true_hit) != negated
            out.append(("correct" if says == fact["value"] else "wrong", quote, hit))
        return out
    keywords = fact.get("keywords") or FACT_KEYWORDS[kind]
    official = fact["value"] if isinstance(fact["value"], list) else [fact["value"]]
    for sentence, quote in sentences:
        for kw in keywords:
            m = _find(sentence, kw)
            if not m or not _attached(sentence, m.start(), names, others):
                continue
            window = sentence[m.end():m.end() + VALUE_WINDOW]
            if kind == "people" and kw in PEOPLE_VERBS:
                by = _find(window, "by")
                if not by:
                    continue  # "founded in 2016" says when, not who
                window = window[by.end():]
            stops = [x.start() for x in [WINDOW_STOP.search(window), *(_find(window, o) for o in others)] if x]
            if stops:
                window = window[:min(stops)]
            if kind == "year":
                stated = YEAR_RE.findall(window)
                if not stated:
                    continue
                ok = any(str(v) == stated[0] for v in official)
                out.append(("correct" if ok else "wrong", quote, stated[0]))
            elif kind == "money":
                amounts = [_amount(a or b) for a, b in MONEY_RE.findall(window)] + ([0.0] if FREE_RE.search(window) else [])
                if not amounts:
                    continue
                allowed = {float(v) for v in official}
                ok = all(a in allowed for a in amounts)
                out.append(("correct" if ok else "wrong", quote, ", ".join(f"{a:g}" for a in amounts)))
            else:  # place, people: any official spelling in the sentence
                spellings = [str(v) for v in official] + [str(a) for a in fact.get("aliases") or []]
                if kind == "people":
                    spellings += [str(v).split()[-1] for v in official if len(str(v).split()) > 1]
                ok = any(_find(window if kind == "people" else sentence, sp) for sp in spellings)
                out.append(("correct" if ok else "wrong", quote, window.strip()[:VALUE_WINDOW]))
            break  # one statement per fact per sentence
    return out


def check_brand_facts(rows, data: dict) -> dict:
    """Per fact: how often answers state it, and how often they get it wrong, by engine."""
    names, others = _names(data), [o for o in data.get("others") or [] if str(o).strip()]
    facts = list(data.get("facts") or [])
    for claim in data.get("false_claims") or []:
        phrase = claim if isinstance(claim, str) else claim.get("phrase")
        if phrase:
            facts.append({"field": f"false claim: {phrase}", "type": "claim", "value": False, "true_phrases": [phrase],
                          "source": None if isinstance(claim, str) else claim.get("source")})
    answered, naming = 0, 0
    tally = {f["field"]: {"stated": 0, "correct": 0, "wrong": 0, "by_engine": defaultdict(lambda: [0, 0]), "wrong_examples": []}
             for f in facts}
    for row in rows:
        answer = (row.get("answer") or "").strip()
        if not answer:
            continue
        answered += 1
        sentences = brand_sentences(answer, names, others)
        if not sentences:
            continue
        naming += 1
        engine = (row.get("engine") or "").strip().lower() or "unknown"
        for fact in facts:
            results = check_fact(fact, sentences, names, others)
            if not results:
                continue
            t = tally[fact["field"]]
            wrong = next((r for r in results if r[0] == "wrong"), None)  # an answer is wrong if any statement is
            t["stated"] += 1
            t["by_engine"][engine][0] += 1
            if wrong:
                t["wrong"] += 1
                t["by_engine"][engine][1] += 1
                if len(t["wrong_examples"]) < 5:
                    t["wrong_examples"].append({"engine": engine, "prompt": (row.get("prompt") or "").strip(),
                                                "run": row.get("run"), "sentence": wrong[1], "stated": wrong[2]})
            else:
                t["correct"] += 1
    results, issues = [], []
    for fact in facts:
        t = tally[fact["field"]]
        entry = {
            "field": fact["field"], "type": fact["type"],
            "official": fact.get("value"), "source": fact.get("source"),
            "stated_in": t["stated"], "correct": t["correct"], "wrong": t["wrong"],
            "wrong_rate": round(t["wrong"] / t["stated"], 3) if t["stated"] else None,
            "wrong_ci95": list(wilson_interval(t["wrong"], t["stated"])) if t["stated"] else None,
            "by_engine": {e: {"stated": v[0], "wrong": v[1]} for e, v in sorted(t["by_engine"].items())},
            "wrong_examples": t["wrong_examples"],
        }
        results.append(entry)
        if not t["wrong"]:
            continue
        ex = t["wrong_examples"][0]
        where = fact.get("source") or "the page that states this fact"
        profiles = ", ".join(data.get("profiles") or []) or "your third-party profiles (Wikipedia, Wikidata, Crunchbase, LinkedIn, G2)"
        issues.append({
            "severity": "medium" if t["wrong"] * 2 >= t["stated"] else "low",
            "code": f"brand_fact.{re.sub(r'[^a-z0-9]+', '-', fact['field'].lower()).strip('-')}",
            "finding": (f"AI answers state {data['brand']}'s {fact['field']} wrongly in {t['wrong']} of {t['stated']} answers "
                        f"that state it ({', '.join(f'{e} {v[1]}/{v[0]}' for e, v in sorted(t['by_engine'].items()) if v[1])})."),
            "evidence": f"{ex['engine']}, \"{ex['prompt']}\" run {ex['run']}: \"{ex['sentence'][:220]}\"",
            "impact": "Buyers who ask an AI assistant get a wrong fact about the brand, and engines repeat what their sources say.",
            "fix": (f"State the fact plainly and early on {where} (one sentence, e.g. \"{data['brand']} {_fact_sentence(fact)}\"), "
                    f"then correct {profiles}. Re-run the same prompts in a month."),
            "confidence": "Hypothesis" if fact["type"] == "money" else "Likely",
            "falsifiability": ("Wrong if the quoted sentence is about another product or an older plan; read the example before editing."
                               if fact["type"] == "money" else "Wrong if the quoted sentence is about another company."),
            "leading_indicator": f"Wrong-answer rate for {fact['field']} on the same prompts, one month after the fix.",
            "lane": "Human",
        })
    return {
        "brand": data["brand"],
        "answers_recorded": answered,
        "answers_naming_brand": naming,
        "facts": results,
        "issues": issues,
        "limits": [
            "Only sentences that name the brand are read; a fact stated through a pronoun counts as not stated.",
            "A price differs from the official list when the answer quotes an old or regional plan; money findings are hypotheses until read.",
            "Answers without an answer column are skipped: paste the whole answer text to have it checked.",
        ],
    }


def _fact_sentence(fact: dict) -> str:
    value = fact.get("value")
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    return {"year": f"was founded in {value}", "place": f"is headquartered in {value}", "people": f"was founded by {value}",
            "money": f"starts at {value}", "claim": f"{'has' if value else 'does not have'} a {fact['field']}"}.get(
        fact["type"], f"{fact['field']}: {value}")


def template_rows(prompts: list, engines: list, runs: int):
    for prompt in prompts:
        for engine in engines:
            for run in range(1, runs + 1):
                yield {"date": "", "engine": engine, "prompt": prompt, "run": run,
                       "cited": "", "mentioned": "", "cited_domains": "", "answer": ""}


def read_rows(path: str, need_citation: bool = True):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fields = set(reader.fieldnames or [])
        missing = {"engine", "prompt"} - fields
        if missing or (need_citation and not ({"cited", "cited_domains"} & fields)):
            raise ValueError(
                f"CSV needs engine, prompt and cited or cited_domains columns; found {sorted(fields)}"
            )
        if not need_citation and "answer" not in fields:
            raise ValueError(f"CSV needs an answer column to check brand facts; found {sorted(fields)}")
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
    parser.add_argument("--facts", metavar="PATH",
                        help="Brand facts JSON: check the answer column for wrong statements about the brand")
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

    if not args.csv or not (args.domain or args.facts):
        parser.error("scoring needs a CSV file and --domain (or --facts to check brand facts only)")
    facts = None
    if args.facts:
        try:
            facts = load_facts(args.facts)
        except (OSError, ValueError) as exc:
            parser.error(f"--facts: {exc}")
    try:
        rows = read_rows(args.csv, need_citation=bool(args.domain))
        result = score(rows, args.domain) if args.domain else {"error": None, "issues": [], "limits": []}
        if facts is not None and not result.get("error"):
            result["brand_facts"] = check_brand_facts(rows, facts)
            result["issues"] = result["issues"] + result["brand_facts"]["issues"]
            if not result["brand_facts"]["answers_recorded"]:
                result["brand_facts"]["note"] = "No answer text in the CSV: add an answer column to check brand facts."
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

    if "engines" in result:
        print(f"AI citation sampling — {result['domain']} ({result['runs_scored']} runs)")
        print("=" * 60)
        for engine, s in result["engines"].items():
            sov = result["share_of_voice"].get(engine)
            sov_text = f", share of voice {sov * 100:.0f}%" if sov is not None else ""
            print(f"  {engine}: cited {s['cited_runs']}/{s['runs']} ({_pct(s['ci95'])} 95% CI) -> {s['verdict']}{sov_text}")
            for d, k, rate in result["top_cited_domains"].get(engine, [])[:5]:
                print(f"      {d}: {k} runs ({rate * 100:.0f}%)")
    bf = result.get("brand_facts")
    if bf:
        print(f"\nBrand facts — {bf['brand']} ({bf['answers_naming_brand']} of {bf['answers_recorded']} answers name it)")
        if bf.get("note"):
            print(f"  {bf['note']}")
        for f in bf["facts"]:
            if not f["stated_in"]:
                print(f"  {f['field']}: not stated in any answer")
                continue
            print(f"  {f['field']}: wrong in {f['wrong']}/{f['stated_in']} answers that state it ({_pct(f['wrong_ci95'])} 95% CI)")
            for ex in f["wrong_examples"][:2]:
                print(f"      {ex['engine']}: \"{ex['sentence'][:140]}\"")
    if result["issues"]:
        print(f"\nIssues ({len(result['issues'])}):")
        for issue in result["issues"]:
            print(f"  {issue['finding'] if isinstance(issue, dict) else issue}")
    limits = result.get("limits", []) + (bf["limits"] if bf else [])
    if limits:
        print("\nLimits:")
        for limit in limits:
            print(f"  - {limit}")


if __name__ == "__main__":
    main()
