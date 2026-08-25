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

Note on scope: this module knows about JSON-LD *shapes*, plus the one piece of
schema.org taxonomy two scripts both need — the LocalBusiness subtype tree,
which is a fixed fact about the vocabulary rather than a judgement about it.
Which types are retired or no longer produce rich results is a judgement, moves
with Google's announcements, and stays in each script as a module-level
constant, pinned to `references/schema-types.md` by
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


# --- schema.org LocalBusiness hierarchy -------------------------------------
#
# A page marked up as `Restaurant` or `Dentist` *is* marked up as a
# LocalBusiness; schema.org's own guidance is to use the most specific subtype
# available. Matching the literal string "LocalBusiness" and nothing else told
# every correctly-marked-up local business, at high severity, to add the schema
# it already had.
#
# Grouped by parent to stay checkable against https://schema.org/LocalBusiness.
# Lowercase throughout: `@type` casing is conventional, not guaranteed.

_LOCAL_BUSINESS_TREE = {
    # Direct subtypes of LocalBusiness.
    "": (
        "localbusiness", "animalshelter", "archiveorganization",
        "automotivebusiness", "childcare", "dentist", "drycleaningorlaundry",
        "emergencyservice", "employmentagency", "entertainmentbusiness",
        "financialservice", "foodestablishment", "governmentoffice",
        "healthandbeautybusiness", "homeandconstructionbusiness",
        "internetcafe", "legalservice", "library", "lodgingbusiness",
        "medicalbusiness", "professionalservice", "radiostation",
        "realestateagent", "recyclingcenter", "selfstorage", "shoppingcenter",
        "sportsactivitylocation", "store", "televisionstation",
        "touristinformationcenter", "travelagency",
    ),
    "automotivebusiness": (
        "autobodyshop", "autodealer", "autopartsstore", "autorental",
        "autorepair", "autowash", "gasstation", "motorcycledealer",
        "motorcyclerepair",
    ),
    "emergencyservice": ("firestation", "hospital", "policestation"),
    "entertainmentbusiness": (
        "adultentertainment", "amusementpark", "artgallery", "casino",
        "comedyclub", "movietheater", "nightclub",
    ),
    "financialservice": (
        "accountingservice", "automatedteller", "bankorcreditunion",
        "insuranceagency",
    ),
    "foodestablishment": (
        "bakery", "barorpub", "brewery", "cafeorcoffeeshop", "distillery",
        "fastfoodrestaurant", "icecreamshop", "restaurant", "winery",
    ),
    "governmentoffice": ("postoffice",),
    "healthandbeautybusiness": (
        "beautysalon", "dayspa", "hairsalon", "healthclub", "nailsalon",
        "tattooparlor",
    ),
    "homeandconstructionbusiness": (
        "electrician", "generalcontractor", "housepainter", "hvacbusiness",
        "locksmith", "movingcompany", "plumber", "roofingcontractor",
    ),
    "legalservice": ("attorney", "notary"),
    "lodgingbusiness": (
        "bedandbreakfast", "campground", "hostel", "hotel", "motel", "resort",
        "skiresort",
    ),
    "medicalbusiness": (
        "communityhealth", "covidtestingfacility", "dermatology",
        "dietnutrition", "emergency", "geriatric", "gynecologic",
        "individualphysician", "medicalclinic", "midwifery", "nursing",
        "obstetric", "optician", "optometric", "otolaryngologic", "pediatric",
        "pharmacy", "physician", "physiciansoffice", "physiotherapy",
        "plasticsurgery", "podiatric", "primarycare", "psychiatric",
        "publichealth", "veterinarycare",
    ),
    "sportsactivitylocation": (
        "bowlingalley", "exercisegym", "golfcourse", "publicswimmingpool",
        "sportsclub", "stadiumorarena", "tenniscomplex",
    ),
    "store": (
        "bikestore", "bookstore", "clothingstore", "computerstore",
        "conveniencestore", "departmentstore", "electronicsstore", "florist",
        "furniturestore", "gardenstore", "grocerystore", "hardwarestore",
        "hobbyshop", "homegoodsstore", "jewelrystore", "liquorstore",
        "mensclothingstore", "mobilephonestore", "movierentalstore",
        "musicstore", "officeequipmentstore", "outletstore", "pawnshop",
        "petstore", "shoestore", "sportinggoodsstore", "tireshop", "toystore",
        "wholesalestore",
    ),
}

#: Every schema.org type that is a LocalBusiness or one of its subtypes,
#: lowercased. `Organization` is deliberately absent: it is LocalBusiness's
#: *parent*, and treating it as local would flag every company on the web.
LOCAL_BUSINESS_TYPES = frozenset(
    name for group in _LOCAL_BUSINESS_TREE.values() for name in group
)

#: Names that are *not* schema.org types but appear on real pages, mapped to
#: what the author meant. `maps_checker.py` matched all five before the taxonomy
#: moved here; keeping them means widening subtype coverage cannot narrow
#: anything. Held apart from LOCAL_BUSINESS_TYPES so the set above stays an
#: honest mirror of https://schema.org/LocalBusiness.
LOCAL_BUSINESS_ALIASES = {
    "autobody": "AutoBodyShop",
    "barorsalon": "BarOrPub",
    "cafe": "CafeOrCoffeeShop",
    "gym": "ExerciseGym",
    "selfstorge": "SelfStorage",
}

_LOCAL_BUSINESS_MATCH = LOCAL_BUSINESS_TYPES | frozenset(LOCAL_BUSINESS_ALIASES)

_TYPE_VALUE_RE = re.compile(r'"@type"\s*:\s*(?:"([^"]*)"|\[([^\]]*)\])', re.I)
_QUOTED_RE = re.compile(r'"([^"]*)"')


def declared_types(html: str) -> List[str]:
    """Every `@type` named in raw HTML, in document order, deduped case-insensitively.

    Reads both shapes — `"@type": "Restaurant"` and `"@type": ["WebPage",
    "Restaurant"]` — and returns the names as written, so callers can quote the
    site's own casing back at the user.
    """
    found, seen = [], set()
    for single, listed in _TYPE_VALUE_RE.findall(html or ""):
        for name in ([single] if single else _QUOTED_RE.findall(listed)):
            name = name.strip()
            key = name.lower()
            if key and key not in seen:
                seen.add(key)
                found.append(name)
    return found


def local_business_types_in(html: str) -> List[str]:
    """LocalBusiness types declared in raw HTML, most-specific-first is not implied.

    Empty for a publisher or SaaS page, which is what makes it safe to drive a
    "you are missing LocalBusiness schema" finding off.
    """
    return [t for t in declared_types(html) if t.lower() in _LOCAL_BUSINESS_MATCH]


def is_local_business(node) -> bool:
    """True when a parsed node declares LocalBusiness or any of its subtypes."""
    if not isinstance(node, dict):
        return False
    return any(t.lower() in _LOCAL_BUSINESS_MATCH for t in type_names(node.get("@type")))
