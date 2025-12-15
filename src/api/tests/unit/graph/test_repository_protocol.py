"""Tests for Graph repository protocols."""

from graph.domain.value_objects import EdgeRecord, NodeRecord
from graph.ports.protocols import NodeNeighborsResult
from graph.ports.repositories import IGraphReadOnlyRepository


class TestIGraphReadOnlyRepositoryProtocol:
    """Tests for IGraphReadOnlyRepository protocol definition."""

    def test_protocol_is_runtime_checkable(self):
        """Protocol should be runtime checkable for isinstance checks."""

        # Create a minimal implementation to verify protocol
        class MinimalRepo:
            def find_nodes_by_path(
                self, path: str
            ) -> tuple[list[NodeRecord], list[EdgeRecord]]:
                return [], []

            def find_nodes_by_slug(
                self, slug: str, node_type: str | None = None
            ) -> list[NodeRecord]:
                return []

            def get_neighbors(self, node_id: str) -> NodeNeighborsResult:
                return NodeNeighborsResult(
                    central_node=NodeRecord(id=node_id, label="Node", properties={}),
                    nodes=[],
                    edges=[],
                )

            def generate_id(self, entity_type: str, entity_slug: str) -> str:
                return ""

            def execute_raw_query(self, query: str) -> list[dict]:
                return []

        # Should satisfy the protocol
        repo = MinimalRepo()
        assert isinstance(repo, IGraphReadOnlyRepository)

    def test_incomplete_implementation_fails_protocol_check(self):
        """Incomplete implementation should not satisfy protocol."""

        class IncompleteRepo:
            def find_nodes_by_path(
                self, path: str
            ) -> tuple[list[NodeRecord], list[EdgeRecord]]:
                return [], []

            # Missing other required methods

        repo = IncompleteRepo()
        assert not isinstance(repo, IGraphReadOnlyRepository)

    def test_protocol_requires_find_nodes_by_path(self):
        """Protocol should require find_nodes_by_path method."""

        class MissingFindByPath:
            def find_nodes_by_slug(
                self, slug: str, node_type: str | None = None
            ) -> list[NodeRecord]:
                return []

            def get_neighbors(self, node_id: str) -> NodeNeighborsResult:
                return NodeNeighborsResult(
                    central_node=NodeRecord(id=node_id, label="Node", properties={}),
                    nodes=[],
                    edges=[],
                )

            def generate_id(self, entity_type: str, entity_slug: str) -> str:
                return ""

            def execute_raw_query(self, query: str) -> list[dict]:
                return []

        repo = MissingFindByPath()
        assert not isinstance(repo, IGraphReadOnlyRepository)

    def test_protocol_requires_generate_id(self):
        """Protocol should require generate_id method for idempotency."""

        class MissingGenerateId:
            def find_nodes_by_path(
                self, path: str
            ) -> tuple[list[NodeRecord], list[EdgeRecord]]:
                return [], []

            def find_nodes_by_slug(
                self, slug: str, node_type: str | None = None
            ) -> list[NodeRecord]:
                return []

            def get_neighbors(self, node_id: str) -> NodeNeighborsResult:
                return NodeNeighborsResult(
                    central_node=NodeRecord(id=node_id, label="Node", properties={}),
                    nodes=[],
                    edges=[],
                )

            def execute_raw_query(self, query: str) -> list[dict]:
                return []

        repo = MissingGenerateId()
        assert not isinstance(repo, IGraphReadOnlyRepository)
