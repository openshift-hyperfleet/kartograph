#!/usr/bin/env bash
# check-branch-has-commits.sh
#
# Fails if the current branch has zero commits vs the base branch.
# A zero-commit branch means no implementation was performed.
#
# This catches the failure pattern where an implementer reports a task
# complete without having written, committed, or pushed any code.
#
# Usage:
#   ./check-branch-has-commits.sh [base_branch]
#
# Exit 0  — branch has at least one new commit vs base.
# Exit 1  — branch is identical to base (zero new commits).

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
  echo "WARNING: Could not detect base branch. Skipping commit count check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping check."
  exit 0
fi

echo "=== Checking for commits ahead of $BASE_BRANCH (merge-base: ${MERGE_BASE:0:8}) ==="

commit_count=$(git rev-list --count "$MERGE_BASE..HEAD" 2>/dev/null || echo "0")

echo "Commits ahead of $BASE_BRANCH: $commit_count"

ahead_log="$(git log --oneline "$MERGE_BASE..HEAD" 2>/dev/null || true)"
if [[ -n "$ahead_log" ]]; then
  echo ""
  printf '%s\n' "$ahead_log"
fi

echo ""
if [[ "$commit_count" -eq 0 ]]; then
  echo "FAIL: Branch has zero commits vs $BASE_BRANCH."
  echo ""
  echo "No implementation has been performed. Do not submit a task with an"
  echo "empty branch. Write the required code, commit it, then re-run checks."
  echo ""
  echo "A PR with 0 commits / 0 files changed is not an implementation —"
  echo "it is a missed task. Write the code first."
  exit 1
else
  echo "PASS: Branch has $commit_count commit(s) ahead of $BASE_BRANCH."
  exit 0
fi
