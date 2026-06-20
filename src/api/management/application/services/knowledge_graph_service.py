"""KnowledgeGraph application service for Management bounded context.

Orchestrates knowledge graph operations with proper authorization,
transaction management, and observability.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import CroniterBadCronError, croniter
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from management.application.observability import (
    DefaultKnowledgeGraphServiceProbe,
    KnowledgeGraphServiceProbe,
)
from management.domain.aggregates import KnowledgeGraph
from management.domain.entities.data_source_sync_run import DataSourceSyncRun
from management.domain.value_objects import (
    KnowledgeGraphMaintenanceRunOutcome,
    KnowledgeGraphMaintenanceRunRecord,
    KnowledgeGraphMaintenanceSchedule,
    KnowledgeGraphId,
    KnowledgeGraphWorkspaceStatus,
    OntologyConfig,
    WorkspaceMode,
    WorkspaceReadinessStatus,
    WorkspaceSessionPointers,
)
from management.ports.exceptions import (
    DuplicateKnowledgeGraphNameError,
    KnowledgeGraphNotFoundError,
    UnauthorizedError,
)
from management.ports.repositories import (
    IDataSourceRepository,
    IDataSourceSyncRunRepository,
    IKnowledgeGraphRepository,
)
from management.ports.canonical_schema import ICanonicalSchemaRepository
from management.ports.maintenance_pipeline import MaintenancePipelinePort
from management.ports.secret_store import ISecretStoreRepository
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    RelationType,
    ResourceType,
    format_resource,
    format_subject,
)


class KnowledgeGraphService:
    """Application service for knowledge graph management.

    Orchestrates knowledge graph operations with proper tenant scoping,
    authorization checks, and business rule enforcement.
    """

    def __init__(
        self,
        session: AsyncSession,
        knowledge_graph_repository: IKnowledgeGraphRepository,
        authz: AuthorizationProvider,
        scope_to_tenant: str,
        probe: KnowledgeGraphServiceProbe | None = None,
        data_source_repository: IDataSourceRepository | None = None,
        sync_run_repository: IDataSourceSyncRunRepository | None = None,
        secret_store: ISecretStoreRepository | None = None,
        canonical_schema_repository: ICanonicalSchemaRepository | None = None,
        maintenance_pipeline: MaintenancePipelinePort | None = None,
    ) -> None:
        """Initialize KnowledgeGraphService with dependencies.

        Args:
            session: Database session for transaction management
            knowledge_graph_repository: Repository for KG persistence
            authz: Authorization provider for permission checks
            scope_to_tenant: Tenant ID string to scope this service to
            probe: Optional domain probe for observability
            data_source_repository: Optional DS repository for cascade delete
            secret_store: Optional secret store for credential cleanup on cascade delete
            canonical_schema_repository: Optional graph-native canonical schema store
        """
        self._session = session
        self._kg_repo = knowledge_graph_repository
        self._authz = authz
        self._scope_to_tenant = scope_to_tenant
        self._probe = probe or DefaultKnowledgeGraphServiceProbe()
        self._ds_repo = data_source_repository
        self._sync_run_repo = sync_run_repository
        self._secret_store = secret_store
        self._canonical_schema_repo = canonical_schema_repository
        self._maintenance_pipeline = maintenance_pipeline

    def _compute_next_run_at_utc(
        self,
        *,
        cron_expression: str,
        timezone_name: str,
        now_utc: datetime | None = None,
    ) -> datetime:
        """Compute next scheduled runtime in UTC from cron + timezone."""
        if not croniter.is_valid(cron_expression):
            raise ValueError(f"Invalid cron expression: {cron_expression!r}")
        try:
            tz = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {timezone_name!r}") from exc

        now_utc = now_utc or datetime.now(UTC)
        local_now = now_utc.astimezone(tz)
        try:
            itr = croniter(cron_expression, local_now)
            next_local = itr.get_next(datetime)
        except (CroniterBadCronError, ValueError) as exc:
            raise ValueError(f"Invalid cron expression: {cron_expression!r}") from exc

        if next_local.tzinfo is None:
            next_local = next_local.replace(tzinfo=tz)
        return next_local.astimezone(UTC)

    async def _get_tenant_scoped_kg(
        self, *, kg_id: str, user_id: str, permission: Permission
    ) -> KnowledgeGraph:
        """Resolve KG with tenant and authz checks."""
        has_permission = await self._check_permission(
            user_id=user_id,
            resource_type=ResourceType.KNOWLEDGE_GRAPH,
            resource_id=kg_id,
            permission=permission,
        )
        if not has_permission:
            self._probe.permission_denied(
                user_id=user_id,
                resource_id=kg_id,
                permission=permission,
            )
            raise UnauthorizedError(
                f"User {user_id} lacks {permission.value} permission on knowledge graph {kg_id}"
            )

        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None or kg.tenant_id != self._scope_to_tenant:
            raise KnowledgeGraphNotFoundError(f"Knowledge graph {kg_id} not found")
        return kg

    async def get_maintenance_schedule(
        self, *, user_id: str, kg_id: str
    ) -> KnowledgeGraphMaintenanceSchedule:
        """Return KG-level maintenance schedule config."""
        kg = await self._get_tenant_scoped_kg(
            kg_id=kg_id,
            user_id=user_id,
            permission=Permission.VIEW,
        )
        return kg.maintenance_schedule or KnowledgeGraphMaintenanceSchedule(
            enabled=False,
            cron_expression="0 2 * * *",
            timezone_name="UTC",
            next_run_at=None,
        )

    async def upsert_maintenance_schedule(
        self,
        *,
        user_id: str,
        kg_id: str,
        cron_expression: str,
        timezone_name: str,
        enabled: bool,
        files_per_job: int = 2,
        worker_count: int = 8,
    ) -> KnowledgeGraphMaintenanceSchedule:
        """Create or update KG-level maintenance schedule configuration."""
        kg = await self._get_tenant_scoped_kg(
            kg_id=kg_id,
            user_id=user_id,
            permission=Permission.MANAGE,
        )
        existing = kg.maintenance_schedule
        normalized_files_per_job = max(1, int(files_per_job))
        normalized_workers = max(1, int(worker_count))
        next_run_at = (
            self._compute_next_run_at_utc(
                cron_expression=cron_expression,
                timezone_name=timezone_name,
            )
            if enabled
            else None
        )
        schedule = KnowledgeGraphMaintenanceSchedule(
            enabled=enabled,
            cron_expression=cron_expression,
            timezone_name=timezone_name,
            next_run_at=next_run_at,
            files_per_job=normalized_files_per_job,
            worker_count=normalized_workers,
        )
        kg.set_maintenance_schedule(schedule)
        await self._kg_repo.save(kg)
        await self._session.commit()
        return schedule

    async def list_maintenance_runs(
        self, *, user_id: str, kg_id: str, limit: int = 20
    ) -> list[KnowledgeGraphMaintenanceRunRecord]:
        """List persisted maintenance run outcomes for a KG."""
        kg = await self._get_tenant_scoped_kg(
            kg_id=kg_id,
            user_id=user_id,
            permission=Permission.VIEW,
        )
        capped_limit = max(1, min(limit, 100))
        return list(kg.maintenance_run_history[-capped_limit:])[::-1]

    async def trigger_maintenance_run(
        self,
        *,
        user_id: str,
        kg_id: str,
        files_per_job: int = 2,
        worker_count: int = 8,
        start_extraction: bool = True,
    ) -> KnowledgeGraphMaintenanceRunRecord:
        """Trigger maintenance ingest and extraction jobs for a knowledge graph."""
        if self._maintenance_pipeline is None:
            raise ValueError("Maintenance pipeline is not configured")
        return await self._maintenance_pipeline.trigger(
            user_id=user_id,
            kg_id=kg_id,
            files_per_job=files_per_job,
            worker_count=worker_count,
            start_extraction=start_extraction,
        )

    async def start_ready_maintenance_jobs(
        self,
        *,
        user_id: str,
        kg_id: str,
        worker_count: int = 8,
    ) -> dict[str, int | str | bool]:
        """Start workers for pending maintenance jobs without re-queueing work."""
        if self._maintenance_pipeline is None:
            raise ValueError("Maintenance pipeline is not configured")
        return await self._maintenance_pipeline.start_ready_maintenance_jobs(
            user_id=user_id,
            kg_id=kg_id,
            worker_count=worker_count,
        )

    async def regenerate_maintenance_jobs(
        self,
        *,
        user_id: str,
        kg_id: str,
        files_per_job: int = 2,
    ) -> dict[str, int | str | bool]:
        """Replace pending maintenance jobs from the current changed-file diff."""
        if self._maintenance_pipeline is None:
            raise ValueError("Maintenance pipeline is not configured")
        return await self._maintenance_pipeline.regenerate_maintenance_jobs(
            user_id=user_id,
            kg_id=kg_id,
            files_per_job=files_per_job,
        )

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
        workspace_id: str,
        name: str,
        description: str,
    ) -> KnowledgeGraph:
        """Create a new knowledge graph in a workspace.

        Args:
            user_id: The user creating the KG
            workspace_id: The workspace to create the KG in
            name: Name of the knowledge graph
            description: Description of the knowledge graph

        Returns:
            The created KnowledgeGraph aggregate

        Raises:
            UnauthorizedError: If user lacks EDIT permission on workspace
            DuplicateKnowledgeGraphNameError: If name already exists in tenant
        """
        has_edit = await self._check_permission(
            user_id=user_id,
            resource_type=ResourceType.WORKSPACE,
            resource_id=workspace_id,
            permission=Permission.EDIT,
        )

        if not has_edit:
            self._probe.permission_denied(
                user_id=user_id,
                resource_id=workspace_id,
                permission=Permission.EDIT,
            )
            raise UnauthorizedError(
                f"User {user_id} lacks edit permission on workspace {workspace_id}"
            )

        try:
            async with self._session.begin():
                kg = KnowledgeGraph.create(
                    tenant_id=self._scope_to_tenant,
                    workspace_id=workspace_id,
                    name=name,
                    description=description,
                    created_by=user_id,
                )
                await self._kg_repo.save(kg)

            self._probe.knowledge_graph_created(
                kg_id=kg.id.value,
                tenant_id=self._scope_to_tenant,
                workspace_id=workspace_id,
                name=name,
            )

            return kg

        except IntegrityError as e:
            self._probe.knowledge_graph_creation_failed(
                tenant_id=self._scope_to_tenant,
                name=name,
                error=str(e),
            )
            raise DuplicateKnowledgeGraphNameError(
                f"Knowledge graph '{name}' already exists in tenant"
            ) from e

    async def get(
        self,
        user_id: str,
        kg_id: str,
    ) -> KnowledgeGraph | None:
        """Get a knowledge graph by ID with authorization check.

        Args:
            user_id: The user requesting access
            kg_id: The knowledge graph ID

        Returns:
            The KnowledgeGraph aggregate, or None if not found or if
            the caller lacks VIEW permission (to avoid existence leakage)
        """
        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None:
            return None

        if kg.tenant_id != self._scope_to_tenant:
            return None

        has_view = await self._check_permission(
            user_id=user_id,
            resource_type=ResourceType.KNOWLEDGE_GRAPH,
            resource_id=kg_id,
            permission=Permission.VIEW,
        )

        if not has_view:
            return None

        self._probe.knowledge_graph_retrieved(kg_id=kg_id)
        return kg

    async def list_for_workspace(
        self,
        user_id: str,
        workspace_id: str,
    ) -> list[KnowledgeGraph]:
        """List knowledge graphs in a workspace.

        Uses read_relationships to discover KG IDs linked to the workspace,
        then fetches each from the repository and filters by tenant.

        Args:
            user_id: The user requesting the list
            workspace_id: The workspace to list KGs for

        Returns:
            List of KnowledgeGraph aggregates

        Raises:
            UnauthorizedError: If user lacks VIEW permission on workspace
        """
        has_view = await self._check_permission(
            user_id=user_id,
            resource_type=ResourceType.WORKSPACE,
            resource_id=workspace_id,
            permission=Permission.VIEW,
        )

        if not has_view:
            self._probe.permission_denied(
                user_id=user_id,
                resource_id=workspace_id,
                permission=Permission.VIEW,
            )
            raise UnauthorizedError(
                f"User {user_id} lacks view permission on workspace {workspace_id}"
            )

        # Read explicit tuples to discover KG IDs linked to this workspace
        tuples = await self._authz.read_relationships(
            resource_type=ResourceType.KNOWLEDGE_GRAPH,
            relation=RelationType.WORKSPACE,
            subject_type=ResourceType.WORKSPACE,
            subject_id=workspace_id,
        )

        # Extract KG IDs from relationship tuples
        # Format is "knowledge_graph:ID"
        kg_ids: list[str] = []
        for rel_tuple in tuples:
            parts = rel_tuple.resource.split(":")
            if len(parts) == 2:
                kg_ids.append(parts[1])

        # Fetch each KG from repo and filter by tenant
        kgs: list[KnowledgeGraph] = []
        for kg_id in kg_ids:
            kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
            if kg is not None and kg.tenant_id == self._scope_to_tenant:
                kgs.append(kg)

        self._probe.knowledge_graphs_listed(
            workspace_id=workspace_id,
            count=len(kgs),
        )

        return kgs

    async def list_for_workspace_with_permission(
        self,
        user_id: str,
        workspace_id: str,
        permission: Permission = Permission.VIEW,
    ) -> list[KnowledgeGraph]:
        """List knowledge graphs in a workspace filtered by per-KG permission.

        Discovers KGs linked to the workspace via SpiceDB relationships, then
        filters to those the user has the requested permission on.

        Unlike list_for_workspace(), this method does NOT require workspace-level
        VIEW permission — per-KG permission checks are sufficient. This supports
        the Mutations Console KG selector which must show KGs the user can EDIT
        within the selected workspace, regardless of their workspace role.

        Args:
            user_id: The user requesting the list
            workspace_id: The workspace to filter by
            permission: Minimum permission to check on each KG (VIEW or EDIT)

        Returns:
            KGs in the workspace that the user has the requested permission on.
            Returns an empty list when the workspace has no KGs or when the user
            lacks the requested permission on all workspace KGs.
        """
        # Discover KG IDs linked to the workspace via SpiceDB relationships
        tuples = await self._authz.read_relationships(
            resource_type=ResourceType.KNOWLEDGE_GRAPH,
            relation=RelationType.WORKSPACE,
            subject_type=ResourceType.WORKSPACE,
            subject_id=workspace_id,
        )

        # Extract KG IDs from relationship tuples (format: "knowledge_graph:<id>")
        kg_ids: list[str] = []
        for rel_tuple in tuples:
            parts = rel_tuple.resource.split(":")
            if len(parts) == 2:
                kg_ids.append(parts[1])

        # Filter by per-KG permission (no workspace-level check required)
        kgs: list[KnowledgeGraph] = []
        for kg_id in kg_ids:
            has_perm = await self._check_permission(
                user_id=user_id,
                resource_type=ResourceType.KNOWLEDGE_GRAPH,
                resource_id=kg_id,
                permission=permission,
            )
            if has_perm:
                kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
                if kg is not None and kg.tenant_id == self._scope_to_tenant:
                    kgs.append(kg)

        self._probe.knowledge_graphs_listed(
            workspace_id=workspace_id,
            count=len(kgs),
        )
        return kgs

    async def list_all(
        self,
        user_id: str,
        permission: Permission = Permission.VIEW,
    ) -> list[KnowledgeGraph]:
        """List all knowledge graphs in the current tenant accessible to the user.

        Fetches all KGs in the tenant then filters to those the user has the
        requested permission on via SpiceDB.

        Args:
            user_id: The user requesting the list
            permission: The permission to check (VIEW by default; pass EDIT to
                return only KGs the user can edit — e.g. for the Mutations
                Console KG selector which must show only submission targets).

        Returns:
            List of KnowledgeGraph aggregates the user has the requested
            permission on.
        """
        all_kgs = await self._kg_repo.find_by_tenant(self._scope_to_tenant)

        accessible_kgs: list[KnowledgeGraph] = []
        for kg in all_kgs:
            has_permission = await self._check_permission(
                user_id=user_id,
                resource_type=ResourceType.KNOWLEDGE_GRAPH,
                resource_id=kg.id.value,
                permission=permission,
            )
            if has_permission:
                accessible_kgs.append(kg)

        self._probe.knowledge_graphs_listed(
            workspace_id=self._scope_to_tenant,
            count=len(accessible_kgs),
        )
        return accessible_kgs

    async def update(
        self,
        user_id: str,
        kg_id: str,
        name: str,
        description: str,
    ) -> KnowledgeGraph:
        """Update a knowledge graph's metadata.

        Args:
            user_id: The user performing the update
            kg_id: The knowledge graph ID
            name: New name
            description: New description

        Returns:
            The updated KnowledgeGraph aggregate

        Raises:
            UnauthorizedError: If user lacks EDIT permission
            ValueError: If KG not found
            DuplicateKnowledgeGraphNameError: If name already exists
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

        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None:
            raise KnowledgeGraphNotFoundError(f"Knowledge graph {kg_id} not found")

        if kg.tenant_id != self._scope_to_tenant:
            raise KnowledgeGraphNotFoundError(f"Knowledge graph {kg_id} not found")

        kg.update(name=name, description=description, updated_by=user_id)

        try:
            await self._kg_repo.save(kg)
            await self._session.commit()
        except IntegrityError as e:
            # SQLAlchemy rolls back the internal transaction automatically on
            # IntegrityError, but the AsyncSession is left in a failed state
            # until rollback() is called.  Without this, any subsequent use of
            # the injected session raises PendingRollbackError.
            await self._session.rollback()
            raise DuplicateKnowledgeGraphNameError(
                f"Knowledge graph '{name}' already exists in tenant"
            ) from e

        self._probe.knowledge_graph_updated(kg_id=kg_id, name=name)

        return kg

    async def delete(
        self,
        user_id: str,
        kg_id: str,
    ) -> bool:
        """Delete a knowledge graph and cascade delete its data sources.

        Args:
            user_id: The user performing the deletion
            kg_id: The knowledge graph ID

        Returns:
            True if deleted, False if not found

        Raises:
            UnauthorizedError: If user lacks MANAGE permission
        """
        has_manage = await self._check_permission(
            user_id=user_id,
            resource_type=ResourceType.KNOWLEDGE_GRAPH,
            resource_id=kg_id,
            permission=Permission.MANAGE,
        )

        if not has_manage:
            self._probe.permission_denied(
                user_id=user_id,
                resource_id=kg_id,
                permission=Permission.MANAGE,
            )
            raise UnauthorizedError(
                f"User {user_id} lacks manage permission on knowledge graph {kg_id}"
            )

        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None:
            return False

        if kg.tenant_id != self._scope_to_tenant:
            return False

        # Use a savepoint so the entire cascade is atomic even though autobegin
        # has already started a transaction via the get_by_id reads above.
        async with self._session.begin_nested():
            if self._ds_repo is not None:
                data_sources = await self._ds_repo.find_by_knowledge_graph(kg_id)
                for ds in data_sources:
                    # Clean up encrypted credentials before removing the row to
                    # prevent orphaned credential blobs in the secret store.
                    if self._secret_store is not None and ds.credentials_path:
                        await self._secret_store.delete(
                            path=ds.credentials_path,
                            tenant_id=self._scope_to_tenant,
                        )
                    ds.mark_for_deletion(deleted_by=user_id)
                    await self._ds_repo.delete(ds)

            kg.mark_for_deletion(deleted_by=user_id)
            await self._kg_repo.delete(kg)

        await self._session.commit()

        self._probe.knowledge_graph_deleted(kg_id=kg_id)

        return True

    async def get_ontology(
        self,
        user_id: str,
        kg_id: str,
    ) -> OntologyConfig | None:
        """Retrieve the ontology for a knowledge graph.

        Returns None when no ontology has been saved yet (caller should
        convert to 404). Returns None also when the KG does not exist or
        the caller lacks VIEW permission (existence leakage prevention).

        Args:
            user_id: The user requesting access
            kg_id: The knowledge graph ID

        Returns:
            The OntologyConfig if one has been saved, otherwise None
        """
        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None or kg.tenant_id != self._scope_to_tenant:
            return None

        has_view = await self._check_permission(
            user_id=user_id,
            resource_type=ResourceType.KNOWLEDGE_GRAPH,
            resource_id=kg_id,
            permission=Permission.VIEW,
        )
        if not has_view:
            return None

        return await self._resolve_canonical_ontology(kg_id)

    async def save_ontology(
        self,
        user_id: str,
        kg_id: str,
        config: OntologyConfig,
    ) -> OntologyConfig:
        """Persist an ontology configuration for a knowledge graph.

        Requires EDIT permission on the knowledge graph. Performs a full
        replace (not a merge) of the stored ontology.

        Args:
            user_id: The user performing the operation
            kg_id: The knowledge graph ID
            config: The OntologyConfig to persist

        Returns:
            The stored OntologyConfig (same as input)

        Raises:
            UnauthorizedError: If user lacks EDIT permission
            KnowledgeGraphNotFoundError: If KG does not exist in this tenant
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

        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None or kg.tenant_id != self._scope_to_tenant:
            raise KnowledgeGraphNotFoundError(f"Knowledge graph {kg_id} not found")

        if self._canonical_schema_repo is None:
            raise ValueError("Canonical schema repository is not configured")
        await self._canonical_schema_repo.replace_ontology(kg_id, config)
        await self._session.commit()

        return config

    async def _resolve_canonical_ontology(self, kg_id: str) -> OntologyConfig | None:
        """Load canonical schema from graph-native storage only."""
        if self._canonical_schema_repo is None:
            return None
        return await self._canonical_schema_repo.get_ontology(kg_id)

    def _evaluate_workspace_readiness(
        self, ontology: OntologyConfig | None
    ) -> WorkspaceReadinessStatus:
        """Evaluate transition readiness flags from canonical schema state."""
        from management.application.workspace_readiness import evaluate_workspace_readiness

        return evaluate_workspace_readiness(ontology)

    async def get_workspace_status(
        self,
        user_id: str,
        kg_id: str,
    ) -> KnowledgeGraphWorkspaceStatus | None:
        """Get mode/readiness/session projection for a knowledge graph workspace."""
        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None or kg.tenant_id != self._scope_to_tenant:
            return None

        has_view = await self._check_permission(
            user_id=user_id,
            resource_type=ResourceType.KNOWLEDGE_GRAPH,
            resource_id=kg_id,
            permission=Permission.VIEW,
        )
        if not has_view:
            return None

        ontology = await self._resolve_canonical_ontology(kg_id)
        readiness = self._evaluate_workspace_readiness(ontology)
        transition_eligible = (
            kg.workspace_mode == WorkspaceMode.SCHEMA_BOOTSTRAP and readiness.is_ready
        )

        return KnowledgeGraphWorkspaceStatus(
            knowledge_graph_id=kg.id.value,
            workspace_mode=kg.workspace_mode,
            readiness=readiness,
            transition_eligible=transition_eligible,
            session_pointers=WorkspaceSessionPointers(
                active_schema_bootstrap_session_id=kg.active_schema_bootstrap_session_id,
                active_extraction_operations_session_id=(
                    kg.active_extraction_operations_session_id
                ),
                most_recent_completed_session_id=kg.most_recent_completed_session_id,
            ),
        )

    async def validate_workspace(
        self,
        user_id: str,
        kg_id: str,
    ) -> KnowledgeGraphWorkspaceStatus:
        """Validate bootstrap readiness with KG edit authorization."""
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

        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None or kg.tenant_id != self._scope_to_tenant:
            raise KnowledgeGraphNotFoundError(f"Knowledge graph {kg_id} not found")

        ontology = await self._resolve_canonical_ontology(kg_id)
        readiness = self._evaluate_workspace_readiness(ontology)
        transition_eligible = (
            kg.workspace_mode == WorkspaceMode.SCHEMA_BOOTSTRAP and readiness.is_ready
        )
        return KnowledgeGraphWorkspaceStatus(
            knowledge_graph_id=kg.id.value,
            workspace_mode=kg.workspace_mode,
            readiness=readiness,
            transition_eligible=transition_eligible,
            session_pointers=WorkspaceSessionPointers(
                active_schema_bootstrap_session_id=kg.active_schema_bootstrap_session_id,
                active_extraction_operations_session_id=(
                    kg.active_extraction_operations_session_id
                ),
                most_recent_completed_session_id=kg.most_recent_completed_session_id,
            ),
        )

    async def transition_workspace_to_extraction(
        self,
        user_id: str,
        kg_id: str,
    ) -> KnowledgeGraphWorkspaceStatus:
        """Transition a knowledge graph workspace to extraction_operations mode."""
        _ = await self.validate_workspace(user_id=user_id, kg_id=kg_id)

        kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None or kg.tenant_id != self._scope_to_tenant:
            raise KnowledgeGraphNotFoundError(f"Knowledge graph {kg_id} not found")

        ontology = await self._resolve_canonical_ontology(kg_id)
        readiness = self._evaluate_workspace_readiness(ontology)
        if not readiness.is_ready:
            joined_reasons = "; ".join(readiness.blocking_reasons)
            raise ValueError(
                f"Knowledge graph {kg_id} is not ready for transition: {joined_reasons}"
            )

        kg.transition_to_extraction_operations()
        await self._kg_repo.save(kg)
        await self._session.commit()

        return KnowledgeGraphWorkspaceStatus(
            knowledge_graph_id=kg.id.value,
            workspace_mode=kg.workspace_mode,
            readiness=readiness,
            transition_eligible=False,
            session_pointers=WorkspaceSessionPointers(
                active_schema_bootstrap_session_id=kg.active_schema_bootstrap_session_id,
                active_extraction_operations_session_id=(
                    kg.active_extraction_operations_session_id
                ),
                most_recent_completed_session_id=kg.most_recent_completed_session_id,
            ),
        )
