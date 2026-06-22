#!/bin/bash
set -euo pipefail

export XDG_CONFIG_HOME="${KARTOGRAPH_EXTRACTION_RUNTIME_OPENSHELL_XDG_CONFIG_HOME:-/var/openshell/xdg}"
export XDG_STATE_HOME="${KARTOGRAPH_EXTRACTION_RUNTIME_OPENSHELL_XDG_STATE_HOME:-/var/openshell/state}"

if [[ "${KARTOGRAPH_EXTRACTION_RUNTIME_BACKEND:-}" == "openshell" ]] && command -v openshell >/dev/null 2>&1; then
  for attempt in $(seq 1 90); do
    if openshell status 2>/dev/null | grep -q "Connected"; then
      break
    fi
    if [[ "${attempt}" -eq 90 ]]; then
      echo "OpenShell gateway did not become reachable on ${KARTOGRAPH_EXTRACTION_RUNTIME_OPENSHELL_GATEWAY_URL:-https://127.0.0.1:17670}" >&2
      exit 1
    fi
    sleep 1
  done
fi

exec uvicorn main:app --host 0.0.0.0 --port 8000
