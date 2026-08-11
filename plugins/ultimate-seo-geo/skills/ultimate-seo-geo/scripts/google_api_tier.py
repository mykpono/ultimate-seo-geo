#!/usr/bin/env python3
"""
Detect available Google API credentials and report the accessible tier.

Tier system:
  0 — API key only (PageSpeed Insights, CrUX, CrUX History)
  1 — OAuth2 / service account (Google Search Console)
  2 — OAuth2 with GA4 scope (GA4 Data API)
  3 — OAuth2 with Google Ads scope (future — Keyword Planner)

Usage:
    python scripts/google_api_tier.py --check
    python scripts/google_api_tier.py --json
"""

import argparse
import json
import os
import sys


TIER_DEFINITIONS = [
    {
        "tier": 0,
        "label": "API Key",
        "apis": ["pagespeed", "crux", "crux_history"],
        "env_vars": ["PAGESPEED_API_KEY", "GOOGLE_API_KEY"],
        "description": "PageSpeed Insights, CrUX API, CrUX History API",
    },
    {
        "tier": 1,
        "label": "OAuth2 — Search Console",
        "apis": ["search_console"],
        "env_vars": ["GOOGLE_APPLICATION_CREDENTIALS", "GSC_CREDENTIALS"],
        "description": "Google Search Console Search Analytics + URL Inspection",
        "token_files": ["gsc-oauth-token.json"],
        "scopes": ["https://www.googleapis.com/auth/webmasters"],
    },
    {
        "tier": 2,
        "label": "OAuth2 — GA4",
        "apis": ["ga4"],
        "env_vars": ["GA4_CREDENTIALS"],
        "description": "GA4 Data API (sessions, users, landing pages)",
        "token_files": ["ga4-oauth-token.json"],
        "scopes": ["https://www.googleapis.com/auth/analytics.readonly"],
    },
    {
        "tier": 3,
        "label": "OAuth2 — Google Ads (future)",
        "apis": ["google_ads"],
        "env_vars": ["GOOGLE_ADS_CREDENTIALS"],
        "description": "Keyword Planner, campaign data (not yet implemented)",
        "scopes": ["https://www.googleapis.com/auth/adwords"],
    },
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)


def _check_api_key() -> dict:
    """Check for Tier 0 API key availability."""
    key = os.environ.get("PAGESPEED_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        source = "PAGESPEED_API_KEY" if os.environ.get("PAGESPEED_API_KEY") else "GOOGLE_API_KEY"
        return {"available": True, "source": source, "note": "API key detected"}
    return {"available": False, "source": None, "note": "No API key found"}


def _check_service_account() -> dict:
    """Check for a service account JSON file via GOOGLE_APPLICATION_CREDENTIALS."""
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not path:
        return {"available": False, "path": None, "scopes": []}

    if not os.path.isfile(path):
        return {
            "available": False,
            "path": path,
            "scopes": [],
            "error": f"File not found: {path}",
        }

    try:
        with open(path, "r", encoding="utf-8") as f:
            sa_data = json.load(f)
        sa_type = sa_data.get("type", "unknown")
        if sa_type != "service_account":
            return {
                "available": False,
                "path": path,
                "scopes": [],
                "note": f"JSON type is '{sa_type}', not 'service_account'",
            }
        return {
            "available": True,
            "path": path,
            "scopes": [],
            "note": "Service account JSON found (scopes depend on API enablement in GCP project)",
        }
    except (json.JSONDecodeError, OSError) as e:
        return {"available": False, "path": path, "scopes": [], "error": str(e)}


def _check_oauth_token(env_var: str, token_filename: str | None) -> dict:
    """Check for an OAuth token file via env var or default repo-root path."""
    path = os.environ.get(env_var)
    if path and os.path.isfile(path):
        return {"available": True, "source": env_var, "path": path}

    if token_filename:
        default_path = os.path.join(REPO_ROOT, token_filename)
        if os.path.isfile(default_path):
            return {"available": True, "source": f"default ({token_filename})", "path": default_path}

    return {"available": False, "source": None, "path": None}


def detect_tier() -> dict:
    """
    Detect available Google API credentials and return tier information.

    Returns a dict with detected_tier, available_apis, unavailable_apis,
    credential_details, and upgrade_instructions.
    """
    detected_tier = -1
    available_apis: list[str] = []
    unavailable_apis: list[dict] = []
    credential_details: dict[str, dict] = {}

    api_key_info = _check_api_key()
    credential_details["api_key"] = api_key_info
    if api_key_info["available"]:
        detected_tier = 0
        available_apis.extend(["pagespeed", "crux", "crux_history"])

    sa_info = _check_service_account()
    credential_details["service_account"] = sa_info

    gsc_token = _check_oauth_token("GSC_CREDENTIALS", "gsc-oauth-token.json")
    credential_details["gsc_oauth"] = gsc_token
    if sa_info["available"] or gsc_token["available"]:
        detected_tier = max(detected_tier, 1)
        available_apis.append("search_console")

    ga4_token = _check_oauth_token("GA4_CREDENTIALS", "ga4-oauth-token.json")
    credential_details["ga4_oauth"] = ga4_token
    if ga4_token["available"] or (sa_info["available"] and ga4_token.get("source")):
        detected_tier = max(detected_tier, 2)
        available_apis.append("ga4")

    if "pagespeed" not in available_apis:
        unavailable_apis.append({
            "api": "pagespeed / crux / crux_history",
            "requires": "Tier 0 — API key",
            "env_var": "PAGESPEED_API_KEY or GOOGLE_API_KEY",
            "setup": "Get a key at https://console.cloud.google.com/apis/credentials",
        })

    if "search_console" not in available_apis:
        unavailable_apis.append({
            "api": "search_console",
            "requires": "Tier 1 — OAuth2 credentials",
            "env_var": "GOOGLE_APPLICATION_CREDENTIALS or GSC_CREDENTIALS",
            "setup": (
                "Create a service account or OAuth client in GCP, enable the "
                "Search Console API, then set GOOGLE_APPLICATION_CREDENTIALS "
                "to the JSON path. Or run: python scripts/gsc_export.py --auth"
            ),
        })

    if "ga4" not in available_apis:
        unavailable_apis.append({
            "api": "ga4",
            "requires": "Tier 2 — OAuth2 with GA4 scope",
            "env_var": "GA4_CREDENTIALS",
            "setup": (
                "Create OAuth credentials with Analytics Reporting scope, "
                "enable the GA4 Data API in GCP, and set GA4_CREDENTIALS "
                "to the token JSON path."
            ),
        })

    unavailable_apis.append({
        "api": "google_ads",
        "requires": "Tier 3 — OAuth2 with Ads scope (future)",
        "env_var": "GOOGLE_ADS_CREDENTIALS",
        "setup": "Not yet implemented. Planned for Keyword Planner integration.",
    })

    if detected_tier < 0:
        upgrade = (
            "No Google API credentials detected. "
            "Set PAGESPEED_API_KEY or GOOGLE_API_KEY to unlock Tier 0 "
            "(PageSpeed Insights, CrUX). Get a key at "
            "https://console.cloud.google.com/apis/credentials"
        )
    elif detected_tier == 0:
        upgrade = (
            "Set GOOGLE_APPLICATION_CREDENTIALS to a service account JSON "
            "with Search Console API scope to unlock Tier 1. "
            "Or run: python scripts/gsc_export.py --auth"
        )
    elif detected_tier == 1:
        upgrade = (
            "Set GA4_CREDENTIALS to an OAuth token with Analytics Reporting "
            "scope to unlock Tier 2 (GA4 Data API)."
        )
    elif detected_tier == 2:
        upgrade = "Tier 3 (Google Ads / Keyword Planner) is planned but not yet implemented."
    else:
        upgrade = "All available tiers are unlocked."

    effective_tier = detected_tier if detected_tier >= 0 else None
    tier_label = TIER_DEFINITIONS[detected_tier]["label"] if detected_tier >= 0 else "None — no credentials detected"

    return {
        "detected_tier": effective_tier,
        "tier_label": tier_label,
        "available_apis": available_apis,
        "unavailable_apis": unavailable_apis,
        "credential_details": credential_details,
        "upgrade_instructions": upgrade,
    }


def print_human(result: dict) -> None:
    """Print tier detection results in a human-readable format."""
    tier = result["detected_tier"]
    print(f"Google API Tier Detection")
    print("=" * 45)
    tier_display = tier if tier is not None else "—"
    print(f"Detected Tier: {tier_display} — {result['tier_label']}")
    print()

    if result["available_apis"]:
        print("Available APIs:")
        for api in result["available_apis"]:
            print(f"  ✅ {api}")
    else:
        print("Available APIs: none")

    print()

    unavailable = [u for u in result["unavailable_apis"] if u["api"] != "google_ads"]
    if unavailable:
        print("Unavailable APIs:")
        for u in unavailable:
            print(f"  ❌ {u['api']} — {u['requires']}")
            print(f"     Set: {u['env_var']}")

    print()
    print(f"Next step: {result['upgrade_instructions']}")


def main():
    parser = argparse.ArgumentParser(
        description="Detect available Google API credentials and report the accessible tier."
    )
    parser.add_argument(
        "--json", "-j", action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--check", "-c", action="store_true",
        help="Run detection and print human-readable summary",
    )
    args = parser.parse_args()

    if not args.json and not args.check:
        parser.print_help()
        sys.exit(0)

    result = detect_tier()

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_human(result)


if __name__ == "__main__":
    main()
