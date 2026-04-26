#!/usr/bin/env bash
# check-domain-exception-http-mapping.sh
#
# Verifies that business route handler files do not silently swallow custom
# domain or port exceptions via a generic `except Exception` catch-all.
#
# When a service method can raise a custom exception defined in
# `domain/exceptions.py` or `ports/exceptions.py`, the route handler must
# have an explicit `except ExceptionType` clause that maps to the correct
# HTTP status code (e.g. 409 Conflict for duplicate-name errors, 422 for
# validation errors). A bare `except Exception → 500` is not spec-compliant
# for any scenario the spec describes as "rejected with X error".
#
# Scope: only files under */presentation/ paths (bounded-context route
# handlers). Infrastructure files (health checks, dev utilities, FastAPI
# dependency helpers) are excluded — generic catch-alls are intentional
# there.
#
# Algorithm:
#   1. Collect all custom exception class names from exceptions.py files.
#   2. Find route handler files under presentation/ directories.
#   3. For each route file that has `except Exception`:
#      - If it catches none of the known custom exception types, flag it.
#
# Exit 0 — no unguarded exception pass-throughs detected (or no route files).
# Exit 1 — flagged files require manual review and fix.

set -euo pipefail

SRC_DIR="${1:-src/api}"

if [[ ! -d "$SRC_DIR" ]]; then
  echo "INFO: Source directory '$SRC_DIR' not found — skipping check."
  exit 0
fi

# ── 1. Collect custom exception class names from domain/ports exception files ──
CUSTOM_EXCEPTIONS=$(grep -rh \
  --include="exceptions.py" \
  --exclude-dir=".venv" \
  "^class [A-Z][A-Za-z]*" \
  "$SRC_DIR" 2>/dev/null \
  | sed 's/class \([A-Za-z][A-Za-z0-9]*\).*/\1/' \
  | grep -v "^Exception$\|^Error$\|^ValueError$\|^TypeError$\|^RuntimeError$" \
  | sort -u \
  || true)

if [[ -z "$CUSTOM_EXCEPTIONS" ]]; then
  echo "OK: No custom exception classes found in exceptions.py files — nothing to check."
  exit 0
fi

EXCEPTION_COUNT=$(echo "$CUSTOM_EXCEPTIONS" | wc -l | tr -d ' ')
echo "Found $EXCEPTION_COUNT custom exception class(es) across domain/ports layers."

# ── 2. Find business route handler files (presentation layer only) ─────────────
# Restrict to */presentation/* to exclude health routes, dev utilities,
# and FastAPI dependency helpers — those use generic catch-alls intentionally.
ROUTE_FILES=$(find "$SRC_DIR" -path "*/presentation/*" -name "*.py" \
  ! -path "*/.venv/*" \
  ! -path "*/tests/*" \
  2>/dev/null \
  | xargs grep -l "@router\." 2>/dev/null \
  || true)

if [[ -z "$ROUTE_FILES" ]]; then
  echo "OK: No presentation-layer route handler files found in '$SRC_DIR'."
  exit 0
fi

FLAGGED=0

while IFS= read -r route_file; do
  # Only inspect files with a generic except Exception catch-all
  if ! grep -q "except Exception" "$route_file" 2>/dev/null; then
    continue
  fi

  # Check whether ANY known custom exception is explicitly caught
  caught_any=0
  while IFS= read -r exc_class; do
    if grep -q "except ${exc_class}" "$route_file" 2>/dev/null; then
      caught_any=1
      break
    fi
  done <<< "$CUSTOM_EXCEPTIONS"

  if [[ $caught_any -eq 0 ]]; then
    echo ""
    echo "POTENTIAL GAP: $route_file"
    echo "  Contains 'except Exception' but catches none of the known custom"
    echo "  domain/port exception types."
    echo "  Any custom exception raised by a service called from this route will"
    echo "  fall through to the generic handler and return HTTP 500."
    echo ""
    echo "  Action required:"
    echo "    1. For each service call that can raise a custom exception, add an"
    echo "       explicit 'except ExceptionType' clause BEFORE the generic catch."
    echo "    2. Map each exception to the correct HTTP status code:"
    echo "       - Duplicate/conflict errors   → 409 Conflict"
    echo "       - Validation/schedule errors  → 422 Unprocessable Entity"
    echo "       - Not-found errors            → 404 Not Found"
    echo "    3. Write a route-level unit test that mocks the service to raise"
    echo "       each exception type and asserts the resulting HTTP status code."
    FLAGGED=$((FLAGGED + 1))
  fi
done <<< "$ROUTE_FILES"

if [[ $FLAGGED -gt 0 ]]; then
  echo ""
  echo "FAIL: $FLAGGED presentation-layer route file(s) have 'except Exception'"
  echo "with no explicit domain/port exception handling. Spec-defined error"
  echo "scenarios (e.g. 'rejected with a duplicate name error') require explicit"
  echo "HTTP status mapping — not a generic 500 response."
  exit 1
fi

echo "OK: All presentation-layer route files with 'except Exception' also catch"
echo "at least one specific domain/port exception type. Manually confirm every"
echo "raiseable exception has an explicit clause and a companion route-level unit test."
exit 0
