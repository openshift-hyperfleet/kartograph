#!/usr/bin/env bash
# check-commit-msg-hook-has-guard.sh
#
# Fails if the git commit-msg hook is absent or does not contain the
# task-ref trailer guard installed by install-git-commit-msg-hook.sh.
#
# WHY: The commit-msg hook is the ONLY mechanism that catches broken trailer
# blocks (a blank line between Task-Ref: and Co-Authored-By:) AT COMMIT TIME,
# before the bad commit enters branch history. When the hook is not installed,
# malformed trailer blocks slip past git commit, fail check-all-commits-have-
# task-ref.sh and check-task-owns-branch-commits.sh at suite time, and require
# an interactive rebase to fix — a slow and error-prone remediation.
#
# ROOT CAUSE HISTORY:
#   task-133: blank line between Task-Ref and Co-Authored-By broke the trailer
#             block; commit-msg hook was not installed; suite FAILed.
#   task-150: same root cause; commit-msg hook not installed; suite FAILed.
#
# INSTALL THE HOOK:
#   bash .hyperloop/checks/install-git-commit-msg-hook.sh
#
# The hook fires automatically at every `git commit` — including quick fix-up
# and documentation commits — and rejects messages that lack a parseable
# Task-Ref trailer or have a blank line within the trailer block.
#
# Usage:
#   bash .hyperloop/checks/check-commit-msg-hook-has-guard.sh
#
# Exit 0 — commit-msg hook is installed and contains the trailer guard.
# Exit 1 — hook is absent or missing the guard.

set -uo pipefail

GUARD_MARKER="# task-ref trailer guard (hyperloop)"

GIT_DIR="$(git rev-parse --git-dir 2>/dev/null)" || {
  echo "WARNING: Not inside a git repository — skipping commit-msg hook check."
  exit 0
}

HOOK_FILE="$GIT_DIR/hooks/commit-msg"

echo "=== Checking commit-msg hook has task-ref trailer guard ==="
echo ""
echo "Hook path: $HOOK_FILE"
echo ""

if [[ ! -f "$HOOK_FILE" ]]; then
  echo "FAIL: commit-msg hook not found at $HOOK_FILE"
  echo ""
  echo "The hook must be installed BEFORE your first commit so that every"
  echo "subsequent commit is checked for a valid, contiguous trailer block."
  echo ""
  echo "A blank line between Task-Ref: and Co-Authored-By: causes git to"
  echo "discard Task-Ref as a trailer, making check-all-commits-have-task-ref.sh"
  echo "and check-task-owns-branch-commits.sh fail even though the text"
  echo "'Task-Ref: task-NNN' appears in the commit body."
  echo ""
  echo "Install the hook now:"
  echo "  bash .hyperloop/checks/install-git-commit-msg-hook.sh"
  echo ""
  echo "Then verify ALL existing commits on this branch have valid trailers:"
  echo "  bash .hyperloop/checks/check-all-commits-have-task-ref.sh"
  echo ""
  echo "(If any existing commits have broken trailer blocks, amend or rebase"
  echo " them to produce a contiguous trailer block before submitting.)"
  exit 1
fi

if ! grep -qF "$GUARD_MARKER" "$HOOK_FILE" 2>/dev/null; then
  echo "FAIL: commit-msg hook exists but is missing the task-ref trailer guard."
  echo ""
  echo "The hook at $HOOK_FILE does not contain:"
  echo "  $GUARD_MARKER"
  echo ""
  echo "This means the hook will not enforce Task-Ref trailer presence or"
  echo "contiguous trailer blocks. Reinstall the guard:"
  echo ""
  echo "  bash .hyperloop/checks/install-git-commit-msg-hook.sh"
  echo ""
  exit 1
fi

echo "PASS: commit-msg hook is installed and contains the task-ref trailer guard."
exit 0
