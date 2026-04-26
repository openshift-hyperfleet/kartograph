#!/usr/bin/env bash
# check-git-state-exclude.sh
#
# Verifies that .git/info/exclude contains a pattern that prevents
# .hyperloop/state/ files from appearing in 'git status' and being
# swept up by 'git add .' or 'git add -A'.
#
# WHY: The orchestrator runs background workers (intake, reviews) that write
# to .hyperloop/state/ while a task branch is checked out. Without an exclude
# entry, any 'git add .' or 'git add -A' command silently stages these files,
# embedding orchestrator metadata in task commits. Once committed, they cause
# permanent 3-way merge conflicts on every subsequent rebase and require a
# full branch abandon to fix — the failure pattern observed in task-034
# (4 state files across 4 crash-caused commits) and task-003.
#
# SCOPE: This is an IMPLEMENTER-ONLY check. Verifiers do not need it because
# they do not perform commits. Do NOT add this check to check-run-backend-suite.sh.
#
# Rule reference: implementer-overlay.yaml — rule 81 (add exclude at branch creation)
#
# WHEN TO RUN:
#   Immediately after branch creation and push — before any other action.
#   Re-run if you switch worktrees or open a new session on the same branch.
#
# Usage:
#   bash .hyperloop/checks/check-git-state-exclude.sh
#
# Exit 0  — .git/info/exclude protects .hyperloop/state/ (or no state/ dir exists)
# Exit 1  — exclude is missing and state/ files are present; branch is vulnerable

set -euo pipefail

EXCLUDE_FILE=".git/info/exclude"
STATE_DIR=".hyperloop/state"

echo "=== Checking .git/info/exclude for .hyperloop/state/ protection ==="

# If we are not in a git repo, skip gracefully
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "INFO: Not inside a git repository — skipping exclude check."
  exit 0
fi

GIT_DIR=$(git rev-parse --git-dir)
EXCLUDE_FILE="${GIT_DIR}/info/exclude"

# Check whether any exclude pattern covers .hyperloop/state/
exclude_present=0
if [[ -f "$EXCLUDE_FILE" ]]; then
  # Accept any of: .hyperloop/state/, .hyperloop/state, .hyperloop/
  if grep -qE '\.hyperloop/(state/?|)$' "$EXCLUDE_FILE" 2>/dev/null; then
    exclude_present=1
  fi
fi

if [[ "$exclude_present" -eq 1 ]]; then
  echo "OK: .git/info/exclude contains a .hyperloop/state/ protection pattern."
  echo ""
  echo "Matching lines:"
  grep -E '\.hyperloop/' "$EXCLUDE_FILE" | sed 's/^/  /'
  exit 0
fi

# Exclude is missing — is there any actual risk?
if [[ ! -d "$STATE_DIR" ]]; then
  echo "ADVISORY: .git/info/exclude does not protect .hyperloop/state/, but"
  echo "no $STATE_DIR directory exists yet. The risk is low now but will"
  echo "increase as the orchestrator writes intake and task state files."
  echo ""
  echo "Add protection now to prevent future accidental commits:"
  echo "  echo '.hyperloop/state/' >> \"\$(git rev-parse --git-dir)/info/exclude\""
  exit 1
fi

# Exclude is missing AND state directory exists — this is the dangerous case
state_files=$(find "$STATE_DIR" -type f 2>/dev/null | head -5 || true)

echo ""
echo "FAIL: .git/info/exclude does NOT protect .hyperloop/state/"
echo ""
echo "  The $STATE_DIR directory exists and contains orchestrator-managed files."
echo "  Without an exclude entry, any 'git add .' or 'git add -A' command will"
echo "  stage these files, causing them to appear in task branch commits."
echo ""
if [[ -n "$state_files" ]]; then
  echo "  Example state files that are currently visible to git:"
  echo "$state_files" | sed 's/^/    /'
  echo ""
fi

# Show current git status for state files to illustrate the risk
untracked_state=$(git status --short -- '.hyperloop/state/' 2>/dev/null | head -10 || true)
if [[ -n "$untracked_state" ]]; then
  echo "  Current 'git status' for .hyperloop/state/ (these would be added by 'git add .'):"
  echo "$untracked_state" | sed 's/^/    /'
  echo ""
fi

echo "  FIX — add the protection entry now:"
echo ""
echo "    echo '.hyperloop/state/' >> \"\$(git rev-parse --git-dir)/info/exclude\""
echo ""
echo "  Then verify:"
echo "    bash .hyperloop/checks/check-git-state-exclude.sh"
echo ""
echo "  This is a LOCAL setting — it does not affect other worktrees or the remote."
echo "  You must re-add it when opening a new session on this branch in a new worktree."
exit 1
