#!/usr/bin/env python3
"""Shape-normalising helpers for JSON-LD.

`@type` may be a string or a list, and one `<script type="application/ld+json">`
block may hold a single object or a top-level array of them. Both shapes are
valid, both appear on real sites, and every audit script that assumed the single
form failed on the other — some by raising `TypeError`/`AttributeError`, the
more dangerous ones by silently reporting nothing and passing the page as clean.

Each script had grown its own copy of the same fix (`_type_names`, `_is_type`,
`_declares_type`, `_schema_nodes`). This is the one implementation they share,
so the next shape that needs handling is handled once.

Deliberately dependency-free, stdlib only: `faq_parity.py` and
`validate_schema.py` are regex/json by design and must not acquire a
BeautifulSoup dependency through the back door.

Note on scope: this module knows about JSON-LD *shapes* only. Which types are
retired or no longer produce rich results stays in each script as a
module-level constant, pinned to `references/schema-types.md` by
`tests/test_schema_status_parity.py` (decision D-017).
"""

import re
from typing import List


def type_names(value) -> List[str]:
    """Return an `@type` value as a list of type strings.

    Accepts the string form, the list form, and anything else (returns empty).
    Non-string members of a list are dropped rather than coerced — an `@type`
    of `["Article", {"@id": "..."}]` yields `["Article"]`.
    """
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def is_type(node, wanted: str) -> bool:
    """True when `node` declares `wanted`, as a string or inside a list `@type`.

    `["WebPage", "FAQPage"]` is the ordinary shape for a page that is both, so
    an `!=` comparison against the raw value skips exactly the pages that carry
    the markup being looked for.
    """
    if not isinstance(node, dict):
        return False
    return wanted in type_names(node.get("@type"))


def nodes(data) -> list:
    """Every schema node carried by one parsed JSON-LD block.

    A block may hold a single object or a top-level array of objects. Calling
    `.get()` straight on the array form raises `AttributeError` and kills the
    parse for the whole page.
    """
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def declares_type(html: str, wanted: str) -> bool:
    """True when raw HTML declares `wanted` as a JSON-LD `@type`, either shape.

    Matches `"@type": "LocalBusiness"` and `"@type": ["LocalBusiness", "Store"]`.
    For callers that scan raw HTML rather than parsed JSON; prefer `is_type()`
    where a parsed node is available.
    """
    escaped = re.escape(wanted)
    pattern = r'"@type"\s*:\s*(?:"%s"|\[[^\]]*"%s")' % (escaped, escaped)
    return bool(re.search(pattern, html or "", re.I))
