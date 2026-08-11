#!/usr/bin/env python3
"""SEO drift baseline, compare, history, and report snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from fetch_page import fetch_page


DEFAULT_DB = os.path.join(os.getcwd(), ".seo-drift.sqlite3")

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            data TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_url_time ON snapshots(url, captured_at)")
    return conn


def _sha(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _similarity(a: str, b: str) -> float:
    """Return 0.0–1.0 similarity ratio between two strings."""
    if not a and not b:
        return 1.0
    return SequenceMatcher(None, a or "", b or "").ratio()


def _pct_change(old: int | float, new: int | float) -> float:
    """Return absolute percentage change. Returns 0 if old is 0."""
    if old == 0:
        return 0.0 if new == 0 else 100.0
    return abs(new - old) / old * 100


def _body_word_count(soup: BeautifulSoup) -> int:
    body = soup.find("body")
    if not body:
        return 0
    for tag in body.find_all(["script", "style", "noscript"]):
        tag.decompose()
    text = body.get_text(" ", strip=True)
    return len(re.findall(r"\S+", text))


def extract_snapshot(html: str, url: str, status_code: int | None = None) -> dict:
    soup = BeautifulSoup(html or "", "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    meta = soup.find("meta", attrs={"name": "description"})
    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    robots = soup.find("meta", attrs={"name": "robots"})
    h1s = [h.get_text(" ", strip=True) for h in soup.find_all("h1")]
    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])]
    schema_blocks = [tag.string or "" for tag in soup.find_all("script", attrs={"type": "application/ld+json"})]
    internal_links = [
        a.get("href", "")
        for a in soup.find_all("a", href=True)
        if not urlparse(a["href"]).netloc or urlparse(a["href"]).netloc == urlparse(url).netloc
    ]

    og_title_tag = soup.find("meta", attrs={"property": "og:title"})
    og_desc_tag = soup.find("meta", attrs={"property": "og:description"})
    og_img_tag = soup.find("meta", attrs={"property": "og:image"})

    return {
        "url": url,
        "status_code": status_code,
        "title": title,
        "meta_description": meta.get("content", "") if meta else "",
        "canonical": canonical.get("href", "") if canonical else "",
        "robots": robots.get("content", "") if robots else "",
        "h1": h1s,
        "headings_hash": _sha("\n".join(headings)),
        "schema_hash": _sha("\n".join(schema_blocks)),
        "schema_count": len(schema_blocks),
        "internal_link_count": len(internal_links),
        "word_count": _body_word_count(soup),
        "og_title": og_title_tag.get("content", "") if og_title_tag else "",
        "og_description": og_desc_tag.get("content", "") if og_desc_tag else "",
        "og_image": og_img_tag.get("content", "") if og_img_tag else "",
    }


def capture(url: str) -> dict:
    fetched = fetch_page(url, timeout=20)
    if fetched.get("error"):
        return {"url": url, "error": fetched["error"]}
    return extract_snapshot(fetched.get("content", ""), fetched.get("url", url), fetched.get("status_code"))


def save_baseline(url: str, db_path: str) -> dict:
    snapshot = capture(url)
    if snapshot.get("error"):
        return snapshot
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO snapshots(url, captured_at, data) VALUES (?, ?, ?)",
            (url, datetime.utcnow().isoformat(timespec="seconds") + "Z", json.dumps(snapshot, sort_keys=True)),
        )
    return {"saved": True, "url": url, "snapshot": snapshot, "db_path": db_path}


def _latest(url: str, db_path: str) -> tuple[str, dict] | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT captured_at, data FROM snapshots WHERE url = ? ORDER BY captured_at DESC, id DESC LIMIT 1",
            (url,),
        ).fetchone()
    if not row:
        return None
    return row[0], json.loads(row[1])


def _apply_rules(previous: dict, current: dict) -> list[dict]:
    """Apply the 17-rule comparison engine and return classified changes."""
    changes: list[dict] = []

    old_status = previous.get("status_code")
    new_status = current.get("status_code")
    if old_status != new_status and old_status is not None and new_status is not None:
        # Rule 1: 200 → 4xx/5xx
        if old_status == 200 and new_status is not None and new_status >= 400:
            changes.append({
                "rule": 1,
                "severity": "critical",
                "field": "status_code",
                "description": f"Status changed from 200 to {new_status}",
                "before": old_status,
                "after": new_status,
            })
        # Rule 4: 200 → 3xx redirect
        elif old_status == 200 and 300 <= (new_status or 0) < 400:
            changes.append({
                "rule": 4,
                "severity": "critical",
                "field": "status_code",
                "description": f"Page now redirects ({new_status}) instead of serving content",
                "before": old_status,
                "after": new_status,
            })
        else:
            changes.append({
                "rule": 1,
                "severity": "warning",
                "field": "status_code",
                "description": f"Status code changed from {old_status} to {new_status}",
                "before": old_status,
                "after": new_status,
            })

    # Rule 2: Canonical changed
    old_canonical = previous.get("canonical", "")
    new_canonical = current.get("canonical", "")
    if old_canonical != new_canonical:
        changes.append({
            "rule": 2,
            "severity": "critical",
            "field": "canonical",
            "description": "Canonical URL changed",
            "before": old_canonical,
            "after": new_canonical,
        })

    # Rule 3: Robots meta changed
    old_robots = previous.get("robots", "")
    new_robots = current.get("robots", "")
    if old_robots != new_robots:
        sev = "critical" if "noindex" in (new_robots or "").lower() else "critical"
        desc = "Robots meta changed to noindex" if "noindex" in (new_robots or "").lower() else "Robots meta directive changed"
        changes.append({
            "rule": 3,
            "severity": sev,
            "field": "robots",
            "description": desc,
            "before": old_robots,
            "after": new_robots,
        })

    # Rules 5 & 7 & 14: Title tag
    old_title = previous.get("title", "")
    new_title = current.get("title", "")
    if old_title != new_title:
        if old_title and not new_title:
            # Rule 5: Title removed
            changes.append({
                "rule": 5,
                "severity": "critical",
                "field": "title",
                "description": "Title tag removed entirely",
                "before": old_title,
                "after": new_title,
            })
        else:
            sim = _similarity(old_title, new_title)
            if sim < 0.5:
                # Rule 7: Significant title change
                changes.append({
                    "rule": 7,
                    "severity": "warning",
                    "field": "title",
                    "description": f"Title changed significantly ({1 - sim:.0%} different)",
                    "before": old_title,
                    "after": new_title,
                })
            else:
                # Rule 14: Minor title tweak
                changes.append({
                    "rule": 14,
                    "severity": "info",
                    "field": "title",
                    "description": f"Minor title tweak ({1 - sim:.0%} different)",
                    "before": old_title,
                    "after": new_title,
                })

    # Rules 8 & 15: Meta description
    old_desc = previous.get("meta_description", "")
    new_desc = current.get("meta_description", "")
    if old_desc != new_desc:
        sim = _similarity(old_desc, new_desc)
        if sim < 0.5:
            changes.append({
                "rule": 8,
                "severity": "warning",
                "field": "meta_description",
                "description": f"Meta description changed significantly ({1 - sim:.0%} different)",
                "before": old_desc,
                "after": new_desc,
            })
        else:
            changes.append({
                "rule": 15,
                "severity": "info",
                "field": "meta_description",
                "description": f"Minor meta description tweak ({1 - sim:.0%} different)",
                "before": old_desc,
                "after": new_desc,
            })

    # Rule 9: H1 changed
    old_h1 = previous.get("h1", [])
    new_h1 = current.get("h1", [])
    if old_h1 != new_h1:
        changes.append({
            "rule": 9,
            "severity": "warning",
            "field": "h1",
            "description": "H1 tag(s) changed",
            "before": old_h1,
            "after": new_h1,
        })

    # Rule 10: Headings structure changed
    if previous.get("headings_hash") != current.get("headings_hash"):
        changes.append({
            "rule": 10,
            "severity": "warning",
            "field": "headings_hash",
            "description": "Heading structure changed (H1/H2/H3 hash differs)",
            "before": previous.get("headings_hash"),
            "after": current.get("headings_hash"),
        })

    # Rules 6 & 11: Schema markup
    old_schema_count = previous.get("schema_count", 0)
    new_schema_count = current.get("schema_count", 0)
    old_schema_hash = previous.get("schema_hash")
    new_schema_hash = current.get("schema_hash")
    if old_schema_hash != new_schema_hash or old_schema_count != new_schema_count:
        if old_schema_count > 0 and new_schema_count == 0:
            # Rule 6: All schema removed
            changes.append({
                "rule": 6,
                "severity": "critical",
                "field": "schema_count",
                "description": f"All schema markup removed ({old_schema_count} blocks → 0)",
                "before": old_schema_count,
                "after": new_schema_count,
            })
        else:
            # Rule 11: Schema changed but not fully removed
            changes.append({
                "rule": 11,
                "severity": "warning",
                "field": "schema_count",
                "description": f"Schema markup changed ({old_schema_count} → {new_schema_count} blocks)",
                "before": old_schema_count,
                "after": new_schema_count,
            })

    # Rules 12 & 17: Word count
    old_wc = previous.get("word_count", 0)
    new_wc = current.get("word_count", 0)
    if old_wc != new_wc and old_wc > 0:
        pct = _pct_change(old_wc, new_wc)
        if pct > 20 and new_wc < old_wc:
            # Rule 12: Word count dropped >20%
            changes.append({
                "rule": 12,
                "severity": "warning",
                "field": "word_count",
                "description": f"Word count dropped {pct:.0f}% ({old_wc} → {new_wc})",
                "before": old_wc,
                "after": new_wc,
            })
        elif pct > 0:
            # Rule 17: Word count changed within 20%
            direction = "increased" if new_wc > old_wc else "decreased"
            changes.append({
                "rule": 17,
                "severity": "info",
                "field": "word_count",
                "description": f"Word count {direction} {pct:.0f}% ({old_wc} → {new_wc})",
                "before": old_wc,
                "after": new_wc,
            })

    # Rules 13 & 16: Internal link count
    old_links = previous.get("internal_link_count", 0)
    new_links = current.get("internal_link_count", 0)
    if old_links != new_links and old_links > 0:
        pct = _pct_change(old_links, new_links)
        if pct > 30:
            # Rule 13: >30% change
            changes.append({
                "rule": 13,
                "severity": "warning",
                "field": "internal_link_count",
                "description": f"Internal link count changed {pct:.0f}% ({old_links} → {new_links})",
                "before": old_links,
                "after": new_links,
            })
        elif pct >= 10:
            # Rule 16: 10–30% change
            changes.append({
                "rule": 16,
                "severity": "info",
                "field": "internal_link_count",
                "description": f"Internal link count changed {pct:.0f}% ({old_links} → {new_links})",
                "before": old_links,
                "after": new_links,
            })

    changes.sort(key=lambda c: (SEVERITY_ORDER.get(c["severity"], 99), c["rule"]))
    return changes


def compare(url: str, db_path: str) -> dict:
    baseline = _latest(url, db_path)
    if not baseline:
        return {"url": url, "error": "No baseline found. Run baseline first."}
    captured_at, previous = baseline
    current = capture(url)
    if current.get("error"):
        return current

    changes = _apply_rules(previous, current)

    return {
        "url": url,
        "baseline_captured_at": captured_at,
        "changes": changes,
        "changed": bool(changes),
    }


def report(url: str, db_path: str, output_json: bool = False) -> dict:
    """Generate a drift report comparing current page state to baseline."""
    baseline_data = _latest(url, db_path)
    if not baseline_data:
        return {"url": url, "error": "No baseline found. Run baseline first."}
    captured_at, previous = baseline_data
    current = capture(url)
    if current.get("error"):
        return current

    changes = _apply_rules(previous, current)
    grouped = {"critical": [], "warning": [], "info": []}
    for c in changes:
        grouped.setdefault(c["severity"], []).append(c)

    return {
        "url": url,
        "report_generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "baseline_captured_at": captured_at,
        "summary": {
            "total_changes": len(changes),
            "critical": len(grouped["critical"]),
            "warning": len(grouped["warning"]),
            "info": len(grouped["info"]),
        },
        "changes_by_severity": grouped,
        "changed": bool(changes),
    }


def _format_report_text(data: dict) -> str:
    """Format report data as human-readable text."""
    if data.get("error"):
        return f"Error: {data['error']}"

    lines = [
        f"SEO Drift Report — {data['url']}",
        f"{'=' * 60}",
        f"Report generated: {data['report_generated_at']}",
        f"Baseline from:    {data['baseline_captured_at']}",
        "",
    ]

    s = data["summary"]
    lines.append(f"Total changes: {s['total_changes']}  "
                 f"(Critical: {s['critical']}, Warning: {s['warning']}, Info: {s['info']})")
    lines.append("")

    severity_labels = {
        "critical": "🔴 CRITICAL — Immediate action required",
        "warning": "🟠 WARNING — Investigate this week",
        "info": "🔵 INFO — Monitor, no immediate action",
    }

    for sev in ("critical", "warning", "info"):
        items = data["changes_by_severity"].get(sev, [])
        if not items:
            continue
        lines.append(severity_labels[sev])
        lines.append("-" * 50)
        for item in items:
            lines.append(f"  Rule {item['rule']}: {item['description']}")
            lines.append(f"    Field:  {item['field']}")
            lines.append(f"    Before: {item['before']}")
            lines.append(f"    After:  {item['after']}")
            lines.append("")
        lines.append("")

    if not data["changed"]:
        lines.append("No drift detected — page matches baseline.")

    return "\n".join(lines)


def history(url: str, db_path: str) -> dict:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT captured_at, data FROM snapshots WHERE url = ? ORDER BY captured_at DESC, id DESC LIMIT 20",
            (url,),
        ).fetchall()
    return {
        "url": url,
        "snapshots": [
            {"captured_at": captured_at, "summary": json.loads(data)}
            for captured_at, data in rows
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Track SEO-critical element drift")
    parser.add_argument("command", choices=["baseline", "compare", "history", "report"])
    parser.add_argument("url", help="URL to monitor")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite database path")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if args.command == "baseline":
        data = save_baseline(args.url, args.db)
    elif args.command == "compare":
        data = compare(args.url, args.db)
    elif args.command == "report":
        data = report(args.url, args.db, output_json=args.json)
    else:
        data = history(args.url, args.db)

    if args.json:
        print(json.dumps(data, indent=2))
    elif args.command == "report":
        print(_format_report_text(data))
    elif data.get("error"):
        print(f"Error: {data['error']}")
        return 1
    else:
        print(json.dumps(data, indent=2))
    return 1 if data.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())

