#!/usr/bin/env bash
# check-last-commit-removes-trailers.sh
#
# Checks the MOST RECENT commit on the current branch for undeclared
# Python symbol removals. When a commit removes a class or function
# definition from application source, it must carry a 'Removes: SymbolName'
# trailer to declare the removal intentional.
#
# MOTIVATION:
#   check-no-source-regressions.sh compares the full merge-base..HEAD range,
#   so running it "before" a commit only audits prior commits — it cannot see
#   the staged changes that are about to become the HEAD commit. This script
#   fills that gap by inspecting HEAD (the last committed revision) against
#   its parent, giving implementers immediate feedback after each commit
#   rather than discovering missing trailers at submission time.
#
# WHEN TO RUN:
#   Immediately after every `git commit` that modifies application source files.
#   If the script fails, amend the commit before creating any new commits:
#     git commit --amend   # add: Removes: ClassName, method_name
#
# IMPORTANT: A separate follow-up commit that only adds the Removes: trailer
# does NOT satisfy check-no-source-regressions.sh, because that script
# matches Removes: trailers to removals commit-by-commit. The trailer must
# appear on the SAME commit that introduced the removal.
#
# Usage:
#   bash .hyperloop/checks/check-last-commit-removes-trailers.sh [source_dir]
#
# Exit 0 — no undeclared symbol removals in the last commit.
# Exit 1 — one or more symbol removals are missing Removes: trailers.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

SOURCE_DIR="${1:-src}"

# Require at least one commit to inspect.
if ! git rev-parse HEAD >/dev/null 2>&1; then
  echo "WARNING: No commits found. Skipping check."
  exit 0
fi

# Find the parent of HEAD.
PARENT=$(git log --format="%P" -1 HEAD 2>/dev/null | awk '{print $1}' || true)

if [[ -z "$PARENT" ]]; then
  echo "INFO: HEAD is the initial commit (no parent). Skipping check."
  exit 0
fi

echo "=== Checking last commit for undeclared symbol removals ==="
COMMIT_SHORT=$(git log -1 --format="%h %s" HEAD)
echo "    Commit: $COMMIT_SHORT"
echo ""

# Collect all Removes: trailer values declared on the last commit.
# Supports comma-separated multiples: Removes: FooClass, bar_method
removes_documented=$(git log -1 HEAD \
    --format='%(trailers:key=Removes,valueonly)' 2>/dev/null \
  | tr ',' '\n' \
  | sed 's/^[[:space:]]*//' \
  | sed 's/[[:space:]]*$//' \
  | grep -v '^$' \
  || true)

found=0
documented=0

# Enumerate Python application source files changed in the last commit.
changed_py_sources=$(git diff --name-only "$PARENT" HEAD 2>/dev/null \
  | grep -E '\.py$' \
  | grep "^$SOURCE_DIR/" \
  | grep -v '/tests/' \
  | grep -v '__pycache__' \
  || true)

for f in $changed_py_sources; do
  # Skip entirely deleted files (handled by check-no-source-regressions.sh).
  if ! git show "HEAD:$f" &>/dev/null 2>&1; then
    continue
  fi

  head_content=$(git show "HEAD:$f" 2>/dev/null || true)

  # ── Removed function/method definitions ──────────────────────────────────
  while IFS= read -r raw_line; do
    [[ -z "$raw_line" ]] && continue

    symbol=$(echo "$raw_line" \
      | grep -oP '(?<=(async )?def )[a-zA-Z_][a-zA-Z0-9_]*' \
      | head -1 || true)
    [[ -z "$symbol" ]] && continue

    # Filter: symbol still exists in HEAD → moved/reordered, not deleted.
    if echo "$head_content" | grep -qE "(async )?def ${symbol}\("; then
      continue
    fi

    if [[ -n "$removes_documented" ]] && echo "$removes_documented" | grep -qxF "$symbol"; then
      echo "  OK (documented): removed function '$symbol' in $f"
      documented=$((documented + 1))
    else
      echo "  MISSING 'Removes: $symbol' trailer — removed function '$symbol' in $f"
      found=$((found + 1))
    fi
  done < <(git diff "$PARENT" HEAD -- "$f" 2>/dev/null \
    | grep '^-[^-]' \
    | grep -E '^-[[:space:]]*(async )?def [a-zA-Z_][a-zA-Z0-9_]*\(' \
    | grep -v '__init__\|__repr__\|__str__\|__eq__\|__hash__\|__len__\|__bool__' \
    || true)

  # ── Removed class definitions ─────────────────────────────────────────────
  while IFS= read -r raw_line; do
    [[ -z "$raw_line" ]] && continue

    symbol=$(echo "$raw_line" \
      | grep -oP '(?<=class )[A-Z][A-Za-z0-9_]*' \
      | head -1 || true)
    [[ -z "$symbol" ]] && continue

    # Filter: class still exists in HEAD → moved/reordered, not deleted.
    if echo "$head_content" | grep -qE "class ${symbol}[:(]"; then
      continue
    fi

    if [[ -n "$removes_documented" ]] && echo "$removes_documented" | grep -qxF "$symbol"; then
      echo "  OK (documented): removed class '$symbol' in $f"
      documented=$((documented + 1))
    else
      echo "  MISSING 'Removes: $symbol' trailer — removed class '$symbol' in $f"
      found=$((found + 1))
    fi
  done < <(git diff "$PARENT" HEAD -- "$f" 2>/dev/null \
    | grep '^-[^-]' \
    | grep -E '^-[[:space:]]*class [A-Z][A-Za-z0-9_]*' \
    || true)
done

echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: $found undeclared symbol removal(s) in the last commit."
  echo ""
  echo "For each missing trailer, amend the CURRENT commit:"
  echo "  git commit --amend"
  echo "  # In the commit body, add one line per removed symbol:"
  echo "  # Removes: ClassName"
  echo "  # Removes: method_name"
  echo "  # (or comma-separated: Removes: ClassA, method_b)"
  echo ""
  echo "Do NOT create a follow-up commit to add the trailer — the trailer"
  echo "must be on the SAME commit as the removal, or check-no-source-regressions.sh"
  echo "will still fail when it compares the branch against the spec."
  exit 1
else
  if [[ $documented -gt 0 ]]; then
    echo "PASS: All symbol removals in the last commit have Removes: trailers."
  else
    echo "PASS: No symbol removals detected in the last commit."
  fi
  exit 0
fi
