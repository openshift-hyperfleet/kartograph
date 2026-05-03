#!/usr/bin/env bash
# check-spec-named-files-exist.sh
#
# Verifies that every file path listed under "## Files / Areas Affected" and
# annotated with "new" actually exists in the worktree at submission time.
#
# Usage: bash .hyperloop/checks/check-spec-named-files-exist.sh
# Exit 0 = all spec-required new files are present (or check is not applicable).
# Exit 1 = one or more spec-required new files are missing from the worktree.

set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
TASK_ID=$(echo "$BRANCH" | grep -oP 'task-\d+' | head -1 || true)

if [[ -z "$TASK_ID" ]]; then
  echo "INFO: Cannot determine task ID from branch '${BRANCH}' — skipping check."
  exit 0
fi

SPEC_FILE=".hyperloop/state/tasks/${TASK_ID}.md"
if [[ ! -f "$SPEC_FILE" ]]; then
  echo "INFO: No spec file found at ${SPEC_FILE} — skipping check."
  exit 0
fi

# ── Parse the "## Files / Areas Affected" section ────────────────────────────
# Collect backtick-quoted paths on lines that also contain the word "new"
# (case-insensitive). Stop parsing at the next level-2 heading (## ...).

MISSING=()
IN_FILES_SECTION=0

while IFS= read -r line; do
  # Enter the target section (allow leading whitespace — YAML indents block scalars)
  if echo "$line" | grep -qP '^\s*##\s+Files\s*/?\s*Areas\s+Affected'; then
    IN_FILES_SECTION=1
    continue
  fi

  # Leave the section at the next ## heading (allow leading whitespace)
  if [[ $IN_FILES_SECTION -eq 1 ]] && echo "$line" | grep -qP '^\s*##\s+'; then
    IN_FILES_SECTION=0
    continue
  fi

  if [[ $IN_FILES_SECTION -eq 1 ]]; then
    # Only inspect lines that mention "new" (new file, new test file, etc.)
    if echo "$line" | grep -qiP '\bnew\b'; then
      # Extract every backtick-quoted token on this line
      while IFS= read -r token; do
        # Skip tokens without a directory separator or file extension
        if [[ "$token" != *"/"* ]] || ! echo "$token" | grep -qP '\.[a-zA-Z0-9]+$'; then
          continue
        fi
        # Skip tokens that contain spaces (unlikely to be a real path)
        if [[ "$token" == *" "* ]]; then
          continue
        fi
        if [[ ! -f "${ROOT}/${token}" ]]; then
          MISSING+=("$token")
        fi
      done < <(echo "$line" | grep -oP '`[^`]+`' | tr -d '`')
    fi
  fi
done < "$SPEC_FILE"

# ── Report ────────────────────────────────────────────────────────────────────

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "FAIL: The following new files are required by ${SPEC_FILE} but do not"
  echo "      exist in the worktree:"
  echo ""
  for f in "${MISSING[@]}"; do
    echo "  MISSING: ${f}"
  done
  echo ""
  echo "The task spec explicitly marks these files as new deliverables."
  echo "Create them before writing worker-result.yaml."
  exit 1
fi

echo "PASS: All spec-required new files exist in the worktree."
exit 0
