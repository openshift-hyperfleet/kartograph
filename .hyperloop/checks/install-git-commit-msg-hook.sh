#!/usr/bin/env bash
# install-git-commit-msg-hook.sh
#
# Installs a git commit-msg hook that mechanically blocks committing without a
# Task-Ref trailer in the commit message.
#
# PURPOSE: The manual "run check-all-commits-have-task-ref.sh before submitting"
# rule is routinely skipped during "trivial" commits (documentation fixes,
# README updates, config tweaks). A commit-msg hook fires automatically for
# every `git commit` — including quick fix-up commits — making Task-Ref
# enforcement mechanical rather than advisory.
#
# WHEN TO RUN:
#   Immediately after branch creation, before your first commit:
#     git checkout -b hyperloop/task-NNN origin/alpha
#     bash .hyperloop/checks/install-git-commit-msg-hook.sh
#
# The hook survives for the lifetime of the git worktree (stored in .git/hooks/).
# It is NOT committed to the repository — each worktree must install it separately.
#
# EXEMPTIONS (same as check-all-commits-have-task-ref.sh):
# - Merge commits (MERGE_HEAD present) — auto-generated, attribution via parents.
# - GitHub squash-merge commits (subject ends with (#NNN)) — upstream PR commits.
#
# Exit 0 — hook installed or already up-to-date.
# Exit 1 — could not install (not inside a git repo).

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "ERROR: Not inside a git repository — cannot install commit-msg hook."
  exit 1
}

GIT_DIR="$(git rev-parse --git-dir 2>/dev/null)"
HOOKS_DIR="$GIT_DIR/hooks"
HOOK_FILE="$HOOKS_DIR/commit-msg"

GUARD_MARKER="# task-ref trailer guard (hyperloop)"
GUARD_BLOCK="${GUARD_MARKER}
COMMIT_MSG_FILE_TR=\"\$1\"
SUBJECT_TR=\$(head -1 \"\$COMMIT_MSG_FILE_TR\")
# Skip merge commits
if [[ -f \"\$(git rev-parse --git-dir 2>/dev/null)/MERGE_HEAD\" ]]; then
  exit 0
fi
# Skip GitHub squash-merge commits (subject ends with (#NNN))
if [[ \"\$SUBJECT_TR\" =~ \\(#[0-9]+\\)\$ ]]; then
  exit 0
fi
# Use git's strict trailer parser instead of grep so that a blank line within
# the trailer block is caught here at commit time. A blank line between
# Task-Ref: and Co-Authored-By: causes git to discard Task-Ref as a trailer,
# making %(trailers:key=Task-Ref,valueonly) return empty in downstream checks
# even though the text 'Task-Ref: task-NNN' is visually present (root cause of
# task-133 FAIL: check-task-owns-branch-commits.sh failed due to broken block).
PARSED_TASK_REF=\"\"
if command -v git >/dev/null 2>&1; then
  PARSED_TASK_REF=\$(git interpret-trailers --parse \"\$COMMIT_MSG_FILE_TR\" 2>/dev/null \
    | grep -iE '^Task-Ref:[[:space:]]*' | head -1 || true)
fi
if [[ -n \"\$PARSED_TASK_REF\" ]]; then
  exit 0
fi
# Distinguish between missing trailer and broken block (present in body text
# but not parseable by git due to a blank line within the trailer block).
RAW_TASK_REF=\$(grep -iE '^Task-Ref:[[:space:]]*' \"\$COMMIT_MSG_FILE_TR\" | head -1 || true)
echo ''
if [[ -n \"\$RAW_TASK_REF\" ]]; then
  echo 'ERROR: Task-Ref trailer found but NOT recognised by git — broken trailer block.'
  echo ''
  echo 'A blank line within the trailer block causes git to discard all trailers'
  echo 'above it. Only the final contiguous block is parsed.'
  echo ''
  echo 'WRONG (blank line breaks the block):'
  echo '  Task-Ref: task-NNN'
  echo '                        ← remove this blank line'
  echo '  Co-Authored-By: Claude <noreply@anthropic.com>'
  echo ''
  echo 'CORRECT (one contiguous block — no blank lines between trailers):'
  echo '  Task-Ref: task-NNN'
  echo '  Co-Authored-By: Claude <noreply@anthropic.com>'
else
  echo 'ERROR: Commit message is missing a Task-Ref trailer.'
  echo ''
  echo 'Every commit on a task branch must include:'
  echo ''
  echo '  Task-Ref: task-NNN'
  echo ''
  echo 'Add it to the END of the commit message body, in a contiguous trailer block:'
  echo ''
  echo '  feat: brief subject'
  echo ''
  echo '  Optional longer body.'
  echo ''
  echo '  Task-Ref: task-NNN'
  echo '  Co-Authored-By: Claude <noreply@anthropic.com>'
  echo ''
  echo 'This applies to ALL commits, including documentation and trivial fixes.'
fi
echo ''
exit 1"

mkdir -p "$HOOKS_DIR"

if [[ -f "$HOOK_FILE" ]]; then
  if grep -qF "$GUARD_MARKER" "$HOOK_FILE" 2>/dev/null; then
    echo "PASS: commit-msg hook already contains the task-ref trailer guard."
    echo "      Location: $HOOK_FILE"
    exit 0
  fi

  # Append the guard to the existing hook, preserving current content.
  printf '\n%s\n' "$GUARD_BLOCK" >> "$HOOK_FILE"
  chmod +x "$HOOK_FILE"
  echo "PASS: task-ref trailer guard appended to existing commit-msg hook."
  echo "      Location: $HOOK_FILE"
  exit 0
fi

# No commit-msg hook yet — create one from scratch.
cat > "$HOOK_FILE" <<'HOOK_EOF'
#!/usr/bin/env bash
# commit-msg hook installed by install-git-commit-msg-hook.sh
set -euo pipefail
HOOK_EOF

printf '\n%s\n' "$GUARD_BLOCK" >> "$HOOK_FILE"
chmod +x "$HOOK_FILE"

echo "PASS: commit-msg hook installed at $HOOK_FILE"
echo "      The hook will reject 'git commit' when the message lacks a"
echo "      Task-Ref: task-NNN trailer — including documentation and trivial"
echo "      fix commits that are commonly committed without the trailer."
