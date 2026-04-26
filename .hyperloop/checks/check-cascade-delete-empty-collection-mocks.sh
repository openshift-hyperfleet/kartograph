#!/usr/bin/env bash
# check-cascade-delete-empty-collection-mocks.sh
#
# Detects cascade-delete test classes where every mock of a `list_by_*` (or
# similarly named collection-fetch) method on a specific mock object always
# returns an empty list — meaning the deletion loop body is never tested.
#
# WHY THIS MATTERS
# ----------------
# When a service delete method contains:
#
#   groups = await self._group_repository.list_by_tenant(tenant_id)
#   for group in groups:                     # loop body
#       group.mark_for_deletion()
#       await self._group_repository.delete(group)
#
# A test that mocks `mock_group_repo.list_by_tenant = AsyncMock(return_value=[])`
# exercises ONLY the zero-item path. The loop body is never entered, so the
# delete call inside is never executed and the SHALL requirement has no test
# coverage.
#
# This is the failure pattern from task-032 (round 18): every TestDeleteTenant
# test used `mock_group_repo.list_by_tenant = AsyncMock(return_value=[])` while
# nearby tests for OTHER repositories (workspaces, api_keys) had non-empty
# returns — which a naive context-window check falsely accepted as full cascade
# coverage, hiding the group loop body as completely untested across all 9 tests.
#
# WHAT IS CHECKED
# ---------------
# For every test file containing a `class TestDelete*` definition, only the
# TestDelete* class body is scanned.
#
# For each specific `<mock_object>.<method>` pair that appears with
# `return_value=[]` anywhere in the class body, the check asks:
#
#   Does the SAME `<mock_object>.<method>` pair appear with a NON-empty
#   return value in the same class body?
#
# "Non-empty" means:
#   a) Same-line: `mock_obj.method = AsyncMock(return_value=<non-[]>)`
#      where <non-[]> is anything other than `[]`.
#   b) Multi-line: the method line has no return_value=, and the immediately
#      next line contains `return_value=<non-[]>`.
#
# CRITICALLY: non-empty detection is scoped to the SAME pair's AsyncMock call.
# Other mocks on nearby lines (e.g., mock_api_key_repo.list = AsyncMock(...))
# do NOT count as non-empty coverage for a different mock object.
#
# TRACKED METHOD PATTERNS
# -----------------------
#   list_by_*, get_all_by_*, find_by_*
#
# SCOPE
# -----
# Only `TestDelete*` class bodies (top-level classes at column 0).
# Files under .venv/ and __pycache__/ are excluded.
#
# IMPLEMENTATION NOTE
# -------------------
# This script writes each class body to a temp file to avoid SIGPIPE issues
# that arise from `echo "$multiline_var" | grep -q` with `set -o pipefail`.
# When `grep -q` finds a match early it closes its stdin; the prior `echo`
# then gets SIGPIPE (exit 141); with pipefail the pipeline fails — triggering
# any `|| fallback` unexpectedly.
#
# Usage:
#   ./check-cascade-delete-empty-collection-mocks.sh [test_dir]
#
# Exit 0 — all pairs in TestDelete* classes have at least one non-empty mock.
# Exit 1 — one or more pairs are only ever mocked with empty lists.

set -euo pipefail

TEST_DIR="${1:-src/api/tests}"
TMPDIR_WORK=$(mktemp -d)
trap 'rm -rf "$TMPDIR_WORK"' EXIT

echo "=== Checking cascade-delete collection mock coverage in: $TEST_DIR ==="
echo ""

fail=0

# Find test files containing at least one TestDelete* class.
delete_test_files=()
while IFS= read -r -d '' f; do
  if grep -qP '^class TestDelete' "$f" 2>/dev/null; then
    delete_test_files+=("$f")
  fi
done < <(find "$TEST_DIR" \
    -name "test_*.py" \
    -not -path "*/.venv/*" \
    -not -path "*/__pycache__/*" \
    -print0 2>/dev/null || true)

if [[ ${#delete_test_files[@]} -eq 0 ]]; then
  echo "  No TestDelete* classes found under $TEST_DIR. Nothing to scan."
  echo ""
  echo "PASS: No cascade-delete collection mock violations (no TestDelete* classes)."
  exit 0
fi

echo "  Found ${#delete_test_files[@]} file(s) with TestDelete* classes."
echo ""

for test_file in "${delete_test_files[@]}"; do
  file_flagged=0
  total_lines=$(wc -l < "$test_file")

  # Get line numbers for TestDelete* class starts and ALL top-level class lines.
  delete_class_starts=()
  while IFS= read -r n; do delete_class_starts+=("$n"); done \
    < <(grep -nP '^class TestDelete' "$test_file" | cut -d: -f1 || true)

  all_class_starts=()
  while IFS= read -r n; do all_class_starts+=("$n"); done \
    < <(grep -nP '^class ' "$test_file" | cut -d: -f1 || true)

  for class_start in "${delete_class_starts[@]}"; do
    # Find end of this class (next top-level class line, or EOF).
    class_end=$((total_lines + 1))
    for b in "${all_class_starts[@]}"; do
      if [[ "$b" -gt "$class_start" && "$b" -lt "$class_end" ]]; then
        class_end="$b"
      fi
    done
    class_end=$((class_end - 1))

    # Write class body to a temp file to avoid SIGPIPE issues with pipefail.
    class_file="${TMPDIR_WORK}/class_body.py"
    sed -n "${class_start},${class_end}p" "$test_file" > "$class_file" 2>/dev/null || true

    # Extract class name from the first line using bash parameter expansion
    # (avoids SIGPIPE from `echo | head -1 | grep` pipelines with pipefail).
    first_line=$(head -1 "$class_file" 2>/dev/null || true)
    if [[ "$first_line" =~ ^class[[:space:]]+([A-Za-z0-9_]+) ]]; then
      class_name="${BASH_REMATCH[1]}"
    else
      class_name="UnknownDeleteClass"
    fi

    # ------------------------------------------------------------------
    # Find all (mock_object.method) pairs explicitly mocked as empty lists.
    # Matches: mock_obj.list_by_method = AsyncMock(return_value=[])  (single line)
    # ------------------------------------------------------------------
    empty_pairs=()
    while IFS= read -r pair; do
      [[ -n "$pair" ]] && empty_pairs+=("$pair")
    done < <(grep -oP '\b(\w+)\.(list_by_\w+|get_all_by_\w+|find_by_\w+)\s*=\s*AsyncMock\(return_value=\[\]\)' \
               "$class_file" 2>/dev/null \
             | grep -oP '^\w+\.\w+' \
             | sort -u || true)

    [[ ${#empty_pairs[@]} -eq 0 ]] && continue

    for pair in "${empty_pairs[@]}"; do
      mock_obj="${pair%%.*}"    # e.g., mock_group_repo
      method="${pair##*.}"      # e.g., list_by_tenant

      # ------------------------------------------------------------------
      # Strategy A (same line): Does this exact pair appear with a non-empty
      # return_value= on the SAME LINE?
      #
      # Pattern: mock_obj.method ...return_value= NOT followed by []
      # The negative lookahead (?!\[\]) ensures we don't match return_value=[]
      # ------------------------------------------------------------------
      has_nonempty=0

      if grep -qP "\b${mock_obj}\.${method}\b.*return_value=(?!\[\])" "$class_file" 2>/dev/null; then
        has_nonempty=1
      fi

      # ------------------------------------------------------------------
      # Strategy B (multi-line): Lines where this pair appears without
      # return_value= on the same line — check the NEXT line for non-empty.
      # Covers:
      #   mock_obj.method = AsyncMock(
      #       return_value=[group1],   ← next line
      #   )
      # ------------------------------------------------------------------
      if [[ $has_nonempty -eq 0 ]]; then
        multiline_occurrences="${TMPDIR_WORK}/multiline_occ.txt"
        grep -nP "\b${mock_obj}\.${method}\b" "$class_file" 2>/dev/null \
          | grep -vP 'return_value=' \
          | cut -d: -f1 > "$multiline_occurrences" || true

        while IFS= read -r rel_lineno; do
          [[ -z "$rel_lineno" ]] && continue
          next_line=$(sed -n "$((rel_lineno + 1))p" "$class_file" 2>/dev/null || true)
          if echo "$next_line" | grep -qP 'return_value=' 2>/dev/null && \
             ! echo "$next_line" | grep -qP 'return_value=\[\]' 2>/dev/null; then
            has_nonempty=1
            break
          fi
        done < "$multiline_occurrences"
      fi

      if [[ $has_nonempty -eq 0 ]]; then
        if [[ $file_flagged -eq 0 ]]; then
          echo "  [FAIL] $test_file"
          file_flagged=1
          fail=1
        fi
        echo "    Class '${class_name}': '${mock_obj}.${method}' is only ever"
        echo "    mocked with return_value=[] (empty list). The cascade-delete loop"
        echo "    body is never entered — the inner delete() is never tested."
        echo ""
        echo "    All occurrences of '${mock_obj}.${method}' in class body:"
        grep -nP "\b${mock_obj}\.${method}\b" "$class_file" 2>/dev/null \
          | head -8 | awk -v offset="$class_start" -F: \
              '{printf "      line %d:%s\n", $1+offset-1, $2}'
        echo ""
        echo "    FIX: Add at least one test in '${class_name}' that mocks"
        echo "    '${mock_obj}.${method}' with a non-empty list of real domain objects:"
        echo ""
        echo "      obj1 = RealDomainClass(...)  # real aggregate, not MagicMock"
        echo "      ${mock_obj}.${method} = AsyncMock(return_value=[obj1])"
        echo "      # ... call the service delete method ..."
        echo "      ${mock_obj}.delete.assert_called_once_with(obj1)"
        echo ""
      fi
    done
  done
done

echo "=== Summary ==="
if [[ $fail -ne 0 ]]; then
  echo ""
  echo "FAIL: One or more TestDelete* classes have (mock_obj.method) pairs where"
  echo "      every return_value= is an empty list. The cascade-delete loop body"
  echo "      is never exercised — leaving SHALL requirements without coverage."
  echo ""
  echo "Each collection-fetch mock used in a cascade-delete loop MUST have at"
  echo "least one test returning a non-empty list, with an assertion that the"
  echo "inner delete was called for each returned item."
  exit 1
else
  echo ""
  echo "PASS: All (mock_obj.method) pairs in TestDelete* classes have at least"
  echo "      one non-empty-list mock, ensuring loop bodies are exercised."
  exit 0
fi
