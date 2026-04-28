#!/usr/bin/env bash
# check-all-commits-have-task-ref.sh
#
# Fails if any commit introduced by this branch is missing a Task-Ref trailer.
#
# WHY: The Task-Ref trailer is the primary signal for tracking which task
# introduced each commit. Without it:
#   1. Foreign-commit checks cannot distinguish this task's work from others.
#   2. Orchestrator tooling cannot identify which commits belong to which task.
#   3. Post-merge audit trails break — blame cannot be attributed to a task.
#
# SCOPE: Only commits between the merge-base with the base branch and HEAD are
# checked. Commits on the base branch itself are not inspected.
#
# EXEMPTIONS: Merge commits (two parents) are skipped — their message is
# auto-generated and Task-Ref attribution flows from the constituent commits.
#
# Usage:
#   bash .hyperloop/checks/check-all-commits-have-task-ref.sh [base_branch]
#
# Exit 0 — every non-merge commit on this branch has a Task-Ref trailer.
# Exit 1 — one or more commits are missing the trailer.

set -uo pipefail

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
  echo "WARNING: Could not detect base branch — skipping Task-Ref trailer check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH — skipping check."
  exit 0
fi

echo "=== Checking that all branch commits have Task-Ref trailers (base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="

MISSING_TRAILER=""
COMMIT_COUNT=0
MERGE_SKIPPED=0

while IFS= read -r sha; do
  [[ -z "$sha" ]] && continue

  # Skip merge commits (2 parents) — their trailer is implicit
  parent_count=$(git log -1 --format="%P" "$sha" 2>/dev/null | wc -w | tr -d ' ' || echo "1")
  if [[ "$parent_count" -ge 2 ]]; then
    MERGE_SKIPPED=$((MERGE_SKIPPED + 1))
    continue
  fi

  COMMIT_COUNT=$((COMMIT_COUNT + 1))

  task_ref=$(git log -1 --format='%B' "$sha" 2>/dev/null \
    | grep -iE '^Task-Ref:[[:space:]]*' \
    | head -1 \
    || true)

  if [[ -z "$task_ref" ]]; then
    short_msg=$(git log -1 --format='%h %s' "$sha" 2>/dev/null || true)
    MISSING_TRAILER="${MISSING_TRAILER}  MISSING: ${short_msg}\n"
  fi
done < <(git rev-list "${MERGE_BASE}..HEAD" 2>/dev/null || true)

echo ""
echo "Examined $COMMIT_COUNT non-merge commit(s) (skipped $MERGE_SKIPPED merge commit(s))."

if [[ -z "$MISSING_TRAILER" ]]; then
  echo "PASS: All commits have Task-Ref trailers."
  exit 0
fi

echo ""
echo "FAIL: The following commits are missing a Task-Ref trailer:"
echo ""
printf "%b" "$MISSING_TRAILER"
echo ""
echo "Every commit on a task branch must include a trailer line in the commit"
echo "message body (separated from the subject by a blank line):"
echo ""
echo "  Task-Ref: task-NNN"
echo ""
echo "── HOW TO ADD MISSING TRAILERS ────────────────────────────────────────────"
echo ""
echo "For each commit listed above, amend or rebase to add the trailer:"
echo ""
echo "  git rebase -i \$(git merge-base HEAD $BASE_BRANCH)"
echo "  # In the editor, change 'pick' to 'reword' for each offending commit."
echo "  # Add 'Task-Ref: task-NNN' as a trailer in the commit message editor."
echo ""
echo "Or for a single commit, if it is the most recent:"
echo ""
echo "  git commit --amend  # add Task-Ref trailer in the editor"
echo ""
exit 1
