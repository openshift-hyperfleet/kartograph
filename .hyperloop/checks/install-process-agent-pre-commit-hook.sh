#!/usr/bin/env bash
# install-process-agent-pre-commit-hook.sh
#
# Installs a git pre-commit hook that mechanically runs
# check-process-improvement-commit-is-clean.sh before every commit.
#
# PURPOSE:
#   All existing process-improvement pre-commit gates are advisory — they
#   require the agent to remember to run them before each commit.  When the
#   orchestrator spawns the process-improvement agent in a task-branch context
#   (e.g. during recovery), a single missed manual gate lets commits land on
#   the task branch.  Observed in task-035 (round 5): four process-improvement
#   commits landed on hyperloop/task-035 despite overlay rules prohibiting it,
#   because the manual pre-commit step was skipped.
#
#   A git pre-commit hook fires automatically for every `git commit` with no
#   per-commit manual action, making the guard mechanical rather than advisory.
#
# WHEN TO RUN:
#   As the ABSOLUTE FIRST action in any process-improvement session — BEFORE
#   branch creation and BEFORE any other command.  Installing before branch
#   creation ensures the hook is active even if the checkout fails or the
#   orchestrator has already placed you on the wrong branch:
#
#     bash .hyperloop/checks/install-process-agent-pre-commit-hook.sh
#     git fetch origin && git checkout -b process-improvement/$(date +%Y%m%d-%H%M%S) origin/alpha
#
#   The hook survives for the lifetime of the git worktree (stored in
#   .git/hooks/), is idempotent, and is NOT committed to the repository.
#
# Exit 0 — hook installed or already up-to-date.
# Exit 1 — could not install (not inside a git repo).

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "ERROR: Not inside a git repository — cannot install pre-commit hook."
  exit 1
}

GIT_DIR="$(git rev-parse --git-dir 2>/dev/null)"
HOOKS_DIR="$GIT_DIR/hooks"
HOOK_FILE="$HOOKS_DIR/pre-commit"

# Path to the check script, relative to repo root.
CHECK_SCRIPT=".hyperloop/checks/check-process-improvement-commit-is-clean.sh"

# Idempotency marker — grep for this before appending.
GUARD_MARKER="# process-agent-clean guard (hyperloop)"

GUARD_BLOCK="${GUARD_MARKER}
REPO_ROOT_PA=\"\$(git rev-parse --show-toplevel 2>/dev/null)\"
if [[ -f \"\${REPO_ROOT_PA}/${CHECK_SCRIPT}\" ]]; then
  bash \"\${REPO_ROOT_PA}/${CHECK_SCRIPT}\" || exit 1
fi"

mkdir -p "$HOOKS_DIR"

if [[ -f "$HOOK_FILE" ]]; then
  # Already installed — idempotent exit.
  if grep -qF "$GUARD_MARKER" "$HOOK_FILE" 2>/dev/null; then
    echo "PASS: pre-commit hook already contains the process-agent-clean guard."
    echo "      Location: $HOOK_FILE"
    exit 0
  fi

  # Existing hook without the guard — append.
  printf '\n%s\n' "$GUARD_BLOCK" >> "$HOOK_FILE"
  chmod +x "$HOOK_FILE"
  echo "PASS: process-agent-clean guard appended to existing pre-commit hook."
  echo "      Location: $HOOK_FILE"
  exit 0
fi

# No pre-commit hook yet — create from scratch.
cat > "$HOOK_FILE" <<'HOOK_EOF'
#!/usr/bin/env bash
# pre-commit hook — installed by install-process-agent-pre-commit-hook.sh
set -euo pipefail
HOOK_EOF

printf '\n%s\n' "$GUARD_BLOCK" >> "$HOOK_FILE"
chmod +x "$HOOK_FILE"

echo "PASS: process-agent-clean pre-commit hook installed at $HOOK_FILE"
echo "      Runs check-process-improvement-commit-is-clean.sh automatically"
echo "      before every 'git commit', blocking commits to hyperloop/task-NNN"
echo "      branches without requiring a manual pre-commit step."
