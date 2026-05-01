#!/usr/bin/env bash
# check-process-improvement-commit-is-clean.sh
#
# Pre-commit gate for the process-improvement agent. Verifies three
# invariants before a process-improvement commit may proceed:
#
#   1. Branch is NOT a task branch (hyperloop/task-NNN pattern).
#   2. All staged files are within .hyperloop/ (no source code changes).
#   3. No overlay file lines are being removed in staged changes.
#
# WHY THIS CHECK:
#   task-019 (round 7): Two process-improvement commits landed on the task
#   branch, each with Task-Ref: process-improvement. These commits:
#     (a) Added new check scripts under .hyperloop/checks/, and
#     (b) Replaced a line in verifier-overlay.yaml instead of appending to it.
#   The result was check-no-foreign-task-commits.sh FAIL AND a cascade
#   check-process-overlay-content-intact.sh FAIL on the task branch.
#
#   check-process-agent-not-on-task-branch.sh guards condition (1) alone.
#   This script combines all three invariants into a single pre-commit gate
#   so the process-improvement agent cannot forget to check any of them.
#
# Usage:
#   bash .hyperloop/checks/check-process-improvement-commit-is-clean.sh
#
# Exit 0  — all three invariants hold; safe to commit.
# Exit 1  — one or more invariants violated; commit is blocked.

set -uo pipefail

cd "$(git rev-parse --show-toplevel)"

# ── Verification-mode early exit ───────────────────────────────────────────────
# When no files are staged, we are in verification context (not pre-commit).
# All three invariants (branch, staged files, overlay removals) require a
# pending commit to be meaningful. Exit 0 immediately so this script does not
# false-positive when the orchestrator runs it during merge verification on a
# clean task branch.
staged_files=$(git diff --cached --name-only 2>/dev/null || true)
if [[ -z "$staged_files" ]]; then
  echo "PASS: No staged files — verification mode; pre-commit invariants do not apply."
  exit 0
fi

FAIL=0

# ── 1. Branch must NOT be a task branch ───────────────────────────────────────
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)

if [[ -z "$BRANCH" || "$BRANCH" == "HEAD" ]]; then
  echo "WARNING: Detached HEAD — cannot verify branch name."
  echo "         Run: git checkout -b process-improvement/$(date +%Y%m%d-%H%M%S) origin/alpha"
  FAIL=1
elif echo "$BRANCH" | grep -qE '^hyperloop/task-[0-9]+'; then
  echo ""
  echo "FAIL [1/3]: Current branch is a task branch: $BRANCH"
  echo ""
  echo "  Process-improvement commits must NEVER land on hyperloop/task-NNN branches."
  echo "  They carry Task-Ref: process-improvement trailers that cause"
  echo "  check-no-foreign-task-commits.sh to FAIL on the task, requiring"
  echo "  orchestrator-level branch reconstruction to clean up."
  echo ""
  echo "  Fix: git checkout -b process-improvement/$(date +%Y%m%d-%H%M%S) origin/alpha"
  echo "       Then cherry-pick or redo your changes on the new branch."
  echo ""
  FAIL=1
else
  echo "PASS [1/3]: Branch '$BRANCH' is not a task branch."
fi

# ── 2. All staged files must be within .hyperloop/ ────────────────────────────
staged_outside=$(git diff --cached --name-only 2>/dev/null \
  | grep -v '^\.hyperloop/' || true)

if [[ -n "$staged_outside" ]]; then
  echo ""
  echo "FAIL [2/3]: Staged files outside .hyperloop/ detected:"
  echo "$staged_outside" | sed 's/^/  /'
  echo ""
  echo "  Process-improvement commits must only touch .hyperloop/ files"
  echo "  (check scripts, overlay YAML, kustomization.yaml)."
  echo "  Source code changes belong to the task implementer, not the"
  echo "  process-improvement agent."
  echo ""
  FAIL=1
else
  echo "PASS [2/3]: All staged files are within .hyperloop/."
fi

# ── 3. No overlay lines may be removed in staged changes ──────────────────────
OVERLAY_DIR=".hyperloop/agents/process"
overlay_removals=$(git diff --cached -- "${OVERLAY_DIR}/" 2>/dev/null \
  | grep '^-' \
  | grep -v '^---' || true)

if [[ -n "$overlay_removals" ]]; then
  echo ""
  echo "FAIL [3/3]: Lines are being REMOVED from overlay files:"
  echo "$overlay_removals" | head -20 | sed 's/^/  /'
  echo ""
  echo "  Overlay files may only have lines APPENDED (net lines ≥ 0)."
  echo "  Removing a rule silently disables behavioral enforcement for all"
  echo "  subsequent tasks. check-process-overlay-content-intact.sh will"
  echo "  catch this at verify time — catching it here is cheaper."
  echo ""
  echo "  To update a rule: ADD the revised text as a NEW bullet below the"
  echo "  original. Never delete or in-place edit existing bullets."
  echo ""
  FAIL=1
else
  echo "PASS [3/3]: No overlay lines removed in staged changes."
fi

echo ""
if [[ $FAIL -ne 0 ]]; then
  echo "RESULT: FAIL — fix all violations above before committing."
  exit 1
fi

echo "RESULT: PASS — process-improvement commit is clean."
exit 0
