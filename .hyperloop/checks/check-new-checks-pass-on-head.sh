#!/usr/bin/env bash
# check-new-checks-pass-on-head.sh
#
# Runs every new check script added by this branch and verifies each one
# exits 0 on the current HEAD.
#
# WHY: A check script that is introduced by a branch but immediately fails on
# that same branch is a process regression: the new enforcement rule cannot be
# satisfied by the work that created it. This is always a sign that either:
#   (a) The check detects a real violation that must be fixed before merging, OR
#   (b) The check itself is buggy and exits 1 on valid code (false positive).
# Both cases must be resolved before the PR can merge.
#
# The task-003 example: check-no-foreign-task-commits.sh was added by the branch
# but immediately failed because the branch itself contained a foreign commit
# (1b0f2478, Task-Ref: task-032). This is case (a) — the violation is real.
#
# NOTE: This script does NOT run itself recursively. It skips any script whose
# name matches its own basename.
#
# Usage:
#   bash .hyperloop/checks/check-new-checks-pass-on-head.sh [base_branch]
#
# Exit 0 — all new check scripts pass on the current HEAD.
# Exit 1 — one or more new check scripts fail.

set -uo pipefail

CHECKS_DIR=".hyperloop/checks"
SELF=$(basename "${BASH_SOURCE[0]}")

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
  echo "WARNING: Could not detect base branch — skipping new-check validation."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH — skipping check."
  exit 0
fi

echo "=== Checking that new check scripts pass on HEAD (base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="
echo ""

# Find check scripts that were ADDED by this branch (not present at merge-base)
new_checks=$(git diff --name-only --diff-filter=A "$MERGE_BASE" HEAD -- "${CHECKS_DIR}/*.sh" 2>/dev/null || true)

if [[ -z "$new_checks" ]]; then
  echo "PASS: No new check scripts added by this branch — nothing to validate."
  exit 0
fi

echo "New check scripts introduced by this branch:"
echo "$new_checks" | sed 's/^/  /'
echo ""

# Determine the expected task ref from the current branch name (if this is a task branch).
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)
EXPECTED_TASK=$(echo "$CURRENT_BRANCH" | grep -oE 'task-[0-9]+' | head -1 || true)

FAILED=()
PASSED=()
SKIPPED_FOREIGN=()

while IFS= read -r check_path; do
  check_name=$(basename "$check_path")

  # Skip self to prevent infinite recursion
  if [[ "$check_name" == "$SELF" ]]; then
    echo "── $check_name — SKIPPED (self)"
    echo ""
    continue
  fi

  if [[ ! -f "$check_path" ]]; then
    echo "── $check_name — MISSING (not found at $check_path)"
    FAILED+=("$check_name (MISSING)")
    echo ""
    continue
  fi

  # On a task branch, skip scripts introduced by foreign (non-matching) commits.
  # A process-improvement agent that committed to the wrong branch may introduce
  # a check script that detects task-branch contamination and intentionally exits 1
  # on any task branch — running it here would cascade check-no-foreign-task-commits.sh
  # failures into a second, misleading FAIL under this script.
  if [[ -n "$EXPECTED_TASK" ]]; then
    intro_commit=$(git log --format="%H" "$MERGE_BASE"..HEAD -- "$check_path" 2>/dev/null | tail -1 || true)
    if [[ -n "$intro_commit" ]]; then
      intro_task_ref=$(git log -1 --format="%(trailers:key=Task-Ref,valueonly)" "$intro_commit" 2>/dev/null \
        | tr -d '[:space:]' || true)
      if [[ -n "$intro_task_ref" && "$intro_task_ref" != "$EXPECTED_TASK" ]]; then
        echo "── $check_name — SKIPPED (introduced by foreign commit ${intro_commit:0:10}, Task-Ref: $intro_task_ref != $EXPECTED_TASK)"
        echo "   check-no-foreign-task-commits.sh already flags this contamination."
        SKIPPED_FOREIGN+=("$check_name (foreign: $intro_task_ref)")
        echo ""
        continue
      fi
    fi
  fi

  echo "── $check_name ──────────────────────────────────────"
  if bash "$check_path" < /dev/null; then
    PASSED+=("$check_name")
  else
    FAILED+=("$check_name")
  fi
  echo ""
done <<< "$new_checks"

echo "========================================================"
echo " New-check validation summary"
echo "========================================================"
echo ""

if [[ ${#PASSED[@]} -gt 0 ]]; then
  echo "PASSED (${#PASSED[@]}):"
  for c in "${PASSED[@]}"; do
    echo "  ✓ $c"
  done
  echo ""
fi

if [[ ${#SKIPPED_FOREIGN[@]} -gt 0 ]]; then
  echo "SKIPPED — foreign-commit contamination (${#SKIPPED_FOREIGN[@]}):"
  for c in "${SKIPPED_FOREIGN[@]}"; do
    echo "  ⚠ $c"
  done
  echo "  (check-no-foreign-task-commits.sh is the authoritative failure for these)"
  echo ""
fi

if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo "FAILED (${#FAILED[@]}):"
  for c in "${FAILED[@]}"; do
    echo "  ✗ $c"
  done
  echo ""
  echo "A new check script that fails on HEAD means either:"
  echo "  (a) The check detected a real violation — fix the violation and re-run."
  echo "  (b) The check has a false-positive bug — fix the script and re-run."
  echo ""
  echo "FAIL: New check scripts must pass on HEAD before the branch can merge."
  exit 1
fi

echo "PASS: All ${#PASSED[@]} new check script(s) pass on HEAD."
exit 0
