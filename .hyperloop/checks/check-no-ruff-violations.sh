#!/usr/bin/env bash
# check-no-ruff-violations.sh
#
# Fails if ruff detects any linting violations in src/api/.
#
# WHY: The backend suite historically did not invoke ruff directly.
# Implementers relying solely on check-run-backend-suite.sh could submit
# branches with linting violations that the suite never caught.
#
# Observed in task-035: UpdateKnowledgeGraphRequest was defined twice in the
# same module (management/presentation/knowledge_graphs/models.py:27 and :59).
# The second definition contained a spurious 'count: int' field that silently
# overwrote the correct first definition, producing a functional bug even
# though all unit tests passed. ruff reports this as F811 (redefinition of
# unused name). Without this check in the backend suite, the violation only
# surfaced at verifier time (round 5), costing multiple resubmission cycles.
#
# Exit 0  — zero ruff violations.
# Exit 1  — one or more violations found.

set -euo pipefail

# Normalize CWD to repo root.
cd "$(git rev-parse --show-toplevel)"

API_DIR="src/api"

if [[ ! -d "$API_DIR" ]]; then
  echo "INFO: $API_DIR not found — skipping ruff check."
  exit 0
fi

echo "=== Running ruff linting check (src/api/) ==="

if (cd "$API_DIR" && uv run ruff check .); then
  echo "PASS: ruff found zero violations."
  exit 0
else
  echo ""
  echo "FAIL: ruff reported linting violations — resolve them before submitting."
  echo ""
  echo "Common violations to watch for:"
  echo "  F811 — duplicate class or function definition in the same file"
  echo "          (the second definition silently overwrites the first)"
  echo "  F401 — unused import"
  echo ""
  echo "Run 'cd src/api && uv run ruff check .' to see full output."
  exit 1
fi
