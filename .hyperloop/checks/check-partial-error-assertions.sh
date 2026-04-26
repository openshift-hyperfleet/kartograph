#!/usr/bin/env bash
# check-partial-error-assertions.sh
#
# Detects OR-chained assertions on error/result fields in test files.
# These allow tests to pass when only ONE of several spec-required
# components is present in the output, hiding the missing components.
#
# WEAK (fails to verify all required components are present):
#   assert "JSON" in result.errors[0] or "parse" in result.errors[0].lower()
#   assert "line" in msg or "error" in msg
#
# CORRECT (one assertion per spec-required component):
#   assert "line 1" in result.errors[0].lower()
#   assert "line content" in result.errors[1].lower()
#
# When a THEN block says "error is reported WITH line number AND content preview",
# an OR-chained assertion lets the test pass with only one component present.
# Each component the spec names must have its own independent assertion.
#
# Patterns caught:
#   - assert "X" in <result_expr> or "Y" in <result_expr>  (Python)
#   - assert "X" in <expr>.lower() or "Y" in <expr>        (Python)
#   - expect(...).toContain("X") chained with or-style expects on same var (TS)
#
# Usage:
#   ./check-partial-error-assertions.sh [test_dir]
#
# Exit 0 — no OR-chained assertions on result/error fields found.
# Exit 1 — one or more such assertions detected.

set -euo pipefail

TEST_DIR="${1:-src/api/tests}"
UI_TEST_DIR="${2:-src/dev-ui}"

echo "=== Scanning for OR-chained assertions on error/result fields ==="

found=0

# Python patterns: `assert "X" in <result_var> or "Y" in <result_var>`
# We look for the 'or' keyword on assert lines that reference common result
# field accessor patterns (.errors, .message, .detail, .error, .msg).
PYTHON_PATTERNS=(
  'assert .* in .*\.(errors|message|detail|error|msg).* or '
  'assert .* in result\..* or '
  'assert .* in response\..* or '
  'assert .* in err.* or .*\.lower()'
)

for pattern in "${PYTHON_PATTERNS[@]}"; do
  hits=$(grep -rn \
    --include="*.py" \
    --exclude-dir=.venv \
    --exclude-dir=__pycache__ \
    -P "$pattern" "$TEST_DIR" 2>/dev/null || true)

  if [[ -n "$hits" ]]; then
    echo ""
    echo "--- OR-chained assertion detected (pattern: '$pattern') ---"
    echo "$hits"
    echo ""
    echo "  This assertion passes when only ONE of the OR branches matches."
    echo "  If the spec THEN block requires BOTH components, split into two"
    echo "  separate assert statements — one per spec-required component."
    found=$((found + 1))
  fi
done

# TypeScript/vitest patterns: similar OR-chained expect patterns
if [[ -d "$UI_TEST_DIR" ]]; then
  TS_PATTERNS=(
    'expect.*toContain.*\|\|.*toContain'
    'toMatch.*\|\|.*toMatch'
  )

  for pattern in "${TS_PATTERNS[@]}"; do
    hits=$(grep -rEn \
      --include="*.ts" \
      --include="*.spec.ts" \
      --include="*.test.ts" \
      --exclude-dir=node_modules \
      --exclude-dir=".nuxt" \
      "$pattern" "$UI_TEST_DIR" 2>/dev/null || true)

    if [[ -n "$hits" ]]; then
      echo ""
      echo "--- OR-chained assertion detected (pattern: '$pattern') ---"
      echo "$hits"
      echo ""
      echo "  Replace OR-chained expects with separate expect().toContain() calls,"
      echo "  one per spec-required component."
      found=$((found + 1))
    fi
  done
fi

echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: $found OR-chained assertion pattern(s) found in test files."
  echo ""
  echo "OR-chained assertions on error/result fields allow tests to pass when"
  echo "only one of several spec-required components is present. Each component"
  echo "named in the spec THEN block must have its own independent assertion."
  exit 1
else
  echo "PASS: No OR-chained assertions on error/result fields found."
  exit 0
fi
