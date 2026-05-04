#!/usr/bin/env bash
# check-route-handler-mock-coverage.sh
#
# Detects test files that use bare Mock() (no spec= argument) for
# application-layer collaborators (services, appliers, repositories).
#
# WHY THIS MATTERS
# ----------------
# Bare Mock() objects accept any attribute access and any method call, returning
# further Mocks. This means validation logic inside the real collaborator is NEVER
# exercised. If a domain method gains a new required constraint (e.g.,
# validate_operation() now requires knowledge_graph_id), the tests will keep
# passing even though the real call path is broken.
#
# Two patterns cause regressions to hide:
#   1. Route test mocks the whole service → service/domain validation skipped.
#   2. Service test mocks the applier → applier/domain validation skipped.
#
# Mock(spec=RealClass) enforces the real interface and raises AttributeError on
# invented methods, providing a minimal safety net. A real Fake* class is better
# still because it exercises actual logic paths.
#
# PATTERNS CAUGHT
# ---------------
#   mock_service = Mock()                     # BARE — no spec
#   mock_applier = AsyncMock()                # BARE — no spec
#   service = MagicMock()                     # BARE — no spec
#
# PATTERNS ALLOWED
# ----------------
#   mock_service = Mock(spec=MutationService) # SPEC'D — interface enforced
#   mock_applier = AsyncMock(spec=Applier)    # SPEC'D — interface enforced
#   service = FakeMutationService()           # REAL FAKE — logic exercised
#
# SCOPE
# -----
# Section 1 (BLOCKING): Route/handler test files — bare service mocks.
#   Any new bare Mock() for a service in a route test is a hard FAIL.
#
# Section 2 (WARNING): All unit test files — bare applier mocks.
#   Appliers contain domain validation; bare mocks hide validate_* regressions.
#   Pre-existing bare applier mocks produce a WARNING (not a hard FAIL) so
#   legacy technical debt doesn't block unrelated tasks. However the verifier
#   MUST manually check whether domain validation changes affect mocked paths.
#
# Usage:
#   ./check-route-handler-mock-coverage.sh [test_dir]
#
# Exit 0  — no hard FAIL; warnings may still be printed.
# Exit 1  — one or more route test files use bare Mock()/AsyncMock() for services.

set -euo pipefail

TEST_DIR="${1:-src/api/tests}"

echo "=== Scanning tests for bare Mock()/AsyncMock() on domain collaborators ==="
echo "    Test dir: $TEST_DIR"
echo ""

blocking_failures=0
warnings=0

# ── Section 1 (BLOCKING): Route / handler test files ──────────────────────────
echo "-- Section 1 [BLOCKING]: Route/handler test files (bare service mocks) --"
echo ""

ROUTE_COLLABORATOR_PATTERNS=(
  "mock.*service\s*=\s*Mock\(\)"
  "mock.*service\s*=\s*AsyncMock\(\)"
  "mock.*service\s*=\s*MagicMock\(\)"
  "mock.*applier\s*=\s*Mock\(\)"
  "mock.*applier\s*=\s*AsyncMock\(\)"
  "mock.*applier\s*=\s*MagicMock\(\)"
  "mock.*repo\s*=\s*Mock\(\)"
  "mock.*repo\s*=\s*AsyncMock\(\)"
  "mock.*repository\s*=\s*Mock\(\)"
  "mock.*repository\s*=\s*AsyncMock\(\)"
  "mock.*store\s*=\s*Mock\(\)"
  "mock.*store\s*=\s*AsyncMock\(\)"
)

ROUTE_FILE_PATTERNS=(
  "test_*route*"
  "test_*endpoint*"
  "test_*router*"
  "test_*api*"
  "test_*handler*"
)

route_test_files=()
for pattern in "${ROUTE_FILE_PATTERNS[@]}"; do
  while IFS= read -r -d '' f; do
    route_test_files+=("$f")
  done < <(find "$TEST_DIR" -name "${pattern}.py" -print0 2>/dev/null || true)
done

if [[ ${#route_test_files[@]} -gt 0 ]]; then
  mapfile -t route_test_files < <(printf '%s\n' "${route_test_files[@]}" | sort -u)
fi

if [[ ${#route_test_files[@]} -eq 0 ]]; then
  echo "  No route/endpoint test files found. Skipping Section 1."
else
  echo "  Found ${#route_test_files[@]} route test file(s)."
  echo ""

  for test_file in "${route_test_files[@]}"; do
    file_flagged=0

    for pattern in "${ROUTE_COLLABORATOR_PATTERNS[@]}"; do
      hits=$(grep -inP "$pattern" "$test_file" 2>/dev/null || true)

      if [[ -n "$hits" ]]; then
        bare_hits=$(echo "$hits" | grep -v "spec=" || true)

        if [[ -n "$bare_hits" ]]; then
          if [[ $file_flagged -eq 0 ]]; then
            echo "  [FAIL] Bare mock in route test: $test_file"
            file_flagged=1
          fi
          echo "$bare_hits" | sed 's/^/    /'
          blocking_failures=$((blocking_failures + 1))
        fi
      fi
    done

    if [[ $file_flagged -eq 1 ]]; then
      echo ""
      echo "  FIX: Replace bare Mock()/AsyncMock() with one of:"
      echo "    Mock(spec=RealServiceClass)       # enforces interface"
      echo "    AsyncMock(spec=RealServiceClass)  # enforces interface + async"
      echo "    FakeRealServiceClass()            # preferred: exercises real logic"
      echo ""
    fi
  done

  if [[ $blocking_failures -eq 0 ]]; then
    echo "  ✓ Section 1 PASS: No bare service mocks in route test files."
  fi
fi

echo ""

# ── Section 2 (WARNING): All unit tests — bare applier mocks ──────────────────
# Appliers contain domain validation logic (e.g., validate_operation()).
# Mocking them at the service-test layer hides validation regressions.
# Pre-existing bare applier mocks are reported as warnings, not hard failures,
# to avoid blocking unrelated tasks with legacy technical debt.
# The VERIFIER must manually inspect whether any domain validation changes
# affect code paths that reach these mocked appliers.
echo "-- Section 2 [WARNING]: Unit test files (bare applier mocks hiding domain validation) --"
echo ""

APPLIER_PATTERNS=(
  "mock.*applier\s*=\s*Mock\(\)"
  "mock.*applier\s*=\s*AsyncMock\(\)"
  "mock.*applier\s*=\s*MagicMock\(\)"
)

all_unit_test_files=()
if [[ -d "$TEST_DIR/unit" ]]; then
  while IFS= read -r -d '' f; do
    all_unit_test_files+=("$f")
  done < <(find "$TEST_DIR/unit" -name "test_*.py" -print0 2>/dev/null || true)
fi

if [[ ${#all_unit_test_files[@]} -eq 0 ]]; then
  echo "  No unit test files found under $TEST_DIR/unit. Skipping Section 2."
else
  echo "  Scanning ${#all_unit_test_files[@]} unit test file(s) for bare applier mocks."
  echo ""

  for test_file in "${all_unit_test_files[@]}"; do
    file_flagged=0

    for pattern in "${APPLIER_PATTERNS[@]}"; do
      hits=$(grep -inP "$pattern" "$test_file" 2>/dev/null || true)

      if [[ -n "$hits" ]]; then
        bare_hits=$(echo "$hits" | grep -v "spec=" || true)

        if [[ -n "$bare_hits" ]]; then
          if [[ $file_flagged -eq 0 ]]; then
            echo "  [WARN] Bare applier mock in: $test_file"
            file_flagged=1
          fi
          echo "$bare_hits" | sed 's/^/    /'
          warnings=$((warnings + 1))
        fi
      fi
    done

    if [[ $file_flagged -eq 1 ]]; then
      echo ""
      echo "  WHY: Bare applier mocks bypass validate_operation() and similar domain"
      echo "  validation. New constraints in those methods will NOT be caught by these tests."
      echo ""
      echo "  ACTION (verifier): If this task modifies domain validation methods (validate_*,"
      echo "  apply_batch, etc.), manually verify each flagged file's mocked call path still"
      echo "  satisfies the new constraint. Require the implementer to upgrade to"
      echo "  Mock(spec=MutationApplier) or a real Fake* if the new validation is affected."
      echo ""
    fi
  done

  if [[ $warnings -eq 0 ]]; then
    echo "  ✓ Section 2 PASS: No bare applier mocks found in unit test files."
  fi
fi

echo ""
echo "=== Summary ==="
echo "  Section 1 (blocking) failures: $blocking_failures"
echo "  Section 2 (warning)  findings: $warnings"
echo ""

if [[ $blocking_failures -gt 0 ]]; then
  echo "FAIL: $blocking_failures bare Mock()/AsyncMock() instance(s) found for services"
  echo "      in route test files. Upgrade to Mock(spec=RealClass) or real fakes."
  exit 1
else
  if [[ $warnings -gt 0 ]]; then
    echo "PASS (with warnings): No blocking failures. However, $warnings bare applier"
    echo "      mock(s) exist in unit test files. Verifier must manually check whether"
    echo "      any domain validation changes in this task affect those mocked paths."
  else
    echo "PASS: No bare Mock()/AsyncMock() for domain collaborators found."
  fi
  exit 0
fi
