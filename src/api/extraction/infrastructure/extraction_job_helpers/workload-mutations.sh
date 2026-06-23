#!/usr/bin/env bash
# Kartograph extraction job helper — validate/apply JSONL via workload API.
# Writes mutations/result.json (agentic-ci verdict artifact).
#
# Usage:
#   helpers/workload-mutations.sh validate mutations/batch.jsonl
#   helpers/workload-mutations.sh apply mutations/batch.jsonl
set -euo pipefail

ACTION="${1:-}"
JSONL_PATH="${2:-}"
WORKDIR="${KARTOGRAPH_WORKSPACE:-/workspace}"

python3 - "${ACTION}" "${JSONL_PATH}" "${WORKDIR}" <<'PY'
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

action, jsonl_path, workdir = sys.argv[1:4]
workdir_path = Path(workdir)
context_path = workdir_path / "job-context.json"
result_path = workdir_path / "mutations" / "result.json"


def write_result(payload: dict) -> None:
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    json.dump(payload, sys.stdout, indent=2)
    print()


def fail(message: str, *, http_status: int | None = None) -> None:
    payload = {
        "action": action,
        "applied": False,
        "operations_applied": 0,
        "valid": False,
        "operation_count": 0,
        "errors": [message],
        "http_status": http_status,
    }
    write_result(payload)
    raise SystemExit(1)


if action not in {"validate", "apply"}:
    fail("first argument must be validate or apply")
jsonl_file = Path(jsonl_path)
if not jsonl_file.is_file():
    fail(f"JSONL file not found: {jsonl_path}")
if not context_path.is_file():
    fail("missing job-context.json in workspace")

context = json.loads(context_path.read_text(encoding="utf-8"))
api_base = str(context["api_base_url"]).rstrip("/")
token = str(context["workload_token"])
jsonl = jsonl_file.read_text(encoding="utf-8")
endpoint = f"{api_base}/extraction/workloads/mutations/{action}"
body = json.dumps({"jsonl": jsonl}).encode("utf-8")
request = urllib.request.Request(
    endpoint,
    data=body,
    method="POST",
    headers={
        "Content-Type": "application/json",
        "X-Workload-Token": token,
    },
)

try:
    with urllib.request.urlopen(request, timeout=600) as response:
        http_status = response.status
        payload = json.loads(response.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    http_status = exc.code
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except json.JSONDecodeError:
        fail(f"workload API returned HTTP {http_status}", http_status=http_status)
    errors = payload.get("detail") or payload.get("errors") or [str(payload)]
    if isinstance(errors, str):
        errors = [errors]
    result = {
        "action": action,
        "applied": False,
        "operations_applied": 0,
        "valid": False,
        "operation_count": 0,
        "errors": [str(item) for item in errors],
        "http_status": http_status,
    }
    write_result(result)
    raise SystemExit(1)
except urllib.error.URLError as exc:
    fail(f"workload API request failed: {exc.reason}")

if action == "validate":
    result = {
        "action": "validate",
        "valid": bool(payload.get("valid")),
        "operation_count": int(payload.get("operation_count") or 0),
        "errors": [str(item) for item in payload.get("errors") or []],
        "http_status": http_status,
    }
else:
    operations_applied = int(payload.get("operations_applied") or 0)
    result = {
        "action": "apply",
        "applied": bool(payload.get("applied")),
        "operations_applied": operations_applied,
        "errors": [str(item) for item in payload.get("errors") or []],
        "http_status": http_status,
    }
    if not result["applied"] or operations_applied <= 0:
        write_result(result)
        raise SystemExit(1)

write_result(result)
PY
