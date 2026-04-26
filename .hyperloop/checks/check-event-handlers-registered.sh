#!/usr/bin/env bash
# check-event-handlers-registered.sh
#
# Fails if any EventHandler implementation (a class that defines
# supported_event_types()) is not referenced in main.py's outbox worker.
#
# ROOT CAUSE THIS ADDRESSES:
#   task-013: SyncLifecycleHandler and IngestionEventHandler were fully
#   unit-tested but never registered in main.py's CompositeEventHandler.
#   The outbox worker never dispatched events to these handlers in production,
#   meaning status transitions and the ingestion pipeline were completely
#   inoperative at runtime despite 100% unit test coverage.
#
#   The failure mode is silent: unit tests pass, checks pass, but
#   JobPackageProduced events cause the outbox worker to raise:
#     ValueError: No handler registered for event type: JobPackageProduced
#
# HOW IT WORKS:
#   1. Finds all .py files in src/api/ (excluding tests, .venv, composite.py)
#      that define a 'def supported_event_types' method.
#   2. Extracts top-level class names from each such file.
#   3. Verifies each class name appears in main.py.
#   4. Additionally checks that main.py contains at least one handler.register()
#      call (guards against an empty main.py matching trivially).
#
# EXCLUSIONS:
#   - Tests (src/api/tests/)
#   - Virtual environment (.venv/)
#   - The composite aggregator itself (composite.py) — it IS the registry
#   - Files in infrastructure/outbox/ other than concrete handlers
#
# FALSE POSITIVES:
#   If a handler class is intentionally not registered because it is used only
#   in a non-outbox context (e.g., a synchronous in-process handler), add a
#   comment line to main.py:
#     # <ClassName> registered via <other mechanism> — not an outbox handler
#   The check will find the class name in main.py and exit 0.
#
# Usage:
#   bash .hyperloop/checks/check-event-handlers-registered.sh
#
# Exit 0  — all EventHandler implementations are referenced in main.py,
#           OR no EventHandler implementations were found outside composite.py.
# Exit 1  — one or more EventHandler implementations are absent from main.py.

set -euo pipefail

API_DIR="src/api"
MAIN_FILE="$API_DIR/main.py"

if [[ ! -f "$MAIN_FILE" ]]; then
  echo "WARNING: $MAIN_FILE not found — skipping handler registration check."
  exit 0
fi

# Confirm main.py has at least one handler.register() call (sanity guard).
if ! grep -q "\.register(" "$MAIN_FILE"; then
  echo "WARNING: $MAIN_FILE has no .register() calls — outbox worker may be empty."
  echo "         If this is expected (e.g., scaffold phase), this check is advisory."
fi

echo "=== Checking EventHandler registrations in $MAIN_FILE ==="
echo ""

FAIL=0
HANDLER_COUNT=0

# Find all non-test, non-venv Python files that implement supported_event_types.
while IFS= read -r handler_file; do
  [[ -z "$handler_file" ]] && continue

  # Skip tests
  [[ "$handler_file" == *"/tests/"* ]] && continue

  # Skip virtual environment
  [[ "$handler_file" == *"/.venv/"* ]] && continue

  # Skip the composite aggregator itself — it IS the registry
  [[ "$handler_file" == *"/composite.py" ]] && continue

  # Extract all top-level class names from this file (lines starting with 'class ')
  classes=$(grep -oP "^class \K[A-Za-z_][A-Za-z0-9_]*" "$handler_file" 2>/dev/null || true)
  [[ -z "$classes" ]] && continue

  while IFS= read -r class_name; do
    [[ -z "$class_name" ]] && continue

    # Only flag classes whose name ends in Handler — avoids spurious hits from
    # helper classes defined in the same file as a handler.
    if [[ "$class_name" != *Handler ]]; then
      continue
    fi

    HANDLER_COUNT=$((HANDLER_COUNT + 1))

    if grep -q "$class_name" "$MAIN_FILE"; then
      echo "OK: $class_name — referenced in main.py"
      echo "    (source: $handler_file)"
    else
      echo "FAIL: $class_name is not referenced in main.py"
      echo "      Source file: $handler_file"
      echo ""
      echo "      This EventHandler has a supported_event_types() method but is"
      echo "      NOT imported or registered in the outbox worker ($MAIN_FILE)."
      echo "      The outbox worker dispatches events ONLY to registered handlers;"
      echo "      any event type this handler supports will silently go unprocessed"
      echo "      (or raise ValueError: No handler registered for event type: ...)."
      echo ""
      echo "      Required fix:"
      echo "        1. Import $class_name in main.py"
      echo "        2. Instantiate it with its dependencies"
      echo "        3. Call handler.register(<instance>, handler_name=\"<name>\")"
      echo "        4. Add a unit test that exercises the handler via the outbox worker"
      echo "           (not just via the handler class in isolation)"
      echo ""
      FAIL=1
    fi
  done <<< "$classes"

done < <(grep -rl --include="*.py" --exclude-dir=.venv --exclude-dir=__pycache__ "def supported_event_types" "$API_DIR" 2>/dev/null || true)

echo ""

if [[ "$HANDLER_COUNT" -eq 0 ]]; then
  echo "OK: No EventHandler implementations found (outside composite.py)."
  exit 0
elif [[ "$FAIL" -eq 0 ]]; then
  echo "PASS: All $HANDLER_COUNT EventHandler implementation(s) are referenced in main.py."
  exit 0
else
  echo "FAIL: One or more EventHandler implementations are absent from main.py."
  echo "      Handlers with no registration are dead code: their event types are"
  echo "      never dispatched by the outbox worker regardless of unit test coverage."
  exit 1
fi
