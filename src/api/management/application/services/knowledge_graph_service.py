"""KnowledgeGraph application service for Management bounded context.

Orchestrates knowledge graph operations with proper authorization,
transaction management, and observability.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from management.application.observability import (
    DefaultKnowledgeGraphServiceProbe,
    KnowledgeGraphServiceProbe,
)
from management.domain.aggregates import KnowledgeGraph
from management.domain.value_objects import KnowledgeGraphId
from management.ports.exceptions import (
    DuplicateKnowledgeGraphNameError,
    UnauthorizedError,
)
from management.ports.repositories import (
    IDataSourceRepository,
    IKnowledgeGraphRepository,
)
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
    ) -> None:
        """Initialize KnowledgeGraphService with dependencies.

        Args:
            session: Database session for transaction management
            knowledge_graph_repository: Repository for KG persistence
            authz: Authorization provider for permission checks
            scope_to_tenant: Tenant ID string to scope this service to
            probe: Optional domain probe for observability
            data_source_repository: Optional DS repository for cascade delete
        """
        self._session = session
        self._kg_repo = knowledge_graph_repository
        self._authz = authz
        self._scope_to_tenant = scope_to_tenant
        self._probe = probe or DefaultKnowledgeGraphServiceProbe()
        self._ds_repo = data_source_repository

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
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[KnowledgeGraph], int]:
        """List knowledge graphs in a workspace with pagination.

        Uses read_relationships to discover KG IDs linked to the workspace,
        then fetches each from the repository and filters by tenant.
        Pagination is applied after filtering.

        Args:
            user_id: The user requesting the list
            workspace_id: The workspace to list KGs for
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (paginated KnowledgeGraph aggregates, total count)

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
        # (N+1 problem - acceptable for walking skeleton)
        kgs: list[KnowledgeGraph] = []
        for kg_id in kg_ids:
            kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
            if kg is not None and kg.tenant_id == self._scope_to_tenant:
                kgs.append(kg)

        total = len(kgs)
        paginated = kgs[offset : offset + limit]

        self._probe.knowledge_graphs_listed(
            workspace_id=workspace_id,
            count=len(paginated),
        )

        return paginated, total

    async def update(
        self,
        user_id: str,
        kg_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> KnowledgeGraph:
        """Update a knowledge graph's metadata.

        Args:
            user_id: The user performing the update
            kg_id: The knowledge graph ID
            name: Optional new name (uses existing if None)
            description: Optional new description (uses existing if None)

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
            raise ValueError(f"Knowledge graph {kg_id} not found")

        if kg.tenant_id != self._scope_to_tenant:
            raise ValueError(f"Knowledge graph {kg_id} not found")

        resolved_name = name if name is not None else kg.name
        resolved_description = (
            description if description is not None else kg.description
        )

        kg.update(
            name=resolved_name,
            description=resolved_description,
            updated_by=user_id,
        )

        try:
            async with self._session.begin():
                await self._kg_repo.save(kg)
        except IntegrityError as e:
            raise DuplicateKnowledgeGraphNameError(
                f"Knowledge graph '{resolved_name}' already exists in tenant"
            ) from e

        self._probe.knowledge_graph_updated(kg_id=kg_id, name=resolved_name)

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

        async with self._session.begin():
            # Cascade delete all data sources before deleting KG
            if self._ds_repo is not None:
                while True:
                    batch, _ = await self._ds_repo.find_by_knowledge_graph(
                        kg_id, offset=0, limit=100
                    )
                    if not batch:
                        break
                    for ds in batch:
                        ds.mark_for_deletion(deleted_by=user_id)
                        await self._ds_repo.delete(ds)

            kg.mark_for_deletion(deleted_by=user_id)
            await self._kg_repo.delete(kg)

        self._probe.knowledge_graph_deleted(kg_id=kg_id)

        return True
