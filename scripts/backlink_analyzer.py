#!/usr/bin/env python3
"""
Backlink Analyzer

Analyzes a backlink profile from CSV exports (Ahrefs, Moz, Semrush),
Google Search Console API (placeholder), or built-in sample data.
Produces a 7-section report with Backlink Health Score, toxic link
detection, anchor text analysis, and competitor gap comparison.

Usage:
    python backlink_analyzer.py --source sample --json
    python backlink_analyzer.py --source csv --input backlinks.csv
    python backlink_analyzer.py --source csv --input backlinks.csv --competitor-url https://rival.com --competitor-input rival_links.csv
    python backlink_analyzer.py --source sample --target-url https://mysite.com

CSV column mapping (column names are normalized to lowercase with underscores):
    source_url / referring_url   — URL of the linking page (required)
    target_url / target          — URL of the page being linked to
    anchor_text / anchor         — Link anchor text
    follow / link_type           — "dofollow"/"follow"/"yes"/"1" = followed; anything else = nofollow
    domain_rating / dr / da      — Numeric domain authority score (0–100)
    tld                          — Top-level domain (auto-detected from source_url if absent)

Ahrefs export: uses "Referring page URL", "Anchor", "DR" — rename or export as CSV and
the normalizer maps common variants automatically. Run with --source sample first to
see expected output format before providing real data.
"""

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from urllib.parse import urlparse

USER_AGENT = "Mozilla/5.0 (compatible; UltimateSEO-Backlinks/1.8)"

TOXIC_PATTERNS_HIGH_RISK = [
    {
        "id": "pbn_high_outbound",
        "description": "Domain has >1000 outbound links (PBN signal)",
        "check": "outbound_links",
        "threshold": 1000,
    },
    {
        "id": "pbn_low_dr",
        "description": "Domain rating <10 with dofollow link (PBN signal)",
        "check": "low_dr_dofollow",
        "threshold": 10,
    },
    {
        "id": "link_farm_wide",
        "description": "Referring domain links to >500 unique domains",
        "check": "links_to_many_domains",
        "threshold": 500,
    },
    {
        "id": "exact_anchor_spam",
        "description": "Exact-match anchor from single domain appears >5 times",
        "check": "repeat_exact_anchor",
        "threshold": 5,
    },
    {
        "id": "deindexed_domain",
        "description": "Referring domain appears deindexed (placeholder)",
        "check": "deindexed",
    },
    {
        "id": "thin_content_page",
        "description": "Referring page has <100 words (thin content host)",
        "check": "thin_page",
        "threshold": 100,
    },
    {
        "id": "high_outbound_page",
        "description": "Referring page has >100 outbound links",
        "check": "page_outbound",
        "threshold": 100,
    },
    {
        "id": "gambling_tld",
        "description": "Link from gambling-associated domain pattern",
        "check": "domain_pattern",
        "patterns": [r"casino", r"poker", r"slot[s]?", r"betting", r"gambl"],
    },
    {
        "id": "pharma_tld",
        "description": "Link from pharma-spam domain pattern",
        "check": "domain_pattern",
        "patterns": [r"viagra", r"cialis", r"pharma", r"pill[s]?", r"drug[s]?store"],
    },
    {
        "id": "adult_tld",
        "description": "Link from adult-content domain pattern",
        "check": "domain_pattern",
        "patterns": [r"xxx", r"porn", r"adult", r"webcam"],
    },
    {
        "id": "same_ip_subnet",
        "description": "Multiple links from same IP subnet (placeholder — needs IP data)",
        "check": "same_subnet",
    },
    {
        "id": "all_same_anchor",
        "description": "All links from a domain use identical anchor text",
        "check": "uniform_anchor_per_domain",
    },
]

TOXIC_PATTERNS_MEDIUM_RISK = [
    {
        "id": "comment_spam_click_here",
        "description": "Anchor text matches comment-spam pattern ('click here')",
        "check": "anchor_pattern",
        "patterns": [
            r"^click here$", r"^visit website$", r"^check this$",
            r"^read more$", r"^visit site$", r"^go here$",
            r"^check this out$", r"^see more$", r"^website$",
        ],
    },
    {
        "id": "irrelevant_tld_mismatch",
        "description": "Foreign-language TLD linking to English-language .com/.org site",
        "check": "tld_mismatch",
        "foreign_tlds": [".ru", ".cn", ".tk", ".pw", ".cc", ".cf", ".ga", ".gq", ".ml"],
    },
    {
        "id": "free_hosting_domain",
        "description": "Link from known free hosting / web 2.0 spam platform",
        "check": "domain_pattern",
        "patterns": [
            r"blogspot\.", r"wordpress\.com", r"weebly\.com",
            r"tumblr\.com", r"wixsite\.com", r"jimdo\.com",
        ],
    },
    {
        "id": "footer_sidebar_link",
        "description": "Suspected footer/sidebar paid link (anchor in common paid positions)",
        "check": "anchor_pattern",
        "patterns": [r"sponsored", r"partner", r"advertis"],
    },
    {
        "id": "numeric_domain",
        "description": "Referring domain is mostly numeric (spam signal)",
        "check": "domain_pattern",
        "patterns": [r"^\d{4,}"],
    },
    {
        "id": "excessive_hyphens",
        "description": "Referring domain has 4+ hyphens (spam signal)",
        "check": "domain_pattern",
        "patterns": [r".*-.*-.*-.*-"],
    },
    {
        "id": "very_long_domain",
        "description": "Referring domain name is suspiciously long (>40 chars)",
        "check": "long_domain",
        "threshold": 40,
    },
    {
        "id": "directory_submission",
        "description": "Link from low-quality directory site",
        "check": "domain_pattern",
        "patterns": [r"directory", r"linkdir", r"submitlink", r"addurl", r"freesubmit"],
    },
    {
        "id": "exact_match_domain",
        "description": "Referring domain is an exact-match keyword domain with low DR",
        "check": "emd_low_dr",
        "threshold": 20,
    },
    {
        "id": "reciprocal_pattern",
        "description": "Anchor text suggests reciprocal link exchange",
        "check": "anchor_pattern",
        "patterns": [r"link exchange", r"reciprocal", r"trade links", r"link partner"],
    },
]


def load_csv(filepath: str) -> list:
    rows = []
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            normalized = {}
            for key, val in row.items():
                normalized[key.strip().lower().replace(" ", "_")] = (val or "").strip()
            rows.append(normalized)
    return rows


def normalize_backlinks(raw_rows: list) -> list:
    backlinks = []
    for row in raw_rows:
        source_url = row.get("source_url", row.get("referring_url", ""))
        target_url = row.get("target_url", row.get("target", ""))
        anchor = row.get("anchor_text", row.get("anchor", ""))
        follow_raw = row.get("follow", row.get("link_type", "yes"))
        dr_raw = row.get("domain_rating", row.get("dr", row.get("da", "0")))
        tld = row.get("tld", "")

        follow = follow_raw.lower() in ("yes", "true", "1", "dofollow", "follow")

        try:
            dr = float(dr_raw)
        except (ValueError, TypeError):
            dr = 0.0

        if not tld and source_url:
            parsed = urlparse(source_url)
            parts = parsed.netloc.split(".")
            if len(parts) >= 2:
                tld = "." + parts[-1]

        source_domain = ""
        if source_url:
            parsed = urlparse(source_url if "://" in source_url else f"http://{source_url}")
            source_domain = parsed.netloc.lower().lstrip("www.")

        backlinks.append({
            "source_url": source_url,
            "source_domain": source_domain,
            "target_url": target_url,
            "anchor_text": anchor,
            "follow": follow,
            "domain_rating": min(max(dr, 0), 100),
            "tld": tld.lower() if tld else "",
        })
    return backlinks


def generate_sample_data(target_url: str = "https://example.com") -> list:
    random.seed(42)
    domains = [
        ("techblog.com", 72, ".com"), ("news-daily.org", 65, ".org"),
        ("seo-weekly.com", 58, ".com"), ("devresource.io", 81, ".io"),
        ("university.edu", 90, ".edu"), ("marketing-hub.com", 55, ".com"),
        ("gov-data.gov", 88, ".gov"), ("random-blog-123.tk", 5, ".tk"),
        ("link-farm-xyz.com", 3, ".com"), ("casino-bonus-free.ru", 8, ".ru"),
        ("great-content.co.uk", 45, ".co.uk"), ("startup-news.com", 62, ".com"),
        ("health-tips-daily.com", 38, ".com"), ("code-tutorials.dev", 70, ".dev"),
        ("forum-posts.net", 22, ".net"), ("free-directory-submit.com", 11, ".com"),
        ("industry-report.com", 77, ".com"), ("blogger-review.com", 42, ".com"),
        ("podcast-show.fm", 50, ".fm"), ("research-paper.edu", 92, ".edu"),
        ("social-media-guru.com", 35, ".com"), ("cheap-pills-online.cn", 4, ".cn"),
        ("travel-guide.com", 48, ".com"), ("design-inspiration.io", 67, ".io"),
        ("local-news.co", 53, ".co"),
    ]

    anchors_pool = [
        ("Example Brand", "branded"), ("example.com", "url"),
        ("click here", "generic"), ("best seo tools", "exact"),
        ("read more", "generic"), ("https://example.com", "url"),
        ("seo audit tool", "exact"), ("visit website", "generic"),
        ("example brand review", "branded"), ("top seo software", "exact"),
        ("this article", "generic"), ("Example", "branded"),
        ("learn more about seo", "partial"), ("great resource", "generic"),
        ("seo analysis platform", "exact"), ("check this out", "generic"),
    ]

    pages = ["/", "/blog", "/features", "/pricing", "/about", "/guides/seo-101",
             "/tools/audit", "/blog/backlink-guide", "/case-studies"]

    backlinks = []
    for i in range(25):
        domain_info = random.choice(domains)
        anchor_info = random.choice(anchors_pool)
        page = random.choice(pages)

        follow = random.random() > 0.25
        dr_jitter = random.uniform(-5, 5)

        backlinks.append({
            "source_url": f"https://{domain_info[0]}/page-{random.randint(1, 500)}",
            "source_domain": domain_info[0],
            "target_url": f"{target_url}{page}",
            "anchor_text": anchor_info[0],
            "follow": follow,
            "domain_rating": min(max(domain_info[1] + dr_jitter, 0), 100),
            "tld": domain_info[2],
        })

    return backlinks


def classify_anchor(anchor: str, brand_terms: list) -> str:
    if not anchor:
        return "empty"
    lower = anchor.lower().strip()
    if not lower:
        return "empty"

    for term in brand_terms:
        if term.lower() in lower:
            return "branded"

    url_pattern = re.compile(r"^https?://|^www\.|\.com|\.org|\.net|\.io")
    if url_pattern.search(lower):
        return "url"

    generic = {"click here", "read more", "visit website", "learn more",
               "check this out", "this article", "here", "website",
               "visit site", "go here", "see more", "more info",
               "source", "link", "this", "great resource"}
    if lower in generic:
        return "generic"

    if len(lower.split()) <= 5 and not any(c in lower for c in "!@#$%"):
        return "exact_match"

    return "other"


def detect_brand_terms(backlinks: list) -> list:
    if not backlinks:
        return ["example"]

    target_domains = set()
    for bl in backlinks:
        if bl.get("target_url"):
            parsed = urlparse(bl["target_url"])
            domain = parsed.netloc.lower().lstrip("www.")
            if domain:
                target_domains.add(domain)

    terms = []
    for domain in target_domains:
        base = domain.split(".")[0]
        if base:
            terms.append(base)
    return terms if terms else ["example"]


# ── Section 1: Profile Overview ──────────────────────────────────────────

def analyze_profile_overview(backlinks: list) -> dict:
    total = len(backlinks)
    domains = set(bl["source_domain"] for bl in backlinks if bl["source_domain"])
    follow_count = sum(1 for bl in backlinks if bl["follow"])
    nofollow_count = total - follow_count

    dr_values = [bl["domain_rating"] for bl in backlinks]
    dr_buckets = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for dr in dr_values:
        if dr <= 20:
            dr_buckets["0-20"] += 1
        elif dr <= 40:
            dr_buckets["21-40"] += 1
        elif dr <= 60:
            dr_buckets["41-60"] += 1
        elif dr <= 80:
            dr_buckets["61-80"] += 1
        else:
            dr_buckets["81-100"] += 1

    avg_dr = sum(dr_values) / max(len(dr_values), 1)
    median_dr = sorted(dr_values)[len(dr_values) // 2] if dr_values else 0

    return {
        "total_backlinks": total,
        "referring_domains": len(domains),
        "follow_count": follow_count,
        "nofollow_count": nofollow_count,
        "follow_ratio": round(follow_count / max(total, 1), 3),
        "avg_domain_rating": round(avg_dr, 1),
        "median_domain_rating": round(median_dr, 1),
        "domain_rating_distribution": dr_buckets,
    }


# ── Section 2: Anchor Text Distribution ──────────────────────────────────

def analyze_anchor_text(backlinks: list, brand_terms: list) -> dict:
    categories = Counter()
    anchor_examples = defaultdict(list)

    for bl in backlinks:
        cat = classify_anchor(bl["anchor_text"], brand_terms)
        categories[cat] += 1
        if len(anchor_examples[cat]) < 5:
            anchor_examples[cat].append(bl["anchor_text"])

    total = max(sum(categories.values()), 1)
    distribution = {}
    for cat in ["branded", "exact_match", "generic", "url", "other", "empty"]:
        count = categories.get(cat, 0)
        distribution[cat] = {
            "count": count,
            "percentage": round(count / total * 100, 1),
            "examples": anchor_examples.get(cat, []),
        }

    exact_pct = distribution.get("exact_match", {}).get("percentage", 0)
    over_optimized = exact_pct > 15

    top_anchors = Counter(bl["anchor_text"] for bl in backlinks if bl["anchor_text"])

    return {
        "distribution": distribution,
        "over_optimized": over_optimized,
        "exact_match_percentage": exact_pct,
        "top_anchors": [{"text": t, "count": c} for t, c in top_anchors.most_common(15)],
    }


# ── Section 3: Referring Domain Quality ──────────────────────────────────

def analyze_domain_quality(backlinks: list) -> dict:
    tld_counter = Counter()
    domain_dr = {}

    for bl in backlinks:
        if bl["tld"]:
            tld_counter[bl["tld"]] += 1
        if bl["source_domain"]:
            domain_dr[bl["source_domain"]] = bl["domain_rating"]

    dr_buckets = {"0-20": [], "21-40": [], "41-60": [], "61-80": [], "81-100": []}
    for domain, dr in domain_dr.items():
        if dr <= 20:
            dr_buckets["0-20"].append(domain)
        elif dr <= 40:
            dr_buckets["21-40"].append(domain)
        elif dr <= 60:
            dr_buckets["41-60"].append(domain)
        elif dr <= 80:
            dr_buckets["61-80"].append(domain)
        else:
            dr_buckets["81-100"].append(domain)

    bucket_summary = {k: len(v) for k, v in dr_buckets.items()}
    high_authority = dr_buckets.get("81-100", []) + dr_buckets.get("61-80", [])

    return {
        "tld_distribution": dict(tld_counter.most_common(20)),
        "domain_rating_buckets": bucket_summary,
        "high_authority_domains": high_authority[:15],
        "low_quality_domains": dr_buckets.get("0-20", [])[:15],
        "unique_tlds": len(tld_counter),
    }


# ── Section 4: Toxic Link Detection ─────────────────────────────────────

def detect_toxic_links(backlinks: list, target_tld: str = ".com") -> dict:
    high_risk = []
    medium_risk = []

    domain_anchors = defaultdict(list)
    domain_links = defaultdict(list)
    for bl in backlinks:
        if bl["source_domain"]:
            domain_anchors[bl["source_domain"]].append(bl["anchor_text"])
            domain_links[bl["source_domain"]].append(bl)

    def _check_domain_patterns(bl, patterns):
        domain = bl["source_domain"]
        for pat in patterns:
            if re.search(pat, domain, re.IGNORECASE):
                return True
        return False

    def _check_anchor_patterns(bl, patterns):
        anchor = bl.get("anchor_text", "").lower()
        for pat in patterns:
            if re.search(pat, anchor, re.IGNORECASE):
                return True
        return False

    seen_high = set()
    seen_medium = set()

    for bl in backlinks:
        link_id = hashlib.md5(
            f"{bl['source_url']}|{bl['target_url']}|{bl['anchor_text']}".encode()
        ).hexdigest()[:12]

        for pattern in TOXIC_PATTERNS_HIGH_RISK:
            check = pattern["check"]
            matched = False

            if check == "low_dr_dofollow":
                matched = bl["domain_rating"] < pattern["threshold"] and bl["follow"]
            elif check == "domain_pattern":
                matched = _check_domain_patterns(bl, pattern["patterns"])
            elif check == "repeat_exact_anchor":
                domain = bl["source_domain"]
                anchors = domain_anchors.get(domain, [])
                anchor_counts = Counter(anchors)
                for a, c in anchor_counts.items():
                    if c > pattern["threshold"] and a and a == bl["anchor_text"]:
                        matched = True
                        break
            elif check == "uniform_anchor_per_domain":
                domain = bl["source_domain"]
                anchors = domain_anchors.get(domain, [])
                if len(anchors) >= 3 and len(set(anchors)) == 1:
                    matched = True

            if matched:
                dedup_key = f"{pattern['id']}|{bl['source_domain']}"
                if dedup_key not in seen_high:
                    seen_high.add(dedup_key)
                    high_risk.append({
                        "link_id": link_id,
                        "pattern_id": pattern["id"],
                        "source_url": bl["source_url"],
                        "source_domain": bl["source_domain"],
                        "anchor_text": bl["anchor_text"],
                        "domain_rating": bl["domain_rating"],
                        "reason": pattern["description"],
                        "tier": "high_risk",
                    })

        for pattern in TOXIC_PATTERNS_MEDIUM_RISK:
            check = pattern["check"]
            matched = False

            if check == "anchor_pattern":
                matched = _check_anchor_patterns(bl, pattern["patterns"])
            elif check == "tld_mismatch":
                foreign_tlds = pattern.get("foreign_tlds", [])
                if bl["tld"] in foreign_tlds and target_tld not in foreign_tlds:
                    matched = True
            elif check == "domain_pattern":
                matched = _check_domain_patterns(bl, pattern["patterns"])
            elif check == "long_domain":
                if len(bl["source_domain"]) > pattern["threshold"]:
                    matched = True
            elif check == "emd_low_dr":
                domain_base = bl["source_domain"].split(".")[0]
                if len(domain_base.split("-")) >= 3 and bl["domain_rating"] < pattern["threshold"]:
                    matched = True

            if matched:
                dedup_key = f"{pattern['id']}|{bl['source_domain']}"
                if dedup_key not in seen_medium:
                    seen_medium.add(dedup_key)
                    medium_risk.append({
                        "link_id": link_id,
                        "pattern_id": pattern["id"],
                        "source_url": bl["source_url"],
                        "source_domain": bl["source_domain"],
                        "anchor_text": bl["anchor_text"],
                        "domain_rating": bl["domain_rating"],
                        "reason": pattern["description"],
                        "tier": "medium_risk",
                    })

    total = max(len(backlinks), 1)
    toxic_domains = set(t["source_domain"] for t in high_risk + medium_risk)

    return {
        "high_risk": high_risk,
        "medium_risk": medium_risk,
        "high_risk_count": len(high_risk),
        "medium_risk_count": len(medium_risk),
        "toxic_domain_count": len(toxic_domains),
        "toxic_ratio": round(len(toxic_domains) / max(len(set(
            bl["source_domain"] for bl in backlinks if bl["source_domain"]
        )), 1), 3),
        "patterns_checked": len(TOXIC_PATTERNS_HIGH_RISK) + len(TOXIC_PATTERNS_MEDIUM_RISK),
    }


# ── Section 5: Top Pages by Backlinks ────────────────────────────────────

def analyze_top_pages(backlinks: list) -> list:
    page_links = defaultdict(lambda: {"count": 0, "domains": set(), "follow": 0, "nofollow": 0})
    for bl in backlinks:
        target = bl["target_url"]
        page_links[target]["count"] += 1
        page_links[target]["domains"].add(bl["source_domain"])
        if bl["follow"]:
            page_links[target]["follow"] += 1
        else:
            page_links[target]["nofollow"] += 1

    results = []
    for url, data in sorted(page_links.items(), key=lambda x: x[1]["count"], reverse=True):
        results.append({
            "target_url": url,
            "backlink_count": data["count"],
            "referring_domains": len(data["domains"]),
            "follow": data["follow"],
            "nofollow": data["nofollow"],
        })
    return results


# ── Section 6: Competitor Gap ────────────────────────────────────────────

def analyze_competitor_gap(backlinks: list, competitor_backlinks: list,
                           competitor_url: str) -> dict:
    my_domains = set(bl["source_domain"] for bl in backlinks if bl["source_domain"])
    comp_domains = set(bl["source_domain"] for bl in competitor_backlinks if bl["source_domain"])

    shared = my_domains & comp_domains
    only_mine = my_domains - comp_domains
    only_competitor = comp_domains - my_domains

    comp_domain_dr = {}
    for bl in competitor_backlinks:
        if bl["source_domain"]:
            comp_domain_dr[bl["source_domain"]] = bl["domain_rating"]

    opportunity_domains = sorted(
        only_competitor,
        key=lambda d: comp_domain_dr.get(d, 0),
        reverse=True,
    )

    opportunities = []
    for domain in opportunity_domains[:20]:
        opportunities.append({
            "domain": domain,
            "domain_rating": comp_domain_dr.get(domain, 0),
        })

    return {
        "competitor_url": competitor_url,
        "my_referring_domains": len(my_domains),
        "competitor_referring_domains": len(comp_domains),
        "shared_domains": len(shared),
        "only_mine": len(only_mine),
        "only_competitor": len(only_competitor),
        "shared_domain_list": sorted(shared)[:20],
        "top_opportunities": opportunities,
    }


# ── Section 7: Velocity ─────────────────────────────────────────────────

def analyze_velocity() -> dict:
    return {
        "status": "requires_time_series_data",
        "message": ("Backlink velocity analysis requires time-series data "
                     "(e.g. monthly snapshots). Export backlink data at regular "
                     "intervals and compare referring domain counts over time."),
        "guidance": [
            "Healthy velocity: steady growth of 5-15 new referring domains/month.",
            "Sudden spike (>3x normal): investigate for negative SEO or viral content.",
            "Sudden drop: check for link removals, disavow impact, or domain expiration.",
        ],
    }


# ── Health Score ─────────────────────────────────────────────────────────

def calculate_health_score(overview: dict, domain_quality: dict,
                           toxic: dict, anchor: dict) -> dict:
    scores = {}

    ref_domains = overview["referring_domains"]
    if ref_domains >= 50:
        scores["referring_domain_count"] = 100
    elif ref_domains >= 20:
        scores["referring_domain_count"] = 70
    elif ref_domains >= 10:
        scores["referring_domain_count"] = 50
    elif ref_domains >= 5:
        scores["referring_domain_count"] = 30
    else:
        scores["referring_domain_count"] = 10

    avg_dr = overview["avg_domain_rating"]
    scores["domain_quality"] = min(100, max(0, avg_dr * 1.2))

    toxic_ratio = toxic["toxic_ratio"]
    if toxic_ratio <= 0.05:
        scores["toxic_ratio"] = 100
    elif toxic_ratio <= 0.10:
        scores["toxic_ratio"] = 75
    elif toxic_ratio <= 0.20:
        scores["toxic_ratio"] = 50
    elif toxic_ratio <= 0.35:
        scores["toxic_ratio"] = 25
    else:
        scores["toxic_ratio"] = 0

    exact_pct = anchor["exact_match_percentage"]
    branded_pct = anchor["distribution"].get("branded", {}).get("percentage", 0)
    if exact_pct <= 10 and branded_pct >= 30:
        scores["anchor_naturalness"] = 100
    elif exact_pct <= 15 and branded_pct >= 20:
        scores["anchor_naturalness"] = 75
    elif exact_pct <= 20:
        scores["anchor_naturalness"] = 50
    elif exact_pct <= 30:
        scores["anchor_naturalness"] = 25
    else:
        scores["anchor_naturalness"] = 0

    tld_dist = domain_quality["tld_distribution"]
    unique_tlds = domain_quality["unique_tlds"]
    if unique_tlds >= 5:
        scores["geographic_relevance"] = 80
    elif unique_tlds >= 3:
        scores["geographic_relevance"] = 60
    else:
        scores["geographic_relevance"] = 40
    edu_gov = tld_dist.get(".edu", 0) + tld_dist.get(".gov", 0)
    if edu_gov > 0:
        scores["geographic_relevance"] = min(100, scores["geographic_relevance"] + 20)

    scores["velocity"] = 50

    follow_ratio = overview["follow_ratio"]
    if 0.60 <= follow_ratio <= 0.85:
        scores["follow_ratio"] = 100
    elif 0.50 <= follow_ratio <= 0.90:
        scores["follow_ratio"] = 70
    elif 0.40 <= follow_ratio <= 0.95:
        scores["follow_ratio"] = 40
    else:
        scores["follow_ratio"] = 15

    weights = {
        "referring_domain_count": 0.20,
        "domain_quality": 0.20,
        "toxic_ratio": 0.20,
        "anchor_naturalness": 0.15,
        "geographic_relevance": 0.10,
        "velocity": 0.10,
        "follow_ratio": 0.05,
    }

    weighted_total = sum(scores[k] * weights[k] for k in weights)
    final_score = round(weighted_total, 1)

    return {
        "score": final_score,
        "component_scores": {k: round(scores[k], 1) for k in weights},
        "weights": weights,
    }


# ── Issues & Recommendations ────────────────────────────────────────────

def generate_issues_and_recommendations(
    overview: dict, anchor: dict, domain_quality: dict,
    toxic: dict, top_pages: list, health: dict,
) -> tuple:
    issues = []
    recommendations = []

    if toxic["high_risk_count"] > 0:
        issues.append({
            "severity": "Critical",
            "finding": (f"{toxic['high_risk_count']} high-risk toxic backlink(s) detected "
                        f"from {toxic['toxic_domain_count']} domain(s)."),
            "fix": "Add flagged domains to Google Disavow file and submit via Search Console.",
        })

    if toxic["medium_risk_count"] > 3:
        issues.append({
            "severity": "Warning",
            "finding": f"{toxic['medium_risk_count']} medium-risk link patterns detected.",
            "fix": "Review flagged links — disavow confirmed spam, monitor borderline cases.",
        })

    if anchor["over_optimized"]:
        issues.append({
            "severity": "High",
            "finding": (f"Exact-match anchor text at {anchor['exact_match_percentage']:.1f}% "
                        f"(threshold: 15%). Over-optimization risk."),
            "fix": ("Diversify new backlink anchors toward branded (40-50%) and "
                    "generic/URL (30-40%). Do NOT alter existing links artificially."),
        })

    branded_pct = anchor["distribution"].get("branded", {}).get("percentage", 0)
    if branded_pct < 20:
        issues.append({
            "severity": "Medium",
            "finding": f"Branded anchor text at only {branded_pct:.1f}% (target: 40-50%).",
            "fix": "Pursue brand-mention link building (PR, guest posts, directory profiles).",
        })

    follow_ratio = overview["follow_ratio"]
    if follow_ratio > 0.90:
        issues.append({
            "severity": "Warning",
            "finding": (f"Follow ratio at {follow_ratio:.0%} — unnaturally high. "
                        f"Natural profiles are 60-85% follow."),
            "fix": "No action needed if organic. Monitor for link scheme patterns.",
        })
    elif follow_ratio < 0.40:
        issues.append({
            "severity": "Medium",
            "finding": f"Follow ratio at {follow_ratio:.0%} — most links are nofollow.",
            "fix": "Focus link-building on editorially-placed dofollow opportunities.",
        })

    low_quality_count = domain_quality["domain_rating_buckets"].get("0-20", 0)
    total_domains = overview["referring_domains"]
    if total_domains > 0 and low_quality_count / total_domains > 0.40:
        issues.append({
            "severity": "High",
            "finding": (f"{low_quality_count} of {total_domains} referring domains "
                        f"have DR <20 ({low_quality_count/total_domains:.0%})."),
            "fix": "Prioritize earning links from DR 40+ sites via content marketing and outreach.",
        })

    if overview["referring_domains"] < 10:
        issues.append({
            "severity": "Medium",
            "finding": f"Only {overview['referring_domains']} referring domains — thin link profile.",
            "fix": "Build domain diversity through guest posting, digital PR, and resource link building.",
        })

    if top_pages:
        homepage_links = 0
        total_links = overview["total_backlinks"]
        for p in top_pages:
            if p["target_url"].rstrip("/").endswith(urlparse(p["target_url"]).netloc):
                homepage_links = p["backlink_count"]
                break
        if total_links > 0 and homepage_links / total_links > 0.80:
            issues.append({
                "severity": "Medium",
                "finding": f"Homepage receives {homepage_links/total_links:.0%} of all backlinks.",
                "fix": "Build deep links to key content/product pages through targeted outreach.",
            })

    if toxic["high_risk_count"] > 0:
        recommendations.append(
            "Create a disavow file for high-risk toxic domains and submit to "
            "Google Search Console. Re-check quarterly."
        )
    if anchor["over_optimized"]:
        recommendations.append(
            "Shift new link acquisition toward branded and generic anchors. "
            "Target: branded 40-50%, exact match <10%, generic 20-30%."
        )
    if overview["referring_domains"] < 20:
        recommendations.append(
            "Grow referring domain count through content-led link building: "
            "original research, data studies, and expert roundups."
        )

    high_auth = domain_quality.get("high_authority_domains", [])
    if len(high_auth) < 3:
        recommendations.append(
            "Pursue high-authority links (DR 60+) through digital PR, "
            "HARO/Connectively responses, and industry publications."
        )

    recommendations.append(
        "Set up monthly backlink monitoring to track velocity and catch "
        "negative SEO early. Export data regularly for trend analysis."
    )

    return issues, recommendations


# ── Full Analysis ────────────────────────────────────────────────────────

def run_analysis(backlinks: list, competitor_backlinks: list = None,
                 competitor_url: str = "", target_url: str = "",
                 data_source: str = "unknown") -> dict:
    if not backlinks:
        return {"error": "No backlink data provided.", "issues": [], "recommendations": []}

    if not target_url:
        targets = Counter(bl["target_url"] for bl in backlinks if bl["target_url"])
        target_url = targets.most_common(1)[0][0] if targets else ""

    target_parsed = urlparse(target_url)
    target_tld = "." + target_parsed.netloc.split(".")[-1] if target_parsed.netloc else ".com"

    brand_terms = detect_brand_terms(backlinks)

    overview = analyze_profile_overview(backlinks)
    anchor = analyze_anchor_text(backlinks, brand_terms)
    domain_quality = analyze_domain_quality(backlinks)
    toxic = detect_toxic_links(backlinks, target_tld)
    top_pages = analyze_top_pages(backlinks)
    velocity = analyze_velocity()

    competitor_gap = None
    if competitor_backlinks and competitor_url:
        competitor_gap = analyze_competitor_gap(backlinks, competitor_backlinks, competitor_url)

    health = calculate_health_score(overview, domain_quality, toxic, anchor)
    issues, recommendations = generate_issues_and_recommendations(
        overview, anchor, domain_quality, toxic, top_pages, health,
    )

    report = {
        "target_url": target_url,
        # Provenance travels with the payload. Previously the only signal that a
        # report was built from generate_sample_data() went to stderr, so stdout
        # JSON from the default invocation was indistinguishable from a real
        # profile once it reached a downstream consumer or a client deliverable.
        "data_source": data_source,
        "is_sample_data": data_source == "sample",
        "backlink_health_score": health["score"],
        "health_score_breakdown": health,
        "section_1_profile_overview": overview,
        "section_2_anchor_text": anchor,
        "section_3_domain_quality": domain_quality,
        "section_4_toxic_links": toxic,
        "section_5_top_pages": top_pages,
        "section_6_competitor_gap": competitor_gap,
        "section_7_velocity": velocity,
        "issues": issues,
        "recommendations": recommendations,
    }
    return report


# ── Text Output ──────────────────────────────────────────────────────────

def print_text_report(report: dict):
    if report.get("error"):
        print(f"Error: {report['error']}")
        return

    target = report.get("target_url", "unknown")
    score = report.get("backlink_health_score", 0)

    print(f"\nBacklink Analysis — {target}")
    print("=" * 64)
    print(f"Backlink Health Score: {score}/100")
    print()

    breakdown = report.get("health_score_breakdown", {})
    components = breakdown.get("component_scores", {})
    weights = breakdown.get("weights", {})
    if components:
        print("Score Breakdown:")
        for key, val in components.items():
            w = weights.get(key, 0)
            label = key.replace("_", " ").title()
            print(f"  {label:<30} {val:>5.1f}  (weight: {w:.0%})")
        print()

    # Section 1
    ov = report.get("section_1_profile_overview", {})
    print("─" * 64)
    print("Section 1: Profile Overview")
    print("─" * 64)
    print(f"  Total backlinks        : {ov.get('total_backlinks', 0)}")
    print(f"  Referring domains      : {ov.get('referring_domains', 0)}")
    print(f"  Follow / Nofollow      : {ov.get('follow_count', 0)} / {ov.get('nofollow_count', 0)}"
          f"  ({ov.get('follow_ratio', 0):.0%} follow)")
    print(f"  Avg domain rating      : {ov.get('avg_domain_rating', 0)}")
    print(f"  Median domain rating   : {ov.get('median_domain_rating', 0)}")
    dr_dist = ov.get("domain_rating_distribution", {})
    if dr_dist:
        print(f"  DR distribution        : {dr_dist}")
    print()

    # Section 2
    anc = report.get("section_2_anchor_text", {})
    print("─" * 64)
    print("Section 2: Anchor Text Distribution")
    print("─" * 64)
    dist = anc.get("distribution", {})
    for cat in ["branded", "exact_match", "generic", "url", "other", "empty"]:
        info = dist.get(cat, {})
        pct = info.get("percentage", 0)
        count = info.get("count", 0)
        bar = "█" * int(pct / 3)
        print(f"  {cat:<14} {count:>4} ({pct:>5.1f}%) {bar}")
    if anc.get("over_optimized"):
        print(f"  ⚠️  OVER-OPTIMIZED: exact-match at {anc.get('exact_match_percentage', 0):.1f}% (>15%)")
    top = anc.get("top_anchors", [])
    if top:
        print(f"\n  Top anchors:")
        for item in top[:10]:
            print(f"    [{item['count']:>2}x] \"{item['text']}\"")
    print()

    # Section 3
    dq = report.get("section_3_domain_quality", {})
    print("─" * 64)
    print("Section 3: Referring Domain Quality")
    print("─" * 64)
    tld = dq.get("tld_distribution", {})
    if tld:
        print(f"  TLD distribution:")
        for ext, count in sorted(tld.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"    {ext:<12} {count}")
    buckets = dq.get("domain_rating_buckets", {})
    if buckets:
        print(f"  DR buckets:")
        for bucket, count in buckets.items():
            bar = "█" * count
            print(f"    DR {bucket:<8} {count:>3} {bar}")
    high_auth = dq.get("high_authority_domains", [])
    if high_auth:
        print(f"  High authority (DR 60+): {', '.join(high_auth[:8])}")
    print()

    # Section 4
    tox = report.get("section_4_toxic_links", {})
    print("─" * 64)
    print("Section 4: Toxic Link Detection")
    print("─" * 64)
    print(f"  Patterns checked       : {tox.get('patterns_checked', 0)}")
    print(f"  High-risk flagged      : {tox.get('high_risk_count', 0)}")
    print(f"  Medium-risk flagged    : {tox.get('medium_risk_count', 0)}")
    print(f"  Toxic domain ratio     : {tox.get('toxic_ratio', 0):.1%}")

    for item in tox.get("high_risk", [])[:10]:
        print(f"\n  🔴 HIGH RISK — {item['reason']}")
        print(f"     Domain: {item['source_domain']} (DR {item['domain_rating']:.0f})")
        print(f"     Anchor: \"{item['anchor_text']}\"")

    for item in tox.get("medium_risk", [])[:10]:
        print(f"\n  ⚠️  MEDIUM RISK — {item['reason']}")
        print(f"     Domain: {item['source_domain']} (DR {item['domain_rating']:.0f})")
        print(f"     Anchor: \"{item['anchor_text']}\"")
    print()

    # Section 5
    pages = report.get("section_5_top_pages", [])
    print("─" * 64)
    print("Section 5: Top Pages by Backlinks")
    print("─" * 64)
    if pages:
        for p in pages[:15]:
            print(f"  [{p['backlink_count']:>3} links, {p['referring_domains']:>3} domains] {p['target_url']}")
    else:
        print("  No page data available.")
    print()

    # Section 6
    gap = report.get("section_6_competitor_gap")
    print("─" * 64)
    print("Section 6: Competitor Gap")
    print("─" * 64)
    if gap:
        print(f"  Competitor             : {gap['competitor_url']}")
        print(f"  My referring domains   : {gap['my_referring_domains']}")
        print(f"  Competitor ref domains : {gap['competitor_referring_domains']}")
        print(f"  Shared domains         : {gap['shared_domains']}")
        print(f"  Only mine              : {gap['only_mine']}")
        print(f"  Only competitor        : {gap['only_competitor']}")
        opps = gap.get("top_opportunities", [])
        if opps:
            print(f"\n  Top link opportunities (domains linking to competitor but not you):")
            for o in opps[:10]:
                print(f"    DR {o['domain_rating']:>5.0f}  {o['domain']}")
    else:
        print("  No competitor data provided. Use --competitor-url and --competitor-input.")
    print()

    # Section 7
    vel = report.get("section_7_velocity", {})
    print("─" * 64)
    print("Section 7: Link Velocity")
    print("─" * 64)
    print(f"  Status: {vel.get('message', 'N/A')}")
    for tip in vel.get("guidance", []):
        print(f"  • {tip}")
    print()

    # Issues
    issues = report.get("issues", [])
    if issues:
        print("─" * 64)
        print(f"Issues ({len(issues)})")
        print("─" * 64)
        for issue in issues:
            sev = issue.get("severity", "Info")
            icon = {"Critical": "🔴", "High": "🔴", "Warning": "⚠️", "Medium": "⚠️"}.get(sev, "ℹ️")
            print(f"  {icon} [{sev}] {issue['finding']}")
            print(f"     Fix: {issue['fix']}")
        print()

    # Recommendations
    recs = report.get("recommendations", [])
    if recs:
        print("─" * 64)
        print(f"Recommendations ({len(recs)})")
        print("─" * 64)
        for i, rec in enumerate(recs, 1):
            print(f"  {i}. {rec}")
        print()


# ── CLI ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Backlink Analyzer — profile audit, toxic detection, competitor gap"
    )
    parser.add_argument("--source", choices=["csv", "gsc", "sample"], default="sample",
                        help="Data source: csv (Ahrefs/Moz/Semrush export), gsc (placeholder), sample")
    parser.add_argument("--input", default="",
                        help="Path to CSV file (required for --source csv)")
    parser.add_argument("--target-url", default="",
                        help="Target site URL (used for reporting and TLD matching)")
    parser.add_argument("--competitor-url", default="",
                        help="Competitor URL for gap analysis")
    parser.add_argument("--competitor-input", default="",
                        help="Path to competitor backlink CSV (for --competitor-url)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.source == "csv":
        if not args.input:
            print("Error: --input is required when --source is csv", file=sys.stderr)
            sys.exit(1)
        try:
            raw = load_csv(args.input)
        except FileNotFoundError:
            print(f"Error: file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading CSV: {e}", file=sys.stderr)
            sys.exit(1)
        backlinks = normalize_backlinks(raw)
        resolved_source = "csv"
        print(f"Loaded {len(backlinks)} backlinks from {args.input}", file=sys.stderr)

    elif args.source == "gsc":
        print("GSC source is a placeholder. Provide service-account credentials via "
              "link_profile.py --gsc-credentials for live GSC data.", file=sys.stderr)
        print("Falling back to sample data.", file=sys.stderr)
        target = args.target_url or "https://example.com"
        backlinks = generate_sample_data(target)
        # --source gsc silently produces sample data today, so the payload must
        # say sample rather than echo back what was requested.
        resolved_source = "sample"

    else:
        resolved_source = "sample"
        target = args.target_url or "https://example.com"
        backlinks = generate_sample_data(target)
        print(f"Generated {len(backlinks)} sample backlinks for demo.", file=sys.stderr)

    competitor_backlinks = None
    if args.competitor_url and args.competitor_input:
        try:
            comp_raw = load_csv(args.competitor_input)
            competitor_backlinks = normalize_backlinks(comp_raw)
            print(f"Loaded {len(competitor_backlinks)} competitor backlinks.", file=sys.stderr)
        except FileNotFoundError:
            print(f"Warning: competitor file not found: {args.competitor_input}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: error reading competitor CSV: {e}", file=sys.stderr)

    report = run_analysis(
        backlinks,
        competitor_backlinks=competitor_backlinks,
        competitor_url=args.competitor_url,
        target_url=args.target_url,
        data_source=resolved_source,
    )

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print_text_report(report)


if __name__ == "__main__":
    main()
