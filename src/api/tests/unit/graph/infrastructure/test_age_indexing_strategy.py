"""Unit tests for AgeIndexingStrategy.

Tests for transactional index creation including:
- BTREE indexes on id column (graphid)
- BTREE indexes on start_id/end_id for edges
- GIN indexes on properties column
- BTREE indexes on properties.id for logical ID lookups
"""

from unittest.mock import MagicMock

import pytest

from graph.domain.value_objects import EntityType
from graph.infrastructure.age_bulk_loading import AgeIndexingStrategy


@pytest.fixture
def indexing_strategy():
    """Create an AgeIndexingStrategy instance."""
    return AgeIndexingStrategy()


@pytest.fixture
def mock_cursor():
    """Create a mock database cursor."""
    cursor = MagicMock()
    # Default: no indexes exist
    cursor.fetchone.return_value = None
    return cursor


class TestCreateLabelIndexesForNodes:
    """Tests for node label index creation."""

    def test_creates_btree_index_on_id_column(self, indexing_strategy, mock_cursor):
        """Should create BTREE index on graphid column for node labels."""
        indexing_strategy.create_label_indexes(
            mock_cursor, "test_graph", "person", EntityType.NODE
        )

        executed_sqls = [str(call) for call in mock_cursor.execute.call_args_list]
        btree_id_calls = [s for s in executed_sqls if "BTREE (id)" in s]
        assert len(btree_id_calls) >= 1, "Should create BTREE index on id column"

    def test_creates_gin_index_on_properties(self, indexing_strategy, mock_cursor):
        """Should create GIN index on properties column for node labels."""
        indexing_strategy.create_label_indexes(
            mock_cursor, "test_graph", "person", EntityType.NODE
        )

        executed_sqls = [str(call) for call in mock_cursor.execute.call_args_list]
        gin_calls = [s for s in executed_sqls if "GIN (properties)" in s]
        assert len(gin_calls) >= 1, "Should create GIN index on properties column"

    def test_creates_btree_index_on_properties_id(self, indexing_strategy, mock_cursor):
        """Should create BTREE index on properties.id for logical ID lookups."""
        indexing_strategy.create_label_indexes(
            mock_cursor, "test_graph", "person", EntityType.NODE
        )

        executed_sqls = [str(call) for call in mock_cursor.execute.call_args_list]
        # Should use agtype_object_field_text_agtype function
        prop_id_calls = [
            s for s in executed_sqls if "agtype_object_field_text_agtype" in s
        ]
        assert len(prop_id_calls) >= 1, "Should create BTREE index on properties.id"

    def test_does_not_create_start_end_indexes_for_nodes(
        self, indexing_strategy, mock_cursor
    ):
        """Should NOT create start_id/end_id indexes for node labels."""
        indexing_strategy.create_label_indexes(
            mock_cursor, "test_graph", "person", EntityType.NODE
        )

        executed_sqls = [str(call) for call in mock_cursor.execute.call_args_list]
        start_id_calls = [s for s in executed_sqls if "start_id" in s]
        end_id_calls = [s for s in executed_sqls if "end_id" in s]
        assert len(start_id_calls) == 0, "Should NOT create start_id index for nodes"
        assert len(end_id_calls) == 0, "Should NOT create end_id index for nodes"

    def test_returns_count_of_created_indexes(self, indexing_strategy, mock_cursor):
        """Should return the number of indexes created."""
        created = indexing_strategy.create_label_indexes(
            mock_cursor, "test_graph", "person", EntityType.NODE
        )

        # Nodes should get 3 indexes: id_btree, props_gin, prop_id_text_btree
        assert created == 3


class TestCreateLabelIndexesForEdges:
    """Tests for edge label index creation."""

    def test_creates_btree_index_on_id_column(self, indexing_strategy, mock_cursor):
        """Should create BTREE index on graphid column for edge labels."""
        indexing_strategy.create_label_indexes(
            mock_cursor, "test_graph", "knows", EntityType.EDGE
        )

        executed_sqls = [str(call) for call in mock_cursor.execute.call_args_list]
        btree_id_calls = [s for s in executed_sqls if "BTREE (id)" in s]
        assert len(btree_id_calls) >= 1, "Should create BTREE index on id column"

    def test_creates_btree_index_on_start_id(self, indexing_strategy, mock_cursor):
        """Should create BTREE index on start_id column for edge labels."""
        indexing_strategy.create_label_indexes(
            mock_cursor, "test_graph", "knows", EntityType.EDGE
        )

        executed_sqls = [str(call) for call in mock_cursor.execute.call_args_list]
        start_id_calls = [s for s in executed_sqls if "BTREE (start_id)" in s]
        assert len(start_id_calls) >= 1, "Should create BTREE index on start_id"

    def test_creates_btree_index_on_end_id(self, indexing_strategy, mock_cursor):
        """Should create BTREE index on end_id column for edge labels."""
        indexing_strategy.create_label_indexes(
            mock_cursor, "test_graph", "knows", EntityType.EDGE
        )

        executed_sqls = [str(call) for call in mock_cursor.execute.call_args_list]
        end_id_calls = [s for s in executed_sqls if "BTREE (end_id)" in s]
        assert len(end_id_calls) >= 1, "Should create BTREE index on end_id"

    def test_creates_gin_index_on_properties_for_edges(
        self, indexing_strategy, mock_cursor
    ):
        """Should create GIN index on properties column for edge labels."""
        indexing_strategy.create_label_indexes(
            mock_cursor, "test_graph", "knows", EntityType.EDGE
        )

        executed_sqls = [str(call) for call in mock_cursor.execute.call_args_list]
        gin_calls = [s for s in executed_sqls if "GIN (properties)" in s]
        assert len(gin_calls) >= 1, "Should create GIN index on properties for edges"

    def test_returns_count_of_created_indexes(self, indexing_strategy, mock_cursor):
        """Should return the number of indexes created."""
        created = indexing_strategy.create_label_indexes(
            mock_cursor, "test_graph", "knows", EntityType.EDGE
        )

        # Edges should get 5 indexes: id_btree, props_gin, prop_id_text_btree,
        # start_id_btree, end_id_btree
        assert created == 5


class TestSkipsExistingIndexes:
    """Tests for skipping already existing indexes."""

    def test_skips_existing_indexes(self, indexing_strategy, mock_cursor):
        """Should not recreate indexes that already exist."""
        # Mock: all indexes already exist
        mock_cursor.fetchone.return_value = (1,)

        created = indexing_strategy.create_label_indexes(
            mock_cursor, "test_graph", "person", EntityType.NODE
        )

        assert created == 0

    def test_creates_only_missing_indexes(self, indexing_strategy, mock_cursor):
        """Should only create indexes that don't exist."""
        # Mock: first two indexes exist, third doesn't
        mock_cursor.fetchone.side_effect = [
            (1,),  # First index exists
            (1,),  # Second index exists
            None,  # Third index doesn't exist
        ]

        created = indexing_strategy.create_label_indexes(
            mock_cursor, "test_graph", "person", EntityType.NODE
        )

        assert created == 1


class TestInputValidation:
    """Tests for input validation."""

    def test_raises_on_invalid_graph_name(self, indexing_strategy, mock_cursor):
        """Should raise ValueError on invalid graph names."""
        with pytest.raises(ValueError, match="Invalid label"):
            indexing_strategy.create_label_indexes(
                mock_cursor, "invalid-graph", "person", EntityType.NODE
            )

    def test_raises_on_invalid_label_name(self, indexing_strategy, mock_cursor):
        """Should raise ValueError on invalid label names."""
        with pytest.raises(ValueError, match="Invalid label"):
            indexing_strategy.create_label_indexes(
                mock_cursor, "test_graph", "invalid-label", EntityType.NODE
            )

        with pytest.raises(ValueError, match="Invalid label"):
            indexing_strategy.create_label_indexes(
                mock_cursor, "test_graph", "label; DROP TABLE", EntityType.NODE
            )

    def test_raises_on_invalid_entity_type(self, indexing_strategy, mock_cursor):
        """Should raise ValueError on invalid entity type."""
        with pytest.raises(ValueError, match="Invalid entity_type"):
            indexing_strategy.create_label_indexes(
                mock_cursor,
                "test_graph",
                "person",
                "invalid",  # type: ignore
            )


class TestIndexNameConsistency:
    """Tests for consistent index naming."""

    def test_uses_correct_index_name_pattern(self, indexing_strategy, mock_cursor):
        """Should use consistent index naming pattern."""
        indexing_strategy.create_label_indexes(
            mock_cursor, "test_graph", "person", EntityType.NODE
        )

        # Check that pg_indexes queries use correct names
        check_calls = [
            call
            for call in mock_cursor.execute.call_args_list
            if "pg_indexes" in str(call)
        ]

        assert len(check_calls) == 3  # 3 indexes for nodes

        # Extract index names from the calls
        index_names = []
        for call in check_calls:
            args = call[0][1]  # Get the tuple of parameters
            index_names.append(args[1])  # Second param is index name

        assert "idx_test_graph_person_id_btree" in index_names
        assert "idx_test_graph_person_props_gin" in index_names
        assert "idx_test_graph_person_prop_id_text_btree" in index_names


class TestProtocolCompliance:
    """Tests for TransactionalIndexingProtocol compliance."""

    def test_implements_protocol_method(self, indexing_strategy):
        """Should have create_label_indexes method matching protocol."""
        assert hasattr(indexing_strategy, "create_label_indexes")
        assert callable(indexing_strategy.create_label_indexes)
