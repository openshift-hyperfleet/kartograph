#!/usr/bin/env bash
# check-task-owns-branch-commits.sh
#
# Verifies the task branch contains at least one commit carrying THIS task's
# Task-Ref trailer, compared against origin/alpha (the authoritative upstream).
#
# WHY THIS CHECK:
#   task-134: The implementer's branch HEAD equalled origin/alpha HEAD — no
#   task-134 commits existed. Local 'alpha' was 2 commits behind origin/alpha,
#   causing every local-alpha-based check to produce a false-positive (it "saw"
#   2 upstream commits as task commits). origin/alpha-based checks (e.g.
#   check-no-foreign-task-commits.sh) found 0 commits between merge-base and
#   HEAD and returned PASS — correct for that check, but leaving the
#   zero-implementation case undetected. The backend suite reported ALL PASS
#   despite the task having zero delivered work.
#
#   This script closes the gap: it uses origin/alpha as the comparison
#   baseline and requires at least one commit with the EXACT Task-Ref matching
#   the current task. A branch that points to origin/alpha HEAD will have 0
#   such commits and will FAIL immediately.
#
# FAILURE MODES DETECTED:
#   1. Branch HEAD == origin/alpha HEAD (implementer never started work).
#   2. Branch contains only commits from other tasks (wrong branch used).
#   3. Commits exist above origin/alpha but none carry this task's Task-Ref
#      (e.g. commits were made without the Task-Ref trailer).
#
# Usage:
#   bash .hyperloop/checks/check-task-owns-branch-commits.sh
#
# Exit 0 — at least one commit with the correct Task-Ref exists above origin/alpha.
# Exit 1 — zero task-specific commits exist above origin/alpha.

set -uo pipefail

cd "$(git rev-parse --show-toplevel)"

# ── Resolve remote alpha ref ─────────────────────────────────────────────────
REMOTE_REF="origin/alpha"
if ! git show-ref --verify --quiet "refs/remotes/$REMOTE_REF" 2>/dev/null; then
  echo "INFO: '$REMOTE_REF' not found — skipping task-ownership check."
  exit 0
fi

REMOTE_SHA=$(git rev-parse "$REMOTE_REF" 2>/dev/null || true)
if [[ -z "$REMOTE_SHA" ]]; then
  echo "WARNING: Could not resolve '$REMOTE_REF' — skipping check."
  exit 0
fi

# ── Determine the current task from branch name ──────────────────────────────
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)
if [[ -z "$BRANCH" || "$BRANCH" == "HEAD" ]]; then
  echo "WARNING: Detached HEAD — cannot determine task; skipping check."
  exit 0
fi

EXPECTED_TASK=$(echo "$BRANCH" | grep -oE 'task-[0-9]+' | head -1 || true)
if [[ -z "$EXPECTED_TASK" ]]; then
  echo "INFO: Branch '$BRANCH' has no task-NNN pattern — skipping task-ownership check."
  exit 0
fi

# ── Compute merge-base with origin/alpha ─────────────────────────────────────
MERGE_BASE=$(git merge-base HEAD "$REMOTE_REF" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with '$REMOTE_REF' — skipping check."
  exit 0
fi

echo "=== Verifying branch owns commits for $EXPECTED_TASK (vs $REMOTE_REF @ ${REMOTE_SHA:0:8}) ==="
echo ""

COMMIT_COUNT=$(git rev-list --count "${MERGE_BASE}..HEAD" 2>/dev/null || echo "0")
echo "Commits above origin/alpha: $COMMIT_COUNT"

if [[ "$COMMIT_COUNT" -eq 0 ]]; then
  echo ""
  echo "FAIL: Branch has ZERO commits above origin/alpha."
  echo ""
  echo "  Branch HEAD:   $(git rev-parse --short HEAD 2>/dev/null)"
  echo "  origin/alpha:  ${REMOTE_SHA:0:8}"
  echo ""
  echo "The task has not been implemented. The branch HEAD equals (or is behind)"
  echo "origin/alpha — no task-specific work has been committed."
  echo ""
  echo "WHY LOCAL CHECKS MAY SHOW FALSE PASSes:"
  echo "  If local 'alpha' is stale (behind origin/alpha), local-alpha-based"
  echo "  checks (check-branch-has-commits.sh, check-implementation-commits-exist.sh)"
  echo "  count upstream commits as 'task commits' and report PASS. This gives a"
  echo "  misleading all-green suite even with zero real implementation work."
  echo ""
  echo "RESOLUTION:"
  echo "  Start the task from origin/alpha and commit at least one change:"
  echo "    git checkout -b hyperloop/$EXPECTED_TASK origin/alpha"
  echo "    # ... implement the task ..."
  echo "    git commit -m 'feat(...): ...' -m '' -m 'Task-Ref: $EXPECTED_TASK'"
  exit 1
fi

# ── Verify at least one commit carries the correct Task-Ref ──────────────────
OWNED_COMMITS=""
while IFS= read -r sha; do
  [[ -z "$sha" ]] && continue
  task_ref=$(git log -1 --format='%(trailers:key=Task-Ref,valueonly)' "$sha" 2>/dev/null \
    | tr -d '[:space:]' || true)
  if [[ "$task_ref" == "$EXPECTED_TASK" ]]; then
    OWNED_COMMITS="${OWNED_COMMITS}${sha}"$'\n'
  fi
done < <(git rev-list --first-parent "${MERGE_BASE}..HEAD" 2>/dev/null || true)

OWNED_COUNT=0
if [[ -n "$OWNED_COMMITS" ]]; then
  OWNED_COUNT=$(echo "$OWNED_COMMITS" | grep -c '[0-9a-f]' || echo "0")
fi

echo ""
if [[ "$OWNED_COUNT" -gt 0 ]]; then
  echo "Commits with Task-Ref: $EXPECTED_TASK:"
  while IFS= read -r sha; do
    [[ -z "$sha" ]] && continue
    echo "  $(git log -1 --format='%h %s' "$sha" 2>/dev/null)"
  done <<< "$OWNED_COMMITS"
  echo ""
  echo "PASS: Branch owns $OWNED_COUNT commit(s) for $EXPECTED_TASK above origin/alpha."
  exit 0
else
  echo "All $COMMIT_COUNT commits above origin/alpha:"
  git log --oneline "${MERGE_BASE}..HEAD" 2>/dev/null | sed 's/^/  /' || true
  echo ""
  echo "FAIL: None of the $COMMIT_COUNT commits above origin/alpha carry Task-Ref: $EXPECTED_TASK."
  echo ""
  echo "The branch contains commits from other tasks or commits without Task-Ref"
  echo "trailers. No $EXPECTED_TASK-specific work has been committed above origin/alpha."
  echo ""
  echo "Root-cause pattern (observed in task-134): local 'alpha' was stale, causing"
  echo "upstream commits already on origin/alpha to appear as 'task commits' in"
  echo "local-alpha-based checks. All other checks produced false PASSes."
  echo ""
  echo "Fix: Create a clean branch from origin/alpha and implement the task:"
  echo "  git checkout -b hyperloop/$EXPECTED_TASK-clean origin/alpha"
  exit 1
fi
