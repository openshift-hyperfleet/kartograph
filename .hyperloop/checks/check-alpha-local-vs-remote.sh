#!/usr/bin/env bash
# check-alpha-local-vs-remote.sh
#
# Verifies that the local 'alpha' branch is not stale relative to origin/alpha.
#
# WHY: All content checks (check-no-source-regressions.sh,
# check-no-test-regressions.sh, check-no-state-file-commits.sh, etc.) diff
# against the merge-base of this branch with the local 'alpha' ref.  When local
# alpha lags behind origin/alpha, new commits already merged into alpha are
# invisible to those checks — violations introduced AFTER the stale snapshot
# silently pass.  Additionally, a stale local 'alpha' means new check scripts
# added to alpha after the worker's branch was cut are absent from the worker's
# repo, causing the backend suite to report them as MISSING and fail.
#
# WHAT IS CHECKED:
#   1. The local 'alpha' ref must not lag behind 'origin/alpha'.
#   2. If local alpha is ahead of origin/alpha (uncommitted-to-remote state),
#      that is a WARNING but not a hard failure.
#
# RESOLUTION when behind:
#   git fetch origin alpha
#   git branch -f alpha origin/alpha   # fast-forward local alpha to remote
#   # Then rebase your task branch:
#   git rebase alpha
#
# IMPORTANT: When new check scripts were added to alpha AFTER this branch was
# created, the rebase above will also pull those scripts into your worktree.
# Always re-run `bash .hyperloop/checks/check-run-backend-suite.sh` after
# rebasing.
#
# Usage:
#   bash .hyperloop/checks/check-alpha-local-vs-remote.sh
#
# Exit 0 — local alpha matches or is ahead of origin/alpha (or remote not tracked).
# Exit 1 — local alpha is behind origin/alpha.

set -uo pipefail

LOCAL_REF="alpha"
REMOTE_REF="origin/alpha"

# If local alpha branch doesn't exist, there is nothing to check.
if ! git rev-parse --verify "$LOCAL_REF" >/dev/null 2>&1; then
  echo "INFO: Local branch '$LOCAL_REF' not found — skipping alpha sync check."
  exit 0
fi

# If the remote tracking ref doesn't exist, we cannot compare.
if ! git rev-parse --verify "$REMOTE_REF" >/dev/null 2>&1; then
  echo "INFO: Remote ref '$REMOTE_REF' not found — skipping alpha sync check."
  echo "      Run 'git fetch origin' if you expect a remote alpha branch."
  exit 0
fi

LOCAL_SHA=$(git rev-parse "$LOCAL_REF")
REMOTE_SHA=$(git rev-parse "$REMOTE_REF")

echo "=== Checking local alpha vs origin/alpha ==="
echo "  local  alpha: ${LOCAL_SHA:0:8}"
echo "  remote alpha: ${REMOTE_SHA:0:8}"

if [[ "$LOCAL_SHA" == "$REMOTE_SHA" ]]; then
  echo ""
  echo "PASS: Local 'alpha' matches origin/alpha exactly."
  exit 0
fi

BEHIND=$(git rev-list --count "${LOCAL_REF}..${REMOTE_REF}" 2>/dev/null || echo "0")
AHEAD=$(git rev-list --count "${REMOTE_REF}..${LOCAL_REF}" 2>/dev/null || echo "0")

if [[ "$BEHIND" -gt 0 ]]; then
  echo ""
  echo "FAIL: Local 'alpha' is ${BEHIND} commit(s) behind origin/alpha."
  echo ""
  echo "  Commits on origin/alpha not yet in local alpha:"
  git log --oneline "${LOCAL_REF}..${REMOTE_REF}" | head -15
  echo ""
  echo "  Why this matters:"
  echo "    - merge-base calculations use LOCAL alpha — a stale local ref"
  echo "      makes all content checks diff against an outdated baseline."
  echo "    - New check scripts added to alpha after your branch was cut are"
  echo "      absent from your worktree; the backend suite reports them MISSING."
  echo ""
  echo "  Resolution:"
  echo "    git fetch origin alpha"
  echo "    git branch -f alpha origin/alpha   # fast-forward local ref"
  echo "    git rebase alpha                   # rebase your task branch"
  echo "    bash .hyperloop/checks/check-run-backend-suite.sh"
  echo ""
  exit 1
fi

# Local is strictly ahead — informational only.
echo ""
echo "PASS: Local 'alpha' is ${AHEAD} commit(s) AHEAD of origin/alpha."
echo "      (origin/alpha may not be fully fetched, or local alpha has unpushed work.)"
exit 0
