#!/usr/bin/env bash
# check-cascade-delete-rollback-test.sh
#
# Fails when a service file contains a transactional cascade delete
# (async with session.begin() inside an async def delete method) but
# the integration test suite has no rollback test for that resource.
#
# Root cause this check addresses:
#   task-035: KnowledgeGraphService.delete() correctly wraps the cascade in
#   `async with session.begin()`, but no integration test injected a failure
#   mid-cascade and asserted full rollback. The spec explicitly required
#   "if any step fails, the entire deletion rolls back with no partial state."
#
# HEURISTIC (three conditions, all must be satisfied to flag a violation):
#   1. A file under */application/services/*.py contains `async def delete`
#      followed (anywhere in the file) by `session.begin()` — indicating a
#      transactional cascade delete.
#   2. From the service filename, derive a resource slug
#      (e.g. knowledge_graph_service.py → knowledge_graph).
#   3. Search src/api/tests/integration/ for any function named
#      test_*rollback* that also lives in a file whose path contains the
#      resource slug OR the related integration directory.
#      If none is found, exit 1 for that resource.
#
# Limitations:
#   - File-scope heuristic: a service may have multiple delete methods; the
#     check cannot distinguish which one uses session.begin(). Verifiers must
#     still read the service manually.
#   - Resource-slug matching is simple substring: "knowledge_graph" must
#     appear in the integration test file path or the test function name.
#   - A test named test_rollback_* with no assertions would pass this script;
#     check-weak-test-assertions.sh or check-empty-test-stubs.sh catch that.
#
# Usage:
#   ./check-cascade-delete-rollback-test.sh [source_dir]
#
# Exit 0  — every transactional cascade-delete service has a rollback integration test.
# Exit 1  — one or more services are missing a rollback integration test.

set -euo pipefail

SOURCE_DIR="${1:-src/api}"
INTEGRATION_TEST_DIR="$SOURCE_DIR/tests/integration"

echo "=== Checking rollback integration tests for transactional cascade deletes ==="
echo "    Service dir : $SOURCE_DIR"
echo "    Test dir    : $INTEGRATION_TEST_DIR"
echo ""

violations=0

# Collect all application service files.
all_service_files=$(find "$SOURCE_DIR" \
  -path "*/.venv" -prune -o \
  -path "*/__pycache__" -prune -o \
  -path "*/tests" -prune -o \
  -name "*.py" \
  -path "*/application/services/*" \
  -print 2>/dev/null || true)

if [[ -z "$all_service_files" ]]; then
  echo "INFO: No application service files found under $SOURCE_DIR — nothing to check."
  exit 0
fi

while IFS= read -r service_file; do
  # --- Condition 1: Does the file contain both `async def delete` and `session.begin()`? ---
  if ! grep -q "async def delete" "$service_file" 2>/dev/null; then
    continue
  fi
  if ! grep -q "session\.begin()" "$service_file" 2>/dev/null; then
    continue
  fi

  # --- Condition 2: Derive the resource slug from the filename. ---
  # knowledge_graph_service.py → knowledge_graph
  basename_no_ext=$(basename "$service_file" .py)
  resource_slug="${basename_no_ext%_service}"
  resource_slug="${resource_slug%_svc}"

  # --- Condition 3: Is there a rollback integration test for this resource? ---
  rollback_test_found=0

  if [[ -d "$INTEGRATION_TEST_DIR" ]]; then
    # PRIMARY: Look for a test function named test_*rollback* in any integration
    # test file (not conftest.py) whose path contains the resource slug.
    matching_files=$(find "$INTEGRATION_TEST_DIR" \
      -name "test_*.py" 2>/dev/null \
      | grep -i "$resource_slug" || true)

    for test_file in $matching_files; do
      if grep -qiE "def test_[a-z0-9_]*rollback[a-z0-9_]*\(" "$test_file" 2>/dev/null; then
        rollback_test_found=1
        break
      fi
    done

    # SECONDARY: Search ALL integration test files (not conftest.py) for a test
    # function that BOTH (a) contains a simulated failure (`raise Exception`) and
    # (b) references the resource slug. This catches rollback tests that don't use
    # "rollback" in their name but clearly simulate a mid-transaction failure.
    if [[ $rollback_test_found -eq 0 ]]; then
      while IFS= read -r candidate_file; do
        [[ "$(basename "$candidate_file")" == conftest.py ]] && continue
        if grep -q "raise Exception" "$candidate_file" 2>/dev/null \
           && grep -q "$resource_slug" "$candidate_file" 2>/dev/null; then
          rollback_test_found=1
          break
        fi
      done < <(find "$INTEGRATION_TEST_DIR" -name "test_*.py" 2>/dev/null || true)
    fi
  fi

  if [[ $rollback_test_found -eq 0 ]]; then
    echo "--- MISSING rollback integration test: $service_file ---"
    echo "  Resource slug : $resource_slug"
    echo "  This service has both 'async def delete' and 'session.begin()' —"
    echo "  a transactional cascade delete that MUST be exercised with a rollback test."
    echo ""
    echo "  The spec requirement 'if any step fails, the entire deletion rolls back"
    echo "  with no partial state' is NOT verified by the implementation alone."
    echo "  You MUST add an integration test that:"
    echo "    1. Creates the aggregate and its child records."
    echo "    2. Injects a failure after one step (e.g. raise Exception inside the transaction)."
    echo "    3. Asserts that NEITHER the parent NOR children were deleted (full rollback)."
    echo ""
    echo "  Example (mirrors IAM test_rollback_removes_both_group_and_outbox_entry):"
    echo "    async def test_${resource_slug}_deletion_rollback_on_failure(async_session, ...):"
    echo "        # arrange: create ${resource_slug} with children"
    echo "        try:"
    echo "            async with async_session.begin():"
    echo "                child.mark_for_deletion()"
    echo "                await child_repo.delete(child)"
    echo "                raise Exception('simulated failure before parent delete')"
    echo "        except Exception:"
    echo "            pass"
    echo "        # assert: both parent and children still exist"
    echo "        assert await ${resource_slug}_repo.get_by_id(${resource_slug}.id) is not None"
    echo ""
    echo "  NOTE: Rollback tests MUST be integration tests (not unit tests)."
    echo "        Mock sessions cannot verify SQLAlchemy transaction rollback semantics."
    echo ""
    violations=$((violations + 1))
  else
    echo "✓ $resource_slug: rollback integration test found."
  fi
done <<< "$all_service_files"

echo ""
if [[ $violations -gt 0 ]]; then
  echo "FAIL: $violations service(s) are missing a rollback integration test."
  echo "Add the missing tests before submitting."
  exit 1
else
  echo "PASS: All transactional cascade-delete services have a rollback integration test."
  exit 0
fi
