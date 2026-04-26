#!/usr/bin/env bash
# check-pages-have-tests.sh
#
# Verifies that every Vue page file under pages/ has corresponding test coverage.
# A page with zero test coverage is an unconditional TDD violation — each page
# represents a spec feature that must be verified before implementation.
#
# For each .vue file in pages/:
#   - If filename is index.vue, the domain key is the parent directory name.
#   - Otherwise, the domain key is the filename (without .vue).
# A page is considered covered if its domain key appears in any test file name
# OR in any test file's content (case-insensitive).
#
# Usage:
#   ./check-pages-have-tests.sh [ui_dir]
#
# Exit 0  — all pages have test coverage.
# Exit 1  — one or more pages have zero test coverage.

set -euo pipefail

UI_DIR="${1:-src/dev-ui}"
PAGES_DIR="$UI_DIR/app/pages"
TESTS_DIR="$UI_DIR/app/tests"

if [[ ! -d "$PAGES_DIR" ]]; then
  echo "No pages directory found at $PAGES_DIR. Nothing to check."
  exit 0
fi

if [[ ! -d "$TESTS_DIR" ]]; then
  echo "FAIL: Pages directory exists at $PAGES_DIR but NO test directory found at $TESTS_DIR."
  echo "Create test files in $TESTS_DIR before writing page components."
  exit 1
fi

echo "=== Checking that every page has test coverage ==="
echo "    Pages dir : $PAGES_DIR"
echo "    Tests dir : $TESTS_DIR"
echo ""

failed=0
passed=0

# Find all .vue files under pages/
while IFS= read -r vue_file; do
  filename=$(basename "$vue_file" .vue)
  parent_dir=$(basename "$(dirname "$vue_file")")

  # Domain key: use parent directory name for index.vue, filename otherwise
  if [[ "$filename" == "index" ]]; then
    domain="$parent_dir"
  else
    domain="$filename"
  fi

  # Also try the singular form (strip trailing 's') for pluralized directories
  # e.g., "workspaces" → "workspace", "data-sources" → "data-source"
  domain_singular="${domain%s}"

  coverage_found=false

  # 1. Check if any test file name contains the domain key (substring match)
  if find "$TESTS_DIR" -name "*.test.ts" -o -name "*.test.js" 2>/dev/null \
      | grep -qi "$domain"; then
    coverage_found=true
  fi

  # 2. Check if domain key appears in any test file content (case-insensitive)
  if [[ "$coverage_found" == "false" ]]; then
    if grep -ril "$domain" "$TESTS_DIR" \
        --include="*.test.ts" --include="*.test.js" \
        --exclude-dir=node_modules \
        --exclude-dir=.venv 2>/dev/null | grep -q .; then
      coverage_found=true
    fi
  fi

  # 3. Try singular form if plural domain had no match
  if [[ "$coverage_found" == "false" && "$domain_singular" != "$domain" ]]; then
    if grep -ril "$domain_singular" "$TESTS_DIR" \
        --include="*.test.ts" --include="*.test.js" \
        --exclude-dir=node_modules \
        --exclude-dir=.venv 2>/dev/null | grep -q .; then
      coverage_found=true
    fi
  fi

  if [[ "$coverage_found" == "true" ]]; then
    echo "  PASS: $vue_file  (domain: $domain)"
    passed=$((passed + 1))
  else
    echo "  FAIL: $vue_file  (domain: '$domain' not found in any test file)"
    failed=$((failed + 1))
  fi

done < <(find "$PAGES_DIR" -name "*.vue" 2>/dev/null | sort)

echo ""
echo "Results: $passed passed, $failed failed."
echo ""

if [[ $failed -gt 0 ]]; then
  echo "FAIL: $failed page file(s) have zero test coverage."
  echo ""
  echo "Every page component MUST have a corresponding test file covering all spec"
  echo "scenarios for that page BEFORE the page file is committed. This is a TDD"
  echo "violation. Create test files in $TESTS_DIR whose name includes the page"
  echo "domain (e.g., 'schema.test.ts' for pages/graph/schema.vue)."
  exit 1
else
  echo "PASS: All page files have corresponding test coverage."
  exit 0
fi
