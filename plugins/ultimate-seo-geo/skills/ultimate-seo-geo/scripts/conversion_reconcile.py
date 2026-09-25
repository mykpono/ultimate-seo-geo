#!/usr/bin/env python3
"""
Read demo requests (or any form conversion) on two rulers: GA4 and the CRM.

GA4 counts form events; the CRM counts submissions and the people behind them.
The two drift apart, and a raw series is usually contaminated: bot bursts,
the team's own test submissions, developer and preview hosts, and one person
submitting four times. A trend quoted from one ruler can point the other way
from the other. On the Improvado v4.1 audit, GA4 organic demo requests fell
44% while the number of distinct clean business people asking for a demo rose 7%.

    python scripts/conversion_reconcile.py --crm submissions.csv --production-host example.com --json
    python scripts/conversion_reconcile.py --crm submissions.csv --ga4 ga4-monthly.csv \\
        --production-host example.com --internal-domain example.com --business-only \\
        --compare 2025-06:2025-08,2026-06:2026-08 --json

--crm is a form-submission or contact export (HubSpot, Salesforce, anything
with one row per submission). Columns are found by name, case-insensitively;
--map field=Column overrides: email (required), date (required), page (the page
URL or host the form was sent from), form, source (original or latest traffic
source), qualified (lifecycle stage or lead status; --qualified-values lists
the values that count).

Each submission is kept or set aside with a reason:
  missing_email      no usable address
  internal           the address is on an --internal-domain (the team testing)
  test_host          sent from localhost, 127.0.0.1, a *.local, preview or
                     staging host, or any host not listed with --production-host
  burst_day          a day with 4x the median of the 28 days before it and 30+
                     submissions, and the days right after it while they stay at
                     1.5x that median (--exclude-dates adds known days;
                     --no-burst-detection turns detection off)
  free_mail          a free-mail address, only with --business-only (B2B)
Kept submissions are counted per month as submissions and as distinct people.
Repeat submitters are reported (submissions per address per month).

--ga4 is optional: monthly GA4 form events, either a CSV with a month or date
column and a count column (keyEvents, conversions, eventCount, count; an
optional channel column filtered by --ga4-channel), or ga4_report.py JSON with
a date dimension. GA4 has no address, so its counts cannot be cleaned the same
way; the output says what that means for each comparison.

--compare A:B,C:D compares two periods (YYYY-MM:YYYY-MM each) on every ruler
and flags when they disagree: opposite directions, or more than --disagree-pp
percentage points apart.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

BURST_FACTOR = 4.0
BURST_MIN = 30
BURST_TRAILING_DAYS = 28
BURST_TAIL_FACTOR = 1.5    # days right after a burst still this far above the baseline belong to it
REPEAT_WARN = 2.0          # submissions per address in a month
CONTAMINATION_WARN = 0.10  # share of a month's submissions set aside
DISAGREE_PP = 20.0

FIELD_CANDIDATES = {
    "email": ("email", "email address", "e-mail", "contact email"),
    "date": ("conversion date", "submitted at", "submission date", "submitted", "create date", "created at",
             "created date", "createdate", "date", "timestamp"),
    "page": ("page url", "conversion page", "page", "url", "page host", "host", "hostname", "form page url"),
    "form": ("form", "form name", "form title", "conversion"),
    "source": ("original source", "original traffic source", "latest source", "latest traffic source",
               "hs_analytics_source", "source", "lead source"),
    "qualified": ("lifecycle stage", "lead status", "pre-qualification status", "qualification"),
}
DEFAULT_QUALIFIED = ("marketingqualifiedlead", "salesqualifiedlead", "opportunity", "customer", "mql", "sql",
                     "pre-qualified", "actively working", "existing customer")
ORGANIC_SOURCE = re.compile(r"organic|seo", re.I)
FREE_MAIL = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "hotmail.com", "outlook.com", "live.com",
    "msn.com", "aol.com", "icloud.com", "me.com", "mail.com", "gmx.com", "gmx.de", "proton.me",
    "protonmail.com", "yandex.ru", "yandex.com", "mail.ru", "qq.com", "163.com", "126.com", "zoho.com",
    "hey.com", "fastmail.com", "web.de", "tutanota.com",
}
TEST_HOST = re.compile(
    r"^(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])$|\.local$|\.test$|\.internal$"
    r"|\.(amplifyapp\.com|vercel\.app|netlify\.app|pages\.dev|herokuapp\.com|webflow\.io|ngrok\.io|ngrok-free\.app)$"
    r"|(^|[.-])(staging|stage|preview|dev|qa|uat|pr-\d+)[.-]", re.I)
DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%m/%d/%Y %H:%M",
                "%m/%d/%Y %I:%M %p", "%d/%m/%Y", "%d.%m.%Y", "%Y/%m/%d")
EMAIL = re.compile(r"^[^@\s]+@([^@\s]+\.[^@\s]+)$")


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def parse_date(value) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d{12,13}", text):  # epoch milliseconds (HubSpot API exports)
        return datetime.fromtimestamp(int(text) / 1000, tz=timezone.utc).date()
    if re.match(r"\d{4}-\d{2}-\d{2}T", text):
        text = text.replace("T", " ", 1)
    text = re.sub(r"(Z|[+-]\d{2}:?\d{2})$", "", text)
    text = re.sub(r"(\d{2}:\d{2}:\d{2})\.\d+", r"\1", text).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt.replace("T", " ")).date()
        except ValueError:
            continue
    return None


def find_columns(header: list, overrides: dict) -> dict:
    lowered = {h.strip().lower(): h for h in header if h}
    columns = {}
    for field, candidates in FIELD_CANDIDATES.items():
        if field in overrides:
            if overrides[field] not in header:
                raise ValueError(f"--map {field}={overrides[field]}: no such column (have: {', '.join(header)})")
            columns[field] = overrides[field]
            continue
        columns[field] = next((lowered[c] for c in candidates if c in lowered), None)
    missing = [f for f in ("email", "date") if not columns[f]]
    if missing:
        raise ValueError(f"no {' or '.join(missing)} column found (have: {', '.join(header)}); use --map {missing[0]}=Column")
    return columns


def load_crm(path: str, overrides: dict | None = None) -> tuple:
    """(submissions, columns, unreadable_dates). Each submission: email, day, host, form, source, qualified."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        columns = find_columns(reader.fieldnames or [], overrides or {})
        out, bad_dates = [], 0
        for raw in reader:
            day = parse_date(raw.get(columns["date"]))
            if day is None:
                bad_dates += 1
                continue
            page = str(raw.get(columns["page"]) or "").strip() if columns["page"] else ""
            out.append({
                "email": str(raw.get(columns["email"]) or "").strip().lower(),
                "day": day,
                "host": host_of(page) if page else None,
                "form": str(raw.get(columns["form"]) or "").strip() if columns["form"] else "",
                "source": str(raw.get(columns["source"]) or "").strip() if columns["source"] else None,
                "qualified_raw": str(raw.get(columns["qualified"]) or "").strip() if columns["qualified"] else None,
            })
    return out, columns, bad_dates


def host_of(page: str) -> str:
    text = page.strip()
    if "://" not in text:
        text = "http://" + text
    return (urlparse(text).hostname or "").lower()


def month_of(value) -> str:
    return value.strftime("%Y-%m") if isinstance(value, date) else str(value)[:7]


def load_ga4(path: str, channel: str | None = None) -> dict:
    """{YYYY-MM: count} from a monthly or daily GA4 export, or ga4_report.py JSON with a date dimension."""
    counts = defaultdict(float)
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        rows = data.get("rows") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ValueError(f"{path}: expected ga4_report.py JSON with 'rows'")
    else:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            lines = [line for line in fh if not line.startswith("#")]  # GA4 UI exports start with # comments
        rows = list(csv.DictReader(lines))
    for row in rows:
        # GA4 names columns "yearMonth" in the API and "Year month" in the UI export: compare without spaces.
        keys = {re.sub(r"[\s_]+", "", str(k).lower()): v for k, v in row.items() if k is not None}
        when = next((keys[k] for k in ("month", "yearmonth", "date", "day") if keys.get(k) not in (None, "")), None)
        count = next((keys[k] for k in ("keyevents", "conversions", "eventcount", "count")
                      if keys.get(k) not in (None, "")), None)
        if when is None or count is None:
            raise ValueError(f"{path}: need a month/date column and a count column (keyEvents, conversions, eventCount, count)")
        row_channel = next((keys[k] for k in ("channel", "sessiondefaultchannelgroup", "defaultchannelgroup",
                                              "firstuserdefaultchannelgroup") if k in keys), None)
        if channel and row_channel is not None and str(row_channel).strip().lower() != channel.lower():
            continue
        text = str(when).strip()
        if re.fullmatch(r"\d{6}", text):
            text = f"{text[:4]}-{text[4:]}"
        elif re.fullmatch(r"\d{8}", text):
            text = f"{text[:4]}-{text[4:6]}"
        else:
            parsed = parse_date(text) if len(text) > 7 else None
            text = month_of(parsed) if parsed else text[:7]
        counts[text] += float(str(count).replace(",", ""))
    return {k: round(v) for k, v in sorted(counts.items())}


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------

def burst_days(submissions: list, factor=BURST_FACTOR, minimum=BURST_MIN, trailing=BURST_TRAILING_DAYS,
               tail=BURST_TAIL_FACTOR) -> dict:
    """{day: {"count", "baseline", "part"}} for days far above the trailing median of the days before them.

    A burst decays over days (Improvado, July 2026: 627 submissions, then 140, 151, 126, 113 against a
    50-90 baseline), so the days straight after a burst stay in it while they are at least `tail`
    times the burst's own baseline.
    """
    per_day = Counter(s["day"] for s in submissions)
    if not per_day:
        return {}
    first, last = min(per_day), max(per_day)
    out = {}
    day = first
    while day <= last:
        history = [per_day.get(day - timedelta(days=i), 0) for i in range(1, trailing + 1)
                   if day - timedelta(days=i) >= first]
        count = per_day.get(day, 0)
        if len(history) >= 7:
            baseline = statistics.median(history)
            if count >= minimum and count >= factor * max(baseline, 1):
                out[day] = {"count": count, "baseline": baseline, "part": "start"}
                follow = day + timedelta(days=1)
                while follow <= last and per_day.get(follow, 0) >= tail * max(baseline, 1):
                    out[follow] = {"count": per_day[follow], "baseline": baseline, "part": "tail"}
                    follow += timedelta(days=1)
                day = follow
                continue
        day += timedelta(days=1)
    return out


def classify(sub: dict, *, production_hosts: set, internal_domains: set, bursts: set, business_only: bool) -> str | None:
    """The reason a submission is set aside, or None when it counts."""
    match = EMAIL.match(sub["email"])
    if not match:
        return "missing_email"
    domain = match.group(1)
    if any(domain == d or domain.endswith("." + d) for d in internal_domains):
        return "internal"
    host = sub.get("host")
    if host is not None and (TEST_HOST.search(host) or (production_hosts and host not in production_hosts)):
        return "test_host"
    if sub["day"] in bursts:
        return "burst_day"
    if business_only and domain in FREE_MAIL:
        return "free_mail"
    return None


def is_qualified(value, accepted) -> bool:
    return bool(value) and re.sub(r"[\s_]+", "", value.lower()) in {re.sub(r"[\s_]+", "", a.lower()) for a in accepted}


def reconcile(submissions: list, *, production_hosts=(), internal_domains=(), business_only=False,
              exclude_dates=(), detect_bursts=True, qualified_values=DEFAULT_QUALIFIED, ga4=None) -> dict:
    production = {h.lower() for h in production_hosts}
    internal = {d.lower().lstrip("@") for d in internal_domains}
    detected = burst_days(submissions) if detect_bursts else {}
    bursts = set(detected) | set(exclude_dates)
    months = defaultdict(lambda: {"submissions": 0, "set_aside": Counter(), "kept": 0, "people": set(),
                                  "organic_people": set(), "qualified_people": set(), "per_email": Counter()})
    has_source = any(s.get("source") is not None for s in submissions)
    has_qualified = any(s.get("qualified_raw") is not None for s in submissions)
    reasons_total = Counter()
    for sub in submissions:
        m = months[month_of(sub["day"])]
        m["submissions"] += 1
        if sub["email"]:
            m["per_email"][sub["email"]] += 1
        reason = classify(sub, production_hosts=production, internal_domains=internal, bursts=bursts,
                          business_only=business_only)
        if reason:
            m["set_aside"][reason] += 1
            reasons_total[reason] += 1
            continue
        m["kept"] += 1
        m["people"].add(sub["email"])
        if sub.get("source") and ORGANIC_SOURCE.search(sub["source"]):
            m["organic_people"].add(sub["email"])
        if is_qualified(sub.get("qualified_raw"), qualified_values):
            m["qualified_people"].add(sub["email"])
    table = []
    for month in sorted(set(months) | set(ga4 or {})):
        m = months.get(month)
        row = {"month": month}
        if m:
            addresses = len(m["per_email"])
            row.update(
                submissions=m["submissions"],
                set_aside=dict(m["set_aside"]),
                set_aside_share=round(sum(m["set_aside"].values()) / m["submissions"], 3),
                kept=m["kept"],
                people=len(m["people"]),
                submissions_per_address=round(sum(m["per_email"].values()) / addresses, 2) if addresses else None,
                organic_people=len(m["organic_people"]) if has_source else None,
                qualified_people=len(m["qualified_people"]) if has_qualified else None,
            )
        else:
            row.update(submissions=0, people=0, note="no CRM rows this month")
        if ga4 is not None:
            row["ga4_events"] = ga4.get(month)
        table.append(row)
    return {
        "months": table,
        "set_aside_total": dict(reasons_total),
        "burst_days": [{"day": d.isoformat(), **v} for d, v in sorted(detected.items())],
        # A burst day is set aside whole, so the real submissions of that day go with it. The
        # baseline median of each detected day estimates how many that was.
        "burst_real_submissions_lost_estimate": round(sum(v["baseline"] for v in detected.values())),
        "excluded_dates": sorted(d.isoformat() for d in exclude_dates),
        "has_source": has_source,
        "has_qualified": has_qualified,
        "rules": {
            "production_hosts": sorted(production) or "not given: only known test and preview hosts are set aside",
            "internal_domains": sorted(internal),
            "business_only": business_only,
            "burst": (f"a day with at least {BURST_FACTOR:g}x the median of the {BURST_TRAILING_DAYS} days before it "
                      f"and at least {BURST_MIN} submissions, plus the days after it still at {BURST_TAIL_FACTOR:g}x "
                      f"that median" if detect_bursts else "off"),
        },
    }


# ---------------------------------------------------------------------------
# Two rulers
# ---------------------------------------------------------------------------

def parse_period(text: str) -> tuple:
    start, _, end = text.strip().partition(":")
    for part in (start, end or start):
        if not re.fullmatch(r"\d{4}-\d{2}", part):
            raise ValueError(f"period {text!r}: use YYYY-MM:YYYY-MM")
    return start, end or start


def _sum(table: list, period: tuple, key: str):
    values = [r.get(key) for r in table if period[0] <= r["month"] <= period[1]]
    if not values or any(v is None for v in values):
        return None
    return sum(values)


def _pct(before, after):
    if before in (None, 0) or after is None:
        return None
    return round((after - before) / before * 100, 1)


def compare(table: list, before: tuple, after: tuple, disagree_pp=DISAGREE_PP) -> dict:
    rulers = {
        "ga4_events": "GA4 form events (all hits, not deduplicated, contamination not removable)",
        "submissions": "CRM submissions, raw",
        "kept": "CRM submissions after contamination is set aside",
        "people": "distinct people after contamination is set aside",
        "organic_people": "distinct people whose CRM source is organic search",
        "qualified_people": "distinct qualified people",
    }
    out = {"before": f"{before[0]}..{before[1]}", "after": f"{after[0]}..{after[1]}", "rulers": {}}
    for key, meaning in rulers.items():
        b, a = _sum(table, before, key), _sum(table, after, key)
        if b is None and a is None:
            continue
        out["rulers"][key] = {"meaning": meaning, "before": b, "after": a, "change_pct": _pct(b, a)}
    changes = {k: v["change_pct"] for k, v in out["rulers"].items() if v["change_pct"] is not None}
    clean = [k for k in ("people", "organic_people", "qualified_people") if k in changes]
    raw = [k for k in ("ga4_events", "submissions") if k in changes]
    conflicts = []
    for r in raw:
        for c in clean:
            opposite = (changes[r] > 0) != (changes[c] > 0) and abs(changes[r]) >= 5 and abs(changes[c]) >= 5
            if opposite or abs(changes[r] - changes[c]) > disagree_pp:
                conflicts.append({"raw": r, "clean": c, "raw_change_pct": changes[r], "clean_change_pct": changes[c],
                                  "opposite_directions": opposite})
    out["disagreements"] = conflicts
    out["verdict"] = ("the rulers disagree: quote the clean count of people, name the ruler with every number, "
                      "and reconcile before calling a trend" if conflicts else
                      "the rulers agree within the threshold" if len(changes) >= 2 else "only one ruler has data")
    return out


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

def build_issues(result: dict) -> list:
    issues = []
    months = [m for m in result["months"] if m.get("submissions")]
    dirty = [m for m in months if m.get("set_aside_share", 0) >= CONTAMINATION_WARN]
    if dirty:
        worst = max(dirty, key=lambda m: m["set_aside_share"])
        totals = result["set_aside_total"]
        issues.append({
            "code": "conversion_contamination", "severity": "medium", "kind": "defect", "lane": "Assisted",
            "finding": (f"In {len(dirty)} of {len(months)} months at least {CONTAMINATION_WARN:.0%} of form submissions "
                        f"are not real prospects; worst {worst['month']} at {worst['set_aside_share']:.0%}."),
            "evidence": "Set aside across the period: " + ", ".join(f"{k} {v:,}" for k, v in sorted(totals.items(), key=lambda kv: -kv[1]))
                        + ("; burst days " + ", ".join(f"{b['day']} ({b['count']} vs median {b['baseline']:g})" for b in result["burst_days"][:5])
                           if result["burst_days"] else ""),
            "impact": "Every conversion rate and demand trend read from the raw series is inflated by these rows, by a different amount each month.",
            "fix": ("Load the form tracker only on production hosts, block internal addresses from the CRM conversion count, "
                    "and put bot protection on the form; report the clean series beside the raw one with the exclusions named."),
            "confidence": "Confirmed",
            "falsifiability": "Wrong if the set-aside rows turn out to be real prospects: check a sample of internal and burst-day addresses against the CRM owner.",
            "leading_indicator": "Share of each month's submissions set aside, after the tracker and form changes ship.",
        })
    repeat = [m for m in months if (m.get("submissions_per_address") or 0) >= REPEAT_WARN]
    if repeat:
        issues.append({
            "code": "repeat_submitters", "severity": "low", "kind": "defect", "lane": "Assisted",
            "finding": (f"In {len(repeat)} months people submit the form {max(m['submissions_per_address'] for m in repeat):.1f} "
                        f"times each on average: submission counts overstate people."),
            "evidence": ", ".join(f"{m['month']} {m['submissions_per_address']}" for m in repeat[:6]),
            "impact": "A count of submissions or GA4 events moves with retries, double sends and testing, not with demand.",
            "fix": "Count distinct people per month; find the cause of repeats (a form that errors, a thank-you page that re-fires, testing).",
            "confidence": "Confirmed",
            "falsifiability": "Wrong if repeat submissions are distinct requests (several demos per person) that sales counts separately.",
            "leading_indicator": "Submissions per address per month.",
        })
    for cmp in result.get("comparisons", []):
        for d in cmp["disagreements"][:1]:
            raw_meaning = cmp["rulers"][d["raw"]]["meaning"]
            clean_meaning = cmp["rulers"][d["clean"]]["meaning"]
            issues.append({
                "code": "rulers_disagree", "severity": "medium", "kind": "data_gap", "lane": "Decision",
                "finding": (f"{cmp['before']} to {cmp['after']}: {raw_meaning} moved {d['raw_change_pct']:+.0f}%, "
                            f"{clean_meaning} moved {d['clean_change_pct']:+.0f}%"
                            + (" — opposite directions." if d["opposite_directions"] else ".")),
                "evidence": "; ".join(f"{k}: {v['before']} -> {v['after']} ({v['change_pct']:+.1f}%)" if v["change_pct"] is not None
                                      else f"{k}: {v['before']} -> {v['after']}" for k, v in cmp["rulers"].items()),
                "impact": "A demand trend quoted from one ruler can be the reverse of what people did. Neither number stands alone until the two are joined.",
                "fix": ("Quote distinct clean people as the demand figure and name the ruler with every number. Join GA4 to the CRM "
                        "(a client id or the CRM's original-source property) before quoting a channel split."),
                "confidence": "Confirmed",
                "falsifiability": "Wrong if the gap is fully explained by a tracking change on one side in the same months: check tag manager and form change history first.",
                "leading_indicator": "Both rulers month by month, until they move together.",
            })
    return issues


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_human(result: dict) -> None:
    print("Conversions on two rulers")
    print(f"Rules: {json.dumps(result['rules'])}")
    print("=" * 96)
    head = f"{'month':<8} {'subm':>6} {'set aside':>10} {'kept':>6} {'people':>6} {'per addr':>8} {'organic':>7} {'qualif':>6} {'GA4':>6}"
    print(head)
    for m in result["months"]:
        def f(v):
            return "-" if v is None else f"{v:,}" if isinstance(v, int) else str(v)
        aside = sum((m.get("set_aside") or {}).values())
        print(f"{m['month']:<8} {f(m.get('submissions')):>6} {aside:>6} {m.get('set_aside_share', 0):>3.0%} {f(m.get('kept')):>6} "
              f"{f(m.get('people')):>6} {f(m.get('submissions_per_address')):>8} {f(m.get('organic_people')):>7} "
              f"{f(m.get('qualified_people')):>6} {f(m.get('ga4_events')):>6}")
    if result["burst_days"]:
        print("\nBurst days: " + ", ".join(f"{b['day']} ({b['count']} vs median {b['baseline']:g})" for b in result["burst_days"]))
    for cmp in result.get("comparisons", []):
        print(f"\n{cmp['before']} vs {cmp['after']}: {cmp['verdict']}")
        for key, v in cmp["rulers"].items():
            change = f"{v['change_pct']:+.1f}%" if v["change_pct"] is not None else "-"
            print(f"  {key:<17} {str(v['before']):>7} -> {str(v['after']):<7} {change:>8}  {v['meaning']}")
    print()
    for issue in result["issues"]:
        print(f"[{issue['severity']}] {issue['finding']}")
    for line in result["limits"]:
        print(f"Note: {line}")


LIMITS = [
    "GA4 counts events, not people, and has no address: its series cannot be cleaned of internal tests, bursts or repeats the way the CRM series is.",
    "A submission with no page URL cannot be checked against --production-host; it is kept.",
    "Burst days are set aside whole: real submissions on those days are lost with the spam (burst_real_submissions_lost_estimate).",
    "Slash dates are read month first (07/27/2026); a day-first export needs --map date=... with ISO dates or a re-export.",
    "Organic people use the CRM's source property, which is first- or last-touch depending on the column exported; GA4's channel is session-scoped. They are different questions.",
]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Form conversions on two rulers: GA4 events and clean CRM people")
    parser.add_argument("--crm", required=True, metavar="CSV", help="CRM export, one row per submission")
    parser.add_argument("--ga4", metavar="CSV_OR_JSON", help="GA4 form events by month or day")
    parser.add_argument("--ga4-channel", metavar="NAME", help='Keep one channel of the GA4 file, e.g. "Organic Search"')
    parser.add_argument("--production-host", action="append", default=[], metavar="HOST",
                        help="A host real visitors submit from (repeat for several, e.g. example.com, www.example.com)")
    parser.add_argument("--internal-domain", action="append", default=[], metavar="DOMAIN",
                        help="The team's email domain; its submissions are tests (repeatable)")
    parser.add_argument("--business-only", action="store_true", help="Set aside free-mail addresses (B2B sites)")
    parser.add_argument("--exclude-dates", metavar="FROM:TO", action="append", default=[],
                        help="Known bad days, YYYY-MM-DD:YYYY-MM-DD (repeatable)")
    parser.add_argument("--no-burst-detection", action="store_true", help="Do not set aside burst days automatically")
    parser.add_argument("--qualified-values", metavar="A,B", help="Values of the qualified column that count")
    parser.add_argument("--map", action="append", default=[], metavar="FIELD=COLUMN", help="Name a column: email, date, page, form, source, qualified")
    parser.add_argument("--form", action="append", default=[], metavar="NAME", help="Count only these forms (repeatable, case-insensitive substring)")
    parser.add_argument("--compare", metavar="A:B,C:D", help="Two periods to compare on every ruler")
    parser.add_argument("--disagree-pp", type=float, default=DISAGREE_PP, help=f"Gap that counts as disagreement (default {DISAGREE_PP:g} points)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    overrides = {}
    for item in args.map:
        field, _, column = item.partition("=")
        if field not in FIELD_CANDIDATES or not column:
            parser.error(f"--map {item}: use FIELD=COLUMN with FIELD one of {', '.join(FIELD_CANDIDATES)}")
        overrides[field] = column
    exclude = set()
    for span in args.exclude_dates:
        start, _, end = span.partition(":")
        first, last = parse_date(start), parse_date(end or start)
        if not first or not last or last < first:
            parser.error(f"--exclude-dates {span}: use YYYY-MM-DD:YYYY-MM-DD")
        while first <= last:
            exclude.add(first)
            first += timedelta(days=1)
    try:
        submissions, columns, bad_dates = load_crm(args.crm, overrides)
        ga4 = load_ga4(args.ga4, args.ga4_channel) if args.ga4 else None
        periods = [parse_period(p) for p in args.compare.split(",")] if args.compare else []
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}) if args.json else f"Error: {exc}")
        return 1
    if args.compare and len(periods) != 2:
        parser.error("--compare takes exactly two periods: A:B,C:D")
    if args.form:
        wanted = [f.lower() for f in args.form]
        submissions = [s for s in submissions if any(w in s["form"].lower() for w in wanted)]
    qualified = tuple(v.strip() for v in args.qualified_values.split(",")) if args.qualified_values else DEFAULT_QUALIFIED

    result = reconcile(submissions, production_hosts=args.production_host, internal_domains=args.internal_domain,
                       business_only=args.business_only, exclude_dates=exclude, detect_bursts=not args.no_burst_detection,
                       qualified_values=qualified, ga4=ga4)
    result["columns"] = columns
    result["rows_without_a_readable_date"] = bad_dates
    if periods:
        result["comparisons"] = [compare(result["months"], periods[0], periods[1], args.disagree_pp)]
    result["issues"] = build_issues(result)
    result["limits"] = LIMITS + ([f"{bad_dates} rows had no readable date and were skipped."] if bad_dates else [])
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_human(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
