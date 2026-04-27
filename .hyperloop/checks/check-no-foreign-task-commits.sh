#!/usr/bin/env bash
# check-no-foreign-task-commits.sh
#
# Fails if any commit on this branch (vs the base branch) carries a Task-Ref:
# trailer that does not match the current task as derived from the branch name.
#
# WHY: When a task branch is rebased against a stale remote ref (origin/alpha
# instead of local alpha), commits belonging to other tasks that landed on local
# alpha but not yet on origin/alpha can appear as "branch commits" in git log.
# These foreign commits would be merged into alpha under the wrong task's PR,
# smuggling unreviewed changes.
#
# This is the pattern observed in task-003: commit 1b0f2478 (Task-Ref: task-032,
# 3,791 insertions, 46 files) was present on the branch because the merge-base
# with local alpha was BEFORE task-032 landed. The PR would have merged those
# changes silently under the task-003 review.
#
# CURRENT TASK DETECTION:
#   Branch name pattern: hyperloop/task-NNN or task-NNN
#   If the branch does not match the pattern, foreign-commit detection is
#   best-effort (any commit carrying a Task-Ref trailer triggers a warning).
#
# Usage:
#   bash .hyperloop/checks/check-no-foreign-task-commits.sh [base_branch]
#
# Exit 0 — no foreign Task-Ref commits detected.
# Exit 1 — one or more commits with a foreign Task-Ref are present.

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
  echo "WARNING: Could not detect base branch — skipping foreign-commit check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH — skipping check."
  exit 0
fi

# Derive current task ID from branch name (hyperloop/task-NNN or task-NNN)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "HEAD")
CURRENT_TASK=$(echo "$CURRENT_BRANCH" | grep -oE 'task-[0-9]+' | head -1 || true)

echo "=== Checking for foreign Task-Ref commits (base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="
echo "  Current branch:  $CURRENT_BRANCH"
echo "  Detected task:   ${CURRENT_TASK:-<unknown — pattern not matched>}"
echo ""

# Collect all commits on this branch with their full message bodies
COMMITS=$(git log --format="%H" "$MERGE_BASE..HEAD" 2>/dev/null || true)

if [[ -z "$COMMITS" ]]; then
  echo "PASS: No commits on this branch — nothing to check."
  exit 0
fi

FOREIGN_FOUND=0
FOREIGN_LIST=""

while IFS= read -r sha; do
  # Extract all Task-Ref trailer lines from this commit's body
  task_refs=$(git log -1 --format="%B" "$sha" 2>/dev/null \
    | grep -E "^Task-Ref:" | sed 's/Task-Ref: *//' | tr -d '[:space:]' || true)

  if [[ -z "$task_refs" ]]; then
    continue  # No Task-Ref trailer — skip (process commits, etc.)
  fi

  # Check each Task-Ref value
  while IFS= read -r ref; do
    if [[ -z "$ref" ]]; then
      continue
    fi

    if [[ -n "$CURRENT_TASK" && "$ref" == "$CURRENT_TASK" ]]; then
      continue  # This task's own commits — OK
    fi

    # Foreign Task-Ref detected
    subject=$(git log -1 --format="%s" "$sha" 2>/dev/null || echo "(unknown subject)")
    FOREIGN_LIST="${FOREIGN_LIST}  ${sha:0:8}  Task-Ref: ${ref}  —  ${subject}\n"
    FOREIGN_FOUND=$((FOREIGN_FOUND + 1))
  done <<< "$task_refs"
done <<< "$COMMITS"

if [[ "$FOREIGN_FOUND" -gt 0 ]]; then
  echo "FAIL: ${FOREIGN_FOUND} commit(s) with a foreign Task-Ref detected on this branch."
  echo ""
  printf "%b" "$FOREIGN_LIST"
  echo ""
  echo "WHY THIS HAPPENS:"
  echo "  The branch was likely rebased against 'origin/alpha' when local 'alpha'"
  echo "  was ahead of origin. Commits that landed on local alpha but were not yet"
  echo "  pushed to origin appear as branch commits because the merge-base with"
  echo "  local alpha is older than those commits."
  echo ""
  echo "HOW TO FIX:"
  echo "  1. Identify only THIS task's commits:"
  echo "     git log --oneline \$(git merge-base HEAD $BASE_BRANCH)..HEAD"
  echo ""
  echo "  2. Create a fresh branch from current local $BASE_BRANCH:"
  echo "     git checkout $BASE_BRANCH"
  echo "     git checkout -b \${CURRENT_BRANCH}-clean"
  echo ""
  echo "  3. Cherry-pick only this task's commits (skip the foreign ones above):"
  echo "     git cherry-pick <task-sha1> [<task-sha2> ...]"
  echo ""
  echo "  4. Verify clean:"
  echo "     bash .hyperloop/checks/check-no-foreign-task-commits.sh"
  echo "     bash .hyperloop/checks/check-branch-rebased-on-alpha.sh"
  echo ""
  echo "  5. Force-push to replace the contaminated branch:"
  echo "     git push --force-with-lease origin HEAD:\${CURRENT_BRANCH}"
  exit 1
fi

echo "PASS: No foreign Task-Ref commits detected on this branch."
exit 0
