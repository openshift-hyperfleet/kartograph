#!/usr/bin/env bash
# check-no-foreign-task-commits.sh
#
# Fails if any commit on this branch (vs the base branch) carries a Task-Ref:
# trailer that references a task other than the current one.
#
# WHY: When an implementer runs 'git rebase origin/alpha' instead of
# 'git rebase alpha', the rebase incorporates commits that are on local alpha
# but not yet pushed — including full task implementation commits from other
# branches. These contaminating commits delete files, remove methods, and add
# state-file noise that causes cascading check failures. This was the root cause
# of task-038's FAIL: commit c6b4ab3a (Task-Ref: task-012) was included in the
# task-038 branch after a rebase against origin/alpha when local alpha was 6
# commits ahead.
#
# TASK DETECTION: Derived automatically from the current branch name.
#   Branch 'hyperloop/task-038' → task id 'task-038'.
#   Override: set TASK_ID env var, or pass --task=task-NNN as the second arg.
#
# Usage:
#   bash .hyperloop/checks/check-no-foreign-task-commits.sh [base_branch] [--task=task-NNN]
#
# Exit 0 — no foreign task commits on this branch.
# Exit 1 — one or more commits reference a different task's Task-Ref.

set -euo pipefail

# Normalize CWD to repo root so git pathspecs work correctly.
cd "$(git rev-parse --show-toplevel)"

BASE_BRANCH="${1:-}"
TASK_OVERRIDE="${2:-}"

# Handle argument order flexibility: --task= can come first
if [[ "$BASE_BRANCH" == --task=* ]]; then
  TASK_OVERRIDE="$BASE_BRANCH"
  BASE_BRANCH=""
fi

# Detect base branch
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
  echo "WARNING: Could not detect base branch. Skipping foreign task commit check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping check."
  exit 0
fi

# Detect current task ID
CURRENT_TASK="${TASK_ID:-}"
if [[ -z "$CURRENT_TASK" ]]; then
  if [[ "$TASK_OVERRIDE" == --task=* ]]; then
    CURRENT_TASK="${TASK_OVERRIDE#--task=}"
  else
    # Derive from branch name: hyperloop/task-038 → task-038
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)
    CURRENT_TASK=$(echo "$BRANCH" | grep -oE 'task-[0-9]+' | head -1 || true)
  fi
fi

if [[ -z "$CURRENT_TASK" ]]; then
  echo "WARNING: Could not detect current task ID from branch name or TASK_ID env var."
  echo "  Branch: $(git rev-parse --abbrev-ref HEAD)"
  echo "  Set TASK_ID=task-NNN or pass --task=task-NNN to enable this check."
  exit 0
fi

echo "=== Checking for foreign task commits (current task: $CURRENT_TASK, base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="

# Collect all commits since merge-base
COMMIT_SHAS=$(git log --format="%H" "$MERGE_BASE..HEAD" 2>/dev/null || true)

if [[ -z "$COMMIT_SHAS" ]]; then
  echo "PASS: No commits on this branch (nothing to check)."
  exit 0
fi

foreign_commits=""
while IFS= read -r SHA; do
  [[ -z "$SHA" ]] && continue
  # Extract the Task-Ref: trailer value from the commit body
  task_ref=$(git log -1 --format="%B" "$SHA" 2>/dev/null \
    | grep -E '^Task-Ref:[[:space:]]*' \
    | sed 's/^Task-Ref:[[:space:]]*//' \
    | tr -d '[:space:]' \
    || true)

  # Only flag commits that carry a Task-Ref for a DIFFERENT task
  if [[ -n "$task_ref" ]] && [[ "$task_ref" != "$CURRENT_TASK" ]]; then
    subject=$(git log -1 --format="%s" "$SHA" 2>/dev/null || echo "(no subject)")
    foreign_commits="${foreign_commits}  ${SHA:0:8}  Task-Ref: $task_ref  \"$subject\"\n"
  fi
done <<< "$COMMIT_SHAS"

if [[ -n "$foreign_commits" ]]; then
  echo ""
  echo "FAIL: Foreign task commits found on this branch:"
  echo ""
  printf "%b" "$foreign_commits"
  echo ""
  echo "This branch ($CURRENT_TASK) contains commits referencing a different task."
  echo "This almost always means a contaminated rebase — caused by running"
  echo "'git rebase origin/alpha' when local 'alpha' was ahead of 'origin/alpha'."
  echo "The rebase picked up task commits from local alpha that were not yet on"
  echo "origin/alpha."
  echo ""
  echo "FIX — cherry-pick delivery commits onto a fresh branch:"
  echo ""
  echo "  Step 1 — identify legitimate delivery commits for $CURRENT_TASK:"
  echo "    git log --oneline \$(git merge-base HEAD $BASE_BRANCH)..HEAD"
  echo "    # Keep only commits with Task-Ref: $CURRENT_TASK or no Task-Ref"
  echo ""
  echo "  Step 2 — create a fresh branch from current $BASE_BRANCH:"
  echo "    git checkout $BASE_BRANCH"
  echo "    git checkout -b hyperloop/${CURRENT_TASK}-clean"
  echo "    git cherry-pick <delivery-sha> [<delivery-sha2> ...]"
  echo ""
  echo "  Step 3 — verify and force-push to the original branch name:"
  echo "    bash .hyperloop/checks/check-no-foreign-task-commits.sh"
  echo "    bash .hyperloop/checks/check-no-state-file-commits.sh"
  echo "    bash .hyperloop/checks/check-no-source-regressions.sh"
  echo "    bash .hyperloop/checks/check-no-test-regressions.sh"
  echo "    git push origin hyperloop/${CURRENT_TASK}-clean:hyperloop/${CURRENT_TASK} --force-with-lease"
  echo ""
  echo "PREVENTION: Always use 'git rebase alpha' (local), never 'git rebase origin/alpha'."
  echo "  Run 'bash .hyperloop/checks/check-alpha-local-vs-remote.sh' before any rebase"
  echo "  to see how far local alpha has diverged from origin/alpha."
  exit 1
fi

echo "PASS: All commits on this branch reference '$CURRENT_TASK' (or carry no Task-Ref)."
exit 0
