"""ga4_audit.py: a GA4 conversion event checked for contamination before it is quoted.

The replay fixture is generated in the shape Improvado published in its verification of
report v4.1: GA4 form events of 227/273/337 (Jun-Aug 2025) and 377/525/197 (Jun-Aug 2026),
with 108 of July's from one visitor; a spam burst on 27 July 2026; developer submissions from
localhost and pr-*.amplifyapp.com pages; an unexplained step between August and September
2025; and 10.9% of organic sessions with landing page (not set).
"""

import csv
import json
import os
import subprocess
import sys
from datetime import date, timedelta

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

import ga4_audit as ga  # noqa: E402

PROD = "improvado.io"


def days(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def daily_row(day, host, channel, n):
    return {"date": day.strftime("%Y%m%d"), "hostName": host, "sessionDefaultChannelGroup": channel, "eventCount": float(n)}


def fixture():
    daily = []
    for day in days(date(2025, 6, 1), date(2026, 8, 31)):
        # before September 2025 the tag fired about twice per real conversion: the step
        per_day = 8 if day < date(2025, 9, 1) else 4
        daily.append(daily_row(day, PROD, "Organic Search", per_day // 2))
        daily.append(daily_row(day, PROD, "Paid Search", per_day - per_day // 2))
        if day >= date(2026, 6, 1):
            daily.append(daily_row(day, "localhost", "Direct", 2))
            daily.append(daily_row(day, "pr-1453.d2x7abc.amplifyapp.com", "Direct", 1))
    for day, n in {date(2026, 7, 27): 300, date(2026, 7, 28): 40, date(2026, 7, 29): 30}.items():
        daily.append(daily_row(day, PROD, "Direct", n))
    monthly_users, monthly_sessions, not_set = [], [], []
    months = sorted({d["date"][:6] for d in daily})
    for ym in months:
        events = sum(r["eventCount"] for r in daily if r["date"].startswith(ym))
        users = events / 2.6 if ym == "202607" else events / 1.2
        monthly_users.append({"yearMonth": ym, "eventCount": events, "totalUsers": users})
        monthly_sessions.append({"yearMonth": ym, "sessionDefaultChannelGroup": "Organic Search", "sessions": 20000.0})
        monthly_sessions.append({"yearMonth": ym, "sessionDefaultChannelGroup": "Paid Search", "sessions": 5000.0})
        not_set.append({"yearMonth": ym, "sessions": 2180.0 if ym >= "202508" else 300.0})
    return {"property_id": "123456789", "event": "generate_lead", "window": ["2025-06-01", "2026-08-31"],
            "daily": {"rows": daily}, "monthly_users": {"rows": monthly_users},
            "monthly_sessions": {"rows": monthly_sessions}, "organic_not_set": {"rows": not_set}}


@pytest.fixture
def result():
    return ga.analyse(fixture(), [PROD])


def test_test_hosts_are_set_aside(result):
    aside = result["hosts"]["set_aside"]
    assert set(aside) == {"localhost", "pr-1453.d2x7abc.amplifyapp.com"}
    assert aside["localhost"]["why"] == "test host"
    aug = next(m for m in result["monthly"] if m["month"] == "2026-08")
    assert aug["test_host"] == 31 * 3


def test_the_burst_uses_the_same_rule_as_the_crm_side(result):
    assert [(b["day"], b["part"]) for b in result["burst_days"]] == [
        ("2026-07-27", "start"), ("2026-07-28", "tail"), ("2026-07-29", "tail")]
    july = next(m for m in result["monthly"] if m["month"] == "2026-07")
    assert july["burst_day"] == 300 + 40 + 30 + 3 * 4  # the spam plus that day's real events
    assert july["clean_events"] == july["events"] - july["test_host"] - july["burst_day"]


def test_repeat_firing_month(result):
    july = next(m for m in result["repeats"] if m["month"] == "2026-07")
    assert july["events_per_user"] == 2.6


def test_the_unexplained_step_is_named(result):
    assert [(s["from"], s["to"], s["ratio"]) for s in result["steps"]] == [("2025-08", "2025-09", 0.48)]  # 30x4 / 31x8 at level sessions


def test_not_set_share(result):
    aug = next(m for m in result["organic_landing_not_set"] if m["month"] == "2025-08")
    assert aug["share"] == 0.109


def test_findings(result):
    codes = {i["code"]: i for i in result["issues"]}
    assert set(codes) == {"ga4_conversion_contamination", "ga4_repeat_firing", "ga4_tracking_step", "ga4_landing_not_set"}
    assert "2025-08 to 2025-09" in codes["ga4_tracking_step"]["finding"]
    assert codes["ga4_tracking_step"]["confidence"] == "Hypothesis"
    assert "localhost" in codes["ga4_conversion_contamination"]["evidence"]


def test_production_host_inferred_when_not_given():
    r = ga.analyse(fixture())
    assert r["hosts"]["production_hosts"] == [PROD] and r["hosts"]["production_inferred"] is True
    assert any("inferred" in line or "taken as production" in line for line in r["limits"])


def test_a_clean_property_raises_nothing():
    daily = [daily_row(d, PROD, "Organic Search", 5) for d in days(date(2026, 1, 1), date(2026, 3, 31))]
    ds = {"daily": {"rows": daily},
          "monthly_users": {"rows": [{"yearMonth": m, "eventCount": 150.0, "totalUsers": 140.0} for m in ("202601", "202602", "202603")]},
          "monthly_sessions": {"rows": [{"yearMonth": m, "sessionDefaultChannelGroup": "Organic Search", "sessions": 9000.0}
                                        for m in ("202601", "202602", "202603")]},
          "organic_not_set": {"rows": []}}
    assert ga.analyse(ds, [PROD])["issues"] == []


def test_replay_and_monthly_csv_feed_conversion_reconcile(tmp_path):
    rows = tmp_path / "ga4.json"
    rows.write_text(json.dumps(fixture()))
    monthly = tmp_path / "ga4-monthly.csv"
    run = subprocess.run([sys.executable, os.path.join(SCRIPTS, "ga4_audit.py"), "--replay", str(rows),
                          "--production-host", PROD, "--save-monthly", str(monthly), "--json"],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    assert out["monthly_written"] == str(monthly)
    import conversion_reconcile as cr
    organic = cr.load_ga4(str(monthly), "Organic Search")
    assert organic["2025-08"] == 31 * 4 and organic["2025-09"] == 30 * 2
    assert "2026-07" in organic


def test_fetch_builds_filtered_paged_requests():
    types = pytest.importorskip("google.analytics.data_v1beta.types")

    class Value:
        def __init__(self, v):
            self.value = v

    class Row:
        def __init__(self, dims, mets):
            self.dimension_values = [Value(d) for d in dims]
            self.metric_values = [Value(m) for m in mets]

    class Response:
        def __init__(self, rows, total):
            self.rows, self.row_count = rows, total

    class Client:
        def __init__(self):
            self.requests = []

        def run_report(self, request):
            self.requests.append(request)
            if request.offset == 0:
                return Response([Row(["20260701", PROD, "Organic Search"], ["3"])], 2)
            return Response([Row(["20260702", PROD, "Organic Search"], ["4"])], 2)

    client = Client()
    block = ga.run_rows(client, "123", "2026-07-01", "2026-07-02", ["date", "hostName", "sessionDefaultChannelGroup"],
                        ["eventCount"], {"eventName": "generate_lead"})
    assert [r["eventCount"] for r in block["rows"]] == [3.0, 4.0]
    assert [r.offset for r in client.requests] == [0, 1]
    assert client.requests[0].dimension_filter.filter.string_filter.value == "generate_lead"
    two = ga._filter({"sessionDefaultChannelGroup": "Organic Search", "landingPage": "(not set)"})
    assert len(two.and_group.expressions) == 2


def test_a_step_while_traffic_also_moves_is_not_called_a_tracking_change():
    # events -30% while sessions +30%: the rate halves, but a traffic shift (new, less ready visitors)
    # explains that as well as a tag change does, so no step is claimed.
    series = [{"month": "2026-01", "clean_events": 100}, {"month": "2026-02", "clean_events": 70}]
    sessions = [{"yearMonth": "202601", "sessions": 10000.0}, {"yearMonth": "202602", "sessions": 13000.0}]
    assert ga.step_check(series, sessions) == []
    steady = [{"yearMonth": "202601", "sessions": 10000.0}, {"yearMonth": "202602", "sessions": 10500.0}]
    assert ga.step_check([{"month": "2026-01", "clean_events": 100}, {"month": "2026-02", "clean_events": 50}], steady)
