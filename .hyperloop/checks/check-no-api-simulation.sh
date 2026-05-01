#!/usr/bin/env bash
# check-no-api-simulation.sh
#
# Fails if any production Vue page or composable uses a setTimeout-based sleep
# pattern as a substitute for a real backend API call.
#
# The specific anti-pattern caught is:
#   await new Promise(resolve => setTimeout(resolve, N))
#   ...followed by assigning from hardcoded constants or inline data...
#
# This pattern simulates API latency without actually calling the backend.
# It passes check-no-coming-soon-stubs.sh (no "Coming Soon" text) but produces
# spec scenarios that appear implemented while the backend integration is absent.
#
# Root cause in task-045: beginOntologyProposal() used this pattern to fake
# a scan+AI-proposal call, hardcoding GITHUB_PROPOSAL_NODES/EDGES constants
# instead of calling POST /management/data-sources/{id}/propose-ontology.
#
# Usage:
#   ./check-no-api-simulation.sh [repo_root]
#
# Exit 0 — no simulation patterns found.
# Exit 1 — one or more simulation patterns found.

set -euo pipefail

REPO_ROOT="${1:-$(git rev-parse --show-toplevel)}"
FRONTEND_PAGES="${REPO_ROOT}/src/dev-ui/app/pages"
FRONTEND_COMPOSABLES="${REPO_ROOT}/src/dev-ui/app/composables"

found=0

check_dir() {
  local dir="$1"
  if [[ ! -d "$dir" ]]; then
    return
  fi

  # Pattern 1: setTimeout used as a sleep/delay — the "await new Promise" form
  # Matches:
  #   await new Promise<void>((resolve) => setTimeout(resolve, ...))
  #   await new Promise(resolve => setTimeout(resolve, ...))
  local hits
  hits=$(grep -rn \
    --include="*.vue" \
    --include="*.ts" \
    --include="*.js" \
    --exclude="*.test.*" \
    --exclude="*.spec.*" \
    -E "new Promise[^)]*setTimeout[[:space:]]*\([[:space:]]*resolve" \
    "$dir" 2>/dev/null || true)

  if [[ -n "$hits" ]]; then
    echo ""
    echo "--- setTimeout sleep simulation detected in production code ---"
    echo "$hits"
    found=$((found + 1))
  fi
}

echo "=== Scanning for setTimeout API simulation patterns in production pages/composables ==="

check_dir "$FRONTEND_PAGES"
check_dir "$FRONTEND_COMPOSABLES"

echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: setTimeout-based API simulation found in production pages/composables."
  echo ""
  echo "Pattern detected:"
  echo "  await new Promise(resolve => setTimeout(resolve, N))"
  echo ""
  echo "This simulates async latency without calling the backend."
  echo "It passes stub-text checks but leaves the spec scenario unimplemented."
  echo ""
  echo "Fix: Implement the real backend endpoint and replace the setTimeout block"
  echo "     with a real apiFetch() call."
  echo ""
  echo "If the backend endpoint does not exist yet, raise a formal blocker:"
  echo "  .hyperloop/blockers/task-NNN-blocker.md"
  echo "describing what backend work is needed, and submit with the blocker rather"
  echo "than shipping simulation code."
  exit 1
else
  echo "PASS: No setTimeout API simulation patterns found."
  exit 0
fi
