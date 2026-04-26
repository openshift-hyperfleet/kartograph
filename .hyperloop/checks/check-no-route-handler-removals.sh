#!/usr/bin/env bash
# check-no-route-handler-removals.sh
#
# Fails if any async route handler (async def ...) that existed in
# */presentation/*/routes.py on the base branch has been removed on the
# current branch without a spec mandate.
#
# WHY A SEPARATE SCRIPT:
#   check-no-source-regressions.sh covers general Python method removals, but
#   its sed-based prefix injection has had a known false-PASS history when
#   file paths contain '/' characters (observed in task-035 Finding 4: three
#   route handlers — get_data_source, update_data_source, delete_data_source —
#   were deleted from management/presentation/data_sources/routes.py and the
#   general check returned PASS). This script avoids that fragility by using
#   grep-based filtering on the raw diff output with no sed path injection.
#
# DETECTION STRATEGY:
#   1. Collect all routes.py files under */presentation/* that were modified
#      or deleted on this branch (grep-based, not pathspec globs).
#   2. For each such file, grep the diff for lines matching
#      '^-[[:space:]]*(async )?def [a-z]' (removed function definitions).
#   3. Any match is a blocking failure unless the spec explicitly mandates
#      the removal.
#
# check-service-route-coverage.sh is complementary but catches a different
# failure mode: service methods with no HTTP route. This script catches the
# inverse: existing HTTP routes that were removed.
#
# Usage:
#   ./check-no-route-handler-removals.sh [base_branch]
#
# Exit 0  — no route handlers removed.
# Exit 1  — one or more async route handlers removed from routes.py files.

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
  echo "WARNING: Could not detect base branch. Skipping route handler removal check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping check."
  exit 0
fi

echo "=== Checking for removed route handlers in routes.py files (base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="

# Use grep-based filtering on the raw name-only diff — no pathspec globs that
# could silently expand to nothing in different shell environments.
changed_routes=$(git diff --name-only "$MERGE_BASE" HEAD 2>/dev/null \
  | grep '/presentation/' \
  | grep '/routes\.py$' \
  || true)

found=0
report=""

for f in $changed_routes; do
  # Get the diff for this specific file using -- to avoid pathspec ambiguity.
  removed_handlers=$(git diff "$MERGE_BASE" HEAD -- "$f" 2>/dev/null \
    | grep '^-[^-]' \
    | grep -E '^-[[:space:]]*(async )?def [a-z_][a-zA-Z0-9_]*\(' \
    || true)

  if [[ -n "$removed_handlers" ]]; then
    report="${report}\n  File: $f\n"
    while IFS= read -r line; do
      # Strip the leading diff '-' and print with indentation.
      report="${report}    ${line#-}\n"
    done <<< "$removed_handlers"
    found=$((found + 1))
  fi
done

echo ""
if [[ $found -gt 0 ]]; then
  printf "%b" "$report"
  echo ""
  echo "FAIL: Route handlers removed from presentation/routes.py file(s)."
  echo ""
  echo "Removing an existing route handler breaks the API contract for any"
  echo "client (including tests) that calls that endpoint. Unless the spec"
  echo "explicitly mandates the removal, restore each deleted handler."
  echo ""
  echo "To restore from the merge base:"
  echo "  git show ${MERGE_BASE}:<path/to/routes.py>"
  echo "  # copy the missing async def block back into the file"
  echo ""
  echo "Note: If the entire routes.py diff is larger than the removed handlers,"
  echo "run the full source-regression check to identify all impacted files:"
  echo "  bash .hyperloop/checks/check-no-source-regressions.sh"
  exit 1
else
  echo "PASS: No route handlers were removed from routes.py files."
  exit 0
fi
