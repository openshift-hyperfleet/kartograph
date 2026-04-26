#!/usr/bin/env bash
# check-no-domain-exception-deletions.sh
#
# Fails if any exception class defined in a ports/exceptions.py or
# domain/exceptions.py file on the base branch has been removed on the
# current branch.
#
# WHY THIS MATTERS:
#   Domain and port exception classes are the typed error vocabulary the
#   application uses to communicate failure reasons to route handlers.
#   When a class like `FooNotFoundError` is deleted:
#     1. The service that raised it is forced to use `ValueError` or a
#        generic exception instead.
#     2. Route handlers that caught `FooNotFoundError → HTTP 404` no longer
#        match, so the exception falls through to the generic handler → HTTP 500
#        or HTTP 400.
#     3. Changing 404 → 400 or 404 → 500 for a "not found" scenario leaks
#        information about resource existence — a security regression.
#   Removing exception classes to avoid fixing a type error or a failing test
#   is NEVER acceptable; the fix is always to restore the class and fix callers.
#
# Usage:
#   ./check-no-domain-exception-deletions.sh [base_branch]
#
# Exit 0 — no domain/port exception classes removed.
# Exit 1 — one or more exception classes were deleted; restore them.

set -euo pipefail

# Normalize CWD to repo root so git pathspecs work correctly.
cd "$(git rev-parse --show-toplevel)"

BASE_BRANCH="${1:-}"
if [[ -z "$BASE_BRANCH" ]]; then
  for candidate in alpha main master; do
    if git show-ref --verify --quiet "refs/heads/$candidate" 2>/dev/null || \
       git show-ref --verify --quiet "refs/remotes/origin/$candidate" 2>/dev/null; then
      BASE_BRANCH="$candidate"
      break
    fi
  done
fi

if [[ -z "$BASE_BRANCH" ]]; then
  echo "WARNING: Could not detect base branch. Skipping domain exception deletion check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping check."
  exit 0
fi

echo "=== Checking for removed domain/port exception classes (base: $BASE_BRANCH @ ${MERGE_BASE:0:8}) ==="

# Collect all ports/exceptions.py and domain/exceptions.py files that were
# modified or deleted on this branch.
CHANGED_EXCEPTION_FILES=$(git diff --name-only "$MERGE_BASE" HEAD -- \
  '*/ports/exceptions.py' \
  '*/domain/exceptions.py' \
  2>/dev/null || true)

found=0
report=""

for f in $CHANGED_EXCEPTION_FILES; do
  # If the file was deleted entirely, report all its classes as removed.
  if ! git show "HEAD:$f" &>/dev/null 2>&1; then
    base_classes=$(git show "${MERGE_BASE}:${f}" 2>/dev/null \
      | grep -E '^[[:space:]]*class [A-Z][A-Za-z0-9_]*' \
      | sed "s|^|  [DELETED FILE: $f] |" \
      || true)
    if [[ -n "$base_classes" ]]; then
      report="${report}\n--- All classes lost — file deleted: $f ---\n${base_classes}\n"
      found=$((found + 1))
    fi
    continue
  fi

  # File still exists — detect individual class removals.
  # NOTE: sed uses '|' as delimiter to avoid ambiguity with '/' in file paths.
  removed=$(git diff "$MERGE_BASE" HEAD -- "$f" 2>/dev/null \
    | grep '^-[^-]' \
    | grep -E '^-[[:space:]]*class [A-Z][A-Za-z0-9_]*' \
    | sed "s|^|  [$f] |" \
    || true)

  if [[ -n "$removed" ]]; then
    report="${report}\n--- Removed exception classes in $f ---\n${removed}\n"
    found=$((found + 1))
  fi
done

echo ""
if [[ $found -gt 0 ]]; then
  printf "%b" "$report"
  echo ""
  echo "FAIL: $found exception file(s) had classes removed."
  echo ""
  echo "Domain and port exception classes MUST NOT be deleted:"
  echo "  - Deleting a typed exception forces callers to use ValueError or a"
  echo "    generic exception, which silently changes the HTTP status code."
  echo "  - A 404 Not Found that becomes 400 Bad Request leaks resource existence"
  echo "    information — this is a security regression."
  echo "  - Deleting an exception to avoid a failing test hides a bug; it does"
  echo "    not fix it. The test failure is a correct signal."
  echo ""
  echo "Fix: restore the deleted classes from '$BASE_BRANCH' and fix the callers:"
  echo "  git show ${MERGE_BASE}:<path/to/exceptions.py> | grep 'class <Name>'"
  echo ""
  echo "If the class was intentionally renamed, add a backwards-compat alias"
  echo "and update all callers in a single atomic commit — do NOT delete the class."
  exit 1
else
  echo "PASS: No domain/port exception classes were removed."
  exit 0
fi
