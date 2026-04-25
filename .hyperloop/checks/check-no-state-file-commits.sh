#!/usr/bin/env bash
# check-no-state-file-commits.sh
#
# Fails if any .hyperloop/state/ files are present in the commits added by
# this branch vs the base branch.
#
# WHY: State files (.hyperloop/state/**) are orchestrator-managed metadata.
# Committing them to a task branch means rebase and reset operations encounter
# permanent merge conflicts because every cycle updates the same files.
# Once state-file commits land on a branch, branch resets cannot cleanly rebase
# onto alpha — the result is a 3-way conflict loop that requires a full branch
# abandon. This is the failure pattern observed in task-003 (rounds 0 and 9).
#
# Usage:
#   ./check-no-state-file-commits.sh [base_branch]
#
# Exit 0  — no .hyperloop/state/ files committed on this branch.
# Exit 1  — state files are present in branch commits; unstage/remove them.

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
  echo "WARNING: Could not detect base branch. Skipping state-file commit check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping check."
  exit 0
fi

echo "=== Checking for .hyperloop/state/ commits on this branch (base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="

# Find all .hyperloop/state/ files touched (added, modified, deleted) on this branch
state_files=$(git diff --name-only "$MERGE_BASE" HEAD -- '.hyperloop/state/' 2>/dev/null || true)

if [[ -z "$state_files" ]]; then
  echo "PASS: No .hyperloop/state/ files committed on this branch."
  exit 0
fi

echo ""
echo "FAIL: The following .hyperloop/state/ files are present in branch commits:"
echo ""
echo "$state_files" | sed 's/^/  /'
echo ""
echo "State files (.hyperloop/state/**) are orchestrator-managed metadata and"
echo "MUST NOT be committed to task branches. Their presence causes permanent"
echo "merge conflicts when the branch is rebased or reset, requiring a full"
echo "branch abandon."
echo ""
echo "To fix:"
echo "  1. Identify which commits added these files:"
echo "     git log --oneline --diff-filter=A,M -- '.hyperloop/state/**'"
echo "  2. Rewrite history to remove them, or reset the branch from alpha:"
echo "     git checkout alpha && git checkout -b hyperloop/task-NNN-v2"
echo "  3. Never add .hyperloop/state/ to your git staging area."
echo "  4. Add '.hyperloop/state/' to .gitignore if not already present."
exit 1
