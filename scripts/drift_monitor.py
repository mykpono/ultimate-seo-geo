#!/usr/bin/env python3
"""SEO drift baseline, compare, and history snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from fetch_page import fetch_page


DEFAULT_DB = os.path.join(os.getcwd(), ".seo-drift.sqlite3")


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


def compare(url: str, db_path: str) -> dict:
    baseline = _latest(url, db_path)
    if not baseline:
        return {"url": url, "error": "No baseline found. Run baseline first."}
    captured_at, previous = baseline
    current = capture(url)
    if current.get("error"):
        return current

    watched_fields = (
        "status_code",
        "title",
        "meta_description",
        "canonical",
        "robots",
        "h1",
        "headings_hash",
        "schema_hash",
        "schema_count",
        "internal_link_count",
    )
    changes = []
    for field in watched_fields:
        if previous.get(field) != current.get(field):
            severity = "critical" if field in {"status_code", "canonical", "robots"} else "warning"
            changes.append({
                "severity": severity,
                "field": field,
                "before": previous.get(field),
                "after": current.get(field),
            })

    return {
        "url": url,
        "baseline_captured_at": captured_at,
        "changes": changes,
        "changed": bool(changes),
    }


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
    parser.add_argument("command", choices=["baseline", "compare", "history"])
    parser.add_argument("url", help="URL to monitor")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite database path")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if args.command == "baseline":
        data = save_baseline(args.url, args.db)
    elif args.command == "compare":
        data = compare(args.url, args.db)
    else:
        data = history(args.url, args.db)

    if args.json:
        print(json.dumps(data, indent=2))
    elif data.get("error"):
        print(f"Error: {data['error']}")
        return 1
    else:
        print(json.dumps(data, indent=2))
    return 1 if data.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())

