#!/usr/bin/env bash
# Run each URL-based audit script sequentially (JSON on stdout per tool).
# Usage: bash scripts/run_individual_checks.sh https://example.com
# For one combined HTML dashboard, use: python scripts/generate_report.py URL -o report.html

set -euo pipefail
URL="${1:?Usage: $0 https://example.com}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/.." || exit 1
PY=python3

echo "=== robots_checker ===" && $PY scripts/robots_checker.py "$URL" --json | head -c 2000 && echo "
..."
echo "=== security_headers ===" && $PY scripts/security_headers.py "$URL" --json | head -c 1500 && echo "
..."
echo "=== social_meta ===" && $PY scripts/social_meta.py "$URL" --json | head -c 1500 && echo "
..."
echo "=== redirect_checker ===" && $PY scripts/redirect_checker.py "$URL" --json | head -c 1500 && echo "
..."
echo "=== llms_txt_checker ===" && $PY scripts/llms_txt_checker.py "$URL" --json | head -c 1500 && echo "
..."
echo "=== broken_links (sample) ===" && $PY scripts/broken_links.py "$URL" --workers 3 --timeout 8 --json | head -c 2500 && echo "
..."
echo "=== internal_links ===" && $PY scripts/internal_links.py "$URL" --depth 1 --max-pages 10 --json | head -c 2500 && echo "
..."
echo "=== pagespeed (may fail without API / network) ===" && $PY scripts/pagespeed.py "$URL" --strategy mobile --json | head -c 2000 && echo "
..." || true
echo "=== entity_checker ===" && $PY scripts/entity_checker.py "$URL" --json | head -c 2000 && echo "
..."
echo "=== link_profile ===" && $PY scripts/link_profile.py "$URL" --max-pages 10 --json | head -c 2500 && echo "
..."
echo "=== hreflang_checker ===" && $PY scripts/hreflang_checker.py "$URL" --json | head -c 2000 && echo "
..."
echo "=== duplicate_content ===" && $PY scripts/duplicate_content.py "$URL" --json | head -c 2500 && echo "
..."
echo "=== sitemap_checker ===" && $PY scripts/sitemap_checker.py "$URL" --json | head -c 2000 && echo "
..."
echo "=== local_signals_checker ===" && $PY scripts/local_signals_checker.py "$URL" --json | head -c 2000 && echo "
..."
echo "=== indexnow_checker (probe) ===" && $PY scripts/indexnow_checker.py "$URL" --probe --json | head -c 2000 && echo "
..."
echo "=== article_seo ===" && $PY scripts/article_seo.py "$URL" --json | head -c 2000 && echo "
..."

TMP=$(mktemp -t seoauditXXXX.html)
trap 'rm -f "$TMP"' EXIT
if curl -fsSL --max-time 20 "$URL" -o "$TMP" 2>/dev/null && [ -s "$TMP" ]; then
  echo "=== parse_html ===" && $PY scripts/parse_html.py "$TMP" --url "$URL" --json | head -c 2000 && echo "
..."
  echo "=== readability ===" && $PY scripts/readability.py "$TMP" --json | head -c 1500 && echo "
..."
  echo "=== validate_schema ===" && $PY scripts/validate_schema.py "$TMP" --json | head -c 2000 && echo "
..."
  echo "=== image_checker ===" && $PY scripts/image_checker.py "$TMP" --base-url "$URL" --json | head -c 2000 && echo "
..."
else
  echo "=== Skipped HTML-file scripts (fetch failed): parse_html, readability, validate_schema, image_checker ==="
fi

echo ""
echo "Done. Truncated output for readability; omit '| head' in this script for full JSON."
