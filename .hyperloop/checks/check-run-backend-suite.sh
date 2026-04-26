#!/usr/bin/env bash
# check-run-backend-suite.sh
#
# Runs ALL backend-universal check scripts in the required sequence and
# prints a consolidated pass/fail summary.
#
# PURPOSE: This is the canonical pre-verdict batch command for backend tasks.
# Running checks individually across a long verification session allows state
# to change between checks (alpha advances, state files accumulate). Running
# this script as the LAST action before writing a verdict guarantees all
# checks reflect a consistent, current state.
#
# NON-FRONTEND checks only. Frontend-specific checks (check-frontend-*.sh,
# check-selector-forwarding.sh, etc.) must be run separately when the task
# touches src/dev-ui.
#
# Usage:
#   bash .hyperloop/checks/check-run-backend-suite.sh
#
# Exit 0  — all included checks passed.
# Exit 1  — one or more checks failed (summary printed at end).

set -uo pipefail

CHECKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Normalize CWD to repo root before running any checks.
#
# WHY: Every check script in this suite uses git pathspecs such as
# '.hyperloop/state/' and 'src/'. Git interprets these pathspecs relative to
# $PWD, not to the repository root. Running this suite from .hyperloop/checks/
# (or any other subdirectory) causes all those pathspecs to silently match
# nothing, making every content check return a false PASS.
#
# Observed failure (task-017, task-019): verifier invoked this script from
# .hyperloop/checks/ → check-no-state-file-commits, check-no-source-regressions,
# and check-no-test-regressions all matched zero files and returned PASS even
# though 39 state-file commits, 2 deleted source files, and 3 deleted test files
# were present on the branch.
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$REPO_ROOT" ]]; then
  echo "ERROR: Not inside a git repository — cannot determine repo root."
  exit 1
fi
if [[ "$PWD" != "$REPO_ROOT" ]]; then
  echo "⚠  NOTICE: Suite invoked from $PWD"
  echo "   Normalizing CWD to repo root: $REPO_ROOT"
  echo "   (Running from a subdirectory causes git pathspecs to silently"
  echo "    match nothing — all content checks would produce false PASSes.)"
  echo ""
  cd "$REPO_ROOT"
fi

# Ordered list of checks to run. Order matters:
# - Infra integrity first (catch sabotage before evaluating code)
# - Staleness second (stale branch → false positives in content checks)
# - State contamination third (a contaminated branch cannot be trusted)
# - Content checks last (only meaningful on a clean, rebased branch)
CHECKS=(
  check-no-check-script-deletions.sh
  check-process-overlays-intact.sh
  check-new-checks-pass-on-head.sh
  check-branch-has-commits.sh
  check-branch-rebased-on-alpha.sh
  check-no-state-file-commits.sh
  check-no-source-regressions.sh
  check-no-test-regressions.sh
  check-empty-test-stubs.sh
  check-domain-aggregate-mocks.sh
  check-no-direct-logger-usage.sh
  check-no-coming-soon-stubs.sh
  check-weak-test-assertions.sh
  check-di-wiring-updated.sh
  check-pytest-env-skip-if-set.sh
  check-cascade-delete-empty-collection-mocks.sh
)

FAILED=()
PASSED=()

ALPHA_SHA_AT_SUITE_START="$(git rev-parse alpha 2>/dev/null || echo 'unknown')"

echo "========================================================"
echo " Backend check suite — $(date '+%Y-%m-%dT%H:%M:%S%z')"
echo " alpha: ${ALPHA_SHA_AT_SUITE_START}"
echo "========================================================"
echo ""

for check in "${CHECKS[@]}"; do
  script="$CHECKS_DIR/$check"

  if [[ ! -f "$script" ]]; then
    echo "ERROR: $check not found at $script — check-no-check-script-deletions.sh should have caught this"
    FAILED+=("$check (MISSING)")
    continue
  fi

  echo "── $check ──────────────────────────────────────"
  if bash "$script"; then
    PASSED+=("$check")
  else
    FAILED+=("$check")

    # Halt immediately when the staleness check fails.
    #
    # WHY: check-no-state-file-commits.sh computes its diff from the same
    # merge-base as check-branch-rebased-on-alpha.sh.  When the branch is
    # stale, that merge-base is OLD — state files committed AFTER the old
    # merge-base are invisible, so the state-file check produces a false PASS.
    # Continuing to run subsequent checks on a stale branch gives results that
    # CANNOT be trusted and that will change in the next round as alpha advances.
    # The only safe response is to stop, require a rebase, and re-run the suite.
    if [[ "$check" == "check-branch-rebased-on-alpha.sh" ]]; then
      echo ""
      echo "========================================================"
      echo " SUITE HALTED: branch is stale."
      echo ""
      echo " Subsequent checks (especially check-no-state-file-commits.sh)"
      echo " diff from a stale merge-base and CANNOT produce reliable results."
      echo " Continuing would mask state-file contamination and other"
      echo " violations introduced after the stale merge-base point."
      echo ""
      echo " Fix: git rebase alpha  (local ref, not origin/alpha)"
      echo " Then: bash .hyperloop/checks/check-run-backend-suite.sh"
      echo "========================================================"
      echo ""
      echo "RESULT: FAIL — branch is stale. All subsequent checks skipped."
      exit 1
    fi
  fi
  echo ""
done

echo "========================================================"
echo " Summary"
echo "========================================================"
echo ""

if [[ ${#PASSED[@]} -gt 0 ]]; then
  echo "PASSED (${#PASSED[@]}):"
  for c in "${PASSED[@]}"; do
    echo "  ✓ $c"
  done
  echo ""
fi

if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo "FAILED (${#FAILED[@]}):"
  for c in "${FAILED[@]}"; do
    echo "  ✗ $c"
  done
  echo ""
  echo "RESULT: FAIL — resolve all failing checks before submitting."
  exit 1
fi

echo "RESULT: ALL PASS — safe to submit."
exit 0
