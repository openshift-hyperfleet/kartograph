#!/usr/bin/env bash
# check-no-test-regressions.sh
#
# Fails if any test file that existed on the base branch has been deleted or
# had lines removed in the current branch. Deleting or truncating passing tests
# is a TDD violation regardless of implementation quality.
#
# TWO COMPARISON PASSES:
#   Pass 1 (merge-base): detects regressions relative to when this branch was cut.
#   Pass 2 (alpha HEAD):  detects regressions where alpha's tests evolved AFTER
#                         the branch was cut but are missing or weaker on this
#                         branch. A branch that is within the rebase tolerance
#                         (≤5 commits behind) can still carry weaker tests than
#                         alpha if alpha gained test coverage in those commits.
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
  echo "FAIL (pass 1 — merge-base): Test regressions detected vs merge-base."
  echo ""
  echo "Passing tests MUST NOT be deleted or truncated."
  echo "  - If a test is failing because the spec changed, update the test — do not delete it."
  echo "  - If a test covers a scenario now out of scope, raise a formal blocker instead."
  echo "  - If lines were removed to fix a merge conflict, restore the lost lines."
  echo ""
  echo "Restore the deleted/truncated tests from the base branch ('$BASE_BRANCH') before submitting."
  exit 1
else
  echo "PASS (pass 1 — merge-base): No test regressions vs merge-base."
fi

# ---------------------------------------------------------------------------
# Pass 2: Compare against current alpha HEAD
#
# Alpha may have gained additional tests after this branch was cut. Even if
# pass 1 shows no regressions vs merge-base, the branch could be missing tests
# that alpha now carries.  A branch that is rebased within the ≤5 commit
# tolerance (check-branch-rebased-on-alpha.sh) can still be missing those tests.
# ---------------------------------------------------------------------------

ALPHA_HEAD=$(git rev-parse "$BASE_BRANCH" 2>/dev/null || true)

# Skip pass 2 if alpha HEAD == merge-base (branch is fully up-to-date)
if [[ -z "$ALPHA_HEAD" || "$ALPHA_HEAD" == "$MERGE_BASE" ]]; then
  echo ""
  echo "PASS (pass 2 — alpha HEAD): Branch is at merge-base; pass 2 not applicable."
  exit 0
fi

echo ""
echo "=== Pass 2: test files vs current $BASE_BRANCH HEAD ($ALPHA_HEAD) ==="

shrunk_vs_alpha=""
deleted_vs_alpha=""

# Enumerate test files that differ between alpha HEAD and this HEAD
changed_vs_alpha=$(git diff --name-only "$ALPHA_HEAD" HEAD -- \
  '*/tests/*.py' '*/tests/**/*.py' \
  '*.test.ts' '*.spec.ts' '*.test.js' '*.spec.js' \
  2>/dev/null || true)

for f in $changed_vs_alpha; do
  # Only consider files that exist in alpha HEAD (not new files we added)
  if ! git cat-file -e "${ALPHA_HEAD}:${f}" 2>/dev/null; then
    continue
  fi

  # File exists in alpha but is gone from HEAD → deletion regression
  if ! git cat-file -e "HEAD:${f}" 2>/dev/null; then
    deleted_vs_alpha="${deleted_vs_alpha}  $f  (present on $BASE_BRANCH, deleted on this branch)\n"
    continue
  fi

  # Count net line change between alpha HEAD and this HEAD for this file
  added_vs_alpha=$(git diff "$ALPHA_HEAD" HEAD -- "$f" 2>/dev/null | grep -c '^+[^+]' || true)
  removed_vs_alpha=$(git diff "$ALPHA_HEAD" HEAD -- "$f" 2>/dev/null | grep -c '^-[^-]' || true)

  if [[ "$removed_vs_alpha" -gt "$added_vs_alpha" ]]; then
    net_removed=$(( removed_vs_alpha - added_vs_alpha ))
    shrunk_vs_alpha="${shrunk_vs_alpha}  $f  (net -${net_removed} lines vs $BASE_BRANCH HEAD)\n"
  fi
done

found2=0

if [[ -n "$deleted_vs_alpha" ]]; then
  echo ""
  echo "--- Test files present on $BASE_BRANCH HEAD but DELETED on this branch ---"
  printf "%b" "$deleted_vs_alpha"
  found2=$((found2 + 1))
fi

if [[ -n "$shrunk_vs_alpha" ]]; then
  echo ""
  echo "--- Test files SMALLER than $BASE_BRANCH HEAD ---"
  echo "    These files have fewer net lines than what $BASE_BRANCH currently carries."
  echo "    This typically means $BASE_BRANCH gained tests after this branch was cut"
  echo "    and those tests are absent here. Cherry-picking this branch onto alpha"
  echo "    would REGRESS alpha's test suite."
  printf "%b" "$shrunk_vs_alpha"
  found2=$((found2 + 1))
fi

echo ""
if [[ $found2 -gt 0 ]]; then
  echo "FAIL (pass 2 — alpha HEAD): This branch has weaker tests than $BASE_BRANCH HEAD."
  echo ""
  echo "Merging or cherry-picking this branch onto alpha would regress the test suite."
  echo "Inspect the diff vs alpha for each file listed above:"
  echo "  git diff $BASE_BRANCH HEAD -- <file>"
  echo ""
  echo "Either:"
  echo "  (a) Rebase onto latest $BASE_BRANCH — the additional alpha tests will be"
  echo "      incorporated and you will need to confirm they still pass."
  echo "  (b) If this task supersedes alpha's version of a test, replace the test"
  echo "      body explicitly and document why the alpha version is being replaced."
  exit 1
else
  echo "PASS (pass 2 — alpha HEAD): No test regressions vs $BASE_BRANCH HEAD."
  exit 0
fi
