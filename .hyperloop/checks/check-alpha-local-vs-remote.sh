#!/usr/bin/env bash
# check-alpha-local-vs-remote.sh
#
# Warns when local 'alpha' and 'origin/alpha' have diverged significantly.
#
# WHY: The orchestrator maintains local 'alpha' independently and may advance
# it dozens of commits without pushing to 'origin/alpha'. When an implementer
# runs 'git rebase origin/alpha' instead of 'git rebase alpha', they rebase
# against the stale remote ref. check-branch-rebased-on-alpha.sh compares
# against LOCAL 'alpha' and then fails even though the implementer believes
# the branch is current.
#
# This check detects the divergence so implementers discover it BEFORE
# attempting a rebase — not after the rebase fails the staleness check.
#
# Exit 0 — local alpha and origin/alpha agree (or origin/alpha doesn't exist).
# Exit 1 — local alpha is ahead of origin/alpha by more than 5 commits
#           (implementer must use 'git rebase alpha', not 'git rebase origin/alpha').

set -euo pipefail

LOCAL_REF="refs/heads/alpha"
REMOTE_REF="refs/remotes/origin/alpha"

if ! git show-ref --verify --quiet "$LOCAL_REF" 2>/dev/null; then
  echo "INFO: Local 'alpha' branch not found — skipping alpha sync check."
  exit 0
fi

if ! git show-ref --verify --quiet "$REMOTE_REF" 2>/dev/null; then
  echo "INFO: 'origin/alpha' not found — skipping alpha sync check."
  exit 0
fi

LOCAL_SHA=$(git rev-parse alpha)
REMOTE_SHA=$(git rev-parse origin/alpha)

if [[ "$LOCAL_SHA" == "$REMOTE_SHA" ]]; then
  echo "OK: Local 'alpha' and 'origin/alpha' point to the same commit (${LOCAL_SHA:0:8})."
  exit 0
fi

# How far ahead is local alpha vs origin/alpha?
AHEAD=$(git rev-list --count origin/alpha..alpha 2>/dev/null || echo "0")
BEHIND=$(git rev-list --count alpha..origin/alpha 2>/dev/null || echo "0")

if [[ "$AHEAD" -gt 5 ]]; then
  # Before failing, check whether the task branch is ALREADY rebased on local alpha
  # (within the same tolerance window as check-branch-rebased-on-alpha.sh, i.e. ≤5
  # commits behind).
  #
  # WHY: check-alpha-local-vs-remote.sh is a preemptive warning that fires when local
  # alpha is significantly ahead of origin/alpha, so implementers know to use
  # 'git rebase alpha' instead of 'git rebase origin/alpha'. But once the task branch
  # IS correctly rebased on local alpha, the local/remote divergence is harmless —
  # origin/alpha being stale is normal orchestrator behavior and does not affect the
  # branch. Continuing to exit 1 in this case causes a false positive that blocks
  # every verification round even when the implementer did everything correctly.
  #
  # FIX: Compare the number of commits the task branch is behind LOCAL alpha (not
  # origin/alpha). If the branch is within 5 commits of local alpha (the same
  # threshold used by check-branch-rebased-on-alpha.sh), the branch is current
  # enough and the local/remote divergence is irrelevant.
  BRANCH_MERGE_BASE=$(git merge-base HEAD alpha 2>/dev/null || echo "")
  BRANCH_BEHIND_ALPHA=9999
  if [[ -n "$BRANCH_MERGE_BASE" ]]; then
    BRANCH_BEHIND_ALPHA=$(git rev-list --count "${BRANCH_MERGE_BASE}..${LOCAL_REF#refs/heads/}" 2>/dev/null || echo "9999")
  fi
  if [[ "$BRANCH_BEHIND_ALPHA" -le 5 ]]; then
    echo "INFO: Local 'alpha' is ${AHEAD} commit(s) ahead of 'origin/alpha', but the"
    echo "      task branch is within ${BRANCH_BEHIND_ALPHA} commit(s) of local alpha"
    echo "      (≤5 threshold — same as check-branch-rebased-on-alpha.sh)."
    echo "      The local/remote divergence is expected orchestrator behavior and is"
    echo "      harmless on this branch."
    echo ""
    echo "      Always use 'git rebase alpha' (not 'git rebase origin/alpha') for any"
    echo "      future rebases on this or other task branches."
    exit 0
  fi

  # Branch is NOT yet on local alpha — the divergence matters.
  echo "ALPHA DIVERGENCE: Local 'alpha' is ${AHEAD} commit(s) ahead of 'origin/alpha'."
  echo ""
  echo "  Local  alpha: ${LOCAL_SHA}"
  echo "  Remote alpha: ${REMOTE_SHA}"
  echo ""
  echo "The orchestrator advances local 'alpha' independently. check-branch-rebased-on-alpha.sh"
  echo "compares against LOCAL 'alpha' — NOT 'origin/alpha'."
  echo ""
  echo "Running 'git rebase origin/alpha' will leave your branch ${AHEAD} commit(s) stale"
  echo "against the staleness check. You MUST run:"
  echo ""
  echo "  git rebase alpha"
  echo ""
  echo "Never use 'git rebase origin/alpha' as a substitute."
  exit 1
fi

if [[ "$BEHIND" -gt 0 ]]; then
  echo "INFO: Local 'alpha' is ${BEHIND} commit(s) behind 'origin/alpha'."
  echo "Consider running 'git fetch origin alpha:alpha' before rebasing."
fi

echo "OK: Local 'alpha' and 'origin/alpha' are within acceptable range (ahead=${AHEAD}, behind=${BEHIND})."
exit 0
