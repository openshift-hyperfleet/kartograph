#!/usr/bin/env bash
# check-process-improvement-commit-is-clean.sh
#
# Pre-commit gate for the process-improvement agent. Verifies four
# invariants before a process-improvement commit may proceed:
#
#   1. Branch is NOT a task branch (hyperloop/task-NNN pattern).
#   2. All staged files are within .hyperloop/ (no source code changes).
#   3. No overlay file lines are being removed in staged changes.
#   4. Commit subject uses an allowed conventional-commit type prefix.
#      (only when .git/COMMIT_EDITMSG is available — i.e. git commit -m)
#
# WHY THIS CHECK:
#   task-019 (round 7): Two process-improvement commits landed on the task
#   branch, each with Task-Ref: process-improvement. These commits:
#     (a) Added new check scripts under .hyperloop/checks/, and
#     (b) Replaced a line in verifier-overlay.yaml instead of appending to it.
#   The result was check-no-foreign-task-commits.sh FAIL AND a cascade
#   check-process-overlay-content-intact.sh FAIL on the task branch.
#
#   task-145 (round 6): Commit 457680c9e used subject
#   "fix(query): correct error_type" with Task-Ref: process-improvement and
#   modified src/api/tests/unit/query/test_application_services.py. The
#   pre-commit hook was not active so invariant [2] was bypassed. Invariant
#   [4] catches the code-domain subject type even when invariant [2] is
#   checked manually, providing defense-in-depth.
#
#   check-process-agent-not-on-task-branch.sh guards condition (1) alone.
#   This script combines all four invariants into a single pre-commit gate
#   so the process-improvement agent cannot forget to check any of them.
#
# Usage:
#   bash .hyperloop/checks/check-process-improvement-commit-is-clean.sh
#   (also invoked as a commit-msg hook: called with $1 = message file path)
#
# Exit 0  — all invariants hold; safe to commit.
# Exit 1  — one or more invariants violated; commit is blocked.

set -uo pipefail

cd "$(git rev-parse --show-toplevel)"

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

# ── 4. Commit subject must use an allowed conventional-commit type ─────────────
# This check fires when (a) invoked as a commit-msg hook (MSG_FILE=$1),
# (b) .git/COMMIT_EDITMSG exists from a prior `git commit -m "..."` invocation,
# or (c) .git/MERGE_MSG exists. Allowed prefixes are the process-safe types.
# Code-domain types (fix, feat, refactor without a process scope) are blocked.
#
# Pattern that caused task-145: "fix(query): correct error_type" — a fix()
# with a non-process scope is always wrong for a process-improvement commit.

ALLOWED_PREFIXES_RE='^(chore\((process|checks)\)|docs\(process\)|refactor\(process\)):'

MSG_FILE="${1:-}"
COMMIT_MSG=""

if [[ -n "$MSG_FILE" && -f "$MSG_FILE" ]]; then
  COMMIT_MSG=$(head -1 "$MSG_FILE" 2>/dev/null || true)
elif [[ -f "$(git rev-parse --git-dir 2>/dev/null)/COMMIT_EDITMSG" ]]; then
  COMMIT_MSG=$(head -1 "$(git rev-parse --git-dir)/COMMIT_EDITMSG" 2>/dev/null || true)
fi

if [[ -n "$COMMIT_MSG" ]]; then
  # Strip leading/trailing whitespace.
  COMMIT_MSG="${COMMIT_MSG#"${COMMIT_MSG%%[![:space:]]*}"}"
  COMMIT_MSG="${COMMIT_MSG%"${COMMIT_MSG##*[![:space:]]}"}"

  if ! echo "$COMMIT_MSG" | grep -qE "$ALLOWED_PREFIXES_RE"; then
    echo ""
    echo "FAIL [4/4]: Commit subject uses a disallowed conventional-commit type:"
    echo "  Subject: $COMMIT_MSG"
    echo ""
    echo "  Process-improvement commits MUST begin with one of:"
    echo "    chore(process):    chore(checks):"
    echo "    docs(process):     refactor(process):"
    echo ""
    echo "  Code-domain types (fix, feat, refactor without 'process' scope) are"
    echo "  PROHIBITED. A 'fix(<non-process>):' subject is the diagnostic fingerprint"
    echo "  of source-code contamination (task-145 root cause: fix(query): ...)."
    echo ""
    echo "  If you are documenting a bug for the orchestrator, use:"
    echo "    chore(process): document bug in <module> for orchestrator triage"
    echo ""
    FAIL=1
  else
    echo "PASS [4/4]: Commit subject uses an allowed process-improvement type."
  fi
else
  echo "SKIP [4/4]: No commit message available at pre-commit time (use -m flag or"
  echo "            the commit-msg hook will run this check when the message is set)."
fi

echo ""
if [[ $FAIL -ne 0 ]]; then
  echo "RESULT: FAIL — fix all violations above before committing."
  exit 1
fi

echo "RESULT: PASS — process-improvement commit is clean."
exit 0
