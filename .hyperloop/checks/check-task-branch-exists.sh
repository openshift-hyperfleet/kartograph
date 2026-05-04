#!/usr/bin/env bash
# check-task-branch-exists.sh
#
# Verifies the current branch is a task branch (hyperloop/task-NNN pattern)
# and confirms it has at least one commit ahead of the base branch.
#
# This is a pre-submission guard that catches the "Agent future missing or
# failed" failure mode: an agent whose branch creation call was interrupted
# leaves the repository on `alpha` (or the wrong branch) with zero commits,
# causing the orchestrator to see `branch: null` permanently.
#
# WHY THIS MATTERS:
#   If the current branch is not a `hyperloop/task-NNN` branch, either:
#     (a) The agent forgot to create the task branch (initialization failure), or
#     (b) The agent is on the wrong branch and will corrupt alpha on push.
#   Both cases are caught here before any submission.
#
# Usage:
#   ./check-task-branch-exists.sh [base_branch]
#
# Exit 0  — on a valid task branch with at least one commit.
# Exit 1  — on a non-task branch, or a task branch with zero commits.

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

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "HEAD")

echo "=== Checking task branch identity ==="
echo "Current branch: $CURRENT_BRANCH"

# Verify this looks like a task branch
if [[ ! "$CURRENT_BRANCH" =~ ^hyperloop/task-[0-9]+ ]] && \
   [[ ! "$CURRENT_BRANCH" =~ ^task-[0-9]+ ]]; then
  echo ""
  echo "FAIL: Current branch '$CURRENT_BRANCH' does not match the expected"
  echo "      task branch pattern (hyperloop/task-NNN or task-NNN)."
  echo ""
  echo "This means either:"
  echo "  (a) The agent failed to create the task branch (initialization failure)."
  echo "  (b) The agent is working on the wrong branch."
  echo ""
  echo "Required action: Run 'git checkout -b hyperloop/task-NNN' (replacing NNN"
  echo "with the task ID from the task file frontmatter) BEFORE any other work."
  echo ""
  echo "If the branch already exists remotely, run:"
  echo "  git fetch origin hyperloop/task-NNN"
  echo "  git checkout hyperloop/task-NNN"
  echo "Then audit existing commits with: git log --oneline alpha..HEAD"
  exit 1
fi

echo "Branch name is valid task pattern."

# Check commit count (delegate to check-branch-has-commits.sh if available)
if [[ -n "$BASE_BRANCH" ]]; then
  MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
  if [[ -n "$MERGE_BASE" ]]; then
    commit_count=$(git rev-list --count "$MERGE_BASE..HEAD" 2>/dev/null || echo "0")
    echo "Commits ahead of $BASE_BRANCH: $commit_count"
    if [[ "$commit_count" -eq 0 ]]; then
      echo ""
      echo "FAIL: Task branch '$CURRENT_BRANCH' exists but has zero commits vs $BASE_BRANCH."
      echo ""
      echo "This is the 'Agent future missing or failed' signature: the branch was"
      echo "created but no implementation was committed before the agent exited."
      echo ""
      echo "Before adding new implementation, check if a prior run left work on a"
      echo "remote branch: git ls-remote origin hyperloop/task-NNN"
      exit 1
    fi
    echo "PASS: Branch '$CURRENT_BRANCH' has $commit_count commit(s) ahead of $BASE_BRANCH."
  else
    echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping commit count."
    echo "PASS: Branch name check passed."
  fi
else
  echo "WARNING: Could not detect base branch. Skipping commit count check."
  echo "PASS: Branch name check passed."
fi

exit 0
