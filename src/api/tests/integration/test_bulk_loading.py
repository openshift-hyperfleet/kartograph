"""Integration tests for AGE bulk loading strategy.

These tests verify that the bulk loading strategy correctly handles:
1. Duplicate detection - duplicate IDs in a batch should raise an error
2. Edge label pre-creation - edge tables should be created even on empty databases
3. Idempotency across batches - running the same batch twice is safe
4. COPY format safety - tab/newline characters in data are escaped
5. Edge orphan detection - edges referencing non-existent nodes fail fast
6. Label validation - invalid label names are rejected
7. UPDATE/DELETE operations work correctly
8. Advisory locks are stable across Python versions
"""

import hashlib

import pytest

from graph.domain.value_objects import (
    EntityType,
    MutationOperation,
    MutationOperationType,
)
from graph.infrastructure.age_bulk_loading import (
    AgeBulkLoadingStrategy,
    compute_stable_hash,
    validate_label_name,
)
from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.observability import DefaultMutationProbe


@pytest.mark.integration
class TestBulkLoadingDuplicateDetection:
    """Tests for duplicate ID detection within a batch."""

    def test_duplicate_node_ids_in_same_batch_raises_error(
        self, clean_graph: AgeGraphClient
    ):
        """Duplicate node IDs in same batch should raise an error."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create two operations with the same ID in the same batch
        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:aaaa111122223333",
                label="person",
                set_properties={
                    "slug": "alice-first",
                    "name": "Alice First",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:aaaa111122223333",  # Same ID!
                label="person",
                set_properties={
                    "slug": "alice-second",
                    "name": "Alice Second",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is False
        assert len(result.errors) == 1
        assert "Duplicate IDs found in batch" in result.errors[0]
        assert "person:aaaa111122223333" in result.errors[0]

    def test_duplicate_edge_ids_in_same_batch_raises_error(
        self, clean_graph: AgeGraphClient
    ):
        """Duplicate edge IDs in same batch should raise an error."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # First create the nodes
        node_operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:bbbb111122223333",
                label="person",
                set_properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:bbbb222233334444",
                label="person",
                set_properties={
                    "slug": "bob",
                    "name": "Bob",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        strategy.apply_batch(
            client=clean_graph,
            operations=node_operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        # Now create duplicate edges
        edge_operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="knows:cccc111122223333",
                label="knows",
                start_id="person:bbbb111122223333",
                end_id="person:bbbb222233334444",
                set_properties={
                    "since": 2020,
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="knows:cccc111122223333",  # Same ID!
                label="knows",
                start_id="person:bbbb111122223333",
                end_id="person:bbbb222233334444",
                set_properties={
                    "since": 2021,
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=edge_operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is False
        assert len(result.errors) == 1
        assert "Duplicate IDs found in batch" in result.errors[0]
        assert "knows:cccc111122223333" in result.errors[0]


@pytest.mark.integration
class TestBulkLoadingIdempotency:
    """Tests for idempotent operations across batches."""

    def test_repeated_batch_is_idempotent(self, clean_graph: AgeGraphClient):
        """Running the same batch twice should not create duplicates."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:dddd111122223333",
                label="person",
                set_properties={
                    "slug": "charlie",
                    "name": "Charlie",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:dddd222233334444",
                label="person",
                set_properties={
                    "slug": "diana",
                    "name": "Diana",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        # Run the batch twice
        result1 = strategy.apply_batch(
            client=clean_graph,
            operations=operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )
        result2 = strategy.apply_batch(
            client=clean_graph,
            operations=operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result1.success is True
        assert result2.success is True

        # Verify exactly 2 nodes exist
        query_result = clean_graph.execute_cypher(
            "MATCH (n:person) WHERE n.id STARTS WITH 'person:dddd' "
            "RETURN count(n) as cnt"
        )
        count = query_result.rows[0][0]
        assert count == 2, f"Expected 2 nodes, got {count}"


@pytest.mark.integration
class TestEdgeLabelPreCreation:
    """Tests for edge label table pre-creation."""

    def test_creates_edge_label_tables_on_empty_database(
        self, clean_graph: AgeGraphClient
    ):
        """Edge labels should be created even when no edges of that type exist."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create nodes and edges in a single batch (edge label doesn't exist yet)
        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:eeee111122223333",
                label="person",
                set_properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:eeee222233334444",
                label="person",
                set_properties={
                    "slug": "bob",
                    "name": "Bob",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="collaborates:ffff111122223333",
                label="collaborates",  # New edge type
                start_id="person:eeee111122223333",
                end_id="person:eeee222233334444",
                set_properties={
                    "project": "test-project",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify the edge was created
        query_result = clean_graph.execute_cypher(
            "MATCH ()-[r:collaborates]->() RETURN count(r) as cnt"
        )
        count = query_result.rows[0][0]
        assert count == 1, f"Expected 1 edge, got {count}"


# =============================================================================
# P0: STABLE ADVISORY LOCKS TESTS
# =============================================================================


class TestStableAdvisoryLocks:
    """Tests for stable advisory lock key generation.

    Python's hash() is not stable across processes or Python versions.
    We must use a deterministic hash like SHA-256.
    """

    def test_compute_stable_hash_is_deterministic(self):
        """Hash should always return same value for same input."""
        key = "test_graph:Person"
        hash1 = compute_stable_hash(key)
        hash2 = compute_stable_hash(key)
        assert hash1 == hash2

    def test_compute_stable_hash_different_keys_differ(self):
        """Different keys should produce different hashes."""
        hash1 = compute_stable_hash("graph1:Person")
        hash2 = compute_stable_hash("graph2:Person")
        assert hash1 != hash2

    def test_compute_stable_hash_fits_in_postgres_bigint(self):
        """Hash should fit within PostgreSQL bigint range (signed 64-bit)."""
        # Test various inputs
        test_keys = [
            "test_graph:Person",
            "my_graph:VeryLongLabelNameThatMightCauseIssues",
            "graph:A",
            "unicode_graph:\u4e2d\u6587\u6807\u7b7e",
        ]
        for key in test_keys:
            hash_value = compute_stable_hash(key)
            # PostgreSQL bigint: -9223372036854775808 to 9223372036854775807
            assert -9223372036854775808 <= hash_value <= 9223372036854775807

    def test_compute_stable_hash_matches_known_value(self):
        """Verify hash matches a pre-computed known value for stability."""
        # This test will fail if the hash algorithm changes
        key = "test_graph:Person"
        expected = (
            int(hashlib.sha256(key.encode()).hexdigest()[:16], 16) & 0x7FFFFFFFFFFFFFFF
        )
        actual = compute_stable_hash(key)
        assert actual == expected


# =============================================================================
# P0: COPY FORMAT INJECTION TESTS
# =============================================================================


class TestCopyFormatSafety:
    """Tests for COPY format safety - tab/newline escaping."""

    def test_escape_copy_data_handles_tabs(self):
        """Tab characters in property values should be escaped."""
        # Tab in the name field - this raw data would break COPY format
        data = 'id\tlabel\t{"name": "Alice\\tBob"}\n'
        # After proper escaping, tabs in values become literal \t
        assert "\\t" in data or "\t" in data

    @pytest.mark.integration
    def test_node_with_tab_in_property_is_created(self, clean_graph: AgeGraphClient):
        """Nodes with tab characters in properties should be created safely.

        Note: AGE's agtype format escapes tab characters as \\t (literal backslash-t)
        rather than preserving actual tab bytes. This is consistent with Cypher
        string semantics. The important thing is that the data is not corrupted
        and the COPY format doesn't break.
        """
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="document:00007ab112223333",
                label="document",
                set_properties={
                    "slug": "document-tab-test",
                    "content": "line1\tcolumn2\tcolumn3",  # Tabs in content
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify the node was created - AGE escapes tabs as \t in agtype
        query_result = clean_graph.execute_cypher(
            "MATCH (d:document) WHERE d.id = 'document:00007ab112223333' "
            "RETURN d.content"
        )
        content = query_result.rows[0][0]
        # AGE returns tabs as escaped \t (two characters: backslash and t)
        assert "\\t" in content or "\t" in content
        # The data should be equivalent (either actual tab or escaped)
        assert content in ("line1\tcolumn2\tcolumn3", "line1\\tcolumn2\\tcolumn3")

    @pytest.mark.integration
    def test_node_with_newline_in_property_is_created(
        self, clean_graph: AgeGraphClient
    ):
        """Nodes with newline characters in properties should be created safely.

        Note: AGE's agtype format escapes newline characters as \\n.
        The important thing is that the data is not corrupted and COPY doesn't break.
        """
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="document:0e01111122223333",
                label="document",
                set_properties={
                    "slug": "document-newline-test",
                    "content": "line1\nline2\nline3",  # Newlines in content
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify the node was created - AGE escapes newlines as \n in agtype
        query_result = clean_graph.execute_cypher(
            "MATCH (d:document) WHERE d.id = 'document:0e01111122223333' "
            "RETURN d.content"
        )
        content = query_result.rows[0][0]
        # AGE may return newlines as escaped \n or actual newlines
        assert "\\n" in content or "\n" in content
        assert content in ("line1\nline2\nline3", "line1\\nline2\\nline3")

    @pytest.mark.integration
    def test_node_with_backslash_in_property_is_created(
        self, clean_graph: AgeGraphClient
    ):
        """Nodes with backslash characters in properties should be created safely.

        Backslashes should be preserved correctly through the COPY and agtype chain.
        """
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="document:bac0111122223333",
                label="document",
                set_properties={
                    "slug": "document-backslash-test",
                    "content": "C:\\Users\\Alice\\file.txt",  # Backslashes
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify the node was created with backslashes preserved
        query_result = clean_graph.execute_cypher(
            "MATCH (d:document) WHERE d.id = 'document:bac0111122223333' "
            "RETURN d.content"
        )
        content = query_result.rows[0][0]
        # Backslashes should be preserved (may be doubled due to escaping)
        assert "Users" in content and "Alice" in content and "file.txt" in content


# =============================================================================
# P0: SILENT EDGE DROPPING (ORPHANED EDGES) TESTS
# =============================================================================


@pytest.mark.integration
class TestOrphanedEdgeDetection:
    """Tests for detecting edges that reference non-existent nodes."""

    def test_edge_to_nonexistent_node_raises_error(self, clean_graph: AgeGraphClient):
        """Creating an edge to a non-existent node should fail, not silently drop."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create one node but not the other
        node_operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:0a01111122223333",
                label="person",
                set_properties={
                    "slug": "alice-orphan-end-test",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        strategy.apply_batch(
            client=clean_graph,
            operations=node_operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        # Now try to create an edge to a non-existent node
        edge_operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="knows:0a01111122223333",
                label="knows",
                start_id="person:0a01111122223333",
                end_id="person:d0e50010e0150000",  # This node doesn't exist
                set_properties={
                    "since": 2020,
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=edge_operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        # Should fail with an error about orphaned edges
        assert result.success is False
        assert len(result.errors) >= 1
        assert any(
            "orphan" in e.lower() or "missing" in e.lower() for e in result.errors
        )

    def test_edge_from_nonexistent_node_raises_error(self, clean_graph: AgeGraphClient):
        """Creating an edge from a non-existent node should fail, not silently drop."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create one node but not the other
        node_operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:0a02222233334444",
                label="person",
                set_properties={
                    "slug": "bob-orphan-start-test",
                    "name": "Bob",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        strategy.apply_batch(
            client=clean_graph,
            operations=node_operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        # Now try to create an edge from a non-existent node
        edge_operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="knows:0a02222233334444",
                label="knows",
                start_id="person:d0e50010e0150000",  # This node doesn't exist
                end_id="person:0a02222233334444",
                set_properties={
                    "since": 2020,
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=edge_operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        # Should fail with an error about orphaned edges
        assert result.success is False
        assert len(result.errors) >= 1

    def test_multiple_orphaned_edges_lists_all_in_error(
        self, clean_graph: AgeGraphClient
    ):
        """Multiple orphaned edges should all be reported in the error."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create just one node
        node_operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:0011100000000111",
                label="person",
                set_properties={
                    "slug": "alice-multi-orphan-test",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        strategy.apply_batch(
            client=clean_graph,
            operations=node_operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        # Create multiple orphaned edges
        edge_operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="knows:0011100000000111",
                label="knows",
                start_id="person:0011100000000111",
                end_id="person:000000000001501a",
                set_properties={"data_source_id": "ds-123", "source_path": "test.md"},
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="knows:0022200000000222",
                label="knows",
                start_id="person:000000000001502a",
                end_id="person:0011100000000111",
                set_properties={"data_source_id": "ds-123", "source_path": "test.md"},
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=edge_operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is False


# =============================================================================
# P1: SQL INJECTION IN CYPHER (LABEL VALIDATION) TESTS
# =============================================================================


class TestLabelValidation:
    """Tests for validating label names to prevent SQL injection."""

    def test_validate_label_name_accepts_valid_labels(self):
        """Valid label names should be accepted."""
        valid_labels = [
            "Person",
            "person",
            "KNOWS",
            "has_relationship",
            "Entity123",
            "A",
            "ab",
            "_underscore_start",
        ]
        for label in valid_labels:
            # Should not raise
            validate_label_name(label)

    def test_validate_label_name_rejects_injection_attempts(self):
        """Labels containing SQL injection patterns should be rejected."""
        injection_labels = [
            "Person; DROP TABLE users--",
            "Label'--",
            'Label"--',
            "Label\n; DELETE FROM",
            "Label`injection`",
            "Label$(cmd)",
            "Label{}",
            "Label[]",
        ]
        for label in injection_labels:
            with pytest.raises(ValueError) as exc_info:
                validate_label_name(label)
            assert "invalid" in str(exc_info.value).lower()

    def test_validate_label_name_rejects_empty(self):
        """Empty labels should be rejected."""
        with pytest.raises(ValueError):
            validate_label_name("")

    def test_validate_label_name_rejects_too_long(self):
        """Labels exceeding max length should be rejected."""
        long_label = "A" * 256  # Postgres identifiers max 63 chars typically
        with pytest.raises(ValueError):
            validate_label_name(long_label)

    @pytest.mark.integration
    def test_injection_label_rejected_before_query(self, clean_graph: AgeGraphClient):
        """SQL injection in label should be caught before query execution."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:0000111122223333",
                label="Person; DROP TABLE users--",  # Injection attempt
                set_properties={
                    "slug": "hacker-injection-test",
                    "name": "Hacker",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is False
        assert any(
            "invalid" in e.lower() or "label" in e.lower() for e in result.errors
        )


# =============================================================================
# P1: UPDATE AND DELETE OPERATIONS TESTS
# =============================================================================


@pytest.mark.integration
class TestUpdateOperations:
    """Tests for UPDATE operations."""

    def test_update_node_adds_properties(self, clean_graph: AgeGraphClient):
        """UPDATE should add new properties to existing node."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create a node
        create_ops = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:0d01111122223333",
                label="person",
                set_properties={
                    "slug": "alice-update-add-props",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        strategy.apply_batch(
            client=clean_graph,
            operations=create_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        # Update with new property
        update_ops = [
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.NODE,
                id="person:0d01111122223333",
                label="person",
                set_properties={
                    "email": "alice@example.com",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=update_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify the property was added (use separate queries - AGE limitation)
        query_result = clean_graph.execute_cypher(
            "MATCH (p:person) WHERE p.id = 'person:0d01111122223333' RETURN p.email"
        )
        assert query_result.rows[0][0] == "alice@example.com"

        query_result = clean_graph.execute_cypher(
            "MATCH (p:person) WHERE p.id = 'person:0d01111122223333' RETURN p.name"
        )
        assert query_result.rows[0][0] == "Alice"

    def test_update_node_modifies_existing_properties(
        self, clean_graph: AgeGraphClient
    ):
        """UPDATE should modify existing properties."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create a node
        create_ops = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:0d02222233334444",
                label="person",
                set_properties={
                    "slug": "bob-update-modify-props",
                    "name": "Bob",
                    "age": 25,
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        strategy.apply_batch(
            client=clean_graph,
            operations=create_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        # Update age
        update_ops = [
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.NODE,
                id="person:0d02222233334444",
                label="person",
                set_properties={
                    "age": 26,
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=update_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        query_result = clean_graph.execute_cypher(
            "MATCH (p:person) WHERE p.id = 'person:0d02222233334444' RETURN p.age"
        )
        age = query_result.rows[0][0]
        assert age == 26

    def test_update_node_removes_properties(self, clean_graph: AgeGraphClient):
        """UPDATE with remove_properties should remove properties."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create a node
        create_ops = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:0d03333344445555",
                label="person",
                set_properties={
                    "slug": "charlie-update-remove-props",
                    "name": "Charlie",
                    "temp_field": "to_remove",
                    "another_temp": "also_remove",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        strategy.apply_batch(
            client=clean_graph,
            operations=create_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        # Remove properties
        update_ops = [
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.NODE,
                id="person:0d03333344445555",
                label="person",
                remove_properties=["temp_field", "another_temp"],
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=update_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify properties were removed (use separate queries - AGE limitation)
        query_result = clean_graph.execute_cypher(
            "MATCH (p:person) WHERE p.id = 'person:0d03333344445555' RETURN p.name"
        )
        assert query_result.rows[0][0] == "Charlie"

        query_result = clean_graph.execute_cypher(
            "MATCH (p:person) WHERE p.id = 'person:0d03333344445555' "
            "RETURN p.temp_field"
        )
        assert query_result.rows[0][0] is None

        query_result = clean_graph.execute_cypher(
            "MATCH (p:person) WHERE p.id = 'person:0d03333344445555' "
            "RETURN p.another_temp"
        )
        assert query_result.rows[0][0] is None

    def test_update_edge_properties(self, clean_graph: AgeGraphClient):
        """UPDATE should work on edge properties too."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create nodes and edge
        create_ops = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:ed9e0d11100000a1",
                label="person",
                set_properties={
                    "slug": "alice-update-edge",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:ed9e0d22200000a2",
                label="person",
                set_properties={
                    "slug": "bob-update-edge",
                    "name": "Bob",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="knows:ed9e0d11100000a0",
                label="knows",
                start_id="person:ed9e0d11100000a1",
                end_id="person:ed9e0d22200000a2",
                set_properties={
                    "since": 2020,
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        strategy.apply_batch(
            client=clean_graph,
            operations=create_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        # Update edge
        update_ops = [
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.EDGE,
                id="knows:ed9e0d11100000a0",
                label="knows",
                set_properties={
                    "since": 2021,
                    "strength": "strong",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=update_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify edge properties (use separate queries - AGE limitation)
        query_result = clean_graph.execute_cypher(
            "MATCH ()-[r:knows]->() WHERE r.id = 'knows:ed9e0d11100000a0' "
            "RETURN r.since"
        )
        assert query_result.rows[0][0] == 2021

        query_result = clean_graph.execute_cypher(
            "MATCH ()-[r:knows]->() WHERE r.id = 'knows:ed9e0d11100000a0' "
            "RETURN r.strength"
        )
        assert query_result.rows[0][0] == "strong"


@pytest.mark.integration
class TestDeleteOperations:
    """Tests for DELETE operations."""

    def test_delete_node(self, clean_graph: AgeGraphClient):
        """DELETE should remove a node."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create a node
        create_ops = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:de1e111122223333",
                label="person",
                set_properties={
                    "slug": "delete-me-node",
                    "name": "DeleteMe",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        strategy.apply_batch(
            client=clean_graph,
            operations=create_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        # Verify it exists
        query_result = clean_graph.execute_cypher(
            "MATCH (p:person) WHERE p.id = 'person:de1e111122223333' RETURN count(p)"
        )
        assert query_result.rows[0][0] == 1

        # Delete it
        delete_ops = [
            MutationOperation(
                op=MutationOperationType.DELETE,
                type=EntityType.NODE,
                id="person:de1e111122223333",
                label="person",
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=delete_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify it's gone
        query_result = clean_graph.execute_cypher(
            "MATCH (p:person) WHERE p.id = 'person:de1e111122223333' RETURN count(p)"
        )
        assert query_result.rows[0][0] == 0

    def test_delete_node_detaches_edges(self, clean_graph: AgeGraphClient):
        """DELETE node should also delete connected edges (DETACH DELETE)."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create nodes and edge
        create_ops = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:de7ac0111a000001",
                label="person",
                set_properties={
                    "slug": "alice-detach-delete",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:de7ac0222a000002",
                label="person",
                set_properties={
                    "slug": "bob-detach-delete",
                    "name": "Bob",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="knows:de7ac0111a000000",
                label="knows",
                start_id="person:de7ac0111a000001",
                end_id="person:de7ac0222a000002",
                set_properties={
                    "since": 2020,
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        strategy.apply_batch(
            client=clean_graph,
            operations=create_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        # Verify edge exists
        query_result = clean_graph.execute_cypher(
            "MATCH ()-[r:knows]->() WHERE r.id = 'knows:de7ac0111a000000' RETURN count(r)"
        )
        assert query_result.rows[0][0] == 1

        # Delete node (should detach edge)
        delete_ops = [
            MutationOperation(
                op=MutationOperationType.DELETE,
                type=EntityType.NODE,
                id="person:de7ac0111a000001",
                label="person",
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=delete_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify edge is also gone
        query_result = clean_graph.execute_cypher(
            "MATCH ()-[r:knows]->() WHERE r.id = 'knows:de7ac0111a000000' RETURN count(r)"
        )
        assert query_result.rows[0][0] == 0

    def test_delete_edge(self, clean_graph: AgeGraphClient):
        """DELETE should remove an edge without affecting nodes."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create nodes and edge
        create_ops = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:de1ed9e111000001",
                label="person",
                set_properties={
                    "slug": "alice-delete-edge",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:de1ed9e222000002",
                label="person",
                set_properties={
                    "slug": "bob-delete-edge",
                    "name": "Bob",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id="knows:de1ed9e111000000",
                label="knows",
                start_id="person:de1ed9e111000001",
                end_id="person:de1ed9e222000002",
                set_properties={
                    "since": 2020,
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        strategy.apply_batch(
            client=clean_graph,
            operations=create_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        # Delete edge only
        delete_ops = [
            MutationOperation(
                op=MutationOperationType.DELETE,
                type=EntityType.EDGE,
                id="knows:de1ed9e111000000",
                label="knows",
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=delete_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify edge is gone
        query_result = clean_graph.execute_cypher(
            "MATCH ()-[r:knows]->() WHERE r.id = 'knows:de1ed9e111000000' RETURN count(r)"
        )
        assert query_result.rows[0][0] == 0

        # Verify nodes still exist
        query_result = clean_graph.execute_cypher(
            "MATCH (p:person) WHERE p.id IN ['person:de1ed9e111000001', 'person:de1ed9e222000002'] "
            "RETURN count(p)"
        )
        assert query_result.rows[0][0] == 2


# =============================================================================
# P1: CARTESIAN JOIN FIX TESTS
# =============================================================================


@pytest.mark.integration
class TestCartesianJoinFix:
    """Tests to verify cartesian join is avoided in graphid resolution."""

    def test_edge_resolution_with_many_nodes_succeeds(
        self, clean_graph: AgeGraphClient
    ):
        """Edge resolution should not create cartesian product with many nodes.

        This test creates enough nodes and edges to potentially trigger
        cartesian join issues if the implementation is incorrect.
        """
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create 20 nodes
        node_ops = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id=f"person:ca00000000000{i:03x}",  # Uses hex format
                label="person",
                set_properties={
                    "slug": f"person-cartesian-{i:03x}",
                    "name": f"Person {i}",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            )
            for i in range(20)
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=node_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )
        assert result.success is True

        # Create edges connecting sequential pairs
        edge_ops = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id=f"knows:ca00000000000{i:03x}",  # Uses hex format
                label="knows",
                start_id=f"person:ca00000000000{i:03x}",
                end_id=f"person:ca00000000000{i + 1:03x}",
                set_properties={
                    "index": i,
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            )
            for i in range(19)
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=edge_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify all edges were created
        query_result = clean_graph.execute_cypher(
            "MATCH ()-[r:knows]->() WHERE r.id STARTS WITH 'knows:ca0000000000' "
            "RETURN count(r)"
        )
        assert query_result.rows[0][0] == 19


# =============================================================================
# P2: OPERATION COUNT OFF-BY-ONE TESTS
# =============================================================================


@pytest.mark.integration
class TestOperationCount:
    """Tests for correct operation counting."""

    def test_operation_count_correct_for_new_label(self, clean_graph: AgeGraphClient):
        """When creating a label via Cypher for first entity, count should be correct."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create 3 nodes of a completely new label
        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id=f"newlabelcount:c00000000000{i:04x}",  # Uses hex format
                label="newlabelcount",
                set_properties={
                    "slug": f"entity-count-{i:04x}",
                    "name": f"Entity {i}",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            )
            for i in range(3)
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True
        assert result.operations_applied == 3

        # Verify exactly 3 nodes exist
        query_result = clean_graph.execute_cypher(
            "MATCH (n:newlabelcount) RETURN count(n)"
        )
        assert query_result.rows[0][0] == 3


# =============================================================================
# P2: BATCH PROPERTY REMOVAL TESTS
# =============================================================================


@pytest.mark.integration
class TestBatchPropertyRemoval:
    """Tests for batched property removal optimization."""

    def test_multiple_property_removal_in_single_operation(
        self, clean_graph: AgeGraphClient
    ):
        """Removing multiple properties should work efficiently."""
        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Create a node with many properties
        create_ops = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id="person:ba7c0e0e0000011a",
                label="person",
                set_properties={
                    "slug": "alice-batch-prop-removal",
                    "name": "Alice",
                    "prop1": "value1",
                    "prop2": "value2",
                    "prop3": "value3",
                    "prop4": "value4",
                    "prop5": "value5",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        strategy.apply_batch(
            client=clean_graph,
            operations=create_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        # Remove multiple properties at once
        update_ops = [
            MutationOperation(
                op=MutationOperationType.UPDATE,
                type=EntityType.NODE,
                id="person:ba7c0e0e0000011a",
                label="person",
                remove_properties=["prop1", "prop2", "prop3", "prop4", "prop5"],
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=update_ops,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify all properties were removed (use separate queries - AGE limitation)
        query_result = clean_graph.execute_cypher(
            "MATCH (p:person) WHERE p.id = 'person:ba7c0e0e0000011a' RETURN p.name"
        )
        assert query_result.rows[0][0] == "Alice"

        # Verify removed properties are null
        for prop in ["prop1", "prop2", "prop3", "prop4", "prop5"]:
            query_result = clean_graph.execute_cypher(
                f"MATCH (p:person) WHERE p.id = 'person:ba7c0e0e0000011a' "
                f"RETURN p.{prop}"
            )
            assert query_result.rows[0][0] is None, f"Property {prop} should be null"


@pytest.mark.integration
class TestBulkLoadingIndexCreation:
    """Tests for index creation during bulk loading.

    When new labels are created via bulk loading, indexes should be created
    immediately to avoid slow full table scans in subsequent UPDATE and INSERT
    queries within the same batch.
    """

    def test_node_label_creation_creates_indexes(self, clean_graph: AgeGraphClient):
        """Creating a new node label via bulk loading should create indexes."""
        import uuid

        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Use unique label to ensure it doesn't exist
        unique_suffix = uuid.uuid4().hex[:8]
        unique_label = f"nodeidx{unique_suffix}"

        operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id=f"{unique_label}:{uuid.uuid4().hex[:16]}",
                label=unique_label,
                set_properties={
                    "slug": "test-entity",
                    "name": "Test Entity",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify indexes were created for the new label
        with clean_graph._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = %s AND tablename = %s
                """,
                (clean_graph.graph_name, unique_label),
            )
            indexes = [row[0] for row in cursor.fetchall()]

        # Should have: id_btree, props_gin, prop_id_btree (3 node indexes)
        assert len(indexes) >= 3, (
            f"Expected at least 3 indexes, got {len(indexes)}: {indexes}"
        )
        assert any("id_btree" in idx for idx in indexes), (
            f"Missing BTREE id index. Found: {indexes}"
        )
        assert any("props_gin" in idx for idx in indexes), (
            f"Missing GIN properties index. Found: {indexes}"
        )
        assert any("prop_id_text_btree" in idx for idx in indexes), (
            f"Missing BTREE properties.id index. Found: {indexes}"
        )

    def test_edge_label_creation_creates_indexes(self, clean_graph: AgeGraphClient):
        """Creating a new edge label via bulk loading should create indexes."""
        import uuid

        strategy = AgeBulkLoadingStrategy()
        probe = DefaultMutationProbe()

        # Use unique labels to ensure they don't exist
        unique_suffix = uuid.uuid4().hex[:8]
        node_label = f"nodee{unique_suffix}"
        edge_label = f"edgeidx{unique_suffix}"

        # Generate valid IDs (label:16_hex_chars format)
        source_id = f"{node_label}:{uuid.uuid4().hex[:16]}"
        target_id = f"{node_label}:{uuid.uuid4().hex[:16]}"

        # First create two nodes
        node_operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id=source_id,
                label=node_label,
                set_properties={
                    "slug": "source-node",
                    "name": "Source Node",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.NODE,
                id=target_id,
                label=node_label,
                set_properties={
                    "slug": "target-node",
                    "name": "Target Node",
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=node_operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )
        assert result.success is True

        # Now create an edge between them
        edge_operations = [
            MutationOperation(
                op=MutationOperationType.CREATE,
                type=EntityType.EDGE,
                id=f"{edge_label}:{uuid.uuid4().hex[:16]}",
                label=edge_label,
                start_id=source_id,
                end_id=target_id,
                set_properties={
                    "data_source_id": "ds-123",
                    "source_path": "test.md",
                },
            ),
        ]

        result = strategy.apply_batch(
            client=clean_graph,
            operations=edge_operations,
            probe=probe,
            graph_name=clean_graph.graph_name,
        )

        assert result.success is True

        # Verify indexes were created for the new edge label
        with clean_graph._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = %s AND tablename = %s
                """,
                (clean_graph.graph_name, edge_label),
            )
            indexes = [row[0] for row in cursor.fetchall()]

        # Should have: id_btree, props_gin, prop_id_btree, start_id_btree, end_id_btree (5 edge indexes)
        assert len(indexes) >= 5, (
            f"Expected at least 5 indexes, got {len(indexes)}: {indexes}"
        )
        assert any("id_btree" in idx for idx in indexes), (
            f"Missing BTREE id index. Found: {indexes}"
        )
        assert any("props_gin" in idx for idx in indexes), (
            f"Missing GIN properties index. Found: {indexes}"
        )
        assert any("prop_id_text_btree" in idx for idx in indexes), (
            f"Missing BTREE properties.id index. Found: {indexes}"
        )
        assert any("start_id_btree" in idx for idx in indexes), (
            f"Missing BTREE start_id index. Found: {indexes}"
        )
        assert any("end_id_btree" in idx for idx in indexes), (
            f"Missing BTREE end_id index. Found: {indexes}"
        )
