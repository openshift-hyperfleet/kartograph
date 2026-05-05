#!/usr/bin/env bash
# check-no-merge-commits-on-branch.sh
#
# Fails if the task branch contains any merge commits (commits with 2+ parents)
# above the merge-base with alpha.
#
# Merge commits are produced by `git merge` — which is explicitly prohibited for
# incorporating upstream changes (only `git rebase` is permitted). A merge commit
# fingerprints the use of `git merge origin/alpha` or `git merge origin/main`, which:
#   (a) Leaves the merge-base stale, causing content checks to diff from an
#       outdated baseline.
#   (b) Introduces upstream commits that carry no Task-Ref trailer, causing
#       check-all-commits-have-task-ref.sh to FAIL.
#   (c) Allows check-branch-rebased-on-alpha.sh to appear in-tolerance while
#       check-no-test-regressions.sh (pass 2) still fails — because the merge
#       advances the rebase-tolerance count without actually rebasing.
#
# Root cause: task-100 used `git merge origin/main` to resolve a rebase conflict,
# producing a merge commit. This masked stale branch state and allowed submission
# despite failing test regressions on alpha HEAD.
#
# Usage:
#   bash .hyperloop/checks/check-no-merge-commits-on-branch.sh [base_branch]
#
# Exit 0 — no merge commits found above the merge-base.
# Exit 1 — one or more merge commits detected.

set -euo pipefail

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
  echo "WARNING: Could not detect base branch — skipping merge-commit check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH — skipping check."
  exit 0
fi

echo "=== Checking for merge commits above merge-base with $BASE_BRANCH (${MERGE_BASE:0:8}) ==="

# Find commits above the merge-base with 2+ parents (i.e. merge commits).
# --merges filters to only commits produced by `git merge`.
merge_commits=$(git log --merges --oneline "${MERGE_BASE}..HEAD" 2>/dev/null || true)

if [[ -z "$merge_commits" ]]; then
  echo ""
  echo "PASS: No merge commits found above merge-base with $BASE_BRANCH."
  exit 0
fi

echo ""
echo "--- Merge commits detected on this branch ---"
echo "$merge_commits" | sed 's/^/  /'
echo ""
echo "FAIL: Merge commits are prohibited on task branches."
echo ""
echo "Merge commits are produced by \`git merge\` and indicate that upstream"
echo "changes were incorporated via merge rather than rebase. This:"
echo "  (a) Leaves the merge-base stale, so content checks diff from an"
echo "      outdated baseline and miss test files added to alpha after the cut."
echo "  (b) Pulls in upstream commits without Task-Ref trailers, failing"
echo "      check-all-commits-have-task-ref.sh."
echo "  (c) Makes check-branch-rebased-on-alpha.sh appear in-tolerance while"
echo "      check-no-test-regressions.sh pass 2 still fails — the merge"
echo "      advances the commit-count gap without moving the true merge-base."
echo ""
echo "Resolution — rebuild the branch cleanly:"
echo "  1. Identify the delivery commits (your actual implementation work):"
echo "       git log --no-merges --oneline \$(git merge-base HEAD $BASE_BRANCH)..HEAD"
echo "  2. Create a clean branch from current alpha:"
echo "       git checkout -b hyperloop/task-NNN-clean $BASE_BRANCH"
echo "  3. Cherry-pick only the delivery commits (exclude any merge commits):"
echo "       git cherry-pick <sha1> [<sha2> ...]"
echo "  4. Re-run the backend suite to confirm exit 0:"
echo "       bash .hyperloop/checks/check-run-backend-suite.sh"
echo ""
echo "Never use \`git merge\` to incorporate upstream changes — always use the"
echo "three-step sequence:"
echo "  git fetch origin && git branch -f alpha origin/alpha && git rebase alpha"
exit 1
