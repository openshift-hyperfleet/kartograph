#!/usr/bin/env bash
# check-cascade-delete-cleanup.sh
#
# Fails if any APPLICATION-LAYER SERVICE file accesses `.credentials_path` on
# a child entity without also calling `secret_store.delete` in the same file.
#
# Root cause this check addresses:
#   A service's `delete` method cascades to child entities via `repo.delete(child)`.
#   When the child entity has a `credentials_path` attribute, encrypted credentials
#   in the secret store MUST also be deleted — otherwise orphaned credential blobs
#   accumulate. The `KnowledgeGraphService.delete` failure (task-034) demonstrated
#   exactly this: DS rows were removed but encrypted_credentials rows were not.
#
# Scope:
#   Only files under */application/services/*.py are checked. Domain aggregates
#   and repositories legitimately hold or map `credentials_path` without being
#   responsible for secret-store cleanup.
#
# Heuristic (file-level):
#   A service file that references `.credentials_path` (reading the attribute on
#   a child entity) MUST also contain at least one call to `secret_store.delete`
#   or `_secret_store.delete`. Absence of that call means credentials are leaked.
#
# Limitations:
#   This check operates at file scope, not method scope. A file that reads
#   `.credentials_path` only in a non-delete method would be flagged if it has
#   no secret_store.delete call anywhere. Verifiers should still read the specific
#   `delete` method manually; this script catches the worst case.
#
# Usage:
#   ./check-cascade-delete-cleanup.sh [source_dir]
#
# Exit 0  — no credential-leak patterns detected in service files.
# Exit 1  — one or more service files are missing secret_store.delete calls.

set -euo pipefail

SOURCE_DIR="${1:-src/api}"

echo "=== Checking cascade-delete credential cleanup in service files under: $SOURCE_DIR ==="

# Only look at application service files — domain aggregates and repos are excluded.
service_files_with_path=$(grep -rl \
  --include="*.py" \
  --exclude-dir=__pycache__ \
  --exclude-dir=.venv \
  --exclude-dir=tests \
  "\.credentials_path" \
  "$SOURCE_DIR" 2>/dev/null \
  | grep -E "/application/services/[^/]+\.py$" || true)

if [[ -z "$service_files_with_path" ]]; then
  echo "PASS: No application service files access .credentials_path — nothing to check."
  exit 0
fi

found=0

while IFS= read -r file; do
  # Confirm the file also calls secret_store.delete or _secret_store.delete
  if ! grep -qE "(secret_store|_secret_store)\.delete" "$file" 2>/dev/null; then
    echo ""
    echo "--- Missing secret_store.delete in: $file ---"
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

echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: $found service file(s) access .credentials_path without calling secret_store.delete."
  echo ""
  echo "Required fix:"
  echo "  1. Inject ISecretStoreRepository into the service constructor."
  echo "  2. In the delete method, for each child with credentials_path set, call:"
  echo "       await self._secret_store.delete("
  echo "           path=child.credentials_path,"
  echo "           tenant_id=<tenant_id>"
  echo "       )"
  echo "     BEFORE calling repo.delete(child)."
  echo "  3. Add a unit test asserting mock_secret_store.delete is called for"
  echo "     every credential-bearing child."
  exit 1
else
  echo "PASS: All service files that access .credentials_path also call secret_store.delete."
  exit 0
fi
