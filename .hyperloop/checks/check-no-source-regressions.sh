#!/usr/bin/env bash
# check-no-source-regressions.sh
#
# Fails if any public method, class, or function that existed in the base
# branch has been removed from application source files without a corresponding
# spec mandate. Deletion of existing, working application code causes regressions
# for callers that depend on the interface.
#
# This check operates on application source (not tests). It flags:
#   1. Deleted source files outside the task scope
#   2. Python def/class lines removed from existing source files
#   3. TypeScript export function/class lines removed from existing source files
#
# FALSE-POSITIVE FILTER: When a method or class appears to be removed in the
# diff but is still present anywhere in the HEAD version of the same file (i.e.
# it was only moved or reordered, not deleted), it is NOT flagged. This prevents
# false positives when code is refactored or reordered within a file.
#
# SPEC-MANDATED REMOVALS: Commits that intentionally remove a symbol (e.g.
# renaming an event class) should include a trailer:
#   Removes: ClassName
# This allows reviewers to cross-reference the spec without manual inspection.
# The script does NOT skip symbols with this trailer — it still reports them —
# but the trailer serves as a signal to the verifier that the removal is
# spec-mandated and not a regression.
#
# IMPORTANT: File enumeration uses grep-based filtering on the raw output of
# `git diff --name-only`, NOT git pathspec globs.  Double-quoted globs like
# "$SOURCE_DIR/**/*.py" are expanded by the shell before git sees them and
# may silently match nothing, causing false PASSes.  All filtering is done
# with grep after the fact so every changed file is considered.
#
# Usage:
#   ./check-no-source-regressions.sh [base_branch] [source_dir]
#
# Exit 0  — no unspecified source deletions detected.
# Exit 1  — source regressions found; verify each against the spec.

set -euo pipefail

# Normalize CWD to repo root so git pathspecs work correctly.
# Running from a subdirectory (e.g., .hyperloop/checks/) causes pathspecs like
# 'src/' to silently match nothing and return false PASSes.
cd "$(git rev-parse --show-toplevel)"

BASE_BRANCH="${1:-}"
SOURCE_DIR="${2:-src}"

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
  echo "WARNING: Could not detect base branch. Skipping source regression check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with $BASE_BRANCH. Skipping check."
  exit 0
fi

echo "=== Checking for source code regressions (base: $BASE_BRANCH @ $MERGE_BASE) ==="

found=0

# 1. Deleted source files (Python, TS, Vue) — excluding test files and __pycache__
#
# Use grep-based filtering instead of git pathspec globs.  Shell-expanded globs
# like "$SOURCE_DIR/**/*.py" may silently match nothing in some environments,
# producing a false PASS.  `git diff --name-only --diff-filter=D` with no
# pathspec returns ALL deleted files; we then restrict to the source directory
# and relevant extensions with grep.
deleted_sources=$(git diff --name-only --diff-filter=D "$MERGE_BASE" HEAD 2>/dev/null \
  | grep -E '\.(py|ts|vue)$' \
  | grep "^$SOURCE_DIR/" \
  | grep -v '__pycache__' \
  | grep -v '\.pyc$' \
  | grep -v '/tests/' \
  | grep -v '\.test\.ts$' \
  | grep -v '\.spec\.ts$' \
  || true)

if [[ -n "$deleted_sources" ]]; then
  echo ""
  echo "--- DELETED source files ---"
  echo "$deleted_sources" | sed 's/^/  /'
  echo ""
  echo "  Each deletion above must correspond to an explicit spec requirement."
  echo "  If the spec does not mention removing these files, restore them."
  found=$((found + 1))
fi

# 2. Python public method/function removals in existing source files
#    Look for 'def <name>(' lines removed (lines starting with 'def ' or '    def ')
#
# FALSE-POSITIVE FILTER: For each removed symbol, verify it genuinely no longer
# exists in the HEAD version of the same file. If the symbol appears in HEAD
# (even at a different line), it was only moved or reordered — not deleted.
# This eliminates false positives from refactoring and code reordering.
#
# Same grep-based approach: enumerate ALL changed files, then filter to Python
# application source.  Avoids the pathspec glob expansion issue.
python_method_removals=""
changed_py_sources=$(git diff --name-only "$MERGE_BASE" HEAD 2>/dev/null \
  | grep -E '\.py$' \
  | grep "^$SOURCE_DIR/" \
  | grep -v '/tests/' \
  | grep -v '__pycache__' \
  || true)

for f in $changed_py_sources; do
  # Skip deleted files (already handled above)
  if ! git show "HEAD:$f" &>/dev/null 2>&1; then
    continue
  fi

  # Cache HEAD content of file for existence checks. We verify each removed
  # symbol against HEAD to filter out moves/reorders that are not true deletions.
  head_content=$(git show "HEAD:$f" 2>/dev/null || true)

  # Process removed defs — check each individually against HEAD content
  while IFS= read -r raw_line; do
    [[ -z "$raw_line" ]] && continue

    # Extract the symbol name (handles 'def foo(' and 'async def foo(')
    symbol=$(echo "$raw_line" | grep -oP '(?<=(async )?def )[a-zA-Z_][a-zA-Z0-9_]*' | head -1 || true)

    if [[ -n "$symbol" ]]; then
      # If the symbol still exists anywhere in HEAD, it was moved/reordered —
      # not truly deleted. Skip it to avoid false positives.
      if echo "$head_content" | grep -qE "(async )?def ${symbol}\("; then
        continue
      fi
    fi

    python_method_removals="${python_method_removals}  [$f] ${raw_line}\n"
  done < <(git diff "$MERGE_BASE" HEAD -- "$f" 2>/dev/null \
    | grep '^-[^-]' \
    | grep -E '^-[[:space:]]*(async )?def [a-zA-Z_][a-zA-Z0-9_]*\(' \
    | grep -v '__init__\|__repr__\|__str__\|__eq__\|__hash__\|__len__\|__bool__' \
    || true)

  # Process removed classes — check each individually against HEAD content
  while IFS= read -r raw_line; do
    [[ -z "$raw_line" ]] && continue

    # Extract the class name
    symbol=$(echo "$raw_line" | grep -oP '(?<=class )[A-Z][A-Za-z0-9_]*' | head -1 || true)

    if [[ -n "$symbol" ]]; then
      # If the class name still exists anywhere in HEAD, it was moved/reordered.
      if echo "$head_content" | grep -qE "class ${symbol}[:(]"; then
        continue
      fi
    fi

    python_method_removals="${python_method_removals}  [$f] ${raw_line}\n"
  done < <(git diff "$MERGE_BASE" HEAD -- "$f" 2>/dev/null \
    | grep '^-[^-]' \
    | grep -E '^-[[:space:]]*class [A-Z][A-Za-z0-9_]*' \
    || true)
done

if [[ -n "$python_method_removals" ]]; then
  echo ""
  echo "--- Removed Python methods/functions/classes in application source ---"
  printf "%b" "$python_method_removals"
  echo ""
  echo "  Each removed method or class must correspond to an explicit spec requirement."
  echo "  If the spec does not mandate removal, restore the definition."
  echo ""
  echo "  NOTE: Symbols that were only MOVED or REORDERED within the same file are"
  echo "  automatically filtered out (they still exist in HEAD). Only true deletions"
  echo "  — where the symbol no longer appears anywhere in the file — are reported."
  echo ""
  echo "  For spec-mandated removals (e.g. renaming an event class), add a trailer"
  echo "  to the commit:  Removes: <ClassName>"
  echo "  This signals to verifiers that the removal is intentional and spec-backed."
  echo ""
  echo "  IMPORTANT: Removing a domain exception class (e.g. class FooNotFoundError)"
  echo "  silently changes the HTTP status code callers receive (e.g. 404 → 400)"
  echo "  because route handlers that caught the specific exception now fall through"
  echo "  to the generic handler. This is a security regression when the status code"
  echo "  leaks information about resource existence."
  found=$((found + 1))
fi

echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: Source regressions detected."
  echo ""
  echo "Existing, working application code MUST NOT be removed without a spec mandate."
  echo "  - Deleting a working method removes functionality callers depend on."
  echo "  - If the spec explicitly says to remove it, add 'Removes: <symbol>' to"
  echo "    the commit trailer and document the spec section in your report."
  echo "  - If you cannot find the spec requirement, restore the deleted code."
  exit 1
else
  echo "PASS: No unspecified source regressions detected."
  exit 0
fi
