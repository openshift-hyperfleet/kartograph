#!/usr/bin/env bash
# check-no-test-regressions.sh
#
# Fails if any test file that existed on the base branch has been deleted or
# had lines removed in the current branch. Deleting or truncating passing tests
# is a TDD violation regardless of implementation quality.
#
# Usage:
#   ./check-no-test-regressions.sh [base_branch]
#
# Exit 0  — no test regressions detected.
# Exit 1  — one or more test files deleted or truncated.

set -euo pipefail

# Detect base branch: accept explicit argument or auto-detect.
BASE_BRANCH="${1:-}"
if [[ -z "$BASE_BRANCH" ]]; then
  for candidate in alpha main master; do
    if git show-ref --verify --quiet "refs/heads/$candidate" 2>/dev/null || \
       git show-ref --verify --quiet "refs/remotes/origin/$candidate" 2>/dev/null; then
      BASE_BRANCH="$candidate"
      break
    fi
  done
fi

if [[ -z "$BASE_BRANCH" ]]; then
  echo "WARNING: Could not detect base branch. Skipping test regression check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping check."
  exit 0
fi

echo "=== Checking for deleted or truncated test files (base: $BASE_BRANCH @ $MERGE_BASE) ==="

# 1. Find deleted test files
deleted_tests=$(git diff --name-only --diff-filter=D "$MERGE_BASE" HEAD -- \
  '*/tests/*.py' '*/tests/**/*.py' \
  '*.test.ts' '*.spec.ts' '*.test.js' '*.spec.js' \
  2>/dev/null || true)

# 2. Find test files with lines removed (net negative line count)
#    A file that shrinks may have had tests removed without full deletion.
shrunk_tests=""
changed_tests=$(git diff --name-only "$MERGE_BASE" HEAD -- \
  '*/tests/*.py' '*/tests/**/*.py' \
  '*.test.ts' '*.spec.ts' '*.test.js' '*.spec.js' \
  2>/dev/null || true)

for f in $changed_tests; do
  # Count added vs removed lines for this file
  added=$(git diff "$MERGE_BASE" HEAD -- "$f" 2>/dev/null | grep -c '^+[^+]' || true)
  removed=$(git diff "$MERGE_BASE" HEAD -- "$f" 2>/dev/null | grep -c '^-[^-]' || true)
  if [[ "$removed" -gt "$added" ]]; then
    net_removed=$(( removed - added ))
    shrunk_tests="${shrunk_tests}  $f  (net -${net_removed} lines)\n"
  fi
done

found=0

if [[ -n "$deleted_tests" ]]; then
  echo ""
  echo "--- DELETED test files ---"
  echo "$deleted_tests" | sed 's/^/  /'
  found=$((found + 1))
fi

if [[ -n "$shrunk_tests" ]]; then
  echo ""
  echo "--- Test files with NET LINE REMOVAL (lines deleted > lines added) ---"
  printf "%b" "$shrunk_tests"
  found=$((found + 1))
fi

echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: Test regressions detected."
  echo ""
  echo "Passing tests MUST NOT be deleted or truncated."
  echo "  - If a test is failing because the spec changed, update the test — do not delete it."
  echo "  - If a test covers a scenario now out of scope, raise a formal blocker instead."
  echo "  - If lines were removed to fix a merge conflict, restore the lost lines."
  echo ""
  echo "Restore the deleted/truncated tests from the base branch ('$BASE_BRANCH') before submitting."
  exit 1
else
  echo "PASS: No test regressions detected."
  exit 0
fi
