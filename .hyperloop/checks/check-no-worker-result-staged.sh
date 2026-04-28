#!/usr/bin/env bash
# check-no-worker-result-staged.sh
#
# Fails if .hyperloop/worker-result.yaml is currently staged in any form:
# addition, modification, or deletion.
#
# PURPOSE: This is a PRE-COMMIT gate. Run it before every `git commit` to
# catch a staged deletion (or addition) before it becomes a branch-history
# violation that check-worker-result-not-committed.sh will flag as a hard FAIL.
#
# The most common failure mode is:
#   - worker-result.yaml exists on the base branch (alpha) and is inherited
#     by the task branch.
#   - The implementer sees it in `git status` and deletes it as "cleanup" via
#     `git rm` or manual deletion + `git add`.
#   - The deletion is committed alongside legitimate changes.
#
# CORRECT FIX (run before committing):
#   git restore --staged --worktree -- .hyperloop/worker-result.yaml
#
# Exit 0 — file is NOT staged; safe to commit.
# Exit 1 — file IS staged (as add, modify, or delete); commit is blocked.

set -uo pipefail

TARGET_FILE=".hyperloop/worker-result.yaml"

staged=$(git diff --cached --name-only -- "$TARGET_FILE" 2>/dev/null || true)

if [[ -z "$staged" ]]; then
  echo "PASS: $TARGET_FILE is not staged — safe to commit."
  exit 0
fi

# Determine what kind of staged change this is for a clearer message
staged_status=$(git diff --cached --name-status -- "$TARGET_FILE" 2>/dev/null | awk '{print $1}' || true)

echo ""
echo "FAIL: $TARGET_FILE is staged (status: ${staged_status:-unknown})."
echo ""
echo "worker-result.yaml is an ephemeral protocol artifact. It must NEVER be"
echo "staged or committed — not as an addition, modification, or deletion."
echo ""
echo "── CORRECT FIX ────────────────────────────────────────────────────────────"
echo ""
echo "  Unstage the file (and restore it if deleted) with:"
echo "    git restore --staged --worktree -- .hyperloop/worker-result.yaml"
echo ""
echo "  Then re-run this check to confirm:"
echo "    bash .hyperloop/checks/check-no-worker-result-staged.sh"
echo ""
echo "── WHY NOT git rm? ────────────────────────────────────────────────────────"
echo ""
echo "  If the file exists on the base branch, its presence on your task branch"
echo "  is expected and harmless. You MUST NOT delete it. check-worker-result-"
echo "  not-committed.sh flags any branch-history touch — including a deletion"
echo "  commit — as a hard FAIL that requires interactive rebase to fix."
echo ""
exit 1
