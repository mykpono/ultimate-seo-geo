#!/usr/bin/env python3
"""
Page-type classifier: label every known URL with a content type, roll the
labels up into a coverage matrix by funnel stage, and report the page types a
site of this kind is expected to have but does not.

Why this exists. The GEO reference records that comparison articles take about
a third of all AI citations, and references/industry-templates.md prescribes
the comparison, alternatives, use-case, integration and case-study pages a
SaaS site needs — but until now nothing could say "this site has zero
comparison pages". Only ecommerce_schema.py labelled pages at all, and it knew
two labels.

How it classifies. URL rules first, in a fixed order, first match wins
(SEOWatchdog's design); ``generic`` is the fallback. A fetched page can then
confirm the URL label or, when two independent page signals agree (H1 or
title pattern, JSON-LD type, call-to-action anchor), override it. Confidence
follows the finding contract: Confirmed when URL and page agree, Likely on a
URL rule alone or two page signals, Hypothesis on one page signal.
``pain_point_problem`` never rises above Hypothesis — no open-source tool
detects it and the patterns are new.

Completeness. The coverage matrix is built from the sitemap URLs plus the
crawled pages, so it can be complete for thousands of URLs without fetching
them. A "missing page type" finding is only made when the sitemap was read
in full or the crawl was complete; otherwise the matrix is reported with
status ``inconclusive`` (the rule from tests/test_orphan_detection.py).

The taxonomy is pinned to references/page-types.md by tests/test_page_type_parity.py.

Usage:
    python page_type_classifier.py https://example.com
    python page_type_classifier.py https://example.com --graph site_graph.json --json
    python page_type_classifier.py https://example.com --site-type saas --rules my_rules.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from urllib.parse import urlparse

import jsonld
import site_graph

CITATION_SHARE_NOTE = "Comparison articles receive ~33% of AI citations (references/ai-search-geo.md, Content Type Citation Share)."

INTENT_STAGES = ("nav", "TOFU", "MOFU", "BOFU", "support", "trust", "meta")

# Role words for persona / ICP pages ("for marketers", "/for/developers").
PERSONA_WORDS = (
    "marketers", "marketing teams", "developers", "engineers", "engineering teams", "designers",
    "product managers", "product teams", "founders", "startups", "small business", "small businesses",
    "smb", "enterprise", "enterprises", "agencies", "freelancers", "sales teams", "sales", "recruiters",
    "hr", "hr teams", "finance teams", "cfos", "ctos", "cmos", "ceos", "it teams", "devops", "data teams",
    "analysts", "support teams", "customer success", "creators", "educators", "teachers", "students",
    "nonprofits", "consultants", "researchers", "ops teams", "operations", "growth teams", "revops",
)
INDUSTRY_WORDS = (
    "healthcare", "health care", "fintech", "financial services", "banking", "insurance", "real estate",
    "education", "edtech", "legal", "law firms", "manufacturing", "retail", "ecommerce", "e-commerce",
    "hospitality", "hotels", "restaurants", "travel", "nonprofit", "government", "public sector",
    "logistics", "supply chain", "automotive", "construction", "energy", "utilities", "telecom",
    "media", "publishing", "gaming", "pharma", "biotech", "life sciences", "saas companies", "agencies",
    "consumer goods", "cpg", "aerospace", "defense", "transportation", "professional services",
)

_PERSONA_RE = re.compile(r"\bfor\s+(?:" + "|".join(re.escape(w) for w in PERSONA_WORDS) + r")\b", re.I)
_INDUSTRY_RE = re.compile(r"\b(?:for|in)\s+(?:the\s+)?(?:" + "|".join(re.escape(w) for w in INDUSTRY_WORDS) + r")\b", re.I)

# Ordered taxonomy. Keep in sync with references/page-types.md (pinned by CI).
#
# Two kinds of URL pattern:
#   "section": tested against the first path segment only ("/blog/"), or the
#              second when the first is a locale code (/en/blog/). A word deep in the path is not a section: /docs/pricing
#              is documentation, /category/integration is an archive.
#   "path":    tested against the whole path (+ query). These are content shapes
#              that legitimately live under any section — "x-vs-y", "what-is-",
#              "for-marketers", "/page/2" — and they WIN over the section label,
#              which is kept as secondary_label (a comparison under /blog/ is
#              counted as a comparison and also as blog output).
# First match wins within each kind, in list order.
def _words_as_slugs(words):
    return "|".join(re.escape(w).replace(r"\ ", "-") for w in words)


PAGE_TYPES: list[dict] = [
    {"label": "homepage", "intent": "nav", "section": [], "path": [r"^/$"],
     "h1": [], "schema": [], "cta": []},
    {"label": "comparison", "intent": "BOFU",
     "section": [r"^/(?:vs|compare|comparisons?|versus)/$"],
     "path": [r"/vs/", r"(?:^|/)[^/]+-vs-[^/]+", r"(?:^|/)[^/]+-versus-[^/]+", r"/compare/"],
     "h1": [r"\bvs\.?\s", r"\bversus\b", r"\bcompared\b", r"\bcomparison\b"],
     "schema": [], "cta": []},
    {"label": "alternatives", "intent": "BOFU",
     "section": [r"^/(?:alternatives?|competitors?)/$"],
     "path": [r"/alternatives?(?:/|$)", r"(?:^|/)[^/]+-alternatives?(?:/|$)", r"(?:^|/)[^/]+-competitors?(?:/|$)"],
     "h1": [r"\balternatives?\b", r"\bcompetitors\b"],
     "schema": [], "cta": []},
    {"label": "pricing", "intent": "BOFU",
     "section": [r"^/(?:pricing|plans|prices?|pricing-plans)/$"],
     "path": [],
     "h1": [r"\bpricing\b", r"\bplans\b"],
     "schema": [], "cta": []},
    {"label": "case_study", "intent": "BOFU",
     "section": [r"^/(?:case-stud(?:y|ies)|customers?|success-stories|customer-stories|testimonials|clients)/$"],
     "path": [],
     "h1": [r"\bcase study\b", r"\bhow \S+ (?:uses|used|achieved|increased|reduced|grew|saved)\b"],
     "schema": [], "cta": []},
    {"label": "integration", "intent": "MOFU",
     "section": [r"^/(?:integrations?|apps|connectors?|marketplace|plugins?|add-?ons)/$"],
     "path": [],
     "h1": [r"\bintegrat(?:e|ion|ions)\b"],
     "schema": [], "cta": []},
    {"label": "persona_icp", "intent": "MOFU",
     "section": [r"^/(?:teams?|roles?|who-we-serve|personas?|who-its-for)/$"],
     "path": [r"/for/(?:" + _words_as_slugs(PERSONA_WORDS) + r")(?:/|$)",
              r"(?:^|/)for-(?:" + _words_as_slugs(PERSONA_WORDS) + r")(?:/|$)"],
     "h1": [_PERSONA_RE.pattern],
     "schema": [], "cta": []},
    {"label": "industry_market", "intent": "MOFU",
     "section": [r"^/(?:industr(?:y|ies)|markets?|verticals?|sectors?)/$"],
     "path": [r"/for/(?:" + _words_as_slugs(INDUSTRY_WORDS) + r")(?:/|$)",
              r"(?:^|/)for-(?:" + _words_as_slugs(INDUSTRY_WORDS) + r")(?:/|$)"],
     "h1": [_INDUSTRY_RE.pattern],
     "schema": [], "cta": []},
    {"label": "solution_use_case", "intent": "MOFU",
     "section": [r"^/(?:solutions?|use-?cases?|workflows?|for)/$"],
     "path": [r"/for/[^/]+", r"/use-?cases?/"],
     "h1": [],
     "schema": [], "cta": []},
    {"label": "pain_point_problem", "intent": "TOFU",
     "section": [r"^/(?:problems?|challenges?)/$"],
     "path": [r"(?:^|/)why-(?:is|are|does|do|my|your)-", r"(?:^|/)how-to-(?:fix|stop|reduce|prevent|avoid|solve)-"],
     "h1": [r"^how to (?:fix|stop|reduce|prevent|avoid|solve)\b", r"^why (?:is|are|does|do) (?:my|your|our)\b", r"\b(?:biggest|common) (?:problems|challenges|mistakes)\b"],
     "schema": [], "cta": []},
    {"label": "product_feature", "intent": "MOFU",
     "section": [r"^/(?:features?|product|platform|capabilit(?:y|ies)|modules?)/$"],
     "path": [],
     "h1": [],
     "schema": ["SoftwareApplication", "WebApplication"],
     "cta": [r"\b(?:start|begin) (?:your )?free trial\b", r"\bbook a demo\b", r"\brequest a demo\b", r"\bget a demo\b", r"\bget started free\b"]},
    {"label": "glossary_definition", "intent": "TOFU",
     "section": [r"^/(?:glossary|dictionary|definitions?|wiki|what-is)/$"],
     "path": [r"(?:^|/)what-(?:is|are)-"],
     "h1": [r"^what (?:is|are) (?:a |an |the )?", r"\bdefinition\b", r"\bglossary\b", r"\bmeaning\b", r"\bexplained$"],
     "schema": ["DefinedTerm", "DefinedTermSet"], "cta": []},
    {"label": "pillar_guide", "intent": "TOFU",
     "section": [r"^/(?:guides?|learn|academy|handbook|playbooks?|resources/guides)/$"],
     "path": [r"(?:^|/)(?:ultimate|complete|definitive|beginners?|comprehensive)-guide"],
     "h1": [r"\b(?:ultimate|complete|definitive|comprehensive|beginner'?s?) guide\b", r"^(?:a |the )?guide to\b"],
     "schema": [], "cta": []},
    {"label": "tool_template", "intent": "TOFU",
     "section": [r"^/(?:tools?|templates?|calculators?|generators?|checklists?|free-tools?)/$"],
     "path": [r"(?:^|/)free-[^/]+-(?:tool|template|calculator|generator|checklist)(?:/|$)", r"(?:^|/)[^/]+-(?:calculator|generator)(?:/|$)"],
     "h1": [r"\b(?:calculator|template|generator|checklist)\b"],
     "schema": [], "cta": []},
    {"label": "docs_help", "intent": "support",
     "section": [r"^/(?:docs?|documentation|help|help-center|support|kb|knowledge-?base|developers?|api|api-reference|api-docs|reference|manual|tutorials?|guides/docs)/$"],
     "path": [],
     "h1": [], "schema": ["TechArticle"], "cta": []},
    {"label": "community_qa", "intent": "support",
     "section": [r"^/(?:questions?|community|forum|forums|discussions?|answers|q-and-a|qa)/$"],
     "path": [],
     "h1": [], "schema": ["QAPage", "DiscussionForumPosting"], "cta": []},
    {"label": "faq", "intent": "support",
     "section": [r"^/(?:faqs?|frequently-asked-questions)/$"],
     "path": [],
     "h1": [r"\bfaqs?\b", r"\bfrequently asked\b"],
     "schema": [], "cta": []},
    {"label": "author", "intent": "trust",
     "section": [r"^/(?:authors?|writers?|contributors?|profile|people|experts?)/$"],
     "path": [],
     "h1": [], "schema": ["ProfilePage"], "cta": []},
    {"label": "tag_archive", "intent": "meta",
     "section": [r"^/(?:tags?|topics?|categor(?:y|ies)|archives?|label|series)/$"],
     "path": [r"/page/\d+(?:/|$)", r"[?&](?:page|paged|pg)=\d+"],
     "h1": [], "schema": ["CollectionPage"], "cta": []},
    {"label": "blog_article", "intent": "TOFU",
     "section": [r"^/(?:blog|articles?|news|insights?|posts?|stories|journal|magazine|press|press-releases?|updates?|changelog|newsroom|thoughts|writing|essays?)/$"],
     "path": [r"^/(?:19|20)\d{2}/(?:0[1-9]|1[0-2])/"],
     "h1": [],
     "schema": ["Article", "BlogPosting", "NewsArticle"], "cta": []},
    {"label": "landing_campaign", "intent": "BOFU",
     "section": [r"^/(?:lp|landing|campaigns?|demo|trial|free-trial|signup|sign-up|register|download|webinars?|events?|newsletter|subscribe|get-started|start)/$"],
     "path": [],
     "h1": [], "schema": ["Event"], "cta": []},
    {"label": "ecom_category", "intent": "MOFU",
     "section": [r"^/(?:collections?|category|categories/shop|c|shop|catalog|catalogue|brands?|sale|deals?|department|departments)/$"],
     "path": [],
     "h1": [],
     "schema": ["ItemList", "CollectionPage", "OfferCatalog"], "cta": []},
    {"label": "ecom_product", "intent": "BOFU",
     "section": [r"^/(?:products|p|item|items|dp|sku|buy|shop/products)/$"],
     "path": [],
     "h1": [],
     "schema": ["Product", "ProductGroup", "IndividualProduct"],
     "cta": [r"\badd to (?:cart|bag|basket)\b", r"\bbuy now\b", r"\badd to trolley\b"]},
    {"label": "location_service", "intent": "BOFU",
     "section": [r"^/(?:locations?|services?|areas?|areas-served|service-areas?|near-me|branches?|stores?|offices?|cities|city)/$"],
     "path": [r"(?:^|/)[^/]+-near-me(?:/|$)"],
     "h1": [r"\bin [A-Z][a-zA-Z]+(?:, [A-Z]{2})?$", r"\bnear (?:you|me)\b"],
     "schema": ["Service"], "cta": []},
    {"label": "about_company", "intent": "trust",
     "section": [r"^/(?:about|about-us|company|team|leadership|our-story|mission|careers?|jobs?|investors?|partners?|security|trust|press-kit|brand)/$"],
     "path": [],
     "h1": [r"^about\b", r"^our (?:story|team|mission)\b"],
     "schema": ["AboutPage"], "cta": []},
    {"label": "contact", "intent": "trust",
     "section": [r"^/(?:contact|contact-us|get-in-touch|talk-to-sales|talk-to-us|talk-to-a-human|book-a-call|book)/$"],
     "path": [],
     "h1": [r"^contact\b", r"\bget in touch\b"],
     "schema": ["ContactPage"], "cta": []},
    {"label": "legal", "intent": "meta",
     "section": [r"^/(?:privacy|privacy-policy|terms|terms-of-service|terms-of-use|legal|cookies?|cookie-policy|gdpr|accessibility|accessibility-statement|disclaimer|imprint|dpa|sla)/$"],
     "path": [],
     "h1": [r"\bprivacy policy\b", r"\bterms (?:of|and) (?:service|use|conditions)\b"],
     "schema": [], "cta": []},
    {"label": "generic", "intent": "meta", "section": [], "path": [], "h1": [], "schema": [], "cta": []},
]

LABELS = tuple(t["label"] for t in PAGE_TYPES)
_BY_LABEL = {t["label"]: t for t in PAGE_TYPES}

# Page types a site of each kind is expected to have (references/industry-templates.md).
# Severity when missing: money pages Medium, the rest Low.
EXPECTED_BY_SITE_TYPE: dict[str, list[str]] = {
    "saas": ["pricing", "product_feature", "comparison", "alternatives", "solution_use_case",
             "integration", "case_study", "docs_help", "blog_article", "about_company"],
    "ecommerce": ["ecom_category", "ecom_product", "comparison", "pillar_guide", "blog_article",
                  "faq", "about_company", "contact"],
    "local": ["location_service", "about_company", "contact", "faq", "blog_article"],
    "publisher": ["blog_article", "author", "tag_archive", "pillar_guide", "about_company"],
    "docs": [],
    "generic": [],
}
# On a SaaS site /products/x is a feature page, not a shop item.
SITE_TYPE_REMAP = {"saas": {"ecom_product": "product_feature"}}
DOCS_HOST_PREFIXES = ("docs.", "developers.", "developer.", "help.", "support.", "learn.", "kb.")
MONEY_TYPES = frozenset({"pricing", "product_feature", "comparison", "alternatives", "solution_use_case",
                         "ecom_category", "ecom_product", "location_service", "case_study"})

# Word floors by page type (references/industry-templates.md, Word Count Floors).
WORD_FLOORS = {
    "product_feature": 600, "ecom_category": 300, "ecom_product": 300,
    "location_service": 600, "blog_article": 1500, "pillar_guide": 3000,
}

SITE_TYPES = ("auto", "saas", "ecommerce", "local", "publisher", "docs", "generic")
UNCLASSIFIED_WARN_SHARE = 0.40
BOFU_IMBALANCE_SHARE = 0.05
MIN_URLS_FOR_IMBALANCE = 50


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def _compile(rules: list[dict]) -> list[dict]:
    return [{"label": t["label"],
             "section": [re.compile(p, re.I) for p in t.get("section", [])],
             "path": [re.compile(p, re.I) for p in t.get("path", [])]} for t in rules]


_URL_RULES = _compile(PAGE_TYPES)
_LOCALE_SEGMENT = re.compile(r"^/[a-z]{2}(?:[-_][a-z]{2,4})?/$", re.I)


def load_rules(path: str) -> list[dict]:
    """Site-specific URL rules, prepended to the defaults.

    JSON list of {"label": <known label>, "pattern": <regex>, "kind": "section"|"path"}.
    A section rule is tested against "/<first-segment>/" (then "/<second>/");
    a path rule (the default) against the whole path.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON list of {{label, pattern}}")
    rules = []
    for i, item in enumerate(data):
        if not isinstance(item, dict) or "label" not in item or "pattern" not in item:
            raise ValueError(f"{path}: rule {i} must have 'label' and 'pattern'")
        if item["label"] not in _BY_LABEL:
            raise ValueError(f"{path}: rule {i} uses unknown label {item['label']!r}; known: {', '.join(LABELS)}")
        kind = item.get("kind", "path")
        if kind not in ("section", "path"):
            raise ValueError(f"{path}: rule {i} kind must be 'section' or 'path'")
        rules.append({"label": item["label"], kind: [item["pattern"]]})
    return rules


def classify_url(url: str, extra_rules: list[dict] | None = None) -> dict:
    """URL-only classification.

    Path (slug-level) rules win; the section rule that also matched is kept
    as ``secondary_label``. Returns {"label", "secondary_label", "rule"} with
    ``rule`` one of "path", "section", "section2" (matched on the second
    segment) or None for "generic".
    """
    parsed = urlparse(url)
    path = parsed.path or "/"
    if path.rstrip("/") == "":
        return {"label": "homepage", "secondary_label": None, "rule": "path"}
    target = path + (("?" + parsed.query) if parsed.query else "")
    segs = [x for x in path.split("/") if x]
    seg1 = f"/{segs[0]}/" if segs else "/"
    seg2 = f"/{segs[1]}/" if len(segs) > 1 else None

    rules = (_compile(extra_rules) if extra_rules else []) + _URL_RULES
    path_hits, sec_hits, sec_level = [], [], None
    for r in rules:
        if r["label"] == "homepage":
            continue
        if r["label"] not in path_hits and any(p.search(target) for p in r["path"]):
            path_hits.append(r["label"])
    for r in rules:
        if r["label"] not in sec_hits and any(p.search(seg1) for p in r["section"]):
            sec_hits.append(r["label"])
    if sec_hits:
        sec_level = "section"
    elif seg2 and _LOCALE_SEGMENT.match(seg1):
        # /en/blog/... — only a locale prefix is skipped. Anything else as the
        # first segment IS the section (a docs product's /features/ subfolder is
        # documentation, not a feature page).
        for r in rules:
            if r["label"] not in sec_hits and any(p.search(seg2) for p in r["section"]):
                sec_hits.append(r["label"])
        if sec_hits:
            sec_level = "section2"

    if path_hits:
        label = path_hits[0]
        others = [l for l in path_hits[1:] + sec_hits if l != label]
        return {"label": label, "secondary_label": others[0] if others else None, "rule": "path"}
    if sec_hits:
        others = [l for l in sec_hits[1:] if l != sec_hits[0]]
        return {"label": sec_hits[0], "secondary_label": others[0] if others else None, "rule": sec_level}
    return {"label": "generic", "secondary_label": None, "rule": None}


def page_signals(page: dict) -> dict[str, list[str]]:
    """Labels suggested by a fetched page's own content, with the evidence.

    Returns {label: [signal, ...]} where a signal is "h1", "title", "schema:<T>"
    or "cta:<anchor>". Each signal source contributes at most once per label.
    """
    votes: dict[str, list[str]] = defaultdict(list)
    h1 = (page.get("h1") or "").strip()
    title = (page.get("title") or "").strip()
    types = set(page.get("jsonld_types") or [])
    anchors = [(l.get("anchor") or "").strip().lower() for l in page.get("out_links") or []]
    is_home = page.get("parts", {}).get("depth", None) == 0 or (page.get("url", "").rstrip("/").count("/") == 2)

    for t in PAGE_TYPES:
        label = t["label"]
        if label in ("homepage", "generic"):
            continue
        for pat in t["h1"]:
            rx = re.compile(pat, re.I)
            if h1 and rx.search(h1):
                votes[label].append("h1")
                break
            if title and rx.search(title):
                votes[label].append("title")
                break
        for st in t["schema"]:
            if st in types:
                # SoftwareApplication / Organization on the homepage describe the
                # site, not the page.
                if is_home and st in ("SoftwareApplication", "WebApplication"):
                    continue
                votes[label].append(f"schema:{st}")
                break
        for pat in t["cta"]:
            rx = re.compile(pat, re.I)
            hit = next((a for a in anchors if rx.search(a)), None)
            if hit:
                votes[label].append(f"cta:{hit[:40]}")
                break
    # LocalBusiness subtypes: the schema.org hierarchy lives in jsonld.py.
    if any(jsonld.is_local_business({"@type": t}) for t in types) and not is_home:
        votes["location_service"].append("schema:LocalBusiness")
    # A Person node alone (no Article) reads as an author/profile page.
    if "Person" in types and not types & {"Article", "BlogPosting", "NewsArticle"} and not is_home:
        votes["author"].append("schema:Person")
    return dict(votes)


def classify_page(page: dict, extra_rules: list[dict] | None = None) -> dict:
    """Combine the URL rule with the page's own signals.

    - URL label + any agreeing page signal        -> Confirmed
    - URL label alone                              -> Likely
    - No URL label, two independent page signals   -> Likely (override generic)
    - No URL label, one page signal                -> Hypothesis
    - URL label but two page signals for another   -> override, Likely
    ``pain_point_problem`` is capped at Hypothesis.
    """
    url = page["url"]
    by_url = classify_url(url, extra_rules)
    signals = page_signals(page)
    label = by_url["label"]
    secondary = by_url["secondary_label"]
    confidence: str | None
    evidence: list[str] = []

    if label == "homepage":
        return {"url": url, "label": "homepage", "secondary_label": None, "confidence": "Confirmed", "evidence": ["url:/"], "signals": signals}

    strongest = max(signals.items(), key=lambda kv: len(kv[1]), default=(None, []))
    if label != "generic":
        if label in signals:
            confidence = "Confirmed"
            evidence = [f"url:{label}"] + [f"{s}:{label}" for s in signals[label]]
        elif strongest[0] and len(strongest[1]) >= 2:
            secondary = label
            label = strongest[0]
            confidence = "Likely"
            evidence = [f"{s}:{label}" for s in strongest[1]] + [f"url:{secondary} (overridden)"]
        else:
            confidence = "Likely"
            evidence = [f"url:{label}"]
    else:
        if strongest[0] and len(strongest[1]) >= 2:
            label, confidence = strongest[0], "Likely"
            evidence = [f"{s}:{label}" for s in strongest[1]]
        elif strongest[0]:
            label, confidence = strongest[0], "Hypothesis"
            evidence = [f"{s}:{label}" for s in strongest[1]]
        else:
            confidence = None
    if label == "pain_point_problem":
        confidence = "Hypothesis"
    return {"url": url, "label": label, "secondary_label": secondary, "confidence": confidence, "evidence": evidence, "signals": signals}


# ---------------------------------------------------------------------------
# Site type
# ---------------------------------------------------------------------------

def detect_site_type(counts: Counter, pages: dict, host: str = "") -> dict:
    """Guess the business type from the host, the label mix and page schema.

    Order matters: a documentation host is docs whatever it links to; a site
    that is mostly articles is a publisher even if one page mentions pricing;
    a shop needs Product schema or add-to-cart evidence, not just /products/
    URLs (SaaS sites use that path for feature pages).
    """
    total = sum(counts.values()) or 1
    home = next((p for p in pages.values() if p.get("depth") == 0), None)
    home_types = set(home.get("jsonld_types") or []) if home else set()
    product_schema_pages = sum(1 for p in pages.values() if {"Product", "ProductGroup"} & set(p.get("jsonld_types") or []))
    cart_pages = sum(1 for p in pages.values() if any(re.search(r"\badd to (?:cart|bag|basket)\b|\bbuy now\b", (l.get("anchor") or ""), re.I) for l in p.get("out_links") or []))
    host = (host or "").lower()

    if host.startswith(DOCS_HOST_PREFIXES) or (counts["docs_help"] / total >= 0.5 and total >= 20):
        return {"site_type": "docs", "evidence": [f"host {host or '?'}; docs_help={counts['docs_help']}/{total} URLs"]}
    editorial = counts["blog_article"] + counts["tag_archive"] + counts["author"]
    if editorial / total >= 0.6 and total >= 20:
        return {"site_type": "publisher", "evidence": [f"{editorial}/{total} URLs are articles, archives or author pages"]}
    if product_schema_pages >= 2 or cart_pages >= 2 or (counts["ecom_product"] >= 5 and (product_schema_pages or cart_pages)):
        return {"site_type": "ecommerce", "evidence": [f"Product schema on {product_schema_pages} fetched page(s), add-to-cart on {cart_pages}, {counts['ecom_product']} product URLs"]}
    home_local = any(jsonld.is_local_business({"@type": t}) for t in home_types)
    if home_local or (counts["location_service"] >= 3 and counts["location_service"] / total > 0.1):
        return {"site_type": "local", "evidence": [f"LocalBusiness schema on homepage: {home_local}; {counts['location_service']} location/service URLs ({counts['location_service'] / total:.0%})"]}
    saas_signals = sum(1 for k in ("product_feature", "integration", "docs_help", "ecom_product") if counts[k] > 0)
    if (counts["pricing"] >= 1 and saas_signals >= 1) or home_types & {"SoftwareApplication", "WebApplication"}:
        return {"site_type": "saas", "evidence": [f"pricing={counts['pricing']}, product_feature={counts['product_feature'] + counts['ecom_product']}, integration={counts['integration']}, docs_help={counts['docs_help']}, homepage schema={sorted(home_types & {'SoftwareApplication', 'WebApplication'})}"]}
    return {"site_type": "generic", "evidence": ["no decisive signal; pass --site-type to override"]}


# ---------------------------------------------------------------------------
# Site-level classification
# ---------------------------------------------------------------------------

def classify_site(graph: dict, site_type: str = "auto", extra_rules: list[dict] | None = None) -> dict:
    pages = graph.get("pages", {})
    sitemap = graph.get("sitemap", {})
    crawl = graph.get("crawl", {})

    # Every known URL, keyed like the graph; fetched pages carry content signals.
    classified: dict[str, dict] = {}
    for key, page in pages.items():
        classified[key] = classify_page(page, extra_rules)
        classified[key]["fetched"] = True
    for url in sitemap.get("urls", {}):
        key = site_graph.page_key(url)
        if key in classified:
            continue
        by_url = classify_url(url, extra_rules)
        classified[key] = {
            "url": url, "label": by_url["label"], "secondary_label": by_url["secondary_label"],
            "confidence": "Likely" if by_url["label"] not in ("generic",) else None,
            "evidence": [f"url:{by_url['label']}"] if by_url["label"] != "generic" else [],
            "signals": {}, "fetched": False,
        }
        if by_url["label"] == "homepage":
            classified[key]["confidence"] = "Confirmed"

    counts = Counter(c["label"] for c in classified.values())
    total = len(classified)
    host = urlparse(graph.get("site") or "").netloc
    source_complete = bool(sitemap.get("complete")) or bool(crawl.get("complete"))
    reasons = []
    if not source_complete:
        reasons.extend(sitemap.get("reasons") or [])
        reasons.extend(crawl.get("reasons") or [])

    detected = detect_site_type(counts, pages, host)
    chosen = detected["site_type"] if site_type == "auto" else site_type
    remap = SITE_TYPE_REMAP.get(chosen, {})
    if remap:
        for c in classified.values():
            if c["label"] in remap:
                c["evidence"] = c["evidence"] + [f"remapped:{c['label']}->{remap[c['label']]} ({chosen} site)"]
                c["label"] = remap[c["label"]]
        counts = Counter(c["label"] for c in classified.values())

    # Families: (label, dir_1) with up to 3 fetched representatives.
    fam_map: dict[tuple, dict] = {}
    for key, c in classified.items():
        parts = site_graph.url_parts(c["url"])
        fk = (c["label"], parts["dir_1"])
        fam = fam_map.setdefault(fk, {"label": c["label"], "dir_1": parts["dir_1"], "count": 0, "fetched": 0, "representatives": [], "word_counts": []})
        fam["count"] += 1
        if c["fetched"]:
            fam["fetched"] += 1
            page = pages[key]
            if len(fam["representatives"]) < 3:
                fam["representatives"].append(c["url"])
            if page.get("word_count") is not None:
                fam["word_counts"].append(page["word_count"])
    families = sorted(fam_map.values(), key=lambda f: (-f["count"], f["label"], f["dir_1"] or ""))
    for f in families:
        f["avg_word_count"] = round(sum(f["word_counts"]) / len(f["word_counts"])) if f["word_counts"] else None
        del f["word_counts"]

    matrix = {}
    for t in PAGE_TYPES:
        label = t["label"]
        n = counts.get(label, 0)
        confs = Counter(c["confidence"] for c in classified.values() if c["label"] == label and c["confidence"])
        matrix[label] = {
            "count": n,
            "share": round(n / total, 3) if total else 0.0,
            "intent": t["intent"],
            "families": [f["dir_1"] for f in families if f["label"] == label][:8],
            "examples": [c["url"] for c in classified.values() if c["label"] == label][:5],
            "confidence": dict(confs),
        }
    by_intent = {}
    for stage in INTENT_STAGES:
        n = sum(m["count"] for m in matrix.values() if m["intent"] == stage)
        by_intent[stage] = {"count": n, "share": round(n / total, 3) if total else 0.0}

    findings = _findings(matrix, by_intent, families, chosen, total, source_complete, reasons)
    return {
        "site": graph.get("site"),
        "site_type": chosen,
        "site_type_detected": detected["site_type"],
        "site_type_evidence": detected["evidence"],
        "urls_classified": total,
        "urls_fetched": len(pages),
        "source": {
            "sitemap_complete": bool(sitemap.get("complete")),
            "crawl_complete": bool(crawl.get("complete")),
            "status": "complete" if source_complete else "inconclusive",
            "reasons": reasons,
        },
        "matrix": matrix,
        "by_intent": by_intent,
        "families": families[:60],
        "pages": {k: {kk: vv for kk, vv in v.items() if kk != "signals"} for k, v in classified.items()},
        "expected": EXPECTED_BY_SITE_TYPE.get(chosen, []),
        "findings": findings,
    }


def _findings(matrix, by_intent, families, site_type, total, source_complete, reasons) -> list[dict]:
    findings: list[dict] = []
    expected = EXPECTED_BY_SITE_TYPE.get(site_type, [])
    missing = [label for label in expected if matrix[label]["count"] == 0]

    if missing and not source_complete:
        findings.append({
            "type": "coverage_inconclusive",
            "severity": "Info",
            "finding": f"{len(missing)} expected page type(s) for a {site_type} site were not seen, but the URL inventory is incomplete.",
            "evidence": f"Missing so far: {', '.join(missing)}. {total} URL(s) classified. " + "; ".join(reasons[:3]),
            "impact": "Cannot say these page types are absent; they may sit in the unread part of the site.",
            "fix": "Re-run with a complete sitemap or a larger crawl (`site_graph.py --max-pages`), then re-check coverage.",
            "confidence": "Hypothesis",
            "labels": missing,
        })
    elif missing:
        for label in missing:
            money = label in MONEY_TYPES
            extra = f" {CITATION_SHARE_NOTE}" if label == "comparison" else ""
            findings.append({
                "type": "missing_page_type",
                "severity": "Medium" if money else "Low",
                "finding": f"No {label.replace('_', ' ')} pages found on a {site_type} site.",
                "evidence": f"0 of {total} URL(s) (sitemap + crawl) match {label} URL patterns; no fetched page carries its content signals.{extra}",
                "impact": _impact_for(label),
                "fix": _fix_for(label),
                "confidence": "Likely",
                "tags": ["opportunity"],
                "label": label,
            })

    funnel_total = by_intent["TOFU"]["count"] + by_intent["MOFU"]["count"] + by_intent["BOFU"]["count"]
    bofu_share = by_intent["BOFU"]["count"] / funnel_total if funnel_total else 1.0
    if site_type in ("saas", "ecommerce") and funnel_total >= MIN_URLS_FOR_IMBALANCE and bofu_share < BOFU_IMBALANCE_SHARE and source_complete:
        findings.append({
            "type": "intent_imbalance",
            "severity": "Low",
            "finding": f"Bottom-of-funnel pages are {bofu_share:.0%} of the site's funnel content.",
            "evidence": f"BOFU={by_intent['BOFU']['count']} of {funnel_total} TOFU+MOFU+BOFU URLs (docs, archives, legal and unclassified pages excluded).",
            "impact": "Traffic lands on informational pages with few conversion-intent pages to link to.",
            "fix": "Add comparison, alternatives and pricing-adjacent pages, and link to them from the top TOFU articles.",
            "confidence": "Likely",
            "tags": ["opportunity"],
        })

    generic_share = matrix["generic"]["share"]
    if total >= 20 and generic_share > UNCLASSIFIED_WARN_SHARE:
        findings.append({
            "type": "unclassified_share",
            "severity": "Info",
            "finding": f"{generic_share:.0%} of URLs matched no page-type rule.",
            "evidence": f"{matrix['generic']['count']} of {total} URLs are 'generic'; examples: {', '.join(matrix['generic']['examples'][:3])}",
            "impact": "The coverage matrix under-counts whatever those pages are.",
            "fix": "Pass `--rules rules.json` with site-specific URL patterns (see references/page-types.md).",
            "confidence": "Confirmed",
        })

    for fam in families:
        floor = WORD_FLOORS.get(fam["label"])
        if not floor or fam["fetched"] < 2 or fam["avg_word_count"] is None:
            continue
        if fam["avg_word_count"] < floor * 0.5:
            findings.append({
                "type": "type_word_floor",
                "severity": "Low",
                "finding": f"{fam['label'].replace('_', ' ')} pages under /{fam['dir_1'] or ''}/ average {fam['avg_word_count']} words; the floor for this type is {floor}.",
                "evidence": f"{fam['fetched']} fetched page(s), e.g. {', '.join(fam['representatives'][:2])}",
                "impact": "Thin pages of a type that competes on depth rarely rank or get cited.",
                "fix": "Expand the thinnest pages in this family first; word floors are in references/industry-templates.md.",
                "confidence": "Likely",
                "label": fam["label"],
            })
    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
    findings.sort(key=lambda f: order.get(f["severity"], 9))
    return findings


def _impact_for(label: str) -> str:
    return {
        "comparison": "The single most-cited content type in AI answers is absent, and 'X vs Y' queries carry the highest purchase intent.",
        "alternatives": "'[competitor] alternative' is the most-searched BOFU pattern in SaaS; those searchers land on third-party lists instead.",
        "pricing": "Buyers and AI assistants cannot find what the product costs; pricing queries go unanswered or to review sites.",
        "product_feature": "No page ranks for feature-level queries; the homepage has to carry every transactional intent.",
        "solution_use_case": "'X for [use case]' queries have no landing page, so MOFU intent is unserved.",
        "integration": "Long-tail '[product] + [tool] integration' queries, usually low competition, are left to competitors.",
        "case_study": "No social proof pages for buyers or for AI systems looking for named outcomes.",
        "docs_help": "Documentation is a high-value long-tail keyword surface; without it support queries route elsewhere.",
        "blog_article": "No informational content to earn links, citations or top-of-funnel visibility.",
        "about_company": "Weak entity and E-E-A-T signals: who is behind the site is unstated.",
        "contact": "Missing trust and local signals; NAP cannot be confirmed.",
        "faq": "Question-shaped queries have no self-contained answer blocks, the shape AI engines cite.",
        "ecom_category": "Category-level 'best X' and '[type] for [need]' queries have no landing page.",
        "ecom_product": "No product pages were found; nothing can carry Product schema or transactional intent.",
        "location_service": "No service or location pages; local queries have nothing to rank.",
        "pillar_guide": "No comprehensive guide anchors the topic cluster; supporting posts have no hub.",
        "author": "No author pages; E-E-A-T experience and expertise signals are unattributed.",
        "tag_archive": "No topic hubs to consolidate internal links across related articles.",
    }.get(label, "A page type the industry template expects is missing.")


def _fix_for(label: str) -> str:
    return {
        "comparison": "Create /vs/[competitor]/ pages for the top 3 competitors with a balanced feature table, pricing row and an honest 'choose X if' section.",
        "alternatives": "Create /[competitor]-alternatives/ pages listing 5-8 options with a comparison table and your own entry described honestly.",
        "pricing": "Publish a server-rendered /pricing/ page with plan cards, Offer schema and an FAQPage block for pricing questions.",
        "product_feature": "Create one /features/[feature]/ page per core capability with use cases, an FAQ and a trial CTA.",
        "solution_use_case": "Create /solutions/[use-case]/ pages for the top 3-5 jobs-to-be-done, each with a workflow walkthrough.",
        "integration": "Create /integrations/[tool]/ pages for every supported tool with setup steps and what data flows.",
        "case_study": "Publish /case-studies/[customer]/ pages with named outcomes, numbers and quotes; add Article schema.",
        "docs_help": "Publish public /docs/ (never behind login) covering setup, concepts and reference.",
        "blog_article": "Start a /blog/ with 6-12 posts per topic cluster linking to the pillar page.",
        "about_company": "Add /about/ with team, credentials and Organization schema (sameAs to social profiles).",
        "contact": "Add /contact/ with NAP, a form and ContactPage schema.",
        "faq": "Add /faq/ with 8-15 self-contained question and answer pairs.",
        "ecom_category": "Create category pages with 300-500 words of above-product copy, ItemList and BreadcrumbList schema.",
        "ecom_product": "Publish crawlable product pages with unique descriptions and Product + Offer schema.",
        "location_service": "Create /services/[service]/ and, for multi-location businesses, /locations/[city]/ pages with unique local content.",
        "pillar_guide": "Write one 3,000-5,000 word guide per topic cluster and link every cluster post to it.",
        "author": "Add /author/[name]/ pages with bio, credentials and Person schema, linked from every byline.",
        "tag_archive": "Add topic hub pages that list the articles in each cluster.",
    }.get(label, "Create the page type per references/industry-templates.md.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(result: dict) -> None:
    print(f"\n🗂️  Page types: {result['site']}")
    print(f"   Site type: {result['site_type']}" + (f" (detected: {result['site_type_detected']})" if result['site_type'] != result['site_type_detected'] else "") + f" — {'; '.join(result['site_type_evidence'])}")
    print(f"   URLs classified: {result['urls_classified']} ({result['urls_fetched']} fetched)  inventory: {result['source']['status']}")
    for r in result["source"]["reasons"][:4]:
        print(f"     - {r}")
    print("\n   Coverage matrix:")
    for label, m in result["matrix"].items():
        if m["count"]:
            print(f"     {label:<22} {m['count']:>6}  {m['share']:>6.1%}  {m['intent']:<7} {', '.join('/' + (f or '') for f in m['families'][:4])}")
    print("\n   By intent: " + ", ".join(f"{k}={v['count']}" for k, v in result["by_intent"].items() if v["count"]))
    if result["expected"]:
        missing = [l for l in result["expected"] if result["matrix"][l]["count"] == 0]
        print(f"   Expected for {result['site_type']}: {len(result['expected'])} types, missing: {', '.join(missing) or 'none'}")
    if result["findings"]:
        print("\n   Findings:")
        for f in result["findings"]:
            print(f"     [{f['severity']}] {f['finding']}")
            print(f"        fix: {f['fix']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify every known URL by page type and report content-type coverage gaps")
    parser.add_argument("url", help="Site URL (homepage)")
    parser.add_argument("--graph", help="site_graph.py output to read instead of crawling")
    parser.add_argument("--site-type", choices=SITE_TYPES, default="auto", help="Business type for the expected-page-types check (default auto)")
    parser.add_argument("--rules", help="JSON list of {label, pattern} URL rules prepended to the defaults")
    parser.add_argument("--max-pages", type=int, default=80, help="Pages to crawl when no --graph is given (default 80)")
    parser.add_argument("--depth", type=int, default=2, help="Crawl depth when no --graph is given (default 2)")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    extra = load_rules(args.rules) if args.rules else None
    if args.graph:
        graph = site_graph.load_graph(args.graph)
    else:
        graph = site_graph.build_graph(args.url, max_pages=max(1, args.max_pages), max_depth=max(0, args.depth))
    result = classify_site(graph, site_type=args.site_type, extra_rules=extra)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_summary(result)


if __name__ == "__main__":
    main()
