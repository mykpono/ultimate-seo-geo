#!/usr/bin/env python3
"""
Semantic Topic Clustering via SERP Overlap

Clusters keywords by Jaccard similarity of their top-10 ranking URL sets.
Keywords that share the same search results belong to the same topic cluster —
reflecting Google's own intent mapping rather than lexical similarity.

Input formats:
  serp_overlap  — CSV with columns: keyword, rank, url
  keyword_list  — CSV with a single column of keywords (guidance mode only)

Usage:
    python topic_cluster.py --input serp_data.csv --format serp_overlap --json
    python topic_cluster.py --input keywords.csv --format keyword_list --min-overlap 0.3
    python topic_cluster.py --help
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from itertools import combinations


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_serp_data(filepath: str) -> dict[str, set[str]]:
    """Load SERP data CSV (keyword, rank, url) → {keyword: {url, ...}}."""
    keyword_urls: dict[str, set[str]] = defaultdict(set)
    try:
        with open(filepath, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fields = [c.lower().strip() for c in (reader.fieldnames or [])]
            if "keyword" not in fields or "url" not in fields:
                print(
                    "Error: CSV must have 'keyword' and 'url' columns. "
                    f"Found: {reader.fieldnames}",
                    file=sys.stderr,
                )
                sys.exit(1)
            col_map = {c.lower().strip(): c for c in reader.fieldnames}
            kw_col = col_map["keyword"]
            url_col = col_map["url"]
            for row in reader:
                kw = row[kw_col].strip()
                url = row[url_col].strip()
                if kw and url:
                    keyword_urls[kw].add(url)
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error reading {filepath}: {exc}", file=sys.stderr)
        sys.exit(1)
    return dict(keyword_urls)


def load_keyword_list(filepath: str) -> list[str]:
    """Load a simple keyword list (one keyword per line or single-column CSV)."""
    keywords = []
    try:
        with open(filepath, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    kw = row[0].strip()
                    if kw and kw.lower() != "keyword":
                        keywords.append(kw)
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    return keywords


# ---------------------------------------------------------------------------
# Clustering engine
# ---------------------------------------------------------------------------

def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Jaccard index: |A ∩ B| / |A ∪ B|."""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def build_similarity_matrix(
    keyword_urls: dict[str, set[str]],
) -> dict[tuple[str, str], float]:
    """Compute pairwise Jaccard similarity for all keyword pairs."""
    similarities = {}
    keywords = sorted(keyword_urls.keys())
    for kw_a, kw_b in combinations(keywords, 2):
        score = jaccard_similarity(keyword_urls[kw_a], keyword_urls[kw_b])
        similarities[(kw_a, kw_b)] = score
    return similarities


def cluster_keywords(
    keyword_urls: dict[str, set[str]], min_overlap: float
) -> list[list[str]]:
    """
    Single-linkage clustering: merge keywords whose SERP Jaccard ≥ min_overlap.

    Uses union-find for efficient merging.
    """
    keywords = sorted(keyword_urls.keys())
    parent: dict[str, str] = {kw: kw for kw in keywords}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for kw_a, kw_b in combinations(keywords, 2):
        if jaccard_similarity(keyword_urls[kw_a], keyword_urls[kw_b]) >= min_overlap:
            union(kw_a, kw_b)

    clusters_map: dict[str, list[str]] = defaultdict(list)
    for kw in keywords:
        clusters_map[find(kw)].append(kw)

    return sorted(clusters_map.values(), key=lambda c: -len(c))


def identify_pillar(cluster: list[str], keyword_urls: dict[str, set[str]]) -> str:
    """
    Pick the pillar keyword: the one whose URL set has the most overlap with
    the rest of the cluster (highest average Jaccard with other members).
    Falls back to the keyword with the most ranking URLs.
    """
    if len(cluster) == 1:
        return cluster[0]

    best_kw = cluster[0]
    best_score = -1.0
    for kw in cluster:
        avg = sum(
            jaccard_similarity(keyword_urls[kw], keyword_urls[other])
            for other in cluster
            if other != kw
        ) / (len(cluster) - 1)
        if avg > best_score or (
            avg == best_score and len(keyword_urls[kw]) > len(keyword_urls.get(best_kw, set()))
        ):
            best_score = avg
            best_kw = kw
    return best_kw


def build_link_matrix(
    clusters: list[dict],
    keyword_urls: dict[str, set[str]],
    min_overlap: float,
) -> list[dict]:
    """
    Generate an internal link matrix: which cluster pages should link to which.
    Intra-cluster links are based on SERP overlap; cross-cluster links connect
    pillars when their overlap is above half the threshold.
    """
    links = []

    for cluster in clusters:
        pillar = cluster["pillar"]
        spokes = [kw for kw in cluster["keywords"] if kw != pillar]

        for spoke in spokes:
            links.append({
                "from": pillar,
                "to": spoke,
                "type": "pillar_to_spoke",
                "direction": "bidirectional",
            })

        for spoke_a, spoke_b in combinations(spokes, 2):
            sim = jaccard_similarity(
                keyword_urls.get(spoke_a, set()), keyword_urls.get(spoke_b, set())
            )
            if sim >= min_overlap:
                links.append({
                    "from": spoke_a,
                    "to": spoke_b,
                    "type": "spoke_to_spoke",
                    "direction": "bidirectional",
                    "overlap": round(sim, 3),
                })

    pillars = [c["pillar"] for c in clusters]
    for p_a, p_b in combinations(pillars, 2):
        sim = jaccard_similarity(
            keyword_urls.get(p_a, set()), keyword_urls.get(p_b, set())
        )
        cross_threshold = min_overlap * 0.5
        if sim >= cross_threshold:
            links.append({
                "from": p_a,
                "to": p_b,
                "type": "cross_cluster",
                "direction": "bidirectional",
                "overlap": round(sim, 3),
            })

    return links


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_clusters_text(
    clusters: list[dict],
    link_matrix: list[dict],
    similarity_pairs: list[dict],
) -> str:
    """Human-readable output."""
    lines = []
    lines.append("=" * 60)
    lines.append("SEMANTIC TOPIC CLUSTERING — SERP Overlap Results")
    lines.append("=" * 60)
    lines.append(f"\nTotal keywords: {sum(len(c['keywords']) for c in clusters)}")
    lines.append(f"Clusters found: {len(clusters)}")
    lines.append("")

    for i, cluster in enumerate(clusters, 1):
        lines.append(f"--- Cluster {i} ---")
        lines.append(f"  Pillar topic: {cluster['pillar']}")
        lines.append(f"  Keywords ({len(cluster['keywords'])}):")
        for kw in cluster["keywords"]:
            marker = " [PILLAR]" if kw == cluster["pillar"] else ""
            lines.append(f"    • {kw}{marker}")
        lines.append("")

    if similarity_pairs:
        lines.append("--- Top SERP Overlaps ---")
        for pair in similarity_pairs[:20]:
            lines.append(
                f"  {pair['keyword_a']} ↔ {pair['keyword_b']}: "
                f"Jaccard {pair['jaccard']:.3f} "
                f"({pair['shared_urls']} shared URLs)"
            )
        lines.append("")

    if link_matrix:
        lines.append("--- Internal Link Matrix ---")
        for link in link_matrix:
            arrow = "↔" if link["direction"] == "bidirectional" else "→"
            label = link["type"].replace("_", " ")
            overlap_str = f" (overlap: {link['overlap']:.3f})" if "overlap" in link else ""
            lines.append(f"  {link['from']} {arrow} {link['to']}  [{label}]{overlap_str}")
        lines.append("")

    lines.append("--- Recommendations ---")
    for cluster in clusters:
        if len(cluster["keywords"]) >= 2:
            lines.append(
                f"  • Create pillar page for \"{cluster['pillar']}\" "
                f"covering {len(cluster['keywords'])} subtopics"
            )
    singleton_count = sum(1 for c in clusters if len(c["keywords"]) == 1)
    if singleton_count:
        lines.append(
            f"  • {singleton_count} keyword(s) have no SERP overlap — "
            "consider standalone pages or manual review"
        )

    return "\n".join(lines)


def format_keyword_list_guidance(keywords: list[str]) -> str:
    """Guidance output when no SERP data is available."""
    lines = []
    lines.append("=" * 60)
    lines.append("TOPIC CLUSTERING — Keyword List Mode (No SERP Data)")
    lines.append("=" * 60)
    lines.append(f"\nKeywords loaded: {len(keywords)}")
    lines.append(
        "\n⚠  Without SERP ranking data, automated Jaccard clustering is not possible."
    )
    lines.append("   To enable automated clustering, provide SERP data in CSV format:")
    lines.append("   keyword,rank,url")
    lines.append("")
    lines.append("Manual clustering guidance:")
    lines.append("  1. Search each keyword in Google and note the top-10 URLs.")
    lines.append("  2. Group keywords that share 3+ of the same top-10 URLs.")
    lines.append("  3. Within each group, pick the broadest keyword as the pillar.")
    lines.append("  4. Use DataForSEO extension for automated SERP collection:")
    lines.append("     See references/optional-extensions-mcp.md")
    lines.append("")
    lines.append("Keywords to research:")
    for kw in keywords:
        lines.append(f"  • {kw}")
    lines.append("")
    lines.append(
        "Re-run with SERP data: "
        "python scripts/topic_cluster.py --input serp_data.csv --format serp_overlap"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Cluster keywords by SERP overlap (Jaccard similarity of top-10 "
            "ranking URL sets). Groups keywords that Google treats as the same "
            "topic, identifies pillar pages, and generates an internal link matrix."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Cluster using SERP data (keyword,rank,url CSV)\n"
            "  python topic_cluster.py --input serp_data.csv --format serp_overlap\n\n"
            "  # Stricter clustering threshold\n"
            "  python topic_cluster.py --input serp_data.csv --format serp_overlap "
            "--min-overlap 0.5\n\n"
            "  # Keyword-only mode (guidance, no automated clustering)\n"
            "  python topic_cluster.py --input keywords.csv --format keyword_list\n\n"
            "  # JSON output\n"
            "  python topic_cluster.py --input serp_data.csv --format serp_overlap --json"
        ),
    )
    parser.add_argument(
        "--input", required=True, help="CSV file path with keyword/SERP data"
    )
    parser.add_argument(
        "--format",
        choices=["serp_overlap", "keyword_list"],
        default="serp_overlap",
        help="Input format: 'serp_overlap' (CSV with keyword,rank,url) or "
        "'keyword_list' (keywords only). Default: serp_overlap",
    )
    parser.add_argument(
        "--min-overlap",
        type=float,
        default=0.3,
        help="Minimum Jaccard similarity to cluster keywords together. Default: 0.3",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output results as JSON"
    )

    args = parser.parse_args()

    if args.min_overlap < 0 or args.min_overlap > 1:
        print("Error: --min-overlap must be between 0 and 1", file=sys.stderr)
        sys.exit(1)

    if args.format == "keyword_list":
        keywords = load_keyword_list(args.input)
        if not keywords:
            print("Error: No keywords found in input file", file=sys.stderr)
            sys.exit(1)

        if args.json:
            print(json.dumps({
                "mode": "keyword_list",
                "keywords": keywords,
                "total_keywords": len(keywords),
                "note": (
                    "No SERP data provided. Automated Jaccard clustering requires "
                    "keyword,rank,url CSV format. See --format serp_overlap."
                ),
            }, indent=2))
        else:
            print(format_keyword_list_guidance(keywords))
        return

    # serp_overlap mode
    keyword_urls = load_serp_data(args.input)
    if not keyword_urls:
        print("Error: No valid SERP data found in input file", file=sys.stderr)
        sys.exit(1)

    raw_clusters = cluster_keywords(keyword_urls, args.min_overlap)
    clusters = []
    for group in raw_clusters:
        pillar = identify_pillar(group, keyword_urls)
        clusters.append({
            "pillar": pillar,
            "keywords": group,
            "size": len(group),
        })

    link_matrix = build_link_matrix(clusters, keyword_urls, args.min_overlap)

    similarity_pairs = []
    for (kw_a, kw_b), score in sorted(
        build_similarity_matrix(keyword_urls).items(), key=lambda x: -x[1]
    ):
        if score > 0:
            shared = keyword_urls[kw_a] & keyword_urls[kw_b]
            similarity_pairs.append({
                "keyword_a": kw_a,
                "keyword_b": kw_b,
                "jaccard": round(score, 4),
                "shared_urls": len(shared),
                "shared_url_list": sorted(shared),
            })

    if args.json:
        print(json.dumps({
            "mode": "serp_overlap",
            "min_overlap": args.min_overlap,
            "total_keywords": len(keyword_urls),
            "total_clusters": len(clusters),
            "clusters": clusters,
            "link_matrix": link_matrix,
            "top_overlaps": similarity_pairs[:30],
        }, indent=2))
    else:
        print(format_clusters_text(clusters, link_matrix, similarity_pairs))


if __name__ == "__main__":
    main()
