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
  # client CLI is present. Idempotent: skip if already registered AND
  # still pointing at the expected endpoint, since XDG_CONFIG_HOME/
  # XDG_STATE_HOME are emptyDir volumes that persist across `api`
  # container restarts within the same pod. Re-register (rather than
  # merely checking existence via `gateway info`) if the stored endpoint
  # has drifted from KARTOGRAPH_EXTRACTION_RUNTIME_OPENSHELL_GATEWAY_URL,
  # otherwise a stale registration from a previous rollout would leave
  # the pod pointed at an unreachable gateway.
  gateway_metadata="${XDG_CONFIG_HOME}/openshell/gateways/${gateway_name}/metadata.json"
  registered_url=""
  if [[ -f "${gateway_metadata}" ]]; then
    registered_url="$(python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as f:
        print(json.load(f).get('gateway_endpoint', ''))
except Exception:
    pass
" "${gateway_metadata}" 2>/dev/null || true)"
  fi
  if [[ "${registered_url}" != "${gateway_url}" ]]; then
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
