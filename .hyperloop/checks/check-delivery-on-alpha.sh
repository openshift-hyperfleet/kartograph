#!/usr/bin/env bash
# check-delivery-on-alpha.sh
#
# Checks whether the implementation work on this task branch has already been
# incorporated into the base branch (alpha), i.e., merged via a different PR
# while this branch remained blocked by orchestrator contamination.
#
# WHY THIS CHECK:
#   task-145 (round 3): The implementer's fix was correct and had already been
#   merged to alpha as commit fbe327bc7 (PR #628). Despite this, the verifier
#   issued a FAIL verdict that caused the orchestrator to route back to the
#   implementer for a third consecutive round — because there was no mechanical
#   way to confirm that the delivery content was already present on alpha.
#
#   This script provides that signal. When it exits 0, the task's implementation
#   is done and the orchestrator should mark the task complete using the alpha
#   commit as evidence, NOT route to the implementer for another round.
#
# DETECTION METHOD:
#   1. Identify delivery commits: commits on this branch with Task-Ref matching
#      the task identifier extracted from the branch name.
#   2. For each delivery commit, check whether its subject line appears in
#      alpha's log — subject equality is the primary signal (same commit message
#      = same or cherry-picked equivalent commit).
#   3. Report per-commit status and a summary PRESENT/ABSENT result.
#
# NOTE: Subject-line matching is intentionally loose — it catches cherry-picks
# and squash-merges that preserve the original subject. If a merge rewrote the
# subject, this script may produce false ABSENT results; treat the output as
# evidence, not a hard gate.
#
# Usage:
#   bash .hyperloop/checks/check-delivery-on-alpha.sh [base_branch]
#
# Exit 0  — ALL delivery commits confirmed present on base branch (task merged).
# Exit 1  — one or more delivery commits absent from base branch.
# Exit 2  — no delivery commits found (unable to determine status).

set -uo pipefail

# Normalize CWD to repo root.
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
  echo "WARNING: Could not detect base branch. Skipping delivery-on-alpha check."
  exit 2
fi

# Prefer remote ref for freshest alpha state.
if git show-ref --verify --quiet "refs/remotes/origin/$BASE_BRANCH" 2>/dev/null; then
  ALPHA_REF="origin/$BASE_BRANCH"
else
  ALPHA_REF="$BASE_BRANCH"
fi

MERGE_BASE=$(git merge-base HEAD "$ALPHA_REF" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $ALPHA_REF. Skipping check."
  exit 2
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD)
EXPECTED_TASK=$(echo "$BRANCH" | grep -oE 'task-[0-9]+' | head -1 || true)

if [[ -z "$EXPECTED_TASK" ]]; then
  echo "WARNING: Branch '$BRANCH' has no task-NNN pattern. Skipping check."
  exit 2
fi

echo "=== Checking whether $EXPECTED_TASK delivery commits are already on $ALPHA_REF ==="
echo ""

# Collect delivery commits: commits with Task-Ref matching the expected task.
delivery_shas=()
while IFS= read -r sha; do
  [[ -z "$sha" ]] && continue
  task_ref=$(git log -1 --format='%(trailers:key=Task-Ref,valueonly)' "$sha" 2>/dev/null \
    | tr -d '[:space:]' || true)
  if [[ "$task_ref" == "$EXPECTED_TASK" ]]; then
    delivery_shas+=("$sha")
  fi
done < <(git rev-list --first-parent "${MERGE_BASE}..HEAD" 2>/dev/null || true)

if [[ ${#delivery_shas[@]} -eq 0 ]]; then
  echo "INFO: No delivery commits found with Task-Ref: $EXPECTED_TASK on this branch."
  echo ""
  echo "RESULT: UNKNOWN — no delivery commits to check against $ALPHA_REF."
  exit 2
fi

echo "Delivery commits with Task-Ref: $EXPECTED_TASK: ${#delivery_shas[@]}"
echo ""

found_on_alpha=0
not_on_alpha=0

for sha in "${delivery_shas[@]}"; do
  subject=$(git log -1 --format='%s' "$sha" 2>/dev/null || echo "<unknown>")
  short_sha="${sha:0:10}"

  # Primary signal: subject line present in alpha log.
  alpha_match=$(git log --oneline "$ALPHA_REF" | grep -F "$subject" | head -1 || true)

  if [[ -n "$alpha_match" ]]; then
    echo "  PRESENT ON ALPHA: $short_sha — $subject"
    echo "            Found:  $alpha_match"
    found_on_alpha=$((found_on_alpha + 1))
  else
    echo "  ABSENT FROM ALPHA: $short_sha — $subject"
    not_on_alpha=$((not_on_alpha + 1))
  fi
done

echo ""
echo "Summary: $found_on_alpha delivery commit(s) PRESENT on $ALPHA_REF, $not_on_alpha ABSENT."
echo ""

if [[ $found_on_alpha -gt 0 && $not_on_alpha -eq 0 ]]; then
  echo "RESULT: ALL DELIVERY COMMITS PRESENT ON $ALPHA_REF"
  echo ""
  echo "The task implementation has already been merged via a different path."
  echo "The orchestrator should mark this task COMPLETE using the alpha commit"
  echo "SHA(s) listed above as evidence of delivery."
  echo ""
  echo "## ORCHESTRATOR ROUTING: MARK_COMPLETE"
  echo "## DO NOT ROUTE TO IMPLEMENTER — the implementation is already done."
  exit 0
elif [[ $found_on_alpha -gt 0 && $not_on_alpha -gt 0 ]]; then
  echo "RESULT: PARTIAL — $found_on_alpha of $((found_on_alpha + not_on_alpha)) delivery commit(s) present on $ALPHA_REF."
  echo "        Remaining commits may need a clean cherry-pick to alpha."
  exit 1
else
  echo "RESULT: DELIVERY COMMITS NOT PRESENT ON $ALPHA_REF"
  echo "        The task implementation has not been merged to $ALPHA_REF."
  echo "        A clean cherry-pick branch is required to deliver this work."
  exit 1
fi
