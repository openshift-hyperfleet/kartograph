#!/usr/bin/env bash
# check-implementation-commits-exist.sh
#
# Verifies that the current branch has at least one "implementation commit" —
# a commit whose subject line begins with feat:, fix:, or test: — ahead of
# the base branch (alpha / main / master).
#
# WHY THIS EXISTS:
#   The "Agent future missing or failed" orchestrator error can leave a task
#   branch in a deceptive state: the branch EXISTS (visible via git ls-remote)
#   and has COMMITS (so check-branch-has-commits.sh passes), but every commit
#   is a process or chore commit written by the process-improvement agent.
#   This makes the branch look like partial implementation work when it is
#   actually zero implementation.
#
#   By distinguishing process commits (chore:, feat(tasks):, chore(intake):,
#   chore(process):) from real implementation commits (feat:, fix:, test:),
#   the verifier can quickly detect that the implementer never started — and
#   combine this signal with check-deps-satisfied.sh to issue a BLOCKED verdict
#   rather than FAIL.
#
# Usage:
#   bash .hyperloop/checks/check-implementation-commits-exist.sh [base_branch]
#
# Exit 0  — at least one feat:/fix:/test: commit exists ahead of base.
# Exit 1  — no implementation commits found (process-only or empty branch).

set -uo pipefail

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
  echo "WARNING: Could not detect base branch — skipping implementation-commit check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH — skipping check."
  exit 0
fi

echo "=== Checking for implementation commits ahead of $BASE_BRANCH (merge-base: ${MERGE_BASE:0:8}) ==="
echo ""

ALL_COMMITS=$(git log --oneline "$MERGE_BASE..HEAD" 2>/dev/null || true)
TOTAL=$(git rev-list --count "$MERGE_BASE..HEAD" 2>/dev/null || echo 0)

echo "Total commits ahead of $BASE_BRANCH: $TOTAL"
if [[ "$TOTAL" -gt 0 ]]; then
  echo "$ALL_COMMITS"
fi
echo ""

# Implementation commit = subject starts with feat:, fix:, or test:
# (covers both bare and scoped forms: feat(scope):, fix(scope):, test(scope):)
IMPL_COMMITS=$(git log --oneline "$MERGE_BASE..HEAD" 2>/dev/null \
  | grep -E '^[0-9a-f]+ (feat|fix|test)(\([^)]+\))?:' || true)

IMPL_COUNT=0
if [[ -n "$IMPL_COMMITS" ]]; then
  IMPL_COUNT=$(echo "$IMPL_COMMITS" | wc -l | tr -d ' ')
fi

if [[ -n "$IMPL_COMMITS" ]]; then
  echo "Implementation commits found:"
  echo "$IMPL_COMMITS"
  echo ""
  echo "PASS: Branch has $IMPL_COUNT implementation commit(s) — real work was performed."
  exit 0
else
  echo "Process/chore commits on this branch:"
  if [[ -n "$ALL_COMMITS" ]]; then
    echo "$ALL_COMMITS"
  else
    echo "(none)"
  fi
  echo ""
  echo "FAIL: No implementation commits (feat:, fix:, test:) found ahead of $BASE_BRANCH."
  echo ""
  echo "This branch contains only process or chore commits. This is the signature of:"
  echo "  - An implementer that crashed before writing any task code, OR"
  echo "  - A process-improvement agent that used a task branch name by mistake."
  echo ""
  echo "Recommended action for verifiers:"
  echo "  1. Run check-deps-satisfied.sh <task-NNN>."
  echo "  2. If deps are unsatisfied → issue BLOCKED verdict immediately."
  echo "  3. If deps ARE satisfied → the implementer crashed for another reason;"
  echo "     issue FAIL and recommend re-assignment."
  exit 1
fi
