"""DataSource application service for Management bounded context.

Orchestrates data source operations with proper authorization,
credential management, transaction management, and observability.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from management.application.observability import (
    DataSourceServiceProbe,
    DefaultDataSourceServiceProbe,
)
from management.domain.aggregates import DataSource
from management.domain.entities import DataSourceSyncRun
from management.domain.value_objects import DataSourceId, KnowledgeGraphId
from management.ports.exceptions import DuplicateDataSourceNameError, UnauthorizedError
from management.ports.repositories import (
    IDataSourceRepository,
    IDataSourceSyncRunRepository,
    IKnowledgeGraphRepository,
)
from management.ports.secret_store import ISecretStoreRepository
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)
from shared_kernel.datasource_types import DataSourceAdapterType


class DataSourceService:
    """Application service for data source management.

    Orchestrates data source operations with proper tenant scoping,
    authorization checks, credential management, and observability.
    """

    def __init__(
        self,
        session: AsyncSession,
        data_source_repository: IDataSourceRepository,
        knowledge_graph_repository: IKnowledgeGraphRepository,
        secret_store: ISecretStoreRepository,
        sync_run_repository: IDataSourceSyncRunRepository,
        authz: AuthorizationProvider,
        scope_to_tenant: str,
        probe: DataSourceServiceProbe | None = None,
    ) -> None:
        """Initialize DataSourceService with dependencies.

        Args:
            session: Database session for transaction management
            data_source_repository: Repository for DS persistence
            knowledge_graph_repository: Repository for KG lookups
            secret_store: Secret store for credential management
            sync_run_repository: Repository for sync run tracking
            authz: Authorization provider for permission checks
            scope_to_tenant: Tenant ID string to scope this service to
            probe: Optional domain probe for observability
        """
        self._session = session
        self._ds_repo = data_source_repository
        self._kg_repo = knowledge_graph_repository
        self._secret_store = secret_store
        self._sync_run_repo = sync_run_repository
        self._authz = authz
        self._scope_to_tenant = scope_to_tenant
        self._probe = probe or DefaultDataSourceServiceProbe()

    async def _check_permission(
        self,
        user_id: str,
        resource_type: ResourceType,
        resource_id: str,
        permission: Permission,
    ) -> bool:
        """Check if user has permission on a resource.

        Args:
            user_id: The user to check
            resource_type: Type of resource
            resource_id: ID of the resource
            permission: The permission to check

        Returns:
            True if user has permission, False otherwise
        """
        resource = format_resource(resource_type, resource_id)
        subject = format_subject(ResourceType.USER, user_id)
        return await self._authz.check_permission(
            resource=resource,
            permission=permission,
            subject=subject,
        )

    async def create(
        self,
        user_id: str,
        kg_id: str,
        name: str,
        adapter_type: DataSourceAdapterType,
        connection_config: dict[str, str],
        raw_credentials: dict[str, str] | None = None,
    ) -> DataSource:
        """Create a new data source in a knowledge graph.

        Args:
            user_id: The user creating the DS
            kg_id: The knowledge graph to create the DS in
            name: Name of the data source
            adapter_type: Type of adapter (e.g., GITHUB)
            connection_config: Connection configuration key-value pairs
            raw_credentials: Optional credentials to encrypt and store

        Returns:
            The created DataSource aggregate

        Raises:
            UnauthorizedError: If user lacks EDIT permission on KG
            ValueError: If KG not found or belongs to different tenant
        """
        has_edit = await self._check_permission(
            user_id=user_id,
            resource_type=ResourceType.KNOWLEDGE_GRAPH,
            resource_id=kg_id,
            permission=Permission.EDIT,
        )

        if not has_edit:
            self._probe.permission_denied(
                user_id=user_id,
                resource_id=kg_id,
                permission=Permission.EDIT,
            )
            raise UnauthorizedError(
                f"User {user_id} lacks edit permission on knowledge graph {kg_id}"
            )

        # Verify KG exists and belongs to tenant
        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None:
            raise ValueError(f"Knowledge graph {kg_id} not found")
        if kg.tenant_id != self._scope_to_tenant:
            raise ValueError(f"Knowledge graph {kg_id} belongs to different tenant")

        try:
            async with self._session.begin():
                ds = DataSource.create(
                    knowledge_graph_id=kg_id,
                    tenant_id=self._scope_to_tenant,
                    name=name,
                    adapter_type=adapter_type,
                    connection_config=connection_config,
                    created_by=user_id,
                )

                if raw_credentials is not None:
                    cred_path = f"datasource/{ds.id.value}/credentials"
                    await self._secret_store.store(
                        path=cred_path,
                        tenant_id=self._scope_to_tenant,
                        credentials=raw_credentials,
                    )
                    ds.credentials_path = cred_path

                await self._ds_repo.save(ds)
        except IntegrityError as e:
            if "uq_data_sources_kg_name" in str(e):
                self._probe.data_source_creation_failed(
                    kg_id=kg_id, name=name, error="duplicate name"
                )
                raise DuplicateDataSourceNameError(
                    f"Data source '{name}' already exists in knowledge graph '{kg_id}'"
                ) from e
            raise

        self._probe.data_source_created(
            ds_id=ds.id.value,
            kg_id=kg_id,
            tenant_id=self._scope_to_tenant,
            name=name,
        )

        return ds

    async def get(
        self,
        user_id: str,
        ds_id: str,
    ) -> DataSource | None:
        """Get a data source by ID with authorization check.

        Args:
            user_id: The user requesting access
            ds_id: The data source ID

        Returns:
            The DataSource aggregate, or None if not found or if
            the caller lacks VIEW permission (to avoid existence leakage)
        """
        ds = await self._ds_repo.get_by_id(DataSourceId(value=ds_id))
        if ds is None:
            return None

        if ds.tenant_id != self._scope_to_tenant:
            return None

        has_view = await self._check_permission(
            user_id=user_id,
            resource_type=ResourceType.DATA_SOURCE,
            resource_id=ds_id,
            permission=Permission.VIEW,
        )

        if not has_view:
            return None

        self._probe.data_source_retrieved(ds_id=ds_id)
        return ds

    async def list_for_knowledge_graph(
        self,
        user_id: str,
        kg_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[DataSource], int]:
        """List data sources for a knowledge graph with pagination.

        Args:
            user_id: The user requesting the list
            kg_id: The knowledge graph to list DSes for
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (paginated DataSource aggregates, total count)

        Raises:
            UnauthorizedError: If user lacks VIEW permission on KG
        """
        has_view = await self._check_permission(
            user_id=user_id,
            resource_type=ResourceType.KNOWLEDGE_GRAPH,
            resource_id=kg_id,
            permission=Permission.VIEW,
        )

        if not has_view:
            self._probe.permission_denied(
                user_id=user_id,
                resource_id=kg_id,
                permission=Permission.VIEW,
            )
            raise UnauthorizedError(
                f"User {user_id} lacks view permission on knowledge graph {kg_id}"
            )

        # Verify KG belongs to tenant (defense-in-depth)
        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None or kg.tenant_id != self._scope_to_tenant:
            raise UnauthorizedError(f"Knowledge graph {kg_id} not accessible")

        data_sources, total = await self._ds_repo.find_by_knowledge_graph(
            kg_id, offset=offset, limit=limit
        )

        self._probe.data_sources_listed(
            kg_id=kg_id,
            count=len(data_sources),
        )

        return data_sources, total

    async def update(
        self,
        user_id: str,
        ds_id: str,
        name: str | None = None,
        connection_config: dict[str, str] | None = None,
        raw_credentials: dict[str, str] | None = None,
    ) -> DataSource:
        """Update a data source's configuration.

        Args:
            user_id: The user performing the update
            ds_id: The data source ID
            name: Optional new name
            connection_config: Optional new connection configuration
            raw_credentials: Optional new credentials to encrypt and store

        Returns:
            The updated DataSource aggregate

        Raises:
            UnauthorizedError: If user lacks EDIT permission
            ValueError: If DS not found
        """
        has_edit = await self._check_permission(
            user_id=user_id,
            resource_type=ResourceType.DATA_SOURCE,
            resource_id=ds_id,
            permission=Permission.EDIT,
        )

        if not has_edit:
            self._probe.permission_denied(
                user_id=user_id,
                resource_id=ds_id,
                permission=Permission.EDIT,
            )
            raise UnauthorizedError(
                f"User {user_id} lacks edit permission on data source {ds_id}"
            )

        ds = await self._ds_repo.get_by_id(DataSourceId(value=ds_id))
        if ds is None:
            raise ValueError(f"Data source {ds_id} not found")

        if ds.tenant_id != self._scope_to_tenant:
            raise ValueError(f"Data source {ds_id} not found")

        try:
            async with self._session.begin():
                if name is not None or connection_config is not None:
                    ds.update_connection(
                        name=name if name is not None else ds.name,
                        connection_config=connection_config
                        if connection_config is not None
                        else ds.connection_config,
                        credentials_path=ds.credentials_path,
                        updated_by=user_id,
                    )

                if raw_credentials is not None:
                    cred_path = f"datasource/{ds.id.value}/credentials"
                    await self._secret_store.store(
                        path=cred_path,
                        tenant_id=self._scope_to_tenant,
                        credentials=raw_credentials,
                    )
                    ds.credentials_path = cred_path

                await self._ds_repo.save(ds)
        except IntegrityError as e:
            if "uq_data_sources_kg_name" in str(e):
                self._probe.data_source_creation_failed(
                    kg_id=ds.knowledge_graph_id,
                    name=name or ds.name,
                    error="duplicate name",
                )
                raise DuplicateDataSourceNameError(
                    f"Data source '{name or ds.name}' already exists in knowledge graph '{ds.knowledge_graph_id}'"
                ) from e
            raise

        if name is not None:
            self._probe.data_source_updated(ds_id=ds_id, name=name)
        else:
            self._probe.data_source_updated(ds_id=ds_id, name=ds.name)

        return ds

    async def delete(
        self,
        user_id: str,
        ds_id: str,
    ) -> bool:
        """Delete a data source.

        Args:
            user_id: The user performing the deletion
            ds_id: The data source ID

        Returns:
            True if deleted, False if not found

        Raises:
            UnauthorizedError: If user lacks MANAGE permission
        """
        has_manage = await self._check_permission(
            user_id=user_id,
            resource_type=ResourceType.DATA_SOURCE,
            resource_id=ds_id,
            permission=Permission.MANAGE,
        )

        if not has_manage:
            self._probe.permission_denied(
                user_id=user_id,
                resource_id=ds_id,
                permission=Permission.MANAGE,
            )
            raise UnauthorizedError(
                f"User {user_id} lacks manage permission on data source {ds_id}"
            )

        ds = await self._ds_repo.get_by_id(DataSourceId(value=ds_id))
        if ds is None:
            return False

        if ds.tenant_id != self._scope_to_tenant:
            return False

        async with self._session.begin():
            if ds.credentials_path:
                await self._secret_store.delete(
                    path=ds.credentials_path,
                    tenant_id=self._scope_to_tenant,
                )

            ds.mark_for_deletion(deleted_by=user_id)
            await self._ds_repo.delete(ds)

        self._probe.data_source_deleted(ds_id=ds_id)

        return True

    async def trigger_sync(
        self,
        user_id: str,
        ds_id: str,
    ) -> DataSourceSyncRun:
        """Trigger a sync for a data source.

        Args:
            user_id: The user triggering the sync
            ds_id: The data source ID

        Returns:
            The created DataSourceSyncRun entity

        Raises:
            UnauthorizedError: If user lacks MANAGE permission
            ValueError: If DS not found
        """
        has_manage = await self._check_permission(
            user_id=user_id,
            resource_type=ResourceType.DATA_SOURCE,
            resource_id=ds_id,
            permission=Permission.MANAGE,
        )

        if not has_manage:
            self._probe.permission_denied(
                user_id=user_id,
                resource_id=ds_id,
                permission=Permission.MANAGE,
            )
            raise UnauthorizedError(
                f"User {user_id} lacks manage permission on data source {ds_id}"
            )

        ds = await self._ds_repo.get_by_id(DataSourceId(value=ds_id))
        if ds is None:
            raise ValueError(f"Data source {ds_id} not found")

        if ds.tenant_id != self._scope_to_tenant:
            raise ValueError(f"Data source {ds_id} not found")

        now = datetime.now(UTC)

        async with self._session.begin():
            sync_run = DataSourceSyncRun(
                id=str(ULID()),
                data_source_id=ds.id.value,
                status="pending",
                started_at=now,
                completed_at=None,
                error=None,
                created_at=now,
            )
            await self._sync_run_repo.save(sync_run)

            # Record sync requested event on the data source aggregate
            ds.request_sync(requested_by=user_id)
            await self._ds_repo.save(ds)

        self._probe.sync_requested(ds_id=ds_id)

        return sync_run
