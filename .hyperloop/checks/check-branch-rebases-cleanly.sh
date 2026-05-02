#!/usr/bin/env bash
# check-branch-rebases-cleanly.sh
#
# Verifies the current branch can be rebased onto 'alpha' without conflicts.
#
# WHY THIS CHECK:
#   check-branch-rebased-on-alpha.sh measures staleness (how many alpha commits
#   are missing), but it does NOT test whether the branch's own commits conflict
#   with alpha's content.  A branch can be within the 5-commit staleness window
#   and yet contain commits whose content duplicates work already merged to alpha
#   — producing unresolvable conflicts at merge time.
#
#   The canonical failure mode (task-042): an implementer wrote out-of-scope
#   changes to files already modified by a recently-merged alpha commit.  The
#   stray commit carried the correct Task-Ref so check-no-foreign-task-commits
#   passed, and the branch was within the staleness threshold so
#   check-branch-rebased-on-alpha passed — but `git rebase alpha` failed with
#   hard conflicts in four files, blocking the PR.
#
# DETECTION STRATEGY:
#   1. Create a temporary git worktree (shares the same object store — no clone).
#   2. Attempt `git rebase alpha` inside that worktree.
#   3. Report PASS or FAIL based on the rebase exit code.
#   4. Always clean up the worktree and temp branch on exit.
#
# Usage:
#   bash .hyperloop/checks/check-branch-rebases-cleanly.sh
#
# Exit 0  — branch rebases onto alpha without conflicts.
# Exit 1  — rebase produced conflicts (scope pollution or duplicate content).

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$REPO_ROOT" ]]; then
  echo "ERROR: Not inside a git repository."
  exit 1
fi
cd "$REPO_ROOT"

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

# Verify 'alpha' ref exists locally.
if ! git rev-parse --verify alpha >/dev/null 2>&1; then
  echo "INFO: Local 'alpha' ref not found — skipping rebase-cleanness check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD alpha 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "INFO: No common ancestor with 'alpha' — skipping rebase-cleanness check."
  exit 0
fi

COMMITS_AHEAD=$(git rev-list --count "${MERGE_BASE}..HEAD" 2>/dev/null || echo "0")
if [[ "$COMMITS_AHEAD" -eq 0 ]]; then
  echo "INFO: No commits ahead of alpha — nothing to rebase."
  echo "PASS: Branch rebases cleanly onto alpha (no task commits)."
  exit 0
fi

echo "=== Dry-run rebase: $CURRENT_BRANCH → alpha ($COMMITS_AHEAD commit(s)) ==="

TEMP_BRANCH="hyperloop-rebase-dryrun-$$"
WORK_DIR="$(mktemp -d)"
WORKTREE_PATH="$WORK_DIR/dryrun"

cleanup() {
  # Abort any in-progress rebase inside the worktree before removing it.
  git -C "$WORKTREE_PATH" rebase --abort 2>/dev/null || true
  git worktree remove --force "$WORKTREE_PATH" 2>/dev/null || true
  git branch -D "$TEMP_BRANCH" 2>/dev/null || true
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

# Add a temporary worktree based on current HEAD.
git worktree add "$WORKTREE_PATH" -b "$TEMP_BRANCH" HEAD --quiet 2>/dev/null

REBASE_OUTPUT=$(git -C "$WORKTREE_PATH" rebase alpha 2>&1 || true)
REBASE_EXIT=$?

if [[ $REBASE_EXIT -eq 0 ]]; then
  echo ""
  echo "PASS: Branch rebases cleanly onto alpha — no conflicts."
  exit 0
fi

# Rebase failed — collect conflicting files before aborting.
CONFLICTING=$(git -C "$WORKTREE_PATH" diff --name-only --diff-filter=U 2>/dev/null || true)
FAILED_COMMIT=$(git -C "$WORKTREE_PATH" rebase --show-current-patch 2>/dev/null \
  | grep "^commit " | head -1 || true)

echo ""
echo "FAIL: Branch cannot rebase onto alpha — conflicts detected."
echo ""
if [[ -n "$FAILED_COMMIT" ]]; then
  echo "Failing commit: $FAILED_COMMIT"
  echo ""
fi
if [[ -n "$CONFLICTING" ]]; then
  echo "Conflicting files:"
  while IFS= read -r f; do
    echo "  $f"
  done <<< "$CONFLICTING"
  echo ""
fi

# Detect whether ANY conflicting file is a test file.
TEST_FILE_CONFLICTS=""
while IFS= read -r f; do
  if [[ "$f" =~ (\.test\.(ts|js)|\.spec\.(ts|js)|test_.*\.py|_test\.py)$ ]]; then
    TEST_FILE_CONFLICTS="$TEST_FILE_CONFLICTS $f"
  fi
done <<< "$CONFLICTING"

if [[ -n "$TEST_FILE_CONFLICTS" ]]; then
  echo "TEST FILE CONFLICT DETECTED"
  echo "One or more conflicting files are test files:"
  for f in $TEST_FILE_CONFLICTS; do
    echo "  $f"
  done
  echo ""
  echo "IMPORTANT: For test file conflicts the correct resolution is MERGE, not DROP."
  echo "Dropping a test file commit silently reduces test coverage — this is always wrong."
  echo ""
  echo "Resolution:"
  echo "  1. Run: git rebase alpha"
  echo "  2. When the conflict appears, open the conflicting test file."
  echo "  3. Keep ALL describe/it/def test_ blocks from BOTH sides of the conflict."
  echo "     Do NOT pick just one side. Do NOT delete blocks from either side."
  echo "  4. Remove git conflict markers (<<<<<<<, =======, >>>>>>>)."
  echo "  5. Check for duplicate describe blocks (same name) and deduplicate only"
  echo "     exact duplicates; different tests with similar names must both be kept."
  echo "  6. Run: git add <conflicting-file> && git rebase --continue"
  echo "  7. Run the test suite to verify all tests pass."
  echo "  8. Run: bash .hyperloop/checks/check-no-test-regressions.sh"
  echo "  9. Re-run this check to confirm exit 0."
else
  echo "Root cause: the branch contains a commit whose content overlaps with"
  echo "changes already merged to alpha.  This is typically caused by writing"
  echo "code outside the task's spec scope (e.g., modifying files not referenced"
  echo "in the spec that were already updated by a different merged PR)."
  echo ""
  echo "Resolution:"
  echo "  1. Identify the offending commit(s):"
  echo "     git log --oneline \$(git merge-base HEAD alpha)..HEAD"
  echo "  2. Check whether alpha already contains equivalent changes to those files:"
  echo "     git log --oneline alpha -- <conflicting-file>"
  echo "  3. Drop the out-of-scope commit(s) via interactive rebase:"
  echo "     git rebase -i \$(git merge-base HEAD alpha)"
  echo "     # Mark stray commits as 'drop' and save"
fi
exit 1
