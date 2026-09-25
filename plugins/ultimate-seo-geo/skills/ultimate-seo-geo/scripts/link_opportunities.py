#!/usr/bin/env python3
"""
Find pages that talk about a target page's topic but do not link to it.

Give it the shared crawl (site_graph.py --out), the page you want to rank
(usually a money page) and the words it should rank for. It returns, for each
page that mentions those words in its own content and does not already link to
the target from its content: the sentence to put the link in, and the anchor to
use.

    python scripts/site_graph.py https://example.com --max-pages 200 --out site_graph.json
    python scripts/link_opportunities.py --graph site_graph.json \\
        --target https://example.com/pricing --terms "pricing" "plans and pricing"
    python scripts/link_opportunities.py --graph site_graph.json --target https://example.com/pricing \\
        --queries rows.json --gsc-pages Pages.csv --json

How it decides:
  * A page that already links to the target from its content (not the header,
    nav, footer or breadcrumb) is done and left out. A page that links only
    from the navigation stays in and is marked: a link in the text still adds
    context the menu does not.
  * Only the page's own content is read: <main> or <article>, else the body
    without header, nav, footer, aside and forms. Text that is already a link
    is blanked, so a term that is already another link's anchor does not count.
  * The anchor is a Search Console query for the target when one appears in
    the sentence (--queries), else the term as the sentence writes it.
  * At most --max-fetch candidate pages are fetched: those naming a term in
    their title or H1 first, then pages in the target's section, then the
    shallowest. The output says how many were not read; absence of an
    opportunity on an unread page is not a claim.

--queries takes a text file (one query per line) or a gsc_insights.py
--save-rows file, from which the target's own queries are read. --gsc-pages
(the Search Console Pages export, or gsc_insights / gsc_query output) orders
the opportunities by the source page's clicks.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

CHROME_REGIONS = frozenset({"nav", "header", "footer", "breadcrumb"})
DEFAULT_MAX_FETCH = 60
DEFAULT_LIMIT = 25
MAX_QUERIES = 50
LINK_MARK = "⁣"   # invisible separator standing in for text that is already a link
# Prose, not page furniture: breadcrumbs, "Copy as Markdown | ..." bars, card bylines and
# carousel controls flatten into "sentences" (seen on developers.cloudflare.com,
# smashingmagazine.com and balloonbay.us). A sentence to put a link in has words.
MIN_WORDS = 6
MAX_EXISTING_LINKS = 2
MAX_SYMBOLS = 1
MAX_TITLE_CASE = 0.6   # "Newsletter Email Newsletter For The Next Ones" is a heading, not prose
SYMBOL_RE = re.compile(r"[|⇄‹›«»→←/·•]")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


def _key(url: str) -> str:
    """host/path, with scheme, www., query, fragment and trailing slash dropped.

    Looser than site_graph.page_key on purpose: smashingmagazine.com's graph holds
    both www and apex copies of a page, and the target must match either.
    """
    parsed = urlparse(str(url or "").strip())
    host = parsed.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    return f"{host}{parsed.path.rstrip('/') or '/'}"


def _term_re(term: str):
    return re.compile(r"(?<![\w-])" + re.escape(term.strip()).replace(r"\ ", r"\s+") + r"(?![\w-])", re.I)


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

def load_queries(path: str, target: str) -> list:
    """Queries for the target: a text list, or a gsc_insights.py --save-rows file (its rows for the target page)."""
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        rows = ((data.get("query_page") or {}).get("rows") if isinstance(data, dict) else None)
        if rows is None:
            raise ValueError(f"{path}: not a gsc_insights.py --save-rows file (no query_page rows)")
        want = _key(target)
        mine = [r for r in rows if _key(r.get("page")) == want and str(r.get("query") or "").strip()]
        mine.sort(key=lambda r: -(r.get("impressions") or 0))
        queries = []
        for r in mine:
            q = str(r["query"]).strip()
            if q.lower() not in (x.lower() for x in queries):
                queries.append(q)
        return queries[:MAX_QUERIES]
    with open(path, encoding="utf-8-sig") as fh:
        return [line.strip() for line in fh if line.strip() and not line.startswith("#")][:MAX_QUERIES]


def load_clicks(path: str) -> dict:
    """{page key: clicks} from any page-traffic file gsc_insights.load_page_traffic reads."""
    import gsc_insights
    traffic = gsc_insights.load_page_traffic(path)
    return {_key(p["page"]): p["clicks"] for p in traffic["pages"]}


# ---------------------------------------------------------------------------
# Candidates from the graph
# ---------------------------------------------------------------------------

def plan(graph: dict, target: str, terms: list, max_fetch: int) -> dict:
    """Which pages to read, which already link, and which were left unread."""
    target_key = _key(target)
    pages = [p for p in (graph.get("pages") or {}).values() if p.get("out_links") is not None]
    target_dir = (urlparse(target).path.strip("/").split("/") or [""])[0]
    patterns = [_term_re(t) for t in terms]
    linking_content, candidates = [], []
    for page in pages:
        key = _key(page.get("key") or page.get("url"))
        if key == target_key or (page.get("canonical") and _key(page["canonical"]) == target_key):
            continue  # the target itself, under another host spelling or a canonical pointing at it
        to_target = [l for l in page.get("out_links") or [] if l.get("key") and _key(l["key"]) == target_key]
        in_content = [l for l in to_target if l.get("region") not in CHROME_REGIONS
                      and l.get("container") not in ("header", "footer")]
        if in_content:
            linking_content.append(page["url"])
            continue
        heading = " ".join(str(page.get(k) or "") for k in ("title", "h1"))
        in_heading = any(p.search(heading) for p in patterns)
        same_dir = bool(target_dir) and urlparse(page["url"]).path.strip("/").split("/")[0] == target_dir
        candidates.append({
            "page": page, "nav_only_link": bool(to_target), "term_in_heading": in_heading,
            "rank": (not in_heading, not same_dir, page.get("depth") or 0, page["url"]),
        })
    candidates.sort(key=lambda c: c["rank"])
    return {
        "target_key": target_key,
        "pages_in_graph": len(pages),
        "already_linking": linking_content,
        "to_fetch": candidates[:max_fetch],
        "not_fetched": len(candidates) - min(len(candidates), max_fetch),
    }


# ---------------------------------------------------------------------------
# Reading one page
# ---------------------------------------------------------------------------

def content_text(html: str) -> str:
    """The page's own content with every link's text blanked (see LINK_MARK)."""
    from bs4 import BeautifulSoup
    import site_graph
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a"):
        a.replace_with(f" {LINK_MARK} ")
    return site_graph._main_text(soup)


def is_prose(sentence: str) -> bool:
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", sentence)
    if len(words) < MIN_WORDS:
        return False
    capitalised = sum(1 for w in words if w[0].isupper()) / len(words)
    return (sentence.count(LINK_MARK) <= MAX_EXISTING_LINKS and len(SYMBOL_RE.findall(sentence)) <= MAX_SYMBOLS
            and capitalised <= MAX_TITLE_CASE)


def part_of_longer_name(sentence: str, match) -> bool:
    """ "Workers AI", "Workers KV": the term followed by another capitalised word is a different name."""
    return bool(re.match(r"\s+[A-Z][A-Za-z0-9]*\b", sentence[match.end():]))


def find_mentions(text: str, terms: list, queries: list) -> list:
    """[(sentence, term, anchor)] for sentences that use a term outside any link."""
    out = []
    term_patterns = [(t, _term_re(t)) for t in terms]
    query_patterns = [(q, _term_re(q)) for q in sorted(queries, key=len, reverse=True)]
    for sentence in SENTENCE_RE.split(text):
        sentence = " ".join(sentence.split())
        if not sentence or len(sentence) > 400 or not is_prose(sentence):
            continue  # a 400-character "sentence" is a list or a table flattened, not prose to link from
        for term, pattern in term_patterns:
            m = next((x for x in pattern.finditer(sentence) if not part_of_longer_name(sentence, x)), None)
            if not m:
                continue
            anchor = next((q.group(0) for _, p in query_patterns for q in [p.search(sentence)] if q), None)
            out.append((sentence.replace(LINK_MARK, "[link]"), term,
                        anchor or m.group(0)))
            break
    return out


def read_candidate(candidate: dict, terms: list, queries: list, fetch) -> dict:
    page = candidate["page"]
    fetched = fetch(page["url"])
    if fetched.get("error") or not fetched.get("html"):
        return {"url": page["url"], "error": fetched.get("error") or "empty page"}
    mentions = find_mentions(content_text(fetched["html"]), terms, queries)
    return {"url": page["url"], "title": page.get("title"), "depth": page.get("depth"),
            "nav_only_link": candidate["nav_only_link"], "term_in_heading": candidate["term_in_heading"],
            "mentions": mentions}


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def find_opportunities(graph: dict, target: str, terms: list, queries=None, clicks=None,
                       max_fetch: int = DEFAULT_MAX_FETCH, limit: int = DEFAULT_LIMIT, fetch=None, workers: int = 5) -> dict:
    queries = queries or []
    terms = [t for t in dict.fromkeys(t.strip() for t in (terms or []) + queries[:10]) if t]
    if not terms:
        raise ValueError("no terms: give --terms, or --queries with at least one query for the target")
    if fetch is None:
        import site_graph
        fetch = site_graph.fetch_url
    p = plan(graph, target, terms, max_fetch)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        read = list(pool.map(lambda c: read_candidate(c, terms, queries, fetch), p["to_fetch"]))
    errors = [r for r in read if r.get("error")]
    opportunities = []
    for r in read:
        if r.get("error") or not r["mentions"]:
            continue
        sentence, term, anchor = r["mentions"][0]
        opportunities.append({
            "source": r["url"], "title": r.get("title"), "depth": r.get("depth"),
            "clicks": (clicks or {}).get(_key(r["url"])),
            "sentence": sentence, "term": term, "anchor": anchor,
            "anchor_from": "search console query" if anchor.lower() in (q.lower() for q in queries) else "term",
            "other_mentions": len(r["mentions"]) - 1,
            "nav_only_link": r["nav_only_link"], "term_in_heading": r["term_in_heading"],
        })
    opportunities.sort(key=lambda o: (-(o["clicks"] or 0), not o["term_in_heading"], o["depth"] or 0, o["source"]))
    result = {
        "target": target,
        "terms": terms,
        "queries_used": len(queries),
        "pages_in_graph": p["pages_in_graph"],
        "already_linking_from_content": len(p["already_linking"]),
        "pages_read": len(read) - len(errors),
        "pages_not_read": p["not_fetched"],
        "fetch_errors": [{"url": e["url"], "error": e["error"]} for e in errors[:10]],
        "count": len(opportunities),
        "opportunities": opportunities[:limit],
        "ordered_by": "source page clicks (Search Console)" if clicks else "term in title or H1, then click depth",
        "limits": [
            "Only pages in the graph are considered; build it with a --max-pages that covers the site.",
            "Pages beyond --max-fetch were not read, so no opportunity on them is a gap in coverage, not a finding.",
            "The sentence is where the topic is named; a person still checks that a link reads naturally there.",
        ],
    }
    if p["not_fetched"]:
        result["limits"].append(f"{p['not_fetched']} candidate page(s) were not read (raise --max-fetch).")
    result["issues"] = build_issues(result)
    return result


def build_issues(result: dict) -> list:
    if not result["count"]:
        return []
    top = result["opportunities"][0]
    return [{
        "severity": "low",
        "kind": "opportunity",
        "lane": "Auto",
        "code": "internal_links.link_opportunities",
        "finding": (f"{result['count']} page(s) name {', '.join(repr(t) for t in result['terms'][:3])} in their content "
                    f"but do not link to {result['target']} from it."),
        "evidence": f"{top['source']}: \"{top['sentence'][:200]}\" (anchor: \"{top['anchor']}\")",
        "impact": ("Contextual links from pages on the same topic tell Google what the target is about and pass it "
                   "link equity; navigation links alone carry less context."),
        "fix": "Add one link per listed page, in the quoted sentence, using the proposed anchor. Start with the pages that earn the most clicks.",
        "confidence": "Confirmed",
        "falsifiability": "Wrong if the quoted sentence uses the term in another sense; read each sentence before linking.",
        "leading_indicator": "Position of the target's main queries in Search Console, four weeks after the links go live.",
        "urls": [o["source"] for o in result["opportunities"][:10]],
    }]


def print_human(result: dict) -> None:
    print(f"Link opportunities -> {result['target']}")
    print(f"Terms: {', '.join(result['terms'])}   ({result['queries_used']} Search Console queries)")
    print(f"Graph: {result['pages_in_graph']} pages; {result['already_linking_from_content']} already link from content; "
          f"{result['pages_read']} read, {result['pages_not_read']} not read")
    print("=" * 78)
    if not result["opportunities"]:
        print("No page read names a term without linking to the target.")
    for o in result["opportunities"]:
        clicks = f"{o['clicks']:,} clicks  " if o["clicks"] is not None else ""
        nav = "  [linked from nav only]" if o["nav_only_link"] else ""
        print(f"\n{clicks}{o['source']}{nav}")
        print(f"  anchor ({o['anchor_from']}): \"{o['anchor']}\"")
        print(f"  sentence: {o['sentence'][:240]}")
    for e in result["fetch_errors"]:
        print(f"\nNot read: {e['url']} ({e['error']})")
    for line in result["limits"]:
        print(f"Limit: {line}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pages that mention a target's topic but do not link to it")
    parser.add_argument("--graph", required=True, metavar="PATH", help="site_graph.py --out file")
    parser.add_argument("--target", required=True, metavar="URL", help="The page that should receive the links")
    parser.add_argument("--terms", nargs="+", default=[], metavar="TERM", help="Words the target should rank for")
    parser.add_argument("--queries", metavar="PATH",
                        help="The target's Search Console queries: a text file (one per line) or a gsc_insights.py --save-rows file")
    parser.add_argument("--gsc-pages", metavar="PATH",
                        help="Page clicks (Search Console Pages CSV, gsc_insights or gsc_query output) to order the results")
    parser.add_argument("--max-fetch", type=int, default=DEFAULT_MAX_FETCH, help=f"Candidate pages to read (default {DEFAULT_MAX_FETCH})")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"Opportunities listed (default {DEFAULT_LIMIT})")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()
    if args.max_fetch < 1 or args.limit < 1:
        parser.error("--max-fetch and --limit must be positive")
    if not args.target.startswith(("http://", "https://")):
        parser.error("--target must be an absolute URL")

    import site_graph
    try:
        graph = site_graph.load_graph(args.graph)
    except (OSError, ValueError) as exc:
        parser.error(f"--graph: {exc}")
    queries = []
    if args.queries:
        try:
            queries = load_queries(args.queries, args.target)
        except (OSError, ValueError) as exc:
            parser.error(f"--queries: {exc}")
    clicks = None
    if args.gsc_pages:
        try:
            clicks = load_clicks(args.gsc_pages)
        except (OSError, ValueError) as exc:
            parser.error(f"--gsc-pages: {exc}")
    if not args.terms and not queries:
        parser.error("give --terms, or --queries with queries for the target")
    if _key(args.target) not in {_key(p.get("key") or p.get("url")) for p in graph.get("pages", {}).values()}:
        print(f"Note: {args.target} is not in the graph; links to it are matched by URL only.", file=sys.stderr)
    result = find_opportunities(graph, args.target, args.terms, queries, clicks, args.max_fetch, args.limit)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_human(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
