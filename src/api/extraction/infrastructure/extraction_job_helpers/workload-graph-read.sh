#!/usr/bin/env bash
# Kartograph extraction job helper — read graph state via workload API.
#
# Usage:
#   helpers/workload-graph-read.sh search-by-slug SLUG [--entity-type TYPE] [--out FILE]
#   helpers/workload-graph-read.sh instances ENTITY_TYPE [--limit N] [--offset N] [--out FILE]
#   helpers/workload-graph-read.sh ontology [--out FILE]
#   helpers/workload-graph-read.sh authoring-guide [--out FILE]
set -euo pipefail

COMMAND="${1:-}"
shift || true

WORKDIR="${KARTOGRAPH_WORKSPACE:-/workspace}"

python3 - "${COMMAND}" "${WORKDIR}" "$@" <<'PY'
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

command, workdir, *args = sys.argv[1:]
workdir_path = Path(workdir)
context_path = workdir_path / "job-context.json"


def fail(message: str, *, http_status: int | None = None) -> None:
    payload = {"error": message}
    if http_status is not None:
        payload["http_status"] = http_status
    json.dump(payload, sys.stdout, indent=2)
    print()
    raise SystemExit(1)


def parse_flags(argv: list[str]) -> tuple[dict[str, str], str | None]:
    flags: dict[str, str] = {}
    out_path: str | None = None
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--out":
            index += 1
            if index >= len(argv):
                fail("--out requires a file path")
            out_path = argv[index]
        elif token == "--entity-type":
            index += 1
            if index >= len(argv):
                fail("--entity-type requires a value")
            flags["entity_type"] = argv[index]
        elif token == "--limit":
            index += 1
            if index >= len(argv):
                fail("--limit requires a value")
            flags["limit"] = argv[index]
        elif token == "--offset":
            index += 1
            if index >= len(argv):
                fail("--offset requires a value")
            flags["offset"] = argv[index]
        else:
            fail(f"unexpected argument: {token}")
        index += 1
    return flags, out_path


def write_payload(payload: dict, out_path: str | None) -> None:
    text = json.dumps(payload, indent=2) + "\n"
    if out_path:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text, end="")


if command not in {
    "search-by-slug",
    "instances",
    "ontology",
    "authoring-guide",
}:
    fail("first argument must be search-by-slug, instances, ontology, or authoring-guide")
if not context_path.is_file():
    fail("missing job-context.json in workspace")

context = json.loads(context_path.read_text(encoding="utf-8"))
api_base = str(context["api_base_url"]).rstrip("/")
token = str(context["workload_token"])

if command == "search-by-slug":
    if not args or args[0].startswith("--"):
        fail("search-by-slug requires SLUG")
    slug = args[0]
    flags, out_path = parse_flags(args[1:])
    query = {"slug": slug}
    entity_type = flags.get("entity_type")
    if entity_type:
        query["entity_type"] = entity_type
    endpoint = f"{api_base}/extraction/workloads/graph/search-by-slug?{urlencode(query)}"
elif command == "instances":
    if not args or args[0].startswith("--"):
        fail("instances requires ENTITY_TYPE")
    entity_type = args[0]
    flags, out_path = parse_flags(args[1:])
    query = {"entity_type": entity_type}
    if "limit" in flags:
        query["limit"] = flags["limit"]
    if "offset" in flags:
        query["offset"] = flags["offset"]
    endpoint = f"{api_base}/extraction/workloads/graph/instances?{urlencode(query)}"
elif command == "ontology":
    flags, out_path = parse_flags(args)
    endpoint = f"{api_base}/extraction/workloads/schema/ontology"
else:
    flags, out_path = parse_flags(args)
    endpoint = f"{api_base}/extraction/workloads/schema/authoring-guide"

request = urllib.request.Request(
    endpoint,
    method="GET",
    headers={"X-Workload-Token": token},
)

try:
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
        detail = payload.get("detail") or payload
    except json.JSONDecodeError:
        detail = f"HTTP {exc.code}"
    fail(str(detail), http_status=exc.code)
except urllib.error.URLError as exc:
    fail(f"workload API request failed: {exc.reason}")

write_payload(payload, out_path)
PY
