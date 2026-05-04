#!/usr/bin/env bash
# check-no-check-script-modifications.sh
#
# Fails if any commit on the current task branch MODIFIES an existing check
# script under .hyperloop/checks/.
#
# WHY THIS CHECK:
#   task-044: Commit 8f0ff4ab5 added `--exclude-dir=.venv` to
#   check-no-api-simulation.sh and was committed directly on hyperloop/task-044.
#   The commit carried Task-Ref: task-044 so check-no-foreign-task-commits.sh
#   did not catch it. check-no-check-script-deletions.sh only looks for
#   deletions and missing .venv exclusions — it does not block modifications.
#   The violation was detected only by manual verifier inspection.
#
#   Check script edits are process-improvement work. They must land on a
#   dedicated process-improvement branch (branched from alpha), not on any
#   hyperloop/task-NNN branch.
#
# CORRECT RESPONSE when a check script produces a false positive:
#   1. Apply the fix locally WITHOUT committing it (so the suite can run).
#   2. Raise a process-improvement note for the orchestrator.
#   3. NEVER commit the fix to the task branch.
#
# COMPLEMENTARY CHECKS:
#   - check-no-check-script-deletions.sh   — catches deleted/sabotaged scripts
#   - check-new-checks-pass-on-head.sh     — validates newly ADDED scripts
#   - This script — catches MODIFICATIONS to pre-existing scripts
#
# NOTE: This check skips non-task branches (it only applies to
#       hyperloop/task-NNN branches where the rule is meaningful).
#
# Usage:
#   bash .hyperloop/checks/check-no-check-script-modifications.sh
#
# Exit 0 — no modifications to existing check scripts on this task branch.
# Exit 1 — one or more pre-existing check scripts were modified on task branch.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

CHECKS_DIR=".hyperloop/checks"

# ── Only applies on task branches ─────────────────────────────────────────────
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)

if [[ -z "$BRANCH" || "$BRANCH" == "HEAD" ]]; then
  echo "WARNING: Detached HEAD — cannot determine branch; skipping check."
  exit 0
fi

if ! echo "$BRANCH" | grep -qE '^hyperloop/task-[0-9]+'; then
  echo "PASS: Not a task branch ('$BRANCH') — check does not apply."
  exit 0
fi

# ── Resolve base branch ────────────────────────────────────────────────────────
BASE_BRANCH=""
for candidate in alpha main master; do
  if git show-ref --verify --quiet "refs/heads/$candidate" 2>/dev/null || \
     git show-ref --verify --quiet "refs/remotes/origin/$candidate" 2>/dev/null; then
    BASE_BRANCH="$candidate"
    break
  fi
done

if [[ -z "$BASE_BRANCH" ]]; then
  echo "WARNING: Could not detect base branch — skipping check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH — skipping check."
  exit 0
fi

echo "=== Checking for check-script modifications on task branch (base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="

# ── Find MODIFIED (not added, not deleted) check scripts ──────────────────────
# diff-filter=M: only files that existed at merge-base and were modified.
modified_scripts=$(git diff --name-only --diff-filter=M "$MERGE_BASE" HEAD \
  -- "${CHECKS_DIR}/*.sh" 2>/dev/null || true)

echo ""

if [[ -z "$modified_scripts" ]]; then
  echo "PASS: No modifications to pre-existing check scripts on this task branch."
  exit 0
fi

echo "FAIL: Pre-existing check scripts were modified on this task branch:"
echo "$modified_scripts" | sed 's/^/  /'
echo ""
echo "Check script edits are process-improvement work and must NOT land on"
echo "hyperloop/task-NNN branches. When a check script produces a false positive:"
echo ""
echo "  CORRECT: Apply the fix locally WITHOUT committing it so the suite"
echo "           passes locally, then raise a process-improvement note for"
echo "           the orchestrator to land the fix on a dedicated branch."
echo ""
echo "  WRONG:   Commit the fix to the task branch (even with a matching"
echo "           Task-Ref: task-NNN trailer — the trailer is not the issue;"
echo "           the file being in .hyperloop/checks/ is)."
echo ""
echo "To remove the offending commit(s) from this branch:"
echo "  git rebase -i \$(git merge-base HEAD $BASE_BRANCH)"
echo "  # Mark the commit(s) touching .hyperloop/checks/ as 'drop'"
echo ""
exit 1
