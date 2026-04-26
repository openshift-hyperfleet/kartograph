#!/usr/bin/env bash
# check-existing-verdict.sh
#
# Reads .hyperloop/worker-result.yaml on the CURRENT branch (HEAD) and
# reports the recorded verdict.
#
# WHY: When an agent future fails and the orchestrator reassigns a task,
# the new agent may land on a branch that already has a fully-passing
# verification. This script surfaces that fact immediately so the agent
# does not re-implement work that is already done.
#
# Exit 0  — worker-result.yaml exists on HEAD and contains "verdict: pass"
# Exit 1  — worker-result.yaml is absent, or verdict is not "pass"
#
# Usage:
#   bash .hyperloop/checks/check-existing-verdict.sh

set -euo pipefail

RESULT_FILE=".hyperloop/worker-result.yaml"

echo "=== Checking for existing passing verdict on current branch ==="

# Check whether the file exists in the working tree (staged or committed)
if [[ ! -f "$RESULT_FILE" ]]; then
  echo "INFO: $RESULT_FILE not present in working tree."
  echo "RESULT: No prior verdict recorded — proceed with full implementation/verification."
  exit 1
fi

VERDICT=$(grep -m1 '^verdict:' "$RESULT_FILE" 2>/dev/null | awk '{print $2}' | tr -d '"' || true)

if [[ -z "$VERDICT" ]]; then
  echo "INFO: $RESULT_FILE exists but contains no 'verdict:' field."
  echo "RESULT: No prior verdict recorded — proceed with full implementation/verification."
  exit 1
fi

echo ""
echo "Prior verdict recorded: $VERDICT"
echo ""

# Show the summary if present
if grep -q '^summary:' "$RESULT_FILE" 2>/dev/null; then
  echo "--- Summary from prior verification ---"
  awk '/^summary:/,/^[a-z]/' "$RESULT_FILE" | head -10
  echo "---"
fi

if [[ "$VERDICT" == "pass" ]]; then
  echo ""
  echo "PASS: A prior 'verdict: pass' is recorded on this branch."
  echo "      Do NOT re-implement. Confirm rebase + check scripts, then submit."
  exit 0
else
  echo ""
  echo "INFO: Prior verdict was '$VERDICT' (not pass)."
  echo "      Proceed with implementation/verification to address prior failures."
  exit 1
fi
