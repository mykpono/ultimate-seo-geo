"""page_type_classifier.py: URL rules by section and slug, page signals, coverage gaps.

The URL corpus below is drawn from the real-site calibration (posthog.com,
developers.cloudflare.com, smashingmagazine.com, python.org) plus the shapes in
references/industry-templates.md. Each false positive that run exposed is a
case here, named for it:

  * ``/category/pricing`` was a pricing page (section words matched deep in the path)
  * ``/docs/x-in-python`` was a location page (the ``-in-`` slug pattern)
  * ``/workers-ai/features/x`` on a docs site was a feature page (second-segment matching)
  * smashingmagazine.com was a SaaS site (one /category/pricing URL beat 6,900 articles)
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import page_type_classifier as ptc  # noqa: E402
import site_graph  # noqa: E402

S = "https://ex.com"


def _url(label, url):
    return (url, label)


# --- classify_url: section rules -------------------------------------------------

@pytest.mark.parametrize("url,label", [
    ("https://ex.com/", "homepage"),
    ("https://ex.com", "homepage"),
    ("https://ex.com/pricing", "pricing"),
    ("https://ex.com/pricing/", "pricing"),
    ("https://ex.com/plans/enterprise", "pricing"),
    ("https://ex.com/vs/competitor", "comparison"),
    ("https://ex.com/compare/a-b", "comparison"),
    ("https://ex.com/alternatives/", "alternatives"),
    ("https://ex.com/customers/acme", "case_study"),
    ("https://ex.com/case-studies/acme", "case_study"),
    ("https://ex.com/integrations/slack", "integration"),
    ("https://ex.com/apps/hubspot", "integration"),
    ("https://ex.com/teams/sales", "persona_icp"),
    ("https://ex.com/industries/healthcare", "industry_market"),
    ("https://ex.com/solutions/onboarding", "solution_use_case"),
    ("https://ex.com/use-cases/onboarding", "solution_use_case"),
    ("https://ex.com/features/dashboards", "product_feature"),
    ("https://ex.com/product/analytics", "product_feature"),
    ("https://ex.com/platform/", "product_feature"),
    ("https://ex.com/glossary/churn", "glossary_definition"),
    ("https://ex.com/guides/onboarding", "pillar_guide"),
    ("https://ex.com/handbook/engineering", "pillar_guide"),
    ("https://ex.com/templates/okr", "tool_template"),
    ("https://ex.com/docs/getting-started", "docs_help"),
    ("https://ex.com/help/article-1", "docs_help"),
    ("https://ex.com/api/reference", "docs_help"),
    ("https://ex.com/questions/how-do-i", "community_qa"),
    ("https://ex.com/community/thread-1", "community_qa"),
    ("https://ex.com/faq", "faq"),
    ("https://ex.com/author/jane-doe", "author"),
    ("https://ex.com/tags/css", "tag_archive"),
    ("https://ex.com/category/design", "tag_archive"),
    ("https://ex.com/blog/post-title", "blog_article"),
    ("https://ex.com/changelog/2026-09", "blog_article"),
    ("https://ex.com/news/launch", "blog_article"),
    ("https://ex.com/demo", "landing_campaign"),
    ("https://ex.com/events/summit", "landing_campaign"),
    ("https://ex.com/collections/shoes", "ecom_category"),
    ("https://ex.com/shop/shoes", "ecom_category"),
    ("https://ex.com/products/red-shoe", "ecom_product"),
    ("https://ex.com/p/12345", "ecom_product"),
    ("https://ex.com/services/plumbing", "location_service"),
    ("https://ex.com/locations/austin", "location_service"),
    ("https://ex.com/about", "about_company"),
    ("https://ex.com/careers/", "about_company"),
    ("https://ex.com/security", "about_company"),
    ("https://ex.com/contact-us", "contact"),
    ("https://ex.com/privacy-policy", "legal"),
    ("https://ex.com/terms", "legal"),
    ("https://ex.com/some-random-page", "generic"),
    ("https://ex.com/psf/sponsors", "generic"),
])
def test_section_rules(url, label):
    assert ptc.classify_url(url)["label"] == label


# --- classify_url: slug rules win over the section ---------------------------------

@pytest.mark.parametrize("url,label,secondary", [
    ("https://ex.com/blog/notion-vs-obsidian", "comparison", "blog_article"),
    ("https://ex.com/2015/03/sass-vs-less", "comparison", "blog_article"),
    ("https://ex.com/blog/best-jira-alternatives", "alternatives", "blog_article"),
    ("https://ex.com/blog/what-is-a-feature-flag", "glossary_definition", "blog_article"),
    ("https://ex.com/docs/what-is-a-context-warehouse", "glossary_definition", "docs_help"),
    ("https://ex.com/blog/ultimate-guide-to-okrs", "pillar_guide", "blog_article"),
    ("https://ex.com/blog/why-is-my-site-slow", "pain_point_problem", "blog_article"),
    ("https://ex.com/blog/how-to-fix-crawl-errors", "pain_point_problem", "blog_article"),
    ("https://ex.com/blog/page/3", "tag_archive", "blog_article"),
    ("https://ex.com/blog?page=2", "tag_archive", "blog_article"),
    ("https://ex.com/for/marketers", "persona_icp", "solution_use_case"),
    ("https://ex.com/solutions/for-healthcare", "industry_market", "solution_use_case"),
    ("https://ex.com/for/onboarding", "solution_use_case", None),
    ("https://ex.com/services/plumber-near-me", "location_service", None),
])
def test_slug_rules_win_and_keep_the_section_as_secondary(url, label, secondary):
    r = ptc.classify_url(url)
    assert (r["label"], r["secondary_label"]) == (label, secondary)


def test_persona_beats_industry_beats_generic_for():
    assert ptc.classify_url("https://ex.com/for/developers")["label"] == "persona_icp"
    assert ptc.classify_url("https://ex.com/for/fintech")["label"] == "industry_market"
    assert ptc.classify_url("https://ex.com/for/something-else")["label"] == "solution_use_case"


# --- classify_url: the calibration false positives -------------------------------------

@pytest.mark.parametrize("url,label", [
    ("https://ex.com/category/pricing", "tag_archive"),          # smashingmagazine.com
    ("https://ex.com/category/integration", "tag_archive"),
    ("https://ex.com/docs/endpoints/pricing", "docs_help"),      # posthog.com
    ("https://ex.com/docs/x-in-python", "docs_help"),            # was location_service
    ("https://ex.com/tutorials/deploy-in-kubernetes", "docs_help"),
    ("https://ex.com/smashing-tv/live-in-berlin", "generic"),
    ("https://ex.com/workers-ai/features/x", "generic"),         # developers.cloudflare.com
    ("https://ex.com/api-shield/security/x", "generic"),
    ("https://ex.com/cache/concepts/retention-vs-freshness/", "comparison"),  # a real comparison, kept
    ("https://ex.com/downloads/windows/", "generic"),            # python.org, was solution_use_case via a loose H1 rule
])
def test_calibration_false_positives_stay_fixed(url, label):
    assert ptc.classify_url(url)["label"] == label


def test_locale_prefix_is_skipped_for_section_matching():
    assert ptc.classify_url("https://ex.com/en/blog/post")["label"] == "blog_article"
    assert ptc.classify_url("https://ex.com/en-us/pricing")["label"] == "pricing"
    assert ptc.classify_url("https://ex.com/de_DE/docs/x")["label"] == "docs_help"
    # A product name is not a locale: its subfolders are not sections.
    assert ptc.classify_url("https://ex.com/workers/pricing")["label"] == "generic"


def test_rule_kind_is_reported():
    assert ptc.classify_url("https://ex.com/pricing")["rule"] == "section"
    assert ptc.classify_url("https://ex.com/en/pricing")["rule"] == "section2"
    assert ptc.classify_url("https://ex.com/blog/a-vs-b")["rule"] == "path"
    assert ptc.classify_url("https://ex.com/zzz")["rule"] is None


# --- extra rules -----------------------------------------------------------------------

def test_extra_rules_are_prepended_and_validated(tmp_path):
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps([
        {"label": "comparison", "pattern": "^/head-to-head/$", "kind": "section"},
        {"label": "case_study", "pattern": "/wins/"},
    ]), encoding="utf-8")
    extra = ptc.load_rules(str(rules))
    assert ptc.classify_url("https://ex.com/head-to-head/a-b", extra)["label"] == "comparison"
    assert ptc.classify_url("https://ex.com/blog/wins/acme", extra)["label"] == "case_study"
    assert ptc.classify_url("https://ex.com/head-to-head/a-b")["label"] == "generic"

    rules.write_text(json.dumps([{"label": "nope", "pattern": "x"}]), encoding="utf-8")
    with pytest.raises(ValueError):
        ptc.load_rules(str(rules))
    rules.write_text(json.dumps({"label": "comparison"}), encoding="utf-8")
    with pytest.raises(ValueError):
        ptc.load_rules(str(rules))


# --- page signals and confidence ------------------------------------------------------------

def _page(url, h1=None, title=None, types=(), anchors=(), depth=1):
    return {
        "url": url, "h1": h1, "title": title, "jsonld_types": list(types),
        "out_links": [{"anchor": a} for a in anchors], "depth": depth,
        "parts": site_graph.url_parts(url), "word_count": 500,
    }


def test_url_and_page_agree_is_confirmed():
    r = ptc.classify_page(_page(S + "/vs/acme", h1="Ex vs Acme"))
    assert (r["label"], r["confidence"]) == ("comparison", "Confirmed")
    assert "h1:comparison" in r["evidence"]


def test_url_rule_alone_is_likely():
    r = ptc.classify_page(_page(S + "/pricing", h1="Simple, honest"))
    assert (r["label"], r["confidence"]) == ("pricing", "Likely")


def test_two_page_signals_override_a_generic_url():
    r = ptc.classify_page(_page(S + "/red-shoe", types=["Product"], anchors=["Add to cart"]))
    assert (r["label"], r["confidence"]) == ("ecom_product", "Likely")


def test_one_page_signal_is_a_hypothesis():
    r = ptc.classify_page(_page(S + "/red-shoe", types=["Product"]))
    assert (r["label"], r["confidence"]) == ("ecom_product", "Hypothesis")


def test_two_page_signals_override_a_url_rule_and_keep_it_as_secondary():
    r = ptc.classify_page(_page(S + "/blog/red-shoe", types=["Product"], anchors=["Buy now"]))
    assert (r["label"], r["secondary_label"], r["confidence"]) == ("ecom_product", "blog_article", "Likely")


def test_pain_point_is_capped_at_hypothesis():
    r = ptc.classify_page(_page(S + "/blog/why-is-my-site-slow", h1="Why is my site slow?"))
    assert (r["label"], r["confidence"]) == ("pain_point_problem", "Hypothesis")


def test_no_signal_generic_has_no_confidence():
    r = ptc.classify_page(_page(S + "/zzz", h1="Hello"))
    assert (r["label"], r["confidence"]) == ("generic", None)


def test_homepage_schema_describes_the_site_not_the_page():
    home = _page(S + "/", types=["SoftwareApplication", "Organization"], depth=0)
    assert ptc.page_signals(home) == {}
    feature = _page(S + "/analytics", types=["SoftwareApplication"])
    assert "product_feature" in ptc.page_signals(feature)


def test_list_valued_and_local_business_subtypes():
    p = _page(S + "/austin", types=["WebPage", "Dentist"])
    assert ptc.page_signals(p)["location_service"] == ["schema:LocalBusiness"]
    p = _page(S + "/jane", types=["Person"])
    assert "author" in ptc.page_signals(p)
    p = _page(S + "/post", types=["Person", "BlogPosting"])
    assert "author" not in ptc.page_signals(p)


def test_persona_and_industry_h1_signals():
    assert "persona_icp" in ptc.page_signals(_page(S + "/x", h1="Analytics for product managers"))
    assert "industry_market" in ptc.page_signals(_page(S + "/x", title="Analytics for healthcare | Ex"))
    assert ptc.page_signals(_page(S + "/x", h1="Download for Windows")) == {}


# --- classify_site -----------------------------------------------------------------------------

def _graph(pages=None, sitemap_urls=(), sitemap_complete=True, crawl_complete=True, site=S + "/"):
    pages = pages or {}
    g = {
        "schema_version": site_graph.GRAPH_SCHEMA_VERSION,
        "site": site,
        "sitemap": {"found": bool(sitemap_urls), "complete": sitemap_complete, "reasons": [] if sitemap_complete else ["stopped after 2 sitemap files"],
                    "urls": {u: {"lastmod": None, "source": "sm"} for u in sitemap_urls}},
        "crawl": {"complete": crawl_complete, "reasons": [] if crawl_complete else ["crawl stopped at max_pages=5: 40 discovered URL(s) not fetched"]},
        "pages": {site_graph.page_key(p["url"]): p for p in pages},
    }
    return g


def _saas_pages():
    return [_page(S + "/", types=["SoftwareApplication", "Organization"], depth=0),
            _page(S + "/pricing", h1="Pricing"), _page(S + "/features/x", h1="X")]


def test_missing_page_types_on_a_complete_saas_inventory():
    urls = [S + "/", S + "/pricing", S + "/features/x", S + "/integrations/slack", S + "/docs/a",
            S + "/blog/a", S + "/about", S + "/customers/acme", S + "/solutions/y"]
    r = ptc.classify_site(_graph(_saas_pages(), urls))
    assert r["site_type"] == "saas"
    assert r["source"]["status"] == "complete"
    missing = {f["label"] for f in r["findings"] if f["type"] == "missing_page_type"}
    assert missing == {"comparison", "alternatives"}
    comp = next(f for f in r["findings"] if f.get("label") == "comparison")
    assert comp["severity"] == "Medium" and "opportunity" in comp["tags"] and comp["confidence"] == "Likely"
    assert "33%" in comp["evidence"]
    assert comp["fix"].startswith("Create /vs/")


def test_low_severity_for_non_money_types():
    urls = [S + "/", S + "/pricing", S + "/features/x", S + "/vs/a", S + "/alternatives/a", S + "/integrations/slack",
            S + "/customers/acme", S + "/solutions/y", S + "/blog/a"]  # no docs, no about
    r = ptc.classify_site(_graph(_saas_pages(), urls))
    sev = {f["label"]: f["severity"] for f in r["findings"] if f["type"] == "missing_page_type"}
    assert sev == {"docs_help": "Low", "about_company": "Low"}


def test_incomplete_inventory_is_inconclusive_not_a_finding():
    r = ptc.classify_site(_graph(_saas_pages(), [S + "/", S + "/pricing"], sitemap_complete=False, crawl_complete=False))
    assert r["source"]["status"] == "inconclusive"
    types = [f["type"] for f in r["findings"]]
    assert "missing_page_type" not in types
    inc = next(f for f in r["findings"] if f["type"] == "coverage_inconclusive")
    assert inc["severity"] == "Info" and "comparison" in inc["labels"]
    assert r["source"]["reasons"]


def test_complete_crawl_without_sitemap_is_enough():
    r = ptc.classify_site(_graph(_saas_pages(), (), sitemap_complete=False, crawl_complete=True))
    assert r["source"]["status"] == "complete"
    assert any(f["type"] == "missing_page_type" for f in r["findings"])


def test_site_type_override_changes_expectations():
    r = ptc.classify_site(_graph(_saas_pages(), [S + "/", S + "/pricing"]), site_type="local")
    assert r["site_type"] == "local" and r["site_type_detected"] == "saas"
    assert {f["label"] for f in r["findings"] if f["type"] == "missing_page_type"} == set(ptc.EXPECTED_BY_SITE_TYPE["local"])


def test_docs_and_generic_sites_have_no_expectations():
    r = ptc.classify_site(_graph([], [S + "/", S + "/x"]), site_type="docs")
    assert not [f for f in r["findings"] if f["type"] in ("missing_page_type", "coverage_inconclusive")]


def test_saas_remaps_products_to_features():
    urls = [S + "/", S + "/pricing", S + "/products/analytics", S + "/products/flags"]
    r = ptc.classify_site(_graph(_saas_pages(), urls))
    assert r["site_type"] == "saas"
    assert r["matrix"]["product_feature"]["count"] == 3 and r["matrix"]["ecom_product"]["count"] == 0
    assert any(e.startswith("remapped:") for e in r["pages"][S + "/products/flags"]["evidence"])


def test_matrix_counts_share_and_intent_rollup():
    urls = [S + "/", S + "/blog/a", S + "/blog/b", S + "/vs/x"]
    r = ptc.classify_site(_graph([], urls), site_type="generic")
    assert r["urls_classified"] == 4
    assert r["matrix"]["blog_article"] == {**r["matrix"]["blog_article"], "count": 2, "share": 0.5, "intent": "TOFU"}
    assert r["by_intent"]["BOFU"]["count"] == 1 and r["by_intent"]["TOFU"]["count"] == 2
    assert r["matrix"]["blog_article"]["families"] == ["blog"]


def test_families_group_by_label_and_first_dir_with_representatives():
    pages = [_page(S + "/blog/a"), _page(S + "/blog/b"), _page(S + "/news/c")]
    r = ptc.classify_site(_graph(pages, [S + "/blog/a", S + "/blog/b", S + "/news/c", S + "/blog/d"]), site_type="generic")
    fam = {(f["label"], f["dir_1"]): f for f in r["families"]}
    assert fam[("blog_article", "blog")]["count"] == 3 and fam[("blog_article", "blog")]["fetched"] == 2
    assert fam[("blog_article", "blog")]["representatives"] == [S + "/blog/a", S + "/blog/b"]
    assert fam[("blog_article", "blog")]["avg_word_count"] == 500


def test_unclassified_share_warning():
    urls = [S + f"/thing-{i}" for i in range(25)]
    r = ptc.classify_site(_graph([], urls), site_type="generic")
    w = next(f for f in r["findings"] if f["type"] == "unclassified_share")
    assert w["severity"] == "Info" and "--rules" in w["fix"]


def test_intent_imbalance_uses_funnel_pages_only():
    """posthog.com: 54% community Q&A and 29% docs must not make BOFU look thin."""
    # BOFU is 6 of 57 funnel URLs (10%) but 6 of 458 URLs overall (1%): only the funnel share counts.
    urls = [S + "/", S + "/pricing"] + [S + f"/questions/{i}" for i in range(400)] + [S + f"/blog/{i}" for i in range(50)] + [S + f"/vs/{i}" for i in range(5)]
    r = ptc.classify_site(_graph(_saas_pages(), urls), site_type="saas")
    assert r["by_intent"]["BOFU"]["count"] == 6 and r["by_intent"]["support"]["count"] == 400
    assert not [f for f in r["findings"] if f["type"] == "intent_imbalance"]
    urls = [S + "/", S + "/pricing"] + [S + f"/blog/{i}" for i in range(60)]
    r = ptc.classify_site(_graph(_saas_pages(), urls), site_type="saas")  # auto would say publisher
    imb = next(f for f in r["findings"] if f["type"] == "intent_imbalance")
    assert imb["severity"] == "Low" and "opportunity" in imb["tags"]


def test_word_floor_finding_needs_two_fetched_pages():
    thin = [dict(_page(S + f"/blog/{i}"), word_count=200) for i in range(2)]
    r = ptc.classify_site(_graph(thin, [p["url"] for p in thin]), site_type="generic")
    f = next(f for f in r["findings"] if f["type"] == "type_word_floor")
    assert f["label"] == "blog_article" and "200 words" in f["finding"]
    r = ptc.classify_site(_graph(thin[:1], [thin[0]["url"]]), site_type="generic")
    assert not [f for f in r["findings"] if f["type"] == "type_word_floor"]


def test_findings_are_severity_ordered_and_carry_the_contract_fields():
    urls = [S + "/", S + "/pricing"] + [S + f"/thing-{i}" for i in range(25)]
    r = ptc.classify_site(_graph(_saas_pages(), urls))
    sev = [f["severity"] for f in r["findings"]]
    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
    assert sev == sorted(sev, key=order.get)
    for f in r["findings"]:
        for k in ("type", "severity", "finding", "evidence", "impact", "fix", "confidence"):
            assert f.get(k), (f["type"], k)


# --- site type detection --------------------------------------------------------------------------

def test_publisher_is_checked_before_saas():
    """smashingmagazine.com: one /category/pricing URL must not make it a SaaS site."""
    urls = [S + "/", S + "/category/pricing"] + [S + f"/2020/01/post-{i}" for i in range(30)] + [S + f"/author/{i}" for i in range(5)]
    r = ptc.classify_site(_graph([], urls))
    assert r["site_type"] == "publisher"


def test_docs_host_prefix_wins():
    r = ptc.classify_site(_graph([], ["https://developers.ex.com/", "https://developers.ex.com/pricing"], site="https://developers.ex.com/"))
    assert r["site_type"] == "docs"


def test_ecommerce_needs_product_evidence_not_just_urls():
    urls = [S + "/", S + "/pricing"] + [S + f"/products/{i}" for i in range(10)]
    r = ptc.classify_site(_graph(_saas_pages(), urls))
    assert r["site_type"] == "saas"
    shop_pages = [_page(S + "/", depth=0), _page(S + "/products/a", types=["Product"], anchors=["Add to cart"]), _page(S + "/products/b", types=["Product"])]
    r = ptc.classify_site(_graph(shop_pages, urls))
    assert r["site_type"] == "ecommerce"


def test_local_business_homepage_schema():
    pages = [_page(S + "/", types=["Dentist"], depth=0), _page(S + "/services/cleaning")]
    r = ptc.classify_site(_graph(pages, [S + "/", S + "/services/cleaning", S + "/about"]))
    assert r["site_type"] == "local"


def test_no_signal_is_generic_with_advice():
    r = ptc.classify_site(_graph([], [S + "/", S + "/a", S + "/b"]))
    assert r["site_type"] == "generic" and "--site-type" in r["site_type_evidence"][0]
