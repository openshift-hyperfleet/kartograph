#!/usr/bin/env bash
# check-cascade-delete-rollback-test.sh
#
# Fails when a service file contains a transactional cascade delete
# (async with session.begin() inside an async def delete method) but
# the integration test suite has no rollback test for that resource.
#
# Root cause this check addresses:
#   task-035 (initial): KnowledgeGraphService.delete() correctly wraps the cascade in
#   `async with session.begin()`, but no integration test injected a failure
#   mid-cascade and asserted full rollback. The spec explicitly required
#   "if any step fails, the entire deletion rolls back with no partial state."
#
#   task-035 (verifier finding): A rollback integration test existed but it
#   exercised only the repository layer (TestCascadeDeleteRollback injected
#   failure directly in the repo, bypassing KnowledgeGraphService). The spec's
#   atomicity guarantee applies to the FULL service.delete() operation — only a
#   test that calls Service.delete() with a real session can prove the service's
#   transaction boundary (async with session.begin()) rolls back correctly.
#
# ENHANCED CHECK (Condition 4):
#   After confirming any rollback integration test exists, verify it is at the
#   SERVICE level. A service-level rollback test must:
#     (a) have "service" in its file path, OR
#     (b) reference the Service class (e.g., KnowledgeGraphService) in the file.
#   If only a repo-level rollback test is found, the check FAILs with a PARTIAL
#   verdict explaining the gap.
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
    echo "    1. Instantiates the Service class with a real AsyncSession."
    echo "    2. Calls service.delete(...) with a dependency that raises mid-cascade."
    echo "    3. Asserts that NEITHER the parent NOR children were deleted (full rollback)."
    echo ""
    echo "  NOTE: Rollback tests MUST be integration tests (not unit tests)."
    echo "        Mock sessions cannot verify SQLAlchemy transaction rollback semantics."
    echo ""
    violations=$((violations + 1))
  else
    # --- Condition 4: Is the rollback test at the SERVICE layer? ---
    #
    # A repo-level rollback test (which injects failure directly in the repository,
    # bypassing the service) does NOT prove the service's transaction boundary rolls
    # back. Only a test that calls Service.delete() with a real session can verify
    # the spec's "entire deletion rolls back" requirement.
    #
    # A test is considered service-level if its integration test file:
    #   (a) has "service" in the file path, OR
    #   (b) references the Service class by name (e.g., KnowledgeGraphService)
    #       or a service fixture (e.g., knowledge_graph_service).

    # Convert snake_case resource slug to PascalCase for class name matching.
    # knowledge_graph → KnowledgeGraph → KnowledgeGraphService
    resource_class=$(echo "$resource_slug" | awk -F'_' \
      '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) substr($i,2); print}' OFS='')
    service_class="${resource_class}Service"
    service_fixture="${resource_slug}_service"

    service_level_found=0

    if [[ -d "$INTEGRATION_TEST_DIR" ]]; then
      while IFS= read -r candidate_file; do
        [[ "$(basename "$candidate_file")" == conftest.py ]] && continue

        # Check if this file has rollback semantics (either by name or raise Exception)
        has_rollback=0
        if grep -qiE "def test_[a-z0-9_]*rollback[a-z0-9_]*\(" "$candidate_file" 2>/dev/null \
           || grep -q "raise Exception" "$candidate_file" 2>/dev/null; then
          has_rollback=1
        fi
        [[ $has_rollback -eq 0 ]] && continue

        # Check if the file is service-level:
        # (a) "service" appears in the file path
        # (b) the file content references the service class or fixture name
        is_service_level=0
        if echo "$candidate_file" | grep -q "service"; then
          is_service_level=1
        elif grep -q "$service_class\|$service_fixture" "$candidate_file" 2>/dev/null; then
          is_service_level=1
        fi

        if [[ $is_service_level -eq 1 ]]; then
          service_level_found=1
          break
        fi
      done < <(find "$INTEGRATION_TEST_DIR" -name "test_*.py" 2>/dev/null || true)
    fi

    if [[ $service_level_found -eq 0 ]]; then
      echo "--- PARTIAL — service-level rollback integration test MISSING: $service_file ---"
      echo "  Resource slug  : $resource_slug"
      echo "  Service class  : $service_class"
      echo "  A rollback integration test exists, but it only exercises the REPOSITORY"
      echo "  layer — it does NOT call ${service_class}.delete() with a real session."
      echo "  The spec's 'entire deletion rolls back' requirement applies to the full"
      echo "  service operation, not just the repository. The service wraps the cascade"
      echo "  in 'async with session.begin()' — only a service-level integration test"
      echo "  can verify this transaction boundary actually rolls back on failure."
      echo ""
      echo "  Add a service-level rollback integration test that:"
      echo "    1. Creates the ${resource_slug} with its child records."
      echo "    2. Instantiates ${service_class} with a real AsyncSession."
      echo "    3. Patches a dependency to raise an exception mid-cascade."
      echo "    4. Calls service.delete(...) and confirms it raises."
      echo "    5. Asserts NEITHER the parent NOR children were deleted."
      echo ""
      echo "  Place the test in a file whose path contains 'service'"
      echo "  (e.g., tests/integration/management/test_${resource_slug}_service.py)."
      echo ""
      violations=$((violations + 1))
    else
      echo "✓ $resource_slug: service-level rollback integration test found."
    fi
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
