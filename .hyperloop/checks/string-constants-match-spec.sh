#!/usr/bin/env bash
# Checks that known spec-defined string constants appear in implementation files.
# Exit 0 = pass, non-zero = fail.
set -euo pipefail

SPEC_DIR="${SPEC_DIR:-.hyperloop/specs}"
SRC_DIR="${SRC_DIR:-src/api}"

failures=0

check_constant() {
  local constant="$1"
  local description="$2"
  if ! grep -r --exclude-dir=.venv --include="*.py" -q "\"${constant}\"" "${SRC_DIR}"; then
    echo "FAIL: spec-defined constant '${constant}' (${description}) not found in ${SRC_DIR}" >&2
    failures=$((failures + 1))
  fi
}

# Error categorization constants from querying bounded context spec
check_constant "unknown_error"    "catch-all error type"
check_constant "forbidden"        "read-only violation error type"
check_constant "timeout"          "query timeout error type"
check_constant "execution_error"  "query execution error type"

if [ "$failures" -gt 0 ]; then
  echo "String constant check: $failures failure(s). Ensure implementation matches spec-defined values." >&2
  exit 1
fi

echo "String constant check: all spec-defined constants present."
