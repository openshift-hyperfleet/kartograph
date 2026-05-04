#!/usr/bin/env bash
# check-weak-test-assertions.sh
#
# Detects loose membership assertions on categorical fields in test files.
# These patterns allow misclassification regressions to pass undetected:
#
#   assert result.error_type in ["timeout", "execution_error"]  # WEAK
#   assert result.error_type == "timeout"                       # CORRECT
#
# The spec assigns exact categories to each error scenario. Tests must
# enforce the exact category with strict equality, not a permissive list.
#
# Patterns caught:
#   - error_type in [         (Python pytest / integration tests)
#   - .error_type).toEqual(   followed by an array (TS/vitest — separate check)
#   - status_code in [
#   - error_code in [
#
# Usage:
#   ./check-weak-test-assertions.sh [test_dir]
#
# Exit 0  — no weak assertions found.
# Exit 1  — one or more weak membership assertions detected.

set -euo pipefail

TEST_DIR="${1:-src/api/tests}"
UI_TEST_DIR="${2:-src/dev-ui}"

echo "=== Scanning for weak 'in [...]' test assertions ==="

found=0

# Python test patterns: `assert <expr> in [<value>, <value>]`
# The most dangerous form is asserting a categorical field against a list
# of two or more values that should be mutually exclusive per the spec.
PYTHON_PATTERNS=(
  "error_type in \["
  "status_code in \["
  "error_code in \["
  "\.type in \["
  "\.category in \["
)

for pattern in "${PYTHON_PATTERNS[@]}"; do
  hits=$(grep -rn \
    --include="*.py" \
    --exclude-dir=.venv \
    --exclude-dir=__pycache__ \
    "$pattern" "$TEST_DIR" 2>/dev/null || true)

  if [[ -n "$hits" ]]; then
    echo ""
    echo "--- Weak assertion detected (pattern: '$pattern') ---"
    echo "$hits"
    echo ""
    echo "  Replace 'assert X in [\"a\", \"b\"]' with 'assert X == \"a\"'."
    echo "  If the spec genuinely permits multiple values, document the exact"
    echo "  spec text justifying the loose assertion as a comment on that line."
    found=$((found + 1))
  fi
done

# TypeScript/vitest patterns: expect(x).toContain or toMatchObject with union list
TS_PATTERNS=(
  "error_type.*toEqual\(\["
  "errorType.*toEqual\(\["
)

if [[ -d "$UI_TEST_DIR" ]]; then
  for pattern in "${TS_PATTERNS[@]}"; do
    hits=$(grep -rn \
      --include="*.ts" \
      --include="*.spec.ts" \
      --exclude-dir=node_modules \
      --exclude-dir=".nuxt" \
      "$pattern" "$UI_TEST_DIR" 2>/dev/null || true)

    if [[ -n "$hits" ]]; then
      echo ""
      echo "--- Weak assertion detected (pattern: '$pattern') ---"
      echo "$hits"
      echo ""
      echo "  Replace 'expect(x).toEqual([...])' with 'expect(x).toBe(\"exact-value\")'."
      found=$((found + 1))
    fi
  done
fi

echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: $found weak assertion pattern(s) found in test files."
  echo ""
  echo "Loose 'in [list]' assertions on categorical fields permit misclassification"
  echo "regressions to pass undetected. Use strict equality (== or toBe) to enforce"
  echo "the exact category specified in the THEN block of the relevant spec scenario."
  exit 1
else
  echo "PASS: No weak categorical assertions found."
  exit 0
fi
