#!/usr/bin/env python3
"""Deterministic content quality checks for E-E-A-T and AI-pattern risks."""

from __future__ import annotations

import argparse
import json
import re
import sys

from bs4 import BeautifulSoup

from fetch_page import fetch_page


FILLER_PHRASES = (
    "in today's digital landscape",
    "it is important to note",
    "delve into",
    "unlock the power",
    "game-changer",
    "comprehensive guide",
    "look no further",
    "seamlessly",
)

UNSUPPORTED_CLAIM_RE = re.compile(
    r"\b(\d+(?:\.\d+)?%|\d+x|\d{4}|study|research|survey|report|according to)\b",
    re.IGNORECASE,
)


def _html_to_text(html: str) -> tuple[str, BeautifulSoup]:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ").split())
    return text, soup


def analyze_html(html: str, url: str = "") -> dict:
    text, soup = _html_to_text(html)
    lower = text.lower()
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    word_count = len(words)
    filler_hits = [phrase for phrase in FILLER_PHRASES if phrase in lower]
    author_present = bool(
        soup.select_one('[rel="author"], .author, .byline, [class*="author"], [itemprop="author"]')
    )
    date_present = bool(
        soup.find("time")
        or soup.select_one('[datetime], [class*="date"], [itemprop="datePublished"], [property="article:published_time"]')
    )
    outbound_sources = [
        a.get("href", "")
        for a in soup.find_all("a", href=True)
        if a.get("href", "").startswith(("http://", "https://")) and (not url or url not in a.get("href", ""))
    ]
    claim_count = len(UNSUPPORTED_CLAIM_RE.findall(text))
    citation_gap = max(0, claim_count - len(outbound_sources))

    issues = []
    recommendations = []
    score = 100

    if word_count < 300:
        score -= 20
        issues.append({
            "severity": "warning",
            "finding": "Page has very little extractable main content",
            "fix": "Add useful first-hand detail, examples, proof, or task-completion copy where appropriate.",
        })
    if filler_hits:
        score -= min(25, len(filler_hits) * 5)
        issues.append({
            "severity": "warning",
            "finding": f"Filler or generic AI-style phrasing detected: {', '.join(filler_hits[:5])}",
            "fix": "Replace generic phrasing with specific observations, concrete examples, and source-backed claims.",
        })
        recommendations.append("Rewrite generic filler phrases into specific, experience-backed statements.")
    if claim_count and citation_gap:
        score -= min(25, citation_gap * 3)
        issues.append({
            "severity": "warning",
            "finding": f"{citation_gap} claim(s) appear to need stronger citation support",
            "fix": "Add primary-source links near statistics, dates, studies, or market claims.",
        })
    if not author_present:
        score -= 10
        issues.append({
            "severity": "info",
            "finding": "No clear author/byline signal detected",
            "fix": "Add author or reviewer attribution on editorial content where relevant.",
        })
    if not date_present:
        score -= 5
        issues.append({
            "severity": "info",
            "finding": "No publication or updated date detected",
            "fix": "Add visible publication or updated dates for informational content.",
        })

    return {
        "url": url,
        "score": max(0, score),
        "word_count": word_count,
        "filler_phrases": filler_hits,
        "claim_count": claim_count,
        "outbound_source_count": len(outbound_sources),
        "citation_gap": citation_gap,
        "author_present": author_present,
        "date_present": date_present,
        "issues": issues,
        "recommendations": recommendations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check deterministic content quality signals")
    parser.add_argument("url_or_file", help="URL or local HTML file")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if args.url_or_file.startswith(("http://", "https://")):
        fetched = fetch_page(args.url_or_file, timeout=20)
        if fetched.get("error"):
            print(json.dumps({"error": fetched["error"]}) if args.json else fetched["error"])
            return 1
        html = fetched.get("content", "")
        data = analyze_html(html, args.url_or_file)
    else:
        with open(args.url_or_file, encoding="utf-8", errors="ignore") as f:
            data = analyze_html(f.read(), args.url_or_file)

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"Content Quality Score: {data['score']}/100")
        for issue in data["issues"]:
            print(f"- {issue['severity'].upper()}: {issue['finding']} Fix: {issue['fix']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

