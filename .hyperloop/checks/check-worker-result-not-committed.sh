#!/usr/bin/env bash
# check-worker-result-not-committed.sh
#
# Fails if .hyperloop/worker-result.yaml is present in the commits added by
# this branch vs the base branch.
#
# WHY: .hyperloop/worker-result.yaml is orchestrator-managed metadata written
# by verifier and implementer workers to report their verdict. Like state files,
# it must NOT be committed to task branches. When a task implementation commit
# is cherry-picked from another branch (e.g. to fix a wrong Task-Ref trailer),
# this file travels inside the cherry-pick unless explicitly stripped. Once it
# lands on the branch, it causes check-no-state-file-commits.sh to miss it
# (that script only covers .hyperloop/state/) while still contaminating the
# commit history.
#
# ROOT CAUSE: task-035 Round 4 FAIL — when cherry-picking commit 0bb08b56,
# the worker did not strip .hyperloop/worker-result.yaml before amending, so
# the orchestrator's prior-round verdict file ended up committed on the task
# branch alongside the 34 state/intake files.
#
# FIX: After every `git cherry-pick <SHA>`, run:
#   git restore --staged --worktree -- '.hyperloop/worker-result.yaml'
# before any commit or amend. Then re-run this check to confirm exit 0.
#
# Usage:
#   bash .hyperloop/checks/check-worker-result-not-committed.sh [base_branch]
#
# Exit 0  — .hyperloop/worker-result.yaml not present in branch commits.
# Exit 1  — file is committed on this branch; must be stripped from history.

set -euo pipefail

# Normalize CWD to repo root so git pathspecs work correctly.
cd "$(git rev-parse --show-toplevel)"

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
  echo "WARNING: Could not detect base branch. Skipping worker-result commit check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping check."
  exit 0
fi

echo "=== Checking for .hyperloop/worker-result.yaml in commits (base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="

# Check if worker-result.yaml was touched (added, modified, deleted) on this branch.
result_file=$(git diff --name-only "$MERGE_BASE" HEAD -- '.hyperloop/worker-result.yaml' 2>/dev/null || true)

if [[ -z "$result_file" ]]; then
  echo "PASS: .hyperloop/worker-result.yaml is not committed on this branch."
  exit 0
fi

echo ""
echo "FAIL: .hyperloop/worker-result.yaml is present in branch commit history."
echo ""
echo "  This file is orchestrator-managed and must NOT be committed to task branches."
echo "  It most commonly appears when a cherry-pick carries it from the source commit"
echo "  without an explicit strip step."
echo ""
echo "  FIX — cherry-pick protocol (run after every git cherry-pick <SHA>):"
echo ""
echo "    git restore --staged --worktree -- '.hyperloop/worker-result.yaml'"
echo "    git commit --amend  # remove the file from the cherry-picked commit"
echo ""
echo "  If the file was committed in multiple commits, cherry-pick delivery commits"
echo "  onto a fresh branch from $BASE_BRANCH and apply the strip step after each pick."
echo ""
echo "  After fixing, re-run this check and confirm PASS before proceeding:"
echo "    bash .hyperloop/checks/check-worker-result-not-committed.sh"
exit 1
