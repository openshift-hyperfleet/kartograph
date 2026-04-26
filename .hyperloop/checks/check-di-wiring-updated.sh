#!/usr/bin/env bash
# check-di-wiring-updated.sh
#
# Fails if a service __init__ signature was changed on this branch but its
# corresponding FastAPI dependency factory (*/dependencies/*.py) was not updated.
#
# WHY: When an application-layer service gains a new constructor parameter,
# unit tests pass because they inject dependencies directly. However, the
# FastAPI factory that builds the service for live requests must ALSO be
# updated — otherwise the parameter silently defaults to None in production
# (the "DI wiring gap" failure pattern observed in task-019: credentials
# cascade was tested but FernetSecretStore was never passed by the factory,
# so orphaned encrypted credentials accumulated in the database).
#
# SCOPE: Only flags cases where:
#   1. A file under src/api/*/application/services/*.py was modified on this branch, AND
#   2. The 'def __init__' line itself changed (indicating a signature change), AND
#   3. A dependency factory file in src/api/*/dependencies/ references the service
#      class by name but was NOT modified on this branch.
#
# FALSE POSITIVES: The check fires whenever the __init__ signature changes —
# including non-dependency parameters (e.g., adding debug: bool = False).
# Inspect the flagged factory file manually and confirm the new parameter is
# either explicitly wired or is a configuration-only flag that should not
# be injected. In either case, touch the factory file with a no-op comment
# to silence the check, and explain in the commit message.
#
# Usage:
#   bash .hyperloop/checks/check-di-wiring-updated.sh
#
# Exit 0  — all modified service constructors have corresponding factory updates
#           (or no service __init__ signatures were changed on this branch).
# Exit 1  — one or more service constructors changed without a factory update.

set -euo pipefail

API_DIR="src/api"
MERGE_BASE=$(git merge-base HEAD alpha 2>/dev/null || true)

if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with alpha. Skipping DI wiring check."
  exit 0
fi

FAIL=0
CHECKED=0

# Find service files modified on this branch
while IFS= read -r service_file; do
  [[ -z "$service_file" ]] && continue
  [[ ! -f "$service_file" ]] && continue

  # Only proceed if the 'def __init__' line itself was changed (new/removed param)
  if ! git diff "$MERGE_BASE" HEAD -- "$service_file" | grep -qE "^\+[^+].*def __init__"; then
    continue
  fi

  CHECKED=$((CHECKED + 1))

  # Extract every class name defined at module level in this file
  class_names=$(grep -oP "^class \K[A-Za-z]+" "$service_file" 2>/dev/null || true)
  [[ -z "$class_names" ]] && continue

  while IFS= read -r class_name; do
    [[ -z "$class_name" ]] && continue

    # Find dependency factory files that instantiate this service class
    dep_files=$(grep -rl --include="*.py" --exclude-dir=.venv \
      "$class_name" "$API_DIR"/*/dependencies/ 2>/dev/null || true)
    [[ -z "$dep_files" ]] && continue

    while IFS= read -r dep_file; do
      [[ -z "$dep_file" ]] && continue

      # Was the dependency factory also modified on this branch?
      if ! git diff --name-only "$MERGE_BASE" HEAD -- "$dep_file" | grep -q .; then
        echo "FAIL: $class_name.__init__ signature changed in:"
        echo "        $service_file"
        echo "      but dependency factory was NOT updated:"
        echo "        $dep_file"
        echo ""
        echo "      When a service gains a new constructor parameter, every factory"
        echo "      that instantiates it must explicitly pass the real implementation."
        echo "      A '| None = None' default is for test injection only — production"
        echo "      code must pass the real object (e.g., FernetSecretStore) so the"
        echo "      feature actually runs in live requests."
        echo ""
        echo "      Reference pattern (data_source.py):"
        echo "        secret_store = FernetSecretStore(session=session, encryption_keys=...)"
        echo "        return DataSourceService(..., secret_store=secret_store)"
        echo ""
        echo "      If the new parameter is NOT a production dependency (e.g., a debug"
        echo "      flag with a safe default), add a no-op comment to $dep_file and"
        echo "      explain in the commit message so this check does not re-fire."
        FAIL=1
      fi
    done <<< "$dep_files"
  done <<< "$class_names"

done < <(git diff --name-only "$MERGE_BASE" HEAD \
  -- "$API_DIR/*/application/services/*.py" 2>/dev/null || true)

if [[ "$CHECKED" -eq 0 ]]; then
  echo "OK: No service __init__ signatures modified on this branch."
  exit 0
elif [[ "$FAIL" -eq 0 ]]; then
  echo "OK: All modified service constructors have corresponding dependency factory updates."
  exit 0
else
  exit 1
fi
