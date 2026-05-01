#!/usr/bin/env bash
# check-page-dedicated-test-files.sh
#
# Requires that every NEW Vue page added by the current branch has a DEDICATED
# test file whose filename contains the page's domain key.  This is stricter
# than check-pages-have-tests.sh, which accepts any test file whose CONTENT
# mentions the domain key (a content-grep that false-positives when an
# unrelated test references a page in a negative assertion, e.g.
# "schema-browser asserts it does NOT navigate to /graph/mutations").
#
# SCOPE: Only pages ADDED by this branch (git diff-filter=A vs merge-base).
# Pre-existing pages on alpha are out of scope; this check does not enforce
# retroactive fixes.  Use --all to audit the entire pages directory.
#
# For each .vue file in pages/ (new to this branch, or all with --all):
#   - If filename is index.vue and parent_dir is the pages root, domain = "index".
#   - If filename is index.vue otherwise, domain = parent directory name.
#   - Otherwise, domain = filename (without .vue).
# A page is covered if at least one test FILE NAME (not content) contains
# the domain key (case-insensitive substring match).
#
# WHY THIS CHECK:
#   task-053, task-058: pages/graph/mutations.vue existed and was fully
#   implemented, but had zero scenario test coverage.  check-pages-have-tests.sh
#   reported PASS because schema-browser.test.ts referenced /graph/mutations in
#   a negative assertion — "assert schema browser does NOT navigate there".
#   That content reference satisfied the grep but left 8 spec scenarios entirely
#   untested.  A dedicated file (mutations.test.ts) would not have existed and
#   this check would have caught the gap before submission.
#
# COMPLEMENTARY CHECK:
#   check-pages-have-tests.sh — broader, lenient coverage (content grep, all pages)
#   This script — narrower, strict coverage (dedicated file name, new pages only)
#
# Usage:
#   ./check-page-dedicated-test-files.sh [--all] [ui_dir]
#
#   --all    Check ALL pages, not just those new to this branch.
#            Useful for a full audit; not used in the backend suite.
#
# Exit 0  — every new page (or all pages with --all) has a dedicated test file.
# Exit 1  — one or more pages lack a dedicated test file.

set -euo pipefail

ALL_PAGES=false
if [[ "${1:-}" == "--all" ]]; then
  ALL_PAGES=true
  shift
fi

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

# ── Determine which pages to check ────────────────────────────────────────────

if [[ "$ALL_PAGES" == "true" ]]; then
  echo "=== Checking ALL pages for dedicated test files (--all mode) ==="
  mapfile -t TARGET_PAGES < <(find "$PAGES_DIR" -name "*.vue" 2>/dev/null | sort)
else
  # Detect base branch (alpha, main, or master)
  BASE_BRANCH=""
  for candidate in alpha main master; do
    if git show-ref --verify --quiet "refs/heads/$candidate" 2>/dev/null || \
       git show-ref --verify --quiet "refs/remotes/origin/$candidate" 2>/dev/null; then
      BASE_BRANCH="$candidate"
      break
    fi
  done

  if [[ -z "$BASE_BRANCH" ]]; then
    echo "WARNING: Could not detect base branch — checking all pages."
    mapfile -t TARGET_PAGES < <(find "$PAGES_DIR" -name "*.vue" 2>/dev/null | sort)
    ALL_PAGES=true  # treat as all-pages for messaging
  else
    MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
    if [[ -z "$MERGE_BASE" ]]; then
      echo "WARNING: Could not compute merge-base with $BASE_BRANCH — checking all pages."
      mapfile -t TARGET_PAGES < <(find "$PAGES_DIR" -name "*.vue" 2>/dev/null | sort)
      ALL_PAGES=true
    else
      echo "=== Checking NEW pages for dedicated test files (base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="
      echo "    (Run with --all to audit all pages)"
      # Only pages ADDED by this branch vs merge-base
      mapfile -t TARGET_PAGES < <(
        git diff --name-only --diff-filter=A "$MERGE_BASE" HEAD \
          -- "${PAGES_DIR}/*.vue" "${PAGES_DIR}/**/*.vue" 2>/dev/null \
          | sort || true
      )
    fi
  fi
fi

echo "    Pages dir : $PAGES_DIR"
echo "    Tests dir : $TESTS_DIR"
echo ""

if [[ ${#TARGET_PAGES[@]} -eq 0 ]]; then
  echo "PASS: No new page files on this branch — nothing to check."
  exit 0
fi

PAGES_BASENAME=$(basename "$PAGES_DIR")

failed=0
passed=0

for vue_file in "${TARGET_PAGES[@]}"; do
  [[ -z "$vue_file" ]] && continue

  filename=$(basename "$vue_file" .vue)
  parent_dir=$(basename "$(dirname "$vue_file")")

  # Domain key: use parent directory name for index.vue, filename otherwise.
  # Special case: if the parent dir IS the pages root itself (e.g. pages/index.vue),
  # use "index" as the domain so we match index.test.ts rather than "pages.test.ts".
  if [[ "$filename" == "index" ]]; then
    if [[ "$parent_dir" == "$PAGES_BASENAME" ]]; then
      domain="index"
    else
      domain="$parent_dir"
    fi
  else
    domain="$filename"
  fi

  # Also check singular form (strip trailing 's') for pluralised directories
  domain_singular="${domain%s}"

  dedicated_found=false

  # Check if any test FILE NAME contains the domain key (case-insensitive).
  # Deliberately NO content-grep fallback — a reference in an unrelated test
  # body does not constitute dedicated coverage.
  if find "$TESTS_DIR" \( -name "*.test.ts" -o -name "*.test.js" \) 2>/dev/null \
      | grep -qi "$domain"; then
    dedicated_found=true
  fi

  # Try singular form if plural had no match
  if [[ "$dedicated_found" == "false" && "$domain_singular" != "$domain" ]]; then
    if find "$TESTS_DIR" \( -name "*.test.ts" -o -name "*.test.js" \) 2>/dev/null \
        | grep -qi "$domain_singular"; then
      dedicated_found=true
    fi
  fi

  if [[ "$dedicated_found" == "true" ]]; then
    echo "  PASS: $vue_file  (domain: $domain)"
    passed=$((passed + 1))
  else
    echo "  FAIL: $vue_file  (no test file named with '$domain')"
    failed=$((failed + 1))
  fi
done

echo ""
echo "Results: $passed passed, $failed failed."
echo ""

if [[ $failed -gt 0 ]]; then
  echo "FAIL: $failed page(s) lack a dedicated test file."
  echo ""
  echo "Every NEW page component MUST have a test file whose NAME includes the"
  echo "page domain key (e.g., 'mutations.test.ts' for pages/graph/mutations.vue)."
  echo ""
  echo "A reference to the page route inside an UNRELATED test body does not"
  echo "satisfy this requirement — create a dedicated test file that covers all"
  echo "spec scenarios for the page before committing the page component."
  echo ""
  echo "Also run: bash .hyperloop/checks/check-pages-have-tests.sh"
  exit 1
else
  echo "PASS: All $passed new page file(s) have a dedicated test file."
  exit 0
fi
