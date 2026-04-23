#!/usr/bin/env bash
# check-cross-task-deferral.sh
#
# Fails if any source file contains inline comments that defer API wiring or
# data population to a future task number. Such forward references are stubs:
# they compile and render, but the feature does not actually work.
#
# Patterns caught (case-insensitive):
#   // Knowledge graph creation will be wired to the API in task-015.
#   // Placeholder list — will be populated once KG management API exists (task-015).
#   // For now, close the dialog and guide the user to ...
#   // Will be wired in task-NNN
#   // when [X] routes are available
#   "in task-0" / "in task-1" etc. — explicit cross-task forward references
#
# Acceptable alternative: raise a formal blocker at .hyperloop/blockers/task-NNN-blocker.md
# and do NOT leave the deferred code path in the source.
#
# Usage:
#   ./check-cross-task-deferral.sh [source_dir]
#
# Exit 0  — no cross-task deferral comments found.
# Exit 1  — one or more deferral comments found.

set -euo pipefail

SOURCE_DIR="${1:-src}"

# Each pattern targets a distinct phrasing of "we'll do this in a later task".
DEFERRAL_PATTERNS=(
  "will be wired.*in task-"
  "wired to the API in task-"
  "will be populated once"
  "Placeholder.*will be"
  "will be.*once.*API exists"
  "when.*routes are available"
  "For now, close the dialog"
  "For now, emit"
  "in task-[0-9][0-9][0-9]"
)

echo "=== Scanning for cross-task deferral comments in: $SOURCE_DIR ==="

found=0

for pattern in "${DEFERRAL_PATTERNS[@]}"; do
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
    -iE "$pattern" "$SOURCE_DIR" 2>/dev/null || true)

  if [[ -n "$hits" ]]; then
    echo ""
    echo "--- Cross-task deferral detected (pattern: '$pattern') ---"
    echo "$hits"
    found=$((found + 1))
  fi
done

echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: $found cross-task deferral pattern(s) found in source files."
  echo ""
  echo "Comments that defer API wiring or data population to a future task are stubs."
  echo "The feature compiles and renders but does not actually work."
  echo ""
  echo "Required action (choose ONE):"
  echo "  A) If the required API endpoint already exists in the codebase, implement"
  echo "     the call now. Do not defer it."
  echo "  B) If the endpoint genuinely does not exist yet, raise a formal blocker:"
  echo "       .hyperloop/blockers/task-NNN-blocker.md"
  echo "     describing the dependency, remove the placeholder code, and raise"
  echo "     it with the orchestrator before submitting."
  echo ""
  echo "A code comment alone is never an acceptable substitute for implementation."
  exit 1
else
  echo "PASS: No cross-task deferral comments found."
  exit 0
fi
