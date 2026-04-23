#!/usr/bin/env bash
# check-frontend-test-infrastructure.sh
#
# Verifies that frontend test infrastructure (vitest) is installed in the
# dev-ui package before Vue component code has been written. A task that adds
# Vue components without configuring vitest cannot satisfy the TDD mandate —
# tests cannot be written without a test runner.
#
# This check is distinct from check-frontend-tests-exist.sh:
#   check-frontend-test-infrastructure.sh  → is vitest configured at all?
#   check-frontend-tests-exist.sh          → do test files exist?
#
# Usage:
#   ./check-frontend-test-infrastructure.sh [ui_dir]
#
# Exit 0  — no UI source files, or vitest is configured in package.json.
# Exit 1  — UI source files exist but vitest is not in package.json.

set -euo pipefail

UI_DIR="${1:-src/dev-ui}"
PACKAGE_JSON="$UI_DIR/package.json"

# Only enforce if the current task (branch) actually changed UI files.
# Pre-existing UI files from merged PRs are not the current task's
# responsibility. Detect the base branch (alpha → main fallback).
if [[ -z "${BASE_BRANCH:-}" ]]; then
  if git rev-parse --verify origin/alpha &>/dev/null; then
    BASE_BRANCH="origin/alpha"
  elif git rev-parse --verify origin/main &>/dev/null; then
    BASE_BRANCH="origin/main"
  else
    echo "ERROR: Neither origin/alpha nor origin/main found. Cannot determine base branch." >&2
    exit 1
  fi
fi

if ! git rev-parse --verify "${BASE_BRANCH}" &>/dev/null; then
  echo "ERROR: BASE_BRANCH '${BASE_BRANCH}' does not exist. Cannot run UI diff." >&2
  exit 1
fi

# Capture git diff separately so real git errors are surfaced, not masked.
git_diff_output=$(git diff "${BASE_BRANCH}...HEAD" --name-only -- "$UI_DIR") || {
  echo "ERROR: git diff '${BASE_BRANCH}...HEAD' -- '$UI_DIR' failed unexpectedly." >&2
  exit 1
}

task_ui_changes=$(echo "$git_diff_output" \
  | grep -E '\.(vue|ts|js)$' \
  | grep -v node_modules \
  | grep -v '\.nuxt' \
  | grep -v dist \
  | head -1 || true)

if [[ -z "$task_ui_changes" ]]; then
  echo "No UI files changed in this task. Skipping frontend infrastructure check."
  exit 0
fi

# If there are no UI source files, nothing to enforce.
# NOTE: counts *.vue, *.ts, AND *.js — same file-type set as task_ui_changes above.
ui_source_count=$(find "$UI_DIR" \
  \( -name "*.vue" -o -name "*.ts" -o -name "*.js" \) 2>/dev/null \
  | grep -v node_modules \
  | grep -v "\.nuxt" \
  | grep -v dist \
  | wc -l || echo 0)

if [[ "$ui_source_count" -eq 0 ]]; then
  echo "No UI source files found in $UI_DIR. Nothing to check."
  exit 0
fi

echo "=== Checking for frontend test infrastructure in: $UI_DIR ==="
echo "    ($ui_source_count UI source files found)"

if [[ ! -f "$PACKAGE_JSON" ]]; then
  echo "FAIL: $PACKAGE_JSON not found. Cannot verify vitest configuration."
  exit 1
fi

# Check that vitest appears in devDependencies or dependencies
if grep -q "vitest" "$PACKAGE_JSON"; then
  echo "PASS: vitest found in $PACKAGE_JSON."
  exit 0
else
  echo ""
  echo "FAIL: $ui_source_count Vue/TS source files exist but vitest is NOT"
  echo "      configured in $PACKAGE_JSON."
  echo ""
  echo "The TDD mandate requires test infrastructure BEFORE component code."
  echo "Minimum setup:"
  echo "  cd $UI_DIR"
  echo "  npm install --save-dev vitest @vue/test-utils @vitejs/plugin-vue"
  echo "  # Add 'test': 'vitest' script to package.json"
  echo ""
  echo "Add vitest FIRST, then write tests, then write components."
  exit 1
fi
