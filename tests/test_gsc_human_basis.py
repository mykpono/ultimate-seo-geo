"""gsc_insights.py human basis: which Search Console queries people could not have produced.

Fixture rows are real Improvado query rows (Sep 2-15 and Aug 18-31 2026) from the v4.1
audit. The client's own board found that 88% of the site's apparent position gain in that
period was machine traffic; before this change, low-CTR advice told the site to rewrite
titles for queries no person had typed.
"""

import os
import sys
from datetime import date

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import gsc_insights as gi  # noqa: E402

AD_FRAUD = "https://improvado.io/blog/best-ad-fraud-detection-software"
BLOG = "https://improvado.io/blog/looker-studio"


def row(query, clicks, impressions, position, page=BLOG):
    return {"query": query, "page": page, "clicks": clicks, "impressions": impressions,
            "ctr": clicks / impressions if impressions else 0.0, "position": position}


# --- one query at a time: real rows --------------------------------------------

@pytest.mark.parametrize("query,clicks,impressions,position,reason", [
    ("ad fraud detection software", 0, 237_872, 2.1, "impossible_ctr"),
    ("ad fraud", 1, 191_486, 5.5, "impossible_ctr"),
    ("ad verification software", 0, 107_639, 10.2, "impossible_ctr"),  # page two still has a floor
    ("site:improvado.io/integrations", 0, 40, 3.0, "search_operator"),
    ("http www.seomoz.org rank-tracker", 0, 12, 40.0, "url_in_query"),
    ('"scott bennett" "improvado" phone fax', 0, 7_810, 5.0, "quoted_template"),
    ('"roku" data governance strategy', 0, 7_441, 9.9, "quoted_template"),
    ("%video marketing trends this month 2025 after:2026-08-14", 0, 30, 8.0, "scraper_syntax"),
])
def test_machine_queries(query, clicks, impressions, position, reason):
    label, reasons = gi.classify_query(query, clicks, impressions, position)
    assert label == "machine" and reason in reasons


@pytest.mark.parametrize("query,clicks,impressions,position", [
    ("improvado", 321, 800, 1.5),
    ("looker studio", 37, 38_056, 7.1),      # low CTR, but clicks a person can produce at that volume
    ("data quality management", 0, 8_568, 12.4),  # page two, zero clicks: too few impressions to rule out people
    ('"deepseek"', 0, 7, 5.0),               # one quoted word alone is how people search a name
    ("#instagramgrowth", 1, 12, 4.5),
    ("ad fraud detection software", 0, 400, 2.0),  # below the impression floor: not enough evidence
])
def test_human_queries(query, clicks, impressions, position):
    assert gi.classify_query(query, clicks, impressions, position) == ("human", [])


def test_long_agent_style_queries_are_set_apart_not_called_machine():
    q = "what are the best tools for building content pipelines that support multiple versions across platforms"
    assert gi.classify_query(q, 0, 90, 8.0) == ("agent_like", ["long_query"])


def test_known_limit_navigational_query_for_another_site():
    # 'banneradsites' is someone looking for another site; 7 clicks on 60,649 impressions at 5.6 is
    # still below any human floor, so it is set aside. The reason code says why, so a reader can overrule it.
    label, reasons = gi.classify_query("banneradsites", 7, 60_649, 5.6)
    assert label == "machine" and reasons == ["impossible_ctr"]


def test_poisson_tail():
    assert gi._poisson_cdf(0, 2.0) == pytest.approx(0.1353, abs=1e-4)
    assert gi._poisson_cdf(37, 38.0) > 0.4
    assert gi._poisson_cdf(0, 475.7) < 1e-200 or gi._poisson_cdf(0, 475.7) == 0.0
    assert gi._poisson_cdf(5, 0.0) == 1.0


def test_floor_ends_at_position_20():
    assert gi.human_ctr_floor(2.9) == 0.002
    assert gi.human_ctr_floor(10.0) == 0.001
    assert gi.human_ctr_floor(19.9) == 0.0005
    assert gi.human_ctr_floor(25.0) is None


def test_classification_is_per_query_across_pages():
    # 5,000 impressions with no click at 2.7 is not conclusive (10 expected, P ~ 4.5e-5);
    # the same query on two pages, 10,000 impressions, is (20 expected, P ~ 2e-9).
    one = row("ad fraud protection platform", 0, 5_000, 2.7, AD_FRAUD)
    assert gi.classify_queries([one])["ad fraud protection platform"]["label"] == "human"
    labels = gi.classify_queries([one, row("ad fraud protection platform", 0, 5_000, 2.7, BLOG)])
    assert labels["ad fraud protection platform"]["label"] == "machine"
    assert labels["ad fraud protection platform"]["impressions"] == 10_000


# --- the human basis -------------------------------------------------------------

AUG = [row("improvado", 401, 772, 1.4), row("looker studio", 40, 30_000, 8.0),
       row("ad fraud", 2, 10_124, 9.0, AD_FRAUD)]
SEP = [row("improvado", 321, 800, 1.5), row("looker studio", 37, 38_056, 7.1),
       row("ad fraud", 1, 191_486, 5.5, AD_FRAUD), row("ad fraud detection software", 0, 237_872, 2.1, AD_FRAUD)]


def test_human_basis_separates_the_gain():
    result = gi.human_basis(SEP, gi.classify_queries(SEP), AUG)
    cur = result["current"]
    assert cur["machine"]["impressions"] == 191_486 + 237_872
    assert cur["human"]["clicks"] == 321 + 37
    assert result["non_human_share_of_impressions"] == pytest.approx(429_358 / 468_214, abs=1e-4)
    change = result["change"]
    assert change["blended"]["position"] < change["human"]["position"] <= 0
    # 'ad fraud' was human in August (10k impressions at 9.0 with 2 clicks is possible), machine in September
    assert result["previous"]["machine"]["impressions"] == 0
    assert 0.5 < change["position_gain_from_non_human"] <= 1
    assert [p["page"] for p in result["pages_mostly_non_human"]] == [AD_FRAUD]
    assert result["reasons"]["impossible_ctr"]["queries"] == 2


def test_human_basis_without_a_previous_window():
    result = gi.human_basis(SEP, gi.classify_queries(SEP))
    assert result["change"]["status"] == "not measured"


def test_non_human_finding_names_the_gain_and_the_pages():
    dataset = {"site_url": "sc-domain:improvado.io", "windows": {"current": ["2026-09-02", "2026-09-15"]},
               "query_page": {"rows": SEP}, "query_page_previous": {"rows": AUG}, "pages": {}}
    out = gi.analyse(dataset, {"human_basis"})
    issue = next(i for i in out["issues"] if i["code"] == "non_human_queries")
    assert issue["lane"] == "Decision" and issue["severity"] == "medium"
    assert "of the apparent gain" in issue["finding"]
    assert issue["urls"] == [AD_FRAUD]


def test_no_finding_when_the_share_is_small():
    rows = [row("improvado", 321, 800, 1.5), row("looker studio", 37, 38_056, 7.1),
            row("site:improvado.io", 0, 40, 1.0)]
    out = gi.analyse({"query_page": {"rows": rows}, "pages": {}}, {"human_basis"})
    assert not [i for i in out["issues"] if i["code"] == "non_human_queries"]


# --- the other analyses read human queries only ---------------------------------

def _curve_rows(position, ctr, n=6, impressions=500):
    return [row(f"bench {position}-{i}", round(impressions * ctr), impressions, position, f"https://ex.com/b{position}-{i}")
            for i in range(n)]


def test_low_ctr_no_longer_asks_to_rewrite_titles_for_machine_queries():
    rows = _curve_rows(2, 0.20) + [row("ad fraud detection software", 0, 237_872, 2.1, AD_FRAUD),
                                   row("people query", 10, 2_000, 2.0)]
    dataset = {"query_page": {"rows": rows}, "pages": {}}
    default = gi.analyse(dataset, {"low_ctr"})
    assert [i["query"] for i in default["low_ctr"]["items"]] == ["people query"]
    assert default["queries_set_aside"]["impressions"] == 237_872
    kept = gi.analyse(dataset, {"low_ctr"}, opts={"include_machine": True})
    assert "ad fraud detection software" in [i["query"] for i in kept["low_ctr"]["items"]]
    assert kept["queries_set_aside"] is None


def test_fetch_adds_one_previous_window_request_for_human_basis():
    class Service:
        def __init__(self):
            self.bodies = []

        def searchanalytics(self):
            return self

        def query(self, siteUrl, body):
            self.bodies.append(body)
            return self

        def execute(self):
            return {"rows": []}

    service = Service()
    data = gi.fetch_dataset(service, "sc-domain:x.com", date(2026, 9, 15), 14, history=False, max_rows=100,
                            previous_queries=True)
    assert data["windows"]["previous"] == ["2026-08-19", "2026-09-01"]
    assert data["query_page_previous"] == {"rows": [], "truncated": False}
    assert [b["dimensions"] for b in service.bodies] == [["query", "page"], ["page"], ["query", "page"]]
