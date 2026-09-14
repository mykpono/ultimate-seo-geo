#!/usr/bin/env python3
"""
Parse and analyze robots.txt for SEO and AI crawler management.

Usage:
    python robots_checker.py https://example.com
    python robots_checker.py https://example.com --json
"""

import argparse
import json
import sys
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)


# AI crawler tokens, grouped by what blocking each one costs. Roles follow each
# vendor's own crawler documentation (checked 2026-09-14):
#   search   -- builds the index an AI search product cites from. Blocking it
#               removes the site from that engine's answers.
#   user     -- fetches a page when a user asks. OpenAI, Perplexity, Meta and
#               Amazon say these may not follow robots.txt.
#   training -- collects content for model training, or is a control token
#               governing training use of content another bot crawled. Blocking
#               it is a licensing choice with no search-citation cost.
AI_CRAWLER_ROLES = {
    "OAI-SearchBot": "search",          # ChatGPT search — distinct from GPTBot
    "Claude-SearchBot": "search",
    "PerplexityBot": "search",
    "meta-webindexer": "search",        # Meta AI search
    "DuckAssistBot": "search",          # DuckDuckGo AI-assisted answers; not used for training
    "Amzn-SearchBot": "search",         # not used for training
    "ChatGPT-User": "user",
    "Claude-User": "user",
    "Perplexity-User": "user",          # Perplexity: generally ignores robots.txt
    "meta-externalfetcher": "user",
    "Amzn-User": "user",
    "MistralAI-User": "user",
    "GPTBot": "training",
    "ClaudeBot": "training",
    "Google-Extended": "training",      # control token — does NOT affect Google Search or AI Overviews
    "Applebot-Extended": "training",    # control token — does not crawl, does not affect Apple search
    "meta-externalagent": "training",
    "Amazonbot": "training",
    "MistralAI-Training": "training",
    "Bytespider": "training",
    "CCBot": "training",
}
AI_CRAWLERS = list(AI_CRAWLER_ROLES)

# Statuses under which a crawler cannot fetch the site root.
BLOCKING_STATUSES = ("fully blocked", "blocked by wildcard (*)")

# Tokens their vendors no longer document, mapped to the current tokens. They
# are reported when a robots.txt names them, never scored.
LEGACY_AI_TOKENS = {
    "anthropic-ai": "ClaudeBot, Claude-SearchBot and Claude-User",
    "Claude-Web": "ClaudeBot, Claude-SearchBot and Claude-User",
    "FacebookBot": "meta-externalagent, meta-webindexer and meta-externalfetcher",
}

# Standard crawlers for reference
STANDARD_CRAWLERS = [
    "Googlebot",
    "Bingbot",
    "Yandex",
    "Baiduspider",
    "DuckDuckBot",
]


def fetch_robots_txt(url: str, timeout: int = 15) -> dict:
    """Fetch and parse robots.txt from a domain."""
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)

    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    result = {
        "url": robots_url,
        "status": None,
        "raw": None,
        "user_agents": {},
        "sitemaps": [],
        "crawl_delays": {},
        "ai_crawler_status": {},
        "ai_crawler_roles": dict(AI_CRAWLER_ROLES),
        "issues": [],
        "error": None,
    }

    try:
        resp = requests.get(robots_url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (compatible; UltimateSEO/1.8)"
        })
        result["status"] = resp.status_code

        if resp.status_code == 404:
            # A missing robots.txt lets every crawler in (RFC 9309 sec 2.3.1.3):
            # a missing hygiene file, not a block.
            result["issues"].append(
                "⚠️ No robots.txt found — every crawler is allowed; add one to declare your sitemap"
            )
            for crawler in AI_CRAWLERS:
                result["ai_crawler_status"][crawler] = "allowed (no robots.txt)"
            return result

        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
            return result

        result["raw"] = resp.text
        _parse_robots(resp.text, result)

    except requests.exceptions.RequestException as e:
        result["error"] = str(e)

    return result


def _parse_robots(content: str, result: dict):
    """Parse robots.txt content into structured data."""
    current_agents = []
    # Consecutive User-agent lines form ONE group sharing the rules that follow
    # (RFC 9309 sec 2.2.1). A rule directive closes the group, so the next
    # User-agent line starts a new one.
    in_agent_group = False

    for line in content.splitlines():
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue

        # Split on first colon
        if ":" not in line:
            continue

        directive, _, value = line.partition(":")
        directive = directive.strip().lower()
        value = value.strip()

        if directive == "user-agent":
            if not in_agent_group:
                current_agents = []
            in_agent_group = True
            if value not in current_agents:
                current_agents.append(value)
            if value not in result["user_agents"]:
                result["user_agents"][value] = {"allow": [], "disallow": []}

        elif directive == "disallow" and current_agents:
            in_agent_group = False
            for agent in current_agents:
                if agent not in result["user_agents"]:
                    result["user_agents"][agent] = {"allow": [], "disallow": []}
                if value:
                    result["user_agents"][agent]["disallow"].append(value)

        elif directive == "allow" and current_agents:
            in_agent_group = False
            for agent in current_agents:
                if agent not in result["user_agents"]:
                    result["user_agents"][agent] = {"allow": [], "disallow": []}
                result["user_agents"][agent]["allow"].append(value)

        elif directive == "sitemap":
            result["sitemaps"].append(value)

        elif directive == "crawl-delay" and current_agents:
            in_agent_group = False
            for agent in current_agents:
                try:
                    result["crawl_delays"][agent] = float(value)
                except ValueError:
                    pass

    # Analyze AI crawler management. User-agent tokens are case-insensitive
    # (RFC 9309 sec 2.2.1), so match on a folded index while keeping the file's
    # original casing for display.
    agents_by_lower = {name.lower(): name for name in result["user_agents"]}

    for crawler in AI_CRAWLERS:
        declared = agents_by_lower.get(crawler.lower())
        if declared is not None:
            rules = result["user_agents"][declared]
            if rules["disallow"] and "/" in rules["disallow"]:
                result["ai_crawler_status"][crawler] = "fully blocked"
            elif rules["disallow"]:
                result["ai_crawler_status"][crawler] = f"partially blocked ({len(rules['disallow'])} paths)"
            elif rules["allow"]:
                result["ai_crawler_status"][crawler] = "explicitly allowed"
            else:
                result["ai_crawler_status"][crawler] = "declared but no rules"
        else:
            # Check wildcard rules
            if "*" in agents_by_lower:
                wildcard = result["user_agents"][agents_by_lower["*"]]
                if wildcard["disallow"] and "/" in wildcard["disallow"]:
                    result["ai_crawler_status"][crawler] = "blocked by wildcard (*)"
                else:
                    result["ai_crawler_status"][crawler] = "not managed (inherits * rules)"
            else:
                result["ai_crawler_status"][crawler] = "not managed (allowed by default)"

    # Generate issues
    unmanaged = [c for c, s in result["ai_crawler_status"].items()
                 if "not managed" in s or "allowed by default" in s]
    if unmanaged:
        result["issues"].append(
            f"ℹ️ {len(unmanaged)} AI crawlers have no rule of their own (allowed unless * blocks them): "
            f"{', '.join(unmanaged[:5])}"
        )

    blocked_search = [c for c, s in result["ai_crawler_status"].items()
                      if s in BLOCKING_STATUSES and AI_CRAWLER_ROLES.get(c) == "search"]
    if blocked_search:
        result["issues"].append(
            f"⚠️ AI search crawlers blocked: {', '.join(blocked_search)} — these build the "
            "indexes AI search answers cite, so the site cannot be cited from them"
        )

    for token, successors in LEGACY_AI_TOKENS.items():
        declared = agents_by_lower.get(token.lower())
        if declared is not None:
            result["issues"].append(
                f"ℹ️ robots.txt names {declared}, which its vendor no longer documents — "
                f"write the rule for {successors} instead"
            )

    if not result["sitemaps"]:
        result["issues"].append("⚠️ No Sitemap directive found in robots.txt")


def main():
    parser = argparse.ArgumentParser(description="Analyze robots.txt for SEO and AI crawlers")
    parser.add_argument("url", help="Website URL or domain")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    result = fetch_robots_txt(args.url)

    if args.json:
        # Exclude raw content from JSON for brevity
        output = {k: v for k, v in result.items() if k != "raw"}
        print(json.dumps(output, indent=2))
        return

    if result["error"]:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"robots.txt Analysis — {result['url']}")
    print("=" * 50)
    print(f"Status: {result['status']}")

    if result["sitemaps"]:
        print(f"\nSitemaps ({len(result['sitemaps'])}):")
        for sm in result["sitemaps"]:
            print(f"  • {sm}")

    print(f"\nUser-Agents ({len(result['user_agents'])}):")
    for agent, rules in result["user_agents"].items():
        allow_count = len(rules["allow"])
        disallow_count = len(rules["disallow"])
        print(f"  {agent}: {disallow_count} disallow, {allow_count} allow")

    if result["crawl_delays"]:
        print(f"\nCrawl Delays:")
        for agent, delay in result["crawl_delays"].items():
            print(f"  {agent}: {delay}s")

    print(f"\nAI Crawler Management:")
    for crawler, status in result["ai_crawler_status"].items():
        role = AI_CRAWLER_ROLES.get(crawler, "unknown")
        if status in BLOCKING_STATUSES and role == "search":
            icon = "⛔"
        elif "not managed" in status:
            icon = "⚠️"
        else:
            icon = "ℹ️"
        print(f"  {icon} {crawler} ({role}): {status}")

    if result["issues"]:
        print(f"\nIssues ({len(result['issues'])}):")
        for issue in result["issues"]:
            print(f"  {issue}")


if __name__ == "__main__":
    main()
