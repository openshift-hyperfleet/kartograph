#!/usr/bin/env bash
# check-domain-events-have-consumers.sh
#
# Fails if any domain event class has no consuming handler anywhere in the
# codebase — i.e., the event is published to the outbox but no handler has
# it in supported_event_types() and no handler file even references its class name.
#
# ROOT CAUSE THIS ADDRESSES:
#   task-013: IngestionEventHandler processed SyncStarted and published
#   JobPackageProduced to the outbox. However, no extraction-context handler
#   existed to consume JobPackageProduced. The CompositeEventHandler raised:
#     ValueError: No handler registered for event type: JobPackageProduced
#   at runtime. The existing check-event-handlers-registered.sh verifies that
#   handler CLASSES are in main.py, but does not verify that every event TYPE
#   flowing through the system has AT LEAST ONE consumer anywhere. This check
#   fills that gap.
#
# HOW IT WORKS:
#   1. Finds all Python class definitions in */domain/events/**/*.py files.
#      These are the canonical domain event classes — the event types that
#      aggregates collect and repositories publish to the outbox.
#   2. For each event class name, searches all handler files (files containing
#      supported_event_types) for any reference to that class name — whether
#      as a string literal in a frozenset return, as an import, or as a dict key.
#   3. Fails if an event class is absent from every handler file, meaning it
#      has zero registered consumers and will raise ValueError at runtime.
#
# IMPORTANT SCOPE:
#   This check detects MISSING CONSUMERS, not missing REGISTRATION.
#   check-event-handlers-registered.sh (the companion check) verifies that
#   handler classes which DO exist are registered in main.py. Run BOTH.
#
# EXEMPTIONS:
#   If an event class is intentionally handled outside the outbox (e.g.,
#   purely internal synchronous events never written to the outbox table),
#   add a comment in the event file:
#     # outbox-exempt: handled synchronously, never written to outbox
#   The check will skip classes in files containing this marker.
#
# Usage:
#   bash .hyperloop/checks/check-domain-events-have-consumers.sh
#
# Exit 0  — every domain event class has at least one handler referencing it,
#           OR no domain event classes were found.
# Exit 1  — one or more domain event classes have no consuming handler.

set -euo pipefail

API_DIR="src/api"

echo "=== Checking that all domain event classes have at least one consumer ==="
echo ""

if [[ ! -d "$API_DIR" ]]; then
  echo "WARNING: $API_DIR not found — skipping domain event consumer check."
  exit 0
fi

# ── Step 1: collect all handler files (files that implement supported_event_types)
# Exclude: tests, .venv, __pycache__, composite.py (the aggregator), ports.py (protocol stubs)
mapfile -t HANDLER_FILES < <(
  grep -rl --include="*.py" \
    --exclude-dir=.venv \
    --exclude-dir=__pycache__ \
    "def supported_event_types" \
    "$API_DIR" 2>/dev/null \
  | grep -v "/tests/" \
  | grep -v "composite\.py" \
  | grep -v "ports\.py" \
  || true
)

if [[ "${#HANDLER_FILES[@]}" -eq 0 ]]; then
  echo "OK: No handler files found — nothing to check."
  exit 0
fi

echo "Handler files found: ${#HANDLER_FILES[@]}"
for f in "${HANDLER_FILES[@]}"; do
  echo "  $f"
done
echo ""

# ── Step 2: build a concatenated view of all handler file contents for fast grepping
HANDLER_CONTENT_TMP=$(mktemp)
trap 'rm -f "$HANDLER_CONTENT_TMP"' EXIT

for hf in "${HANDLER_FILES[@]}"; do
  [[ -f "$hf" ]] && cat "$hf" >> "$HANDLER_CONTENT_TMP"
done

# ── Step 3: collect all domain event class names
#   Search in */domain/events/**/*.py, excluding __init__.py and test files.
FAIL=0
EVENT_COUNT=0
UNCOVERED=()

while IFS= read -r event_file; do
  [[ -z "$event_file" ]] && continue
  [[ ! -f "$event_file" ]] && continue

  # Skip files marked as outbox-exempt
  if grep -q "outbox-exempt" "$event_file" 2>/dev/null; then
    echo "SKIP (outbox-exempt): $event_file"
    continue
  fi

  # Extract top-level class names (lines starting with 'class ')
  classes=$(grep -oP "^class \K[A-Za-z_][A-Za-z0-9_]*" "$event_file" 2>/dev/null || true)
  [[ -z "$classes" ]] && continue

  while IFS= read -r class_name; do
    [[ -z "$class_name" ]] && continue

    # Skip non-event helper classes (snapshots, base classes).
    # Domain event classes typically end with a past-tense verb pattern (Created,
    # Updated, Deleted, Failed, Requested, Produced, Applied, Started, Completed).
    # We warn on classes that don't match but still check them to be safe.

    EVENT_COUNT=$((EVENT_COUNT + 1))

    # Check if the class name appears anywhere in any handler file.
    # This catches: string literals in frozensets, dict keys (imported class name),
    # and import statements referencing the class.
    if grep -q "$class_name" "$HANDLER_CONTENT_TMP" 2>/dev/null; then
      echo "OK: $class_name — referenced in at least one handler file"
      echo "    (source: $event_file)"
    else
      echo ""
      echo "FAIL: $class_name has no consuming handler"
      echo "      Source file:  $event_file"
      echo ""
      echo "      This domain event class is defined but does not appear in ANY"
      echo "      handler file's supported_event_types() coverage. If it is published"
      echo "      to the outbox, the CompositeEventHandler will raise:"
      echo "        ValueError: No handler registered for event type: $class_name"
      echo ""
      echo "      Required action (choose ONE):"
      echo "        A) Implement a handler that processes $class_name events:"
      echo "           - Create a handler class in the appropriate bounded context"
      echo "           - Add '$class_name' to its supported_event_types()"
      echo "           - Register the handler in main.py"
      echo "           - Write tests for the handler"
      echo ""
      echo "        B) If this event is never published to the outbox (internal only):"
      echo "           Add this comment to $event_file:"
      echo "             # outbox-exempt: handled synchronously, never written to outbox"
      echo ""
      echo "        C) If the consuming context is not yet built (cross-task dependency):"
      echo "           File a formal blocker at .hyperloop/blockers/task-NNN-blocker.md"
      echo "           naming $class_name and its blocking dependency."
      echo ""
      UNCOVERED+=("$class_name")
      FAIL=1
    fi
  done <<< "$classes"

done < <(
  find "$API_DIR" -path "*/domain/events/*.py" \
    -not -path "*/.venv/*" \
    -not -path "*/__pycache__/*" \
    -not -path "*/tests/*" \
    -not -name "__init__.py" \
    2>/dev/null \
  | sort
)

echo ""
echo "--- Summary ---"
echo "Domain event classes checked: $EVENT_COUNT"

if [[ "$EVENT_COUNT" -eq 0 ]]; then
  echo "OK: No domain event classes found — nothing to check."
  exit 0
elif [[ "$FAIL" -eq 0 ]]; then
  echo "PASS: All $EVENT_COUNT domain event class(es) have at least one consuming handler."
  exit 0
else
  echo ""
  echo "FAIL: ${#UNCOVERED[@]} domain event class(es) have no consuming handler:"
  for name in "${UNCOVERED[@]}"; do
    echo "  - $name"
  done
  echo ""
  echo "Every event published to the outbox MUST have a registered consumer."
  echo "Publishing without a consumer causes a runtime ValueError in the outbox worker."
  echo "See individual FAIL entries above for remediation steps."
  exit 1
fi
