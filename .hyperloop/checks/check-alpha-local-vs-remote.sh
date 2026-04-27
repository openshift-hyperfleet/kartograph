#!/usr/bin/env bash
# check-alpha-local-vs-remote.sh
#
# Verifies that the local 'alpha' branch is in sync with 'origin/alpha'.
# A diverged local alpha causes false positives in rebased-on-alpha and
# merge-base checks because they reference the local tracking ref.
#
# WHY THIS CHECK:
#   When check-branch-rebased-on-alpha.sh computes the merge-base, it uses
#   the local 'alpha' ref. If local alpha is stale (behind origin) the
#   check will claim the branch is up-to-date when it is actually behind
#   the true remote alpha. Conversely, if a local commit was accidentally
#   pushed to alpha, the merge-base drifts forward and worker branches
#   appear to diverge unnecessarily.
#
# SEVERITY RULES:
#   FAIL — local alpha is AHEAD of origin/alpha (local has extra commits,
#           potential contamination).
#   PASS — local alpha equals origin/alpha (fully in sync).
#   PASS — local alpha is BEHIND origin/alpha but not ahead (normal worktree
#           staleness; the check-branch-rebased-on-alpha already covers this).
#
# EXIT CODES:
#   0 — local alpha is not ahead of origin/alpha (OK or stale-but-clean)
#   1 — local alpha has commits not in origin/alpha (contamination risk)
#
# Usage:
#   ./check-alpha-local-vs-remote.sh

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "=== Checking local alpha vs remote origin/alpha ==="

# If the local branch 'alpha' doesn't exist at all, nothing to compare.
if ! git show-ref --verify --quiet refs/heads/alpha 2>/dev/null; then
  echo "INFO: Local 'alpha' branch does not exist — skipping local/remote comparison."
  echo "PASS: No drift detected (local alpha absent)."
  exit 0
fi

# Fetch the remote ref without modifying the working tree.
if ! git fetch origin alpha --quiet 2>/dev/null; then
  echo "WARNING: Could not fetch origin/alpha — skipping remote comparison."
  echo "PASS: Skipping (no network access or remote unavailable)."
  exit 0
fi

LOCAL_SHA=$(git rev-parse refs/heads/alpha 2>/dev/null || echo "unknown")
REMOTE_SHA=$(git rev-parse refs/remotes/origin/alpha 2>/dev/null || echo "unknown")

if [[ "$LOCAL_SHA" == "unknown" || "$REMOTE_SHA" == "unknown" ]]; then
  echo "WARNING: Could not resolve one or both alpha refs — skipping."
  echo "PASS: Skipping (ref resolution failed)."
  exit 0
fi

if [[ "$LOCAL_SHA" == "$REMOTE_SHA" ]]; then
  echo "OK: local alpha (${LOCAL_SHA:0:8}) == origin/alpha (${REMOTE_SHA:0:8})."
  echo "PASS: Local alpha is in sync with remote."
  exit 0
fi

# Determine relationship (ahead / behind / diverged).
AHEAD=$(git rev-list --count refs/remotes/origin/alpha..refs/heads/alpha 2>/dev/null || echo 0)
BEHIND=$(git rev-list --count refs/heads/alpha..refs/remotes/origin/alpha 2>/dev/null || echo 0)

if [[ "$AHEAD" -gt 0 ]]; then
  echo "FAIL: local alpha has ${AHEAD} commit(s) not in origin/alpha."
  echo "  local  alpha: ${LOCAL_SHA:0:8}"
  echo "  remote alpha: ${REMOTE_SHA:0:8}"
  echo ""
  echo "Local alpha commits not on origin/alpha:"
  git log --oneline refs/remotes/origin/alpha..refs/heads/alpha | head -10
  echo ""
  echo "Fix: investigate whether local alpha was accidentally modified."
  echo "     If safe: git branch -f alpha origin/alpha"
  echo "     (only valid when alpha is not checked out in the current shell)"
  exit 1
fi

# Local is only BEHIND (no contamination). This is normal in multi-worktree
# setups where the alpha branch is checked out elsewhere and cannot be fast-
# forwarded. The check-branch-rebased-on-alpha.sh check enforces the ≤5 commit
# staleness threshold; this check does not duplicate that constraint.
echo "INFO: local alpha (${LOCAL_SHA:0:8}) is ${BEHIND} commit(s) behind origin/alpha (${REMOTE_SHA:0:8})."
echo "INFO: local alpha is not ahead — no contamination detected."
echo "PASS: Local alpha is clean (behind but not ahead of remote)."
exit 0
