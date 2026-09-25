"""conversion_reconcile.py: demo requests on two rulers, GA4 events and clean CRM people.

No CRM export ships with the repo, so the end-to-end fixture is generated. Its shape
follows what Improvado measured and published in its verification of report v4.1
(22 Sep 2026): 552 distinct clean business people asked for a demo in June-August 2025
and 591 in 2026 (+7%); GA4 organic demo events went 460 -> 257 (-44%); a spam burst of
627 submissions on 27 July was followed by 140, 151, 126 and 113 (1,157 in five days);
the team's own test submissions came from improvado.io addresses and from localhost and
pr-*.amplifyapp.com pages. The fixture reproduces those totals, not the private rows.
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

import conversion_reconcile as cr  # noqa: E402

HEADER = ["Conversion Date", "Email", "Page URL", "Form", "Original Source", "Lifecycle Stage"]
PEOPLE = {"2025-06": 154, "2025-07": 199, "2025-08": 199, "2026-06": 259, "2026-07": 159, "2026-08": 173}
SPAM = {date(2026, 7, 27): 627, date(2026, 7, 28): 140, date(2026, 7, 29): 151, date(2026, 7, 30): 126, date(2026, 7, 31): 113}
GA4_ORGANIC = {"2025-06": 150, "2025-07": 160, "2025-08": 150, "2026-06": 90, "2026-07": 87, "2026-08": 80}  # 460 -> 257


def month_days(month):
    y, m = map(int, month.split("-"))
    d = date(y, m, 1)
    while d.month == m:
        yield d
        d += timedelta(days=1)


def fixture_rows():
    rows = []
    for month, people in PEOPLE.items():
        # Improvado's published count leaves 27-31 July 2026 out whole, so the fixture's real people
        # submit on the other days; a real submission on a burst day is set aside with the spam.
        days = [d for d in month_days(month) if d not in SPAM]
        for i in range(people):
            day = days[i % len(days)]
            email = f"buyer{i}@company{month.replace('-', '')}-{i}.com"
            source = "ORGANIC_SEARCH" if i % 3 == 0 else "PAID_SEARCH"
            stage = "salesqualifiedlead" if i % 4 == 0 else "lead"
            host = "https://improvado.io/register/talk-to-an-expert" if i % 5 else "https://lp.improvado.io/demo"
            rows.append([day.isoformat() + " 10:00", email, host, "Demo request", source, stage])
            if i % 10 == 0:  # a real person submitting twice
                rows.append([day.isoformat() + " 10:05", email.upper(), host, "Demo request", source, stage])
        if month.startswith("2026"):
            for i, day in enumerate(days):
                # the team testing on production, and on developer and preview hosts
                rows.append([day.isoformat() + " 12:00", f"qa{i % 4}@improvado.io", "https://improvado.io/register/talk-to-an-expert", "Demo request", "DIRECT_TRAFFIC", "lead"])
                rows.append([day.isoformat() + " 12:30", f"dev{i}@testmail-company.com", "http://localhost:3000/register/talk-to-an-expert", "Demo request", "DIRECT_TRAFFIC", "lead"])
                rows.append([day.isoformat() + " 13:00", f"pr{i}@testmail-company.com", "https://pr-1453.d2x7abc.amplifyapp.com/register", "Demo request", "DIRECT_TRAFFIC", "lead"])
    for day, count in SPAM.items():
        for i in range(count):
            domain = "gmail.com" if i % 2 else "taomail.kdns.fr"
            rows.append([day.isoformat() + "T03:00:00Z", f"bot{day.day}-{i}@{domain}", "https://improvado.io/register/talk-to-an-expert",
                         "Demo request", "OFFLINE", "lead"])
    return rows


@pytest.fixture
def exports(tmp_path):
    crm = tmp_path / "hubspot-form-submissions.csv"
    with open(crm, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerows(fixture_rows())
    ga4 = tmp_path / "ga4-demo-events.csv"
    with open(ga4, "w", newline="") as fh:
        fh.write("# ----------------------------------------\n# Key events by month\n")
        w = csv.writer(fh)
        w.writerow(["Year month", "Session default channel group", "Key events"])
        for month, count in GA4_ORGANIC.items():
            w.writerow([month.replace("-", ""), "Organic Search", count])
            w.writerow([month.replace("-", ""), "Paid Search", count * 2])
    return crm, ga4


def run(crm, ga4, *extra):
    cmd = [sys.executable, os.path.join(SCRIPTS, "conversion_reconcile.py"), "--crm", str(crm), "--ga4", str(ga4),
           "--ga4-channel", "Organic Search", "--production-host", "improvado.io", "--production-host", "lp.improvado.io",
           "--internal-domain", "improvado.io", "--business-only", "--compare", "2025-06:2025-08,2026-06:2026-08", "--json", *extra]
    out = subprocess.run(cmd, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr + out.stdout
    return json.loads(out.stdout)


# --- end to end: the Improvado shape ----------------------------------------------

def test_clean_people_rise_while_ga4_organic_falls(exports):
    result = run(*exports)
    cmp = result["comparisons"][0]["rulers"]
    assert (cmp["people"]["before"], cmp["people"]["after"]) == (552, 591)
    assert cmp["people"]["change_pct"] == 7.1
    assert (cmp["ga4_events"]["before"], cmp["ga4_events"]["after"]) == (460, 257)
    assert cmp["ga4_events"]["change_pct"] == -44.1
    assert cmp["submissions"]["after"] > cmp["submissions"]["before"] * 3  # raw rows balloon with tests and spam
    d = result["comparisons"][0]["disagreements"]
    assert any(x["raw"] == "ga4_events" and x["clean"] == "people" and x["opposite_directions"] for x in d)


def test_the_spam_burst_and_its_tail_are_set_aside(exports):
    result = run(*exports)
    bursts = {b["day"]: b["part"] for b in result["burst_days"]}
    assert bursts == {"2026-07-27": "start", "2026-07-28": "tail", "2026-07-29": "tail",
                      "2026-07-30": "tail", "2026-07-31": "tail"}
    july = next(m for m in result["months"] if m["month"] == "2026-07")
    assert july["set_aside"]["burst_day"] >= 1157  # the 1,157 spam rows, plus the tests those days
    assert july["people"] == 159
    # what the day-level exclusion costs: about a median day of real rows per burst day
    assert 0 < result["burst_real_submissions_lost_estimate"] < 100


def test_team_and_preview_host_tests_are_set_aside(exports):
    result = run(*exports)
    aug = next(m for m in result["months"] if m["month"] == "2026-08")
    assert aug["set_aside"]["internal"] == 31
    assert aug["set_aside"]["test_host"] == 62  # localhost and pr-*.amplifyapp.com, one each a day
    assert aug["set_aside_share"] > 0.3


def test_organic_and_qualified_people_come_from_the_crm_columns(exports):
    result = run(*exports)
    june = next(m for m in result["months"] if m["month"] == "2025-06")
    assert june["organic_people"] == len(range(0, 154, 3))
    assert june["qualified_people"] == len(range(0, 154, 4))


def test_findings(exports):
    codes = {i["code"]: i for i in run(*exports)["issues"]}
    assert set(codes) == {"conversion_contamination", "rulers_disagree"}
    assert codes["rulers_disagree"]["kind"] == "data_gap" and codes["rulers_disagree"]["lane"] == "Decision"
    assert "opposite directions" in codes["rulers_disagree"]["finding"]
    assert "burst days 2026-07-27" in codes["conversion_contamination"]["evidence"]


def test_without_burst_detection_the_spam_counts_as_people(exports):
    result = run(*exports, "--no-burst-detection")
    july = next(m for m in result["months"] if m["month"] == "2026-07")
    # the taomail.kdns.fr half of the spam is not free mail, so it passes as business people
    assert july["people"] > 159 + 500
    assert result["burst_days"] == []


def test_known_bad_days_can_be_named(exports):
    result = run(*exports, "--no-burst-detection", "--exclude-dates", "2026-07-27:2026-07-31")
    assert next(m for m in result["months"] if m["month"] == "2026-07")["people"] == 159


# --- units ----------------------------------------------------------------------

@pytest.mark.parametrize("host,test", [
    ("localhost", True), ("127.0.0.1", True), ("pr-1453.d2x7abc.amplifyapp.com", True),
    ("staging.example.com", True), ("my-site.vercel.app", True), ("preview-42.example.com", True),
    ("example.com", False), ("www.example.com", False), ("lp.example.com", False), ("developers.example.com", False),
])
def test_test_hosts(host, test):
    assert bool(cr.TEST_HOST.search(host)) is test


def test_classify_reasons():
    base = {"day": date(2026, 8, 3), "host": "example.com"}
    kw = dict(production_hosts={"example.com"}, internal_domains={"example.com"}, bursts=set(), business_only=True)
    assert cr.classify({**base, "email": ""}, **kw) == "missing_email"
    assert cr.classify({**base, "email": "qa@mail.example.com"}, **kw) == "internal"
    assert cr.classify({**base, "email": "a@b.com", "host": "evil.com"}, **kw) == "test_host"
    assert cr.classify({**base, "email": "a@gmail.com"}, **kw) == "free_mail"
    assert cr.classify({**base, "email": "a@b.com", "host": None}, **kw) is None  # no page URL: kept
    assert cr.classify({**base, "email": "a@b.com"}, **{**kw, "bursts": {date(2026, 8, 3)}}) == "burst_day"


def test_burst_needs_a_baseline_and_a_floor():
    subs = [{"day": date(2026, 7, 1) + timedelta(days=i)} for i in range(20) for _ in range(5)]
    subs += [{"day": date(2026, 7, 21)} for _ in range(25)]  # 5x the median but under 30 submissions
    assert cr.burst_days(subs) == {}
    subs += [{"day": date(2026, 7, 21)} for _ in range(10)]  # now 35
    assert list(cr.burst_days(subs)) == [date(2026, 7, 21)]


def test_ga4_formats(tmp_path):
    daily = tmp_path / "daily.csv"
    daily.write_text("Date,Event count\n20260701,3\n20260702,4\n20260801,1\n")
    assert cr.load_ga4(str(daily)) == {"2026-07": 7, "2026-08": 1}
    js = tmp_path / "ga4.json"
    js.write_text(json.dumps({"rows": [{"date": "2026-07-03", "conversions": 2}, {"date": "2026-07-09", "conversions": 1}]}))
    assert cr.load_ga4(str(js)) == {"2026-07": 3}
    bad = tmp_path / "bad.csv"
    bad.write_text("Page,Views\n/a,3\n")
    with pytest.raises(ValueError, match="month/date column and a count column"):
        cr.load_ga4(str(bad))


@pytest.mark.parametrize("text,expected", [
    ("2026-07-27", date(2026, 7, 27)), ("2026-07-27T10:15:00Z", date(2026, 7, 27)),
    ("2026-07-27T10:15:00.123+02:00", date(2026, 7, 27)), ("07/27/2026 10:15 AM", date(2026, 7, 27)),
    ("27.07.2026", date(2026, 7, 27)), ("1785139200000", date(2026, 7, 27)), ("soon", None),
])
def test_dates(text, expected):
    assert cr.parse_date(text) == expected


def test_columns_found_by_name_or_mapped(tmp_path):
    assert cr.find_columns(["E-mail", "Created At", "Page"], {})["email"] == "E-mail"
    with pytest.raises(ValueError, match="no email column"):
        cr.find_columns(["Name", "Created At"], {})
    assert cr.find_columns(["Contact", "Created At"], {"email": "Contact"})["email"] == "Contact"


def test_rulers_that_agree_raise_nothing():
    table = [{"month": "2025-06", "people": 100, "ga4_events": 200}, {"month": "2026-06", "people": 110, "ga4_events": 215}]
    cmp = cr.compare(table, ("2025-06", "2025-06"), ("2026-06", "2026-06"))
    assert cmp["disagreements"] == [] and "agree" in cmp["verdict"]
