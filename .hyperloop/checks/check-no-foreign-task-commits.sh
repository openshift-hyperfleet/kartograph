#!/usr/bin/env bash
# check-no-foreign-task-commits.sh
#
# Fails if any commit on the current branch (vs base) carries a Task-Ref
# trailer that does not match the task identifier in the current branch name.
#
# WHY THIS CHECK:
#   Foreign-task commits (e.g., task-032 commits present on a task-019 branch)
#   introduce unrelated changes that are hard to diagnose — duplicate test
#   function names, unexpected schema changes, or service-layer conflicts that
#   surface as ruff/mypy/pytest failures with no obvious link to the current
#   task's diff.  The canonical example is task-019: a task-032 commit added a
#   second `test_delete_cascades_encrypted_credentials` method, causing F811
#   and mypy no-redef failures that blocked the merge.
#
# DETECTION STRATEGY:
#   1. Extract the expected task ref from the current branch name
#      (branch pattern: task-NNN/<description> → expected = task-NNN).
#   2. For each commit between merge-base and HEAD, read the Task-Ref trailer.
#   3. Flag any commit whose Task-Ref differs from the expected task ref.
#   Commits with NO Task-Ref trailer are warned but not blocked (process
#   improvement commits and merge commits legitimately omit the trailer).
#
# Usage:
#   ./check-no-foreign-task-commits.sh [base_branch]
#
# Exit 0  — no foreign-task commits detected.
# Exit 1  — one or more commits carry a mismatched Task-Ref.

set -euo pipefail

# Normalize CWD to repo root.
cd "$(git rev-parse --show-toplevel)"

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
  echo "WARNING: Could not detect base branch. Skipping foreign-task commit check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping check."
  exit 0
fi

# If origin/$BASE_BRANCH exists and is AHEAD of local $BASE_BRANCH, use the
# more recent merge-base (the one closer to HEAD). This handles the case where
# a PR has been merged to origin/alpha after the local alpha ref was last updated,
# so commits from that merged PR (with their own Task-Ref trailers) don't appear
# as "foreign" on task branches that were correctly rebased on origin/alpha.
REMOTE_REF="origin/$BASE_BRANCH"
if git show-ref --verify --quiet "refs/remotes/$REMOTE_REF" 2>/dev/null; then
  MB_REMOTE=$(git merge-base HEAD "$REMOTE_REF" 2>/dev/null || echo "")
  if [[ -n "$MB_REMOTE" && "$MB_REMOTE" != "$MERGE_BASE" ]]; then
    COUNT_LOCAL=$(git rev-list --count "${MERGE_BASE}..HEAD" 2>/dev/null || echo "999999")
    COUNT_REMOTE=$(git rev-list --count "${MB_REMOTE}..HEAD" 2>/dev/null || echo "999999")
    if [[ "$COUNT_REMOTE" -lt "$COUNT_LOCAL" ]]; then
      MERGE_BASE="$MB_REMOTE"
    fi
  fi
fi

# Extract the task ref from the current branch name (e.g., task-019/credentials → task-019).
BRANCH=$(git rev-parse --abbrev-ref HEAD)
EXPECTED_TASK=$(echo "$BRANCH" | grep -oE 'task-[0-9]+' | head -1 || true)

if [[ -z "$EXPECTED_TASK" ]]; then
  echo "WARNING: Branch '$BRANCH' has no task-NNN pattern. Skipping foreign-task check."
  exit 0
fi

echo "=== Checking for foreign-task commits (expected: $EXPECTED_TASK, base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="

# Collect all commit SHAs between merge-base and HEAD.
commits=$(git log --format="%H" "$MERGE_BASE"..HEAD 2>/dev/null || true)

if [[ -z "$commits" ]]; then
  echo "INFO: No commits found between merge-base and HEAD."
  echo "PASS: No foreign-task commits detected."
  exit 0
fi

found=0
report=""

while IFS= read -r sha; do
  [[ -z "$sha" ]] && continue

  # Extract the Task-Ref trailer value (strip all whitespace for clean comparison).
  task_ref=$(git log -1 --format="%(trailers:key=Task-Ref,valueonly)" "$sha" 2>/dev/null \
    | tr -d '[:space:]' || true)

  subject=$(git log -1 --format="%s" "$sha" 2>/dev/null || echo "<unknown>")

  if [[ -z "$task_ref" ]]; then
    # No Task-Ref trailer — warn only, not a blocking failure.
    echo "  INFO: ${sha:0:10} has no Task-Ref trailer: $subject"
    continue
  fi

  if [[ "$task_ref" != "$EXPECTED_TASK" ]]; then
    report="${report}  FOREIGN: ${sha:0:10}  Task-Ref=$task_ref (expected $EXPECTED_TASK)\n"
    report="${report}           Subject: $subject\n"
    found=$((found + 1))
  fi
done <<< "$commits"

echo ""
if [[ $found -gt 0 ]]; then
  printf "%b" "$report"
  echo ""
  echo "FAIL: Foreign-task commits detected on this branch."
  echo ""
  echo "Commits from other tasks introduce unrelated changes (duplicate tests,"
  echo "schema changes, service conflicts) that cause linting, type-checking,"
  echo "or functional failures that are difficult to diagnose."
  echo ""
  echo "To remove foreign commits, use interactive rebase:"
  echo "  git rebase -i $MERGE_BASE"
  echo "  # Mark foreign commits as 'drop' and save"
  echo ""
  echo "Alternatively, cherry-pick only the task-specific commits onto a fresh"
  echo "branch from $BASE_BRANCH."
  exit 1
else
  echo "PASS: No foreign-task commits detected."
  exit 0
fi
