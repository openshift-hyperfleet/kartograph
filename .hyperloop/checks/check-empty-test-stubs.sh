#!/usr/bin/env bash
# check-empty-test-stubs.sh
#
# Detects test functions whose body consists ONLY of docstrings, `pass`,
# and/or ellipsis (`...`). These are empty placeholders that pass trivially
# and provide zero coverage — they are the most dangerous form of stub
# because pytest reports them as PASSING while testing nothing.
#
# Pattern caught (exact task-031 failure mode):
#
#   async def test_normalized_ulid_used_in_spicedb_subject(self, ...) -> None:
#       """Full-flow: lowercase header is normalized before SpiceDB."""
#       pass    ← trivially passes, no assertion, no test body at all
#
# NOT caught (functions with real statements, even if assertions are indirect):
#
#   def test_archon_rule(self):
#       archrule("x").match("y").should_not_import("z").check("pkg")
#
#   def test_setup_then_assert(self):
#       result = call_service()
#       assert result.status == "ok"
#
# Excluded: @pytest.fixture-decorated functions (named test_* by convention).
#
# Usage:
#   ./check-empty-test-stubs.sh [test_dir]
#
# Exit 0  — no empty test stubs found.
# Exit 1  — one or more empty test stubs detected.

set -euo pipefail

TEST_DIR="${1:-src/api/tests}"

echo "=== Scanning for empty test stubs (docstring/pass-only test functions) ==="

python3 - "$TEST_DIR" <<'PYEOF'
import ast
import os
import sys


def is_fixture(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True if the function is decorated with @pytest.fixture."""
    for decorator in func_node.decorator_list:
        # @pytest.fixture
        if isinstance(decorator, ast.Attribute) and decorator.attr == "fixture":
            return True
        # @fixture  (imported directly)
        if isinstance(decorator, ast.Name) and decorator.id == "fixture":
            return True
        # @pytest.fixture(scope=...) — Call wrapping the attribute
        if isinstance(decorator, ast.Call):
            f = decorator.func
            if isinstance(f, ast.Attribute) and f.attr == "fixture":
                return True
            if isinstance(f, ast.Name) and f.id == "fixture":
                return True
    return False


def is_stub_body(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """
    Return True if the function body contains ONLY docstrings, pass
    statements, and/or ellipsis — i.e., the function does nothing at all.

    A function with ANY real statement (assignment, expression call, return,
    assert, with, for, if, etc.) is NOT a stub, regardless of whether it
    contains explicit assert statements.
    """
    for stmt in func_node.body:
        # Docstring: Expr(value=Constant(str))
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            if isinstance(stmt.value.value, (str, type(...))):
                continue  # docstring or ellipsis — still a stub
        # pass statement
        if isinstance(stmt, ast.Pass):
            continue
        # Any other statement (assignment, call, assert, return, with, for…)
        # means the function has a real body — NOT a stub.
        return False
    return True


def check_file(path: str) -> list[tuple[str, int, str]]:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        source = fh.read()

    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        print(f"  WARNING: could not parse {path}: {exc}", file=sys.stderr)
        return []

    stubs: list[tuple[str, int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        if is_fixture(node):
            continue
        if is_stub_body(node):
            stubs.append((path, node.lineno, node.name))

    return stubs


test_dir = sys.argv[1]
all_stubs: list[tuple[str, int, str]] = []

for root, dirs, files in os.walk(test_dir):
    dirs[:] = [
        d for d in dirs
        if d not in (".venv", "__pycache__", ".git", "node_modules")
    ]
    for fname in files:
        if not fname.endswith(".py"):
            continue
        if not (fname.startswith("test_") or fname.endswith("_test.py")):
            continue
        path = os.path.join(root, fname)
        all_stubs.extend(check_file(path))

if all_stubs:
    print(f"\nFAIL: Found {len(all_stubs)} empty test stub(s):\n")
    for path, lineno, name in all_stubs:
        print(f"  {path}:{lineno}: {name}")
    print()
    print("These functions have a body consisting only of docstrings and/or `pass`.")
    print("They pass trivially and provide zero coverage guarantee.")
    print()
    print("Fill in the test body. At minimum add one of:")
    print("  - an `assert` statement")
    print("  - a mock assertion call (e.g. mock.assert_called_once_with(...))")
    print("  - a pytest.raises() or pytest.warns() context manager")
    print("  - a domain/service call whose result is then asserted")
    sys.exit(1)
else:
    print("PASS: No empty test stubs found.")
    sys.exit(0)
PYEOF
