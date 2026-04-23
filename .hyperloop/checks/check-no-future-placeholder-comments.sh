#!/usr/bin/env bash
# check-no-future-placeholder-comments.sh
#
# Fails if any source file contains comment-style placeholder markers that
# indicate a spec scenario was silently deferred rather than implemented or
# formally scope-blocked.
#
# Patterns caught:
#   <!-- Future: ... -->    (Vue/HTML templates)
#   // Future: ...          (JS/TS)
#   # Future: ...           (Python/shell)
#   <!-- TODO: ... -->      (Vue/HTML templates standing in for missing UI)
#
# A "Future:" comment in production source is NOT acceptable as a substitute
# for implementing a spec scenario. Either implement the scenario or raise a
# formal blocker at .hyperloop/blockers/task-NNN-blocker.md before submitting.
#
# Usage:
#   ./check-no-future-placeholder-comments.sh [source_dir]
#
# Exit 0  — no placeholder comments found.
# Exit 1  — one or more placeholder comments found.

set -euo pipefail

SOURCE_DIR="${1:-src}"

# Only flag placeholder comments in files that this task (branch) actually changed.
# Pre-existing placeholders in files not touched by the current task are not this
# task's responsibility. Tasks that add new placeholders will be caught.
if [[ -z "${BASE_BRANCH:-}" ]]; then
  if git rev-parse --verify origin/alpha &>/dev/null; then
    BASE_BRANCH="origin/alpha"
  else
    BASE_BRANCH="origin/main"
  fi
fi
CHANGED_FILES=$(git diff "${BASE_BRANCH}...HEAD" --name-only 2>/dev/null \
  | grep -E '\.(vue|ts|js|py|html)$' \
  | grep -v node_modules \
  | grep -v '\.nuxt' \
  | grep -v dist \
  | grep -v '\.venv' \
  || true)

if [[ -z "$CHANGED_FILES" ]]; then
  echo "No source files changed in this task. Skipping placeholder comment check."
  exit 0
fi

PLACEHOLDER_PATTERNS=(
  "<!-- Future:"
  "// Future:"
  "# Future:"
  "<!-- TODO:"
  "# TODO: implement"
  "// TODO: implement"
  "<!-- not yet implemented"
  "<!-- placeholder"
)

echo "=== Scanning for future-placeholder comments in task-changed files ==="

found=0

for pattern in "${PLACEHOLDER_PATTERNS[@]}"; do
  # Search only files changed in the current task (scoped to what this PR adds).
  hits=$(echo "$CHANGED_FILES" \
    | xargs -r grep -in "$pattern" 2>/dev/null || true)

  if [[ -n "$hits" ]]; then
    echo ""
    echo "--- Placeholder comment detected (pattern: '$pattern') ---"
    echo "$hits"
    found=$((found + 1))
  fi
done

echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: $found placeholder comment pattern(s) found in source files."
  echo ""
  echo "Placeholder comments are NOT acceptable substitutes for implemented spec scenarios."
  echo "For each blocked scenario, create a formal blocker file:"
  echo "  .hyperloop/blockers/task-NNN-blocker.md"
  echo "describing what is blocked and why, then raise it with the orchestrator."
  exit 1
else
  echo "PASS: No future-placeholder comments found."
  exit 0
fi
