#!/usr/bin/env bash
# check-deps-satisfied.sh
#
# Reads the task state file for the current task branch and verifies that
# every task listed in `deps:` has `status: done`.
#
# SECONDARY CHECK (stale-state detection):
#   If a dep's state file says anything other than "done", this script also
#   checks whether the dep's branch (origin/hyperloop/<dep>) is already an
#   ancestor of alpha — i.e., its PR was merged into alpha even though the
#   orchestrator hasn't updated the state file yet.  In that case the check
#   emits a WARN line and exits 0 (satisfied), allowing implementation to
#   proceed.  It does NOT exit 0 silently: the WARN line is captured by
#   implementers and verifiers to flag the stale state to the orchestrator.
#
# WHY THIS EXISTS:
#   "Agent future missing or failed" with branch: null is the signature of an
#   agent that crashed during initialization — often because it attempted to
#   implement a task whose dependencies were not yet satisfied, causing it to
#   encounter missing interfaces, APIs, or domain objects mid-work.
#
#   Running this check at task START prevents wasting an agent round on a
#   blocked task. Running it at VERIFY time distinguishes an infrastructure
#   crash (deps satisfied, re-assign) from a blocked task (deps not done,
#   re-queue after dep completion).
#
#   However, the orchestrator state file can lag behind the git history: a
#   dep's PR may be merged into alpha while its state still shows "in-progress".
#   Without the secondary git-ancestry check, every agent spawned for the
#   dependent task will block indefinitely — and if the agent's BLOCKED report
#   itself fails to propagate, the orchestrator records "Agent future missing
#   or failed" instead of BLOCKED, creating an unresolvable loop.
#
# Usage:
#   bash .hyperloop/checks/check-deps-satisfied.sh [task-NNN]
#
#   If task-NNN is omitted, the script infers it from the current branch name.
#
# Exit 0  — all deps are done (or merged into alpha, or no deps listed).
# Exit 1  — one or more deps are not done AND not merged into alpha.

set -uo pipefail

STATE_DIR=".hyperloop/state/tasks"

# ── Task ID resolution ────────────────────────────────────────────────────────

TASK_ID="${1:-}"

if [[ -z "$TASK_ID" ]]; then
  BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
  TASK_ID=$(echo "$BRANCH" | grep -oE 'task-[0-9]+' | head -1 || echo "")
fi

if [[ -z "$TASK_ID" ]]; then
  echo "OK: Could not infer task ID from branch name — skipping dep check."
  exit 0
fi

TASK_FILE="${STATE_DIR}/${TASK_ID}.md"

if [[ ! -f "$TASK_FILE" ]]; then
  echo "WARN: Task file not found: $TASK_FILE — skipping dep check."
  exit 0
fi

echo "=== Checking dependencies for $TASK_ID ==="
echo "Task file: $TASK_FILE"

# ── Extract deps from YAML front-matter ──────────────────────────────────────
# Handles both inline (deps: [task-008]) and block (deps:\n- task-008) formats.

# Extract text between the two '---' front-matter delimiters
FRONTMATTER=$(awk '/^---/{found++; if(found==2) exit} found==1{print}' "$TASK_FILE")

# Inline array:  deps: [task-008, task-009]
INLINE_DEPS=$(echo "$FRONTMATTER" | grep -E '^deps:\s*\[' \
  | sed 's/deps:\s*\[//;s/\]//;s/,/ /g' \
  | tr -s ' ' '\n' \
  | grep -E 'task-[0-9]+' || true)

# Block list:
#   deps:
#   - task-008
BLOCK_DEPS=$(echo "$FRONTMATTER" | awk '/^deps:/{found=1; next} found && /^-/{print; next} found && /^[^-]/{exit}' \
  | grep -oE 'task-[0-9]+' || true)

ALL_DEPS=$(printf "%s\n%s" "$INLINE_DEPS" "$BLOCK_DEPS" | grep -E 'task-[0-9]+' | sort -u || true)

if [[ -z "$ALL_DEPS" ]]; then
  echo "OK: No dependencies listed for $TASK_ID."
  exit 0
fi

# ── Detect base branch for ancestry check ────────────────────────────────────

BASE_BRANCH=""
for candidate in alpha main master; do
  if git show-ref --verify --quiet "refs/heads/$candidate" 2>/dev/null; then
    BASE_BRANCH="$candidate"
    break
  fi
done

# ── Check each dep ────────────────────────────────────────────────────────────

FAILED=0

while IFS= read -r dep; do
  [[ -z "$dep" ]] && continue

  DEP_FILE="${STATE_DIR}/${dep}.md"

  if [[ ! -f "$DEP_FILE" ]]; then
    echo "WARN: Dep task file not found: $DEP_FILE (treating as unknown)"
    continue
  fi

  STATUS=$(awk '/^---/{found++; if(found==2) exit} found==1 && /^status:/{print $2; exit}' "$DEP_FILE" | tr -d '"' || echo "unknown")

  if [[ "$STATUS" == "done" ]]; then
    echo "OK: $dep is done."
    continue
  fi

  # ── Secondary check: is the dep's branch merged into alpha? ──────────────
  # This detects the "stale state file" pattern where a dep's PR was merged
  # into alpha but the orchestrator hasn't updated the state file yet.

  MERGED_INTO_BASE=0
  if [[ -n "$BASE_BRANCH" ]]; then
    DEP_BRANCH_REF=""
    # Check remote first, then local
    if git ls-remote --exit-code origin "hyperloop/${dep}" &>/dev/null; then
      git fetch --quiet origin "hyperloop/${dep}" 2>/dev/null || true
      DEP_BRANCH_REF="origin/hyperloop/${dep}"
    elif git show-ref --verify --quiet "refs/heads/hyperloop/${dep}" 2>/dev/null; then
      DEP_BRANCH_REF="hyperloop/${dep}"
    fi

    if [[ -n "$DEP_BRANCH_REF" ]]; then
      if git merge-base --is-ancestor "$DEP_BRANCH_REF" "$BASE_BRANCH" 2>/dev/null; then
        MERGED_INTO_BASE=1
      fi
    fi
  fi

  if [[ "$MERGED_INTO_BASE" -eq 1 ]]; then
    echo "WARN: $dep state shows '$STATUS' but its branch is already merged into $BASE_BRANCH."
    echo "      Orchestrator state file is stale — the dep's code is available in $BASE_BRANCH."
    echo "      Treating as satisfied. Implementer/verifier: note this stale state in your report"
    echo "      and recommend the orchestrator marks $dep as done."
  else
    echo "FAIL: $dep has status '$STATUS' — must be 'done' before $TASK_ID can be implemented."
    FAILED=1
  fi

done <<< "$ALL_DEPS"

# ── Result ────────────────────────────────────────────────────────────────────

echo ""
if [[ "$FAILED" -eq 1 ]]; then
  echo "FAIL: One or more dependencies are not satisfied."
  echo "      Do NOT create a task branch or begin implementation."
  echo "      Re-queue $TASK_ID after the blocking dep(s) are marked done."
  exit 1
fi

echo "PASS: All dependencies satisfied for $TASK_ID — safe to begin implementation."
exit 0
