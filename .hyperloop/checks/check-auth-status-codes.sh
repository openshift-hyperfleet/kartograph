#!/usr/bin/env bash
# check-auth-status-codes.sh
#
# Flags integration tests that assert HTTP 403 in authorization-related test files.
#
# Rationale: This codebase uses a "no distinction between unauthorized and
# missing" security pattern, meaning many authorization failures are intentionally
# returned as 404, not 403. An integration test asserting 403 for an
# authorization scenario is often wrong — the spec (and corresponding unit test)
# will say 404.
#
# This script does NOT auto-fail on every 403 (some are legitimately correct).
# It prints a list of matches so the verifier can manually cross-check each one
# against the spec's THEN block and the corresponding route unit test.
#
# Exit 0 if no 403 assertions are found in integration auth tests.
# Exit 1 if any are found (verifier must review each one before approving).

set -euo pipefail

INTEGRATION_DIR="src/api/tests/integration"

if [[ ! -d "$INTEGRATION_DIR" ]]; then
  echo "INFO: No integration test directory found at $INTEGRATION_DIR — skipping check."
  exit 0
fi

# Find 403 assertions in any integration test file whose name suggests
# authorization/permission/access testing.
MATCHES=$(grep -rn "status_code == 403\|status_code==403\|assert.*403" \
  --include="*auth*" \
  --include="*permission*" \
  --include="*access*" \
  "$INTEGRATION_DIR" 2>/dev/null || true)

if [[ -z "$MATCHES" ]]; then
  echo "OK: No HTTP 403 assertions found in integration authorization tests."
  exit 0
fi

echo "REVIEW REQUIRED: The following integration test(s) assert HTTP 403 in"
echo "authorization-related files. This codebase uses 404 for many unauthorized"
echo "scenarios (\"no distinction between unauthorized and missing\" pattern)."
echo ""
echo "For each line below, verify against:"
echo "  1. The spec THEN block for the scenario"
echo "  2. The corresponding unit test for the same route handler"
echo ""
echo "$MATCHES"
echo ""
echo "If the spec and unit test both say 404, the integration test is WRONG."
echo "If the spec explicitly permits 403, annotate it and re-run after fixing."
exit 1
