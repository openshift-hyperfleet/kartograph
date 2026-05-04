#!/usr/bin/env bash
# check-spec-string-literals.sh
#
# Verify that every spec-required string literal appears in a source file.
#
# Usage:
#   bash .hyperloop/checks/check-spec-string-literals.sh <source_file> "<literal1>" ["<literal2>" ...]
#
# Example (query error types):
#   bash .hyperloop/checks/check-spec-string-literals.sh \
#       src/api/query/application/services.py \
#       "unexpected_error" "forbidden" "timeout" "execution_error"
#
# Exit 0  — all required strings found
# Exit 1  — one or more required strings missing (implementation does not match spec)

set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <source_file> <literal1> [<literal2> ...]" >&2
    exit 1
fi

SOURCE_FILE="$1"
shift
LITERALS=("$@")

if [[ ! -f "$SOURCE_FILE" ]]; then
    echo "FAIL: Source file not found: $SOURCE_FILE" >&2
    exit 1
fi

FAILURES=()

for literal in "${LITERALS[@]}"; do
    if grep -qF "$literal" "$SOURCE_FILE"; then
        echo "PASS: '$literal' found in $SOURCE_FILE"
    else
        echo "FAIL: '$literal' NOT found in $SOURCE_FILE (spec requires this exact string)"
        FAILURES+=("$literal")
    fi
done

if [[ ${#FAILURES[@]} -gt 0 ]]; then
    echo ""
    echo "RESULT: FAIL — ${#FAILURES[@]} spec-required string(s) absent from implementation."
    echo "  Missing: ${FAILURES[*]}"
    echo "  This indicates the implementation uses a different string than the spec requires."
    echo "  Passing tests do NOT clear this failure if tests were written from the implementation."
    exit 1
fi

echo ""
echo "RESULT: PASS — all spec-required strings present in $SOURCE_FILE"
