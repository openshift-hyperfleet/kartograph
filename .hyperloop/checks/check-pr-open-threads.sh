#!/usr/bin/env bash
# check-pr-open-threads.sh
#
# Verifies that all review threads on the task's pull request are resolved.
# Exits non-zero if any PENDING (unresolved) threads remain.
#
# WHY THIS EXISTS:
#   task-003 cycled through 8 consecutive "pr-feedback-addressed" check failures
#   because the implementer kept submitting without resolving every open review
#   thread. The orchestrator's `pr-feedback-addressed` check is a black box to
#   agents; this script makes the same gate mechanical and self-diagnosable.
#   Agents can run it themselves before reporting done and see exactly which
#   threads remain open.
#
# REQUIREMENTS:
#   - `gh` CLI must be authenticated.
#   - The current task state file must contain a `pr:` field with the PR URL,
#     OR a PR URL/number must be passed as the first argument.
#
# Usage:
#   bash .hyperloop/checks/check-pr-open-threads.sh [PR_URL_OR_NUMBER]
#
# Exit 0  — all review threads are resolved (or no review threads exist).
# Exit 1  — one or more threads are still PENDING/unresolved.

set -uo pipefail

# ── Resolve PR number ─────────────────────────────────────────────────────────

PR_ARG="${1:-}"
PR_NUMBER=""

if [[ -n "$PR_ARG" ]]; then
  # Accept full URL or bare number
  PR_NUMBER=$(echo "$PR_ARG" | grep -oE '[0-9]+$' || echo "")
fi

if [[ -z "$PR_NUMBER" ]]; then
  # Infer task ID from branch name, then read PR from task state file
  BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
  TASK_ID=$(echo "$BRANCH" | grep -oE 'task-[0-9]+' | head -1 || echo "")

  if [[ -n "$TASK_ID" ]]; then
    TASK_FILE=".hyperloop/state/tasks/${TASK_ID}.md"
    if [[ -f "$TASK_FILE" ]]; then
      PR_URL=$(awk '/^---/{found++; if(found==2) exit} found==1 && /^pr:/{print $2; exit}' "$TASK_FILE" \
               | tr -d '"' || echo "")
      PR_NUMBER=$(echo "$PR_URL" | grep -oE '[0-9]+$' || echo "")
    fi
  fi
fi

if [[ -z "$PR_NUMBER" ]]; then
  echo "SKIP: No PR number found (pass as argument or set pr: in task state file)."
  echo "      If this task has no PR yet, this check is not applicable."
  exit 0
fi

echo "=== Checking PR #${PR_NUMBER} for unresolved review threads ==="

# ── Query GitHub for review threads ──────────────────────────────────────────

if ! command -v gh &>/dev/null; then
  echo "WARN: gh CLI not found — cannot check PR threads. Install gh and authenticate."
  echo "      Skipping check (exit 0 to avoid false-blocking CI environments)."
  exit 0
fi

# gh pr view returns reviewThreads with isResolved boolean
THREAD_JSON=$(gh pr view "$PR_NUMBER" \
  --json reviewThreads \
  --jq '.reviewThreads[] | {isResolved: .isResolved, isOutdated: .isOutdated, body: (.comments[0].body // "" | .[0:120])}' \
  2>/dev/null || echo "")

if [[ -z "$THREAD_JSON" ]]; then
  echo "OK: No review threads found on PR #${PR_NUMBER}."
  exit 0
fi

PENDING=0
PENDING_DETAILS=""

while IFS= read -r line; do
  IS_RESOLVED=$(echo "$line" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['isResolved'])" 2>/dev/null || echo "false")
  IS_OUTDATED=$(echo "$line" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['isOutdated'])" 2>/dev/null || echo "false")
  BODY=$(echo "$line" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['body'])" 2>/dev/null || echo "")

  if [[ "$IS_RESOLVED" == "False" && "$IS_OUTDATED" == "False" ]]; then
    PENDING=1
    PENDING_DETAILS="${PENDING_DETAILS}  PENDING: ${BODY}...\n"
  fi
done < <(gh pr view "$PR_NUMBER" \
  --json reviewThreads \
  --jq '.reviewThreads[]' \
  2>/dev/null | python3 -c "
import sys, json
data = sys.stdin.read().strip()
# gh returns one JSON object per line or a single array
try:
    items = json.loads(data)
    if isinstance(items, list):
        for item in items:
            print(json.dumps(item))
    else:
        print(json.dumps(items))
except Exception:
    for line in data.split('\n'):
        line = line.strip()
        if line:
            print(line)
" 2>/dev/null || true)

echo ""
if [[ "$PENDING" -eq 1 ]]; then
  echo "FAIL: Unresolved review threads remain on PR #${PR_NUMBER}."
  echo ""
  echo "Unresolved threads:"
  printf "%b" "$PENDING_DETAILS"
  echo ""
  echo "Run: gh pr view ${PR_NUMBER} --comments"
  echo "to see full thread content."
  echo ""
  echo "Each unresolved thread must be addressed with a commit before submitting."
  exit 1
fi

echo "PASS: All review threads on PR #${PR_NUMBER} are resolved."
exit 0
