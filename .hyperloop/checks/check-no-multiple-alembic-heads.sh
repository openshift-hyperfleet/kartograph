#!/usr/bin/env bash
# check-no-multiple-alembic-heads.sh
#
# Fails if the migration versions directory has multiple Alembic heads — which
# causes `alembic upgrade head` to abort at startup with:
#   "Multiple head revisions are present for given argument 'head'"
#
# PURPOSE: This is a PRE-PUSH gate. Two migration branches without a merge
# revision produce divergent heads. This check catches the problem before it
# reaches CI or a running service.
#
# The most common failure mode is:
#   - Two feature branches each add a migration that chains off the same parent.
#   - After merging both, the versions/ directory has two leaf revisions (heads)
#     with no common successor — Alembic cannot determine which to run last.
#
# CORRECT FIX:
#   cd src/api
#   uv run alembic merge heads -m "merge migration branches"
#   # Then stage and commit the generated merge revision.
#
# Exit 0 — single head; safe to push.
# Exit 1 — multiple heads detected; push is blocked.

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"

if [[ ! -d "$REPO_ROOT/src/api/infrastructure/migrations" ]]; then
  echo "WARN: migrations directory not found — skipping Alembic head check."
  exit 0
fi

head_output=$(cd "$REPO_ROOT/src/api" && uv run alembic heads 2>&1) || true

head_count=$(echo "$head_output" | grep -c "(head)" || true)

if [[ "$head_count" -le 1 ]]; then
  echo "PASS: Alembic migration graph has a single head — safe to push."
  exit 0
fi

echo ""
echo "FAIL: Multiple Alembic migration heads detected ($head_count heads)."
echo ""
echo "Current heads:"
echo "$head_output" | grep "(head)" | sed 's/^/  /'
echo ""
echo "Running \`alembic upgrade head\` with multiple heads aborts at startup."
echo ""
echo "── CORRECT FIX ─────────────────────────────────────────────────────────────"
echo ""
echo "  Create a merge revision that makes the graph linear again:"
echo ""
echo "    cd src/api"
echo "    uv run alembic merge heads -m \"merge migration branches\""
echo ""
echo "  Then stage and commit the generated merge revision, then push."
echo ""
echo "── VERIFY ───────────────────────────────────────────────────────────────────"
echo ""
echo "  After committing the merge revision, re-run this check:"
echo "    bash .hyperloop/checks/check-no-multiple-alembic-heads.sh"
echo ""
exit 1
