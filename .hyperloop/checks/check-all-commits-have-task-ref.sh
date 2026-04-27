#!/usr/bin/env bash
# check-all-commits-have-task-ref.sh
#
# Fails if any commit on the current branch (vs base) is missing a Task-Ref
# trailer entirely.
#
# WHY THIS CHECK:
#   check-no-foreign-task-commits.sh only warns (INFO) when a commit has no
#   Task-Ref trailer.  In practice, commits without trailers indicate the author
#   forgot to add the required trailer — which undermines traceability and makes
#   check-no-foreign-task-commits.sh unable to determine whether a commit is
#   foreign or not.  The canonical example from task-019: commit fa157f980a
#   ("test: add tenant isolation unit tests for FernetSecretStore") lacked a
#   Task-Ref: task-019 trailer.
#
# Usage:
#   ./check-all-commits-have-task-ref.sh [base_branch]
#
# Exit 0  — every commit carries a non-empty Task-Ref trailer.
# Exit 1  — one or more commits are missing the Task-Ref trailer.

set -euo pipefail

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
  echo "WARNING: Could not detect base branch. Skipping Task-Ref trailer check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping check."
  exit 0
fi

echo "=== Checking that all commits carry a Task-Ref trailer (base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="

commits=$(git log --format="%H" "$MERGE_BASE"..HEAD 2>/dev/null || true)

if [[ -z "$commits" ]]; then
  echo "INFO: No commits found between merge-base and HEAD."
  echo "PASS: No commits to check."
  exit 0
fi

found=0
report=""

while IFS= read -r sha; do
  [[ -z "$sha" ]] && continue

  task_ref=$(git log -1 --format="%(trailers:key=Task-Ref,valueonly)" "$sha" 2>/dev/null \
    | tr -d '[:space:]' || true)

  subject=$(git log -1 --format="%s" "$sha" 2>/dev/null || echo "<unknown>")

  if [[ -z "$task_ref" ]]; then
    report="${report}  MISSING-TRAILER: ${sha:0:10}  Subject: $subject\n"
    found=$((found + 1))
  fi
done <<< "$commits"

echo ""
if [[ $found -gt 0 ]]; then
  printf "%b" "$report"
  echo ""
  echo "FAIL: $found commit(s) are missing a Task-Ref trailer."
  echo ""
  echo "Every commit on a task branch must include:"
  echo "    Task-Ref: task-NNN"
  echo "as a git trailer (blank line before trailers in the commit message)."
  echo ""
  echo "To add the trailer to the most recent commit:"
  echo "  git commit --amend -m \"\$(git log -1 --format='%B')\" --trailer 'Task-Ref: <task-NNN>'"
  echo ""
  echo "For older commits, use an interactive rebase to reword each affected commit."
  exit 1
else
  echo "PASS: All commits carry a Task-Ref trailer."
  exit 0
fi
