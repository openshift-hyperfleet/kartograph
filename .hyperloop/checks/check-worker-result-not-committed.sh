#!/usr/bin/env bash
# check-worker-result-not-committed.sh
#
# Fails if .hyperloop/worker-result.yaml has been committed to this branch.
#
# WHY: worker-result.yaml is written by verifiers as the final verdict file.
# It is a temporary working artifact — it must NOT be staged or committed to
# the task branch. Committing it causes two problems:
#
#   1. MERGE CONFLICT: Every subsequent task round overwrites the same file.
#      When the orchestrator rebases the next round, it encounters a 3-way
#      conflict on worker-result.yaml that blocks all further rebase operations.
#
#   2. FALSE PROVENANCE: A committed result file implies the verdict is permanent
#      and frozen. The orchestrator reads it from the filesystem, not from git
#      history — committing it does not change orchestrator behavior but it does
#      pollute branch history and confuse future readers.
#
# The correct workflow: write worker-result.yaml to the working directory (or
# .hyperloop/state/) but do NOT stage or commit it.
#
# Usage:
#   bash .hyperloop/checks/check-worker-result-not-committed.sh [base_branch]
#
# Exit 0 — worker-result.yaml is not committed on this branch.
# Exit 1 — worker-result.yaml appears in branch commit history.

set -euo pipefail

RESULT_FILE=".hyperloop/worker-result.yaml"

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
  echo "WARNING: Could not detect base branch — skipping worker-result commit check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH — skipping check."
  exit 0
fi

echo "=== Checking that worker-result.yaml is not committed (base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="

# Check if the file appears in any diff (added or modified) between merge-base and HEAD
committed=$(git diff --name-only "$MERGE_BASE" HEAD -- "$RESULT_FILE" 2>/dev/null || true)

if [[ -z "$committed" ]]; then
  echo "PASS: $RESULT_FILE is not committed on this branch."
  exit 0
fi

# Find which commits introduced it
offending_commits=$(git log --oneline "$MERGE_BASE..HEAD" -- "$RESULT_FILE" 2>/dev/null || true)

echo ""
echo "FAIL: $RESULT_FILE is committed on this branch."
echo ""
if [[ -n "$offending_commits" ]]; then
  echo "Commits that touched the file:"
  echo "$offending_commits" | sed 's/^/  /'
  echo ""
fi
echo "worker-result.yaml is a verifier working artifact. It MUST NOT be committed"
echo "to the task branch — committing it causes merge conflicts in subsequent"
echo "rebase rounds and pollutes branch history."
echo ""
echo "HOW TO FIX:"
echo "  Option A — interactive rebase (remove from affected commits):"
echo "    git rebase -i \$(git merge-base HEAD $BASE_BRANCH)"
echo "    # For each offending commit, edit it and run:"
echo "    git restore --staged --worktree -- '$RESULT_FILE'"
echo "    git rebase --continue"
echo ""
echo "  Option B — cherry-pick to a clean branch (for many affected commits):"
echo "    git log --oneline \$(git merge-base HEAD $BASE_BRANCH)..HEAD"
echo "    git checkout $BASE_BRANCH && git checkout -b \$(git rev-parse --abbrev-ref HEAD)-clean"
echo "    git cherry-pick <only-the-real-implementation-SHAs>"
echo ""
echo "After fixing, add to .git/info/exclude to prevent future accidents:"
echo "  echo '.hyperloop/worker-result.yaml' >> \$(git rev-parse --git-dir)/info/exclude"
exit 1
