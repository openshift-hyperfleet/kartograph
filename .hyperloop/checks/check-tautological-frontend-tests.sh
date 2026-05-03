#!/usr/bin/env bash
# check-tautological-frontend-tests.sh
#
# Detects non-falsifiable (tautological) test cases in TypeScript test files.
# A tautological test is one whose assertions pass trivially because control
# flow or assertion values are determined entirely by hardcoded literals within
# the test body — no production code path can ever make the test fail.
#
# ROOT CAUSE (task-122): Two tests defined local boolean variables, assigned
# them hardcoded values, and asserted on those same variables without involving
# any real production code through a mock boundary.
#
# PATTERNS DETECTED
#
# Pattern 1 — Always-executed branch (hardcoded activation):
#   let hasActiveSyncs = false     ← declared false (conditional intent)
#   hasActiveSyncs = true          ← unconditional hardcoded reassignment
#   if (hasActiveSyncs) {          ← always executes; production code inside
#     startPolling()               ←   is always called regardless of real state
#   }
#   expect(pollingStarted).toBe(true)  ← trivially passes
#
# Pattern 2 — Dead branch (always-false guard):
#   let triggerFailed = true
#   if (!triggerFailed) {   ← always false; block can NEVER execute
#     startPolling()        ← production code path permanently unreachable
#   }
#   expect(pollingStarted).toBe(false)  ← trivially passes
#
# NOT FLAGGED (legitimate tests):
#   let isActive = false
#   isActive = await loadDataSources()   ← driven by a real function call
#   if (isActive) { startPolling() }
#
#   const spy = vi.fn()
#   spy()
#   expect(spy).toHaveBeenCalled()       ← tests real call-through
#
# Usage:
#   ./check-tautological-frontend-tests.sh [test_dir]
#
# Exit 0 — no tautological dead-branch patterns found.
# Exit 1 — one or more tautological patterns detected.

set -euo pipefail

TEST_DIR="${1:-src/dev-ui}"

echo "=== Scanning for tautological (non-falsifiable) test patterns ==="
echo "    Test directory: $TEST_DIR"
echo ""

python3 - "$TEST_DIR" <<'PYEOF'
"""
Scan TypeScript test files for tautological boolean-guard patterns.

For each test file, look for:

  Pattern 1 — Hardcoded activation (always-true branch):
    let <var> = false    (declared as conditional gate)
    <var> = true         (hardcoded literal — never from a real function call)
    if (<var>) { ... }   (block ALWAYS executes regardless of production code)

  Pattern 2 — Dead branch (always-false guard):
    let <var> = true
    if (!<var>) { ... }  (block can NEVER execute)

Both patterns cause tests to pass trivially: the test exercises only its own
inline logic, not the real production code path behind the mock boundary.
"""
import re
import os
import sys

# File patterns for TypeScript test files
TEST_FILE_RE = re.compile(r'\.(test|spec)\.(ts|js)$')
SKIP_DIRS = {'node_modules', '.nuxt', '.output', 'dist', '.venv', '__pycache__'}

# --- Regex builders ---------------------------------------------------------

def make_decl_re() -> re.Pattern:
    return re.compile(r'\blet\s+(\w+)\s*=\s*(true|false)\b')

def make_reassign_literal_re(var: str) -> re.Pattern:
    """Matches: <var> = true  OR  <var> = false  (hardcoded literal)"""
    return re.compile(rf'\b{re.escape(var)}\s*=\s*(true|false)\b')

def make_reassign_fn_re(var: str) -> re.Pattern:
    """Matches: <var> = <non-literal>  (driven by a real function call)"""
    return re.compile(
        rf'\b{re.escape(var)}\s*=\s*(?!true\b)(?!false\b)(\S)'
    )

def make_dead_false_re(var: str) -> re.Pattern:
    """if (!<var>) — dead when var is true"""
    return re.compile(rf'\bif\s*\(\s*!\s*{re.escape(var)}\s*[)&|]')

def make_dead_true_re(var: str) -> re.Pattern:
    """if (<var>) — always executes when var is hardcoded-true"""
    return re.compile(rf'\bif\s*\(\s*{re.escape(var)}\s*[)&|]')

# ---------------------------------------------------------------------------

DECL_RE = make_decl_re()
LOOKAHEAD_LINES = 30


def find_test_files(root: str) -> list[str]:
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if TEST_FILE_RE.search(fname):
                result.append(os.path.join(dirpath, fname))
    return sorted(result)


def scan_file(path: str) -> list[tuple[int, int, str, str]]:
    """
    Returns list of (decl_line_no, branch_line_no, var_name, description).
    Line numbers are 1-based.
    """
    findings = []
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except OSError:
        return findings

    for i, line in enumerate(lines):
        m = DECL_RE.search(line)
        if not m:
            continue

        var = m.group(1)
        declared_val = m.group(2)   # 'true' or 'false' — original declared value
        current_val = declared_val  # tracks effective value as we scan ahead
        activated_by_literal = False  # True if current_val was set by a literal reassign

        reassign_literal_re = make_reassign_literal_re(var)
        reassign_fn_re = make_reassign_fn_re(var)
        dead_false_re = make_dead_false_re(var)
        dead_true_re = make_dead_true_re(var)

        for j in range(i + 1, min(i + LOOKAHEAD_LINES + 1, len(lines))):
            next_line = lines[j]

            # Function-driven (non-literal) reassignment → variable CAN receive
            # a real value from production code. Stop scanning; not tautological.
            if reassign_fn_re.search(next_line):
                if not reassign_literal_re.search(next_line):
                    break  # real function call drives the variable — not tautological

            # Hardcoded literal reassignment — update effective value and note it.
            reassign_m = reassign_literal_re.search(next_line)
            if reassign_m:
                new_val = reassign_m.group(1)
                if new_val != current_val:
                    activated_by_literal = True  # value flipped via hardcoded literal
                current_val = new_val
                continue

            # ── Pattern 2: Dead branch — if (!var) when var is true ───────
            if current_val == 'true' and dead_false_re.search(next_line):
                desc = (
                    f"`let {var}` evaluates to `true` (hardcoded), so "
                    f"`if (!{var})` on line {j + 1} is always false — "
                    f"the block can never execute; production code inside "
                    f"it is unreachable and the test assertion trivially passes"
                )
                findings.append((i + 1, j + 1, var, desc))
                break

            # ── Pattern 1: Always-executed branch ─────────────────────────
            # Only flag if the variable was *declared false* (suggesting it was
            # meant to be a conditional gate) and then flipped to true by a
            # hardcoded literal assignment — not by a real function call.
            if (
                current_val == 'true'
                and declared_val == 'false'
                and activated_by_literal
                and dead_true_re.search(next_line)
            ):
                desc = (
                    f"`let {var}` was declared `false` but set to `true` "
                    f"unconditionally by a hardcoded literal (no function call), "
                    f"so `if ({var})` on line {j + 1} is always true — "
                    f"the block always executes regardless of production code state; "
                    f"the test assertion trivially passes"
                )
                findings.append((i + 1, j + 1, var, desc))
                break

    return findings


def main() -> None:
    test_dir = sys.argv[1] if len(sys.argv) > 1 else 'src/dev-ui'

    if not os.path.isdir(test_dir):
        print(f"Directory not found: {test_dir}")
        print("PASS: Nothing to scan.")
        sys.exit(0)

    files = find_test_files(test_dir)
    if not files:
        print(f"No test files found under {test_dir}.")
        print("PASS: Nothing to scan.")
        sys.exit(0)

    all_findings: list[tuple[str, int, int, str, str]] = []
    for path in files:
        for decl_line, branch_line, var, desc in scan_file(path):
            all_findings.append((path, decl_line, branch_line, var, desc))

    if all_findings:
        print(f"FAIL: Found {len(all_findings)} tautological (non-falsifiable) "
              f"test pattern(s):\n")
        for path, decl_line, branch_line, var, desc in all_findings:
            print(f"  {path}:{decl_line} — variable `{var}`")
            print(f"  {desc}")
            print()
        print("─" * 70)
        print()
        print("WHY THIS IS A PROBLEM")
        print("  These tests pass trivially regardless of whether the production")
        print("  code is correct. A bug in the real polling/composable logic will")
        print("  NOT cause these tests to fail — they test their own inline booleans,")
        print("  not the production code path.")
        print()
        print("HOW TO FIX")
        print("  Replace hardcoded boolean assignments with real mock boundaries:")
        print()
        print("  BAD  (Pattern 1 — always-executed branch):")
        print("    let hasActiveSyncs = false")
        print("    hasActiveSyncs = true              // hardcoded — not from a mock")
        print("    if (hasActiveSyncs) { startPolling() }  // always runs")
        print()
        print("  GOOD (Pattern 1 fix):")
        print("    const mockLoadSources = vi.fn().mockResolvedValueOnce([{ status: 'running' }])")
        print("    const sources = await mockLoadSources()")
        print("    const hasActiveSyncs = sources.some(s => s.status === 'running')")
        print("    if (hasActiveSyncs) { startPolling() }")
        print("    expect(startPolling).toHaveBeenCalledOnce()")
        print()
        print("  BAD  (Pattern 2 — dead branch):")
        print("    let triggerFailed = true")
        print("    if (!triggerFailed) { startPolling() }  // can never run")
        print()
        print("  GOOD (Pattern 2 fix):")
        print("    const startPolling = vi.fn()")
        print("    mockApiFetch.mockRejectedValueOnce(new Error('trigger failed'))")
        print("    await triggerSyncAndStartPolling()")
        print("    expect(startPolling).not.toHaveBeenCalled()")
        print()
        print("  The test must be able to FAIL if the production code is wrong.")
        sys.exit(1)
    else:
        print("PASS: No tautological dead-branch patterns found in test files.")
        sys.exit(0)


main()
PYEOF
