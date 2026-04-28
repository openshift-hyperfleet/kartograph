#!/usr/bin/env bash
# check-process-agent-not-on-task-branch.sh
#
# Fails if the current branch matches the task-branch pattern hyperloop/task-NNN.
#
# PURPOSE: Pre-commit gate for the process-improvement agent. Process-improvement
# commits must NEVER land on hyperloop/task-NNN branches — they must go to a
# dedicated process-improvement branch (e.g. branched from alpha).
#
# WHY: When process-improvement commits land on a task branch, they carry
# "Task-Ref: process-improvement" trailers that cause check-no-foreign-task-commits.sh
# to fail for the task. Observed in task-019: two process-improvement agent commits
# on the task branch caused a verifier FAIL that required orchestrator intervention.
#
# CORRECT FIX (if you find yourself on a task branch):
#   1. Switch to a process-improvement branch:
#        git checkout -b process-improvement/$(date +%Y%m%d) origin/alpha
#   2. Cherry-pick your uncommitted work, or push to the correct branch.
#
# Usage:
#   bash .hyperloop/checks/check-process-agent-not-on-task-branch.sh
#
# Exit 0 — current branch is not a task branch; safe to commit.
# Exit 1 — current branch is a task branch; commit is blocked.

set -uo pipefail

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)

if [[ -z "$BRANCH" || "$BRANCH" == "HEAD" ]]; then
  echo "WARNING: Could not determine current branch (detached HEAD) — skipping check."
  exit 0
fi

if echo "$BRANCH" | grep -qE '^hyperloop/task-[0-9]+'; then
  echo ""
  echo "FAIL: Current branch is a task branch: $BRANCH"
  echo ""
  echo "Process-improvement commits must NEVER land on hyperloop/task-NNN branches."
  echo "They introduce foreign Task-Ref trailers that cause check-no-foreign-task-commits.sh"
  echo "to fail for the task, blocking its merge and requiring orchestrator intervention."
  echo ""
  echo "── CORRECT FIX ────────────────────────────────────────────────────────────"
  echo ""
  echo "  1. Switch to a dedicated process-improvement branch:"
  echo "     git checkout -b process-improvement/$(date +%Y%m%d) origin/alpha"
  echo ""
  echo "  2. If you have already committed, cherry-pick to the new branch and drop"
  echo "     the commits from the task branch via interactive rebase."
  echo ""
  echo "  3. Confirm you are on the new branch:"
  echo "     bash .hyperloop/checks/check-process-agent-not-on-task-branch.sh"
  echo ""
  exit 1
fi

echo "PASS: Current branch ($BRANCH) is not a hyperloop/task-NNN branch — safe to commit."
exit 0
