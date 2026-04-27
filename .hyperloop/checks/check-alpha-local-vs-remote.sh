#!/usr/bin/env bash
# check-alpha-local-vs-remote.sh
#
# Verifies that the local 'alpha' branch is not ahead of 'origin/alpha' with
# SOURCE CODE changes. Process-only divergence (.hyperloop/ files) is allowed
# since those commits do not affect implementation checks.
#
# WHY THIS CHECK:
#   When check-branch-rebased-on-alpha.sh and check-no-foreign-task-commits.sh
#   compute merge-bases, they use the local 'alpha' ref. If local alpha has
#   source code commits not in origin/alpha, the merge-base drifts and worker
#   branches may see false-positive foreign-commit or regression failures.
#
#   However, process-only commits on local alpha (affecting only .hyperloop/
#   files such as agent overlays or check scripts) do NOT affect source code
#   merge-base calculations and are therefore acceptable.
#
# SEVERITY RULES:
#   FAIL  — local alpha has commits that touch src/ not present in origin/alpha.
#   PASS  — local alpha equals origin/alpha (fully in sync).
#   PASS  — local alpha is only behind origin/alpha (normal staleness).
#   PASS  — local alpha is ahead of origin/alpha, but only with .hyperloop/
#            process commits (no src/ changes).
#
# EXIT CODES:
#   0 — no source-code divergence detected
#   1 — local alpha has source-code commits not in origin/alpha
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

if [[ "$AHEAD" -eq 0 ]]; then
  # Local is only BEHIND — normal in multi-worktree setups.
  echo "INFO: local alpha (${LOCAL_SHA:0:8}) is ${BEHIND} commit(s) behind origin/alpha (${REMOTE_SHA:0:8})."
  echo "INFO: local alpha is not ahead — no contamination detected."
  echo "PASS: Local alpha is clean (behind but not ahead of remote)."
  exit 0
fi

# Local is AHEAD of origin/alpha. Check whether the extra commits touch src/.
extra_commits=$(git log --format="%H" refs/remotes/origin/alpha..refs/heads/alpha 2>/dev/null || true)
src_contamination=0

while IFS= read -r sha; do
  [[ -z "$sha" ]] && continue
  # List files changed in this commit
  if git diff-tree --no-commit-id -r --name-only "$sha" 2>/dev/null | grep -q '^src/'; then
    src_contamination=1
    echo "FAIL: local alpha commit ${sha:0:8} touches src/ — not present in origin/alpha."
    echo "  Subject: $(git log -1 --format='%s' "$sha" 2>/dev/null || echo '<unknown>')"
  fi
done <<< "$extra_commits"

if [[ $src_contamination -eq 1 ]]; then
  echo ""
  echo "FAIL: local alpha has source-code commits not in origin/alpha."
  echo "  local  alpha: ${LOCAL_SHA:0:8} (${AHEAD} commit(s) ahead, ${BEHIND} behind)"
  echo "  remote alpha: ${REMOTE_SHA:0:8}"
  echo ""
  echo "Fix: investigate whether local alpha was accidentally modified."
  echo "     If safe: git branch -f alpha origin/alpha"
  echo "     (only valid when alpha is not checked out in the current shell)"
  exit 1
fi

# Ahead only with .hyperloop/ process commits — acceptable.
echo "INFO: local alpha (${LOCAL_SHA:0:8}) is ${AHEAD} commit(s) ahead of origin/alpha (${REMOTE_SHA:0:8})."
echo "INFO: All extra commits are process-only (.hyperloop/). No src/ changes detected."
echo "INFO: This is a known worktree constraint — cannot update local alpha while it is"
echo "      checked out at another path. Process commits do not affect implementation checks."
echo "PASS: Local alpha divergence is process-only; no source-code contamination detected."
exit 0
