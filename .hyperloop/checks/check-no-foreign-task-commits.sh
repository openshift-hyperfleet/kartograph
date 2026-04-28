#!/usr/bin/env bash
# check-no-foreign-task-commits.sh
#
# Fails if any commit on this branch carries a Task-Ref trailer whose value
# does NOT match the task derived from the branch name.
#
# WHY: Foreign commits (from process-improvement cycles, intake runs, other
# task branches, etc.) end up on task branches when workers:
#   (a) branch from a dirty working tree instead of a clean alpha,
#   (b) cherry-pick from the wrong ref,
#   (c) commit orchestrator artifacts during a different task context.
#
# The consequences are concrete:
#   1. If the foreign commit is already on alpha, rebase produces a duplicate
#      and forces a force-push to clean up.
#   2. Reviewers cannot isolate what THIS task actually changed.
#   3. Test suites on the foreign commits may conflict or regress alpha's state.
#
# TASK DETECTION:
#   Derived from the branch name: hyperloop/task-019 → task-019
#   Branch names not matching the hyperloop/task-NNN pattern are skipped
#   (prints INFO and exits 0 — does not block unrelated branches).
#
# Usage:
#   bash .hyperloop/checks/check-no-foreign-task-commits.sh [base_branch]
#
# Exit 0 — all commits on this branch carry the expected Task-Ref, or carry
#           no Task-Ref (covered separately by check-all-commits-have-task-ref.sh).
# Exit 1 — one or more commits carry a foreign (wrong) Task-Ref.

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
  echo "WARNING: Could not detect base branch — skipping foreign-commit check."
  exit 0
fi

# Determine the expected Task-Ref from the branch name (e.g. hyperloop/task-019 → task-019)
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)
EXPECTED_TASK=$(echo "$BRANCH_NAME" | grep -oE 'task-[0-9]+' | head -1 || true)

if [[ -z "$EXPECTED_TASK" ]]; then
  echo "INFO: Branch '$BRANCH_NAME' does not match hyperloop/task-NNN pattern — skipping foreign-commit check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH — skipping check."
  exit 0
fi

echo "=== Checking for foreign Task-Ref commits (expected: $EXPECTED_TASK, base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="

FOREIGN_COMMITS=""
COMMIT_COUNT=0

while IFS= read -r sha; do
  [[ -z "$sha" ]] && continue
  COMMIT_COUNT=$((COMMIT_COUNT + 1))

  # Extract the Task-Ref trailer value from the commit body
  task_ref=$(git log -1 --format='%B' "$sha" 2>/dev/null \
    | grep -iE '^Task-Ref:[[:space:]]*' \
    | sed -E 's/^Task-Ref:[[:space:]]*//' \
    | tr -d '[:space:]' \
    | head -1 \
    || true)

  # No Task-Ref: not a foreign commit — missing-trailer is a separate concern
  [[ -z "$task_ref" ]] && continue

  if [[ "$task_ref" != "$EXPECTED_TASK" ]]; then
    short_msg=$(git log -1 --format='%h %s' "$sha" 2>/dev/null || true)
    FOREIGN_COMMITS="${FOREIGN_COMMITS}  FOREIGN: ${short_msg}  (Task-Ref: ${task_ref})\n"
  fi
done < <(git rev-list "${MERGE_BASE}..HEAD" 2>/dev/null || true)

echo ""
echo "Examined $COMMIT_COUNT commit(s) on this branch."

if [[ -z "$FOREIGN_COMMITS" ]]; then
  echo "PASS: All commits with Task-Ref trailers carry Task-Ref=$EXPECTED_TASK."
  exit 0
fi

echo ""
echo "FAIL: Foreign Task-Ref commits found on this branch."
echo ""
printf "%b" "$FOREIGN_COMMITS"
echo ""
echo "All commits on this branch must carry Task-Ref=$EXPECTED_TASK."
echo "Foreign commits indicate the branch was not started cleanly from '$BASE_BRANCH',"
echo "or that commits from another task/cycle were accidentally included."
echo ""
echo "── RESOLUTION ──────────────────────────────────────────────────────────────"
echo ""
echo "Option A — rebuild from current $BASE_BRANCH (safest when many foreign commits):"
echo ""
echo "  git fetch origin $BASE_BRANCH"
echo "  git checkout -b hyperloop/${EXPECTED_TASK}-clean origin/$BASE_BRANCH"
echo "  # List delivery commits for THIS task only:"
echo "  git log --oneline \$(git merge-base origin/hyperloop/${EXPECTED_TASK} origin/$BASE_BRANCH)..origin/hyperloop/${EXPECTED_TASK} --format='%H %s'"
echo "  git cherry-pick <sha1> [<sha2> ...]"
echo "  git push --force-with-lease origin HEAD:hyperloop/${EXPECTED_TASK}"
echo ""
echo "Option B — drop specific foreign commits via interactive rebase:"
echo ""
echo "  git rebase -i \$(git merge-base HEAD $BASE_BRANCH)"
echo "  # Change 'pick' to 'drop' for each foreign commit listed above."
echo ""
exit 1
