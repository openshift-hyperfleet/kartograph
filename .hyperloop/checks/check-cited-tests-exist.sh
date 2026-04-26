#!/usr/bin/env bash
# check-cited-tests-exist.sh
#
# Verifies that named test functions actually exist in the test suite.
# Verifiers MUST run this before citing any test names in a report.
# A test cited as "covered" that cannot be found by grep is a fabricated
# citation — the most dangerous form of false PASS because it masks real
# defects behind invented evidence.
#
# Root cause: task-035 verifier cited test_delete_rolls_back_on_ds_deletion_failure,
# test_delete_cascades_encrypted_credentials, test_list_all_returns_all_visible_kgs,
# and test_list_all_filters_unauthorized_kgs as "COVERED" when none existed.
#
# Usage:
#   ./check-cited-tests-exist.sh test_name_1 test_name_2 ...
#   ./check-cited-tests-exist.sh                   # reads names from stdin
#
# Exit 0  — all named tests found in test suite.
# Exit 1  — one or more named tests not found.

set -euo pipefail

TEST_DIR="${TEST_DIR:-src/api/tests}"

echo "=== Verifying cited test names exist in test suite ==="
echo "    Scanning: $TEST_DIR"
echo ""

# Collect test names from arguments or stdin
if [[ $# -gt 0 ]]; then
    test_names=("$@")
else
    mapfile -t test_names
fi

if [[ ${#test_names[@]} -eq 0 ]]; then
    echo "Usage: $0 test_name_1 test_name_2 ..."
    echo "       or pipe names from stdin, one per line"
    exit 1
fi

found=0
missing=0

for test_name in "${test_names[@]}"; do
    # Strip leading/trailing whitespace
    test_name="$(echo "$test_name" | tr -d '[:space:]')"
    [[ -z "$test_name" ]] && continue

    # Search for the test function definition in the test directory
    hits=$(grep -rn \
        --include="*.py" \
        --exclude-dir=.venv \
        --exclude-dir=__pycache__ \
        "def ${test_name}[[:space:](]" \
        "$TEST_DIR" 2>/dev/null || true)

    if [[ -n "$hits" ]]; then
        echo "  FOUND:   $test_name"
        echo "           $(echo "$hits" | head -1)"
        found=$((found + 1))
    else
        echo "  MISSING: $test_name"
        echo "           (no matching 'def ${test_name}' in $TEST_DIR)"
        missing=$((missing + 1))
    fi
done

echo ""
if [[ $missing -gt 0 ]]; then
    echo "FAIL: $missing test name(s) not found in $TEST_DIR."
    echo ""
    echo "Do NOT include test names in verification reports unless grep confirms"
    echo "they exist. Citing a non-existent test is worse than an honest gap"
    echo "report: it creates false confidence that requirements are satisfied."
    echo ""
    echo "For each MISSING test above, either:"
    echo "  a) Remove it from the report and record the scenario as PARTIAL, or"
    echo "  b) Find the correct test name via: grep -rn 'def test_' $TEST_DIR | grep <keyword>"
    exit 1
else
    echo "PASS: All $found cited test(s) verified to exist in $TEST_DIR."
    exit 0
fi
