#!/usr/bin/env bash
# check-no-coming-soon-stubs.sh
#
# Fails if any source file in the given directory contains "Coming Soon" text
# or other common stub markers that indicate an unimplemented spec scenario.
#
# Usage:
#   ./check-no-coming-soon-stubs.sh [source_dir]
#
# Exit 0  — no stub markers found.
# Exit 1  — one or more stub markers found (unimplemented scenarios).

set -euo pipefail

SOURCE_DIR="${1:-src}"

STUB_PATTERNS=(
  "Coming Soon"
  "coming-soon"
  "coming_soon"
  "TODO: implement"
  "TODO: wire"
  "Not yet implemented"
  "# stub"
  "// stub"
  "emit.*toast.*Coming"
)

echo "=== Scanning for Coming Soon / stub markers in: $SOURCE_DIR ==="

found=0

for pattern in "${STUB_PATTERNS[@]}"; do
  # Search all source files, excluding node_modules, __pycache__, .git, dist
  hits=$(grep -rn \
    --include="*.vue" \
    --include="*.ts" \
    --include="*.js" \
    --include="*.py" \
    --include="*.html" \
    --exclude-dir=node_modules \
    --exclude-dir=__pycache__ \
    --exclude-dir=.git \
    --exclude-dir=dist \
    --exclude-dir=".nuxt" \
    --exclude-dir=.venv \
    "$pattern" "$SOURCE_DIR" 2>/dev/null || true)

  if [[ -n "$hits" ]]; then
    echo ""
    echo "--- Stub marker detected (pattern: '$pattern') ---"
    echo "$hits"
    found=$((found + 1))
  fi
done

echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: $found stub pattern(s) found in source files."
  echo "Stubs and 'Coming Soon' placeholders are NOT acceptable implementations."
  echo "Either implement the scenario fully or raise a scope blocker before submitting."
  exit 1
else
  echo "PASS: No stub markers found."
  exit 0
fi
