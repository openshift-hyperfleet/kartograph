#!/usr/bin/env bash
# check-worker-result-not-committed.sh
#
# Fails if .hyperloop/worker-result.yaml appears anywhere in the commits added
# by this branch versus the base branch — including as an addition, modification,
# OR deletion.
#
# WHY: worker-result.yaml is an ephemeral protocol artifact written by verifiers
# as a verdict handoff file. It must NEVER appear in the commit history of a task
# branch for two reasons:
#
#   1. Committing it contaminates the branch with orchestrator-internal state,
#      making the branch non-deterministic across cycles (different rounds write
#      different verdicts, causing perpetual rebase conflicts).
#
#   2. Even a *deletion* commit is flagged. If the file was accidentally committed
#      in commit A and then deleted in commit B, both commits appear in the branch
#      diff and both are violations. The ONLY correct fix is `git rebase -i` to
#      excise commit A from history entirely — so neither commit A nor the deletion
#      appears in the branch log.
#
# CORRECT REMEDIATION:
#   git rebase -i $(git merge-base HEAD alpha)
#   # In the editor, "edit" the offending commit, then:
#   git restore --staged --worktree -- .hyperloop/worker-result.yaml
#   git rebase --continue
#   # Re-run this check: exit 0 means the file is gone from history.
#
# WRONG REMEDIATION (do not do this):
#   git rm .hyperloop/worker-result.yaml && git commit  # leaves the deletion in history
#
# Usage:
#   bash .hyperloop/checks/check-worker-result-not-committed.sh [base_branch]
#
# Exit 0 — worker-result.yaml does not appear in any branch commit.
# Exit 1 — worker-result.yaml appears in the branch history (add, modify, or delete).

set -uo pipefail

TARGET_FILE=".hyperloop/worker-result.yaml"

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
  echo "WARNING: Could not detect base branch — skipping worker-result check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH — skipping check."
  exit 0
fi

echo "=== Checking that $TARGET_FILE never appears in branch commits (base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="

# Check all diff-filter variants: Added, Copied, Deleted, Modified, Renamed
touches=$(git diff --name-only "$MERGE_BASE" HEAD -- "$TARGET_FILE" 2>/dev/null || true)

if [[ -z "$touches" ]]; then
  echo "PASS: $TARGET_FILE does not appear in any commit on this branch."
  exit 0
fi

# Find the specific commits that touch the file for diagnostic output
offending_commits=$(git log --oneline "$MERGE_BASE"..HEAD -- "$TARGET_FILE" 2>/dev/null || true)

echo ""
echo "FAIL: $TARGET_FILE appears in the commit history of this branch."
echo ""
echo "Offending commits:"
echo "$offending_commits" | sed 's/^/  /'
echo ""
echo "worker-result.yaml is an ephemeral protocol artifact and must NEVER appear"
echo "in any task-branch commit — including as an addition, modification, or deletion."
echo ""
echo "── CORRECT FIX ────────────────────────────────────────────────────────────"
echo ""
echo "  Step 1 — open an interactive rebase from the merge-base:"
echo "    git rebase -i \$(git merge-base HEAD $BASE_BRANCH)"
echo ""
echo "  Step 2 — in the editor, change 'pick' to 'edit' for each offending commit."
echo ""
echo "  Step 3 — when the rebase pauses at each offending commit, unstage/remove"
echo "           the file and continue:"
echo "    git restore --staged --worktree -- .hyperloop/worker-result.yaml"
echo "    git rebase --continue"
echo ""
echo "  Step 4 — confirm the file is gone from history:"
echo "    bash .hyperloop/checks/check-worker-result-not-committed.sh"
echo ""
echo "── WRONG FIX (do not do this) ─────────────────────────────────────────────"
echo ""
echo "  git rm .hyperloop/worker-result.yaml && git commit"
echo ""
echo "  This leaves a DELETION commit in the branch log, which this check also"
echo "  flags. The file must not appear in ANY commit — including a deletion."
echo ""
exit 1
