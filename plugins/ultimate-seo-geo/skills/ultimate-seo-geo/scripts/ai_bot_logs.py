#!/usr/bin/env python3
"""
Count AI crawler visits in server access logs, and check them against the vendors' published IP ranges.

robots_checker.py reports what robots.txt allows, and ai_bot_access.py what a
firewall does to a spoofed request. Access logs are the only record of what the
real crawlers requested and what the server answered.

Reads Apache/Nginx combined log format and JSON lines (Nginx JSON, Cloudflare
Logpush field names and similar), plain or gzipped. Output is aggregate:
counts, status classes, top paths and dates. IP addresses are used for
verification and never printed.

Limits, repeated in every result:
  * Requests a CDN answers from cache never reach origin logs, so origin logs
    undercount crawlers on cached sites. Use CDN logs where you have them.
  * "Not seen" covers only the window the logs span; sampled or rotated logs
    undercount. It is never proof that a crawler does not visit.
  * Only OpenAI, Anthropic and Perplexity publish IP ranges. Other crawlers'
    hits cannot be verified and may include spoofed user agents.

Usage:
    python ai_bot_logs.py access.log
    python ai_bot_logs.py access.log access.log.1.gz --verify-ips --json
"""

import argparse
import gzip
import ipaddress
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

from robots_checker import AI_CRAWLER_ROLES
from url_safety import validate_url


# Published IP range files (checked 2026-09-14). All three vendors use the
# {"prefixes": [{"ipv4Prefix": ...}]} shape; Anthropic publishes one list for
# all of its crawlers.
IP_RANGE_URLS = {
    "OAI-SearchBot": "https://openai.com/searchbot.json",
    "ChatGPT-User": "https://openai.com/chatgpt-user.json",
    "GPTBot": "https://openai.com/gptbot.json",
    "PerplexityBot": "https://www.perplexity.com/perplexitybot.json",
    "Perplexity-User": "https://www.perplexity.com/perplexity-user.json",
    "ClaudeBot": "https://claude.com/crawling/bots.json",
    "Claude-SearchBot": "https://claude.com/crawling/bots.json",
    "Claude-User": "https://claude.com/crawling/bots.json",
}

REFUSED_STATUSES = {401, 403, 406, 451}
# A crawler is reported as turned away when at least this share of at least
# MIN_REQUESTS requests were refused.
REFUSED_SHARE_THRESHOLD = 50
MIN_REQUESTS = 5

# A token matches only as a whole token: "Claude-User" must not count as
# ClaudeBot, nor "Amzn-SearchBot" as Amazonbot.
_TOKEN_PATTERNS = [
    (crawler, re.compile(r"(?<![a-z0-9-])" + re.escape(crawler.lower()) + r"(?![a-z0-9-])"))
    for crawler in AI_CRAWLER_ROLES
]

# Apache/Nginx combined format. Nginx escapes quotes inside fields as \x22,
# Apache as \" -- both are handled.
COMBINED = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<request>(?:[^"\\]|\\.)*)" (?P<status>\d{3}) \S+'
    r'(?: "(?:[^"\\]|\\.)*" "(?P<ua>(?:[^"\\]|\\.)*)")?'
)

JSON_FIELDS = {
    "ip": ("remote_addr", "client_ip", "ClientIP", "ip", "remoteIp", "c-ip"),
    "ua": ("http_user_agent", "user_agent", "userAgent", "ClientRequestUserAgent", "ua"),
    "status": ("status", "status_code", "statusCode", "EdgeResponseStatus"),
    "path": ("request_uri", "uri", "path", "ClientRequestURI", "url"),
    "request": ("request",),
    "time": ("time_local", "time", "timestamp", "@timestamp", "EdgeStartTimestamp"),
}

LIMITS = [
    "Requests a CDN answers from cache never reach origin logs, so origin logs undercount "
    "crawlers on cached sites. Use CDN logs where you have them.",
    "Not seen covers only the window these logs span; sampled or rotated logs undercount. "
    "It is not proof that a crawler never visits.",
    "Only OpenAI, Anthropic and Perplexity publish IP ranges. Hits from other crawlers "
    "cannot be verified and may include spoofed user agents.",
]


def match_crawler(user_agent: str):
    ua = (user_agent or "").lower()
    for crawler, pattern in _TOKEN_PATTERNS:
        if pattern.search(ua):
            return crawler
    return None


def parse_time(value):
    """Parse a log timestamp into an aware UTC datetime, or None."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            n = float(value)
            divisor = 1e9 if n > 1e17 else 1e6 if n > 1e14 else 1e3 if n > 1e11 else 1
            return datetime.fromtimestamp(n / divisor, tz=timezone.utc)
        text = str(value)
        try:
            parsed = datetime.strptime(text, "%d/%b/%Y:%H:%M:%S %z")
        except ValueError:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, OverflowError, OSError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _path_from_request(request):
    parts = str(request or "").split()
    return parts[1] if len(parts) >= 2 else None


def _first(record: dict, keys: tuple):
    for key in keys:
        if record.get(key) not in (None, ""):
            return record[key]
    return None


def parse_line(line: str):
    """Parse one log line into {ip, ua, status, path, time}, or None if unrecognised."""
    line = line.strip()
    if not line:
        return None
    if line.startswith("{"):
        try:
            record = json.loads(line)
        except ValueError:
            return None
        if not isinstance(record, dict):
            return None
        entry = {
            "ip": _first(record, JSON_FIELDS["ip"]),
            "ua": _first(record, JSON_FIELDS["ua"]),
            "status": _first(record, JSON_FIELDS["status"]),
            "path": _first(record, JSON_FIELDS["path"]) or _path_from_request(_first(record, JSON_FIELDS["request"])),
            "time": parse_time(_first(record, JSON_FIELDS["time"])),
        }
    else:
        m = COMBINED.match(line)
        if not m:
            return None
        entry = {
            "ip": m.group("ip"),
            "ua": m.group("ua"),
            "status": m.group("status"),
            "path": _path_from_request(m.group("request")),
            "time": parse_time(m.group("time")),
        }
    try:
        entry["status"] = int(str(entry["status"]))
    except (TypeError, ValueError):
        entry["status"] = None
    if entry["path"]:
        entry["path"] = str(entry["path"]).split("?", 1)[0]
    return entry


def parse_prefixes(document) -> list:
    """Collect every ipv4Prefix / ipv6Prefix network in a published range file."""
    networks = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("ipv4Prefix", "ipv6Prefix") and isinstance(value, str):
                    try:
                        networks.append(ipaddress.ip_network(value, strict=False))
                    except ValueError:
                        continue
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(document)
    return networks


def _fetch_prefixes(url: str, timeout: int, max_redirects: int = 3):
    current = url
    try:
        for _ in range(max_redirects + 1):
            safe = validate_url(current)
            if not safe.ok:
                return None, f"{url}: URL safety check failed: {safe.reason}"
            response = requests.get(
                safe.normalized_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; UltimateSEO; +https://github.com/mykpono/ultimate-seo-geo)"},
                timeout=timeout,
                allow_redirects=False,
            )
            location = response.headers.get("Location")
            if response.is_redirect and location:
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            networks = parse_prefixes(response.json())
            if not networks:
                return None, f"{url}: no prefixes found"
            return networks, None
        return None, f"{url}: too many redirects"
    except (requests.exceptions.RequestException, ValueError) as exc:
        return None, f"{url}: {exc}"


def fetch_ip_ranges(timeout: int = 15) -> tuple:
    """Return ({crawler: [networks]}, {crawler: error}), fetching each URL once."""
    by_url = {}
    ranges, errors = {}, {}
    for crawler, url in IP_RANGE_URLS.items():
        if url not in by_url:
            by_url[url] = _fetch_prefixes(url, timeout)
        networks, error = by_url[url]
        if error:
            errors[crawler] = error
        else:
            ranges[crawler] = networks
    return ranges, errors


def _iso(dt):
    return dt.isoformat() if dt else None


def analyze(lines, ranges=None, range_errors=None, top_paths: int = 10) -> dict:
    """Aggregate AI crawler requests from log lines.

    `ranges` maps crawler -> published networks; None means verification was not
    requested. Crawlers absent from `ranges` cannot be verified.
    """
    counts = Counter()
    first = last = None
    stats = {}
    ip_cache = {}

    for line in lines:
        counts["lines_read"] += 1
        entry = parse_line(line)
        if entry is None:
            if line.strip():
                counts["lines_skipped"] += 1
            continue
        counts["lines_parsed"] += 1
        when = entry["time"]
        if when:
            first = when if first is None or when < first else first
            last = when if last is None or when > last else last
        if not entry["ua"]:
            counts["no_user_agent"] += 1
            continue
        crawler = match_crawler(entry["ua"])
        if not crawler:
            continue

        s = stats.setdefault(crawler, {
            "hits": 0, "refused": 0, "status": Counter(), "robots_txt": 0, "paths": Counter(),
            "first": None, "last": None, "verified": 0, "unverified": 0, "verified_refused": 0,
        })
        s["hits"] += 1
        status = entry["status"]
        refused = status in REFUSED_STATUSES
        s["refused"] += refused
        s["status"][f"{status // 100}xx" if status else "unknown"] += 1
        path = entry["path"] or ""
        if path == "/robots.txt":
            s["robots_txt"] += 1
        elif path:
            s["paths"][path] += 1
        if when:
            s["first"] = when if s["first"] is None or when < s["first"] else s["first"]
            s["last"] = when if s["last"] is None or when > s["last"] else s["last"]

        if ranges is not None and crawler in ranges:
            key = (crawler, entry["ip"])
            if key not in ip_cache:
                try:
                    address = ipaddress.ip_address(str(entry["ip"]).strip("[]"))
                    ip_cache[key] = any(address in net for net in ranges[crawler])
                except ValueError:
                    ip_cache[key] = False
            if ip_cache[key]:
                s["verified"] += 1
                s["verified_refused"] += refused
            else:
                s["unverified"] += 1

    if not counts["lines_parsed"]:
        return {
            "error": "no log lines could be parsed; supported formats are Apache/Nginx combined and JSON lines",
            "lines_read": counts["lines_read"],
        }

    crawlers, issues = {}, []
    for crawler, role in AI_CRAWLER_ROLES.items():
        s = stats.get(crawler)
        if not s:
            continue
        verifiable = ranges is not None and crawler in ranges
        basis_hits = s["verified"] if verifiable else s["hits"]
        basis_refused = s["verified_refused"] if verifiable else s["refused"]
        share = round(100 * basis_refused / basis_hits, 1) if basis_hits else None
        crawlers[crawler] = {
            "role": role,
            "hits": s["hits"],
            "status_classes": dict(sorted(s["status"].items())),
            "refused": s["refused"],
            "refused_share": share,
            "refused_share_basis": "verified requests" if verifiable else "all requests, unverified",
            "robots_txt_requests": s["robots_txt"],
            "top_paths": s["paths"].most_common(top_paths),
            "first_seen": _iso(s["first"]),
            "last_seen": _iso(s["last"]),
            "verified_hits": s["verified"] if verifiable else None,
            "unverified_hits": s["unverified"] if verifiable else None,
        }

        if role in ("search", "user") and share is not None and share >= REFUSED_SHARE_THRESHOLD and basis_hits >= MIN_REQUESTS:
            icon = "⚠️" if role == "search" else "ℹ️"
            caveat = "" if verifiable else (
                ". These requests are unverified: a firewall correctly refusing spoofed crawlers looks the same"
                + ("; rerun with --verify-ips" if crawler in IP_RANGE_URLS else "")
            )
            issues.append(
                f"{icon} {crawler} was refused (401/403/406/451) on {share}% of {basis_hits} "
                f"{'verified ' if verifiable else ''}requests: the server or CDN is turning it away{caveat}"
            )
        if verifiable and s["unverified"]:
            issues.append(
                f"ℹ️ {s['unverified']} request(s) claiming to be {crawler} came from outside its published "
                "IP ranges and are likely spoofed; they are excluded from its refusal share"
            )

    for crawler, error in sorted((range_errors or {}).items()):
        if crawler in stats:
            issues.append(f"ℹ️ IP ranges for {crawler} could not be fetched ({error}); its requests are unverified")

    not_seen = {
        role: [c for c, r in AI_CRAWLER_ROLES.items() if r == role and c not in stats]
        for role in ("search", "user", "training")
    }
    if not_seen["search"]:
        window = f" between {_iso(first)} and {_iso(last)}" if first and last else ""
        issues.append(
            f"ℹ️ No requests from AI search crawlers {', '.join(not_seen['search'])}{window}. Logs may be "
            "partial or sit behind a CDN cache, so this is not proof they never visit"
        )

    return {
        "lines_read": counts["lines_read"],
        "lines_parsed": counts["lines_parsed"],
        "lines_skipped": counts["lines_skipped"],
        "lines_without_user_agent": counts["no_user_agent"],
        "window": {"first": _iso(first), "last": _iso(last)},
        "ip_verification": "requested" if ranges is not None else "not requested",
        "crawlers": crawlers,
        "not_seen": not_seen,
        "issues": issues,
        "limits": LIMITS,
        "error": None,
    }


def iter_lines(paths):
    """Yield lines from each log file in turn; `-` reads stdin, `.gz` is decompressed."""
    for path in paths:
        if path == "-":
            yield from sys.stdin
            continue
        opener = gzip.open if path.endswith(".gz") else open
        with opener(path, "rt", encoding="utf-8", errors="replace") as fh:
            yield from fh


def main():
    parser = argparse.ArgumentParser(description="Count AI crawler visits in server access logs")
    parser.add_argument("logs", nargs="+", help="Access log files (combined format or JSON lines; .gz ok; - for stdin)")
    parser.add_argument(
        "--verify-ips",
        action="store_true",
        help="Fetch OpenAI, Anthropic and Perplexity published IP ranges and separate verified from spoofed requests",
    )
    parser.add_argument("--top-paths", type=int, default=10, help="Paths to list per crawler (default: 10)")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    ranges, range_errors = (None, {})
    if args.verify_ips:
        ranges, range_errors = fetch_ip_ranges()

    try:
        result = analyze(iter_lines(args.logs), ranges=ranges, range_errors=range_errors, top_paths=args.top_paths)
    except OSError as exc:
        result = {"error": f"could not read log: {exc}"}

    if args.json:
        print(json.dumps(result, indent=2))
        if result.get("error"):
            sys.exit(1)
        return
    if result.get("error"):
        print(f"Error: {result['error']}")
        sys.exit(1)

    window = result["window"]
    print("AI crawler requests in access logs")
    print("=" * 50)
    print(f"Lines parsed: {result['lines_parsed']} of {result['lines_read']}  |  Window: {window['first']} to {window['last']}")
    print(f"IP verification: {result['ip_verification']}")
    for crawler, c in result["crawlers"].items():
        verified = f", verified {c['verified_hits']}/{c['hits']}" if c["verified_hits"] is not None else ""
        share = f", refused {c['refused_share']}%" if c["refused_share"] else ""
        print(f"  {crawler} ({c['role']}): {c['hits']} requests{verified}{share}, robots.txt {c['robots_txt_requests']}x")
    if result["issues"]:
        print(f"\nIssues ({len(result['issues'])}):")
        for issue in result["issues"]:
            print(f"  {issue}")
    print("\nLimits:")
    for limit in result["limits"]:
        print(f"  - {limit}")


if __name__ == "__main__":
    main()
