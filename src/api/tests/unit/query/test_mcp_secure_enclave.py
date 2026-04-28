"""Unit tests for MCPQuerySecureEnclave.

Tests the secure enclave authorization applied to raw Cypher query results:
- Authorized nodes/edges return full properties (spec: Secure enclave redaction)
- Unauthorized nodes are redacted to ID-only (spec: Secure enclave redaction)
- Unauthorized edges are redacted to ID, start_id, end_id (spec: Secure enclave redaction)
- Graph topology is preserved — unauthorized entities still appear (spec: Secure enclave redaction)
- Permission results are cached per knowledge_graph_id (spec: performance requirement)
"""

from __future__ import annotations

from typing import Any

import pytest

from query.application.mcp_secure_enclave import MCPQuerySecureEnclave


# ---------------------------------------------------------------------------
# Type-erasing test helper
# ---------------------------------------------------------------------------


async def _redact(enclave: MCPQuerySecureEnclave, rows: list) -> list[Any]:
    """Type-erasing wrapper so plain dict literals don't clash with QueryResultRow TypedDicts.

    Test data literals like ``[{"node": {"id": "1", ...}}]`` are inferred as
    ``list[dict[str, dict[str, str]]]`` by mypy, which is incompatible with the
    strict ``list[QueryResultRow]`` signature.  A single ignore here is cleaner
    than annotating every call site.
    """
    return await enclave.apply_redaction(rows)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeAuthorizationProvider:
    """Fake AuthorizationProvider for testing secure enclave.

    Authorizes knowledge_graph_ids in `authorized_kg_ids`.
    If `raise_error` is True, raises on every check_permission call.
    """

    def __init__(
        self,
        authorized_kg_ids: set[str] | None = None,
        raise_error: bool = False,
    ) -> None:
        self.authorized_kg_ids = authorized_kg_ids or set()
        self.raise_error = raise_error
        self.check_calls: list[tuple[str, str, str]] = []

    async def check_permission(
        self, resource: str, permission: str, subject: str
    ) -> bool:
        self.check_calls.append((resource, permission, subject))
        if self.raise_error:
            raise Exception("SpiceDB unavailable")
        # Resource format: "knowledge_graph:kg-id"
        kg_id = resource.split(":", 1)[1] if ":" in resource else resource
        return kg_id in self.authorized_kg_ids

    # Required protocol methods (no-ops for tests)
    async def write_relationship(
        self, resource: str, relation: str, subject: str
    ) -> None:
        pass

    async def write_relationships(self, relationships: list) -> None:
        pass

    async def bulk_check_permission(self, requests: list) -> set[str]:
        return set()

    async def delete_relationship(
        self, resource: str, relation: str, subject: str
    ) -> None:
        pass

    async def delete_relationships(self, relationships: list) -> None:
        pass

    async def delete_relationships_by_filter(
        self,
        resource_type: str,
        resource_id: str | None = None,
        relation: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> None:
        pass

    async def lookup_subjects(
        self,
        resource: str,
        relation: str,
        subject_type: str,
        optional_subject_relation: str | None = None,
    ) -> list:
        return []

    async def lookup_resources(
        self, resource_type: str, permission: str, subject: str
    ) -> list:
        return []

    async def read_relationships(
        self,
        resource_type: str,
        resource_id: str | None = None,
        relation: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> list:
        return []


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def authorized_authz() -> FakeAuthorizationProvider:
    """Authorization provider that grants VIEW on 'kg-1'."""
    return FakeAuthorizationProvider(authorized_kg_ids={"kg-1"})


@pytest.fixture
def unauthorized_authz() -> FakeAuthorizationProvider:
    """Authorization provider that denies everything."""
    return FakeAuthorizationProvider(authorized_kg_ids=set())


@pytest.fixture
def error_authz() -> FakeAuthorizationProvider:
    """Authorization provider that raises on every call."""
    return FakeAuthorizationProvider(raise_error=True)


@pytest.fixture
def authorized_enclave(
    authorized_authz: FakeAuthorizationProvider,
) -> MCPQuerySecureEnclave:
    return MCPQuerySecureEnclave(authz=authorized_authz, user_id="user-123")


@pytest.fixture
def unauthorized_enclave(
    unauthorized_authz: FakeAuthorizationProvider,
) -> MCPQuerySecureEnclave:
    return MCPQuerySecureEnclave(authz=unauthorized_authz, user_id="user-123")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestApplyRedactionEmptyInput:
    """Tests for empty input."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_empty_input(
        self, authorized_enclave: MCPQuerySecureEnclave
    ) -> None:
        """Empty results should return empty list."""
        result = await _redact(authorized_enclave, [])
        assert result == []


class TestNodeRedaction:
    """Tests for node entity redaction (spec: Secure enclave redaction — node rules)."""

    @pytest.mark.asyncio
    async def test_authorized_node_returns_full_properties(
        self, authorized_enclave: MCPQuerySecureEnclave
    ) -> None:
        """Authorized node should have all properties intact."""
        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": "kg-1"},
                }
            }
        ]
        result = await _redact(authorized_enclave, rows)

        assert len(result) == 1
        assert result[0]["node"]["properties"]["name"] == "Alice"
        assert result[0]["node"]["label"] == "Person"
        assert result[0]["node"]["id"] == "1"

    @pytest.mark.asyncio
    async def test_unauthorized_node_redacted_to_id_only(
        self, unauthorized_enclave: MCPQuerySecureEnclave
    ) -> None:
        """Unauthorized node should have ALL properties stripped, keeping only 'id'."""
        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": "kg-1"},
                }
            }
        ]
        result = await _redact(unauthorized_enclave, rows)

        assert len(result) == 1
        node = result[0]["node"]
        # Only 'id' should remain
        assert node == {"id": "1"}
        assert "label" not in node
        assert "properties" not in node

    @pytest.mark.asyncio
    async def test_node_without_knowledge_graph_id_is_redacted(
        self, authorized_enclave: MCPQuerySecureEnclave
    ) -> None:
        """Node lacking knowledge_graph_id cannot be authorized — must be redacted."""
        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice"},  # no knowledge_graph_id
                }
            }
        ]
        result = await _redact(authorized_enclave, rows)

        assert result[0]["node"] == {"id": "1"}

    @pytest.mark.asyncio
    async def test_node_with_empty_knowledge_graph_id_is_redacted(
        self, authorized_enclave: MCPQuerySecureEnclave
    ) -> None:
        """Node with empty knowledge_graph_id should be redacted."""
        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": ""},
                }
            }
        ]
        result = await _redact(authorized_enclave, rows)

        assert result[0]["node"] == {"id": "1"}

    @pytest.mark.asyncio
    async def test_node_with_none_knowledge_graph_id_is_redacted(
        self, authorized_enclave: MCPQuerySecureEnclave
    ) -> None:
        """Node with None knowledge_graph_id should be redacted."""
        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": None},
                }
            }
        ]
        result = await _redact(authorized_enclave, rows)

        assert result[0]["node"] == {"id": "1"}


class TestEdgeRedaction:
    """Tests for edge entity redaction (spec: Secure enclave redaction — edge rules)."""

    @pytest.mark.asyncio
    async def test_authorized_edge_returns_full_properties(
        self, authorized_enclave: MCPQuerySecureEnclave
    ) -> None:
        """Authorized edge should have all properties intact."""
        rows = [
            {
                "edge": {
                    "id": "10",
                    "label": "KNOWS",
                    "start_id": "1",
                    "end_id": "2",
                    "properties": {"since": 2020, "knowledge_graph_id": "kg-1"},
                }
            }
        ]
        result = await _redact(authorized_enclave, rows)

        assert len(result) == 1
        edge = result[0]["edge"]
        assert edge["properties"]["since"] == 2020
        assert edge["label"] == "KNOWS"
        assert edge["start_id"] == "1"
        assert edge["end_id"] == "2"

    @pytest.mark.asyncio
    async def test_unauthorized_edge_redacted_to_endpoints_only(
        self, unauthorized_enclave: MCPQuerySecureEnclave
    ) -> None:
        """Unauthorized edge should keep only id, start_id, and end_id."""
        rows = [
            {
                "edge": {
                    "id": "10",
                    "label": "KNOWS",
                    "start_id": "1",
                    "end_id": "2",
                    "properties": {"since": 2020, "knowledge_graph_id": "kg-1"},
                }
            }
        ]
        result = await _redact(unauthorized_enclave, rows)

        assert len(result) == 1
        edge = result[0]["edge"]
        assert edge == {"id": "10", "start_id": "1", "end_id": "2"}
        assert "label" not in edge
        assert "properties" not in edge

    @pytest.mark.asyncio
    async def test_edge_without_knowledge_graph_id_is_redacted(
        self, authorized_enclave: MCPQuerySecureEnclave
    ) -> None:
        """Edge lacking knowledge_graph_id cannot be authorized — must be redacted."""
        rows = [
            {
                "edge": {
                    "id": "10",
                    "label": "KNOWS",
                    "start_id": "1",
                    "end_id": "2",
                    "properties": {},  # no knowledge_graph_id
                }
            }
        ]
        result = await _redact(authorized_enclave, rows)

        assert result[0]["edge"] == {"id": "10", "start_id": "1", "end_id": "2"}


class TestGraphTopologyPreservation:
    """Tests that graph topology is preserved for unauthorized entities.

    Spec: AND the graph topology (which entities exist and are connected) is preserved.
    Unauthorized entities MUST remain in the result set — just with properties stripped.
    """

    @pytest.mark.asyncio
    async def test_unauthorized_nodes_remain_in_results(
        self, unauthorized_enclave: MCPQuerySecureEnclave
    ) -> None:
        """Unauthorized nodes must appear in results (redacted, not removed)."""
        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": "kg-1"},
                }
            },
            {
                "node": {
                    "id": "2",
                    "label": "Person",
                    "properties": {"name": "Bob", "knowledge_graph_id": "kg-1"},
                }
            },
        ]
        result = await _redact(unauthorized_enclave, rows)

        # Both rows remain (topology preserved)
        assert len(result) == 2
        # Both are redacted (id-only)
        assert result[0]["node"] == {"id": "1"}
        assert result[1]["node"] == {"id": "2"}

    @pytest.mark.asyncio
    async def test_unauthorized_edges_remain_in_results(
        self, unauthorized_enclave: MCPQuerySecureEnclave
    ) -> None:
        """Unauthorized edges must appear in results (redacted, not removed)."""
        rows = [
            {
                "edge": {
                    "id": "10",
                    "label": "KNOWS",
                    "start_id": "1",
                    "end_id": "2",
                    "properties": {"knowledge_graph_id": "kg-1"},
                }
            }
        ]
        result = await _redact(unauthorized_enclave, rows)

        assert len(result) == 1
        assert result[0]["edge"] == {"id": "10", "start_id": "1", "end_id": "2"}

    @pytest.mark.asyncio
    async def test_mixed_authorized_and_unauthorized(
        self,
    ) -> None:
        """Authorized entities get full data; unauthorized get redacted — all present."""
        authz = FakeAuthorizationProvider(authorized_kg_ids={"kg-authorized"})
        enclave = MCPQuerySecureEnclave(authz=authz, user_id="user-123")

        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {
                        "name": "Alice",
                        "knowledge_graph_id": "kg-authorized",
                    },
                }
            },
            {
                "node": {
                    "id": "2",
                    "label": "Person",
                    "properties": {"name": "Bob", "knowledge_graph_id": "kg-denied"},
                }
            },
        ]
        result = await _redact(enclave, rows)

        assert len(result) == 2
        # Alice is authorized — full properties
        assert result[0]["node"]["properties"]["name"] == "Alice"
        # Bob is not authorized — redacted
        assert result[1]["node"] == {"id": "2"}


class TestScalarValues:
    """Tests for scalar values in query results."""

    @pytest.mark.asyncio
    async def test_scalar_value_passes_through_unchanged(
        self, authorized_enclave: MCPQuerySecureEnclave
    ) -> None:
        """Scalar values (count, etc.) have no entity to authorize, pass through."""
        rows = [{"value": 42}]
        result = await _redact(authorized_enclave, rows)

        assert result == [{"value": 42}]

    @pytest.mark.asyncio
    async def test_scalar_passes_through_even_when_unauthorized(
        self, unauthorized_enclave: MCPQuerySecureEnclave
    ) -> None:
        """Scalar values should pass through regardless of authorization state."""
        rows = [{"value": 100}]
        result = await _redact(unauthorized_enclave, rows)

        assert result == [{"value": 100}]


class TestMapResults:
    """Tests for map-style query results (Apache AGE single-column constraint)."""

    @pytest.mark.asyncio
    async def test_map_result_authorized_nodes_preserved(
        self, authorized_enclave: MCPQuerySecureEnclave
    ) -> None:
        """Authorized nodes within map results should have full properties."""
        rows = [
            {
                "person": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": "kg-1"},
                },
                "count": 5,
            }
        ]
        result = await _redact(authorized_enclave, rows)

        assert result[0]["person"]["properties"]["name"] == "Alice"
        assert result[0]["count"] == 5

    @pytest.mark.asyncio
    async def test_map_result_unauthorized_nodes_and_edges_redacted(
        self, unauthorized_enclave: MCPQuerySecureEnclave
    ) -> None:
        """Unauthorized nodes and edges within map results should be redacted."""
        rows = [
            {
                "person": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": "kg-1"},
                },
                "relationship": {
                    "id": "10",
                    "label": "KNOWS",
                    "start_id": "1",
                    "end_id": "2",
                    "properties": {"since": 2020, "knowledge_graph_id": "kg-1"},
                },
            }
        ]
        result = await _redact(unauthorized_enclave, rows)

        assert result[0]["person"] == {"id": "1"}
        assert result[0]["relationship"] == {"id": "10", "start_id": "1", "end_id": "2"}


class TestPermissionCaching:
    """Tests that permission checks are cached per knowledge_graph_id."""

    @pytest.mark.asyncio
    async def test_same_kg_id_checked_only_once(self) -> None:
        """Multiple entities with same knowledge_graph_id → single SpiceDB call."""
        authz = FakeAuthorizationProvider(authorized_kg_ids={"kg-1"})
        enclave = MCPQuerySecureEnclave(authz=authz, user_id="user-123")

        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": "kg-1"},
                }
            },
            {
                "node": {
                    "id": "2",
                    "label": "Person",
                    "properties": {"name": "Bob", "knowledge_graph_id": "kg-1"},
                }
            },
            {
                "node": {
                    "id": "3",
                    "label": "Person",
                    "properties": {"name": "Carol", "knowledge_graph_id": "kg-1"},
                }
            },
        ]
        await _redact(enclave, rows)

        # Only one SpiceDB call for kg-1 despite 3 entities
        assert len(authz.check_calls) == 1

    @pytest.mark.asyncio
    async def test_different_kg_ids_checked_separately(self) -> None:
        """Entities with different knowledge_graph_ids → separate SpiceDB calls."""
        authz = FakeAuthorizationProvider(authorized_kg_ids={"kg-1", "kg-2"})
        enclave = MCPQuerySecureEnclave(authz=authz, user_id="user-123")

        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": "kg-1"},
                }
            },
            {
                "node": {
                    "id": "2",
                    "label": "Person",
                    "properties": {"name": "Bob", "knowledge_graph_id": "kg-2"},
                }
            },
        ]
        await _redact(enclave, rows)

        # Two calls — one per unique kg_id
        assert len(authz.check_calls) == 2


class TestAuthorizationFailSafe:
    """Tests that authorization errors result in redaction (fail-safe)."""

    @pytest.mark.asyncio
    async def test_spicedb_error_causes_node_redaction(
        self, error_authz: FakeAuthorizationProvider
    ) -> None:
        """SpiceDB errors must cause redaction, not expose data (fail-safe)."""
        enclave = MCPQuerySecureEnclave(authz=error_authz, user_id="user-123")
        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": "kg-1"},
                }
            }
        ]
        result = await _redact(enclave, rows)

        # Redacted due to SpiceDB error
        assert result[0]["node"] == {"id": "1"}

    @pytest.mark.asyncio
    async def test_spicedb_error_causes_edge_redaction(
        self, error_authz: FakeAuthorizationProvider
    ) -> None:
        """SpiceDB errors on edges must cause redaction."""
        enclave = MCPQuerySecureEnclave(authz=error_authz, user_id="user-123")
        rows = [
            {
                "edge": {
                    "id": "10",
                    "label": "KNOWS",
                    "start_id": "1",
                    "end_id": "2",
                    "properties": {"knowledge_graph_id": "kg-1"},
                }
            }
        ]
        result = await _redact(enclave, rows)

        assert result[0]["edge"] == {"id": "10", "start_id": "1", "end_id": "2"}


class TestSubjectInAuthorizationCall:
    """Tests that the correct user_id is used in SpiceDB calls."""

    @pytest.mark.asyncio
    async def test_uses_correct_user_id(self) -> None:
        """Authorization checks must use the enclave's user_id."""
        authz = FakeAuthorizationProvider(authorized_kg_ids={"kg-1"})
        enclave = MCPQuerySecureEnclave(authz=authz, user_id="user-alice")

        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"knowledge_graph_id": "kg-1"},
                }
            }
        ]
        await _redact(enclave, rows)

        # The subject in the check should be "user:user-alice"
        assert len(authz.check_calls) == 1
        _, _, subject = authz.check_calls[0]
        assert "user-alice" in subject
