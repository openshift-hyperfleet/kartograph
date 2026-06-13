"""Map graph storage failures to workload HTTP responses for GMA tools."""

from __future__ import annotations

from fastapi import HTTPException, status

from infrastructure.database.exceptions import GraphQueryError

_GRAPH_STORAGE_MARKERS = (
    "graph with oid",
    "does not exist",
    "ag_catalog",
)


def is_graph_storage_error(exc: BaseException) -> bool:
    """Return True when the failure indicates tenant AGE graph storage is unavailable."""
    if isinstance(exc, GraphQueryError):
        return True
    message = str(exc).lower()
    return any(marker in message for marker in _GRAPH_STORAGE_MARKERS)


def raise_graph_storage_http_error(exc: BaseException) -> None:
    """Raise HTTP 503 with operator-facing guidance for graph storage failures."""
    if not is_graph_storage_error(exc):
        raise exc
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Tenant graph storage is unavailable (corrupt or missing AGE graph). "
            "This is a platform/infrastructure issue, not invalid JSONL or ontology. "
            "In local dev, run `make dev-repair-age-graphs` or restore from "
            "`make dev-backup`, then retry prepopulation from the current label."
        ),
    ) from exc
