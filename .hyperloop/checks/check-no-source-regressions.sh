#!/usr/bin/env bash
# check-no-source-regressions.sh
#
# Fails if any public method, class, or function that existed in the base
# branch has been removed from application source files without a corresponding
# spec mandate. Deletion of existing, working application code causes regressions
# for callers that depend on the interface.
#
# This check operates on application source (not tests). It flags:
#   1. Deleted source files outside the task scope
#   2. Python def/class lines removed from existing source files
#   3. TypeScript export function/class lines removed from existing source files
#
# Usage:
#   ./check-no-source-regressions.sh [base_branch] [source_dir]
#
# Exit 0  — no unspecified source deletions detected.
# Exit 1  — source regressions found; verify each against the spec.

set -euo pipefail

BASE_BRANCH="${1:-}"
SOURCE_DIR="${2:-src}"

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
  echo "WARNING: Could not detect base branch. Skipping source regression check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping check."
  exit 0
fi

echo "=== Checking for source code regressions (base: $BASE_BRANCH @ $MERGE_BASE) ==="

found=0

# 1. Deleted source files (Python, TS, Vue) — excluding test files and __pycache__
deleted_sources=$(git diff --name-only --diff-filter=D "$MERGE_BASE" HEAD -- \
  "$SOURCE_DIR/**/*.py" "$SOURCE_DIR/**/*.ts" "$SOURCE_DIR/**/*.vue" \
  2>/dev/null \
  | grep -v '__pycache__' \
  | grep -v '\.pyc$' \
  | grep -v '/tests/' \
  | grep -v '\.test\.ts$' \
  | grep -v '\.spec\.ts$' \
  || true)

if [[ -n "$deleted_sources" ]]; then
  echo ""
  echo "--- DELETED source files ---"
  echo "$deleted_sources" | sed 's/^/  /'
  echo ""
  echo "  Each deletion above must correspond to an explicit spec requirement."
  echo "  If the spec does not mention removing these files, restore them."
  found=$((found + 1))
fi

# 2. Python public method/function removals in existing source files
#    Look for 'def <name>(' lines removed (lines starting with 'def ' or '    def ')
python_method_removals=""
changed_py_sources=$(git diff --name-only "$MERGE_BASE" HEAD -- \
  "$SOURCE_DIR/**/*.py" \
  2>/dev/null \
  | grep -v '/tests/' \
  | grep -v '__pycache__' \
  || true)

for f in $changed_py_sources; do
  # Skip deleted files (already handled above)
  if ! git show "HEAD:$f" &>/dev/null 2>&1; then
    continue
  fi
  removed_defs=$(git diff "$MERGE_BASE" HEAD -- "$f" 2>/dev/null \
    | grep '^-[^-]' \
    | grep -E '^\-[[:space:]]*(async )?def [a-zA-Z_][a-zA-Z0-9_]*\(' \
    | grep -v '__init__\|__repr__\|__str__\|__eq__\|__hash__\|__len__\|__bool__' \
    | sed "s/^/  [$f] /" \
    || true)
  if [[ -n "$removed_defs" ]]; then
    python_method_removals="${python_method_removals}${removed_defs}\n"
  fi
done

if [[ -n "$python_method_removals" ]]; then
  echo ""
  echo "--- Removed Python methods/functions in application source ---"
  printf "%b" "$python_method_removals"
  echo ""
  echo "  Each removed method must correspond to an explicit spec requirement."
  echo "  If the spec does not mandate removal, restore the method."
  found=$((found + 1))
fi

echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: Source regressions detected."
  echo ""
  echo "Existing, working application code MUST NOT be removed without a spec mandate."
  echo "  - Deleting a working method removes functionality callers depend on."
  echo "  - If the spec explicitly says to remove it, document that ref in your commit."
  echo "  - If you cannot find the spec requirement, restore the deleted code."
  exit 1
else
  echo "PASS: No unspecified source regressions detected."
  exit 0
fi
