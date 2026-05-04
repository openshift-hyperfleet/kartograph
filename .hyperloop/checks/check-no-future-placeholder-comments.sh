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

echo "=== Scanning for future-placeholder comments in: $SOURCE_DIR ==="

found=0

for pattern in "${PLACEHOLDER_PATTERNS[@]}"; do
  hits=$(grep -rn \
    --include="*.vue" \
    --include="*.ts" \
    --include="*.js" \
    --include="*.py" \
    --include="*.html" \
    --exclude-dir=node_modules \
    --exclude-dir=__pycache__ \
    --exclude-dir=.git \
    --exclude-dir=dist \
    --exclude-dir=".nuxt" \
    --exclude-dir=.venv \
    -i "$pattern" "$SOURCE_DIR" 2>/dev/null || true)

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
