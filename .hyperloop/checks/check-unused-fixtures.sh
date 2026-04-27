#!/usr/bin/env bash
# check-unused-fixtures.sh
#
# Detects @pytest.fixture functions whose fixture name is not referenced
# in any function's parameter list within the same file (neither a test_*
# function nor another fixture that feeds into tests).
#
# An unused fixture is always evidence of a missing test: the developer
# scaffolded the fixture in anticipation of a test but never wrote the body.
# This is the root cause of task-019's missing coverage of the KG cascade
# credential deletion scenario — service_with_secret_store was defined but
# never referenced in any function's parameter list in the same file.
#
# Pattern caught:
#
#   @pytest.fixture
#   async def service_with_secret_store(self, ...):   ← defined
#       ...
#
#   # test_delete_cascades_encrypted_credentials never written ← MISSING
#   # service_with_secret_store appears in NO function's parameter list
#
# NOT caught (correct negatives):
#   - Fixtures injected into other fixtures: mock_session → user_service → test_*
#     (mock_session appears in user_service's params, so it is "used")
#   - Fixtures in conftest.py files used by tests in other files
#     (cross-file injection cannot be checked per-file)
#   - Files with no test_ functions at all (conftest.py pattern)
#
# Usage:
#   ./check-unused-fixtures.sh [test_dir]
#
# Exit 0  — all same-file fixtures are referenced in at least one function.
# Exit 1  — one or more fixtures are defined but never referenced.

set -euo pipefail

TEST_DIR="${1:-src/api/tests}"

echo "=== Scanning for @pytest.fixture functions with no same-file consumer ==="
echo "    Directory: $TEST_DIR"
echo ""

python3 - "$TEST_DIR" <<'PYEOF'
import ast
import os
import sys


def _is_autouse(dec: ast.expr) -> bool:
    """Return True if a decorator is @pytest.fixture(autouse=True) or similar."""
    if not isinstance(dec, ast.Call):
        return False
    for kw in dec.keywords:
        if kw.arg == "autouse" and isinstance(kw.value, ast.Constant):
            if kw.value.value:
                return True
    return False


def get_fixture_names(tree: ast.Module) -> set[str]:
    """Return all non-autouse fixture function names in the tree."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            matched = False
            # @pytest.fixture
            if isinstance(dec, ast.Attribute) and dec.attr == "fixture":
                matched = True
            # @fixture (direct import)
            elif isinstance(dec, ast.Name) and dec.id == "fixture":
                matched = True
            # @pytest.fixture(...) or @fixture(...) or @pytest_asyncio.fixture(...)
            elif isinstance(dec, ast.Call):
                f = dec.func
                if isinstance(f, ast.Attribute) and f.attr == "fixture":
                    matched = True
                elif isinstance(f, ast.Name) and f.id == "fixture":
                    matched = True
            if matched:
                # Skip autouse fixtures — they are injected by pytest without
                # appearing in any parameter list; requiring them in param lists
                # would be a false positive.
                if _is_autouse(dec):
                    continue
                names.add(node.name)
    return names


def get_all_consumer_param_names(tree: ast.Module) -> set[str]:
    """
    Return all parameter names from every function in the tree — both test_*
    functions and other fixtures. A fixture is "used" if its name appears in
    ANY function's parameter list (direct use in a test, or injection into
    another fixture that eventually feeds a test).
    """
    params: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for arg in node.args.args + node.args.kwonlyargs:
            params.add(arg.arg)
        if node.args.vararg:
            params.add(node.args.vararg.arg)
    return params


def file_has_tests(tree: ast.Module) -> bool:
    """Return True if the file contains at least one test_ function."""
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        for node in ast.walk(tree)
    )


def check_file(path: str) -> list[tuple[str, str]]:
    """Return (fixture_name, filepath) pairs for unused same-file fixtures."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        source = fh.read()

    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        print(f"  WARNING: could not parse {path}: {exc}", file=sys.stderr)
        return []

    fixture_names = get_fixture_names(tree)
    if not fixture_names:
        return []

    # Skip files with no test functions — these are conftest.py or pure fixture
    # modules where all fixtures are consumed cross-file by design.
    if not file_has_tests(tree):
        return []

    # A fixture is unused if its name never appears as a parameter in ANY
    # function in the same file (test or fixture).
    consumer_params = get_all_consumer_param_names(tree)

    # "self" is always a param name in method contexts — exclude it from
    # consumer_params so we don't accidentally count it as a fixture reference.
    # (No fixture should be named "self".)

    unused: list[tuple[str, str]] = []
    for name in sorted(fixture_names):
        if name not in consumer_params:
            unused.append((name, path))
    return unused


test_dir = sys.argv[1]
all_unused: list[tuple[str, str]] = []

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
        all_unused.extend(check_file(path))

if all_unused:
    print(f"FAIL: Found {len(all_unused)} unused fixture(s):\n")
    for fixture_name, filepath in all_unused:
        print(f"  @pytest.fixture  {fixture_name}  ({filepath})")
    print()
    print("An unused fixture is always evidence of a missing test.")
    print("The fixture was scaffolded in anticipation of a test body that was never written.")
    print("For each unused fixture above, either:")
    print("  a) Write the missing test function that uses the fixture and exercises")
    print("     the spec scenario the fixture was designed for, OR")
    print("  b) Delete the fixture if the spec scenario is formally blocked.")
    print()
    print("Root cause pattern (task-019): service_with_secret_store was defined")
    print("but test_delete_cascades_encrypted_credentials was never written,")
    print("leaving the KG cascade credential deletion code path untested.")
    sys.exit(1)
else:
    print("PASS: All same-file fixtures are referenced in at least one function.")
    sys.exit(0)
PYEOF
