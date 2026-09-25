#!/usr/bin/env python3
"""
Check a GA4 conversion event for contamination before anyone quotes it (Tier 2).

A GA4 conversion series carries more than prospects: events fired on localhost
and preview builds, bot bursts, one visitor firing the event again and again,
and steps where a tag or form change moved the count while demand did not.
On the Improvado v4.1 audit, 108 of July's form events came from one visitor
and a step between August and September 2025 was never explained.

    python scripts/ga4_audit.py --property 123456789 --event generate_lead \\
        --start 2025-06-01 --end 2026-09-15 --production-host example.com --json
    python scripts/ga4_audit.py --property 123456789 --event generate_lead --save-rows ga4.json
    python scripts/ga4_audit.py --replay ga4.json --production-host example.com --json   # no API call

Five checks, each from the GA4 Data API alone:
  hosts      events whose hostName is a test host (localhost, *.amplifyapp.com,
             staging, preview...) or not a --production-host
  bursts     days far above the trailing median (conversion_reconcile.py's rule,
             so both rulers are cleaned the same way)
  repeats    events per user by month; above 2 means retries, double-firing tags
             or testing, not people
  steps      a month where events per 1,000 sessions jumps or drops by half while
             sessions hold: the signature of a tag, form or consent change
  not_set    the share of organic sessions whose landing page is "(not set)",
             which hides pages from every landing-page report

It also writes the monthly series with test hosts and burst days removed
(--save-monthly), in the shape conversion_reconcile.py --ga4 reads. GA4 has no
visitor id in the Data API, so repeats are read from events per user; a single
visitor firing 108 events needs the BigQuery export to name.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from conversion_reconcile import TEST_HOST, burst_days_from_counts  # noqa: E402  one rule for both rulers

REPEAT_WARN = 2.0
STEP_RATIO = 1.5          # events per 1,000 sessions up 50% or down to two thirds
STEP_SESSIONS_STABLE = 0.2
STEP_MIN_EVENTS = 30
NOT_SET_WARN = 0.05
HOST_WARN = 0.05
PAGE_SIZE = 100000

LIMITS = [
    "The Data API has no visitor id: repeats are events per user by month, not a list of the visitors who fired them.",
    "hostName is where the page ran; events sent by the Measurement Protocol or a server container may carry the production host whatever their origin.",
    "A step in events per session names the month to check in the tag manager and form change history; it does not say which change it was.",
]


# ---------------------------------------------------------------------------
# Fetch (the only part that touches the API)
# ---------------------------------------------------------------------------

def _filter(spec):
    """FilterExpression from {"field": value} (exact match, all ANDed)."""
    if not spec:
        return None
    from google.analytics.data_v1beta.types import Filter, FilterExpression, FilterExpressionList
    parts = [FilterExpression(filter=Filter(field_name=k, string_filter=Filter.StringFilter(
        value=v, match_type=Filter.StringFilter.MatchType.EXACT))) for k, v in spec.items()]
    return parts[0] if len(parts) == 1 else FilterExpression(and_group=FilterExpressionList(expressions=parts))


def run_rows(client, property_id: str, start: str, end: str, dimensions: list, metrics: list, where=None) -> dict:
    """{"rows": [...], "truncated": False} for one report, paged with offset. Raises RuntimeError on API errors."""
    from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
    rows, offset = [], 0
    while True:
        request = RunReportRequest(
            property=f"properties/{property_id}", date_ranges=[DateRange(start_date=start, end_date=end)],
            dimensions=[Dimension(name=d) for d in dimensions], metrics=[Metric(name=m) for m in metrics],
            dimension_filter=_filter(where), limit=PAGE_SIZE, offset=offset)
        try:
            response = client.run_report(request)
        except Exception as exc:  # google.api_core errors, auth and transport errors
            raise RuntimeError(f"GA4 report failed ({','.join(dimensions)}): {exc}") from exc
        for r in response.rows:
            entry = {d: r.dimension_values[i].value for i, d in enumerate(dimensions)}
            for i, m in enumerate(metrics):
                entry[m] = float(r.metric_values[i].value or 0)
            rows.append(entry)
        offset += len(response.rows)
        if not response.rows or offset >= (response.row_count or 0):
            return {"rows": rows, "truncated": False}


def fetch_dataset(client, property_id: str, event: str, start: str, end: str) -> dict:
    ev = {"eventName": event}
    return {
        "property_id": property_id, "event": event, "window": [start, end],
        "daily": run_rows(client, property_id, start, end, ["date", "hostName", "sessionDefaultChannelGroup"], ["eventCount"], ev),
        "monthly_users": run_rows(client, property_id, start, end, ["yearMonth"], ["eventCount", "totalUsers"], ev),
        "monthly_sessions": run_rows(client, property_id, start, end, ["yearMonth", "sessionDefaultChannelGroup"], ["sessions"]),
        "organic_not_set": run_rows(client, property_id, start, end, ["yearMonth"], ["sessions"],
                                    {"sessionDefaultChannelGroup": "Organic Search", "landingPage": "(not set)"}),
    }


# ---------------------------------------------------------------------------
# Analyses (pure: rows in, results out)
# ---------------------------------------------------------------------------

def _rows(block):
    return (block or {}).get("rows", []) if isinstance(block, dict) else (block or [])


def _day(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date() if len(value) == 8 else date.fromisoformat(value)


def _month(value: str) -> str:
    value = str(value)
    return f"{value[:4]}-{value[4:6]}" if len(value) >= 6 and value[:6].isdigit() else value[:7]


def host_check(daily: list, production_hosts: set) -> dict:
    by_host = defaultdict(float)
    for r in daily:
        by_host[(r.get("hostName") or "").lower()] += r.get("eventCount", 0)
    production = production_hosts or ({max(by_host, key=by_host.get)} if by_host else set())
    test = {}
    for host, n in by_host.items():
        if host in production:
            continue
        test[host] = {"events": round(n), "why": "test host" if TEST_HOST.search(host or "") else
                      "not set" if host in ("", "(not set)") else "not a production host"}
    total = sum(by_host.values())
    excluded = sum(v["events"] for v in test.values())
    return {
        "production_hosts": sorted(production),
        "production_inferred": not production_hosts,
        "hosts": {h: round(n) for h, n in sorted(by_host.items(), key=lambda kv: -kv[1])},
        "set_aside": dict(sorted(test.items(), key=lambda kv: -kv[1]["events"])),
        "share": round(excluded / total, 4) if total else 0.0,
    }


def monthly_series(daily: list, production: set, bursts: set) -> list:
    months = defaultdict(lambda: {"events": 0.0, "test_host": 0.0, "burst_day": 0.0, "by_channel": defaultdict(float),
                                  "clean_by_channel": defaultdict(float)})
    for r in daily:
        day = _day(r["date"])
        m = months[day.strftime("%Y-%m")]
        n = r.get("eventCount", 0)
        channel = r.get("sessionDefaultChannelGroup") or "(not set)"
        m["events"] += n
        m["by_channel"][channel] += n
        if (r.get("hostName") or "").lower() not in production:
            m["test_host"] += n
        elif day in bursts:
            m["burst_day"] += n
        else:
            m["clean_by_channel"][channel] += n
    out = []
    for month in sorted(months):
        m = months[month]
        clean = m["events"] - m["test_host"] - m["burst_day"]
        out.append({"month": month, "events": round(m["events"]), "test_host": round(m["test_host"]),
                    "burst_day": round(m["burst_day"]), "clean_events": round(clean),
                    "by_channel": {k: round(v) for k, v in sorted(m["by_channel"].items())},
                    "clean_by_channel": {k: round(v) for k, v in sorted(m["clean_by_channel"].items())}})
    return out


def repeat_check(monthly_users: list) -> list:
    out = []
    for r in sorted(monthly_users, key=lambda r: r["yearMonth"]):
        users = r.get("totalUsers", 0)
        out.append({"month": _month(r["yearMonth"]), "events": round(r.get("eventCount", 0)), "users": round(users),
                    "events_per_user": round(r["eventCount"] / users, 2) if users else None})
    return out


def step_check(series: list, monthly_sessions: list) -> list:
    sessions = defaultdict(float)
    for r in monthly_sessions:
        sessions[_month(r["yearMonth"])] += r.get("sessions", 0)
    points = [(m["month"], m["clean_events"], sessions.get(m["month"], 0)) for m in series]
    steps = []
    for (m0, e0, s0), (m1, e1, s1) in zip(points, points[1:]):
        if not s0 or not s1 or max(e0, e1) < STEP_MIN_EVENTS or not e0:
            continue
        rate0, rate1 = e0 / s0 * 1000, e1 / s1 * 1000
        ratio = rate1 / rate0 if rate0 else None
        sessions_change = (s1 - s0) / s0
        if ratio and (ratio >= STEP_RATIO or ratio <= 1 / STEP_RATIO) and abs(sessions_change) < STEP_SESSIONS_STABLE:
            steps.append({"from": m0, "to": m1, "events_per_1000_sessions": [round(rate0, 2), round(rate1, 2)],
                          "ratio": round(ratio, 2), "sessions_change_pct": round(sessions_change * 100, 1)})
    return steps


def not_set_check(monthly_sessions: list, organic_not_set: list) -> list:
    organic = defaultdict(float)
    for r in monthly_sessions:
        if r.get("sessionDefaultChannelGroup") == "Organic Search":
            organic[_month(r["yearMonth"])] += r.get("sessions", 0)
    missing = {_month(r["yearMonth"]): r.get("sessions", 0) for r in organic_not_set}
    return [{"month": m, "organic_sessions": round(organic[m]), "landing_not_set": round(missing.get(m, 0)),
             "share": round(missing.get(m, 0) / organic[m], 4) if organic[m] else None}
            for m in sorted(organic)]


def analyse(dataset: dict, production_hosts=()) -> dict:
    daily = _rows(dataset.get("daily"))
    hosts = host_check(daily, {h.lower() for h in production_hosts})
    production = set(hosts["production_hosts"])
    per_day = defaultdict(float)
    for r in daily:
        if (r.get("hostName") or "").lower() in production:
            per_day[_day(r["date"])] += r.get("eventCount", 0)
    bursts = burst_days_from_counts({d: round(n) for d, n in per_day.items()})
    series = monthly_series(daily, production, set(bursts))
    result = {
        "property_id": dataset.get("property_id"),
        "event": dataset.get("event"),
        "window": dataset.get("window"),
        "hosts": hosts,
        "burst_days": [{"day": d.isoformat(), **v} for d, v in sorted(bursts.items())],
        "monthly": series,
        "repeats": repeat_check(_rows(dataset.get("monthly_users"))),
        "steps": step_check(series, _rows(dataset.get("monthly_sessions"))),
        "organic_landing_not_set": not_set_check(_rows(dataset.get("monthly_sessions")), _rows(dataset.get("organic_not_set"))),
        "limits": LIMITS + (["No --production-host given: the host with the most events is taken as production."]
                            if hosts["production_inferred"] else []),
    }
    result["issues"] = build_issues(result)
    return result


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

def build_issues(r: dict) -> list:
    event = r.get("event") or "the conversion event"
    issues = []
    hosts, series = r["hosts"], r["monthly"]
    burst_events = sum(m["burst_day"] for m in series)
    total = sum(m["events"] for m in series)
    if hosts["share"] >= HOST_WARN or (total and burst_events / total >= HOST_WARN):
        issues.append({
            "code": "ga4_conversion_contamination", "severity": "medium", "kind": "defect", "lane": "Assisted",
            "finding": (f"{hosts['share']:.0%} of {event} events come from non-production hosts and "
                        f"{burst_events / total if total else 0:.0%} from burst days; every GA4 conversion figure includes them."),
            "evidence": "; ".join([f"{h} {v['events']:,} ({v['why']})" for h, v in list(hosts["set_aside"].items())[:4]]
                                  + [f"burst {b['day']} {b['count']:,} vs median {b['baseline']:g}" for b in r["burst_days"][:3]]),
            "impact": "Conversion rates and demand trends read from GA4 move with testing and bots, by a different amount each month.",
            "fix": ("Send GA4 and the form tracker only from production hosts (gate the tag on the hostname), add a GA4 data filter "
                    "for internal and developer traffic, and put bot protection on the form. Quote the clean series (--save-monthly)."),
            "confidence": "Confirmed",
            "falsifiability": "Wrong if the non-production host is a real customer-facing domain: list it with --production-host and re-run.",
            "leading_indicator": "Share of the event from non-production hosts each month, after the tag change ships.",
        })
    heavy = [m for m in r["repeats"] if (m["events_per_user"] or 0) >= REPEAT_WARN]
    if heavy:
        worst = max(heavy, key=lambda m: m["events_per_user"])
        issues.append({
            "code": "ga4_repeat_firing", "severity": "low", "kind": "defect", "lane": "Assisted",
            "finding": f"{event} fires {worst['events_per_user']} times per user in {worst['month']} ({len(heavy)} months at {REPEAT_WARN:g} or more).",
            "evidence": ", ".join(f"{m['month']} {m['events']:,} events / {m['users']:,} users" for m in heavy[:6]),
            "impact": "Event counts move with retries, double-firing tags and testing rather than with the number of people converting.",
            "fix": ("Check that the tag fires once per submission (not on page load of the thank-you page and on submit), and count "
                    "users or CRM people, not events. The BigQuery export names the visitors behind the repeats."),
            "confidence": "Likely",
            "falsifiability": "Wrong if one user legitimately converts several times (several forms), which the event parameters show.",
            "leading_indicator": "Events per user for the event, month by month.",
        })
    for step in r["steps"][:2]:
        direction = "rose" if step["ratio"] > 1 else "fell"
        issues.append({
            "code": "ga4_tracking_step", "severity": "medium", "kind": "data_gap", "lane": "Human",
            "finding": (f"{event} per 1,000 sessions {direction} {step['events_per_1000_sessions'][0]} -> "
                        f"{step['events_per_1000_sessions'][1]} from {step['from']} to {step['to']} while sessions moved "
                        f"{step['sessions_change_pct']:+.0f}%: likely a tracking change, not demand."),
            "evidence": f"Clean events (test hosts and burst days removed) divided by sessions, {step['from']} and {step['to']}.",
            "impact": "A trend that spans this month compares two different measurements; any year-over-year figure across it is suspect.",
            "fix": (f"Open the tag manager version history, the GA4 change history and the form's change log for {step['from']} "
                    f"to {step['to']}; annotate the change in GA4 and compare only like-for-like periods."),
            "confidence": "Hypothesis",
            "falsifiability": "Wrong if a real change in demand (a campaign, a price change, a new form) explains the step; the change logs settle it.",
            "leading_indicator": "Events per 1,000 sessions, which should stay level once the cause is known.",
        })
    bad = [m for m in r["organic_landing_not_set"] if (m["share"] or 0) >= NOT_SET_WARN]
    if bad:
        worst = max(bad, key=lambda m: m["share"])
        issues.append({
            "code": "ga4_landing_not_set", "severity": "low", "kind": "defect", "lane": "Assisted",
            "finding": f"Up to {worst['share']:.1%} of organic sessions have landing page (not set) ({worst['month']}).",
            "evidence": ", ".join(f"{m['month']} {m['share']:.1%}" for m in bad[:6]),
            "impact": "Organic sessions that no page gets credit for: every landing-page report and content ROI figure undercounts.",
            "fix": ("Usually sessions that start without a page_view (consent mode, a tag firing before config, or a session "
                    "timing out mid-visit). Check that the GA4 config tag fires on every page before any event."),
            "confidence": "Likely",
            "falsifiability": "Wrong if the share is stable and small after consent-mode modelling is accounted for.",
            "leading_indicator": "Monthly share of organic sessions with landing page (not set).",
        })
    return issues


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_monthly(result: dict, path: str) -> None:
    """Clean monthly events by channel, in the shape conversion_reconcile.py --ga4 reads."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["yearMonth", "sessionDefaultChannelGroup", "eventCount"])
        for m in result["monthly"]:
            for channel, n in m["clean_by_channel"].items():
                w.writerow([m["month"].replace("-", ""), channel, n])


def print_human(r: dict) -> None:
    print(f"GA4 conversion audit — {r.get('event')} on property {r.get('property_id') or '(replay)'}")
    h = r["hosts"]
    print(f"Production hosts: {', '.join(h['production_hosts'])}{' (inferred)' if h['production_inferred'] else ''}; "
          f"{h['share']:.1%} of events set aside by host")
    for host, v in list(h["set_aside"].items())[:8]:
        print(f"  {v['events']:>7,}  {host or '(empty)'}  [{v['why']}]")
    if r["burst_days"]:
        print("Burst days: " + ", ".join(f"{b['day']} ({b['count']} vs {b['baseline']:g})" for b in r["burst_days"]))
    print(f"\n{'month':<8} {'events':>7} {'test host':>9} {'burst':>6} {'clean':>6} {'per user':>8}")
    per_user = {m["month"]: m["events_per_user"] for m in r["repeats"]}
    for m in r["monthly"]:
        print(f"{m['month']:<8} {m['events']:>7,} {m['test_host']:>9,} {m['burst_day']:>6,} {m['clean_events']:>6,} "
              f"{per_user.get(m['month']) if per_user.get(m['month']) is not None else '-':>8}")
    for s in r["steps"]:
        print(f"Step {s['from']} -> {s['to']}: {s['events_per_1000_sessions']} per 1,000 sessions, sessions {s['sessions_change_pct']:+}%")
    print()
    for i in r["issues"]:
        print(f"[{i['severity']}] {i['finding']}")
    for line in r["limits"]:
        print(f"Note: {line}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="GA4 conversion event contamination audit (Tier 2)")
    parser.add_argument("--property", help="GA4 property id (numbers only)")
    parser.add_argument("--event", help="The conversion event, e.g. generate_lead or form_submit")
    today = date.today()
    parser.add_argument("--start", default=(today - timedelta(days=455)).isoformat(), help="First day (default: 15 months ago)")
    parser.add_argument("--end", default=(today - timedelta(days=1)).isoformat(), help="Last day (default: yesterday)")
    parser.add_argument("--production-host", action="append", default=[], metavar="HOST",
                        help="A real site host (repeatable); default: the host with the most events")
    parser.add_argument("--save-rows", metavar="PATH", help="Also write the fetched rows for --replay")
    parser.add_argument("--replay", metavar="PATH", help="Analyse rows saved by --save-rows instead of calling the API")
    parser.add_argument("--save-monthly", metavar="CSV", help="Write clean monthly events by channel for conversion_reconcile.py --ga4")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    if args.replay:
        try:
            with open(args.replay, encoding="utf-8") as fh:
                dataset = json.load(fh)
        except (OSError, ValueError) as exc:
            parser.error(f"--replay: cannot read {args.replay}: {exc}")
        if not isinstance(dataset, dict) or "daily" not in dataset:
            parser.error(f"--replay: {args.replay} was not written by --save-rows")
    else:
        if not args.property or not args.event:
            parser.error("--property and --event are required unless --replay is given")
        import ga4_report  # credential handling lives there; imported late so --replay needs no Google libraries
        client = ga4_report._load_ga4_client(args.property)
        try:
            dataset = fetch_dataset(client, args.property, args.event, args.start, args.end)
        except RuntimeError as exc:
            print(json.dumps({"error": str(exc)}) if args.json else f"Error: {exc}")
            return 1
        if args.save_rows:
            with open(args.save_rows, "w", encoding="utf-8") as fh:
                json.dump(dataset, fh)

    result = analyse(dataset, args.production_host)
    if args.save_monthly:
        write_monthly(result, args.save_monthly)
        result["monthly_written"] = args.save_monthly
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_human(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
