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
# THE TWO FIX DIRECTIONS:
#
#   ADDED on branch (not on alpha)  → strip from history via interactive rebase
#   DELETED from alpha on branch    → restore the file to match alpha's version
#   MODIFIED on branch vs alpha     → strip the modification from history
#
# Applying only one direction's fix while ignoring the other is PARTIAL.
# After any fix, re-run this script and confirm exit 0 before proceeding.
#
# Usage:
#   ./check-no-state-file-commits.sh [base_branch]
#
# Exit 0  — no .hyperloop/state/ files committed on this branch.
# Exit 1  — state files are present in branch commits; unstage/remove them.

set -euo pipefail

# Normalize CWD to repo root so git pathspecs work correctly.
# Running from a subdirectory (e.g., .hyperloop/checks/) causes pathspecs like
# '.hyperloop/state/' to silently match nothing and return false PASSes.
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

# Categorise by direction to give targeted fix instructions
added_or_modified=$(git diff --name-only --diff-filter=AM "$MERGE_BASE" HEAD -- '.hyperloop/state/' 2>/dev/null || true)
deleted_from_alpha=$(git diff --name-only --diff-filter=D  "$MERGE_BASE" HEAD -- '.hyperloop/state/' 2>/dev/null || true)

echo ""
echo "FAIL: The following .hyperloop/state/ files are present in branch commits:"
echo ""
echo "$state_files" | sed 's/^/  /'
echo ""
echo "State files (.hyperloop/state/**) are orchestrator-managed metadata and"
echo "MUST NOT be committed to task branches. Their presence causes permanent"
echo "merge conflicts when the branch is rebased or reset, requiring a full"
echo "branch abandon."

if [[ -n "$added_or_modified" ]]; then
  echo ""
  echo "── ADDED / MODIFIED on this branch (not present on $BASE_BRANCH) ──────────"
  echo "$added_or_modified" | sed 's/^/  /'
  CONTAMINATED_COUNT=$(echo "$added_or_modified" | wc -l | tr -d ' ')
  echo ""
  echo "  These files did NOT exist on $BASE_BRANCH. They were added by commits"
  echo "  on this branch and must be REMOVED FROM HISTORY."
  echo ""

  # Detect if any contamination came from the intake process (external actor).
  # Intake state files follow the pattern .hyperloop/state/intake/<date>-*.md and
  # are written by orchestrator intake workers, NOT by the implementing agent.
  # When intake files are present, cherry-pick is ALWAYS preferred over interactive
  # rebase — the contamination is external, not implementer-authored, making it
  # impossible to remove via "edit and drop" in a rebase without also reconstructing
  # the legitimate implementation commits from scratch.
  intake_contamination=$(echo "$added_or_modified" | grep "\.hyperloop/state/intake/" || true)

  if [[ -n "$intake_contamination" ]] || [[ "$CONTAMINATED_COUNT" -gt 5 ]]; then
    if [[ -n "$intake_contamination" ]]; then
      echo "  PREFERRED FIX (intake-worker contamination detected — cherry-pick is required):"
      echo "  The contaminating files include .hyperloop/state/intake/ entries written by"
      echo "  the orchestrator intake process, not by your task. Interactive rebase cannot"
      echo "  cleanly excise commits from another agent. Cherry-pick the delivery commits"
      echo "  onto a fresh alpha branch instead."
    else
      echo "  PREFERRED FIX (${CONTAMINATED_COUNT} contaminated files — cherry-pick is safer than interactive rebase):"
    fi
    echo ""
    echo "  Step 1 — identify delivery commits (commits that do NOT touch .hyperloop/state/):"
    echo "    git log --oneline \$(git merge-base HEAD $BASE_BRANCH)..HEAD -- ':!.hyperloop/state'"
    echo ""
    echo "  Step 2 — create a fresh branch from current $BASE_BRANCH and cherry-pick:"
    echo "    git checkout $BASE_BRANCH"
    echo "    git checkout -b hyperloop/task-NNN-clean"
    echo "    git cherry-pick <delivery-sha> [<delivery-sha2> ...]"
    echo ""
    echo "  Step 3 — confirm clean, then force-push to the original branch name:"
    echo "    bash .hyperloop/checks/check-no-state-file-commits.sh"
    echo "    bash .hyperloop/checks/check-branch-rebased-on-alpha.sh"
    echo "    git push origin hyperloop/task-NNN-clean:hyperloop/task-NNN --force-with-lease"
    echo "    # This keeps the existing PR and orchestrator state valid."
  else
    echo "  FIX:"
    echo ""
    echo "  Step 1 — find the offending commits:"
    echo "    git log --oneline --diff-filter=A,M -- '.hyperloop/state/**' \$(git merge-base HEAD $BASE_BRANCH)..HEAD"
    echo ""
    echo "  Step 2 — strip them via interactive rebase:"
    echo "    git rebase -i \$(git merge-base HEAD $BASE_BRANCH)"
    echo "    # For each offending commit, edit it and run:"
    echo "    git restore --staged --worktree -- '.hyperloop/state/'"
    echo "    git rebase --continue"
    echo ""
    echo "  Step 3 — verify the file no longer appears in any diff:"
    echo "    git diff --name-only \$(git merge-base HEAD $BASE_BRANCH)..HEAD -- '.hyperloop/state/'"
  fi
fi

if [[ -n "$deleted_from_alpha" ]]; then
  echo ""
  echo "── DELETED from $BASE_BRANCH (existed on $BASE_BRANCH, removed on this branch) ──"
  echo "$deleted_from_alpha" | sed 's/^/  /'
  echo ""
  echo "  These files EXIST on $BASE_BRANCH but were deleted by commits on this"
  echo "  branch. They must be RESTORED to match $BASE_BRANCH:"
  echo ""
  echo "  git checkout $BASE_BRANCH -- <file>"
  echo "  git commit -m 'chore: restore $BASE_BRANCH state files removed by branch commits'"
fi

echo ""
echo "IMPORTANT: Fixing only one direction (added OR deleted) is PARTIAL."
echo "After any fix, re-run this script and confirm PASS before proceeding."
exit 1
