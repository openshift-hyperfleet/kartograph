#!/usr/bin/env bash
# check-idempotency-tests.sh
#
# When a spec mentions "idempotent", "duplicate delivery", or "retry" in a
# THEN block, two categories of test are required:
#
#   (a) FILTERING test  — already-processed entries excluded from re-delivery.
#   (b) RE-EXECUTION test — handler/worker called TWICE with the same event;
#       final state is identical to a single successful run.
#
# This script checks that BOTH categories exist whenever the spec contains
# idempotency language. It uses heuristics — manual review is still required.
#
# Usage:
#   ./check-idempotency-tests.sh <spec_file> [test_dir]
#
# Exit 0 — both filtering AND re-execution candidate tests found (or no
#           idempotency requirement detected in spec).
# Exit 1 — idempotency requirement detected but one or both test categories
#           are missing.

set -euo pipefail

SPEC_FILE="${1:-}"
TEST_DIR="${2:-src/api/tests}"

if [[ -z "$SPEC_FILE" || ! -f "$SPEC_FILE" ]]; then
  echo "Usage: $0 <spec_file> [test_dir]" >&2
  echo "Error: spec file not found or not provided." >&2
  exit 1
fi

echo "=== Idempotency test coverage check: $SPEC_FILE ==="

# ── 1. Detect whether the spec has an idempotency THEN requirement ──────────
IDEMPOTENCY_PATTERNS=(
  "idempoten"
  "duplicate delivery"
  "duplicate.*side effect"
  "retry.*same.*state"
  "same final state"
  "no duplicate"
  "reprocess.*same"
)

spec_has_idempotency=0
for pattern in "${IDEMPOTENCY_PATTERNS[@]}"; do
  if grep -qi "$pattern" "$SPEC_FILE" 2>/dev/null; then
    spec_has_idempotency=1
    echo "  ✓ Idempotency requirement detected (matched: '$pattern')"
    break
  fi
done

if [[ $spec_has_idempotency -eq 0 ]]; then
  echo "No idempotency requirement detected in spec. Nothing to verify."
  exit 0
fi

failures=0

# ── 2. Check for FILTERING tests ────────────────────────────────────────────
# Patterns that indicate "already-processed entries are excluded".
FILTERING_TEST_PATTERNS=(
  "processed_at.*IS NULL"
  "already_processed"
  "excluded_from_fetch"
  "processed.*excluded"
  "skip.*processed"
  "filter.*processed"
  "not_redelivered"
)

echo ""
echo "--- Category (a): Filtering test (already-processed entries excluded) ---"
filtering_found=0
for pat in "${FILTERING_TEST_PATTERNS[@]}"; do
  hits=$(grep -ril "$pat" "$TEST_DIR" 2>/dev/null | head -3 || true)
  if [[ -n "$hits" ]]; then
    filtering_found=1
    echo "  ✓ Candidate filtering test(s) found (pattern: '$pat'):"
    echo "$hits" | sed 's/^/    /'
    break
  fi
done

# Broader fallback: any test asserting IS NULL on processed columns
if [[ $filtering_found -eq 0 ]]; then
  hits=$(grep -ril "IS NULL\|is_null\|processed_at" "$TEST_DIR" 2>/dev/null | head -3 || true)
  if [[ -n "$hits" ]]; then
    filtering_found=1
    echo "  ✓ Candidate filtering test(s) found (processed_at / IS NULL assertion):"
    echo "$hits" | sed 's/^/    /'
  fi
fi

if [[ $filtering_found -eq 0 ]]; then
  echo "  !! MISSING: No test found that asserts already-processed entries are"
  echo "  !!          excluded from re-delivery. Add a test that checks the"
  echo "  !!          'processed_at IS NULL' (or equivalent) filter is applied."
  failures=$((failures + 1))
fi

# ── 3. Check for RE-EXECUTION tests ─────────────────────────────────────────
# Patterns that indicate calling the handler/worker a second time with the
# same event and verifying the final state.
REEXECUTION_TEST_PATTERNS=(
  "call.*twice\|twice.*call"
  "second.*invocation\|invocation.*second"
  "duplicate.*invoc\|invoc.*duplicate"
  "retry.*same.*entry\|same.*entry.*retry"
  "idempoten.*handler\|handler.*idempoten"
  "second_call\|call_count.*2\|called_twice"
  "already.*written.*spicedb\|spicedb.*already"
  "no.*duplicate.*relationship\|relationship.*no.*duplicate"
  "partial.*failure.*retry\|retry.*partial.*failure"
  "simulate.*partial\|partial.*fail"
)

echo ""
echo "--- Category (b): Re-execution test (handler called twice, same safe state) ---"
reexec_found=0
for pat in "${REEXECUTION_TEST_PATTERNS[@]}"; do
  hits=$(grep -ril -E "$pat" "$TEST_DIR" 2>/dev/null | head -3 || true)
  if [[ -n "$hits" ]]; then
    reexec_found=1
    echo "  ✓ Candidate re-execution test(s) found (pattern: '$pat'):"
    echo "$hits" | sed 's/^/    /'
    break
  fi
done

if [[ $reexec_found -eq 0 ]]; then
  echo "  !! MISSING: No test found that exercises the duplicate-delivery scenario:"
  echo "  !!  1. Handler is invoked and writes side effects (e.g. SpiceDB relationship)."
  echo "  !!  2. Handler raises an exception BEFORE the entry is marked processed."
  echo "  !!  3. Worker retries — handler is invoked again with the same event."
  echo "  !!  4. Final state (side effects, DB row) is identical to a single"
  echo "  !!     successful run; no duplicates created."
  echo "  !! Add an integration test (or a unit test with a fake external client)"
  echo "  !! that explicitly exercises steps 1-4 above."
  failures=$((failures + 1))
fi

# ── 4. Result ────────────────────────────────────────────────────────────────
echo ""
if [[ $failures -gt 0 ]]; then
  echo "FAIL: $failures idempotency test category/categories are missing."
  echo "Both filtering AND re-execution tests are required when the spec"
  echo "specifies idempotency or duplicate-delivery safety."
  exit 1
else
  echo "PASS: Both filtering and re-execution candidate tests found."
  echo "Manually confirm each candidate test actually exercises its scenario."
  exit 0
fi
