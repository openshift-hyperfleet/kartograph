#!/usr/bin/env bash
# check-no-direct-logger-usage.sh
#
# Enforce Domain Oriented Observability (DOO): no direct logger.* or print()
# calls outside of designated observability implementation files.
#
# Per AGENTS.md: "Domain probes should be 100% preferred over logger.* and
# print()." Only *probe*.py files, observability.py implementations, and the
# logging setup module are permitted to call structlog loggers directly.

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
SRC="$ROOT/src/api"

# Scan for module-level logger.<method>() calls in non-observability files.
# Legitimate probe implementations use self._logger.* (attribute form), so
# bare logger.* matches only module-level violations.
LOGGER_VIOLATIONS=$(
  grep -r \
    --include="*.py" \
    --exclude-dir=.venv \
    --exclude-dir=tests \
    --exclude="*probe*.py" \
    --exclude="observability.py" \
    --exclude="logging.py" \
    --exclude="dev_routes.py" \
    -nE "\blogger\.(debug|info|warning|error|critical|exception)\s*\(" \
    "$SRC" 2>/dev/null || true
)

# Scan for bare print() calls (also prohibited by DOO).
PRINT_VIOLATIONS=$(
  grep -r \
    --include="*.py" \
    --exclude-dir=.venv \
    --exclude-dir=tests \
    --exclude="*probe*.py" \
    --exclude="observability.py" \
    -nE "^\s*print\s*\(" \
    "$SRC" 2>/dev/null || true
)

ALL_VIOLATIONS=""
if [ -n "$LOGGER_VIOLATIONS" ]; then
  ALL_VIOLATIONS="$LOGGER_VIOLATIONS"
fi
if [ -n "$PRINT_VIOLATIONS" ]; then
  if [ -n "$ALL_VIOLATIONS" ]; then
    ALL_VIOLATIONS="$ALL_VIOLATIONS"$'\n'"$PRINT_VIOLATIONS"
  else
    ALL_VIOLATIONS="$PRINT_VIOLATIONS"
  fi
fi

if [ -z "$ALL_VIOLATIONS" ]; then
  echo "PASS: No direct logger.* or print() calls found outside observability implementations."
  exit 0
fi

echo "FAIL: Direct logger.* or print() calls detected outside domain observability implementations."
echo ""
echo "Per AGENTS.md DOO mandate: domain probes must be used for ALL observability —"
echo "including error handlers, exception handlers, and presentation-layer helpers."
echo ""
echo "To fix: add a probe method (e.g., probe.server_error_occurred(...)) to the"
echo "relevant probe Protocol and its default implementation, inject the probe via"
echo "FastAPI Depends, and call probe.<method>() instead of logger.*."
echo ""
echo "Violations:"
echo "$ALL_VIOLATIONS"
exit 1
