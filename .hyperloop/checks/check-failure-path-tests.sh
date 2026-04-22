#!/usr/bin/env bash
# check-failure-path-tests.sh
#
# Scans the spec file(s) under review for THEN conditions that require
# failure-path / rollback behaviour and verifies that at least one test
# file contains an assertion on the expected NOT-called / rollback outcome.
#
# Usage:
#   ./check-failure-path-tests.sh <spec_file> [test_dir]
#
# Exit 0  — every detected failure-path THEN condition has a candidate test.
# Exit 1  — one or more failure-path THEN conditions have no matching test.
#
# The script uses heuristics, not AST analysis. Its job is to force a human
# review moment, not to give a definitive pass/fail on test quality.

set -euo pipefail

SPEC_FILE="${1:-}"
TEST_DIR="${2:-src/api/tests}"

if [[ -z "$SPEC_FILE" || ! -f "$SPEC_FILE" ]]; then
  echo "Usage: $0 <spec_file> [test_dir]" >&2
  echo "Error: spec file not found or not provided." >&2
  exit 1
fi

# ── 1. Extract lines from the spec that describe failure/rollback THEN conditions ─
FAILURE_THEN_PATTERNS=(
  "if any.*fail"
  "roll.*back"
  "rolls back"
  "before retry"
  "no partial state"
  "not.*called"
  "entire.*deletion.*rolls"
  "locks.*released"
)

echo "=== Scanning spec: $SPEC_FILE ==="

found_failure_conditions=0
missing_tests=0

for pattern in "${FAILURE_THEN_PATTERNS[@]}"; do
  matches=$(grep -in "$pattern" "$SPEC_FILE" 2>/dev/null || true)
  if [[ -n "$matches" ]]; then
    found_failure_conditions=1
    echo ""
    echo "--- Failure-path THEN condition detected (pattern: '$pattern') ---"
    echo "$matches"

    # Derive simple search terms from the pattern for test lookup
    # Strip regex metacharacters for a plain-text grep
    safe_term=$(echo "$pattern" | sed 's/\.\*/ /g; s/\\//g' | tr -s ' ')

    # Look for tests that assert NOT-called or rollback on this condition
    test_hits=$(grep -ril \
      -e "assert_not_called\|assert_never_called\|not_called\|rollback\|rolls_back\|side_effect.*Error\|side_effect.*Exception\|raises\|pytest.raises" \
      "$TEST_DIR" 2>/dev/null | head -5 || true)

    if [[ -z "$test_hits" ]]; then
      echo "  !! WARNING: No test files found that assert rollback/not-called behaviour."
      echo "  !! Searched: $TEST_DIR"
      echo "  !! You MUST add a test that makes a dependency raise mid-operation and"
      echo "  !! asserts that downstream operations were NOT called."
      missing_tests=$((missing_tests + 1))
    else
      echo "  ✓ Candidate test files (verify they cover THIS failure path):"
      echo "$test_hits" | sed 's/^/    /'
      echo "  ^ Manually confirm one of these tests the specific rollback scenario."
    fi
  fi
done

if [[ $found_failure_conditions -eq 0 ]]; then
  echo "No failure-path THEN conditions detected in spec. Nothing to verify."
  exit 0
fi

echo ""
if [[ $missing_tests -gt 0 ]]; then
  echo "FAIL: $missing_tests failure-path THEN condition(s) have no candidate test files."
  echo "Add failure-path tests before submitting."
  exit 1
else
  echo "PASS: All detected failure-path THEN conditions have candidate test files."
  echo "Manually verify each candidate test actually exercises the failure path."
  exit 0
fi
