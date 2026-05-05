#!/usr/bin/env bash
# install-process-agent-pre-commit-hook.sh
#
# Installs TWO git hooks for the process-improvement agent:
#
#   1. pre-commit hook  — runs check-process-improvement-commit-is-clean.sh
#                         before every commit; blocks staged files outside
#                         .hyperloop/ and overlay-line removals.
#
#   2. commit-msg hook  — validates commit subject uses an allowed
#                         conventional-commit type prefix
#                         (chore(process): chore(checks): docs(process):
#                          refactor(process):); blocks code-domain types
#                         (fix, feat, refactor without process scope).
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
#   task-145 root cause: the pre-commit hook was the ONLY barrier. When it was
#   absent, commit 457680c9e ("fix(query): correct error_type") modified a
#   source file with Task-Ref: process-improvement, contaminating the task
#   branch for six consecutive rounds. Adding an independent commit-msg hook
#   ensures a single missed installation still leaves one barrier running.
#
# WHEN TO RUN:
#   As the ABSOLUTE FIRST action in any process-improvement session — BEFORE
#   branch creation and BEFORE any other command.  Installing before branch
#   creation ensures hooks are active even if the checkout fails or the
#   orchestrator has already placed you on the wrong branch:
#
#     bash .hyperloop/checks/install-process-agent-pre-commit-hook.sh
#     git fetch origin && git checkout -b process-improvement/$(date +%Y%m%d-%H%M%S) origin/alpha
#
#   After installation, verify BOTH hooks are active:
#     cat "$(git rev-parse --git-dir)/hooks/pre-commit" | grep -q process-agent-clean && echo "pre-commit ACTIVE"
#     cat "$(git rev-parse --git-dir)/hooks/commit-msg" | grep -q process-subject-guard && echo "commit-msg ACTIVE"
#
#   The hooks survive for the lifetime of the git worktree (stored in
#   .git/hooks/), are idempotent, and are NOT committed to the repository.
#
# Exit 0 — both hooks installed or already up-to-date.
# Exit 1 — could not install (not inside a git repo).

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "ERROR: Not inside a git repository — cannot install hooks."
  exit 1
}

GIT_DIR="$(git rev-parse --git-dir 2>/dev/null)"
HOOKS_DIR="$GIT_DIR/hooks"
mkdir -p "$HOOKS_DIR"

# ── Paths and markers ──────────────────────────────────────────────────────────
CHECK_SCRIPT=".hyperloop/checks/check-process-improvement-commit-is-clean.sh"

PRE_COMMIT_HOOK="$HOOKS_DIR/pre-commit"
PRE_COMMIT_MARKER="# process-agent-clean guard (hyperloop)"
PRE_COMMIT_BLOCK="${PRE_COMMIT_MARKER}
REPO_ROOT_PA=\"\$(git rev-parse --show-toplevel 2>/dev/null)\"
if [[ -f \"\${REPO_ROOT_PA}/${CHECK_SCRIPT}\" ]]; then
  bash \"\${REPO_ROOT_PA}/${CHECK_SCRIPT}\" || exit 1
fi"

COMMIT_MSG_HOOK="$HOOKS_DIR/commit-msg"
COMMIT_MSG_MARKER="# process-subject-guard (hyperloop)"
# The commit-msg hook receives the message file as $1 and delegates to the
# same check-process-improvement-commit-is-clean.sh which accepts it as $1.
COMMIT_MSG_BLOCK="${COMMIT_MSG_MARKER}
REPO_ROOT_PSG=\"\$(git rev-parse --show-toplevel 2>/dev/null)\"
if [[ -f \"\${REPO_ROOT_PSG}/${CHECK_SCRIPT}\" ]]; then
  bash \"\${REPO_ROOT_PSG}/${CHECK_SCRIPT}\" \"\$1\" || exit 1
fi"

# ── Install pre-commit hook ────────────────────────────────────────────────────
if [[ -f "$PRE_COMMIT_HOOK" ]]; then
  if grep -qF "$PRE_COMMIT_MARKER" "$PRE_COMMIT_HOOK" 2>/dev/null; then
    echo "PASS: pre-commit hook already contains the process-agent-clean guard."
    echo "      Location: $PRE_COMMIT_HOOK"
  else
    printf '\n%s\n' "$PRE_COMMIT_BLOCK" >> "$PRE_COMMIT_HOOK"
    chmod +x "$PRE_COMMIT_HOOK"
    echo "PASS: process-agent-clean guard appended to existing pre-commit hook."
    echo "      Location: $PRE_COMMIT_HOOK"
  fi
else
  cat > "$PRE_COMMIT_HOOK" <<'HOOK_EOF'
#!/usr/bin/env bash
# pre-commit hook — installed by install-process-agent-pre-commit-hook.sh
set -euo pipefail
HOOK_EOF
  printf '\n%s\n' "$PRE_COMMIT_BLOCK" >> "$PRE_COMMIT_HOOK"
  chmod +x "$PRE_COMMIT_HOOK"
  echo "PASS: process-agent-clean pre-commit hook installed at $PRE_COMMIT_HOOK"
  echo "      Blocks commits to hyperloop/task-NNN branches and files outside .hyperloop/."
fi

# ── Install commit-msg hook ────────────────────────────────────────────────────
if [[ -f "$COMMIT_MSG_HOOK" ]]; then
  if grep -qF "$COMMIT_MSG_MARKER" "$COMMIT_MSG_HOOK" 2>/dev/null; then
    echo "PASS: commit-msg hook already contains the process-subject-guard."
    echo "      Location: $COMMIT_MSG_HOOK"
  else
    printf '\n%s\n' "$COMMIT_MSG_BLOCK" >> "$COMMIT_MSG_HOOK"
    chmod +x "$COMMIT_MSG_HOOK"
    echo "PASS: process-subject-guard appended to existing commit-msg hook."
    echo "      Location: $COMMIT_MSG_HOOK"
  fi
else
  cat > "$COMMIT_MSG_HOOK" <<'HOOK_EOF'
#!/usr/bin/env bash
# commit-msg hook — installed by install-process-agent-pre-commit-hook.sh
set -euo pipefail
HOOK_EOF
  printf '\n%s\n' "$COMMIT_MSG_BLOCK" >> "$COMMIT_MSG_HOOK"
  chmod +x "$COMMIT_MSG_HOOK"
  echo "PASS: process-subject-guard commit-msg hook installed at $COMMIT_MSG_HOOK"
  echo "      Blocks commits whose subject uses code-domain types (fix, feat, etc.)."
fi

echo ""
echo "Both hooks active. Verify with:"
echo "  cat \"\$(git rev-parse --git-dir)/hooks/pre-commit\" | grep -q process-agent-clean && echo 'pre-commit ACTIVE'"
echo "  cat \"\$(git rev-parse --git-dir)/hooks/commit-msg\" | grep -q process-subject-guard && echo 'commit-msg ACTIVE'"
