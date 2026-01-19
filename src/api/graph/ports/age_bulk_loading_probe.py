"""Observability protocol for AGE bulk loading infrastructure.

This probe captures infrastructure-level events specific to Apache AGE's
bulk loading implementation. These are distinct from domain-level mutation
events captured by MutationProbe.

Following Domain Oriented Observability pattern:
https://martinfowler.com/articles/domain-oriented-observability.html
"""

from __future__ import annotations

from typing import Protocol


class AgeBulkLoadingProbe(Protocol):
    """Infrastructure probe for AGE bulk loading operations.

    Captures timing and diagnostic information for the staging table
    pattern used by AgeBulkLoadingStrategy. These events are implementation
    details of the AGE adapter, not domain-level concerns.

    All methods should be non-blocking and safe to call in hot paths.
    """

    def staging_table_created(
        self,
        table_name: str,
        entity_type: str,
    ) -> None:
        """Record that a staging table was created.

        Args:
            table_name: Name of the staging table
            entity_type: "node" or "edge"
        """
        ...

    def staging_data_copied(
        self,
        table_name: str,
        entity_type: str,
        row_count: int,
        duration_ms: float,
    ) -> None:
        """Record that data was COPYed to a staging table.

        Args:
            table_name: Name of the staging table
            entity_type: "node" or "edge"
            row_count: Number of rows copied
            duration_ms: Time taken for the COPY operation
        """
        ...

    def staging_index_created(
        self,
        table_name: str,
        index_type: str,
        duration_ms: float,
    ) -> None:
        """Record that an index was created on a staging table.

        Args:
            table_name: Name of the staging table
            index_type: Type of index ("label", "start_id", "end_id")
            duration_ms: Time taken to create the index
        """
        ...

    def graphids_resolved(
        self,
        edge_count: int,
        resolved_count: int,
        duration_ms: float,
    ) -> None:
        """Record that edge graphids were resolved.

        Args:
            edge_count: Total number of edges in staging
            resolved_count: Number of edges with resolved graphids
            duration_ms: Time taken for resolution
        """
        ...

    def labels_pre_created(
        self,
        entity_type: str,
        label_count: int,
        new_label_count: int,
        duration_ms: float,
    ) -> None:
        """Record that labels were pre-created in batch.

        Args:
            entity_type: "node" or "edge"
            label_count: Total number of distinct labels
            new_label_count: Number of labels that were newly created
            duration_ms: Time taken to check and create labels
        """
        ...

    def indexes_pre_created(
        self,
        entity_type: str,
        label_count: int,
        index_count: int,
        duration_ms: float,
    ) -> None:
        """Record that indexes were pre-created for new labels.

        Args:
            entity_type: "node" or "edge"
            label_count: Number of labels that received indexes
            index_count: Total number of indexes created
            duration_ms: Time taken to create indexes
        """
        ...
