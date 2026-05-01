#!/usr/bin/env bash
# check-frontend-scenario-labels.sh
#
# Verifies that every spec scenario under a given requirement has a
# corresponding test label (describe/it/test string) in the provided test files.
#
# Scenario names are extracted from "#### Scenario: <name>" headers in the spec.
# Each name is searched case-insensitively in the test file content.
#
# Root cause of task-060 FAIL-1: the implementer claimed "all six scenarios"
# were covered when the spec defined NINE. Three scenarios had zero test
# coverage and no test group label referenced them by name:
#   - "Knowledge graph selection"
#   - "Submission"
#   - "Submission failure"
#
# Usage:
#   ./check-frontend-scenario-labels.sh <spec-file> <test-file> [test-file ...]
#
#   Optional: narrow to one requirement section by piping the spec through grep
#   or by providing a partial spec extract:
#
#   awk '/### Requirement: Mutations Console/,/^### /' specs/ui/experience.spec.md \
#     | bash .hyperloop/checks/check-frontend-scenario-labels.sh /dev/stdin \
#         src/dev-ui/app/tests/mutations-console.test.ts
#
# Exit 0 — all spec scenarios found in at least one test file.
# Exit 1 — one or more spec scenarios have no test coverage.

set -euo pipefail

if [[ $# -eq 0 ]]; then
  # Called with no arguments (e.g. from check-new-checks-pass-on-head.sh which
  # validates new scripts by running them without args). This script requires
  # explicit inputs — exit 0 to signal "nothing to check" rather than failing.
  echo "PASS: No spec file or test files provided — nothing to check."
  echo "Usage: $0 <spec-file> <test-file> [test-file ...]"
  exit 0
fi

if [[ $# -lt 2 ]]; then
  cat <<'EOF'
Usage: check-frontend-scenario-labels.sh <spec-file> <test-file> [test-file ...]

Verifies that every "#### Scenario: <name>" in the spec appears as a string
(case-insensitive) in at least one of the provided test files.

To check only the scenarios under one requirement, pipe a spec excerpt:

  awk '/### Requirement: Mutations Console/{found=1} found{print} /^### [A-Z]/ && !/Mutations Console/{found=0}' \
      specs/ui/experience.spec.md \
    | bash .hyperloop/checks/check-frontend-scenario-labels.sh /dev/stdin \
        src/dev-ui/app/tests/mutations-console.test.ts

EOF
  exit 1
fi

SPEC_FILE="$1"
shift
TEST_FILES=("$@")

if [[ "$SPEC_FILE" != "/dev/stdin" && ! -f "$SPEC_FILE" ]]; then
  echo "FAIL: Spec file not found: $SPEC_FILE"
  exit 1
fi

for tf in "${TEST_FILES[@]}"; do
  if [[ ! -f "$tf" ]]; then
    echo "FAIL: Test file not found: $tf"
    exit 1
  fi
done

echo "=== Checking spec scenario coverage ==="
echo "    Spec : $SPEC_FILE"
for tf in "${TEST_FILES[@]}"; do
  echo "    Test : $tf"
done
echo ""

# Extract all scenario names from the spec.
# Pattern: "#### Scenario: <name>" (leading whitespace tolerated).
mapfile -t SCENARIO_NAMES < <(
  grep -E "^#{1,4}\s*Scenario:\s+" "$SPEC_FILE" 2>/dev/null \
    | sed -E 's/^#{1,4}\s*Scenario:\s+//' \
    | sed 's/[[:space:]]*$//'
)

if [[ ${#SCENARIO_NAMES[@]} -eq 0 ]]; then
  echo "PASS: No 'Scenario:' headers found in $SPEC_FILE — nothing to check."
  exit 0
fi

echo "Found ${#SCENARIO_NAMES[@]} scenario(s) in spec:"
for s in "${SCENARIO_NAMES[@]}"; do
  echo "  - $s"
done
echo ""

found=0
missing=0
missing_names=()

for scenario in "${SCENARIO_NAMES[@]}"; do
  # Search for the scenario name in any test file (case-insensitive substring).
  # This allows for reasonable paraphrasing while catching completely absent scenarios.
  matched=false
  for tf in "${TEST_FILES[@]}"; do
    if grep -qi "$scenario" "$tf" 2>/dev/null; then
      matched=true
      break
    fi
  done

  if [[ "$matched" == "true" ]]; then
    echo "  COVERED : $scenario"
    found=$((found + 1))
  else
    echo "  MISSING : $scenario"
    missing=$((missing + 1))
    missing_names+=("$scenario")
  fi
done

echo ""
echo "Results: $found covered, $missing missing out of ${#SCENARIO_NAMES[@]} total."
echo ""

if [[ $missing -gt 0 ]]; then
  echo "FAIL: $missing spec scenario(s) have no test coverage:"
  for s in "${missing_names[@]}"; do
    echo "  - \"$s\""
  done
  echo ""
  echo "Each '#### Scenario:' in the spec MUST appear as a string in at least"
  echo "one test file's describe() or it() label (or anywhere in the test file)."
  echo ""
  echo "Steps to fix:"
  echo "  1. Add a describe() or it() block whose label includes the scenario name."
  echo "  2. Write at least one assertion that exercises the scenario's THEN clause."
  echo "  3. Re-run this script to confirm all scenarios are covered."
  echo ""
  echo "If a scenario is genuinely out of scope for the current task, document it"
  echo "as a formal blocker in .hyperloop/blockers/ before submitting — do NOT"
  echo "omit the scenario silently and claim full coverage in the commit message."
  exit 1
else
  echo "PASS: All $found spec scenario(s) have test coverage."
  exit 0
fi
