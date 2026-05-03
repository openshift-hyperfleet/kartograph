#!/usr/bin/env bash
# check-no-dead-ports.sh
#
# Detects Protocol classes added to */ports/*.py on this branch that are
# not imported in any non-test production file.
#
# WHY THIS MATTERS
# ----------------
# A port (Protocol class) that is only referenced in test fakes is a dead
# abstraction. It:
#   - Provides no runtime boundary enforcement in production.
#   - Misleads readers into thinking the production code path is decoupled
#     via the interface when it is actually calling infrastructure directly.
#   - Accumulates as dead code that future engineers must maintain without
#     understanding its purpose.
#
# WHAT IS CAUGHT
# --------------
# New Protocol classes (added on this branch) in files matching:
#   src/api/*/ports/*.py
# …that have ZERO imports in non-test, non-port production source files.
#
# The check greps for the class name in all *.py files under src/api/,
# excluding:
#   - tests/ directories
#   - .venv/ directories
#   - The port definition file itself
#
# WHAT IS NOT CAUGHT
# ------------------
# - Protocols already on alpha before this branch was cut (only new ones).
# - Infrastructure imports where the protocol is used as a type hint only
#   in *_dependencies.py composition files — those ARE counted as production use.
#
# FIX OPTIONS
# -----------
# When this check fails, either:
#   1. Inject the Protocol into the production code path (e.g., as a FastAPI
#      Depends() parameter so the handler receives the interface at runtime), OR
#   2. Remove the Protocol if the direct infrastructure call is the intended
#      permanent pattern — do not keep dead abstractions "for future use".
#
# Usage:
#   bash .hyperloop/checks/check-no-dead-ports.sh
#
# Exit 0  — all new Protocol classes in ports/ are used in production code.
# Exit 1  — one or more new Protocol classes are never imported in production.

set -euo pipefail

API_DIR="src/api"
MERGE_BASE=$(git merge-base HEAD alpha 2>/dev/null || true)

if [[ -z "$MERGE_BASE" ]]; then
  echo "WARNING: Could not compute merge-base with alpha. Skipping dead-port check."
  exit 0
fi

# Find port files modified/added on this branch.
port_files_changed=$(git diff --name-only "$MERGE_BASE" HEAD \
  -- "${API_DIR}/*/ports/*.py" 2>/dev/null || true)

if [[ -z "$port_files_changed" ]]; then
  echo "OK: No ports/ files modified on this branch — skipping dead-port check."
  exit 0
fi

echo "=== Checking for dead Protocol classes in ports/ ==="
echo ""

FAIL=0
CHECKED=0

while IFS= read -r port_file; do
  [[ -z "$port_file" ]] && continue
  [[ ! -f "$port_file" ]] && continue

  # Extract Protocol class names added (not removed) on this branch.
  # Matches lines of the form:  +class IFooBar(Protocol):
  # (The diff grep catches only added lines; removals are ignored.)
  new_proto_names=$(
    git diff "$MERGE_BASE" HEAD -- "$port_file" \
    | grep -oP '^\+class \K[A-Za-z][A-Za-z0-9_]+(?=\s*\([^)]*Protocol)' \
    2>/dev/null || true
  )

  if [[ -z "$new_proto_names" ]]; then
    continue
  fi

  while IFS= read -r proto_name; do
    [[ -z "$proto_name" ]] && continue
    CHECKED=$((CHECKED + 1))

    # Search for the protocol name in non-test, non-.venv production files,
    # excluding the port definition file itself.
    used_in_prod=$(
      grep -rl --include="*.py" --exclude-dir=.venv --exclude-dir=__pycache__ \
        "$proto_name" "$API_DIR" \
        2>/dev/null \
      | grep -v "tests/" \
      | grep -v ".venv/" \
      | grep -v "__pycache__/" \
      | grep -v "$port_file" \
      || true
    )

    if [[ -z "$used_in_prod" ]]; then
      echo "[FAIL] Protocol '$proto_name' (defined in $port_file)"
      echo "       is not imported in any non-test production file."
      echo ""
      echo "       Fix option A — Wire the port into production:"
      echo "         Inject '$proto_name' as a FastAPI Depends() parameter or"
      echo "         constructor argument so the handler uses the interface at runtime."
      echo ""
      echo "       Fix option B — Remove the dead abstraction:"
      echo "         If direct infrastructure calls are the intended permanent pattern,"
      echo "         delete '$proto_name' and its test fake — do not keep unused ports."
      echo ""
      FAIL=1
    else
      echo "[OK]  '$proto_name' is used in production:"
      echo "$used_in_prod" | sed 's/^/        /'
    fi

  done <<< "$new_proto_names"

done <<< "$port_files_changed"

echo ""
echo "=== Summary ==="
echo "  New Protocol classes checked: $CHECKED"

if [[ $FAIL -eq 1 ]]; then
  echo ""
  echo "FAIL: One or more new Protocol classes are dead abstractions (no production use)."
  echo "      See above for fix options."
  exit 1
else
  echo ""
  echo "PASS: All new Protocol classes in ports/ have at least one production import."
  exit 0
fi
