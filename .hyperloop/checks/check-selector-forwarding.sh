#!/usr/bin/env bash
# check-selector-forwarding.sh
#
# Detects Vue/TS source files where a `selected*` reactive ref is declared
# but its .value never appears inside any async function body that contains
# an `await` call.
#
# This catches the "selector populated but not forwarded to execution"
# anti-pattern:
#
#   // WRONG — selectedKgId drives the badge label but is never passed to the call
#   const selectedKgId = ref<string | null>(null)
#   ...
#   const res = await queryGraph(
#     cypherQuery,
#     Number(timeout.value),
#     Number(maxRows.value),
#     // selectedKgId.value is NOT passed here
#   )
#
# Detection strategy (Python-based for reliable multi-line analysis):
#   1. Parse the <script setup> block of each Vue file (or plain TS files).
#   2. Find all `const selected\w+ = ref` declarations.
#   3. For each such variable, extract async function bodies (functions that
#      contain at least one `await` keyword).
#   4. If `selectedVar.value` never appears inside any such async body,
#      flag the file — the selector is wired to display but not to execution.
#
# Usage:
#   ./check-selector-forwarding.sh [ui_source_dir]
#
# Exit 0  — all selected* refs appear inside async action bodies (or no such refs).
# Exit 1  — one or more files have selected* refs disconnected from await calls.

set -euo pipefail

UI_SOURCE_DIR="${1:-src/dev-ui}"

echo "=== Scanning for selector refs not forwarded to async action bodies ==="

python3 - "$UI_SOURCE_DIR" << 'PYEOF'
import sys
import re
import pathlib

src_dir = sys.argv[1] if len(sys.argv) > 1 else "src/dev-ui"
failures = 0


def extract_script_content(content: str) -> str:
    """Extract the content of <script setup> or <script> from a Vue SFC."""
    m = re.search(r'<script\b[^>]*>(.*?)</script>', content, re.DOTALL)
    return m.group(1) if m else content


def extract_async_function_bodies(script: str) -> list[str]:
    """
    Rough extraction of async function bodies using brace counting.

    Finds lines that open an async function (async function, async () =>,
    async (args) =>) and collects everything until the matching closing brace.
    Returns the raw text of each body.
    """
    lines = script.split('\n')
    bodies = []
    i = 0

    # Pattern to detect the start of an async function
    ASYNC_START = re.compile(
        r'\basync\s+function\b'          # async function foo() {
        r'|\basync\s+\(.*?\)\s*=>'      # async (args) =>
        r'|\basync\s+\w+\s*\('          # async foo(   (method shorthand)
    )

    while i < len(lines):
        line = lines[i]
        if ASYNC_START.search(line):
            # Collect this function body by counting braces
            depth = 0
            body_lines = []
            j = i
            found_open = False
            while j < len(lines):
                body_lines.append(lines[j])
                depth += lines[j].count('{') - lines[j].count('}')
                if lines[j].count('{') > 0:
                    found_open = True
                # Stop once we close the opening brace (depth returns to 0)
                if found_open and depth <= 0:
                    break
                j += 1
            body_text = '\n'.join(body_lines)
            # Only keep it if it actually has an await call
            if re.search(r'\bawait\b', body_text):
                bodies.append(body_text)
            i = j + 1
        else:
            i += 1

    return bodies


def strip_comments(text: str) -> str:
    """Remove single-line (//) and block (/* */) comments."""
    # Remove block comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    # Remove single-line comments
    text = re.sub(r'//[^\n]*', '', text)
    return text


SKIP_DIRS = {'node_modules', '.nuxt', 'dist', '.output', '.cache'}

source_files: list[pathlib.Path] = []
for ext in ('*.vue', '*.ts'):
    for p in pathlib.Path(src_dir).rglob(ext):
        # Skip test files and excluded directories
        if any(skip in p.parts for skip in SKIP_DIRS):
            continue
        if '.test.' in p.name or '.spec.' in p.name:
            continue
        source_files.append(p)

for path in source_files:
    try:
        raw = path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, OSError):
        continue

    # For Vue files, operate on the script block only
    if path.suffix == '.vue':
        script = extract_script_content(raw)
    else:
        script = raw

    # Find declared selectedXxxId refs — these are entity-ID scoping selectors
    # (e.g. selectedKgId, selectedWorkspaceId, selectedNamespaceId).
    # We intentionally exclude generic `selected*` names like `selectedNode`,
    # `selectedItem`, etc. which are UI-interaction state, not API scoping params.
    declared_vars = re.findall(r'const\s+(selected\w+Id)\s*=\s*ref[(<]', script)
    if not declared_vars:
        continue

    # Extract async function bodies that contain await
    async_bodies = extract_async_function_bodies(script)

    for var in declared_vars:
        value_ref = f'{var}.value'
        # Check if var.value appears in any async body (stripped of comments)
        forwarded = any(
            value_ref in strip_comments(body)
            for body in async_bodies
        )

        if not forwarded and async_bodies:
            # Confirm the variable's .value appears somewhere in the file
            # (skip variables that are truly unused everywhere — different issue)
            value_in_file = value_ref in strip_comments(script)
            if not value_in_file:
                # Completely unused — flag more strongly
                print(f"\n--- FAIL: {path} ---")
                print(f"  '{var}' is declared but '{value_ref}' never appears in the script.")
                print(f"  The selector is purely decorative — its state is never read.")
                failures += 1
            else:
                # The value is read (e.g., for a computed display label) but
                # never forwarded to an awaited API call.
                print(f"\n--- FAIL: {path} ---")
                print(f"  '{var}.value' is referenced in the script but never appears")
                print(f"  inside any async function body that contains an `await` call.")
                print(f"  The selector populates and displays correctly but its value is")
                print(f"  not forwarded to the API composable — queries always run unscoped.")
                print(f"")
                print(f"  Required: pass `{var}.value || undefined` as an explicit argument")
                print(f"  to the composable call inside the action handler.")
                failures += 1

print()
if failures:
    print(f"FAIL: {failures} selector-forwarding gap(s) detected.")
    print()
    print("Each flagged 'selected*' ref is bound to a UI element and may be used in")
    print("display logic, but its value is never passed to the awaited API composable.")
    print("This means user selections have no effect on the actual operation — the")
    print("selector is a stub that shows the right UI without changing the behaviour.")
    sys.exit(1)
else:
    print("PASS: All 'selected*' refs appear forwarded to async action bodies.")
    sys.exit(0)

PYEOF
