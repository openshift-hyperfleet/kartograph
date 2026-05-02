#!/usr/bin/env bash
# check-frontend-type-check.sh
#
# Runs vue-tsc (TypeScript type-check for Vue) on the dev-ui project and
# fails if any type errors are reported.
#
# Unit tests exercise component LOGIC but cannot catch import-level syntax
# errors such as duplicate import blocks (task-045 blocking defect) because
# vitest mocks the component graph at the module boundary. Only a type-check
# or full build will surface those errors.
#
# This check is intentionally separate from check-frontend-tests-pass.sh so
# that a type error is reported with a clear, actionable message rather than
# buried in test output.
#
# Usage:
#   bash .hyperloop/checks/check-frontend-type-check.sh [ui_dir]
#
# Exit 0  — vue-tsc exits 0 (no type errors).
# Exit 1  — vue-tsc exits non-zero OR pnpm/vue-tsc not available.
# Exit 0  — no package.json found (non-frontend task).

set -euo pipefail

UI_DIR="${1:-src/dev-ui}"

if [[ ! -f "$UI_DIR/package.json" ]]; then
  echo "No package.json found at $UI_DIR. Skipping frontend type-check."
  exit 0
fi

# Only run when vue-tsc is declared as a dependency/devDependency.
if ! grep -q "vue-tsc" "$UI_DIR/package.json" 2>/dev/null; then
  echo "vue-tsc not declared in $UI_DIR/package.json. Skipping type-check."
  exit 0
fi

if ! command -v pnpm &>/dev/null; then
  echo "FAIL: pnpm is not installed. Cannot run frontend type-check."
  exit 1
fi

# node_modules must exist for vue-tsc to resolve types.
if [[ ! -d "$UI_DIR/node_modules" ]]; then
  echo "FAIL: $UI_DIR/node_modules is absent."
  echo ""
  echo "The frontend dependencies must be installed before a type-check can run:"
  echo "  cd $UI_DIR && pnpm install"
  echo ""
  echo "After installing, commit pnpm-lock.yaml if it changed."
  exit 1
fi

echo "=== Running vue-tsc type-check in: $UI_DIR ==="

set +e
(cd "$UI_DIR" && pnpm exec vue-tsc --noEmit 2>&1)
exit_code=$?
set -e

echo ""
if [[ $exit_code -eq 0 ]]; then
  echo "PASS: vue-tsc reported no type errors."
  exit 0
else
  echo "FAIL: vue-tsc exited with code $exit_code."
  echo ""
  echo "Common causes:"
  echo "  1. Duplicate import block — two 'import { ... } from <module>' statements"
  echo "     for the same module in the same file (root cause of task-045 FAIL)."
  echo "     Fix: merge the two blocks into one."
  echo "  2. A named export used in the component does not exist in the source module."
  echo "  3. Type mismatch on a prop or return value."
  echo ""
  echo "Run: cd $UI_DIR && pnpm exec vue-tsc --noEmit"
  echo "to see the full error list with file names and line numbers."
  exit 1
fi
