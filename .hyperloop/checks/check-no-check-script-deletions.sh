#!/usr/bin/env bash
# check-no-check-script-deletions.sh
#
# Fails if any check script in .hyperloop/checks/ has been deleted or if any
# check script has had its .venv exclusion guard removed.
#
# Check scripts are process enforcement infrastructure — they protect spec
# coverage across every task. Deleting or disabling them undermines all prior
# process improvements and is treated the same as deleting tests.
#
# Usage:
#   ./check-no-check-script-deletions.sh [base_branch]
#
# Exit 0  — no check script deletions or sabotage detected.
# Exit 1  — one or more scripts deleted or .venv exclusion removed.

set -euo pipefail

CHECKS_DIR=".hyperloop/checks"

# Detect base branch: accept explicit argument or auto-detect.
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
  echo "WARNING: Could not detect base branch. Skipping check script deletion check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping check."
  exit 0
fi

echo "=== Checking for deleted/sabotaged check scripts (base: $BASE_BRANCH @ $MERGE_BASE) ==="

found=0

# 1. Deleted check scripts
deleted_scripts=$(git diff --name-only --diff-filter=D "$MERGE_BASE" HEAD -- \
  "$CHECKS_DIR/*.sh" 2>/dev/null || true)

if [[ -n "$deleted_scripts" ]]; then
  echo ""
  echo "--- DELETED check scripts ---"
  echo "$deleted_scripts" | sed 's/^/  /'
  found=$((found + 1))
fi

# 2. Check scripts that lost --exclude-dir=.venv (sabotage pattern)
#    Any script that uses grep -r or grep --include and no longer has .venv excluded
#    will scan third-party packages and generate false positives.
sabotaged_scripts=""
existing_scripts=$(find "$CHECKS_DIR" -name "*.sh" 2>/dev/null | sort || true)
for script in $existing_scripts; do
  # Only flag scripts that use grep with include patterns (search-type scripts)
  if grep -q -- '--include=' "$script" 2>/dev/null; then
    if ! grep -qE -- '--exclude-dir=.?.venv' "$script" 2>/dev/null; then
      sabotaged_scripts="${sabotaged_scripts}  $script\n"
    fi
  fi
done

if [[ -n "$sabotaged_scripts" ]]; then
  echo ""
  echo "--- Check scripts MISSING --exclude-dir=.venv (virtual-env scanning sabotage) ---"
  printf "%b" "$sabotaged_scripts"
  echo ""
  echo "  Scripts that grep source files MUST include --exclude-dir=.venv to avoid"
  echo "  false positives from third-party packages in the virtual environment."
  found=$((found + 1))
fi

echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: Check script infrastructure damaged."
  echo ""
  echo "Check scripts in $CHECKS_DIR are process enforcement infrastructure."
  echo "They MUST NOT be deleted, disabled, or modified to produce false positives."
  echo ""
  echo "  - Restore deleted scripts from the base branch ('$BASE_BRANCH')."
  echo "  - Re-add '--exclude-dir=.venv' to any grep-based script that is missing it."
  exit 1
else
  echo "PASS: Check script infrastructure intact."
  exit 0
fi
