#!/usr/bin/env bash
#
# Delete Kartograph-owned OpenShell sandboxes left over from sticky GMA sessions
# and extraction jobs (e.g. after make down without end-session).
#
# Safe to run when openshell is not installed or the gateway is down — exits 0.

set -euo pipefail

KARTOGRAPH_SANDBOX_PATTERN='^kartograph-(gma|extract)-'

if ! command -v openshell >/dev/null 2>&1; then
    echo "openshell not on PATH; skipping Kartograph sandbox cleanup"
    exit 0
fi

names="$(openshell sandbox list --names 2>/dev/null | grep -E "$KARTOGRAPH_SANDBOX_PATTERN" || true)"
if [[ -z "${names// }" ]]; then
    echo "No Kartograph OpenShell sandboxes to clean up"
    exit 0
fi

echo "Cleaning up Kartograph OpenShell sandboxes..."
while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    echo "  → deleting $name"
    openshell sandbox delete "$name" 2>/dev/null || echo "    (delete failed or already gone: $name)"
done <<< "$names"
echo "OpenShell sandbox cleanup done."
