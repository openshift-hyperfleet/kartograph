#!/bin/bash
set -euo pipefail

export XDG_CONFIG_HOME="${KARTOGRAPH_EXTRACTION_RUNTIME_OPENSHELL_XDG_CONFIG_HOME:-/var/openshell/xdg}"
export XDG_STATE_HOME="${KARTOGRAPH_EXTRACTION_RUNTIME_OPENSHELL_XDG_STATE_HOME:-/var/openshell/state}"

if [[ "${KARTOGRAPH_EXTRACTION_RUNTIME_BACKEND:-}" == "openshell" ]] && command -v openshell >/dev/null 2>&1; then
  gateway_name="${KARTOGRAPH_EXTRACTION_RUNTIME_OPENSHELL_GATEWAY_NAME:-openshell}"
  gateway_url="${KARTOGRAPH_EXTRACTION_RUNTIME_OPENSHELL_GATEWAY_URL:-https://127.0.0.1:17670}"

  # openshell-bootstrap (init container) stages mTLS certs into
  # XDG_CONFIG_HOME but has no openshell CLI available (its image only
  # ships the openshell-gateway server binary), so it cannot register
  # the gateway itself. Registration happens here instead, where the
  # client CLI is present. Idempotent: skip if already registered, since
  # XDG_CONFIG_HOME/XDG_STATE_HOME are emptyDir volumes that persist
  # across `api` container restarts within the same pod.
  if ! openshell gateway info --name "${gateway_name}" >/dev/null 2>&1; then
    openshell gateway add "${gateway_url}" --local --name "${gateway_name}"
  fi

  for attempt in $(seq 1 90); do
    if openshell status 2>/dev/null | grep -q "Connected"; then
      break
    fi
    if [[ "${attempt}" -eq 90 ]]; then
      echo "OpenShell gateway did not become reachable on ${gateway_url}" >&2
      exit 1
    fi
    sleep 1
  done
fi

exec uvicorn main:app --host 0.0.0.0 --port 8000
