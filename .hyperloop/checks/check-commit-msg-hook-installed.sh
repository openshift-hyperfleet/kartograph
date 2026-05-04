#!/usr/bin/env bash
# check-commit-msg-hook-installed.sh
#
# Verifies the commit-msg hook containing the task-ref trailer guard is
# installed in the current git worktree's .git/hooks/commit-msg file.
#
# WHY:
#   The commit-msg hook is the ONLY mechanical gate that catches a broken
#   trailer block (blank line between Task-Ref: and Co-Authored-By:) AT
#   COMMIT TIME — before the commit enters history. If the hook is absent,
#   broken trailer blocks are only caught post-hoc by check-all-commits-have-
#   task-ref.sh during the backend suite. At that point the commit is in
#   history and requires an interactive rebase to fix.
#
#   task-133 and task-137 both failed due to blank lines within trailer
#   blocks. The commit-msg hook already detects this case; its absence is
#   the root cause of both recurring failures.
#
# GUARD MARKER: The hook is considered installed when .git/hooks/commit-msg
#   contains the line "# task-ref trailer guard (hyperloop)". This is the
#   exact marker written by install-git-commit-msg-hook.sh.
#
# Usage:
#   bash .hyperloop/checks/check-commit-msg-hook-installed.sh
#
# Exit 0 — commit-msg hook is installed with the task-ref trailer guard.
# Exit 1 — hook is absent or missing the guard.

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "WARNING: Not inside a git repository — skipping commit-msg hook check."
  exit 0
}

GIT_DIR="$(git rev-parse --git-dir 2>/dev/null)"
HOOK_FILE="$GIT_DIR/hooks/commit-msg"
GUARD_MARKER="# task-ref trailer guard (hyperloop)"

echo "=== Checking commit-msg hook installation ==="
echo ""
echo "Expected hook: $HOOK_FILE"
echo "Required marker: $GUARD_MARKER"
echo ""

if [[ ! -f "$HOOK_FILE" ]]; then
  echo "FAIL: $HOOK_FILE does not exist."
  echo ""
  echo "The commit-msg hook is the mechanical gate that prevents blank lines"
  echo "within trailer blocks from entering history. Without it, broken trailer"
  echo "blocks are only caught post-hoc by check-all-commits-have-task-ref.sh,"
  echo "requiring an interactive rebase to repair."
  echo ""
  echo "Install the hook NOW (before your next commit):"
  echo ""
  echo "  bash .hyperloop/checks/install-git-commit-msg-hook.sh"
  echo ""
  exit 1
fi

if ! grep -qF "$GUARD_MARKER" "$HOOK_FILE" 2>/dev/null; then
  echo "FAIL: $HOOK_FILE exists but does not contain the task-ref trailer guard."
  echo ""
  echo "The hook was installed without the guard (possibly by another tool)."
  echo "Append the guard now:"
  echo ""
  echo "  bash .hyperloop/checks/install-git-commit-msg-hook.sh"
  echo ""
  exit 1
fi

echo "PASS: commit-msg hook is installed and contains the task-ref trailer guard."
exit 0
