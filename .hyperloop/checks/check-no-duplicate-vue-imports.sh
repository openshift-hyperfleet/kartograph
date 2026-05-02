#!/usr/bin/env bash
# check-no-duplicate-vue-imports.sh
#
# Detects duplicate `import { ... } from '<module>'` statements in Vue and
# TypeScript files modified on this branch.
#
# Duplicate import blocks are a TypeScript/build error that unit tests cannot
# catch — they fail `vue-tsc` and `pnpm build` even when all logic tests pass.
# Root cause of task-045 blocking defect: task-074 added Select imports to
# mutations.vue without removing the pre-existing Select import block.
#
# Usage:
#   bash .hyperloop/checks/check-no-duplicate-vue-imports.sh [file...]
#
#   When called with no arguments, checks all .vue and .ts files changed
#   relative to the merge-base with alpha.
#
# Exit 0  — no duplicate imports found.
# Exit 1  — one or more files contain duplicate imports from the same module.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# Determine files to check.
if [[ $# -gt 0 ]]; then
  files=("$@")
else
  MERGE_BASE="$(git merge-base HEAD alpha 2>/dev/null || git merge-base HEAD origin/alpha 2>/dev/null)"
  if [[ -z "$MERGE_BASE" ]]; then
    echo "WARN: Cannot determine merge-base with alpha. Checking all .vue and .ts files."
    mapfile -t files < <(git ls-files '*.vue' '*.ts' 2>/dev/null || true)
  else
    mapfile -t files < <(
      git diff --name-only "$MERGE_BASE"..HEAD -- '*.vue' '*.ts' 2>/dev/null || true
    )
  fi
fi

if [[ ${#files[@]} -eq 0 ]]; then
  echo "PASS: No .vue or .ts files to check."
  exit 0
fi

echo "=== Checking for duplicate imports in ${#files[@]} file(s) ==="

failed=0
failed_files=()

for file in "${files[@]}"; do
  [[ -z "$file" ]] && continue
  [[ ! -f "$file" ]] && continue

  # Extract all `from '...'` and `from "..."` module specifiers, including
  # multi-line import blocks collapsed to just their from clause.
  # Count occurrences of each unique module specifier; flag any > 1.
  duplicates=$(
    grep -oE "from ['\"][^'\"]+['\"]" "$file" 2>/dev/null \
      | sort \
      | uniq -d \
      || true
  )

  if [[ -n "$duplicates" ]]; then
    echo ""
    echo "FAIL: $file contains duplicate import(s) from:"
    while IFS= read -r dup; do
      echo "  $dup"
    done <<< "$duplicates"
    echo "  Fix: merge the two import blocks into one."
    failed=$((failed + 1))
    failed_files+=("$file")
  fi
done

echo ""
if [[ $failed -gt 0 ]]; then
  echo "FAIL: $failed file(s) contain duplicate imports."
  echo ""
  echo "Root cause pattern: when extending a Vue component that already imports"
  echo "from a UI library (e.g. @/components/ui/select), adding new feature code"
  echo "re-imports the same symbols without removing the original import block."
  echo ""
  echo "Fix for each failing file:"
  echo "  1. Open the file and search for multiple 'from <module>' lines."
  echo "  2. Merge the named imports into a single import statement."
  echo "  3. Re-run this check to confirm exit 0."
  exit 1
else
  echo "PASS: No duplicate imports found."
  exit 0
fi
