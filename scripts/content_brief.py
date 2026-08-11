#!/usr/bin/env python3
"""
Content Brief Generator

Generates structured content briefs for writers by analyzing competitor pages.
Extracts heading outlines, word counts, schema types, and key topics, then
produces a recommended outline, word count target, schema suggestions,
and AI citation opportunities.

Usage:
    python content_brief.py "target keyword"
    python content_brief.py "target keyword" --competitors url1 url2 url3
    python content_brief.py "target keyword" --competitors url1 url2 --site https://mysite.com --json
    python content_brief.py --help
"""

import argparse
import json
import re
import sys
from collections import Counter
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 required. Install with: pip install beautifulsoup4")
    sys.exit(1)

try:
    from fetch_page import fetch_page
except ImportError:
    print(
        "Error: fetch_page module not found. Run from the scripts/ directory or "
        "add it to PYTHONPATH.",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from url_safety import validate_url
except ImportError:
    validate_url = None


STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "with", "by", "of", "from", "as", "is", "are", "was", "were", "be",
    "been", "this", "that", "these", "those", "it", "he", "she", "they",
    "we", "you", "i", "your", "my", "their", "our", "its", "which", "who",
    "whom", "whose", "what", "where", "when", "why", "how", "all", "any",
    "both", "each", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very", "can",
    "will", "just", "should", "have", "has", "had", "do", "does", "did",
    "get", "got", "make", "use", "used", "also", "about", "into",
    "then", "there", "would", "could", "here",
}


# ---------------------------------------------------------------------------
# Page analysis
# ---------------------------------------------------------------------------

def analyze_page(url: str) -> dict | None:
    """Fetch and analyze a single competitor page."""
    if validate_url:
        safe = validate_url(url)
        if not safe.ok:
            print(f"  Skipping {url}: {safe.reason}", file=sys.stderr)
            return None

    result = fetch_page(url, timeout=20)
    if result.get("error") or not result.get("content"):
        print(f"  Skipping {url}: {result.get('error', 'empty response')}", file=sys.stderr)
        return None

    soup = BeautifulSoup(result["content"], "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag:
        meta_desc = meta_tag.get("content", "")

    headings = extract_headings(soup)
    body_text = soup.get_text(separator=" ", strip=True)
    word_count = len(body_text.split())
    schema_types = extract_schema_types(result["content"])
    key_phrases = extract_key_phrases(body_text)

    return {
        "url": url,
        "title": title,
        "meta_description": meta_desc,
        "headings": headings,
        "word_count": word_count,
        "schema_types": schema_types,
        "key_phrases": key_phrases,
    }


def extract_headings(soup: BeautifulSoup) -> list[dict]:
    """Extract H1–H3 headings with their level."""
    headings = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 1:
            headings.append({
                "level": tag.name,
                "text": text,
            })
    return headings


def extract_schema_types(html: str) -> list[str]:
    """Extract JSON-LD schema @type values from raw HTML."""
    types = []
    for match in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(match.group(1))
            _collect_types(data, types)
        except (json.JSONDecodeError, ValueError):
            pass
    return list(dict.fromkeys(types))


def _collect_types(data: object, types: list[str]) -> None:
    """Recursively collect @type values from JSON-LD structures."""
    if isinstance(data, dict):
        if "@type" in data:
            t = data["@type"]
            if isinstance(t, list):
                types.extend(t)
            else:
                types.append(t)
        if "@graph" in data:
            _collect_types(data["@graph"], types)
        for v in data.values():
            if isinstance(v, (dict, list)):
                _collect_types(v, types)
    elif isinstance(data, list):
        for item in data:
            _collect_types(item, types)


def extract_key_phrases(text: str, top_n: int = 30) -> list[str]:
    """Extract likely key phrases (bigrams and trigrams) from body text."""
    words = re.findall(r"[a-z][a-z'-]+", text.lower())
    words = [w for w in words if w not in STOP_WORDS and len(w) > 2]

    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
    trigrams = [
        f"{words[i]} {words[i+1]} {words[i+2]}" for i in range(len(words) - 2)
    ]

    counts = Counter(bigrams + trigrams)
    return [phrase for phrase, _ in counts.most_common(top_n) if counts[phrase] >= 2]


# ---------------------------------------------------------------------------
# Brief generation
# ---------------------------------------------------------------------------

def merge_outlines(analyses: list[dict], target_keyword: str) -> list[dict]:
    """
    Merge heading outlines from multiple competitor pages into a recommended
    outline. H2s that appear in 2+ competitors are prioritized.
    """
    h2_counts: Counter = Counter()
    h3_under_h2: dict[str, Counter] = {}

    for analysis in analyses:
        current_h2 = None
        seen_h2 = set()
        for h in analysis["headings"]:
            normalized = h["text"].strip().lower()
            if h["level"] == "h2":
                current_h2 = h["text"].strip()
                if normalized not in seen_h2:
                    h2_counts[current_h2] += 1
                    seen_h2.add(normalized)
                if current_h2 not in h3_under_h2:
                    h3_under_h2[current_h2] = Counter()
            elif h["level"] == "h3" and current_h2:
                h3_under_h2[current_h2][h["text"].strip()] += 1

    seen_normalized = set()
    outline = []
    for h2, count in h2_counts.most_common():
        norm = h2.lower()
        if norm in seen_normalized:
            continue
        seen_normalized.add(norm)
        entry = {
            "level": "h2",
            "text": h2,
            "competitor_count": count,
            "sub_headings": [],
        }
        if h2 in h3_under_h2:
            seen_h3 = set()
            for h3, h3_count in h3_under_h2[h2].most_common(5):
                h3_norm = h3.lower()
                if h3_norm not in seen_h3:
                    seen_h3.add(h3_norm)
                    entry["sub_headings"].append({
                        "level": "h3",
                        "text": h3,
                        "competitor_count": h3_count,
                    })
        outline.append(entry)

    return outline


def suggest_secondary_keywords(
    analyses: list[dict], target_keyword: str
) -> list[str]:
    """Extract secondary keywords from competitor headings and key phrases."""
    target_words = set(target_keyword.lower().split())
    candidates: Counter = Counter()

    for analysis in analyses:
        for h in analysis["headings"]:
            text = h["text"].lower()
            words = set(re.findall(r"[a-z][a-z'-]+", text))
            new_words = words - target_words - STOP_WORDS
            if new_words and len(new_words) <= 4:
                candidates[h["text"].strip()] += 1

        for phrase in analysis["key_phrases"]:
            phrase_words = set(phrase.split())
            if not phrase_words.issubset(target_words | STOP_WORDS):
                candidates[phrase] += 1

    return [kw for kw, count in candidates.most_common(15) if count >= 2]


def recommend_schema(analyses: list[dict], target_keyword: str) -> list[dict]:
    """Recommend schema types based on competitor usage and keyword signals."""
    type_counts: Counter = Counter()
    for analysis in analyses:
        for t in analysis["schema_types"]:
            type_counts[t] += 1

    recommendations = []
    kw_lower = target_keyword.lower()

    always = ["WebPage", "BreadcrumbList"]
    for schema in always:
        recommendations.append({
            "type": schema,
            "reason": "Universal best practice",
            "priority": "required",
        })

    if any(w in kw_lower for w in ("how to", "guide", "tutorial", "steps")):
        recommendations.append({
            "type": "HowTo",
            "reason": "Tutorial/how-to content detected from keyword",
            "priority": "recommended",
            "note": "Rich results removed but schema still valid for AI engines",
        })

    if any(w in kw_lower for w in ("what is", "faq", "questions")):
        recommendations.append({
            "type": "FAQPage",
            "reason": "Q&A content detected from keyword",
            "priority": "recommended",
            "note": "FAQ rich results retired May 2026 — keep as AI/entity signal",
        })

    article_signals = ("blog", "article", "post", "guide", "review", "news")
    if any(w in kw_lower for w in article_signals):
        recommendations.append({
            "type": "Article",
            "reason": "Article-type content detected",
            "priority": "recommended",
        })

    for schema_type, count in type_counts.most_common(10):
        existing = {r["type"] for r in recommendations}
        if schema_type not in existing and count >= 2:
            recommendations.append({
                "type": schema_type,
                "reason": f"Used by {count}/{len(analyses)} competitors",
                "priority": "consider",
            })

    return recommendations


def identify_snippet_opportunities(
    target_keyword: str, outline: list[dict]
) -> list[dict]:
    """Identify featured snippet and AI citation opportunities."""
    opportunities = []

    opportunities.append({
        "type": "definition_snippet",
        "suggestion": (
            f"Add a 40–60 word definition paragraph immediately after an H2 "
            f"\"What is {target_keyword.title()}?\" — this targets both "
            f"featured snippets and AI Overview citations."
        ),
        "format": "paragraph",
    })

    list_headings = [
        h for h in outline
        if any(w in h["text"].lower() for w in ("best", "top", "types", "ways", "steps"))
    ]
    if list_headings:
        opportunities.append({
            "type": "list_snippet",
            "suggestion": (
                f"Structure \"{list_headings[0]['text']}\" as an ordered/unordered "
                f"list with 5–9 items for list snippet eligibility."
            ),
            "format": "list",
        })

    comparison_headings = [
        h for h in outline
        if any(w in h["text"].lower() for w in ("vs", "comparison", "compare", "difference"))
    ]
    if comparison_headings:
        opportunities.append({
            "type": "table_snippet",
            "suggestion": (
                f"Add a comparison table (≤4 columns) under "
                f"\"{comparison_headings[0]['text']}\" for table snippet eligibility."
            ),
            "format": "table",
        })

    opportunities.append({
        "type": "ai_citation",
        "suggestion": (
            "Place the most authoritative answer in the first 30% of the "
            "article body. 44.2% of AI citations pull from the opening section. "
            "Include named author + publication date for 3× AI citation rate."
        ),
        "format": "structural",
    })

    return opportunities


def find_internal_link_candidates(
    site_url: str, target_keyword: str
) -> list[dict]:
    """Crawl the site's homepage to find internal link candidates."""
    candidates = []
    result = fetch_page(site_url, timeout=15)
    if result.get("error") or not result.get("content"):
        return candidates

    soup = BeautifulSoup(result["content"], "html.parser")
    parsed_site = urlparse(site_url)
    domain = parsed_site.netloc
    target_words = set(target_keyword.lower().split())

    seen = set()
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        absolute = urljoin(site_url, href)
        link_parsed = urlparse(absolute)
        if link_parsed.netloc != domain:
            continue

        normalized = f"{link_parsed.scheme}://{link_parsed.netloc}{link_parsed.path}"
        if normalized in seen or normalized.rstrip("/") == site_url.rstrip("/"):
            continue
        seen.add(normalized)

        anchor_text = link.get_text(strip=True)
        path_words = set(
            re.findall(r"[a-z]+", link_parsed.path.lower())
        )
        anchor_words = set(
            re.findall(r"[a-z]+", anchor_text.lower())
        ) if anchor_text else set()

        relevance_words = path_words | anchor_words
        overlap = relevance_words & target_words
        if overlap:
            candidates.append({
                "url": normalized,
                "anchor_text": anchor_text or "(no anchor text)",
                "relevance": f"Matched: {', '.join(sorted(overlap))}",
            })

    candidates.sort(key=lambda c: -len(re.findall(r"[a-z]+", c["relevance"])))
    return candidates[:10]


def generate_brief(
    target_keyword: str,
    analyses: list[dict],
    site_url: str | None = None,
) -> dict:
    """Assemble the full content brief from competitor analyses."""
    outline = merge_outlines(analyses, target_keyword) if analyses else []

    word_counts = [a["word_count"] for a in analyses if a["word_count"] > 0]
    if word_counts:
        avg_words = sum(word_counts) // len(word_counts)
        recommended_words = max(avg_words, 1500)
        word_count_range = {
            "minimum": max(int(avg_words * 0.8), 1200),
            "target": recommended_words,
            "stretch": int(avg_words * 1.3),
            "competitor_average": avg_words,
            "competitor_range": f"{min(word_counts)}–{max(word_counts)}",
        }
    else:
        word_count_range = {
            "minimum": 1500,
            "target": 2000,
            "stretch": 2500,
            "competitor_average": None,
            "competitor_range": "N/A (no competitors analyzed)",
        }

    secondary_keywords = suggest_secondary_keywords(analyses, target_keyword)
    schema = recommend_schema(analyses, target_keyword)
    snippets = identify_snippet_opportunities(target_keyword, outline)

    internal_links = []
    if site_url:
        print(f"  Scanning {site_url} for internal link candidates...", file=sys.stderr)
        internal_links = find_internal_link_candidates(site_url, target_keyword)

    brief = {
        "target_keyword": target_keyword,
        "secondary_keywords": secondary_keywords,
        "word_count": word_count_range,
        "suggested_outline": outline,
        "schema_recommendations": schema,
        "snippet_opportunities": snippets,
        "internal_link_suggestions": internal_links,
        "competitor_analysis": [
            {
                "url": a["url"],
                "title": a["title"],
                "word_count": a["word_count"],
                "heading_count": len(a["headings"]),
                "schema_types": a["schema_types"],
            }
            for a in analyses
        ],
    }

    return brief


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_brief_text(brief: dict) -> str:
    """Human-readable content brief."""
    lines = []
    lines.append("=" * 60)
    lines.append("CONTENT BRIEF")
    lines.append("=" * 60)
    lines.append(f"\nTarget Keyword: {brief['target_keyword']}")

    if brief["secondary_keywords"]:
        lines.append(f"\nSecondary Keywords ({len(brief['secondary_keywords'])}):")
        for kw in brief["secondary_keywords"]:
            lines.append(f"  • {kw}")

    wc = brief["word_count"]
    lines.append(f"\nWord Count Target:")
    lines.append(f"  Minimum:  {wc['minimum']} words")
    lines.append(f"  Target:   {wc['target']} words")
    lines.append(f"  Stretch:  {wc['stretch']} words")
    if wc.get("competitor_average"):
        lines.append(f"  Competitor avg: {wc['competitor_average']} words ({wc['competitor_range']})")

    if brief["suggested_outline"]:
        lines.append(f"\nSuggested Outline:")
        lines.append(f"  H1: {brief['target_keyword'].title()}")
        for h2 in brief["suggested_outline"]:
            freq = f" (in {h2['competitor_count']}/{len(brief['competitor_analysis'])} competitors)" if brief["competitor_analysis"] else ""
            lines.append(f"  H2: {h2['text']}{freq}")
            for h3 in h2.get("sub_headings", []):
                lines.append(f"    H3: {h3['text']}")

    if brief["schema_recommendations"]:
        lines.append(f"\nSchema Recommendations:")
        for s in brief["schema_recommendations"]:
            note = f" — {s['note']}" if s.get("note") else ""
            lines.append(f"  [{s['priority'].upper()}] {s['type']}: {s['reason']}{note}")

    if brief["snippet_opportunities"]:
        lines.append(f"\nFeatured Snippet / AI Citation Opportunities:")
        for opp in brief["snippet_opportunities"]:
            lines.append(f"  [{opp['format'].upper()}] {opp['suggestion']}")

    if brief["internal_link_suggestions"]:
        lines.append(f"\nInternal Link Suggestions ({len(brief['internal_link_suggestions'])}):")
        for link in brief["internal_link_suggestions"]:
            lines.append(f"  • {link['url']}")
            lines.append(f"    Anchor: \"{link['anchor_text']}\" — {link['relevance']}")

    if brief["competitor_analysis"]:
        lines.append(f"\nCompetitor Summary:")
        for comp in brief["competitor_analysis"]:
            lines.append(f"  • {comp['url']}")
            lines.append(f"    Title: {comp['title']}")
            lines.append(f"    Words: {comp['word_count']} | Headings: {comp['heading_count']} | Schema: {', '.join(comp['schema_types']) or 'none'}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a structured content brief for writers. Analyzes competitor "
            "pages to extract heading outlines, word counts, schema types, and "
            "key topics. Produces a recommended outline, word count target, schema "
            "suggestions, and AI citation opportunities."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Brief from keyword alone (no competitor analysis)\n"
            "  python content_brief.py \"project management software\"\n\n"
            "  # Brief with competitor analysis\n"
            "  python content_brief.py \"best crm\" --competitors "
            "https://site1.com/crm https://site2.com/crm\n\n"
            "  # Brief with internal link suggestions\n"
            "  python content_brief.py \"email marketing\" "
            "--competitors https://competitor.com/guide "
            "--site https://mysite.com\n\n"
            "  # JSON output to file\n"
            "  python content_brief.py \"seo tools\" --competitors url1 url2 "
            "--json --output brief.json"
        ),
    )
    parser.add_argument(
        "keyword", help="Target keyword for the content brief"
    )
    parser.add_argument(
        "--competitors",
        nargs="+",
        default=[],
        help="1–5 competitor URLs to analyze for structure and topics",
    )
    parser.add_argument(
        "--site",
        default=None,
        help="Your site URL — used to suggest internal links",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output results as JSON"
    )

    args = parser.parse_args()

    if len(args.competitors) > 5:
        print("Warning: Limiting to first 5 competitor URLs", file=sys.stderr)
        args.competitors = args.competitors[:5]

    analyses = []
    if args.competitors:
        print(f"Analyzing {len(args.competitors)} competitor page(s)...", file=sys.stderr)
        for url in args.competitors:
            print(f"  Fetching {url}...", file=sys.stderr)
            analysis = analyze_page(url)
            if analysis:
                analyses.append(analysis)
        print(f"  Successfully analyzed {len(analyses)}/{len(args.competitors)} page(s)", file=sys.stderr)

    brief = generate_brief(args.keyword, analyses, args.site)

    if args.json:
        output = json.dumps(brief, indent=2, ensure_ascii=False)
    else:
        output = format_brief_text(brief)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\nBrief written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
