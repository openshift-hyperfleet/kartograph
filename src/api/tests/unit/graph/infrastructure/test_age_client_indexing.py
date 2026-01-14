"""Unit tests for AgeGraphClient indexing functionality.

Tests for comprehensive index creation including:
- BTREE indexes on id column (graphid)
- BTREE indexes on start_id/end_id for edges
- GIN indexes on properties column
- BTREE indexes on properties.id for logical ID lookups
"""

from unittest.mock import MagicMock

import pytest

from graph.infrastructure.age_client import AgeGraphClient
from infrastructure.database.exceptions import DatabaseConnectionError


@pytest.fixture
def mock_db_settings():
    """Provide test database settings."""
    from infrastructure.settings import DatabaseSettings

    return DatabaseSettings(
        host="testhost",
        port=5432,
        database="testdb",
        username="testuser",
        password="testpass",
        graph_name="test_graph",
    )


@pytest.fixture
def connected_client_with_mock_cursor(mock_db_settings):
    """Create a client with mocked connection that appears connected."""
    client = AgeGraphClient(mock_db_settings)

    # Create mock cursor
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)

    # Create mock connection
    connection = MagicMock()
    connection.cursor.return_value = cursor

    # Make client appear connected
    client._current_connection = connection
    client._connected = True

    return client, cursor, connection


class TestEnsureLabelIndexesVertex:
    """Tests for vertex label index creation."""

    def test_creates_btree_index_on_id_column(self, connected_client_with_mock_cursor):
        """Should create BTREE index on graphid column for vertex labels."""
        client, cursor, connection = connected_client_with_mock_cursor

        # Mock: label exists, indexes don't exist
        cursor.fetchone.side_effect = [
            (1,),  # Label exists
            None,  # BTREE id index doesn't exist
            None,  # GIN properties index doesn't exist
            None,  # BTREE properties.id index doesn't exist
        ]

        client.ensure_label_indexes("person", kind="v")

        # Verify BTREE index on id column was created
        executed_sqls = [str(call) for call in cursor.execute.call_args_list]
        btree_id_calls = [s for s in executed_sqls if "BTREE (id)" in s]
        assert len(btree_id_calls) >= 1, "Should create BTREE index on id column"

    def test_creates_gin_index_on_properties(self, connected_client_with_mock_cursor):
        """Should create GIN index on properties column for vertex labels."""
        client, cursor, connection = connected_client_with_mock_cursor

        # Mock: label exists, indexes don't exist
        cursor.fetchone.side_effect = [
            (1,),  # Label exists
            None,  # BTREE id index doesn't exist
            None,  # GIN properties index doesn't exist
            None,  # BTREE properties.id index doesn't exist
        ]

        client.ensure_label_indexes("person", kind="v")

        # Verify GIN index on properties was created
        executed_sqls = [str(call) for call in cursor.execute.call_args_list]
        gin_calls = [s for s in executed_sqls if "GIN (properties)" in s]
        assert len(gin_calls) >= 1, "Should create GIN index on properties column"

    def test_creates_btree_index_on_properties_id(
        self, connected_client_with_mock_cursor
    ):
        """Should create BTREE index on properties.id for logical ID lookups."""
        client, cursor, connection = connected_client_with_mock_cursor

        # Mock: label exists, indexes don't exist
        cursor.fetchone.side_effect = [
            (1,),  # Label exists
            None,  # BTREE id index doesn't exist
            None,  # GIN properties index doesn't exist
            None,  # BTREE properties.id index doesn't exist
        ]

        client.ensure_label_indexes("person", kind="v")

        # Verify BTREE index on properties.id was created
        executed_sqls = [str(call) for call in cursor.execute.call_args_list]
        prop_id_calls = [
            s for s in executed_sqls if "agtype_access_operator" in s and "id" in s
        ]
        assert len(prop_id_calls) >= 1, "Should create BTREE index on properties.id"

    def test_does_not_create_start_end_indexes_for_vertex(
        self, connected_client_with_mock_cursor
    ):
        """Should NOT create start_id/end_id indexes for vertex labels."""
        client, cursor, connection = connected_client_with_mock_cursor

        # Mock: label exists, indexes don't exist
        cursor.fetchone.side_effect = [
            (1,),  # Label exists
            None,
            None,
            None,  # Indexes don't exist
        ]

        client.ensure_label_indexes("person", kind="v")

        # Verify NO start_id/end_id indexes
        executed_sqls = [str(call) for call in cursor.execute.call_args_list]
        start_id_calls = [s for s in executed_sqls if "start_id" in s]
        end_id_calls = [s for s in executed_sqls if "end_id" in s]
        assert len(start_id_calls) == 0, "Should NOT create start_id index for vertices"
        assert len(end_id_calls) == 0, "Should NOT create end_id index for vertices"


class TestEnsureLabelIndexesEdge:
    """Tests for edge label index creation."""

    def test_creates_btree_index_on_id_column(self, connected_client_with_mock_cursor):
        """Should create BTREE index on graphid column for edge labels."""
        client, cursor, connection = connected_client_with_mock_cursor

        # Mock: label exists, indexes don't exist
        cursor.fetchone.side_effect = [
            (1,),  # Label exists
            None,
            None,
            None,
            None,
            None,  # Indexes don't exist
        ]

        client.ensure_label_indexes("knows", kind="e")

        executed_sqls = [str(call) for call in cursor.execute.call_args_list]
        btree_id_calls = [s for s in executed_sqls if "BTREE (id)" in s]
        assert len(btree_id_calls) >= 1, (
            "Should create BTREE index on id column for edges"
        )

    def test_creates_btree_index_on_start_id(self, connected_client_with_mock_cursor):
        """Should create BTREE index on start_id column for edge labels."""
        client, cursor, connection = connected_client_with_mock_cursor

        # Mock: label exists, indexes don't exist
        cursor.fetchone.side_effect = [
            (1,),  # Label exists
            None,
            None,
            None,
            None,
            None,  # Indexes don't exist
        ]

        client.ensure_label_indexes("knows", kind="e")

        executed_sqls = [str(call) for call in cursor.execute.call_args_list]
        start_id_calls = [s for s in executed_sqls if "BTREE (start_id)" in s]
        assert len(start_id_calls) >= 1, (
            "Should create BTREE index on start_id for edges"
        )

    def test_creates_btree_index_on_end_id(self, connected_client_with_mock_cursor):
        """Should create BTREE index on end_id column for edge labels."""
        client, cursor, connection = connected_client_with_mock_cursor

        # Mock: label exists, indexes don't exist
        cursor.fetchone.side_effect = [
            (1,),  # Label exists
            None,
            None,
            None,
            None,
            None,  # Indexes don't exist
        ]

        client.ensure_label_indexes("knows", kind="e")

        executed_sqls = [str(call) for call in cursor.execute.call_args_list]
        end_id_calls = [s for s in executed_sqls if "BTREE (end_id)" in s]
        assert len(end_id_calls) >= 1, "Should create BTREE index on end_id for edges"

    def test_creates_gin_index_on_properties_for_edges(
        self, connected_client_with_mock_cursor
    ):
        """Should create GIN index on properties column for edge labels."""
        client, cursor, connection = connected_client_with_mock_cursor

        # Mock: label exists, indexes don't exist
        cursor.fetchone.side_effect = [
            (1,),  # Label exists
            None,
            None,
            None,
            None,
            None,  # Indexes don't exist
        ]

        client.ensure_label_indexes("knows", kind="e")

        executed_sqls = [str(call) for call in cursor.execute.call_args_list]
        gin_calls = [s for s in executed_sqls if "GIN (properties)" in s]
        assert len(gin_calls) >= 1, "Should create GIN index on properties for edges"


class TestEnsureLabelIndexesSkipsExisting:
    """Tests for skipping already existing indexes."""

    def test_skips_existing_indexes(self, connected_client_with_mock_cursor):
        """Should not recreate indexes that already exist."""
        client, cursor, connection = connected_client_with_mock_cursor

        # Mock: label exists, all indexes already exist
        cursor.fetchone.side_effect = [
            (1,),  # Label exists
            (1,),  # BTREE id index exists
            (1,),  # GIN properties index exists
            (1,),  # BTREE properties.id index exists
        ]

        created = client.ensure_label_indexes("person", kind="v")

        # Should return 0 - no indexes created
        assert created == 0

    def test_creates_only_missing_indexes(self, connected_client_with_mock_cursor):
        """Should only create indexes that don't exist."""
        client, cursor, connection = connected_client_with_mock_cursor

        # Mock: label exists, some indexes exist
        cursor.fetchone.side_effect = [
            (1,),  # Label exists
            (1,),  # BTREE id index exists
            None,  # GIN properties index doesn't exist
            (1,),  # BTREE properties.id index exists
        ]

        created = client.ensure_label_indexes("person", kind="v")

        # Should return 1 - only GIN index created
        assert created == 1


class TestEnsureLabelIndexesValidation:
    """Tests for input validation."""

    def test_raises_when_not_connected(self, mock_db_settings):
        """Should raise DatabaseConnectionError when not connected."""
        client = AgeGraphClient(mock_db_settings)

        with pytest.raises(DatabaseConnectionError):
            client.ensure_label_indexes("person", kind="v")

    def test_raises_on_invalid_label_name(self, connected_client_with_mock_cursor):
        """Should raise ValueError on invalid label names."""
        client, cursor, connection = connected_client_with_mock_cursor

        with pytest.raises(ValueError, match="Invalid label"):
            client.ensure_label_indexes("invalid-label", kind="v")

        with pytest.raises(ValueError, match="Invalid label"):
            client.ensure_label_indexes("label; DROP TABLE", kind="v")

    def test_returns_zero_when_label_does_not_exist(
        self, connected_client_with_mock_cursor
    ):
        """Should return 0 when label doesn't exist in graph."""
        client, cursor, connection = connected_client_with_mock_cursor

        # Mock: label doesn't exist
        cursor.fetchone.return_value = None

        created = client.ensure_label_indexes("nonexistent", kind="v")

        assert created == 0


class TestEnsureAllLabelsIndexed:
    """Tests for indexing all labels in graph."""

    def test_indexes_both_vertex_and_edge_labels(
        self, connected_client_with_mock_cursor
    ):
        """Should create indexes for both vertex and edge labels."""
        client, cursor, connection = connected_client_with_mock_cursor

        # Mock: return vertex and edge labels
        cursor.fetchall.return_value = [
            ("person", "v"),
            ("company", "v"),
            ("knows", "e"),
            ("works_at", "e"),
        ]

        # Mock ensure_label_indexes to track calls
        client.ensure_label_indexes = MagicMock(return_value=3)

        client.ensure_all_labels_indexed()

        # Should be called for each label with correct kind
        calls = client.ensure_label_indexes.call_args_list
        assert len(calls) == 4

        # Verify vertex labels called with kind='v'
        vertex_calls = [c for c in calls if c[1].get("kind") == "v"]
        assert len(vertex_calls) == 2

        # Verify edge labels called with kind='e'
        edge_calls = [c for c in calls if c[1].get("kind") == "e"]
        assert len(edge_calls) == 2


class TestBackwardsCompatibility:
    """Tests for backwards compatibility with existing code."""

    def test_ensure_label_index_still_works(self, connected_client_with_mock_cursor):
        """Legacy ensure_label_index should still work for vertex labels."""
        client, cursor, connection = connected_client_with_mock_cursor

        # Mock: label exists, index doesn't exist
        cursor.fetchone.side_effect = [
            None,  # Index doesn't exist
            (1,),  # Label exists
        ]

        # The old method should still work
        result = client.ensure_label_index("person")

        # Should return boolean
        assert isinstance(result, bool)
