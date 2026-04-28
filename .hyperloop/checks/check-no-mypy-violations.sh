#!/usr/bin/env bash
# check-no-mypy-violations.sh
#
# Fails if mypy detects any type errors in src/api/.
#
# WHY: Type errors are caught by mypy but not by the existing backend check
# scripts. Observed in task-035: the duplicate UpdateKnowledgeGraphRequest
# class definition triggered:
#
#   management/presentation/knowledge_graphs/models.py:59: error: Name
#   "UpdateKnowledgeGraphRequest" already defined on line 27 [no-redef]
#   Found 1 error in 1 file (checked 497 source files)
#
# mypy [no-redef] and ruff F811 are two views of the same bug: a Python class
# or function defined twice in the same file. Python silently accepts this and
# the second definition wins, which can corrupt request model validation even
# when all unit tests pass (tests that import the class by name always get the
# second definition, which may differ in fields from the first).
#
# Exit 0  — zero mypy errors.
# Exit 1  — one or more errors found.

set -euo pipefail

# Normalize CWD to repo root.
cd "$(git rev-parse --show-toplevel)"

API_DIR="src/api"

if [[ ! -d "$API_DIR" ]]; then
  echo "INFO: $API_DIR not found — skipping mypy check."
  exit 0
fi

echo "=== Running mypy type checking (src/api/) ==="

if (cd "$API_DIR" && uv run mypy . --config-file pyproject.toml --ignore-missing-imports); then
  echo "PASS: mypy found zero type errors."
  exit 0
else
  echo ""
  echo "FAIL: mypy reported type errors — resolve them before submitting."
  echo ""
  echo "Common errors to watch for:"
  echo "  [no-redef] — a name is defined more than once in the same file"
  echo "               (Python uses the last definition, which may differ"
  echo "                from what tests expect and imports assume)"
  echo ""
  echo "Run 'cd src/api && uv run mypy . --config-file pyproject.toml --ignore-missing-imports'"
  echo "to see full output."
  exit 1
fi
