#!/usr/bin/env bash
# check-service-route-coverage.sh
#
# Detects application-service CRUD methods that lack corresponding HTTP routes
# in the presentation layer of the same bounded context. A feature is only
# API-complete when the full vertical slice exists: service → route → route tests.
#
# Root cause: task-035 — KnowledgeGraphService.update() and .delete() were
# implemented and service-tested, but no PATCH or DELETE HTTP routes existed.
# The previous verifier reported PASS without checking for routes.
#
# Detection strategy: For each *_service.py in */application/services/, extract
# the names of public async methods that begin with a CRUD verb (create, get,
# list, update, delete). Then inspect all routes.py files in the same bounded
# context's presentation/ directory for the corresponding @router.<verb> decorator.
#
# Mapping:
#   create  → @router.post
#   get     → @router.get
#   list*   → @router.get
#   update  → @router.patch OR @router.put
#   delete  → @router.delete
#
# Note: A single @router.get can satisfy both "get" and "list*" within a context.
# The critical misses are update (PATCH/PUT) and delete (DELETE) — these are the
# verbs most often skipped when an implementer stops at the service layer.
#
# Usage:
#   ./check-service-route-coverage.sh [api_dir]
#
# Exit 0  — all service CRUD methods have corresponding HTTP routes.
# Exit 1  — one or more service CRUD methods lack HTTP routes.

set -euo pipefail

API_DIR="${1:-src/api}"

echo "=== Checking service CRUD → HTTP route coverage ==="
echo "    Scanning: $API_DIR"
echo ""

python3 - "$API_DIR" <<'PYEOF'
import ast
import os
import sys

API_DIR = sys.argv[1]

# CRUD verb → required HTTP router decorator(s)
CRUD_TO_HTTP: dict[str, list[str]] = {
    "create": ["post"],
    "get": ["get"],
    "list": ["get"],
    "update": ["patch", "put"],
    "delete": ["delete"],
}


def extract_public_async_methods(filepath: str) -> list[str]:
    """Return names of public async methods defined in any class in filepath."""
    try:
        with open(filepath, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except (SyntaxError, OSError):
        return []

    methods: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, ast.AsyncFunctionDef) and not item.name.startswith("_"):
                methods.append(item.name)
    return methods


def get_route_verbs_in_dir(presentation_dir: str) -> set[str]:
    """Collect all @router.<verb> decorators found in any routes.py under dir."""
    verbs: set[str] = set()
    if not os.path.isdir(presentation_dir):
        return verbs

    for root, dirs, files in os.walk(presentation_dir):
        dirs[:] = [d for d in dirs if d not in (".venv", "__pycache__", ".git")]
        for fname in files:
            if fname != "routes.py":
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                continue
            for verb in ["get", "post", "patch", "put", "delete"]:
                if f"@router.{verb}" in content:
                    verbs.add(verb)
    return verbs


def crud_prefix(method_name: str) -> str | None:
    """Return the CRUD prefix of a method name, or None if not a CRUD method."""
    for prefix in CRUD_TO_HTTP:
        if method_name == prefix or method_name.startswith(prefix + "_"):
            return prefix
    return None


failures: list[dict] = []

for root, dirs, files in os.walk(API_DIR):
    dirs[:] = [d for d in dirs if d not in (".venv", "__pycache__", ".git", "node_modules")]

    # Only process files matching */application/services/*_service.py
    path_parts = root.replace("\\", "/").split("/")
    if "application" not in path_parts or "services" not in path_parts:
        continue

    for fname in files:
        if not fname.endswith("_service.py"):
            continue

        service_file = os.path.join(root, fname)
        methods = extract_public_async_methods(service_file)
        if not methods:
            continue

        # Infer bounded context: the directory immediately under API_DIR
        rel = os.path.relpath(service_file, API_DIR)
        context = rel.split(os.sep)[0]

        # Find the presentation directory for this context
        presentation_dir = os.path.join(API_DIR, context, "presentation")
        route_verbs = get_route_verbs_in_dir(presentation_dir)

        for method in methods:
            prefix = crud_prefix(method)
            if prefix is None:
                continue

            required_verbs = CRUD_TO_HTTP[prefix]
            if any(v in route_verbs for v in required_verbs):
                continue  # at least one matching HTTP route exists

            verb_display = " or ".join(f"@router.{v}" for v in required_verbs)
            failures.append(
                {
                    "service": service_file,
                    "method": method,
                    "prefix": prefix,
                    "expected": verb_display,
                    "presentation_dir": presentation_dir,
                    "route_verbs_found": sorted(route_verbs),
                }
            )

if failures:
    print(f"FAIL: {len(failures)} service CRUD method(s) lack corresponding HTTP routes:\n")
    for f in failures:
        print(f"  Service file : {f['service']}")
        print(f"  Method       : {f['method']}()")
        print(f"  Missing route: {f['expected']}")
        print(f"  Searched in  : {f['presentation_dir']}")
        found_str = ", ".join(f"@router.{v}" for v in f["route_verbs_found"]) or "(none)"
        print(f"  Routes found : {found_str}")
        print()
    print("A service method with no HTTP route is unreachable by API consumers.")
    print("Every spec SHALL requirement for an HTTP endpoint requires:")
    print("  1. Service method")
    print("  2. @router.<verb> route in presentation/<resource>/routes.py")
    print("  3. Pydantic request model")
    print("  4. Route-level unit tests")
    sys.exit(1)
else:
    print("PASS: All service CRUD methods have corresponding HTTP routes.")
    sys.exit(0)
PYEOF
