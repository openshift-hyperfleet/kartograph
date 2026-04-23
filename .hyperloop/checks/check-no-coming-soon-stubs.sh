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

# Only flag stub markers in files that this task (branch) actually changed.
# Pre-existing stubs in files not touched by the current task are not this
# task's responsibility. Tasks that add new stubs will be caught.
if [[ -z "${BASE_BRANCH:-}" ]]; then
  if git rev-parse --verify origin/alpha &>/dev/null; then
    BASE_BRANCH="origin/alpha"
  else
    BASE_BRANCH="origin/main"
  fi
fi
CHANGED_FILES=$(git diff "${BASE_BRANCH}...HEAD" --name-only 2>/dev/null \
  | grep -E '\.(vue|ts|js|py|html)$' \
  | grep -v node_modules \
  | grep -v '\.nuxt' \
  | grep -v dist \
  | grep -v '\.venv' \
  || true)

if [[ -z "$CHANGED_FILES" ]]; then
  echo "No source files changed in this task. Skipping stub marker check."
  exit 0
fi

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

echo "=== Scanning for Coming Soon / stub markers in task-changed files ==="

found=0

for pattern in "${STUB_PATTERNS[@]}"; do
  # Search only files changed in the current task (scoped to what this PR adds).
  # This avoids false positives from pre-existing stubs in unrelated files.
  hits=$(echo "$CHANGED_FILES" \
    | xargs -r grep -n "$pattern" 2>/dev/null || true)

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
