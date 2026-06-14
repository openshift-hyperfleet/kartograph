#!/usr/bin/env bash
#
# Capture and restore a single Knowledge Graph from a Kartograph dev instance.
#
# Usage:
#   ./scripts/kg-data-backup.sh capture <knowledge-graph-id>
#   ./scripts/kg-data-backup.sh restore <knowledge-graph-id> [backup-id|latest] [--yes] [--replace]
#   ./scripts/kg-data-backup.sh list <knowledge-graph-id>
#
# Makefile shortcuts:
#   make kg-backup KG_ID=01KTYN8Q0RJS2CCQX044S4V96C
#   make kg-restore KG_ID=01KTYN8Q0RJS2CCQX044S4V96C
#   make kg-backup-list KG_ID=01KTYN8Q0RJS2CCQX044S4V96C
#
# Backups are written to .kartograph/kg-backups/<kg-id>/<timestamp>/ (gitignored).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

COMPOSE_PROJECT="${COMPOSE_PROJECT:-kartograph}"

usage() {
    cat <<'EOF'
Usage:
  kg-data-backup.sh capture <knowledge-graph-id>
  kg-data-backup.sh restore <knowledge-graph-id> [backup-id|latest] [--yes] [--replace]
  kg-data-backup.sh list <knowledge-graph-id>

Environment:
  COMPOSE_PROJECT   Docker compose project name (default: kartograph)

Examples:
  make kg-backup KG_ID=01KTYN8Q0RJS2CCQX044S4V96C
  make kg-restore KG_ID=01KTYN8Q0RJS2CCQX044S4V96C BACKUP=latest
  ./scripts/kg-data-backup.sh restore 01KTYN8Q0RJS2CCQX044S4V96C latest --replace --yes
EOF
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

postgres_container_id() {
    local container_id
    container_id="$(
        docker compose -p "$COMPOSE_PROJECT" \
            -f "$REPO_ROOT/compose.yaml" \
            -f "$REPO_ROOT/compose.dev.yaml" \
            ps -q postgres 2>/dev/null | head -n 1 || true
    )"
    if [[ -z "$container_id" ]]; then
        die "Postgres container not found for compose project '$COMPOSE_PROJECT'. Is 'make dev' running?"
    fi
    printf '%s' "$container_id"
}

ensure_dev_postgres() {
    postgres_container_id >/dev/null
}

run_python() {
    ensure_dev_postgres
    cd "$REPO_ROOT/src/api"
    COMPOSE_PROJECT="$COMPOSE_PROJECT" uv run python "$REPO_ROOT/scripts/kg_data_backup.py" "$@"
}

ACTION="${1:-}"
shift || true

case "$ACTION" in
    capture|restore|list)
        run_python "$ACTION" "$@"
        ;;
    ""|-h|--help|help)
        usage
        ;;
    *)
        die "Unknown command: ${ACTION}. Run with --help for usage."
        ;;
esac
