"""DataSource application service for Management bounded context.

Orchestrates data source operations with proper authorization,
credential management, transaction management, and observability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from management.application.observability import (
    DataSourceServiceProbe,
    DefaultDataSourceServiceProbe,
)
from management.domain.aggregates import DataSource
from management.domain.entities import DataSourceSyncRun
from management.domain.value_objects import DataSourceId, KnowledgeGraphId, Ontology
from management.ports.exceptions import UnauthorizedError
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


@dataclass
class DataSourceWithLatestRun:
    """Pair of a DataSource aggregate and its most recent sync run (if any).

    Used by list_all_for_user to return a flat list of data sources with
    their latest sync status embedded — avoiding N+1 API calls from the
    sidebar navigation badge.
    """

    data_source: DataSource
    latest_sync_run: DataSourceSyncRun | None


@dataclass
class RunControlResult:
    """Result payload for extraction run-control commands."""

    action: str
    affected_count: int
    updated_runs: list[DataSourceSyncRun]
    started_run: DataSourceSyncRun | None = None


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
        ontology: Ontology | None = None,
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

        ds = DataSource.create(
            knowledge_graph_id=kg_id,
            tenant_id=self._scope_to_tenant,
            name=name,
            adapter_type=adapter_type,
            connection_config=connection_config,
            ontology=ontology,
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
        await self._session.commit()

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
    ) -> list[DataSource]:
        """List data sources for a knowledge graph.

        Args:
            user_id: The user requesting the list
            kg_id: The knowledge graph to list DSes for

        Returns:
            List of DataSource aggregates

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

        data_sources = await self._ds_repo.find_by_knowledge_graph(kg_id)

        self._probe.data_sources_listed(
            kg_id=kg_id,
            count=len(data_sources),
        )

        return data_sources

    async def list_all_for_user(
        self,
        user_id: str,
    ) -> list[DataSourceWithLatestRun]:
        """Return all data sources accessible to the user across the tenant.

        Discovers all knowledge graphs in the current tenant, filters to those
        the user has VIEW permission on, then aggregates their data sources with
        the latest sync run per source. This enables the sidebar navigation badge
        to show a live count of active syncs with a single API call.

        Args:
            user_id: Authenticated user requesting the list.

        Returns:
            List of DataSourceWithLatestRun pairs (data source + optional latest run).
        """
        all_kgs = await self._kg_repo.find_by_tenant(self._scope_to_tenant)

        result: list[DataSourceWithLatestRun] = []
        for kg in all_kgs:
            has_view = await self._check_permission(
                user_id=user_id,
                resource_type=ResourceType.KNOWLEDGE_GRAPH,
                resource_id=kg.id.value,
                permission=Permission.VIEW,
            )
            if not has_view:
                continue

            data_sources = await self._ds_repo.find_by_knowledge_graph(kg.id.value)
            for ds in data_sources:
                latest_run = await self._sync_run_repo.get_latest_for_data_source(
                    ds.id.value
                )
                result.append(
                    DataSourceWithLatestRun(
                        data_source=ds,
                        latest_sync_run=latest_run,
                    )
                )

        return result

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
        await self._session.commit()

        if name is not None:
            self._probe.data_source_updated(ds_id=ds_id, name=name)
        else:
            self._probe.data_source_updated(ds_id=ds_id, name=ds.name)

        return ds

    async def update_ontology(
        self,
        user_id: str,
        ds_id: str,
        ontology: Ontology,
    ) -> DataSource:
        """Update the approved ontology for a data source.

        Requires EDIT permission on the data source. Replaces the stored
        ontology with the provided one and persists the change.

        Args:
            user_id: The user performing the update
            ds_id: The data source ID
            ontology: The new approved ontology (may be empty)

        Returns:
            The updated DataSource aggregate

        Raises:
            UnauthorizedError: If user lacks EDIT permission on the DS
            ValueError: If DS not found or belongs to a different tenant
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

        ds.update_ontology(ontology=ontology, updated_by=user_id)
        await self._ds_repo.save(ds)
        await self._session.commit()

        self._probe.data_source_updated(ds_id=ds_id, name=ds.name)

        return ds

    async def refresh_commit_references(
        self,
        user_id: str,
        ds_id: str,
        tracked_branch_head_commit: str,
        clone_head_commit: str | None = None,
    ) -> DataSource:
        """Persist refreshed source commit references for a data source.

        Requires MANAGE permission on the data source. This action updates
        tracked and clone commit references and initializes extraction baseline
        on first refresh so per-source diff counts can be computed immediately.
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
        if ds is None or ds.tenant_id != self._scope_to_tenant:
            raise ValueError(f"Data source {ds_id} not found")

        resolved_clone_head = clone_head_commit or tracked_branch_head_commit
        ds.tracked_branch_head_commit = tracked_branch_head_commit
        ds.clone_head_commit = resolved_clone_head
        if ds.last_extraction_baseline_commit is None:
            ds.last_extraction_baseline_commit = tracked_branch_head_commit

        await self._ds_repo.save(ds)
        await self._session.commit()
        self._probe.data_source_updated(ds_id=ds_id, name=ds.name)
        return ds

    async def adopt_tracked_head_as_baseline(
        self,
        user_id: str,
        ds_id: str,
    ) -> DataSource:
        """Move extraction baseline to the currently tracked branch head."""
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
        if ds is None or ds.tenant_id != self._scope_to_tenant:
            raise ValueError(f"Data source {ds_id} not found")
        if not ds.tracked_branch_head_commit:
            raise ValueError(
                "Cannot adopt tracked branch head as baseline before refs are refreshed"
            )

        ds.last_extraction_baseline_commit = ds.tracked_branch_head_commit
        await self._ds_repo.save(ds)
        await self._session.commit()
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

        if ds.credentials_path:
            await self._secret_store.delete(
                path=ds.credentials_path,
                tenant_id=self._scope_to_tenant,
            )

        ds.mark_for_deletion(deleted_by=user_id)
        await self._ds_repo.delete(ds)
        await self._session.commit()

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

        # Record SyncStarted event on the data source aggregate.
        # This event carries the sync_run_id so lifecycle handlers
        # can update the correct sync run record.
        ds.request_sync(sync_run_id=sync_run.id, requested_by=user_id)
        await self._ds_repo.save(ds)
        await self._session.commit()

        self._probe.sync_requested(ds_id=ds_id)

        return sync_run

    async def apply_run_control(
        self,
        user_id: str,
        ds_id: str,
        action: str,
    ) -> RunControlResult:
        """Apply run-control action to sync runs for a data source."""
        if action == "start":
            started = await self.trigger_sync(user_id=user_id, ds_id=ds_id)
            return RunControlResult(
                action=action,
                affected_count=1,
                updated_runs=[],
                started_run=started,
            )

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
        if ds is None or ds.tenant_id != self._scope_to_tenant:
            raise ValueError(f"Data source {ds_id} not found")

        runs = await self._sync_run_repo.find_by_data_source(ds_id)
        active_statuses = {"pending", "ingesting", "ai_extracting", "applying"}
        targets: list[DataSourceSyncRun] = []
        now = datetime.now(UTC)

        if action == "pause":
            targets = [run for run in runs if run.status in active_statuses]
            for run in targets:
                run.status = "pending"
                run.logs.append("Run paused by control plane")
        elif action == "halt":
            targets = [run for run in runs if run.status in active_statuses]
            for run in targets:
                run.status = "failed"
                run.completed_at = now
                run.error = "Run halted by control plane"
                run.logs.append("Run halted by control plane")
        elif action == "reset_running":
            targets = [run for run in runs if run.status in active_statuses]
            for run in targets:
                run.status = "pending"
                run.completed_at = None
                run.error = None
        elif action == "reset_failed":
            targets = [run for run in runs if run.status == "failed"]
            for run in targets:
                run.status = "pending"
                run.completed_at = None
                run.error = None
        elif action == "reset_completed":
            targets = [run for run in runs if run.status == "completed"]
            for run in targets:
                run.status = "pending"
                run.completed_at = None
                run.error = None
        elif action == "reset_all":
            targets = list(runs)
            for run in targets:
                run.status = "pending"
                run.completed_at = None
                run.error = None
        else:
            raise ValueError(f"Unsupported run control action: {action}")

        for run in targets:
            await self._sync_run_repo.save(run)
        await self._session.commit()

        return RunControlResult(
            action=action,
            affected_count=len(targets),
            updated_runs=targets,
        )
