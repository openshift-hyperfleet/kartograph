#!/usr/bin/env bash
# check-alpha-local-vs-remote.sh
#
# Verifies that local 'alpha' and 'origin/alpha' point to the same commit,
# or that local alpha is BEHIND origin/alpha (safe: worker just needs a pull).
#
# WHY: When local 'alpha' is AHEAD of 'origin/alpha' — meaning alpha has commits
# that have not been pushed — a worker who rebases against 'origin/alpha' instead
# of local 'alpha' creates a branch whose merge-base with local alpha predates
# those unpushed commits. Those commits then appear as "branch commits" in
# `git log alpha..HEAD`, contaminating the branch with foreign task work.
#
# This is the pattern observed in task-003: commit 1b0f2478 (Task-Ref: task-032)
# was present on local alpha but not yet on origin/alpha. The task-003 branch
# was rebased against origin/alpha, so its merge-base with local alpha was BEFORE
# task-032, making that commit appear as a task-003 branch commit. The PR would
# have merged 3,791 lines of unreviewed task-032 work under a task-003 PR.
#
# THE SAFE REBASE PROTOCOL:
#   1. git fetch origin
#   2. git checkout alpha && git merge --ff-only origin/alpha
#   3. git checkout <task-branch> && git rebase alpha    # local ref, not origin/alpha
#
# Exit 0 — local alpha and origin/alpha are in sync (or origin is ahead: safe to pull).
# Exit 1 — local alpha is AHEAD of origin/alpha; rebasing against origin/alpha will
#           produce contaminated branches. Push or coordinate before worker rebases.

set -euo pipefail

BASE_BRANCH="alpha"

# Skip gracefully if alpha does not exist locally
if ! git rev-parse --verify "$BASE_BRANCH" >/dev/null 2>&1; then
  echo "INFO: Local branch '$BASE_BRANCH' not found — skipping alpha sync check."
  exit 0
fi

# Skip gracefully if origin/alpha does not exist
if ! git rev-parse --verify "origin/$BASE_BRANCH" >/dev/null 2>&1; then
  echo "INFO: 'origin/$BASE_BRANCH' not found — skipping alpha sync check."
  exit 0
fi

LOCAL_SHA=$(git rev-parse "$BASE_BRANCH")
REMOTE_SHA=$(git rev-parse "origin/$BASE_BRANCH")

echo "=== Checking local vs remote alpha alignment ==="
echo "  local  alpha: ${LOCAL_SHA}"
echo "  origin/alpha: ${REMOTE_SHA}"
echo ""

if [[ "$LOCAL_SHA" == "$REMOTE_SHA" ]]; then
  echo "PASS: local alpha and origin/alpha are in sync."
  exit 0
fi

LOCAL_AHEAD=$(git rev-list --count "origin/${BASE_BRANCH}..${BASE_BRANCH}" 2>/dev/null || echo "0")
REMOTE_AHEAD=$(git rev-list --count "${BASE_BRANCH}..origin/${BASE_BRANCH}" 2>/dev/null || echo "0")

if [[ "$LOCAL_AHEAD" -gt 0 ]]; then
  echo "FAIL: local 'alpha' is ${LOCAL_AHEAD} commit(s) AHEAD of 'origin/alpha'."
  echo ""
  echo "Commits on local alpha not yet pushed to origin:"
  git log --oneline "origin/${BASE_BRANCH}..${BASE_BRANCH}" | head -20
  echo ""
  echo "WHY THIS IS DANGEROUS:"
  echo "  Any worker who runs 'git rebase origin/alpha' (instead of 'git rebase alpha')"
  echo "  will base their branch on the OLD origin tip. The ${LOCAL_AHEAD} unpushed"
  echo "  commit(s) above will then appear in 'git log alpha..HEAD' as branch commits,"
  echo "  contaminating the task branch with foreign task work."
  echo ""
  echo "  Example (task-003): task-032 work was on local alpha but not origin/alpha."
  echo "  task-003 was rebased against origin/alpha → task-032 commit appeared as a"
  echo "  task-003 branch commit → PR would have merged 3,791 unreviewed lines."
  echo ""
  echo "FIX (repo owner):"
  echo "  Push local alpha to origin so both refs are aligned:"
  echo "    git push origin alpha"
  echo ""
  echo "FIX (worker, if you cannot push alpha):"
  echo "  Always rebase against local alpha (not origin/alpha):"
  echo "    git fetch origin"
  echo "    git checkout alpha && git merge --ff-only origin/alpha"
  echo "    git checkout <task-branch> && git rebase alpha"
  exit 1
fi

if [[ "$REMOTE_AHEAD" -gt 0 ]]; then
  echo "WARN: 'origin/alpha' is ${REMOTE_AHEAD} commit(s) ahead of local alpha."
  echo ""
  echo "Commits on origin/alpha not yet fetched locally:"
  git log --oneline "${BASE_BRANCH}..origin/${BASE_BRANCH}" | head -20
  echo ""
  echo "This means your local alpha is stale. Before rebasing your task branch:"
  echo "  git checkout alpha && git merge --ff-only origin/alpha"
  echo "  git checkout <task-branch> && git rebase alpha"
  echo ""
  echo "A stale local alpha causes check-branch-rebased-on-alpha.sh to report the"
  echo "branch as further behind than it actually is."
  exit 1
fi
