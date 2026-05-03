#!/usr/bin/env bash
# check-no-merge-commits.sh
#
# Fails if any commit on the current branch (between merge-base and HEAD)
# is a merge commit (has more than one parent).
#
# WHY THIS CHECK:
#   task-100: The implementer ran `git merge origin/main` instead of the
#   spec-mandated `git rebase alpha`. The merge commit (079d29d65) was
#   silently missed by check-no-foreign-task-commits.sh because that check
#   only inspects direct commits in the merge-base..HEAD range — the 31
#   foreign commits from main came in as ANCESTORS of the merge commit, not
#   as first-parent commits, so they were never examined for Task-Ref. The
#   merge commit itself had no Task-Ref trailer and was only warned about,
#   not failed. The resulting branch:
#     1. Contained 31 release-note and deploy-image commits from main.
#     2. Deleted src/dev-ui/app/tests/navigation-structure.test.ts because
#        main had not yet received alpha's task-119 work.
#     3. Failed check-no-test-regressions.sh on the deleted file.
#
#   Merge commits on task branches are ALWAYS a protocol violation. The only
#   permitted way to incorporate upstream changes is `git rebase alpha`.
#   When rebase conflicts arise (e.g. in uv.lock), resolve them inline:
#     uv lock && git add src/api/uv.lock && git rebase --continue
#
# Usage:
#   bash .hyperloop/checks/check-no-merge-commits.sh [base_branch]
#
# Exit 0 — no merge commits found between merge-base and HEAD.
# Exit 1 — one or more merge commits found on this branch.

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
  echo "WARNING: Could not detect base branch — skipping merge-commit check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH — skipping check."
  exit 0
fi

echo "=== Checking for merge commits on branch (base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="
echo ""

# List commits between merge-base and HEAD that have more than one parent.
# --merges: only outputs commits with 2+ parents (merge commits).
merge_commits=$(git log --merges --format="%H %s" "$MERGE_BASE"..HEAD 2>/dev/null || true)

if [[ -z "$merge_commits" ]]; then
  echo "PASS: No merge commits found on this branch — rebase discipline maintained."
  exit 0
fi

echo "FAIL: Merge commit(s) found on this branch:"
echo ""
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  sha="${line%% *}"
  subject="${line#* }"
  parents=$(git log -1 --format="%P" "$sha" 2>/dev/null || true)
  echo "  ${sha:0:10}  $subject"
  echo "  Parents: $parents"
  echo ""
done <<< "$merge_commits"

echo "Merge commits are NEVER permitted on task branches.  A merge commit"
echo "introduces its ancestor commits into the branch as non-first-parent"
echo "history, which:"
echo "  1. Bypasses check-no-foreign-task-commits.sh — foreign ancestor"
echo "     commits are invisible to the merge-base..HEAD range walk."
echo "  2. May delete files present on alpha but absent from the merged ref."
echo "  3. Makes the task branch non-isolatable for review and rebase."
echo ""
echo "Resolution:"
echo "  1. Identify the commit BEFORE the bad merge:"
echo "     git log --oneline \$(git merge-base HEAD $BASE_BRANCH)..HEAD"
echo "  2. Reset to that commit:"
echo "     git reset --hard <sha-before-merge>"
echo "  3. Rebase onto alpha (the ONLY permitted integration mechanism):"
echo "     git rebase alpha"
echo "  4. If uv.lock conflicts during rebase:"
echo "     uv lock && git add src/api/uv.lock && git rebase --continue"
exit 1
