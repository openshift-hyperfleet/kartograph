"""Secure enclave service for MCP query authorization.

Applies per-entity SpiceDB authorization to raw Cypher query results,
redacting entities the requesting user is not authorized to view while
preserving graph topology (spec: Secure enclave redaction).

Authorization model:
    Each node and edge carries a ``knowledge_graph_id`` property.
    The service checks VIEW permission on the corresponding KnowledgeGraph
    via SpiceDB. Entities whose ``knowledge_graph_id`` is absent, empty, None,
    or non-string are denied immediately without a round-trip to SpiceDB.

Redaction rules:
    - Authorized node:   full NodeDict returned
    - Unauthorized node: ``{"id": node_id}`` (all other fields stripped)
    - Authorized edge:   full EdgeDict returned
    - Unauthorized edge: ``{"id": edge_id, "start_id": ..., "end_id": ...}``
                         (all other fields stripped, topology preserved)
    - Scalar values:     passed through unchanged (no entity to authorize)
    - Map results:       each nested node/edge value is recursively evaluated

Performance:
    Permission results are cached per ``knowledge_graph_id`` within a single
    ``apply_redaction`` call to avoid redundant SpiceDB round-trips when
    multiple entities share the same parent KnowledgeGraph.

Fail-safe:
    Any SpiceDB error during permission checking causes the entity to be
    redacted. Data is never exposed on errors.
"""

from __future__ import annotations

from typing import Any

from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)

from query.domain.value_objects import QueryResultRow


def _is_edge_dict(value: dict[str, Any]) -> bool:
    """Return True if *value* looks like an EdgeDict.

    EdgeDict is distinguished from NodeDict by the presence of both
    ``start_id`` and ``end_id`` alongside ``id``, ``label``, and
    ``properties``.
    """
    return (
        "id" in value
        and "label" in value
        and "properties" in value
        and "start_id" in value
        and "end_id" in value
    )


def _is_node_dict(value: dict[str, Any]) -> bool:
    """Return True if *value* looks like a NodeDict.

    NodeDict has ``id``, ``label``, and ``properties`` but NOT
    ``start_id`` / ``end_id`` (those distinguish EdgeDict).
    """
    return (
        "id" in value
        and "label" in value
        and "properties" in value
        and "start_id" not in value
        and "end_id" not in value
    )


class MCPQuerySecureEnclave:
    """Applies per-entity SpiceDB authorization to MCP Cypher query results.

    Redacts unauthorized entities while preserving graph topology.

    Args:
        authz:   Authorization provider (SpiceDB client or compatible).
        user_id: The ID of the requesting user (MCP auth context).
    """

    def __init__(self, authz: AuthorizationProvider, user_id: str) -> None:
        self._authz = authz
        self._user_id = user_id
        # Cache: kg_id → bool (True = user has VIEW permission)
        self._permission_cache: dict[str, bool] = {}

    async def apply_redaction(self, rows: list[QueryResultRow]) -> list[QueryResultRow]:
        """Apply secure enclave authorization to a list of result rows.

        Each row is processed independently. Within a row, all node and edge
        values are authorized against SpiceDB (with per-kg_id caching).

        Args:
            rows: Raw query result rows from the graph repository.

        Returns:
            The same rows with unauthorized entities redacted according
            to the spec redaction rules.
        """
        return [await self._process_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Private — row / value processing
    # ------------------------------------------------------------------

    async def _process_row(self, row: QueryResultRow) -> QueryResultRow:
        """Process a single result row, recursing into each value."""
        result: QueryResultRow = {}
        for key, value in row.items():
            result[key] = await self._process_value(value)
        return result

    async def _process_value(self, value: Any) -> Any:
        """Recursively process a single value.

        Dispatch table:
        - EdgeDict → ``_authorize_edge``
        - NodeDict → ``_authorize_node``
        - dict     → recurse into values (map result)
        - other    → pass through (scalar)

        EdgeDict is checked BEFORE NodeDict because EdgeDict is a strict
        superset of NodeDict's fields.
        """
        if isinstance(value, dict):
            if _is_edge_dict(value):
                return await self._authorize_edge(value)
            if _is_node_dict(value):
                return await self._authorize_node(value)
            # Plain dict (map result or nested structure) — recurse
            return {k: await self._process_value(v) for k, v in value.items()}

        # Scalar (int, str, float, bool, None, list, …) — no entity to check
        return value

    # ------------------------------------------------------------------
    # Private — entity authorization
    # ------------------------------------------------------------------

    async def _authorize_node(self, node: dict[str, Any]) -> dict[str, Any]:
        """Return full NodeDict if authorized, or ``{"id": ...}`` if not."""
        kg_id = self._extract_kg_id(node.get("properties", {}))
        if kg_id is None or not await self._check_kg_view(kg_id):
            return {"id": node["id"]}
        return node

    async def _authorize_edge(self, edge: dict[str, Any]) -> dict[str, Any]:
        """Return full EdgeDict if authorized, or minimal topology dict if not."""
        kg_id = self._extract_kg_id(edge.get("properties", {}))
        if kg_id is None or not await self._check_kg_view(kg_id):
            return {
                "id": edge["id"],
                "start_id": edge["start_id"],
                "end_id": edge["end_id"],
            }
        return edge

    # ------------------------------------------------------------------
    # Private — SpiceDB permission check (cached)
    # ------------------------------------------------------------------

    async def _check_kg_view(self, kg_id: str) -> bool:
        """Return True if the user has VIEW permission on *kg_id* (cached).

        Any SpiceDB error causes the method to return False (fail-safe).
        """
        if kg_id in self._permission_cache:
            return self._permission_cache[kg_id]

        try:
            has_permission = await self._authz.check_permission(
                resource=format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id),
                permission=Permission.VIEW,
                subject=format_subject(ResourceType.USER, self._user_id),
            )
        except Exception:
            # Fail-safe: any error → deny (do not expose data on errors)
            has_permission = False

        self._permission_cache[kg_id] = has_permission
        return has_permission

    # ------------------------------------------------------------------
    # Private — helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_kg_id(properties: Any) -> str | None:
        """Extract and validate the knowledge_graph_id from entity properties.

        Returns None if the value is absent, None, non-string, or empty —
        all of which trigger immediate denial per the spec.
        """
        if not isinstance(properties, dict):
            return None
        kg_id = properties.get("knowledge_graph_id")
        if not kg_id or not isinstance(kg_id, str):
            return None
        return kg_id
