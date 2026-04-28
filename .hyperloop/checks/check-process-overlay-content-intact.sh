#!/usr/bin/env bash
# check-process-overlay-content-intact.sh
#
# Fails if any line has been REMOVED from a process overlay file in
# .hyperloop/agents/process/ relative to the base branch.
#
# WHY: check-process-overlays-intact.sh only detects file deletions. An
# implementer can remove individual rules from an overlay (silently disabling
# behavioral enforcement) without deleting the file, and the existing check
# passes. Observed in task-035: a rule about worker-result.yaml rebase hygiene
# was removed from implementer-overlay.yaml in a cleanup commit, causing the
# exact failure mode the rule was designed to prevent.
#
# POLICY:
#   - Adding lines to overlay files is always permitted (process-improvement agent
#     does this intentionally).
#   - Removing lines is a content regression and is always blocked.
#   - If a rule genuinely needs to be replaced, the new text must appear before
#     the old text is removed (net addition ≥ 0 lines per file).
#
# REMEDIATION:
#   git diff $(git merge-base HEAD alpha) HEAD -- .hyperloop/agents/process/
#   # Find removed lines (prefixed with '-'). Restore them.
#   # Then re-run this check.
#
# Usage:
#   bash .hyperloop/checks/check-process-overlay-content-intact.sh [base_branch]
#
# Exit 0  — no overlay content has been removed.
# Exit 1  — one or more lines were removed from an overlay file.

set -uo pipefail

PROCESS_DIR=".hyperloop/agents/process"

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
  echo "WARNING: Could not detect base branch. Skipping process overlay content check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping check."
  exit 0
fi

echo "=== Checking process overlay content integrity (base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="

# Get list of overlay files that existed at the merge-base.
# We check YAML files only (the overlay format).
overlay_files_at_base=$(git ls-tree -r --name-only "$MERGE_BASE" -- "$PROCESS_DIR" 2>/dev/null \
  | grep -E '\.(yaml|yml)$' || true)

if [[ -z "$overlay_files_at_base" ]]; then
  echo "INFO: No overlay YAML files found at merge-base — nothing to check."
  echo "PASS: Process overlay content intact."
  exit 0
fi

found_removals=0

while IFS= read -r overlay_file; do
  # Skip files that no longer exist at HEAD (check-process-overlays-intact.sh
  # already handles file-level deletions; we don't double-report here).
  if ! git cat-file -e "HEAD:$overlay_file" 2>/dev/null; then
    continue
  fi

  # Count lines removed (lines starting with '-' in the diff, excluding diff
  # header lines like '--- a/file' and hunk markers '@@ ... @@').
  removed_lines=$(git diff "$MERGE_BASE"..HEAD -- "$overlay_file" 2>/dev/null \
    | grep '^-' \
    | grep -v '^---' \
    || true)

  if [[ -n "$removed_lines" ]]; then
    found_removals=$((found_removals + 1))
    echo ""
    echo "FAIL: Lines removed from $overlay_file:"
    echo "$removed_lines" | head -40 | sed 's/^/  /'
    if [[ $(echo "$removed_lines" | wc -l) -gt 40 ]]; then
      echo "  ... (truncated; run git diff $MERGE_BASE HEAD -- $overlay_file to see all)"
    fi
    echo ""
    echo "  Process overlay files must never have lines removed — removing a rule"
    echo "  silently disables behavioral enforcement for all subsequent tasks."
    echo ""
    echo "  To fix: restore the removed lines in $overlay_file, then re-run this check."
    echo "  If a rule needs updating, add the new text before removing the old text"
    echo "  (or just edit it in-place within a single commit — net lines ≥ 0)."
  fi
done <<< "$overlay_files_at_base"

echo ""
if [[ $found_removals -gt 0 ]]; then
  echo "RESULT: FAIL — $found_removals overlay file(s) have content regressions."
  exit 1
else
  echo "PASS: No lines removed from any process overlay file."
  exit 0
fi
