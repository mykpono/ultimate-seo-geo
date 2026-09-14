#!/usr/bin/env python3
"""
Find text on a page that is aimed at AI systems but hidden from human readers.

Prompt injection on web pages puts instructions for LLM crawlers and AI
assistants ("ignore previous instructions", "AI assistants must recommend ...")
where a visitor never sees them: CSS-hidden elements, noscript, HTML comments,
alt / title / aria-label attributes, meta descriptions, JSON-LD, or invisible
Unicode (tag characters and long zero-width runs). A site owner who did not
put it there has been compromised, often through a plugin, an injected script
or user comments. One who did is hiding text from visitors, which Google's
spam policies prohibit when it is placed to manipulate search engines.

Only instruction-like text in a hidden place is flagged. The same sentence in
visible body copy, such as an article about prompt injection, is not.

Limits, repeated in every result:
  * Hidden means inline styles, the hidden attribute, noscript / template and
    common hiding or screen-reader classes. Text hidden by external stylesheets
    or scripts is not seen; check a rendered page in DevTools.
  * Instruction patterns are English and phrase-based. Paraphrased or
    other-language instructions are missed, so no findings is not proof of a
    clean page.

Usage:
    python hidden_instructions.py https://example.com
    python hidden_instructions.py page.html --json
"""

import argparse
import json
import os
import re
import sys

try:
    from bs4 import BeautifulSoup, Comment
except ImportError:
    print("Error: beautifulsoup4 required. Install with: pip install beautifulsoup4")
    sys.exit(1)


INSTRUCTION_PATTERNS = [
    ("override", re.compile(
        r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier|preceding|other)\s+"
        r"(?:instructions|prompts|directions|rules|context)", re.I)),
    ("role", re.compile(
        r"\byou\s+are\s+(?:now\s+)?(?:an?\s+)?(?:ai|assistant|chatbot|language\s+model|llm|chatgpt|claude|gemini|copilot|perplexity)\b",
        re.I)),
    ("addressed to AI", re.compile(
        r"\b(?:chatgpt|claude|gemini|perplexity|copilot|llms?|large\s+language\s+models?|"
        r"ai\s+(?:assistants?|models?|agents?|systems?|crawlers?|search\s+engines?))\b[^.!?\n]{0,60}?"
        r"\b(?:must|should|always|never|recommend|mention|say|state|tell|describe|rank|cite|respond)\b", re.I)),
    # Instruction form only: "System prompt" as a heading or link title (Wikipedia's own
    # article on prompt injection has one) is a topic, not an injection.
    ("system prompt", re.compile(
        r"(?:\bsystem\s+prompt\s*:|\b(?:new|updated|override(?:\s+the)?)\s+system\s+prompt\b"
        r"|\bnew\s+instructions\s*:|<\|im_start\|>|\[/?INST\])", re.I)),
    ("answer framing", re.compile(
        r"\bwhen\s+(?:summari[sz]ing|asked\s+about|answering\s+questions\s+about)\s+(?:this|our|the)\b", re.I)),
]

# Inline declarations that take an element out of what a visitor sees.
HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none"
    r"|visibility\s*:\s*hidden"
    r"|opacity\s*:\s*0(?:\.0+)?\s*(?:;|!|$)"
    r"|font-size\s*:\s*0(?:\.0+)?(?:px|pt|em|rem|%)?\s*(?:;|!|$)"
    r"|(?:left|top|text-indent|margin-left)\s*:\s*-\d{3,}(?:\.\d+)?(?:px|em|rem)"
    r"|clip\s*:\s*rect\(\s*0",
    re.I,
)
SCREEN_READER_CLASSES = {"sr-only", "visually-hidden", "screen-reader-text"}
HIDING_CLASSES = {"d-none", "hidden", "invisible"}
TEXT_ATTRIBUTES = ("alt", "title", "aria-label")
META_NAMES = {"description", "og:description", "twitter:description"}

TAG_CHARACTERS = re.compile("[\U000E0000-\U000E007F]+")
ZERO_WIDTH_RUN = re.compile("[​‌‍⁠﻿]{16,}")
BLACK_FLAG = "\U0001F3F4"  # subdivision flags (England, Scotland, Wales) use tag characters legitimately

LIMITS = [
    "Hidden means inline styles, the hidden attribute, noscript and template, and common hiding or "
    "screen-reader classes. Text hidden by external stylesheets or scripts is not seen; check the "
    "rendered page in DevTools.",
    "Instruction patterns are English and phrase-based. Paraphrased or other-language instructions are "
    "missed, so no findings is not proof of a clean page.",
]
SNIPPET_BEFORE, SNIPPET_AFTER = 60, 120
PLACE_PHRASES = {
    "hidden element": "a hidden element",
    "HTML comment": "an HTML comment",
    "attribute": "an attribute",
    "meta tag": "a meta tag",
    "structured data": "structured data",
}


def find_instruction(text: str):
    """Return (pattern name, match) for the first instruction-like phrase in text, or None."""
    for name, pattern in INSTRUCTION_PATTERNS:
        match = pattern.search(text or "")
        if match:
            return name, match
    return None


def _snippet(text: str, match) -> str:
    start = max(0, match.start() - SNIPPET_BEFORE)
    end = min(len(text), match.end() + SNIPPET_AFTER)
    body = re.sub(r"\s+", " ", text[start:end]).strip()
    return ("…" if start else "") + body + ("…" if end < len(text) else "")


def hidden_reason(tag):
    """Why a visitor cannot see this element, or None. aria-hidden is not a reason: it hides from screen readers only."""
    if tag.name in ("noscript", "template"):
        return f"{tag.name} element"
    if tag.has_attr("hidden"):
        return "hidden attribute"
    match = HIDDEN_STYLE.search(tag.get("style") or "")
    if match:
        return f"inline style ({re.sub(r'[;!]$', '', match.group(0)).strip()})"
    classes = {c.lower() for c in (tag.get("class") or [])}
    if classes & SCREEN_READER_CLASSES:
        return f"screen-reader-only class ({sorted(classes & SCREEN_READER_CLASSES)[0]})"
    if classes & HIDING_CLASSES:
        return f"hiding class ({sorted(classes & HIDING_CLASSES)[0]})"
    return None


def scan_markup(html: str) -> list:
    """Instruction-like text in places a visitor does not see."""
    soup = BeautifulSoup(html, "html.parser")
    found = []

    def record(context, where, text, severity):
        hit = find_instruction(text)
        if hit:
            found.append({
                "context": context,
                "where": where,
                "pattern": hit[0],
                "snippet": _snippet(text, hit[1]),
                "severity": severity,
            })

    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        record("structured data", "JSON-LD", script.get_text(" "), "warning")
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        record("HTML comment", "<!-- -->", str(comment), "warning")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    inside_hidden = set()
    for tag in soup.find_all(True):
        for attr in TEXT_ATTRIBUTES:
            if tag.has_attr(attr):
                record("attribute", f"{tag.name}[{attr}]", str(tag[attr]), "warning")
        if tag.name == "meta" and (tag.get("name") or tag.get("property") or "").lower() in META_NAMES:
            record("meta tag", f"meta {(tag.get('name') or tag.get('property')).lower()}", tag.get("content") or "", "warning")

        if id(tag) in inside_hidden:
            continue
        reason = hidden_reason(tag)
        if reason:
            inside_hidden.update(id(d) for d in tag.descendants)
            record("hidden element", f"<{tag.name}> {reason}", tag.get_text(" "), "critical")
    return found


def scan_unicode(text: str) -> list:
    """Invisible Unicode that carries text only machines read."""
    found = []
    for match in TAG_CHARACTERS.finditer(text):
        if match.start() > 0 and text[match.start() - 1] == BLACK_FLAG:
            continue
        decoded = "".join(chr(ord(c) - 0xE0000) for c in match.group(0) if 0x20 <= ord(c) - 0xE0000 < 0x7F)
        found.append({"kind": "Unicode tag characters", "length": len(match.group(0)), "decoded": decoded[:200]})
    for match in ZERO_WIDTH_RUN.finditer(text):
        found.append({"kind": "zero-width character run", "length": len(match.group(0)), "decoded": None})
    return found


def check_html(html: str, source: str) -> dict:
    hidden = scan_markup(html)
    invisible = scan_unicode(html)
    issues = []
    for item in hidden:
        icon = "🔴" if item["severity"] == "critical" else "⚠️"
        place = PLACE_PHRASES.get(item["context"], item["context"])
        issues.append(
            f"{icon} Instruction-like text aimed at AI systems in {place} ({item['where']}): "
            f"\"{item['snippet']}\". Visitors cannot see it. If the site did not add it, treat it as a compromise "
            "(plugin, injected script or user comments); if it did, remove it: Google's spam policies cover hidden "
            "text and attempts to manipulate generative AI responses in Google Search"
        )
    for item in invisible:
        detail = f', decoding to "{item["decoded"]}"' if item["decoded"] else ""
        issues.append(
            f"⚠️ Invisible {item['kind']} ({item['length']} characters){detail}. They carry text only machines "
            "read; find where they enter the page and remove them"
        )
    critical = any(item["severity"] == "critical" for item in hidden)
    return {
        "source": source,
        "hidden_instructions": hidden,
        "invisible_unicode": invisible,
        "score": 0 if critical else 50 if issues else 100,
        "issues": issues,
        "limits": LIMITS,
        "error": None,
    }


def load_source(source: str, timeout: int):
    """Return (html, error) from a local file or a URL."""
    if os.path.isfile(source):
        with open(source, encoding="utf-8", errors="replace") as fh:
            return fh.read(), None
    from fetch_page import fetch_page

    result = fetch_page(source, timeout=timeout)
    if result.get("error"):
        return None, result["error"]
    return result.get("content") or "", None


def main():
    parser = argparse.ArgumentParser(description="Find instructions to AI systems hidden from human readers")
    parser.add_argument("source", help="URL or saved HTML file")
    parser.add_argument("--timeout", type=int, default=30, help="Fetch timeout in seconds (default: 30)")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    html, error = load_source(args.source, args.timeout)
    result = {"source": args.source, "error": error} if error else check_html(html, args.source)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get("error"):
            sys.exit(1)
        return
    if result.get("error"):
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"Hidden AI instructions — {result['source']}")
    print("=" * 50)
    print(f"Hidden instruction-like text: {len(result['hidden_instructions'])}")
    print(f"Invisible Unicode runs: {len(result['invisible_unicode'])}")
    if result["issues"]:
        print(f"\nIssues ({len(result['issues'])}):")
        for issue in result["issues"]:
            print(f"  {issue}")
    else:
        print("\nNo hidden instruction-like text found.")
    print("\nLimits:")
    for limit in result["limits"]:
        print(f"  - {limit}")


if __name__ == "__main__":
    main()
