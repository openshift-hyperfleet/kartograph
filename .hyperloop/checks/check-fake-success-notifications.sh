#!/usr/bin/env bash
# check-fake-success-notifications.sh
#
# Fails if any Vue/TS file emits a success notification (toast.success, $notify,
# useToast success call) inside a handler that contains no outbound API call.
#
# The canonical anti-pattern (FAIL from task-014):
#
#   async function handleCreate() {
#     // Knowledge graph creation will be wired to the API in task-015.
#     // For now, close the dialog and guide the user to add a data source.
#     toast.success(`Knowledge graph "${name}" created`, { ... })
#     createDialogOpen.value = false
#   }
#
# A success notification without an API call means the user sees "Created!"
# but nothing was persisted. The feature is a lie.
#
# Detection strategy (two-pass):
#   Pass 1 — find files that have a toast/notify success call.
#   Pass 2 — for each such file, check whether at least one API call pattern
#             exists in the same file (apiFetch, $fetch, useApiClient, fetch(,
#             axios, useFetch, await api.).
#
# Files with success notifications but NO API call patterns are flagged.
# (False-positive rate is low: legitimate files always have at least one fetch.)
#
# Usage:
#   ./check-fake-success-notifications.sh [ui_source_dir]
#
# Exit 0  — all success notifications are co-located with real API calls.
# Exit 1  — one or more files emit success with no API call.

set -euo pipefail

UI_SOURCE_DIR="${1:-src/dev-ui}"

SUCCESS_PATTERNS=(
  "toast\.success("
  "toast\.add.*severity.*success"
  "\$notify.*type.*success"
  "useToast.*success"
  "notification.*success"
)

# Patterns that indicate a real outbound API call exists in the file.
API_CALL_PATTERNS=(
  "apiFetch("
  "\$fetch("
  "useApiClient"
  "useFetch("
  "await fetch("
  "axios\."
  "await api\."
  "\$api\."
)

echo "=== Scanning for fake success notifications (success toast + no API call) ==="

found=0

for success_pattern in "${SUCCESS_PATTERNS[@]}"; do
  # Find files that contain a success notification
  success_files=$(grep -rl \
    --include="*.vue" \
    --include="*.ts" \
    --exclude-dir=node_modules \
    --exclude-dir=.nuxt \
    --exclude-dir=dist \
    --exclude-dir=.venv \
    -E "$success_pattern" "$UI_SOURCE_DIR" 2>/dev/null || true)

  for file in $success_files; do
    # Skip test files — mocked toasts in tests are expected
    if [[ "$file" == *".test."* ]] || [[ "$file" == *".spec."* ]]; then
      continue
    fi

    has_api_call=false
    for api_pattern in "${API_CALL_PATTERNS[@]}"; do
      if grep -qE "$api_pattern" "$file" 2>/dev/null; then
        has_api_call=true
        break
      fi
    done

    if [[ "$has_api_call" == "false" ]]; then
      echo ""
      echo "--- Fake success notification in: $file ---"
      echo "  SUCCESS toast/notify found, but NO outbound API call detected."
      echo ""
      grep -nE "$success_pattern" "$file" | head -5 | sed 's/^/  /'
      echo ""
      echo "  Tip: If the endpoint does not yet exist, raise a formal blocker"
      echo "       at .hyperloop/blockers/ and REMOVE the fake success path."
      found=$((found + 1))
    fi
  done
done

echo ""
if [[ $found -gt 0 ]]; then
  echo "FAIL: $found file(s) emit success notifications without any API call."
  echo ""
  echo "Emitting 'Created!' / 'Saved!' toasts without persisting data is a stub."
  echo "The user believes the action succeeded — it did not."
  echo ""
  echo "Required fix: either wire the handler to the real API endpoint, or remove"
  echo "the success notification and raise a formal blocker describing the dependency."
  exit 1
else
  echo "PASS: All success notifications are co-located with real API calls."
  exit 0
fi
