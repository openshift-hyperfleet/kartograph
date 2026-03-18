"""Repository protocols (ports) for Management bounded context.

Repository protocols define the interface for persisting and retrieving
Management aggregates. Implementations use PostgreSQL for storage
and the transactional outbox pattern for domain event publishing.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from management.domain.aggregates import DataSource, KnowledgeGraph
from management.domain.entities import DataSourceSyncRun
from management.domain.value_objects import DataSourceId, KnowledgeGraphId


@runtime_checkable
class IKnowledgeGraphRepository(Protocol):
    """Repository for KnowledgeGraph aggregate persistence.

    Implementations coordinate PostgreSQL for metadata storage and
    the transactional outbox pattern for domain event publishing.
    Returns fully hydrated KnowledgeGraph aggregates per DDD pattern.
    """

    async def save(self, knowledge_graph: KnowledgeGraph) -> None:
        """Persist a knowledge graph aggregate (upsert).

        Creates a new knowledge graph or updates an existing one. Persists
        metadata to PostgreSQL and domain events to the outbox.

        Args:
            knowledge_graph: The KnowledgeGraph aggregate to persist

        Raises:
            management.ports.exceptions.DuplicateKnowledgeGraphNameError:
                If name already exists in tenant
        """
        ...

    async def get_by_id(
        self, knowledge_graph_id: KnowledgeGraphId
    ) -> KnowledgeGraph | None:
        """Retrieve a knowledge graph by its ID.

        Args:
            knowledge_graph_id: The unique identifier of the knowledge graph

        Returns:
            The KnowledgeGraph aggregate, or None if not found
        """
        ...

    async def find_by_tenant(
        self, tenant_id: str, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[KnowledgeGraph], int]:
        """List knowledge graphs with pagination.

        Args:
            tenant_id: The tenant to list knowledge graphs for
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (items for the requested page, total count)
        """
        ...

    async def delete(self, knowledge_graph: KnowledgeGraph) -> bool:
        """Delete a knowledge graph and emit domain events.

        The knowledge graph should have mark_for_deletion() called before
        this method to record the KnowledgeGraphDeleted event. The outbox
        worker will handle any necessary cleanup.

        Args:
            knowledge_graph: The KnowledgeGraph aggregate to delete
                (with deletion event recorded)

        Returns:
            True if deleted, False if not found
        """
        ...


@runtime_checkable
class IDataSourceRepository(Protocol):
    """Repository for DataSource aggregate persistence.

    Implementations coordinate PostgreSQL for metadata storage and
    the transactional outbox pattern for domain event publishing.
    Returns fully hydrated DataSource aggregates per DDD pattern.
    """

    async def save(self, data_source: DataSource) -> None:
        """Persist a data source aggregate (upsert).

        Creates a new data source or updates an existing one. Persists
        metadata to PostgreSQL and domain events to the outbox.

        Args:
            data_source: The DataSource aggregate to persist
        """
        ...

    async def get_by_id(self, data_source_id: DataSourceId) -> DataSource | None:
        """Retrieve a data source by its ID.

        Args:
            data_source_id: The unique identifier of the data source

        Returns:
            The DataSource aggregate, or None if not found
        """
        ...

    async def find_by_knowledge_graph(
        self, knowledge_graph_id: str, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[DataSource], int]:
        """List data sources with pagination.

        Args:
            knowledge_graph_id: The knowledge graph to list data sources for
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (items for the requested page, total count)
        """
        ...

    async def delete(self, data_source: DataSource) -> bool:
        """Delete a data source and emit domain events.

        The data source should have mark_for_deletion() called before
        this method to record the DataSourceDeleted event. The outbox
        worker will handle any necessary cleanup.

        Args:
            data_source: The DataSource aggregate to delete
                (with deletion event recorded)

        Returns:
            True if deleted, False if not found
        """
        ...


@runtime_checkable
class IDataSourceSyncRunRepository(Protocol):
    """Repository for DataSourceSyncRun entity persistence.

    Simple repository for sync run tracking. Sync runs are entities
    (not aggregates) and do not emit domain events through the outbox.
    """

    async def save(self, sync_run: DataSourceSyncRun) -> None:
        """Persist a sync run (insert or update).

        Creates a new sync run record or updates an existing one.
        Does not use the outbox pattern since sync runs are entities,
        not aggregate roots.

        Args:
            sync_run: The DataSourceSyncRun entity to persist
        """
        ...

    async def get_by_id(self, sync_run_id: str) -> DataSourceSyncRun | None:
        """Retrieve a sync run by its ID.

        Args:
            sync_run_id: The unique identifier of the sync run

        Returns:
            The DataSourceSyncRun entity, or None if not found
        """
        ...

    async def find_by_data_source(self, data_source_id: str) -> list[DataSourceSyncRun]:
        """List all sync runs for a data source.

        Args:
            data_source_id: The data source to list sync runs for

        Returns:
            List of DataSourceSyncRun entities for the data source
        """
        ...
