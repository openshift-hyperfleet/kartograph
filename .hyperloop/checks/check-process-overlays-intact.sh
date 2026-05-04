#!/usr/bin/env bash
# check-process-overlays-intact.sh
#
# Fails if any process governance file in .hyperloop/agents/process/ has been
# deleted from the base branch. These overlay YAML files and the kustomization
# are injected into every agent prompt — removing them silently disables
# behavioral rules for all subsequent tasks.
#
# Usage:
#   ./check-process-overlays-intact.sh [base_branch]
#
# Exit 0  — process overlay infrastructure is intact.
# Exit 1  — one or more process governance files have been deleted.

set -euo pipefail

PROCESS_DIR=".hyperloop/agents/process"

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
  echo "WARNING: Could not detect base branch. Skipping process overlay check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping check."
  exit 0
fi

echo "=== Checking for deleted process overlay files (base: $BASE_BRANCH @ $MERGE_BASE) ==="

deleted_overlays=$(git diff --name-only --diff-filter=D "$MERGE_BASE" HEAD -- \
  "$PROCESS_DIR/*.yaml" "$PROCESS_DIR/*.yml" \
  2>/dev/null || true)

found=0

if [[ -n "$deleted_overlays" ]]; then
  echo ""
  echo "--- DELETED process governance files ---"
  echo "$deleted_overlays" | sed 's/^/  /'
  echo ""
  echo "  Process overlay files in $PROCESS_DIR are injected into every agent"
  echo "  at spawn time. Deleting them disables behavioral enforcement rules for"
  echo "  all subsequent tasks — this is a critical process regression."
  found=$((found + 1))
fi

echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: Process governance infrastructure damaged."
  echo ""
  echo "Files in $PROCESS_DIR MUST NOT be deleted or renamed."
  echo "  - Restore deleted files from the base branch ('$BASE_BRANCH')."
  echo "  - If a rule needs to change, EDIT the file — do not delete it."
  exit 1
else
  echo "PASS: Process overlay infrastructure intact."
  exit 0
fi
