#!/usr/bin/env bash
# check-cascade-delete-cleanup.sh
#
# Fails if any APPLICATION-LAYER SERVICE file cascades deletion to DataSource
# child entities without also calling secret_store.delete for their credentials.
#
# Root cause this check addresses:
#   A service's `delete` method cascades to child entities via `repo.delete(child)`.
#   When the child entity has a `credentials_path` attribute, encrypted credentials
#   in the secret store MUST also be deleted — otherwise orphaned credential blobs
#   accumulate. The `KnowledgeGraphService.delete` failure (task-019) demonstrated
#   exactly this: DS rows were removed but encrypted_credentials rows were not.
#
# TWO HEURISTICS are applied — both must pass:
#
#   HEURISTIC 1 (direct access):
#     A service file that references `.credentials_path` (reading the attribute on
#     a child entity) MUST also contain at least one call to `secret_store.delete`
#     or `_secret_store.delete`. Absence of that call means credentials are leaked.
#
#   HEURISTIC 2 (indirect cascade):
#     A service file that calls `_ds_repo.delete(` or `_data_source_repository.delete(`
#     is performing (or cascading) a DataSource deletion. Because DataSource always
#     carries `credentials_path`, such a file MUST also contain `secret_store.delete`.
#     This catches the failure pattern where the service NEVER accesses `.credentials_path`
#     because it skipped the cleanup step entirely — making Heuristic 1 silent.
#
# Scope:
#   Only files under */application/services/*.py are checked. Domain aggregates
#   and repositories legitimately hold or map `credentials_path` without being
#   responsible for secret-store cleanup.
#
# Limitations:
#   Both heuristics operate at file scope, not method scope. Verifiers should still
#   read the specific `delete` method manually; this script catches the worst cases.
#
# Usage:
#   ./check-cascade-delete-cleanup.sh [source_dir]
#
# Exit 0  — no credential-leak patterns detected in service files.
# Exit 1  — one or more service files are missing secret_store.delete calls.

set -euo pipefail

SOURCE_DIR="${1:-src/api}"

echo "=== Checking cascade-delete credential cleanup in service files under: $SOURCE_DIR ==="

found=0

# ---------------------------------------------------------------------------
# HEURISTIC 1: Service files that read .credentials_path but skip secret cleanup.
# ---------------------------------------------------------------------------

service_files_with_path=$(grep -rl \
  --include="*.py" \
  --exclude-dir=__pycache__ \
  --exclude-dir=.venv \
  --exclude-dir=tests \
  "\.credentials_path" \
  "$SOURCE_DIR" 2>/dev/null \
  | grep -E "/application/services/[^/]+\.py$" || true)

if [[ -n "$service_files_with_path" ]]; then
  while IFS= read -r file; do
    if ! grep -qE "(secret_store|_secret_store)\.delete" "$file" 2>/dev/null; then
      echo ""
      echo "--- [HEURISTIC 1] Missing secret_store.delete in: $file ---"
      echo "  This service accesses .credentials_path on child entities but never"
      echo "  calls secret_store.delete(...) or _secret_store.delete(...)."
      echo ""
      echo "  For every child entity where credentials_path is set, you MUST call:"
      echo "    await self._secret_store.delete(path=child.credentials_path, tenant_id=...)"
      echo "  BEFORE calling repo.delete(child)."
      echo ""
      echo "  .credentials_path references in this file:"
      grep -n "\.credentials_path" "$file" | sed 's/^/    /'
      found=$((found + 1))
    fi
  done <<< "$service_files_with_path"
fi

# ---------------------------------------------------------------------------
# HEURISTIC 2: Service files that call _ds_repo.delete / _data_source_repository.delete
#              but have NO secret_store.delete anywhere in the file.
#
# WHY: DataSource always carries credentials_path. Any service that deletes
# DataSource objects directly (bypassing DataSourceService) MUST also clean
# up credentials. If the file never references .credentials_path it is
# skipping the cleanup entirely — Heuristic 1 is silent in that case.
# ---------------------------------------------------------------------------

# Patterns for direct DataSource-repo delete calls (covers common naming conventions).
# NOTE: Use \( to match a literal '(' in grep -E patterns; bare '(' opens a group.
DS_REPO_DELETE_PATTERNS=(
  "_ds_repo\.delete\("
  "_data_source_repository\.delete\("
  "data_source_repository\.delete\("
  "ds_repo\.delete\("
)

# Collect all service files first.
all_service_files=$(find "$SOURCE_DIR" \
  -path "*/.venv" -prune -o \
  -path "*/__pycache__" -prune -o \
  -path "*/tests" -prune -o \
  -name "*.py" \
  -path "*/application/services/*" \
  -print 2>/dev/null || true)

if [[ -n "$all_service_files" ]]; then
  while IFS= read -r file; do
    # Check if this service file calls delete on a DataSource repository.
    calls_ds_repo_delete=0
    matched_pattern=""
    for pattern in "${DS_REPO_DELETE_PATTERNS[@]}"; do
      if grep -qE "$pattern" "$file" 2>/dev/null; then
        calls_ds_repo_delete=1
        matched_pattern="$pattern"
        break
      fi
    done

    [[ $calls_ds_repo_delete -eq 0 ]] && continue

    # This file deletes DataSource records. It MUST also call secret_store.delete.
    if ! grep -qE "(secret_store|_secret_store)\.delete" "$file" 2>/dev/null; then
      echo ""
      echo "--- [HEURISTIC 2] DataSource cascade delete without secret cleanup: $file ---"
      echo "  This service calls a DataSource repository delete method (matched: $matched_pattern)"
      echo "  but does NOT call secret_store.delete(...) anywhere in the file."
      echo ""
      echo "  DataSource entities carry credentials_path. Any service that deletes"
      echo "  DataSource records MUST also delete their encrypted credentials BEFORE"
      echo "  removing the database row, or credential blobs are permanently orphaned."
      echo ""
      echo "  Required steps:"
      echo "    1. Inject ISecretStoreRepository into __init__ (| None = None for test compat)."
      echo "    2. In the delete loop, for each ds with credentials_path, call:"
      echo "         if ds.credentials_path:"
      echo "             await self._secret_store.delete("
      echo "                 path=ds.credentials_path,"
      echo "                 tenant_id=<tenant_id>"
      echo "             )"
      echo "    3. Then call repo.delete(ds)."
      echo "    4. Update the DI factory to wire ISecretStoreRepository."
      echo "    5. Add a unit test asserting mock_secret_store.delete is called for"
      echo "       every credential-bearing child."
      echo ""
      echo "  DataSource repo delete calls in this file:"
      grep -nE "_ds_repo\.delete\(|_data_source_repository\.delete\(|data_source_repository\.delete\(|ds_repo\.delete\(" "$file" | sed 's/^/    /'
      found=$((found + 1))
    fi
  done <<< "$all_service_files"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: $found service file(s) cascade DataSource deletions without calling secret_store.delete."
  echo ""
  echo "Both encrypted credential rows AND database rows must be removed."
  echo "Leaving encrypted_credentials rows while deleting data_sources rows"
  echo "creates permanently orphaned credential blobs with no referencing row."
  exit 1
else
  echo "PASS: All service files that delete DataSource records also call secret_store.delete."
  exit 0
fi
