#!/usr/bin/env bash
# check-worker-result-not-committed.sh
#
# Verifies that .hyperloop/worker-result.yaml is NOT present in the commit
# history of this branch (relative to the alpha base). This guards against
# branch contamination where a prior-round worker result is baked into the
# branch history and would be replayed on a subsequent round.
#
# WHY THIS CHECK:
#   The worker-result.yaml file is written and committed by the worker as the
#   FINAL step of their work — after the backend suite passes. If the file
#   already appears in the branch history (e.g., because an orchestrator
#   intake run committed it, or a previous-round worker left it behind),
#   the branch is considered contaminated and must be rebuilt from alpha.
#
#   This check runs BEFORE the worker commits their result so it detects
#   pre-existing contamination early.
#
# SCOPE:
#   Only commits between merge-base(HEAD, alpha) and HEAD are examined.
#   The check does NOT inspect the working tree or the index — only committed
#   history on this branch.
#
# EXIT CODES:
#   0 — worker-result.yaml is not present in branch commit history
#   1 — worker-result.yaml was committed in this branch (contamination)
#
# Usage:
#   ./check-worker-result-not-committed.sh [base_branch]

set -euo pipefail

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
  echo "WARNING: Could not detect base branch. Skipping worker-result check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping check."
  exit 0
fi

echo "=== Checking worker-result.yaml not committed on branch (base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="

# Collect commits that touched .hyperloop/worker-result.yaml on this branch.
contaminated_commits=$(git log --format="%H %s" "$MERGE_BASE"..HEAD \
  -- .hyperloop/worker-result.yaml 2>/dev/null || true)

if [[ -z "$contaminated_commits" ]]; then
  echo "PASS: .hyperloop/worker-result.yaml is not committed on this branch."
  exit 0
fi

echo "FAIL: .hyperloop/worker-result.yaml was committed in this branch's history."
echo ""
echo "Contaminated commits:"
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  echo "  $line"
done <<< "$contaminated_commits"
echo ""
echo "The worker-result.yaml file must only be committed as the final step"
echo "of the current worker run (after the backend suite passes). Pre-existing"
echo "result commits indicate branch contamination from a prior round."
echo ""
echo "Fix: rebuild the branch by cherry-picking only task-specific commits"
echo "onto a fresh branch from current alpha."
exit 1
