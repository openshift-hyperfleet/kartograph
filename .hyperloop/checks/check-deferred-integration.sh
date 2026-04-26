#!/usr/bin/env bash
# check-deferred-integration.sh
#
# Fails if any source file contains docstring or comment language that defers
# framework/library integration to a future task, without a corresponding formal
# blocker file at .hyperloop/blockers/task-NNN-blocker.md.
#
# Root cause this check addresses:
#   task-012: The GitHubAdapter declared dlt as a pyproject.toml dependency but
#   never imported or called dlt in production code. The adapter docstring said
#   "dlt integration deferred to a future task." The spec had a SHALL requirement
#   for dlt — declaring the dependency without implementing the import is PARTIAL,
#   not COVERED. The verifier must issue FAIL in this case.
#
# What this check catches:
#   Patterns in Python docstrings and comments that explicitly state a library
#   or framework integration is deferred, pending, or "future work":
#
#     # dlt integration deferred to a future task
#     """dlt integration is deferred."""
#     # TODO: integrate dlt
#     # NOTE: X integration is deferred
#     # X will be integrated in a future task
#     # X integration pending
#
# What constitutes a legitimate exemption:
#   A formal blocker file at .hyperloop/blockers/task-NNN-blocker.md that
#   names the deferred library and explains why it cannot be integrated now.
#   If a blocker file exists for the current task, this check reports a WARNING
#   (not a failure) — the orchestrator is aware of the gap.
#
# Usage:
#   ./check-deferred-integration.sh [source_dir]
#
# Exit 0  — no unblocked deferred-integration comments found.
# Exit 1  — one or more deferred-integration comments without a blocker.

set -euo pipefail

SOURCE_DIR="${1:-src/api}"
BLOCKERS_DIR=".hyperloop/blockers"

echo "=== Checking for deferred framework integration comments in: $SOURCE_DIR ==="

# Patterns that indicate a library/framework integration has been deferred.
# All patterns are case-insensitive and matched with grep -iE.
DEFERRAL_PATTERNS=(
  "integration deferred"
  "deferred to a future task"
  "deferred for a future"
  "integrate.*in a future task"
  "integration is pending"
  "framework integration.*deferred"
  "not yet integrated"
  "integration.*not yet implemented"
  "will be integrated.*later"
  "will integrate.*future"
  "TODO:.*integrat"
  "NOTE:.*integration.*deferred"
  "integration.*TODO"
)

found=0

for pattern in "${DEFERRAL_PATTERNS[@]}"; do
  hits=$(grep -rn \
    --include="*.py" \
    --exclude-dir=__pycache__ \
    --exclude-dir=.venv \
    --exclude-dir=tests \
    -iE "$pattern" \
    "$SOURCE_DIR" 2>/dev/null || true)

  if [[ -n "$hits" ]]; then
    # Check if any blocker file exists — if a blocker covers this, warn instead of fail.
    blocker_count=0
    if [[ -d "$BLOCKERS_DIR" ]]; then
      blocker_count=$(find "$BLOCKERS_DIR" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    fi

    if [[ "$blocker_count" -eq 0 ]]; then
      echo ""
      echo "--- Deferred integration comment without a blocker (pattern: '$pattern') ---"
      echo "$hits"
      found=$((found + 1))
    else
      echo ""
      echo "INFO: Deferred integration comment found but blocker(s) exist in $BLOCKERS_DIR"
      echo "  (pattern: '$pattern'). Verify the blocker covers this specific deferral."
      echo "$hits" | sed 's/^/  /'
    fi
  fi
done

# Second pass: check if a SHALL-declared library appears in pyproject.toml but has
# no production import. This catches the "declared but never imported" anti-pattern.
#
# Use `wc -l` instead of `grep -c` to avoid the grep-no-match exit-1 bug where
# grep emits the count "0" before exiting non-zero, causing `|| echo 0` to produce
# a two-line "0\n0" value that breaks arithmetic tests.
PYPROJECT="${SOURCE_DIR%/api}/api/pyproject.toml"
if [[ ! -f "$PYPROJECT" ]]; then
  PYPROJECT="pyproject.toml"
fi

if [[ -f "$PYPROJECT" ]]; then
  echo ""
  echo "=== Checking for SHALL-declared libraries with no production import ==="

  # Libraries known to be SHALL requirements from current specs.
  # Extend this list as new SHALL framework requirements are added.
  SHALL_LIBS=("dlt")

  for lib in "${SHALL_LIBS[@]}"; do
    # Count pyproject.toml references.
    # Wrap grep in a group with || true so that "no matches" (grep exit 1) does not
    # cause pipefail to abort the script. wc -l always exits 0 and outputs the count.
    in_pyproject=$( (grep -iE "\"${lib}|'${lib}|${lib}\[" "$PYPROJECT" 2>/dev/null || true) | wc -l | tr -d ' ')

    if [[ "$in_pyproject" -gt 0 ]]; then
      # Check if it's imported anywhere in production source.
      # Same grep || true pattern to prevent pipefail abort on no-matches.
      import_count=$( (grep -rl \
        --include="*.py" \
        --exclude-dir=__pycache__ \
        --exclude-dir=.venv \
        --exclude-dir=tests \
        -E "^import ${lib}|^from ${lib}" \
        "$SOURCE_DIR" 2>/dev/null || true) | wc -l | tr -d ' ')

      if [[ "$import_count" -eq 0 ]]; then
        echo ""
        echo "--- SHALL library declared in pyproject.toml but never imported in production code ---"
        echo "  Library:              $lib"
        echo "  pyproject.toml refs:  $in_pyproject line(s)"
        echo "  Production imports:   NONE"
        echo ""
        echo "  Adding a library to pyproject.toml is a PREREQUISITE, not an"
        echo "  implementation. A SHALL requirement for '$lib' is NOT satisfied"
        echo "  until at least one 'import $lib' or 'from $lib ...' statement"
        echo "  exists in production source code under $SOURCE_DIR."
        found=$((found + 1))
      else
        echo "  PASS: $lib — declared in pyproject.toml AND imported in $import_count production file(s)."
      fi
    fi
  done
fi

echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: $found deferred-integration issue(s) found."
  echo ""
  echo "Required action (choose ONE per deferred item):"
  echo "  A) Implement the framework integration now."
  echo "     - Import the library in production code."
  echo "     - Wire it into the relevant code path."
  echo "     - Write a test that verifies the framework is actually invoked."
  echo ""
  echo "  B) Raise a formal blocker if integration is genuinely impossible now:"
  echo "       .hyperloop/blockers/task-NNN-blocker.md"
  echo "     Name the blocked library, explain why, and notify the orchestrator."
  echo "     Remove the deferral comment from source."
  echo ""
  echo "A comment or docstring saying 'integration deferred' is NEVER a substitute"
  echo "for implementation or a formal blocker."
  exit 1
else
  echo "PASS: No unblocked deferred-integration issues found."
  exit 0
fi
