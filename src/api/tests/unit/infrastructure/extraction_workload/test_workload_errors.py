"""Unit tests for workload graph storage error mapping."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from infrastructure.database.exceptions import GraphQueryError
from infrastructure.extraction_workload.workload_errors import (
    is_graph_storage_error,
    raise_graph_storage_http_error,
)


def test_is_graph_storage_error_detects_graph_query_error() -> None:
    assert is_graph_storage_error(GraphQueryError("graph with oid 1 does not exist", query="MATCH (n) RETURN n"))


def test_is_graph_storage_error_detects_message_markers() -> None:
    assert is_graph_storage_error(RuntimeError("graph with oid 17491 does not exist"))


def test_raise_graph_storage_http_error_maps_to_503() -> None:
    with pytest.raises(HTTPException) as exc_info:
        raise_graph_storage_http_error(
            GraphQueryError("graph with oid 17491 does not exist", query="MATCH (n) RETURN n")
        )
    assert exc_info.value.status_code == 503
    assert "dev-repair-age-graphs" in str(exc_info.value.detail)


def test_raise_graph_storage_http_error_reraises_unrelated_errors() -> None:
    with pytest.raises(ValueError, match="unrelated"):
        raise_graph_storage_http_error(ValueError("unrelated"))
