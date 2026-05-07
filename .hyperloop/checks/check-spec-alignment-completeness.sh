#!/usr/bin/env bash
# check-spec-alignment-completeness.sh
#
# Verifies that every "### Requirement:" section in a spec file is referenced by
# name in at least one of the provided test files.
#
# This catches the failure mode where an implementer builds N-1 of N requirements
# and the test suite shows all-green because neither the missing feature NOR a test
# for it was ever written. All other existing checks (check-pages-have-tests.sh,
# check-frontend-scenario-labels.sh) require something to exist before checking it —
# this check uses the SPEC as the source of truth, not the implementation.
#
# Root cause of task-151 FAIL: Requirement 12 (Graph Visualizer) was absent from
# both the implementation and the test suite. check-pages-have-tests.sh did not flag
# it because the page file was never created. check-frontend-scenario-labels.sh did
# not flag it because the implementer ran it only against sections they believed they
# had implemented. 2615 tests passed; the feature was 100% absent.
#
# Usage:
#   ./check-spec-alignment-completeness.sh <spec-file> <test-file> [test-file ...]
#
# Typical invocation for a dev-ui spec:
#   bash .hyperloop/checks/check-spec-alignment-completeness.sh \
#       specs/ui/experience.spec.md \
#       src/dev-ui/app/tests/*.test.ts
#
# Exit 0 — every requirement section is referenced in at least one test file.
# Exit 1 — one or more requirement sections have no test reference.

set -euo pipefail

if [[ $# -eq 0 ]]; then
  # No-arg invocation from check-new-checks-pass-on-head.sh — nothing to check.
  echo "PASS: No arguments provided — nothing to check."
  echo "Usage: $0 <spec-file> <test-file> [test-file ...]"
  exit 0
fi

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <spec-file> <test-file> [test-file ...]"
  exit 1
fi

SPEC_FILE="$1"
shift
TEST_FILES=("$@")

if [[ ! -f "$SPEC_FILE" ]]; then
  echo "FAIL: Spec file not found: $SPEC_FILE"
  exit 1
fi

missing_test_files=()
for tf in "${TEST_FILES[@]}"; do
  if [[ ! -f "$tf" ]]; then
    missing_test_files+=("$tf")
  fi
done
if [[ ${#missing_test_files[@]} -gt 0 ]]; then
  echo "FAIL: The following test files were not found:"
  for tf in "${missing_test_files[@]}"; do
    echo "  $tf"
  done
  exit 1
fi

echo "=== Checking spec requirement section coverage ==="
echo "    Spec      : $SPEC_FILE"
echo "    Test files: ${#TEST_FILES[@]}"
echo ""

# Extract all requirement section names from the spec.
# Pattern: "### Requirement: <name>" (with up to 3 leading hashes, optional whitespace)
mapfile -t REQUIREMENT_NAMES < <(
  grep -E "^#{1,3}\s*Requirement:\s+" "$SPEC_FILE" 2>/dev/null \
    | sed -E 's/^#{1,3}\s*Requirement:\s+//' \
    | sed 's/[[:space:]]*$//'
)

if [[ ${#REQUIREMENT_NAMES[@]} -eq 0 ]]; then
  echo "PASS: No '### Requirement:' headers found in $SPEC_FILE — nothing to check."
  exit 0
fi

echo "Found ${#REQUIREMENT_NAMES[@]} requirement section(s) in spec:"
for r in "${REQUIREMENT_NAMES[@]}"; do
  echo "  - $r"
done
echo ""

covered=0
missing=0
missing_names=()

for req in "${REQUIREMENT_NAMES[@]}"; do
  matched=false
  for tf in "${TEST_FILES[@]}"; do
    if grep -qi "$req" "$tf" 2>/dev/null; then
      matched=true
      break
    fi
  done

  if [[ "$matched" == "true" ]]; then
    echo "  COVERED : $req"
    covered=$((covered + 1))
  else
    echo "  MISSING : $req"
    missing=$((missing + 1))
    missing_names+=("$req")
  fi
done

echo ""
echo "Results: $covered covered, $missing missing out of ${#REQUIREMENT_NAMES[@]} total."
echo ""

if [[ $missing -gt 0 ]]; then
  echo "FAIL: $missing requirement section(s) have no reference in any test file:"
  for r in "${missing_names[@]}"; do
    echo "  - \"$r\""
  done
  echo ""
  echo "Every '### Requirement:' section in the spec MUST be referenced by name in"
  echo "at least one test file. A requirement with no test reference means the feature"
  echo "was silently omitted — neither the implementation nor a test for it was written,"
  echo "and no other check will detect this gap."
  echo ""
  echo "Steps to fix:"
  echo "  1. Implement the missing requirement."
  echo "  2. Write a spec-alignment test that includes the requirement name as a"
  echo "     substring in a describe() or it() label."
  echo "  3. Re-run: bash .hyperloop/checks/check-spec-alignment-completeness.sh \\"
  echo "         <spec-file> src/dev-ui/app/tests/*.test.ts"
  exit 1
else
  echo "PASS: All $covered requirement section(s) are referenced in test files."
  exit 0
fi
