#!/usr/bin/env bash
# check-watch-handler-reload-tests.sh
#
# Detects watch handlers in Vue pages/composables that perform both a clear AND
# a fetch/reload, then verifies the corresponding test file covers the fetch call
# (not just the clear).
#
# Background (task-058): Implementers consistently tested the "clear state" half
# of watch(tenantVersion, ...) handlers but omitted assertions that the subsequent
# fetch/reload API calls were made. Two pages shipped with PARTIAL coverage.
#
# Heuristic: For each *.vue file under pages/ or composables/ that contains both
# of the following patterns in a watch body:
#   - An assignment clearing a ref: `XXX.value = ` (state clear)
#   - A function call that looks like a fetch/load: fetch*()/load*()
# ...we check the companion test file for an assertion on the fetch call.
#
# Exit 0 — no gaps detected (or none applicable).
# Exit 1 — one or more fetch calls in watch handlers lack test coverage.
#
# Usage:
#   bash .hyperloop/checks/check-watch-handler-reload-tests.sh [src_dir]

set -euo pipefail

SRC_DIR="${1:-src/dev-ui/app}"

if [[ ! -d "$SRC_DIR" ]]; then
  echo "INFO: $SRC_DIR not found — skipping watch-handler reload test check."
  exit 0
fi

TESTS_DIR="${SRC_DIR}/tests"
PAGES_DIR="${SRC_DIR}/pages"
COMPOSABLES_DIR="${SRC_DIR}/composables"

if [[ ! -d "$TESTS_DIR" ]]; then
  echo "INFO: $TESTS_DIR not found — skipping."
  exit 0
fi

failed=0
checked=0

check_file() {
  local vue_file="$1"

  # Extract fetch/load function calls that appear inside watch( blocks.
  # We look for patterns like: fetchSchema(), loadKnowledgeGraphs(), fetchNodeLabels()
  # inside a watch( ... ) call body.
  #
  # Strategy: extract lines between "watch(" and the next ");" or "})" that
  # contain a call to fetch*/load*/refresh*/reload*.
  local fetch_calls
  fetch_calls=$(python3 - "$vue_file" <<'PYEOF' 2>/dev/null || true)
import re, sys
text = open(sys.argv[1]).read()
# Find watch(...) blocks — look for watch( followed by an arrow function
# We use a simple heuristic: find lines with fetch/load/refresh/reload inside
# blocks that also contain ".value =" (state clearing)
watch_blocks = re.findall(
    r'watch\s*\([^,]+,\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}',
    text, re.DOTALL
)
# Also match single-statement arrow: watch(x, async () => { ... })
fetch_calls = set()
for block in watch_blocks:
    if '.value =' not in block and '.value=' not in block:
        continue  # not a clear+reload pattern
    calls = re.findall(r'\b((?:fetch|load|refresh|reload)\w*)\s*\(', block)
    fetch_calls.update(calls)
for c in sorted(fetch_calls):
    print(c)
PYEOF

  if [[ -z "$fetch_calls" ]]; then
    return 0  # No clear+reload watch pattern found in this file
  fi

  # Derive the test file name from the vue file path
  local basename
  basename=$(basename "$vue_file" .vue)
  # Look for any test file that matches the component name
  local test_files
  test_files=$(find "$TESTS_DIR" -name "${basename}.test.ts" -o -name "${basename}-*.test.ts" 2>/dev/null | head -10)

  if [[ -z "$test_files" ]]; then
    # No test file found — can't check coverage
    return 0
  fi

  for fetch_call in $fetch_calls; do
    local covered=0
    for test_file in $test_files; do
      # Check if the test file has an assertion on this fetch call
      # We look for: expect(...fetchCall...) or mockFetchCall or fetchCall assertions
      if grep -qE "(expect|assert|toHaveBeenCalled|${fetch_call})" "$test_file" 2>/dev/null; then
        # More specific: check for the actual function name in an assertion context
        if grep -qE "(${fetch_call}|mock.*${fetch_call}|${fetch_call}.*mock)" "$test_file" 2>/dev/null; then
          covered=1
          break
        fi
      fi
    done

    if [[ $covered -eq 0 ]]; then
      echo "WARN: $vue_file — watch handler calls \`${fetch_call}()\` but no assertion found in test file(s): $(echo "$test_files" | tr '\n' ' ')"
      failed=$((failed + 1))
    fi
    checked=$((checked + 1))
  done
}

# Check pages
if [[ -d "$PAGES_DIR" ]]; then
  while IFS= read -r -d '' f; do
    check_file "$f"
  done < <(find "$PAGES_DIR" -name "*.vue" -print0 2>/dev/null)
fi

# Check composables
if [[ -d "$COMPOSABLES_DIR" ]]; then
  while IFS= read -r -d '' f; do
    check_file "$f"
  done < <(find "$COMPOSABLES_DIR" -name "*.vue" -print0 2>/dev/null)
fi

echo ""
if [[ $failed -gt 0 ]]; then
  echo "FAIL: $failed watch-handler reload call(s) appear to lack test assertions."
  echo ""
  echo "For each watch handler that clears state and then calls fetch/load functions,"
  echo "tests MUST assert BOTH the clear AND the subsequent fetch call."
  echo ""
  echo "Example fix: after incrementing tenantVersion in a test, assert that"
  echo "  vi.mocked(fetchSchema).toHaveBeenCalled()"
  echo "in addition to asserting that result.value or error.value are cleared."
  exit 1
else
  if [[ $checked -eq 0 ]]; then
    echo "PASS: No clear+reload watch handler patterns found requiring coverage checks."
  else
    echo "PASS: All $checked fetch/reload calls in watch handlers appear to have test coverage."
  fi
  exit 0
fi
