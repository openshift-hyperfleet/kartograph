#!/usr/bin/env bash
# check-frontend-tests-pass.sh
#
# Runs the frontend test suite (vitest) and fails if any test fails.
# check-frontend-tests-exist.sh verifies test FILES exist — this script
# verifies they actually PASS. A test that imports a non-existent export
# produces a TypeError at runtime; that failure is invisible to file-
# existence checks but fatal here.
#
# Usage:
#   ./check-frontend-tests-pass.sh [ui_dir]
#
# Exit 0  — all frontend tests pass (or no test suite is configured).
# Exit 1  — one or more frontend tests fail (including import errors).

set -euo pipefail

UI_DIR="${1:-src/dev-ui}"

if [[ ! -f "$UI_DIR/package.json" ]]; then
  echo "No package.json found at $UI_DIR. Skipping frontend test check."
  exit 0
fi

# Only proceed when a "test" script is declared
if ! python3 -c "
import json, sys
pkg = json.load(open(sys.argv[1]))
sys.exit(0 if 'test' in pkg.get('scripts', {}) else 1)
" "$UI_DIR/package.json" 2>/dev/null; then
  echo "No 'test' script declared in $UI_DIR/package.json. Skipping frontend test check."
  exit 0
fi

if ! command -v pnpm &>/dev/null; then
  echo "FAIL: pnpm is not installed. Cannot run frontend tests."
  exit 1
fi

# Detect missing node_modules BEFORE attempting to run tests.
#
# WHY: Without node_modules the vitest binary is absent and pnpm emits the
# opaque error "sh: line 1: vitest: command not found" with no indication of
# what went wrong.  In isolated worktrees (e.g. Hyperloop task agents) pnpm
# install is NOT run automatically on checkout — the dependency must be
# installed manually.  This guard provides a clear, actionable message before
# the test runner is even invoked.
#
# Observed in task-141: verifier blocked submission because vitest was missing;
# CI passed (external evidence the tests work) but the worktree was missing
# node_modules, causing a confusing environment mismatch.
if [[ ! -d "$UI_DIR/node_modules" ]]; then
  echo "FAIL: node_modules not found in $UI_DIR."
  echo ""
  echo "Dependencies must be installed before running tests."
  echo ""
  echo "Fix (run from the repo root):"
  echo "  cd $UI_DIR && pnpm install"
  echo ""
  echo "Then re-run this check:"
  echo "  bash .hyperloop/checks/check-frontend-tests-pass.sh"
  exit 1
fi

echo "=== Running frontend test suite in: $UI_DIR ==="
echo "    (CI=true disables vitest watch mode)"
echo ""

# Capture both stdout and stderr; preserve exit code.
# CI=true instructs vitest to run once and exit rather than enter watch mode.
set +e
(cd "$UI_DIR" && CI=true pnpm run test 2>&1)
exit_code=$?
set -e

echo ""
if [[ $exit_code -eq 0 ]]; then
  echo "PASS: All frontend tests passed."
  exit 0
else
  echo "FAIL: Frontend test suite exited with code $exit_code."
  echo ""
  echo "Common causes:"
  echo "  1. A test imports a named export that does not exist in the source module."
  echo "     Look for 'TypeError: X is not a function' or 'SyntaxError: The requested"
  echo "     module ... does not provide an export named ...' in the output above."
  echo "  2. A component or page test references UI state (e.g. selectedKgId) that"
  echo "     was never added to the page component — the page is missing the feature."
  echo "  3. A mock is missing for a composable used by the component under test."
  echo ""
  echo "The test suite must pass before submitting. Never submit with failing tests."
  exit 1
fi
