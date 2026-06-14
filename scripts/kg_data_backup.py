#!/usr/bin/env python3
"""Capture and restore a single Knowledge Graph from a Kartograph dev instance.

Backs up PostgreSQL metadata, encrypted credentials, Apache AGE graph data
(nodes and edges scoped by knowledge_graph_id), and SpiceDB authorization
tuples for the KG and its data sources.

Usage:
    uv run python scripts/kg_data_backup.py capture <knowledge-graph-id>
    uv run python scripts/kg_data_backup.py restore <knowledge-graph-id> [backup-id|latest] --yes
    uv run python scripts/kg_data_backup.py list <knowledge-graph-id>

Environment (defaults match `make dev` / env/postgres.env):
    KARTOGRAPH_DB_HOST, KARTOGRAPH_DB_PORT, KARTOGRAPH_DB_DATABASE,
    KARTOGRAPH_DB_USERNAME, KARTOGRAPH_DB_PASSWORD
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKUP_ROOT = REPO_ROOT / ".kartograph" / "kg-backups"
POSTGRES_ENV = REPO_ROOT / "env" / "postgres.env"
SPICEDB_ENV = REPO_ROOT / "env" / "spicedb.env"

POSTGRES_TABLES_IN_RESTORE_ORDER = [
    "knowledge_graphs",
    "encrypted_credentials",
    "data_sources",
    "data_source_sync_runs",
    "knowledge_graph_type_definitions",
    "extraction_runs",
    "extraction_jobs",
    "extraction_agent_sessions",
]

ULID_PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def db_settings() -> dict[str, str]:
    file_values = load_env_file(POSTGRES_ENV)
    host = os.getenv("KARTOGRAPH_DB_HOST", file_values.get("POSTGRES_HOST", "localhost"))
    if host == "postgres":
        host = "localhost"
    return {
        "host": host,
        "port": os.getenv("KARTOGRAPH_DB_PORT", file_values.get("POSTGRES_PORT", "5432")),
        "database": os.getenv(
            "KARTOGRAPH_DB_DATABASE", file_values.get("POSTGRES_DB", "kartograph")
        ),
        "user": os.getenv(
            "KARTOGRAPH_DB_USERNAME", file_values.get("POSTGRES_USER", "kartograph")
        ),
        "password": os.getenv(
            "KARTOGRAPH_DB_PASSWORD", file_values.get("POSTGRES_PASSWORD", "")
        ),
    }


def spicedb_database_name() -> str:
    return "spicedb"


def connect(database: str | None = None) -> psycopg2.extensions.connection:
    settings = db_settings()
    return psycopg2.connect(
        host=settings["host"],
        port=settings["port"],
        dbname=database or settings["database"],
        user=settings["user"],
        password=settings["password"],
    )


def timestamp_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def git_commit_short() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def validate_kg_id(kg_id: str) -> None:
    if not ULID_PATTERN.match(kg_id):
        raise SystemExit(f"Invalid knowledge graph id: {kg_id}")


def json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, memoryview):
        return base64.b64encode(value.tobytes()).decode("ascii")
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(bytes(value)).decode("ascii")
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=json_default),
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def agtype_to_python(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text.strip('"')
        return text.strip('"')
    return value


def fetch_kg_metadata(conn: psycopg2.extensions.connection, kg_id: str) -> dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM knowledge_graphs WHERE id = %s",
            (kg_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise SystemExit(f"Knowledge graph not found: {kg_id}")
        return dict(row)


def fetch_table_rows(
    conn: psycopg2.extensions.connection,
    table: str,
    *,
    where_sql: str,
    params: tuple[Any, ...],
) -> list[dict[str, Any]]:
    query = sql.SQL("SELECT * FROM {} WHERE ").format(sql.Identifier(table)) + sql.SQL(where_sql)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def fetch_postgres_payload(
    conn: psycopg2.extensions.connection, kg_id: str, tenant_id: str
) -> dict[str, list[dict[str, Any]]]:
    data_sources = fetch_table_rows(
        conn,
        "data_sources",
        where_sql="knowledge_graph_id = %s",
        params=(kg_id,),
    )
    data_source_ids = tuple(row["id"] for row in data_sources)
    credential_paths = tuple(
        row["credentials_path"] for row in data_sources if row.get("credentials_path")
    )

    sync_runs: list[dict[str, Any]] = []
    if data_source_ids:
        placeholders = sql.SQL(", ").join(sql.Placeholder() * len(data_source_ids))
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                sql.SQL("SELECT * FROM data_source_sync_runs WHERE data_source_id IN ({})").format(
                    placeholders
                ),
                data_source_ids,
            )
            sync_runs = [dict(row) for row in cur.fetchall()]

    credentials: list[dict[str, Any]] = []
    if credential_paths:
        placeholders = sql.SQL(", ").join(sql.Placeholder() * len(credential_paths))
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                sql.SQL(
                    "SELECT * FROM encrypted_credentials WHERE tenant_id = %s AND path IN ({})"
                ).format(placeholders),
                (tenant_id, *credential_paths),
            )
            credentials = [dict(row) for row in cur.fetchall()]

    return {
        "knowledge_graphs": fetch_table_rows(
            conn, "knowledge_graphs", where_sql="id = %s", params=(kg_id,)
        ),
        "data_sources": data_sources,
        "data_source_sync_runs": sync_runs,
        "knowledge_graph_type_definitions": fetch_table_rows(
            conn,
            "knowledge_graph_type_definitions",
            where_sql="knowledge_graph_id = %s",
            params=(kg_id,),
        ),
        "extraction_runs": fetch_table_rows(
            conn, "extraction_runs", where_sql="knowledge_graph_id = %s", params=(kg_id,)
        ),
        "extraction_jobs": fetch_table_rows(
            conn, "extraction_jobs", where_sql="knowledge_graph_id = %s", params=(kg_id,)
        ),
        "extraction_agent_sessions": fetch_table_rows(
            conn,
            "extraction_agent_sessions",
            where_sql="knowledge_graph_id = %s",
            params=(kg_id,),
        ),
        "encrypted_credentials": credentials,
    }


def fetch_graph_payload(
    conn: psycopg2.extensions.connection, graph_name: str, kg_id: str
) -> dict[str, Any]:
    escaped_kg_id = cypher_escape(kg_id)
    escaped_graph_name = cypher_escape(graph_name)
    with conn.cursor() as cur:
        cur.execute("LOAD 'age'")
        cur.execute('SET search_path = ag_catalog, "$user", public')

        cur.execute(
            f"""
            SELECT * FROM cypher('{escaped_graph_name}', $$
                MATCH (n)
                WHERE n.knowledge_graph_id = '{escaped_kg_id}'
                RETURN id(n), label(n), properties(n)
            $$) AS (age_id agtype, label agtype, properties agtype)
            """
        )
        nodes = []
        node_age_ids: set[str] = set()
        for age_id, label, properties in cur.fetchall():
            age_id_text = str(agtype_to_python(age_id))
            label_text = str(agtype_to_python(label))
            props = agtype_to_python(properties)
            if not isinstance(props, dict):
                props = {}
            nodes.append(
                {
                    "age_id": age_id_text,
                    "label": label_text,
                    "properties": props,
                }
            )
            node_age_ids.add(age_id_text)

        cur.execute(
            f"""
            SELECT * FROM cypher('{escaped_graph_name}', $$
                MATCH (a)-[r]->(b)
                WHERE a.knowledge_graph_id = '{escaped_kg_id}'
                  AND b.knowledge_graph_id = '{escaped_kg_id}'
                RETURN id(r), label(r), id(a), id(b), properties(r)
            $$) AS (age_id agtype, label agtype, start_age_id agtype, end_age_id agtype, properties agtype)
            """
        )
        edges = []
        for age_id, label, start_age_id, end_age_id, properties in cur.fetchall():
            props = agtype_to_python(properties)
            if not isinstance(props, dict):
                props = {}
            edges.append(
                {
                    "age_id": str(agtype_to_python(age_id)),
                    "label": str(agtype_to_python(label)),
                    "start_age_id": str(agtype_to_python(start_age_id)),
                    "end_age_id": str(agtype_to_python(end_age_id)),
                    "properties": props,
                }
            )

    return {
        "graph_name": graph_name,
        "knowledge_graph_id": kg_id,
        "nodes": nodes,
        "edges": edges,
    }


def fetch_spicedb_payload(
    spicedb_conn: psycopg2.extensions.connection,
    kg_id: str,
    data_source_ids: list[str],
) -> list[dict[str, str]]:
    with spicedb_conn.cursor(cursor_factory=RealDictCursor) as cur:
        if data_source_ids:
            placeholders = sql.SQL(", ").join(sql.Placeholder() * len(data_source_ids))
            query = sql.SQL(
                """
                SELECT namespace, object_id, relation, userset_namespace, userset_object_id, userset_relation
                FROM relation_tuple
                WHERE deleted_xid = '9223372036854775807'::xid8
                  AND (
                    (namespace = 'knowledge_graph' AND object_id = %s)
                    OR (namespace = 'data_source' AND object_id IN ({}))
                  )
                ORDER BY namespace, object_id, relation
                """
            ).format(placeholders)
            cur.execute(query, (kg_id, *data_source_ids))
        else:
            cur.execute(
                """
                SELECT namespace, object_id, relation, userset_namespace, userset_object_id, userset_relation
                FROM relation_tuple
                WHERE deleted_xid = '9223372036854775807'::xid8
                  AND namespace = 'knowledge_graph'
                  AND object_id = %s
                ORDER BY namespace, object_id, relation
                """,
                (kg_id,),
            )
        return [dict(row) for row in cur.fetchall()]


def backup_dir_for(kg_id: str, backup_id: str) -> Path:
    return BACKUP_ROOT / kg_id / backup_id


def resolve_backup_dir(kg_id: str, requested: str) -> Path:
    kg_root = BACKUP_ROOT / kg_id
    if requested == "latest":
        latest = kg_root / "latest"
        if latest.is_symlink():
            return latest.resolve()
        if latest.is_dir():
            return latest
        candidates = sorted(p for p in kg_root.iterdir() if p.is_dir() and p.name != "latest")
        if not candidates:
            raise SystemExit(f"No backups found for knowledge graph {kg_id}")
        return candidates[-1]

    explicit = kg_root / requested
    if explicit.is_dir():
        return explicit
    if Path(requested).is_dir():
        return Path(requested)
    raise SystemExit(f"Backup not found: {requested}")


def write_manifest(
    backup_dir: Path,
    *,
    kg_id: str,
    compose_project: str,
    kg_name: str,
    tenant_id: str,
    workspace_id: str,
    counts: dict[str, int],
) -> None:
    manifest = {
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "compose_project": compose_project,
        "git_commit": git_commit_short(),
        "knowledge_graph_id": kg_id,
        "knowledge_graph_name": kg_name,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "age_graph_name": f"tenant_{tenant_id}",
        "counts": counts,
    }
    write_json(backup_dir / "manifest.json", manifest)


def cmd_capture(args: argparse.Namespace) -> None:
    validate_kg_id(args.knowledge_graph_id)
    kg_id = args.knowledge_graph_id

    conn = connect()
    try:
        kg = fetch_kg_metadata(conn, kg_id)
        tenant_id = kg["tenant_id"]
        workspace_id = kg["workspace_id"]
        graph_name = f"tenant_{tenant_id}"

        postgres_payload = fetch_postgres_payload(conn, kg_id, tenant_id)
        graph_payload = fetch_graph_payload(conn, graph_name, kg_id)
    finally:
        conn.close()

    spicedb_conn = connect(spicedb_database_name())
    try:
        spicedb_payload = fetch_spicedb_payload(
            spicedb_conn,
            kg_id,
            [row["id"] for row in postgres_payload["data_sources"]],
        )
    finally:
        spicedb_conn.close()

    backup_id = timestamp_utc()
    backup_dir = backup_dir_for(kg_id, backup_id)
    backup_dir.mkdir(parents=True, exist_ok=True)

    write_json(backup_dir / "postgres.json", postgres_payload)
    write_json(backup_dir / "graph.json", graph_payload)
    write_json(backup_dir / "spicedb.json", spicedb_payload)

    counts = {
        "postgres_knowledge_graphs": len(postgres_payload["knowledge_graphs"]),
        "postgres_data_sources": len(postgres_payload["data_sources"]),
        "postgres_data_source_sync_runs": len(postgres_payload["data_source_sync_runs"]),
        "postgres_type_definitions": len(postgres_payload["knowledge_graph_type_definitions"]),
        "postgres_extraction_runs": len(postgres_payload["extraction_runs"]),
        "postgres_extraction_jobs": len(postgres_payload["extraction_jobs"]),
        "postgres_extraction_agent_sessions": len(postgres_payload["extraction_agent_sessions"]),
        "postgres_encrypted_credentials": len(postgres_payload["encrypted_credentials"]),
        "graph_nodes": len(graph_payload["nodes"]),
        "graph_edges": len(graph_payload["edges"]),
        "spicedb_relationships": len(spicedb_payload),
    }
    write_manifest(
        backup_dir,
        kg_id=kg_id,
        compose_project=args.compose_project,
        kg_name=kg["name"],
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        counts=counts,
    )

    latest = BACKUP_ROOT / kg_id / "latest"
    latest.parent.mkdir(parents=True, exist_ok=True)
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(backup_id, target_is_directory=True)

    print(f"Captured knowledge graph '{kg['name']}' ({kg_id})")
    print(f"Backup directory: {backup_dir}")
    print("Counts:")
    for key, value in counts.items():
        print(f"  {key}: {value}")


def decode_row_values(row: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(row)
    if "encrypted_value" in decoded and isinstance(decoded["encrypted_value"], str):
        decoded["encrypted_value"] = base64.b64decode(decoded["encrypted_value"])
    return decoded


def insert_rows(
    conn: psycopg2.extensions.connection,
    table: str,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = sql.SQL(", ").join(sql.Placeholder() * len(columns))
    statement = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        placeholders,
    )
    with conn.cursor() as cur:
        for row in rows:
            values = [decode_row_values(row)[column] for column in columns]
            cur.execute(statement, values)


def delete_existing_kg_data(conn: psycopg2.extensions.connection, kg_id: str, graph_name: str) -> None:
    escaped_kg_id = cypher_escape(kg_id)
    escaped_graph_name = cypher_escape(graph_name)
    with conn.cursor() as cur:
        cur.execute("LOAD 'age'")
        cur.execute('SET search_path = ag_catalog, "$user", public')
        cur.execute(
            f"""
            SELECT * FROM cypher('{escaped_graph_name}', $$
                MATCH (n)
                WHERE n.knowledge_graph_id = '{escaped_kg_id}'
                DETACH DELETE n
            $$) AS (result agtype)
            """
        )

        cur.execute("DELETE FROM extraction_agent_sessions WHERE knowledge_graph_id = %s", (kg_id,))
        cur.execute("DELETE FROM extraction_jobs WHERE knowledge_graph_id = %s", (kg_id,))
        cur.execute("DELETE FROM extraction_runs WHERE knowledge_graph_id = %s", (kg_id,))
        cur.execute(
            "DELETE FROM knowledge_graph_type_definitions WHERE knowledge_graph_id = %s",
            (kg_id,),
        )
        cur.execute(
            """
            DELETE FROM data_source_sync_runs
            WHERE data_source_id IN (SELECT id FROM data_sources WHERE knowledge_graph_id = %s)
            """,
            (kg_id,),
        )
        cur.execute(
            """
            DELETE FROM encrypted_credentials
            WHERE path IN (
                SELECT credentials_path FROM data_sources
                WHERE knowledge_graph_id = %s AND credentials_path IS NOT NULL
            )
            """,
            (kg_id,),
        )
        cur.execute("DELETE FROM data_sources WHERE knowledge_graph_id = %s", (kg_id,))
        cur.execute("DELETE FROM knowledge_graphs WHERE id = %s", (kg_id,))


def ensure_label_exists(cur: Any, graph_name: str, label: str, *, edge: bool) -> None:
    cur.execute(
        """
        SELECT l.id
        FROM ag_catalog.ag_label l
        JOIN ag_catalog.ag_graph g ON l.graph = g.graphid
        WHERE g.name = %s AND l.name = %s
        """,
        (graph_name, label),
    )
    if cur.fetchone():
        return
    if edge:
        cur.execute("SELECT ag_catalog.create_elabel(%s, %s)", (graph_name, label))
    else:
        cur.execute("SELECT ag_catalog.create_vlabel(%s, %s)", (graph_name, label))


def cypher_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def cypher_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(cypher_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        inner = ", ".join(f"{key}: {cypher_literal(item)}" for key, item in value.items())
        return "{" + inner + "}"
    text = cypher_escape(str(value))
    return f"'{text}'"


def restore_graph_nodes(
    conn: psycopg2.extensions.connection, graph_payload: dict[str, Any]
) -> None:
    graph_name = graph_payload["graph_name"]
    with conn.cursor() as cur:
        cur.execute("LOAD 'age'")
        cur.execute('SET search_path = ag_catalog, "$user", public')

        labels = sorted({node["label"] for node in graph_payload["nodes"]})
        for label in labels:
            ensure_label_exists(cur, graph_name, label, edge=False)

        for node in graph_payload["nodes"]:
            label = node["label"]
            props_map = ", ".join(
                f"{key}: {cypher_literal(value)}" for key, value in node["properties"].items()
            )
            query = f"""
                SELECT * FROM cypher('{cypher_escape(graph_name)}', $$
                    CREATE (n:{label} {{{props_map}}})
                    RETURN id(n)
                $$) AS (age_id agtype)
            """
            cur.execute(query)

        edge_labels = sorted({edge["label"] for edge in graph_payload["edges"]})
        for label in edge_labels:
            ensure_label_exists(cur, graph_name, label, edge=True)

        for edge in graph_payload["edges"]:
            label = edge["label"]
            props_map = ", ".join(
                f"{key}: {cypher_literal(value)}" for key, value in edge["properties"].items()
            )
            start_id = cypher_escape(edge["start_age_id"])
            end_id = cypher_escape(edge["end_age_id"])
            if props_map:
                create_edge = f"""
                    MATCH (a), (b)
                    WHERE id(a) = {start_id} AND id(b) = {end_id}
                    CREATE (a)-[r:{label} {{{props_map}}}]->(b)
                    RETURN id(r)
                """
            else:
                create_edge = f"""
                    MATCH (a), (b)
                    WHERE id(a) = {start_id} AND id(b) = {end_id}
                    CREATE (a)-[r:{label}]->(b)
                    RETURN id(r)
                """
            query = f"""
                SELECT * FROM cypher('{cypher_escape(graph_name)}', $$
                    {create_edge}
                $$) AS (age_id agtype)
            """
            cur.execute(query)


def spicedb_settings() -> tuple[str, str]:
    env_values = load_env_file(SPICEDB_ENV)
    token = os.getenv("SPICEDB_GRPC_PRESHARED_KEY", env_values.get("SPICEDB_GRPC_PRESHARED_KEY", "changeme"))
    network = os.getenv("KARTOGRAPH_COMPOSE_NETWORK", "kartograph_kartograph")
    return token, network


def restore_spicedb_relationships(relationships: list[dict[str, str]]) -> None:
    token, network = spicedb_settings()
    certs_dir = REPO_ROOT / "certs"
    for rel in relationships:
        resource = f"{rel['namespace']}:{rel['object_id']}"
        subject = f"{rel['userset_namespace']}:{rel['userset_object_id']}"
        if rel["userset_relation"] and rel["userset_relation"] != "...":
            subject = f"{subject}#{rel['userset_relation']}"
        cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            network,
            "-e",
            "ZED_ENDPOINT=spicedb:50051",
            "-e",
            f"ZED_TOKEN={token}",
            "-e",
            "GRPC_DEFAULT_SSL_ROOTS_FILE_PATH=/certs/spicedb-cert.pem",
            "-v",
            f"{certs_dir}:/certs:ro",
            "authzed/zed:latest",
            "--no-verify-ca",
            "relationship",
            "touch",
            resource,
            rel["relation"],
            subject,
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)


def cmd_restore(args: argparse.Namespace) -> None:
    validate_kg_id(args.knowledge_graph_id)
    backup_dir = resolve_backup_dir(args.knowledge_graph_id, args.backup_id)
    manifest = read_json(backup_dir / "manifest.json")
    postgres_payload = read_json(backup_dir / "postgres.json")
    graph_payload = read_json(backup_dir / "graph.json")
    spicedb_payload = read_json(backup_dir / "spicedb.json")

    if not args.yes:
        print(f"This will restore knowledge graph {args.knowledge_graph_id} from:")
        print(f"  {backup_dir}")
        if args.replace:
            print("Existing data for this knowledge graph will be deleted first.")
        reply = input("Continue? [y/N] ").strip().lower()
        if reply not in {"y", "yes"}:
            raise SystemExit("Aborted.")

    conn = connect()
    try:
        conn.autocommit = False
        if args.replace:
            delete_existing_kg_data(conn, args.knowledge_graph_id, graph_payload["graph_name"])

        for table in POSTGRES_TABLES_IN_RESTORE_ORDER:
            insert_rows(conn, table, postgres_payload.get(table, []))

        restore_graph_nodes(conn, graph_payload)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    restore_spicedb_relationships(spicedb_payload)

    print(f"Restored knowledge graph '{manifest.get('knowledge_graph_name', args.knowledge_graph_id)}'")
    print(f"From backup: {backup_dir}")


def cmd_list(args: argparse.Namespace) -> None:
    validate_kg_id(args.knowledge_graph_id)
    kg_root = BACKUP_ROOT / args.knowledge_graph_id
    if not kg_root.exists():
        print(f"No backups yet for knowledge graph {args.knowledge_graph_id}")
        return
    print(f"Backups for knowledge graph {args.knowledge_graph_id} in {kg_root}:")
    for path in sorted(p for p in kg_root.iterdir() if p.is_dir() and p.name != "latest"):
        manifest_path = path / "manifest.json"
        if manifest_path.exists():
            manifest = read_json(manifest_path)
            counts = manifest.get("counts", {})
            print(
                f"  {path.name}  nodes={counts.get('graph_nodes', '?')} "
                f"data_sources={counts.get('postgres_data_sources', '?')} "
                f"name={manifest.get('knowledge_graph_name', '?')}"
            )
        else:
            print(f"  {path.name}")
    latest = kg_root / "latest"
    if latest.is_symlink():
        print(f"\nlatest -> {os.readlink(latest)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture", help="Capture a knowledge graph backup")
    capture.add_argument("knowledge_graph_id")
    capture.add_argument(
        "--compose-project",
        default=os.getenv("COMPOSE_PROJECT", "kartograph"),
        help="Docker compose project name (stored in manifest metadata)",
    )
    capture.set_defaults(func=cmd_capture)

    restore = subparsers.add_parser("restore", help="Restore a knowledge graph backup")
    restore.add_argument("knowledge_graph_id")
    restore.add_argument("backup_id", nargs="?", default="latest")
    restore.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing data for this knowledge graph before restoring",
    )
    restore.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    restore.set_defaults(func=cmd_restore)

    list_cmd = subparsers.add_parser("list", help="List backups for a knowledge graph")
    list_cmd.add_argument("knowledge_graph_id")
    list_cmd.set_defaults(func=cmd_list)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
