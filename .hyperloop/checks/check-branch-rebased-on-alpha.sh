#!/usr/bin/env bash
# check-branch-rebased-on-alpha.sh
#
# Verifies the current branch's merge-base with 'alpha' is recent enough
# that fixes committed to alpha after the branch was cut are present.
#
# A stale merge-base causes check failures on code the task never modified:
# an assertion already corrected in alpha still appears in its old (wrong)
# form on the stale branch, producing a false-positive check failure.
#
# Exit 0 if alpha has 0-5 commits not yet incorporated into this branch.
# Exit 1 if alpha has more than 5 commits the branch is missing (too stale).

set -euo pipefail

BASE_BRANCH="alpha"

if ! git rev-parse --verify "$BASE_BRANCH" >/dev/null 2>&1; then
  echo "INFO: Branch '$BASE_BRANCH' not found — skipping staleness check."
  exit 0
fi

MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)
if [[ -z "$MERGE_BASE" ]]; then
  echo "INFO: No common ancestor with '$BASE_BRANCH' — skipping staleness check."
  exit 0
fi

COMMITS_BEHIND=$(git rev-list --count "${MERGE_BASE}..${BASE_BRANCH}" 2>/dev/null || echo "0")

if [[ "$COMMITS_BEHIND" -le 5 ]]; then
  echo "OK: Branch is ${COMMITS_BEHIND} commit(s) behind '${BASE_BRANCH}' — within acceptable range."
  exit 0
fi

echo "STALE BRANCH: This branch is ${COMMITS_BEHIND} commit(s) behind '${BASE_BRANCH}'."
echo ""
echo "Commits on '${BASE_BRANCH}' not yet incorporated into this branch:"
git log --oneline -n 20 "${MERGE_BASE}..${BASE_BRANCH}"
echo ""
echo "Resolution: git rebase ${BASE_BRANCH}"
echo ""
echo "A stale branch causes false-positive check failures: assertions already"
echo "fixed in '${BASE_BRANCH}' (e.g. 403→404 corrections) appear in their old"
echo "broken form on this branch even though this task never touched those files."
echo "Rebase onto current '${BASE_BRANCH}' before submitting."
exit 1
