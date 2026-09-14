#!/usr/bin/env python3
"""
Check whether AI crawlers can actually fetch a page, not just whether robots.txt allows them.

robots.txt is advice; a firewall or CDN bot rule is enforcement. A site can
allow OAI-SearchBot in robots.txt while its WAF answers that user agent with a
403 or a JavaScript challenge, and the site is just as absent from AI answers.

The URL is fetched once with a browser user agent, then once per AI crawler
user agent, each from a fresh session so no challenge cookie carries over, and
the responses are compared.

Limits, repeated in every result:
  * Requests come from this machine's IP, not the vendor's published ranges.
    Firewalls that verify bots by IP may refuse this request while letting the
    real crawler through, or the reverse. A refusal here is suspected, not proof.
  * 429 and 5xx responses mean rate limiting or an outage as often as a bot
    rule, so they are reported as inconclusive.

Usage:
    python ai_bot_access.py https://example.com
    python ai_bot_access.py https://example.com --roles search --json
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

from robots_checker import AI_CRAWLER_ROLES
from url_safety import validate_url


BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Full user-agent strings where the vendor publishes one (checked 2026-09-14).
# Firewall bot rules match on the product token, so crawlers without a published
# string get their token in a standard compatible wrapper.
DOCUMENTED_USER_AGENTS = {
    "OAI-SearchBot": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36; compatible; OAI-SearchBot/1.4; +https://openai.com/searchbot"
    ),
    "ChatGPT-User": (
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; "
        "+https://openai.com/bot"
    ),
    "PerplexityBot": (
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; "
        "+https://perplexity.ai/perplexitybot)"
    ),
    "Perplexity-User": (
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; "
        "+https://perplexity.ai/perplexity-user)"
    ),
    "DuckAssistBot": "DuckAssistBot/1.2; (+http://duckduckgo.com/duckassistbot.html)",
}

# Statuses a bot rule answers with. 429 and 5xx are deliberately absent.
BLOCK_STATUSES = {401, 403, 406, 451}
INCONCLUSIVE_STATUSES = {429, 500, 502, 503, 504}

# Body markers of WAF/CDN challenge and block pages. A marker counts only when
# the browser response lacks it: bot-management scripts are injected into
# ordinary pages too, so presence alone proves nothing.
CHALLENGE_MARKERS = (
    ("Cloudflare", "cf_chl_opt"),
    ("Cloudflare", "challenge-platform"),
    ("Cloudflare", "<title>just a moment...</title>"),
    ("Cloudflare", "attention required! | cloudflare"),
    ("Imperva", "_incapsula_resource"),
    ("DataDome", "captcha-delivery.com"),
    ("HUMAN", "px-captcha"),
    ("Sucuri", "sucuri website firewall"),
)

MAX_BODY_BYTES = 262144
LIMITS = [
    "Requests come from this machine's IP, not the crawler vendor's published IP ranges. "
    "A firewall that verifies bots by IP can treat the real crawler differently, so a "
    "refusal here is suspected, not proven. Confirm in the firewall or CDN bot logs.",
    "429 and 5xx responses are reported as inconclusive: they mean rate limiting or an "
    "outage as often as a bot rule.",
]


def user_agent_for(crawler: str) -> tuple:
    """Return (user agent, "documented" | "token") for a crawler token."""
    if crawler in DOCUMENTED_USER_AGENTS:
        return DOCUMENTED_USER_AGENTS[crawler], "documented"
    return f"Mozilla/5.0 (compatible; {crawler}/1.0)", "token"


def fetch(url: str, user_agent: str, timeout: int = 12, max_redirects: int = 5) -> dict:
    """GET a URL with one user agent from a fresh session, validating every hop."""
    result = {"status": None, "final_url": url, "bytes": 0, "server": None,
              "cf_mitigated": None, "error": None, "body": ""}
    session = requests.Session()
    try:
        current = url
        response = None
        for hop in range(max_redirects + 1):
            safe = validate_url(current)
            if not safe.ok:
                result["error"] = f"URL safety check failed: {safe.reason}"
                return result
            response = session.get(
                safe.normalized_url,
                headers={
                    "User-Agent": user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
                timeout=timeout,
                allow_redirects=False,
                stream=True,
            )
            location = response.headers.get("Location")
            if not (response.is_redirect and location):
                break
            response.close()
            if hop == max_redirects:
                result["error"] = f"Too many redirects (max {max_redirects})"
                return result
            current = urljoin(response.url, location)

        body = b""
        for chunk in response.iter_content(chunk_size=65536):
            body += chunk
            if len(body) >= MAX_BODY_BYTES:
                break
        response.close()
        headers = {k.lower(): v for k, v in response.headers.items()}
        result.update(
            status=response.status_code,
            final_url=response.url,
            bytes=len(body),
            server=headers.get("server"),
            cf_mitigated=headers.get("cf-mitigated"),
            body=body[:MAX_BODY_BYTES].decode("utf-8", "replace").lower(),
        )
    except requests.exceptions.RequestException as exc:
        result["error"] = f"Request failed: {exc}"
    finally:
        session.close()
    return result


def challenge_vendor(response: dict, baseline: dict) -> str:
    """Name the WAF whose challenge page this is, or "" when it is not one."""
    if (response.get("cf_mitigated") or "").lower() == "challenge":
        return "Cloudflare"
    body, baseline_body = response.get("body") or "", baseline.get("body") or ""
    for vendor, marker in CHALLENGE_MARKERS:
        if marker in body and marker not in baseline_body:
            return vendor
    return ""


def classify(response: dict, baseline: dict) -> tuple:
    """Return (verdict, challenge vendor) for one crawler's response."""
    if response.get("error"):
        return "error", ""
    vendor = challenge_vendor(response, baseline)
    if vendor:
        return "challenged", vendor
    status = response.get("status")
    if status in BLOCK_STATUSES:
        return "blocked", ""
    if status in INCONCLUSIVE_STATUSES:
        return "inconclusive", ""
    if status == baseline.get("status") or (200 <= (status or 0) < 400 and 200 <= (baseline.get("status") or 0) < 400):
        return "allowed", ""
    return "different", ""


def _baseline_problem(baseline: dict) -> str:
    if baseline.get("error"):
        return baseline["error"]
    if (baseline.get("cf_mitigated") or "").lower() == "challenge":
        return "the browser request was challenged"
    status = baseline.get("status")
    if status in BLOCK_STATUSES or status in INCONCLUSIVE_STATUSES:
        return f"the browser request returned HTTP {status}"
    return ""


def check_access(url: str, roles=("search", "user"), timeout: int = 12, workers: int = 3) -> dict:
    """Fetch url as a browser and as each AI crawler in `roles`, and compare."""
    safe = validate_url(url)
    if not safe.ok:
        return {"url": url, "error": f"URL safety check failed: {safe.reason}"}
    target = safe.normalized_url
    crawlers = [c for c, role in AI_CRAWLER_ROLES.items() if role in roles]

    baseline = fetch(target, BROWSER_USER_AGENT, timeout)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        responses = dict(zip(crawlers, pool.map(lambda c: fetch(target, user_agent_for(c)[0], timeout), crawlers)))

    problem = _baseline_problem(baseline)
    bots = {}
    for crawler in crawlers:
        response = responses[crawler]
        verdict, vendor = ("inconclusive", "") if problem else classify(response, baseline)
        bots[crawler] = {
            "role": AI_CRAWLER_ROLES[crawler],
            "user_agent_source": user_agent_for(crawler)[1],
            "status": response["status"],
            "verdict": verdict,
            "challenge_vendor": vendor or None,
            "server": response["server"],
            "error": response["error"],
        }

    refused = {role: [c for c, b in bots.items() if b["role"] == role and b["verdict"] in ("blocked", "challenged")]
               for role in ("search", "user")}
    inconclusive = [c for c, b in bots.items() if b["verdict"] in ("inconclusive", "error")]
    conclusive_search = [c for c, b in bots.items()
                         if b["role"] == "search" and b["verdict"] not in ("inconclusive", "error")]

    issues = []
    if problem:
        issues.append(
            f"ℹ️ Inconclusive: {problem}, so bot rules cannot be told apart from blocking of this network"
        )
    for role, label, icon in (("search", "AI search crawler", "⚠️"), ("user", "AI user-fetch", "ℹ️")):
        if refused[role]:
            details = ", ".join(_describe(c, bots[c]) for c in refused[role])
            issues.append(
                f"{icon} Suspected firewall block: {label} user agents were refused while a browser was "
                f"served: {details}. robots.txt cannot fix this; check the firewall or CDN bot settings"
            )
    if inconclusive and not problem:
        issues.append(f"ℹ️ Inconclusive (rate limited, server error or network error): {', '.join(inconclusive)}")

    allowed_search = [c for c in conclusive_search if bots[c]["verdict"] == "allowed"]
    return {
        "url": target,
        "status": "inconclusive" if problem else "ok",
        "baseline": {k: baseline[k] for k in ("status", "final_url", "bytes", "server", "error")},
        "bots": bots,
        "refused_search": refused["search"],
        "refused_user": refused["user"],
        "inconclusive": inconclusive,
        "score": round(100 * len(allowed_search) / len(conclusive_search)) if conclusive_search and not problem else None,
        "issues": issues,
        "limits": LIMITS,
        "error": None,
    }


def _describe(crawler: str, bot: dict) -> str:
    if bot["verdict"] == "challenged":
        return f"{crawler} ({bot['challenge_vendor']} challenge)"
    return f"{crawler} (HTTP {bot['status']})"


def main():
    parser = argparse.ArgumentParser(description="Check whether AI crawler user agents can fetch a URL")
    parser.add_argument("url", help="URL to test")
    parser.add_argument(
        "--roles",
        default="search,user",
        help="Comma-separated crawler roles to test: search, user, training (default: search,user)",
    )
    parser.add_argument("--timeout", type=int, default=12, help="Per-request timeout in seconds (default: 12)")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    roles = tuple(r.strip() for r in args.roles.split(",") if r.strip())
    unknown = sorted(set(roles) - {"search", "user", "training"})
    if unknown:
        print(json.dumps({"error": f"unknown roles: {', '.join(unknown)}"}) if args.json else f"Error: unknown roles: {', '.join(unknown)}")
        sys.exit(1)

    result = check_access(args.url, roles=roles, timeout=args.timeout)
    if args.json:
        print(json.dumps(result, indent=2))
        return
    if result.get("error"):
        print(f"Error: {result['error']}")
        sys.exit(1)

    base = result["baseline"]
    print(f"AI bot access — {result['url']}")
    print("=" * 50)
    print(f"Browser baseline: HTTP {base['status']} ({base['bytes']} bytes, server: {base['server'] or 'unknown'})")
    for crawler, bot in result["bots"].items():
        vendor = f", {bot['challenge_vendor']} challenge" if bot["challenge_vendor"] else ""
        print(f"  {crawler} ({bot['role']}): HTTP {bot['status']} -> {bot['verdict']}{vendor}")
    if result["issues"]:
        print(f"\nIssues ({len(result['issues'])}):")
        for issue in result["issues"]:
            print(f"  {issue}")
    print("\nLimits:")
    for limit in result["limits"]:
        print(f"  - {limit}")


if __name__ == "__main__":
    main()
