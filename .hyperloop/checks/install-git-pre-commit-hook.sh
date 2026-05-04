#!/usr/bin/env bash
# install-git-pre-commit-hook.sh
#
# Installs a git pre-commit hook that mechanically blocks committing
# .hyperloop/worker-result.yaml in any form (addition, modification, deletion).
#
# PURPOSE: The manual "run check-no-worker-result-staged.sh before committing"
# rule is routinely skipped during quick fix-up commits made in resubmission
# rounds. A git pre-commit hook fires automatically for every `git commit` with
# no per-commit manual step, making the guard mechanical rather than advisory.
#
# WHEN TO RUN:
#   Immediately after branch creation, before your first commit:
#     git checkout -b hyperloop/task-NNN origin/alpha
#     bash .hyperloop/checks/install-git-pre-commit-hook.sh
#
# The hook survives for the lifetime of the git worktree (stored in .git/hooks/).
# It is NOT committed to the repository — each worktree must install it separately.
#
# Exit 0 — hook installed or already up-to-date.
# Exit 1 — could not install (not inside a git repo, or hook already conflicts).

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "ERROR: Not inside a git repository — cannot install pre-commit hook."
  exit 1
}

GIT_DIR="$(git rev-parse --git-dir 2>/dev/null)"
HOOKS_DIR="$GIT_DIR/hooks"
HOOK_FILE="$HOOKS_DIR/pre-commit"

# Relative path from repo root — used inside the hook body.
CHECK_SCRIPT=".hyperloop/checks/check-no-worker-result-staged.sh"

# The guard block appended to (or placed in) the hook.
GUARD_MARKER="# worker-result guard (hyperloop)"
GUARD_BLOCK="${GUARD_MARKER}
REPO_ROOT_WR=\"\$(git rev-parse --show-toplevel 2>/dev/null)\"
if [[ -f \"\${REPO_ROOT_WR}/${CHECK_SCRIPT}\" ]]; then
  bash \"\${REPO_ROOT_WR}/${CHECK_SCRIPT}\" || exit 1
fi"

mkdir -p "$HOOKS_DIR"

if [[ -f "$HOOK_FILE" ]]; then
  # If the hook already contains the guard, report up-to-date and exit.
  if grep -qF "$GUARD_MARKER" "$HOOK_FILE" 2>/dev/null; then
    echo "PASS: pre-commit hook already contains the worker-result guard."
    echo "      Location: $HOOK_FILE"
    exit 0
  fi

  # Append the guard to the existing hook, preserving its current content.
  printf '\n%s\n' "$GUARD_BLOCK" >> "$HOOK_FILE"
  chmod +x "$HOOK_FILE"
  echo "PASS: worker-result guard appended to existing pre-commit hook."
  echo "      Location: $HOOK_FILE"
  exit 0
fi

# No pre-commit hook yet — create one from scratch.
cat > "$HOOK_FILE" <<'HOOK_EOF'
#!/usr/bin/env bash
# pre-commit hook installed by install-git-pre-commit-hook.sh
set -euo pipefail
HOOK_EOF

printf '\n%s\n' "$GUARD_BLOCK" >> "$HOOK_FILE"
chmod +x "$HOOK_FILE"

echo "PASS: pre-commit hook installed at $HOOK_FILE"
echo "      The hook will run check-no-worker-result-staged.sh automatically"
echo "      before every 'git commit', blocking any staged touch of"
echo "      .hyperloop/worker-result.yaml without requiring a manual step."
