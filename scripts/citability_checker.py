#!/usr/bin/env python3
"""
Citability and structure check for one page (GEO § 3, Citability and Structural Readability).

Measures, from the page HTML, the structural proxies the references name for
passages AI search engines can lift and cite. It does not know the target
query, so it cannot judge whether a passage answers it; it measures shape:

- passage shape:     no section runs over 350 words of prose without a list, table or subheading
- paragraph length:  paragraphs of 120 words or fewer
- headings:          one H1, no skipped levels; question-style headings are counted
- specificity:       paragraphs carrying figures or attributed sources

Also reported, not scored:
- lead: a paragraph of 15+ words starts within the first 60 paragraph words after
  the H1 (a Low finding when absent)
- long openings: sections whose first sentence runs over 40 words

Both are in the rubric, but on the 13 validation pages neither varied: every
article had a lead and no section took over 60 words to finish its first
sentence. A component that never varies only inflates the score, so the score
uses the four that did.

Pages that are not article-style are reported as not applicable, with no score:
under MIN_WORDS words of main content, fewer than MIN_SECTIONS real sections
(unless LONG_UNSECTIONED+ words), or less than MIN_PROSE_SHARE of the words in
paragraphs (homepages, section fronts and hubs are mostly cards and links).

Every finding is Medium or lower: these are heuristics about shape, and a fix
should make the page clearer for readers, not be written for an AI engine
(§ 19 rules 10c and 10d).

Usage:
    python citability_checker.py page.html --json
    python citability_checker.py --url https://example.com/guide --json
"""

import argparse
import json
import re
import sys

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - requirements.txt installs it
    BeautifulSoup = None

MIN_WORDS = 500
MIN_SECTIONS = 2
MIN_PROSE_SHARE = 0.4           # paragraphs must carry this share of the words: fronts and hubs are lists of links
SECTION_MIN_WORDS = 30          # a heading with less body than this is not a section to judge
LEAD_WINDOW = 60                # words after the H1 within which the lead paragraph must start
LONG_OPENING = 40               # first-sentence length reported (not scored) as a long section opening
PASSAGE_MAX = 350
LONG_PARAGRAPH = 120
LEAD_MIN_WORDS = 15
LONG_UNSECTIONED = 800       # words; a page this long with no sections is judged as one wall

# Component weights of the 0-100 score; they sum to 100.
WEIGHTS = {
    "passage_shape": 45,
    "paragraph_length": 25,
    "heading_structure": 20,
    "specificity": 10,
}

NOISE_TAGS = ("script", "style", "noscript", "template", "svg", "nav", "aside", "form", "button", "iframe")
PAGE_CHROME = ("header", "footer")  # removed only when there is no <main>/<article>: inside one they hold the H1
HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")
PROSE = ("p",)
STRUCTURED = ("ul", "ol", "table", "dl", "pre")
BLOCKS = HEADINGS + PROSE + STRUCTURED + ("blockquote",)

WORD = re.compile(r"[^\W_][\w'’-]*", re.UNICODE)
SENTENCE_END = re.compile(r"[.!?](?:[\"'”’)\]]*)(?=\s|$)")
QUESTION_START = re.compile(
    r"^(what|how|why|when|where|which|who|whose|can|could|does|do|did|is|are|was|were|should|will|would)\b", re.I)
SPECIFIC = re.compile(r"\d|according to|\bsource[sd]?:|\bstudy\b|\bsurvey\b|\breport(?:s|ed)?\b|\bdata\b", re.I)


def words(text: str) -> list:
    return WORD.findall(text or "")


def _clean_text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True))


def _root(soup):
    for tag in NOISE_TAGS:
        for el in soup.find_all(tag):
            el.decompose()
    for attrs in ({"hidden": True}, {"aria-hidden": "true"}, {"role": "navigation"}):
        for el in soup.find_all(attrs=attrs):
            el.decompose()
    main = soup.find("main") or soup.find(attrs={"role": "main"})
    if main is not None:
        return main, "main"
    articles = soup.find_all("article")
    if articles:
        return max(articles, key=lambda a: len(words(_clean_text(a)))), "article"
    for tag in PAGE_CHROME:
        for el in soup.find_all(tag):
            el.decompose()
    return (soup.body or soup), "body"


def _is_layout_table(table) -> bool:
    """A table used for page layout (prose in cells, no header cells), not for data."""
    if table.find("th") is not None:
        return False
    cells = table.find_all("td")
    return bool(cells) and max(len(words(_clean_text(c))) for c in cells) >= 150


def _structured_blocks(root) -> list:
    blocks = []
    for el in root.find_all(list(BLOCKS) + ["div"]):
        if el.find_parent(list(BLOCKS)) is not None:
            continue
        name = el.name
        if name == "div":
            if el.find(list(BLOCKS) + ["div"]) is not None:
                continue
            name = "p"
        text = _clean_text(el)
        count = len(words(text))
        if count:
            blocks.append({"tag": name, "text": text, "words": count,
                           "level": int(name[1]) if name in HEADINGS else None})
    return blocks


def _loose_blocks(root) -> list:
    """Fallback for pages whose prose is not in <p> or leaf <div>: split text at blank lines and <br><br>."""
    for br in root.find_all("br"):
        br.replace_with("\n")
    for heading in root.find_all(list(HEADINGS)):
        heading.replace_with(f"\n\n\x00H{heading.name[1]}\x00{_clean_text(heading)}\n\n")
    for el in root.find_all(["p", "div", "li", "tr", "blockquote", "section", "table"]):
        el.append("\n\n")
    blocks = []
    for chunk in re.split(r"\n\s*\n", root.get_text("")):
        heading = re.match(r"\s*\x00H(\d)\x00(.*)", chunk, re.S)
        text = re.sub(r"\s+", " ", heading.group(2) if heading else chunk).strip()
        count = len(words(text))
        if count:
            level = int(heading.group(1)) if heading else None
            blocks.append({"tag": f"h{level}" if heading else "p", "text": text, "words": count, "level": level})
    return blocks


def extract_blocks(html: str) -> tuple:
    """Top-level content blocks of the main content, in document order.

    Returns (blocks, source, h1_count) where each block is {"tag", "text", "words", "level"}.
    A block nested in another block (a <p> inside an <li> or <blockquote>) is part
    of its parent, and a leaf <div> holding prose directly counts as a paragraph.
    Layout tables are unwrapped. When those blocks miss most of the text (prose
    separated only by <br>), the text is split at blank lines instead. H1s are
    counted across the whole document: many sites put the title outside <main>.
    """
    soup = BeautifulSoup(html, "html.parser")
    h1_count = len(soup.find_all("h1"))
    root, source = _root(soup)
    # Innermost first: unwrapping an outer table's cells must not strip a nested
    # table's rows while leaving its <table> tag around all of the text.
    for table in reversed(root.find_all("table")):
        if _is_layout_table(table):
            for tag in table.find_all(["tbody", "thead", "tr", "td"]) + [table]:
                tag.unwrap()
    blocks = _structured_blocks(root)
    total = len(words(_clean_text(root)))
    if total and sum(b["words"] for b in blocks) < 0.5 * total:
        blocks, source = _loose_blocks(root), source + "+text"
    return blocks, source, h1_count


def _sections(blocks: list) -> tuple:
    """Split blocks at H2-H4 into (intro, sections); each section is {"heading", "level", "body"}."""
    intro, sections, current = [], [], None
    for block in blocks:
        if block["level"] is not None and 2 <= block["level"] <= 4:
            current = {"heading": block["text"], "level": block["level"], "body": []}
            sections.append(current)
        elif block["level"] is not None:
            continue  # h1 / h5 / h6 do not split sections
        elif current is None:
            intro.append(block)
        else:
            current["body"].append(block)
    return intro, sections


def _first_sentence_words(body: list):
    """Words to the end of a section's first sentence, or None when it opens with a list or table
    or has no sentence punctuation to measure."""
    if body[0]["tag"] in STRUCTURED:
        return None
    prose = []
    for block in body:
        if block["tag"] in STRUCTURED:
            break
        prose.append(block["text"])
    text = " ".join(prose)
    for m in SENTENCE_END.finditer(text):
        count = len(words(text[:m.end()]))
        if count >= 4:
            return count
    return None


def _has_lead(blocks: list) -> bool:
    """A paragraph of LEAD_MIN_WORDS+ words starts within the first LEAD_WINDOW words of content.

    Only paragraph words count toward the window. Headings do not, so a summary
    under "Abstract" or "Overview" is a lead; neither do tables, lists and code,
    which on many pages are an infobox or sidebar that sits before the first
    paragraph in the HTML but beside it on screen (Wikipedia).
    """
    seen = 0
    for block in blocks:
        if block["tag"] != "p":
            continue
        if seen > LEAD_WINDOW:
            return False
        if block["tag"] == "p" and block["words"] >= LEAD_MIN_WORDS:
            return True
        seen += block["words"]
    return False


def _headline(text: str, limit: int = 70) -> str:
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def analyze(html: str, url: str = "") -> dict:
    if BeautifulSoup is None:
        return {"url": url, "error": "beautifulsoup4 is not installed (pip install -r requirements.txt)"}
    blocks, source, h1_count = extract_blocks(html)
    # Content before the H1 (breadcrumbs, a table of contents, a series title) is not the page.
    first_h1 = next((i for i, b in enumerate(blocks) if b["level"] == 1), None)
    if first_h1 is not None:
        blocks = blocks[first_h1 + 1:]
    intro, all_sections = _sections(blocks)
    body_words = lambda s: sum(b["words"] for b in s["body"])  # noqa: E731
    sections = [s for s in all_sections if body_words(s) >= SECTION_MIN_WORDS]
    paragraphs = [b for b in blocks if b["tag"] == "p"]
    total_words = sum(b["words"] for b in blocks if b["level"] is None)
    prose_share = sum(p["words"] for p in paragraphs) / total_words if total_words else 0.0
    headings = [b for b in blocks if b["level"] is not None]
    questions = [h for h in headings if h["level"] >= 2 and (h["text"].rstrip().endswith("?")
                                                             or QUESTION_START.match(h["text"]))]

    result = {
        "url": url,
        "content_source": source,
        "words": total_words,
        "sections": len(sections),
        "paragraphs": len(paragraphs),
        "prose_share": round(prose_share, 2),
        "question_headings": {"count": len(questions), "of": sum(1 for h in headings if h["level"] >= 2)},
        "applicable": True,
        "score": None,
        "components": {},
        "issues": [],
    }
    if total_words >= MIN_WORDS and prose_share < MIN_PROSE_SHARE:
        result["applicable"] = False
        result["reason"] = (
            f"Only {round(100 * prose_share)}% of the {total_words} words are in paragraphs: the page is mostly "
            f"lists, cards or links (a homepage, section front or hub), not article-style content."
        )
        return result
    if len(sections) < MIN_SECTIONS and total_words >= LONG_UNSECTIONED:
        # A long page with no section headings is article-style with weak structure,
        # not "not applicable": judge it as one section.
        body = [b for b in blocks if b["level"] is None]
        sections = [{"heading": "(whole page, no section headings)", "level": 2, "body": body}]
        result["sections"] = 0
    elif total_words < MIN_WORDS or len(sections) < MIN_SECTIONS:
        result["applicable"] = False
        result["reason"] = (
            f"{total_words} words of main content in {len(sections)} section(s); the check scores article-style "
            f"pages with at least {MIN_WORDS} words in {MIN_SECTIONS}+ sections (or {LONG_UNSECTIONED}+ words "
            f"without section headings). If the page builds its content with JavaScript, rerun on rendered HTML."
        )
        return result

    components = {}

    lead = _has_lead(blocks)
    result["lead"] = {"present": lead}

    long_openings = [(s, n) for s in sections if (n := _first_sentence_words(s["body"])) and n > LONG_OPENING]
    result["long_openings"] = {"count": len(long_openings), "of": len(sections),
                               "examples": [f"{_headline(s['heading'])} ({n} words)" for s, n in long_openings[:3]]}

    # Passage shape.
    walls = [s for s in sections if body_words(s) > PASSAGE_MAX
             and not any(b["tag"] in STRUCTURED for b in s["body"])]
    components["passage_shape"] = {"score": round(100 * (1 - len(walls) / len(sections))), "walls": len(walls),
                                   "examples": [f"{_headline(s['heading'])} ({body_words(s)} words)" for s in walls[:3]]}

    # Paragraph length.
    long_paragraphs = [p for p in paragraphs if p["words"] > LONG_PARAGRAPH]
    components["paragraph_length"] = {
        "score": round(100 * (1 - len(long_paragraphs) / len(paragraphs))) if paragraphs else 0,
        "long": len(long_paragraphs), "of": len(paragraphs),
        "examples": [_headline(" ".join(words(p["text"])[:12])) + f" ({p['words']} words)" for p in long_paragraphs[:3]],
    }

    # Heading structure.
    skips = []
    previous = None
    for h in headings:
        if previous is not None and h["level"] > previous + 1:
            skips.append(f"H{previous} → H{h['level']} at \"{_headline(h['text'], 50)}\"")
        previous = h["level"]
    components["heading_structure"] = {"score": (50 if h1_count == 1 else 0) + (50 if not skips else 0),
                                       "h1": h1_count, "skipped_levels": skips[:3]}

    # Specificity.
    substantive = [p for p in paragraphs if p["words"] >= 20]
    specific = [p for p in substantive if SPECIFIC.search(p["text"])]
    ratio = len(specific) / len(substantive) if substantive else 0
    components["specificity"] = {"score": min(100, round(200 * ratio)), "specific": len(specific),
                                 "of": len(substantive)}

    result["components"] = components
    result["score"] = round(sum(components[k]["score"] * w for k, w in WEIGHTS.items()) / sum(WEIGHTS.values()))
    result["issues"] = _issues(components, lead)
    return result


def _issues(c: dict, lead: bool) -> list:
    issues = []
    ps = c["passage_shape"]
    if ps["walls"]:
        issues.append({
            "severity": "medium",
            "finding": f"{ps['walls']} section(s) run over {PASSAGE_MAX} words of prose with no list, table "
                       f"or subheading",
            "evidence": "Sections: " + "; ".join(ps["examples"]),
            "fix": "Split each into subsections under descriptive headings, or move steps and comparisons into "
                   "lists and tables.",
            "falsifiability": "If readers finish these sections (scroll depth, time on section) at the page "
                              "average, their length is not hurting them.",
            "leading_indicator": "Rerun citability_checker.py: no sections over the prose limit.",
        })
    if not lead:
        issues.append({
            "severity": "low",
            "finding": "The page does not open with a summary paragraph",
            "evidence": f"No paragraph of {LEAD_MIN_WORDS}+ words starts within the first {LEAD_WINDOW} words "
                        f"after the H1.",
            "fix": "Add a two- or three-sentence opening that states what the page answers.",
            "falsifiability": "If the page already earns its target snippet or AI citation without an opening "
                              "summary, the lead is not the constraint.",
            "leading_indicator": "Rerun citability_checker.py: lead present.",
        })
    pl = c["paragraph_length"]
    if pl["long"] and pl["score"] < 80:
        issues.append({
            "severity": "low",
            "finding": f"{pl['long']} of {pl['of']} paragraphs exceed {LONG_PARAGRAPH} words",
            "evidence": "Paragraphs: " + "; ".join(pl["examples"]),
            "fix": "Break long paragraphs into two to four sentences, one idea each.",
            "leading_indicator": "Rerun citability_checker.py: paragraph length score 80+.",
        })
    hs = c["heading_structure"]
    if hs["skipped_levels"]:
        issues.append({
            "severity": "low",
            "finding": "Heading levels skip",
            "evidence": "; ".join(hs["skipped_levels"]),
            "fix": "Nest headings in order (H2 before H3) so the outline matches the content structure.",
            "leading_indicator": "Rerun citability_checker.py: no skipped levels.",
        })
    return issues


def fetch(url: str) -> str:
    resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (compatible; UltimateSEO/1.8)"})
    resp.raise_for_status()
    return resp.text


def main():
    parser = argparse.ArgumentParser(description="Citability and structure check for one page (GEO § 3)")
    parser.add_argument("file", nargs="?", help="Saved HTML file")
    parser.add_argument("--url", "-u", help="Fetch and check this URL")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if args.url:
        try:
            html = fetch(args.url)
        except requests.RequestException as exc:
            print(json.dumps({"url": args.url, "error": f"fetch failed: {exc}"}) if args.json
                  else f"Error: fetch failed: {exc}", file=sys.stdout if args.json else sys.stderr)
            sys.exit(1)
    elif args.file:
        with open(args.file, encoding="utf-8", errors="ignore") as fh:
            html = fh.read()
    else:
        parser.error("Provide an HTML file or --url")

    result = analyze(html, args.url or "")
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get("error"):
            print(f"Error: {result['error']}")
        elif not result["applicable"]:
            print(f"Not applicable: {result['reason']}")
        else:
            print(f"Citability score: {result['score']}/100 ({result['words']} words, {result['sections']} sections)")
            for name, comp in result["components"].items():
                print(f"  {name}: {comp['score']}")
            for issue in result["issues"]:
                print(f"  [{issue['severity']}] {issue['finding']}")
    sys.exit(1 if result.get("error") else 0)


if __name__ == "__main__":
    main()
