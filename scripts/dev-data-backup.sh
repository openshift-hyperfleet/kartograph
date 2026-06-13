#!/usr/bin/env bash
#
# Backup and restore Kartograph development databases (PostgreSQL).
#
# Captures the kartograph application database (metadata, ontology, AGE graph,
# IAM, outbox, etc.) and the spicedb authorization database. Optionally archives
# prepared JobPackage files from the host work dir.
#
# Usage:
#   ./scripts/dev-data-backup.sh backup [--project <compose-project>]
#   ./scripts/dev-data-backup.sh restore [--project <compose-project>] [backup-id|latest] [--yes]
#   ./scripts/dev-data-backup.sh list
#
# Makefile shortcuts: make dev-backup, make dev-restore, make dev-backup-list
#
# Default compose project is "kartograph" (standard `make dev`). Isolated instances
# use project names like "kg-my-feature" from dev-instance.sh:
#   COMPOSE_PROJECT=kg-my-feature ./scripts/dev-data-backup.sh backup

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_ROOT="$REPO_ROOT/.kartograph/backups"

COMPOSE_PROJECT="${COMPOSE_PROJECT:-kartograph}"
COMPOSE_FILES=(-f "$REPO_ROOT/compose.yaml" -f "$REPO_ROOT/compose.dev.yaml")
AUTO_CONFIRM=false
BACKUP_ID=""

# shellcheck disable=SC1091
source "$REPO_ROOT/env/postgres.env"

POSTGRES_USER="${POSTGRES_USER:-kartograph}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-kartograph_dev_password}"
APP_DATABASE="${POSTGRES_DB:-kartograph}"
AUTH_DATABASE="spicedb"

usage() {
    cat <<'EOF'
Usage:
  dev-data-backup.sh backup [--project <compose-project>]
  dev-data-backup.sh restore [--project <compose-project>] [backup-id|latest] [--yes]
  dev-data-backup.sh repair [--project <compose-project>]
  dev-data-backup.sh list

Environment:
  COMPOSE_PROJECT   Docker Compose project name (default: kartograph)

Examples:
  make dev-backup
  make dev-restore
  ./scripts/dev-data-backup.sh restore 2026-06-12T19-30-00Z
  COMPOSE_PROJECT=kg-kartograph ./scripts/dev-data-backup.sh backup
EOF
}

log() {
    printf '%s\n' "$*"
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

compose() {
    docker compose -p "$COMPOSE_PROJECT" "${COMPOSE_FILES[@]}" "$@"
}

postgres_container_id() {
    local container_id
    container_id="$(compose ps -q postgres 2>/dev/null | head -n 1 || true)"
    if [[ -z "$container_id" ]]; then
        die "Postgres container not found for compose project '$COMPOSE_PROJECT'. Is 'make dev' running?"
    fi
    printf '%s' "$container_id"
}

postgres_exec() {
    local container_id
    container_id="$(postgres_container_id)"
    docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$container_id" "$@"
}

git_commit_short() {
    if git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown"
    else
        echo "unknown"
    fi
}

timestamp_utc() {
    date -u +"%Y-%m-%dT%H-%M-%SZ"
}

stop_dependent_services() {
    log "Stopping API and SpiceDB to release database connections..."
    compose stop api spicedb >/dev/null 2>&1 || true
}

start_dependent_services() {
    log "Starting API and SpiceDB..."
    compose start spicedb api >/dev/null 2>&1 || compose up -d spicedb api
}

terminate_db_connections() {
    local database="$1"
    postgres_exec psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${database}' AND pid <> pg_backend_pid();" \
        >/dev/null
}

dump_database() {
    local database="$1"
    local output_path="$2"
    log "  Dumping database '${database}'..."
    postgres_exec pg_dump -U "$POSTGRES_USER" -d "$database" -Fc --no-owner --no-acl \
        >"$output_path"
}

restore_database() {
    local database="$1"
    local dump_path="$2"
    local container_id
    container_id="$(postgres_container_id)"
    log "  Restoring database '${database}'..."
    terminate_db_connections "$database"
    # Stream the custom-format dump into the container (shell redirect via function breaks stdin).
    docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" "$container_id" \
        pg_restore -U "$POSTGRES_USER" -d "$database" --clean --if-exists --no-owner --no-acl \
        <"$dump_path"
}

maybe_backup_job_packages() {
    local backup_dir="$1"
    local source_dir="/tmp/kartograph/job_packages"
    if [[ -d "$source_dir" ]] && [[ -n "$(ls -A "$source_dir" 2>/dev/null || true)" ]]; then
        log "  Archiving prepared JobPackages from ${source_dir}..."
        tar -C "$(dirname "$source_dir")" -czf "$backup_dir/job_packages.tar.gz" "$(basename "$source_dir")"
    fi
}

maybe_restore_job_packages() {
    local backup_dir="$1"
    local archive="$backup_dir/job_packages.tar.gz"
    if [[ -f "$archive" ]]; then
        log "  Restoring prepared JobPackages to /tmp/kartograph/..."
        mkdir -p /tmp
        tar -C /tmp -xzf "$archive"
    fi
}

write_manifest() {
    local backup_dir="$1"
    local created_at
    created_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    cat >"$backup_dir/manifest.json" <<EOF
{
  "created_at": "${created_at}",
  "compose_project": "${COMPOSE_PROJECT}",
  "git_commit": "$(git_commit_short)",
  "databases": ["${APP_DATABASE}", "${AUTH_DATABASE}"],
  "files": {
    "kartograph_dump": "kartograph.dump",
    "spicedb_dump": "spicedb.dump",
    "job_packages_archive": "job_packages.tar.gz"
  }
}
EOF
}

cmd_backup() {
    local backup_id backup_dir
    backup_id="$(timestamp_utc)"
    backup_dir="$BACKUP_ROOT/$backup_id"
    mkdir -p "$backup_dir"

    log "Creating dev backup '${backup_id}' (project: ${COMPOSE_PROJECT})..."
    dump_database "$APP_DATABASE" "$backup_dir/kartograph.dump"
    dump_database "$AUTH_DATABASE" "$backup_dir/spicedb.dump"
    maybe_backup_job_packages "$backup_dir"
    write_manifest "$backup_dir"

    ln -sfn "$backup_id" "$BACKUP_ROOT/latest"
    log "Backup complete: ${backup_dir}"
    log "Latest symlink: ${BACKUP_ROOT}/latest"
}

resolve_backup_dir() {
    local requested="${1:-latest}"
    local backup_dir=""
    if [[ "$requested" == "latest" ]]; then
        if [[ -L "$BACKUP_ROOT/latest" ]]; then
            backup_dir="$(readlink -f "$BACKUP_ROOT/latest")"
        elif [[ -d "$BACKUP_ROOT/latest" ]]; then
            backup_dir="$BACKUP_ROOT/latest"
        else
            backup_dir="$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -n 1)"
        fi
    elif [[ -d "$BACKUP_ROOT/$requested" ]]; then
        backup_dir="$BACKUP_ROOT/$requested"
    elif [[ -d "$requested" ]]; then
        backup_dir="$requested"
    fi

    if [[ -z "$backup_dir" || ! -d "$backup_dir" ]]; then
        die "Backup not found: ${requested}. Run 'make dev-backup-list' to see available backups."
    fi
    if [[ ! -f "$backup_dir/kartograph.dump" || ! -f "$backup_dir/spicedb.dump" ]]; then
        die "Backup '${backup_dir}' is missing required dump files."
    fi
    printf '%s' "$backup_dir"
}

graph_is_queryable() {
    local graph_name="$1"
    postgres_exec psql -U "$POSTGRES_USER" -d "$APP_DATABASE" -v ON_ERROR_STOP=1 -c \
        "LOAD 'age'; SET search_path = ag_catalog, \"\$user\", public; SELECT * FROM cypher('${graph_name}', \$\$ RETURN 1 \$\$) as (x agtype);" \
        >/dev/null 2>&1
}

repair_tenant_age_graph() {
    local graph_name="$1"
    if graph_is_queryable "$graph_name"; then
        return 0
    fi
    log "  Repairing AGE graph ${graph_name}..."
    postgres_exec psql -U "$POSTGRES_USER" -d "$APP_DATABASE" -c \
        "LOAD 'age'; SET search_path = ag_catalog, \"\$user\", public; SELECT ag_catalog.drop_graph('${graph_name}', true);" \
        >/dev/null 2>&1 || true
    postgres_exec psql -U "$POSTGRES_USER" -d "$APP_DATABASE" -c \
        "LOAD 'age'; SET search_path = ag_catalog, \"\$user\", public; SELECT ag_catalog.create_graph('${graph_name}');"
}

repair_all_tenant_age_graphs() {
    log "Ensuring tenant AGE graphs are queryable after restore..."
    local graph_names=""
    graph_names="$(postgres_exec psql -U "$POSTGRES_USER" -d "$APP_DATABASE" -Atc \
        "SELECT DISTINCT graph_name FROM (
            SELECT name AS graph_name FROM ag_catalog.ag_graph WHERE name LIKE 'tenant_%'
            UNION
            SELECT 'tenant_' || id AS graph_name FROM tenants
        ) AS tenant_graphs ORDER BY graph_name")"
    while IFS= read -r graph_name; do
        [[ -z "$graph_name" ]] && continue
        repair_tenant_age_graph "$graph_name"
    done <<< "$graph_names"
}

cmd_restore() {
    local backup_dir
    backup_dir="$(resolve_backup_dir "$BACKUP_ID")"

    if [[ "$AUTO_CONFIRM" != "true" ]]; then
        log "This will REPLACE all data in databases '${APP_DATABASE}' and '${AUTH_DATABASE}'"
        log "for compose project '${COMPOSE_PROJECT}' from:"
        log "  ${backup_dir}"
        read -r -p "Continue? [y/N] " reply
        case "$reply" in
            y|Y|yes|YES) ;;
            *) log "Aborted."; exit 1 ;;
        esac
    fi

    stop_dependent_services
    log "Restoring dev backup from '${backup_dir}'..."
    restore_database "$APP_DATABASE" "$backup_dir/kartograph.dump"
    restore_database "$AUTH_DATABASE" "$backup_dir/spicedb.dump"
    repair_all_tenant_age_graphs
    maybe_restore_job_packages "$backup_dir"
    start_dependent_services

    log "Restore complete."
    log "If the dev UI shows an empty tenant, clear ~/.kartograph/token.json and sign in again."
    log "Note: repaired AGE graphs start empty — re-run instance prepopulation if needed."
}

cmd_list() {
    if [[ ! -d "$BACKUP_ROOT" ]]; then
        log "No backups yet. Run 'make dev-backup' first."
        exit 0
    fi
    log "Available backups in ${BACKUP_ROOT}:"
    find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d ! -name 'latest' -printf '%f\n' 2>/dev/null \
        | sort -r \
        || true
    if [[ -L "$BACKUP_ROOT/latest" ]]; then
        log ""
        log "latest -> $(readlink "$BACKUP_ROOT/latest")"
    fi
}

ACTION="${1:-}"
shift || true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project)
            COMPOSE_PROJECT="$2"
            shift 2
            ;;
        --yes|-y)
            AUTO_CONFIRM=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            if [[ -z "$BACKUP_ID" ]]; then
                BACKUP_ID="$1"
                shift
            else
                die "Unknown argument: $1"
            fi
            ;;
    esac
done

case "$ACTION" in
    backup)
        cmd_backup
        ;;
    restore)
        BACKUP_ID="${BACKUP_ID:-latest}"
        cmd_restore
        ;;
    repair)
        repair_all_tenant_age_graphs
        log "AGE graph repair complete."
        ;;
    list)
        cmd_list
        ;;
    ""|-h|--help|help)
        usage
        ;;
    *)
        die "Unknown command: ${ACTION}. Run with --help for usage."
        ;;
esac
