#!/usr/bin/env python3
"""Visible-HTML parity for FAQ answer text.

FAQ answer text that exists in JSON-LD but not in the rendered HTML satisfies a
parser while the user — and the AI crawler — see nothing. This is a
specialisation of `references/procedures/03-geo-ai-search.md` step 4 ("Key
content absent from raw HTML = invisible to AI bots") and feeds the Citability
dimension of the GEO Score.

Deliberately dependency-free: `validate_schema.py` is regex/json only and must
not grow a BeautifulSoup dependency.

Comparison is containment, not equality, over normalised text. JSON-LD
`acceptedAnswer.text` routinely carries `<p>` tags, HTML entities and `&nbsp;`
that the rendered DOM does not, so raw equality reports false misses.
"""

import html
import re

import jsonld
from typing import List

# Answers shorter than this are skipped: a handful of characters can appear
# incidentally anywhere in the page and would make containment meaningless.
MIN_ANSWER_CHARS = 25

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
)


def normalize(text: str) -> str:
    """Strip tags, unescape entities, collapse whitespace, casefold.

    Order matters: tags are stripped before entities are unescaped so that a
    literal `&lt;p&gt;` in the source survives as text rather than being
    unescaped into a tag and then deleted.
    """
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    # `\s` covers the U+00A0 that `&nbsp;` unescapes to.
    return re.sub(r"\s+", " ", text).strip().casefold()


def visible_text(html_content: str) -> str:
    """Normalised visible text of a page, with script/style contents removed.

    JSON-LD lives inside <script>, so it must be stripped first — otherwise the
    markup would trivially "contain" its own answer text and never flag.
    """
    return normalize(_SCRIPT_STYLE_RE.sub(" ", html_content or ""))


def _iter_questions(schema_obj):
    """Yield Question nodes from a FAQPage `mainEntity`, list or single."""
    if not jsonld.is_type(schema_obj, "FAQPage"):
        return
    entity = schema_obj.get("mainEntity")
    if isinstance(entity, dict):
        entity = [entity]
    if not isinstance(entity, list):
        return
    for node in entity:
        if jsonld.is_type(node, "Question"):
            yield node


def _answer_text(question) -> str:
    answer = question.get("acceptedAnswer") or question.get("suggestedAnswer")
    if isinstance(answer, list):
        answer = answer[0] if answer else None
    if isinstance(answer, dict):
        return answer.get("text") or ""
    if isinstance(answer, str):
        return answer
    return ""


def missing_answers(schema_obj, page_visible_text: str) -> List[str]:
    """Return question names whose answer text is absent from the rendered HTML.

    `page_visible_text` must already be normalised via `visible_text()`.
    """
    missing = []
    for question in _iter_questions(schema_obj):
        answer = normalize(_answer_text(question))
        if len(answer) < MIN_ANSWER_CHARS:
            continue
        if answer not in page_visible_text:
            name = normalize(question.get("name") or "") or "(unnamed question)"
            missing.append(question.get("name") or name)
    return missing
