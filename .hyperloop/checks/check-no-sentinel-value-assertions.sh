#!/usr/bin/env bash
# check-no-sentinel-value-assertions.sh
#
# Detects frontend test files that read Vue/TypeScript source as plain text
# (via readFileSync) and then use toContain() to assert against specific
# implementation tokens — sentinel values, initialization literals, or
# comparison operators with string literals.
#
# ROOT CAUSE (task-145 FAIL):
#   task-145-spec-alignment.test.ts read query/index.vue as a string and
#   asserted:
#     expect(QUERY_VUE).toContain("selectedKgId = ref('__all__')")
#     expect(QUERY_VUE).toContain("=== '__all__' ? undefined : id")
#   task-148 subsequently changed the sentinel from '__all__' to '' while
#   preserving identical spec behavior. Four tests broke despite zero
#   behavioral regression.
#
# WHY THIS MATTERS:
#   Source-string assertions that embed specific runtime values (sentinel
#   literals, initialization values, comparison operators with literals) are
#   inherently fragile. Any refactoring that preserves behavior — changing
#   a sentinel, renaming a local variable, reordering expressions — will
#   break these tests even though no spec behavior regressed. This makes
#   them implementation-detail tests, not spec-alignment tests.
#
# PATTERNS DETECTED (in test files that also use readFileSync for .vue files):
#
#   FRAGILE — breaks on any sentinel/implementation refactoring:
#     expect(VUE_SRC).toContain("selectedKgId = ref('__all__')")
#     expect(VUE_SRC).toContain("ref('')")
#     expect(VUE_SRC).toContain("=== '__all__'")
#     expect(VUE_SRC).toContain("!== '__all__'")
#     expect(VUE_SRC).toContain("|| undefined")
#     expect(VUE_SRC).toContain("? undefined :")
#
#   SAFE — structural presence checks that survive refactoring:
#     expect(VUE_SRC).toContain('selectedKgId')    ← ref variable name
#     expect(VUE_SRC).toContain('SelectItem')      ← component name
#     expect(VUE_SRC).toContain('apiFetch')        ← API call name
#     expect(VUE_SRC).toContain('v-model')         ← directive name
#
# SCOPE:
#   Only flagged in test files that ALSO contain readFileSync loading a .vue
#   source file. This prevents false positives in behavioral tests that mount
#   components and assert on DOM output.
#
# Usage:
#   ./check-no-sentinel-value-assertions.sh [test_dir]
#
# Exit 0 — no implementation-token assertions found.
# Exit 1 — one or more fragile source-string assertion patterns detected.

set -euo pipefail

TEST_DIR="${1:-src/dev-ui}"

echo "=== Scanning for implementation-token assertions in source-text tests ==="
echo "    Test directory: $TEST_DIR"
echo ""

python3 - "$TEST_DIR" <<'PYEOF'
"""
Scan TypeScript test files for implementation-token toContain() assertions
inside files that read Vue source as plain text via readFileSync().

A test file "reads Vue source as text" if it contains:
    readFileSync('...path...vue...')  or  readFileSync("...path...vue...")

In such files, the following toContain() patterns are flagged as fragile
implementation-token assertions (they test HOW something is implemented,
not WHAT behavior the spec requires):

    ref('...')       — specific initialization value
    ref("...")
    === '...'        — equality comparison against a string literal
    === "..."
    !== '...'        — inequality comparison against a string literal
    !== "..."
    || undefined     — falsy-gate implementation pattern
    ? undefined :    — ternary returning undefined (falsy-gate variant)

These patterns break when any subsequent task refactors the implementation
detail while preserving identical spec behavior.
"""

import re
import os
import sys

TEST_DIR = sys.argv[1] if len(sys.argv) > 1 else "src/dev-ui"
SKIP_DIRS = {"node_modules", ".nuxt", ".output", "dist", ".venv", "__pycache__"}

# Matches readFileSync loading a .vue source file (not a test file)
READS_VUE_RE = re.compile(
    r"""readFileSync\s*\(\s*['"][^'"]*\.vue['"]""",
    re.IGNORECASE,
)

# Implementation-token patterns inside toContain() argument strings.
# Each entry is (pattern_re, human_label).
IMPL_TOKEN_CHECKS = [
    (
        re.compile(r"""toContain\s*\(\s*['"].*ref\s*\(\s*['"]"""),
        "ref('value') — specific initialization literal inside toContain()",
    ),
    (
        re.compile(r"""toContain\s*\(\s*['"].*===\s*['"]"""),
        "=== 'value' — equality operator with string literal inside toContain()",
    ),
    (
        re.compile(r"""toContain\s*\(\s*['"].*!==\s*['"]"""),
        "!== 'value' — inequality operator with string literal inside toContain()",
    ),
    (
        re.compile(r"""toContain\s*\(\s*['"].*\|\|\s*undefined"""),
        "|| undefined — falsy-gate implementation pattern inside toContain()",
    ),
    (
        re.compile(r"""toContain\s*\(\s*['"].*\?\s*undefined\s*:"""),
        "? undefined : — ternary returning undefined inside toContain()",
    ),
]


def find_test_files(root: str) -> list[str]:
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if re.search(r"\.(test|spec)\.(ts|js)$", fname):
                result.append(os.path.join(dirpath, fname))
    return sorted(result)


def scan_file(path: str) -> list[tuple[int, str, str]]:
    """
    Returns list of (line_no_1based, matched_pattern_label, line_content).
    Only returns findings if the file also reads a .vue source file as text.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
            lines = content.splitlines()
    except OSError:
        return []

    # Only scan files that load Vue source as plain text.
    if not READS_VUE_RE.search(content):
        return []

    findings = []
    for i, line in enumerate(lines):
        for pattern_re, label in IMPL_TOKEN_CHECKS:
            if pattern_re.search(line):
                findings.append((i + 1, label, line.strip()))
                break  # one finding per line is enough

    return findings


def main() -> None:
    if not os.path.isdir(TEST_DIR):
        print(f"Directory not found: {TEST_DIR}")
        print("PASS: Nothing to scan.")
        sys.exit(0)

    files = find_test_files(TEST_DIR)
    if not files:
        print(f"No test files found under {TEST_DIR}.")
        print("PASS: Nothing to scan.")
        sys.exit(0)

    all_findings: list[tuple[str, int, str, str]] = []
    for path in files:
        for lineno, label, line in scan_file(path):
            all_findings.append((path, lineno, label, line))

    if all_findings:
        print(
            f"FAIL: Found {len(all_findings)} implementation-token assertion(s) "
            f"in source-text test files:\n"
        )
        for path, lineno, label, line in all_findings:
            print(f"  {path}:{lineno}")
            print(f"  Pattern : {label}")
            print(f"  Line    : {line}")
            print()

        print("─" * 70)
        print()
        print("WHY THIS IS A PROBLEM")
        print(
            "  These tests read a Vue component as a plain-text string and then"
            " assert\n"
            "  that specific implementation tokens exist (sentinel values, exact\n"
            "  operators, initialization literals). Any subsequent task that\n"
            "  refactors those tokens while preserving identical spec behavior will\n"
            "  break these tests — even though nothing regressed.\n"
            "  (Root cause of task-145 FAIL: four tests asserting '__all__' broke\n"
            "  when task-148 changed the sentinel to '' with identical behavior.)"
        )
        print()
        print("HOW TO FIX")
        print(
            "  Replace implementation-token assertions with structural or behavioral"
            " assertions:"
        )
        print()
        print("  FRAGILE (breaks on sentinel refactoring):")
        print("    expect(QUERY_VUE).toContain(\"selectedKgId = ref('__all__')\")")
        print("    expect(QUERY_VUE).toContain(\"=== '__all__'\")")
        print()
        print("  SAFE structural alternative (survives any sentinel refactoring):")
        print("    expect(QUERY_VUE).toContain('selectedKgId')  // ref NAME, not value")
        print("    expect(QUERY_VUE).toContain('SelectItem')    // component name")
        print()
        print("  BETTER behavioral alternative (mount and assert DOM output):")
        print("    const wrapper = mount(QueryPage)")
        print("    const selector = wrapper.find('[data-testid=\"kg-selector\"]')")
        print("    expect(selector.exists()).toBe(true)")
        print(
            "    // Test WHAT the component does (shows all-KG option), not HOW"
            " (which sentinel)"
        )
        sys.exit(1)
    else:
        print("PASS: No implementation-token assertions found in source-text test files.")
        sys.exit(0)


main()
PYEOF
