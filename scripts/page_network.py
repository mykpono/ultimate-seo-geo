#!/usr/bin/env python3
"""
What a rendered page calls over the network, and which of those calls anyone can make.

A raw-HTML crawl sees the page's markup, not the requests its scripts send. On the
Improvado v4.1 audit, the site's AI sandbox widget sent visitors' questions straight
to a public agent endpoint from the browser, with no key and a CORS policy that let
any site call it; the crawl-based report saw only the llms.txt line that named the
endpoint. This script renders each page with Playwright, records every request, and:

  * finds first-party API calls (xhr/fetch to the site's own domain or subdomains,
    tag-manager proxies and beacons excluded) and whether they carry an auth header;
  * checks each one's CORS: the header on the page's own response, then a harmless
    OPTIONS preflight from a foreign origin (--no-probe skips it). An endpoint that
    answers any origin and needs no key can be called by any website or script,
    at the site's cost;
  * lists the third-party hosts and the tracking vendors the page loads, the tag
    weight behind a slow Interaction to Next Paint;
  * with --llms-txt, probes the API endpoints the site advertises in /llms.txt the
    same way (OPTIONS and GET only, never a POST).

    python scripts/page_network.py https://example.com/ https://example.com/pricing --json
    python scripts/page_network.py https://example.com/ --llms-txt --json

Recorded URLs drop their query strings (tracker hits carry emails and ids), and no
header value is kept except CORS and content type. Needs Playwright:
pip install playwright && playwright install chromium.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import urljoin, urlsplit

import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from render_page import render_url, strip_query  # noqa: E402
from url_safety import validate_url  # noqa: E402

PROBE_ORIGIN = "https://cors-probe.invalid"
MAX_PROBES = 20
TAG_LOAD_VENDORS = 10
TAG_LOAD_HOSTS = 30

# First-party paths that are analytics plumbing, not an API: server-side tag-manager
# proxies, Cloudflare's own endpoints, RUM beacons, and self-hosted analytics ingestion
# (PostHog's /e/, /flags/, /i/v0/e/ on posthog.com are public by design).
FIRST_PARTY_PLUMBING = re.compile(
    r"^/(_tag|gtm|sgtm|tag|tags|metrics|cdn-cgi|_vercel/(insights|speed-insights)|rum|beacon|g/collect|collect|j/collect|mp/collect"
    r"|e|i/v\d+/(e|logs)|flags|decide|batch|capture|ingest|engage|s)(/|$)",
    re.I)
# Only a call that does work can be abused at the site's cost: CORS open on a GET of public data
# (Gatsby page-data, a Next.js prefetch, a consent script) is how static sites work.
WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")

# Tracking and tag vendors by host suffix. A host not listed here is reported as an
# unrecognised third party, never guessed.
VENDORS = {
    "google-analytics.com": "Google Analytics", "analytics.google.com": "Google Analytics",
    "googletagmanager.com": "Google Tag Manager", "doubleclick.net": "Google Ads", "googleadservices.com": "Google Ads",
    "googlesyndication.com": "Google Ads", "google.com/ccm": "Google Ads", "google.com/rmkt": "Google Ads",
    "google.com/pagead": "Google Ads", "facebook.net": "Meta", "facebook.com": "Meta", "connect.facebook.net": "Meta",
    "ads.linkedin.com": "LinkedIn", "snap.licdn.com": "LinkedIn", "px.ads.linkedin.com": "LinkedIn",
    "reddit.com": "Reddit", "redditstatic.com": "Reddit", "clarity.ms": "Microsoft Clarity", "bat.bing.com": "Microsoft Ads",
    "bing.com": "Microsoft Ads", "hs-scripts.com": "HubSpot", "hs-analytics.net": "HubSpot", "hs-banner.com": "HubSpot",
    "hubspot.com": "HubSpot", "hsforms.com": "HubSpot", "hsforms.net": "HubSpot", "hscollectedforms.net": "HubSpot",
    "hotjar.com": "Hotjar", "hotjar.io": "Hotjar", "visualwebsiteoptimizer.com": "VWO", "wingify.com": "VWO",
    "segment.com": "Segment", "segment.io": "Segment", "intercom.io": "Intercom", "intercomcdn.com": "Intercom",
    "drift.com": "Drift", "driftt.com": "Drift", "twitter.com": "X", "ads-twitter.com": "X", "t.co": "X",
    "tiktok.com": "TikTok", "bzr.openai.com": "OpenAI Ads", "bzrcdn.openai.com": "OpenAI Ads",
    "quora.com": "Quora", "taboola.com": "Taboola", "outbrain.com": "Outbrain", "criteo.com": "Criteo",
    "adroll.com": "AdRoll", "6sc.co": "6sense", "demandbase.com": "Demandbase", "zoominfo.com": "ZoomInfo",
    "clearbit.com": "Clearbit", "mixpanel.com": "Mixpanel", "amplitude.com": "Amplitude", "heap.io": "Heap",
    "heapanalytics.com": "Heap", "fullstory.com": "FullStory", "posthog.com": "PostHog", "plausible.io": "Plausible",
    "cookielaw.org": "OneTrust", "onetrust.com": "OneTrust", "cookiebot.com": "Cookiebot", "sentry.io": "Sentry",
    "sentry-cdn.com": "Sentry", "newrelic.com": "New Relic", "nr-data.net": "New Relic",
    "hubapi.com": "HubSpot", "hsadspixel.net": "HubSpot", "hscta.net": "HubSpot", "apollo.io": "Apollo",
    "midbound.ai": "Midbound",
}
# Hosts that serve fonts, media and code rather than track: listed apart, never counted as vendors.
INFRASTRUCTURE = ("fonts.googleapis.com", "fonts.gstatic.com", "gstatic.com", "cdnjs.cloudflare.com", "jsdelivr.net",
                  "unpkg.com", "cloudflarestream.com", "cloudfront.net", "amazonaws.com", "akamaized.net", "fastly.net",
                  "ytimg.com", "youtube.com", "youtube-nocookie.com", "vimeo.com", "vimeocdn.com", "website-files.com",
                  "googleapis.com", "recaptcha.net", "hcaptcha.com", "stripe.com", "jquery.com", "bootstrapcdn.com")
MULTI_PART_SUFFIXES = {"co", "com", "org", "net", "ac", "gov", "edu", "ne", "or"}


def site_of(host: str) -> str:
    """Registrable domain, by a short heuristic: example.co.uk, not co.uk; example.com for a.b.example.com."""
    labels = (host or "").lower().strip(".").split(".")
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in MULTI_PART_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def vendor_of(url: str) -> str | None:
    """Vendor for a request URL. A key with a path ("google.com/ccm") matches that host and path prefix."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    for key, name in VENDORS.items():
        suffix, _, path = key.partition("/")
        if (host == suffix or host.endswith("." + suffix)) and (not path or (parts.path or "").startswith("/" + path)):
            return name
    return None


def _is_infrastructure(host: str) -> bool:
    return any(host == s or host.endswith("." + s) for s in INFRASTRUCTURE)


def is_api_call(entry: dict, page_site: str) -> bool:
    parts = urlsplit(entry["url"])
    if entry.get("resource_type") not in ("xhr", "fetch"):
        return False
    if site_of(parts.hostname or "") != page_site:
        return False
    return not FIRST_PARTY_PLUMBING.match(parts.path or "/")


def probe_cors(url: str, method: str = "POST", timeout: int = 10) -> dict:
    """A CORS preflight from a foreign origin. OPTIONS only: it runs no handler on a correct server."""
    safe = validate_url(url)
    if not safe.ok:
        return {"error": f"URL safety check failed: {safe.reason}"}
    import requests
    try:
        r = requests.options(url, timeout=timeout, allow_redirects=False, headers={
            "Origin": PROBE_ORIGIN, "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type"})
    except requests.RequestException as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    return {"status": r.status_code,
            "allow_origin": r.headers.get("access-control-allow-origin"),
            "allow_credentials": r.headers.get("access-control-allow-credentials"),
            "allow_methods": r.headers.get("access-control-allow-methods")}


def cors_verdict(page_cors: dict, probe: dict | None) -> str:
    """'any origin', 'reflects any origin', 'restricted', or 'unknown'."""
    if (page_cors or {}).get("access-control-allow-origin") == "*":
        return "any origin"
    if probe and not probe.get("error"):
        if probe.get("allow_origin") == "*":
            return "any origin"
        if probe.get("allow_origin") == PROBE_ORIGIN:
            return "reflects any origin"
        return "restricted"
    return "unknown"


def analyse_page(page_url: str, network: list, probe=probe_cors, do_probe: bool = True) -> dict:
    page_site = site_of(urlsplit(page_url).hostname or "")
    apis, probed = {}, 0
    for entry in network:
        if not is_api_call(entry, page_site):
            continue
        key = (entry["method"], entry["url"])
        if key in apis:
            continue
        result = None
        writes = entry["method"] in WRITE_METHODS
        if writes and do_probe and probed < MAX_PROBES and cors_verdict(entry.get("cors"), None) == "unknown":
            result = probe(entry["url"], entry["method"] if entry["method"] not in ("GET", "HEAD") else "GET")
            probed += 1
        verdict = cors_verdict(entry.get("cors"), result)
        apis[key] = {"url": entry["url"], "method": entry["method"], "status": entry.get("status"),
                     "has_auth_header": entry.get("has_auth_header", False), "cors": verdict,
                     "writes": writes,
                     "open": writes and verdict in ("any origin", "reflects any origin") and not entry.get("has_auth_header"),
                     "probe": result}
    third = {}
    vendors = {}
    for entry in network:
        host = (urlsplit(entry["url"]).hostname or "").lower()
        if not host or site_of(host) == page_site:
            continue
        third[host] = third.get(host, 0) + 1
        name = vendor_of(entry["url"])
        if name:
            vendors.setdefault(name, set()).add(host)
    first_party_plumbing = sorted({strip_query(e["url"]) for e in network if site_of(urlsplit(e["url"]).hostname or "") == page_site
                                   and e.get("resource_type") in ("xhr", "fetch", "ping")
                                   and FIRST_PARTY_PLUMBING.match(urlsplit(e["url"]).path or "/")})
    return {
        "page": page_url,
        "requests": len(network),
        "first_party_apis": list(apis.values()),
        "open_endpoints": [a for a in apis.values() if a["open"]],
        "readable_cross_origin": [a["url"] for a in apis.values() if not a["writes"] and a["cors"] == "any origin"],
        "third_party_hosts": dict(sorted(third.items(), key=lambda kv: (-kv[1], kv[0]))),
        "vendors": {k: sorted(v) for k, v in sorted(vendors.items())},
        "infrastructure_hosts": sorted(h for h in third if _is_infrastructure(h)),
        "unrecognised_third_parties": sorted(h for h in set(third) - {h for hosts in vendors.values() for h in hosts}
                                             if not _is_infrastructure(h)),
        "first_party_tag_proxies": first_party_plumbing,
    }


# ---------------------------------------------------------------------------
# llms.txt endpoints
# ---------------------------------------------------------------------------

API_SHAPE = re.compile(r"(^|/)(api|v\d+|graphql|ask|chat|query|mcp|rpc|completions?)(/|$)", re.I)
URL_IN_TEXT = re.compile(r"https?://[^\s<>()\"'`\]]+")


def llms_endpoints(text: str, site: str) -> list:
    """API-shaped URLs on the site's own domain named in llms.txt: /api/, /v1/, /ask, /mcp, api.* hosts."""
    out = []
    for raw in URL_IN_TEXT.findall(text or ""):
        url = raw.rstrip(".,;:")
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if site_of(host) != site:
            continue
        if API_SHAPE.search(parts.path or "") or host.split(".")[0] in ("api", "agent", "mcp", "graphql"):
            if not re.search(r"\.(md|txt|html?|pdf|json|xml)$", parts.path or "", re.I):
                out.append(strip_query(url))
    return sorted(set(out))


def probe_endpoint(url: str, timeout: int = 10) -> dict:
    """GET, then (for anything that is not an HTML page) an OPTIONS preflight from a foreign origin. Never a POST.

    An HTML answer means a page, not an endpoint (Improvado's llms.txt lists /mcp/<source> marketing
    pages). A 403 with an HTML body is a server or firewall refusing the method, not an auth check;
    auth is a 401, a WWW-Authenticate header, or a 403 with a non-HTML body.
    """
    safe = validate_url(url)
    if not safe.ok:
        return {"url": url, "error": f"URL safety check failed: {safe.reason}"}
    import requests
    try:
        g = requests.get(url, timeout=timeout, allow_redirects=False, headers={"Origin": PROBE_ORIGIN})
    except requests.RequestException as exc:
        return {"url": url, "error": f"{type(exc).__name__}: {exc}"}
    ctype = (g.headers.get("content-type") or "").lower()
    get = {"status": g.status_code, "content_type": ctype.split(";")[0] or None,
           "allow_origin": g.headers.get("access-control-allow-origin"),
           "www_authenticate": bool(g.headers.get("www-authenticate"))}
    if "text/html" in ctype and g.status_code < 400:
        return {"url": url, "get": get, "kind": "page", "open": False}
    pre = probe_cors(url, "POST", timeout)
    return classify_endpoint(url, get, pre)


def classify_endpoint(url: str, get: dict, pre: dict) -> dict:
    html = "text/html" in (get.get("content_type") or "")
    auth = (get.get("status") == 401 or get.get("www_authenticate")
            or (get.get("status") == 403 and not html) or pre.get("status") == 401)
    verdict = cors_verdict({"access-control-allow-origin": "*"} if get.get("allow_origin") == "*" else {}, pre)
    return {"url": url, "kind": "endpoint", "get": get, "preflight": pre, "cors": verdict,
            "asks_for_auth": bool(auth), "open": verdict in ("any origin", "reflects any origin") and not auth}


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

def build_issues(pages: list, llms: dict | None) -> list:
    issues = []
    open_eps = {}
    for p in pages:
        for ep in p["open_endpoints"]:
            open_eps.setdefault((ep["method"], ep["url"]), {**ep, "pages": []})["pages"].append(p["page"])
    for ep in (llms or {}).get("endpoints", []) + (llms or {}).get("given", []):
        if ep.get("open"):
            open_eps.setdefault(("probe", ep["url"]), {"url": ep["url"], "method": ep.get("source", "advertised in llms.txt"),
                                                         "cors": ep["cors"], "pages": []})
    if open_eps:
        eps = list(open_eps.values())
        issues.append({
            "code": "open_public_endpoint", "severity": "medium", "kind": "defect", "lane": "Human",
            "finding": (("One of the site's own API endpoints accepts" if len(eps) == 1 else
                         f"{len(eps)} of the site's own API endpoints accept") + " write calls from any website with no key "
                        f"({', '.join(sorted({e['cors'] for e in eps}))})."),
            "evidence": "; ".join(f"{e['method']} {e['url']}" + (f" from {e['pages'][0]}" if e["pages"] else "") for e in eps[:5]),
            "impact": ("Any site or script can call these endpoints as if it were the site's own page: abuse and cost "
                       "(an LLM endpoint bills per call), prompt injection into anything it reads, and data it returns."),
            "fix": ("Call the endpoint through the site's own server with a key it holds, restrict CORS to the site's "
                    "origins, rate-limit it, and remove it from llms.txt and agent guidance until a security owner signs "
                    "off. Confirm with the owner before changing it: a public endpoint can be intended."),
            "confidence": "Confirmed",
            "falsifiability": "Wrong if the endpoint is meant to be public and is rate-limited and budgeted; the owner says so.",
            "leading_indicator": "The CORS header and the auth answer of each endpoint, re-probed after the change.",
            "urls": sorted({p for e in eps for p in e["pages"]}),
        })
    heavy = [p for p in pages if len(p["vendors"]) >= TAG_LOAD_VENDORS or len(p["third_party_hosts"]) >= TAG_LOAD_HOSTS]
    if heavy:
        worst = max(heavy, key=lambda p: (len(p["vendors"]), len(p["third_party_hosts"])))
        issues.append({
            "code": "tag_load", "severity": "low", "kind": "opportunity", "lane": "Assisted",
            "finding": (f"{worst['page']} loads {len(worst['vendors'])} tracking vendors from "
                        f"{len(worst['third_party_hosts'])} third-party hosts."),
            "evidence": ", ".join(worst["vendors"]) + (f"; unrecognised: {', '.join(worst['unrecognised_third_parties'][:6])}"
                                                      if worst["unrecognised_third_parties"] else ""),
            "impact": "Each tag adds main-thread work on every page: the usual cause of a slow Interaction to Next Paint on mobile.",
            "fix": ("List who owns each vendor and what decision it feeds; remove the unowned ones, load the rest after "
                    "interaction or through a server-side container, and re-measure INP in CrUX four weeks later."),
            "confidence": "Likely",
            "falsifiability": "Wrong if INP passes in CrUX on mobile; then the tags cost bandwidth but not responsiveness.",
            "leading_indicator": "Mobile INP p75 in CrUX, and the vendor count per page.",
            "urls": [p["page"] for p in heavy],
        })
    return issues


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_human(result: dict) -> None:
    for p in result["pages"]:
        print(f"{p['page']}: {p['requests']} requests, {len(p['third_party_hosts'])} third-party hosts, "
              f"{len(p['vendors'])} vendors")
        for a in p["first_party_apis"]:
            flag = "OPEN" if a["open"] else "ok"
            print(f"  [{flag}] {a['method']} {a['url']}  status {a['status']}  CORS {a['cors']}"
                  f"{'  auth header' if a['has_auth_header'] else ''}")
        if p["first_party_tag_proxies"]:
            print(f"  tag proxies (not APIs): {', '.join(p['first_party_tag_proxies'][:4])}")
        print(f"  vendors: {', '.join(p['vendors']) or '-'}")
        if p["unrecognised_third_parties"]:
            print(f"  unrecognised: {', '.join(p['unrecognised_third_parties'][:10])}")
    llms = result.get("llms_txt")
    if llms:
        if llms.get("url"):
            eps = llms.get("endpoints", [])
            pages = sum(1 for e in eps if e.get("kind") == "page")
            print(f"\nllms.txt ({llms.get('url')}): {len(eps)} API-shaped URLs, {pages} of them HTML pages")
        for ep in llms.get("endpoints", []) + llms.get("given", []):
            if ep.get("kind") == "page":
                continue
            print(f"  [{'OPEN' if ep.get('open') else 'ok'}] {ep['url']}  CORS {ep.get('cors')}  auth {ep.get('asks_for_auth')}"
                  f"{'  ' + ep['error'] if ep.get('error') else ''}")
    print()
    for i in result["issues"]:
        print(f"[{i['severity']}] {i['finding']}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Network calls of rendered pages: open first-party endpoints and tag load")
    parser.add_argument("urls", nargs="+", help="Pages to render (same site)")
    parser.add_argument("--llms-txt", action="store_true", help="Also probe API endpoints named in the site's /llms.txt")
    parser.add_argument("--endpoint", action="append", default=[], metavar="URL",
                        help="Also probe this endpoint (found in the page's scripts, docs or llms.txt history); repeatable")
    parser.add_argument("--no-probe", action="store_true", help="Do not send OPTIONS/GET probes; read only what the pages did")
    parser.add_argument("--timeout", type=int, default=45, help="Render timeout per page in seconds")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    pages, errors = [], []
    for url in args.urls:
        rendered = render_url(url, timeout=args.timeout, capture_network=True)
        if rendered.error:
            errors.append({"page": url, "error": rendered.error})
            continue
        pages.append(analyse_page(rendered.final_url or url, rendered.network, do_probe=not args.no_probe))
    llms = None
    if args.llms_txt and args.urls:
        root = urljoin(args.urls[0], "/llms.txt")
        llms = {"url": root}
        safe = validate_url(root)
        if not safe.ok:
            llms["error"] = f"URL safety check failed: {safe.reason}"
        else:
            import requests
            try:
                r = requests.get(root, timeout=15)
                llms["status"] = r.status_code
                eps = llms_endpoints(r.text if r.ok else "", site_of(urlsplit(root).hostname or ""))
                llms["endpoints"] = [probe_endpoint(u) if not args.no_probe else {"url": u} for u in eps[:MAX_PROBES]]
            except requests.RequestException as exc:
                llms["error"] = f"{type(exc).__name__}: {exc}"
    if args.endpoint:
        llms = llms or {}
        llms["given"] = [dict(probe_endpoint(u), source="given with --endpoint") for u in args.endpoint[:MAX_PROBES]]
    result = {"pages": pages, "errors": errors, "llms_txt": llms,
              "limits": ["Only requests made while the page loads are seen; a widget that calls its endpoint after a click or a typed question needs that interaction.",
                         "CORS is read from the page's own response and one OPTIONS preflight; an endpoint that checks the Origin only on POST is not probed further."]}
    result["issues"] = build_issues(pages, llms)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_human(result)
        for e in errors:
            print(f"Error: {e['page']}: {e['error']}", file=sys.stderr)
    return 1 if errors and not pages else 0


if __name__ == "__main__":
    sys.exit(main())
