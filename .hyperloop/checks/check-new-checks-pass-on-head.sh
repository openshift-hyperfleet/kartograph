#!/usr/bin/env bash
# check-new-checks-pass-on-head.sh
#
# Verifies that any check script NEWLY ADDED on this branch (vs the alpha
# merge-base) passes against the current codebase before it can enter the suite.
#
# WHY THIS MATTERS
# ----------------
# When a process-improvement branch adds a new check script AND includes it
# in check-run-backend-suite.sh, that check becomes mandatory for every
# subsequent task that rebases onto alpha. If existing code already violates
# the check, EVERY task inherits the violation — including tasks whose work
# predates the check's introduction.
#
# This was the root cause of the task-017 and task-019 cycle failures:
#   check-cascade-delete-empty-collection-mocks.sh was added to alpha while
#   test_tenant_service.py::TestDeleteTenant already violated it. Both tasks
#   were blocked not for their own work but for a pre-existing violation
#   they could not have anticipated.
#
# WHAT IS CHECKED
# ---------------
# 1. Find any .sh files under .hyperloop/checks/ added on this branch
#    (git diff --diff-filter=A vs the alpha merge-base).
# 2. Run each newly added check against the current working tree.
# 3. Exit 1 if any newly added check exits non-zero.
#
# A process-improvement branch that adds both a check AND companion fix
# commits for all existing violations will pass this gate. A branch that
# adds the check without fixing violations will fail here — requiring the
# author to include fix commits before the check is activated in the suite.
#
# SCOPE EXCLUSION
# ---------------
# Meta-infrastructure scripts are excluded from their own validation to
# avoid infinite recursion and circular dependencies:
#   - check-new-checks-pass-on-head.sh  (this script)
#   - check-run-backend-suite.sh        (meta-runner, not a content check)
#   - check-no-check-script-deletions.sh (integrity guard, not content check)
#
# Usage:
#   bash .hyperloop/checks/check-new-checks-pass-on-head.sh
#
# Exit 0 — all newly added check scripts pass on the current codebase,
#           OR no new check scripts were added on this branch.
# Exit 1 — at least one newly added check script fails on the current
#           codebase (existing violations must be fixed before merging).

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"

# Compute merge-base with alpha (local ref — orchestrator advances local alpha
# independently and may not push to origin/alpha, so always use local ref).
MERGE_BASE="$(git merge-base HEAD alpha 2>/dev/null || true)"

if [[ -z "$MERGE_BASE" ]]; then
  echo "SKIP: Cannot compute merge-base with local 'alpha' ref."
  echo "PASS: Skipping new-check validation (no common ancestor with alpha)."
  exit 0
fi

# Meta-infrastructure scripts excluded from self-validation.
EXCLUDED=(
  "check-new-checks-pass-on-head.sh"
  "check-run-backend-suite.sh"
  "check-no-check-script-deletions.sh"
)

# Find newly added check scripts on this branch (paths relative to repo root).
mapfile -t NEW_CHECK_PATHS < <(
  git diff --name-only --diff-filter=A "$MERGE_BASE" HEAD -- '.hyperloop/checks/' 2>/dev/null \
  | grep '\.sh$' || true
)

if [[ ${#NEW_CHECK_PATHS[@]} -eq 0 ]]; then
  echo "PASS: No new check scripts added on this branch — nothing to validate."
  exit 0
fi

echo "=== Validating newly added check scripts against current codebase ==="
echo ""
echo "  Merge-base : $MERGE_BASE"
echo "  New scripts : ${#NEW_CHECK_PATHS[@]}"
echo ""

FAILED=()
SKIPPED=()
PASSED=()

for rel_path in "${NEW_CHECK_PATHS[@]}"; do
  check_name="$(basename "$rel_path")"

  # Skip meta-infrastructure scripts.
  is_excluded=0
  for excl in "${EXCLUDED[@]}"; do
    if [[ "$check_name" == "$excl" ]]; then
      is_excluded=1
      break
    fi
  done
  if [[ $is_excluded -eq 1 ]]; then
    SKIPPED+=("$check_name (meta-infrastructure)")
    continue
  fi

  full_path="$REPO_ROOT/$rel_path"
  if [[ ! -f "$full_path" ]]; then
    echo "  WARNING: $check_name listed by git-diff but absent at $full_path — skipping."
    SKIPPED+=("$check_name (file not found)")
    continue
  fi

  echo "  Running: $check_name"
  tmp_out="$(mktemp)"
  if bash "$full_path" > "$tmp_out" 2>&1; then
    PASSED+=("$check_name")
    echo "    ✓ PASS"
  else
    FAILED+=("$check_name")
    echo "    ✗ FAIL — output:"
    sed 's/^/      /' "$tmp_out"
  fi
  rm -f "$tmp_out"
  echo ""
done

echo "=== Summary ==="
echo ""

if [[ ${#PASSED[@]} -gt 0 ]]; then
  echo "PASSED (${#PASSED[@]}):"
  for c in "${PASSED[@]}"; do echo "  ✓ $c"; done
  echo ""
fi

if [[ ${#SKIPPED[@]} -gt 0 ]]; then
  echo "SKIPPED (${#SKIPPED[@]}):"
  for c in "${SKIPPED[@]}"; do echo "  - $c"; done
  echo ""
fi

if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo "FAILED (${#FAILED[@]}):"
  for c in "${FAILED[@]}"; do echo "  ✗ $c"; done
  echo ""
  echo "FAIL: Newly added check scripts must pass on the current codebase before"
  echo "      they are activated in the backend suite.  Fix all violations reported"
  echo "      above and include the fix commits on the same branch as the check."
  echo ""
  echo "  Root cause of task-017/task-019: check-cascade-delete-empty-collection-"
  echo "  mocks.sh was merged to alpha while test_tenant_service.py::TestDeleteTenant"
  echo "  already violated it.  Every task that rebased onto alpha inherited the"
  echo "  violation and was blocked — even though the tasks never touched that file."
  exit 1
fi

echo "PASS: All newly added check scripts pass on the current codebase."
exit 0
