#!/usr/bin/env bash
# check-frontend-tests-exist.sh
#
# Verifies that at least one frontend test file exists when the task touches
# Vue/UI source files. The absence of any frontend tests when UI code has been
# added or modified is a TDD violation.
#
# Usage:
#   ./check-frontend-tests-exist.sh [ui_source_dir] [ui_test_dir]
#
# Exit 0  — no UI source changes, or UI test files exist.
# Exit 1  — UI source files changed but zero test files found.

set -euo pipefail

UI_SOURCE_DIR="${1:-src/dev-ui}"
UI_TEST_DIR="${2:-src/dev-ui}"

# Only enforce if the current task (branch) actually changed UI files.
# Pre-existing UI files from merged PRs are not the current task's
# responsibility. Detect the base branch (alpha → main fallback).
if [[ -z "${BASE_BRANCH:-}" ]]; then
  if git rev-parse --verify origin/alpha &>/dev/null; then
    BASE_BRANCH="origin/alpha"
  else
    BASE_BRANCH="origin/main"
  fi
fi
task_ui_changes=$(git diff "${BASE_BRANCH}...HEAD" --name-only 2>/dev/null \
  | grep -E '\.(vue|ts|js)$' \
  | grep -v node_modules \
  | grep -v '\.nuxt' \
  | grep -v dist \
  | head -1 || true)

if [[ -z "$task_ui_changes" ]]; then
  echo "No UI files changed in this task. Skipping frontend tests check."
  exit 0
fi

# Check whether there are any Vue/TS source files in the UI directory
ui_source_count=$(find "$UI_SOURCE_DIR" \
  -name "*.vue" -o -name "*.ts" 2>/dev/null \
  | grep -v node_modules \
  | grep -v ".nuxt" \
  | grep -v dist \
  | wc -l || echo 0)

if [[ "$ui_source_count" -eq 0 ]]; then
  echo "No UI source files found in $UI_SOURCE_DIR. Nothing to check."
  exit 0
fi

echo "=== Checking for frontend tests in: $UI_TEST_DIR ==="
echo "    ($ui_source_count UI source files found in $UI_SOURCE_DIR)"

# Look for test files (vitest, jest, playwright component tests)
test_files=$(find "$UI_TEST_DIR" \
  \( -name "*.test.ts" -o -name "*.spec.ts" -o -name "*.test.js" -o -name "*.spec.js" \) \
  2>/dev/null \
  | grep -v node_modules \
  | grep -v ".nuxt" \
  | grep -v dist \
  | head -20 || true)

if [[ -z "$test_files" ]]; then
  echo ""
  echo "FAIL: UI source files exist but ZERO frontend test files were found."
  echo ""
  echo "The TDD mandate (AGENTS.md) applies to Vue/UI work."
  echo "For each UI scenario in the spec, write at least one component or unit test"
  echo "(vitest + @vue/test-utils or Playwright component test) BEFORE writing the"
  echo "component code."
  echo ""
  echo "Minimum setup:"
  echo "  cd $UI_SOURCE_DIR"
  echo "  # Add vitest + @vue/test-utils to devDependencies"
  echo "  # Create tests/<component>.test.ts for each spec scenario"
  exit 1
else
  test_count=$(echo "$test_files" | wc -l)
  echo "PASS: $test_count frontend test file(s) found."
  echo "$test_files" | sed 's/^/  /'
  exit 0
fi
