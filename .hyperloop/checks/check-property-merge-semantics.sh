#!/usr/bin/env bash
# check-property-merge-semantics.sh
#
# Detects SQL property-update statements that use direct assignment instead of
# the jsonb merge operator, which silently drops all existing properties not
# present in the new batch.
#
# BAD (replaces ALL existing properties):
#   SET properties = (s.properties::text)::ag_catalog.agtype
#
# GOOD (merges — preserves existing properties):
#   SET properties = (
#       (t.properties::text)::jsonb || (s.properties::text)::jsonb
#   )::text::ag_catalog.agtype
#
# The check looks at every production Python file that contains "SET properties"
# and verifies that each occurrence is accompanied by "||" within 300 characters
# (covering both single-line and short multi-line SQL strings).
#
# Test files are excluded: docstrings in test files legitimately document
# anti-patterns (to explain what the test guards against) and would produce
# false positives.  Production SQL should only live in source, not tests.
#
# Usage:
#   ./check-property-merge-semantics.sh [src_dir]
#
# Exit 0 — all "SET properties" patterns include the jsonb merge operator.
# Exit 1 — at least one direct-assignment pattern found (merge operator absent).

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
SRC="${1:-${REPO_ROOT}/src/api}"

echo "=== Checking SQL property-update merge semantics ==="

check_file() {
    local file="$1"
    python3 - "$file" <<'PYEOF'
import re
import sys

path = sys.argv[1]
try:
    with open(path) as f:
        content = f.read()
except OSError as e:
    print(f"  ERROR reading {path}: {e}", file=sys.stderr)
    sys.exit(0)  # Don't fail on unreadable files

issues = []

# Find every "SET properties =" with up to 300 chars of following context.
# 300 chars covers both single-line and short multi-line SQL strings.
for m in re.finditer(r'SET\s+properties\s*=\s*.{0,300}', content, re.DOTALL):
    snippet = m.group(0)
    # Allow jsonb merge (||) and jsonb subtraction (- operator for remove-properties).
    # Flag only pure direct-assignment patterns where neither operator is present.
    has_merge = '||' in snippet
    has_subtraction = re.search(r'::\s*jsonb\s*-\s*%s', snippet) is not None
    if not has_merge and not has_subtraction:
        line_no = content[:m.start()].count('\n') + 1
        issues.append((line_no, snippet[:120].replace('\n', '\\n')))

if issues:
    for line_no, snippet in issues:
        print(f"  FAIL {path}:{line_no}: 'SET properties =' without '||' merge operator")
        print(f"       Snippet: {snippet!r}")
    sys.exit(1)
PYEOF
}

FAILED=0
FILES_CHECKED=0

while IFS= read -r file; do
    FILES_CHECKED=$((FILES_CHECKED + 1))
    check_file "$file" || FAILED=1
done < <(grep -rl "SET properties" "$SRC" \
             --include="*.py" \
             --exclude-dir=.venv \
             --exclude-dir=__pycache__ \
             --exclude-dir=tests \
         2>/dev/null || true)

echo ""
if [ "$FAILED" -eq 0 ]; then
    echo "PASS: All SQL property updates use merge semantics (jsonb ||)."
    echo "      Files checked: $FILES_CHECKED"
    exit 0
fi

echo ""
echo "FAIL: One or more SQL property updates use direct assignment."
echo ""
echo "Direct assignment silently REPLACES all existing properties with the new"
echo "batch's values. Any property present in the old node but absent from the"
echo "new batch is permanently lost — a silent data-loss bug that is invisible"
echo "in idempotency tests that use the same data in both calls."
echo ""
echo "Fix: use the jsonb merge operator:"
echo "  SET properties = ("
echo "      (existing_col::text)::jsonb || (new_col::text)::jsonb"
echo "  )::text::ag_catalog.agtype"
exit 1
