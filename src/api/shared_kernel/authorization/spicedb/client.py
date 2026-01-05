"""SpiceDB client implementation for authorization.

Provides async SpiceDB client wrapping the authzed library with proper
error handling and type safety.
"""

from __future__ import annotations

import asyncio
from enum import IntEnum

from authzed.api.v1 import (
    CheckPermissionRequest,
    Consistency,
    LookupResourcesRequest,
    LookupSubjectsRequest,
    ObjectReference,
    Relationship,
    RelationshipUpdate,
    SubjectReference,
    WriteRelationshipsRequest,
)
from authzed.api.v1.permission_service_pb2 import CheckPermissionResponse
from grpcutil import insecure_bearer_token_credentials

from shared_kernel.authorization.observability import (
    AuthorizationProbe,
    DefaultAuthorizationProbe,
)
from shared_kernel.authorization.protocols import AuthorizationProvider, CheckRequest
from shared_kernel.authorization.spicedb.exceptions import (
    SpiceDBConnectionError,
    SpiceDBPermissionError,
)
from shared_kernel.authorization.types import RelationshipSpec, SubjectRelation


class RelationshipOperation(IntEnum):
    """Enum for relationship operation types."""

    WRITE = RelationshipUpdate.OPERATION_TOUCH
    DELETE = RelationshipUpdate.OPERATION_DELETE


def _parse_reference(ref: str, ref_type: str) -> tuple[str, str]:
    """Parse a resource or subject reference string.

    Args:
        ref: Reference string in format "type:id"
        ref_type: Description for error messages (e.g., "resource", "subject")

    Returns:
        Tuple of (type, id)

    Raises:
        ValueError: If reference format is invalid
    """
    if ":" not in ref:
        raise ValueError(
            f"Invalid {ref_type} format: '{ref}'. Expected 'type:id' format."
        )
    parts = ref.split(":", 1)
    return (parts[0], parts[1])


def _build_relationship_update(
    resource: str, relation: str, subject: str, operation: RelationshipOperation
) -> RelationshipUpdate:
    """Build a RelationshipUpdate for write or delete operations.

    Args:
        resource: Resource identifier (e.g., "group:abc123")
        relation: Relation name (e.g., "member")
        subject: Subject identifier (e.g., "user:alice")
        operation: RelationshipOperation.WRITE or DELETE

    Returns:
        RelationshipUpdate object ready for WriteRelationshipsRequest
    """
    resource_type, resource_id = _parse_reference(resource, "resource")
    subject_type, subject_id = _parse_reference(subject, "subject")

    relationship = Relationship(
        resource=ObjectReference(
            object_type=resource_type,
            object_id=resource_id,
        ),
        relation=relation,
        subject=SubjectReference(
            object=ObjectReference(
                object_type=subject_type,
                object_id=subject_id,
            ),
        ),
    )

    return RelationshipUpdate(
        operation=int(operation),  # Convert enum to int for protobuf
        relationship=relationship,
    )


class SpiceDBClient(AuthorizationProvider):
    """SpiceDB client implementation of AuthorizationProvider protocol.

    This client provides async methods for writing relationships, checking
    permissions, and bulk permission checks against a SpiceDB instance.
    """

    def __init__(
        self,
        endpoint: str,
        preshared_key: str,
        probe: AuthorizationProbe | None = None,
    ):
        """Initialize SpiceDB client.

        Args:
            endpoint: SpiceDB gRPC endpoint (e.g., "localhost:50051")
            preshared_key: Pre-shared key for authentication
            probe: Optional domain probe for observability
        """
        self._endpoint = endpoint
        self._preshared_key = preshared_key
        self._client = None
        self._probe = probe or DefaultAuthorizationProbe()
        self._init_lock = asyncio.Lock()

    async def _ensure_client(self):
        """Lazily initialize the gRPC client with thread-safe double-check locking."""
        if self._client is None:
            async with self._init_lock:
                # Double-check after acquiring lock
                if self._client is None:
                    try:
                        from authzed.api.v1 import AsyncClient

                        # Create credentials with preshared key
                        credentials = insecure_bearer_token_credentials(
                            self._preshared_key
                        )

                        # Initialize client
                        self._client = AsyncClient(
                            self._endpoint,
                            credentials,
                        )
                    except Exception as e:
                        self._probe.connection_failed(
                            endpoint=self._endpoint,
                            error=e,
                        )
                        raise SpiceDBConnectionError(
                            f"Failed to connect to SpiceDB at {self._endpoint}: {e}"
                        ) from e

    async def write_relationship(
        self,
        resource: str,
        relation: str,
        subject: str,
    ) -> None:
        """Write a relationship to SpiceDB.

        Args:
            resource: Resource identifier (e.g., "group:abc123")
            relation: Relation name (e.g., "member", "owner")
            subject: Subject identifier (e.g., "user:alice")

        Raises:
            SpiceDBPermissionError: If the write fails
        """
        await self._ensure_client()
        assert self._client is not None  # For mypy

        # Parse resource and subject
        resource_type, resource_id = _parse_reference(resource, "resource")
        subject_type, subject_id = _parse_reference(subject, "subject")

        try:
            # Create relationship update
            relationship = Relationship(
                resource=ObjectReference(
                    object_type=resource_type,
                    object_id=resource_id,
                ),
                relation=relation,
                subject=SubjectReference(
                    object=ObjectReference(
                        object_type=subject_type,
                        object_id=subject_id,
                    ),
                ),
            )

            update = RelationshipUpdate(
                operation=RelationshipUpdate.OPERATION_TOUCH,
                relationship=relationship,
            )

            request = WriteRelationshipsRequest(updates=[update])

            await self._client.WriteRelationships(request)

            self._probe.relationship_written(
                resource=resource,
                relation=relation,
                subject=subject,
            )

        except Exception as e:
            self._probe.relationship_write_failed(
                resource=resource,
                relation=relation,
                subject=subject,
                error=e,
            )
            raise SpiceDBPermissionError(
                f"Failed to write relationship: {resource} {relation} {subject}"
            ) from e

    async def _execute_relationship_updates(
        self,
        relationships: list[RelationshipSpec],
        operation: RelationshipOperation,
    ) -> None:
        """Execute relationship updates (write or delete) with error handling.

        Args:
            relationships: List of RelationshipSpec objects
            operation: RelationshipOperation.WRITE or DELETE

        Raises:
            SpiceDBPermissionError: If the operation fails
        """
        if not relationships:
            return

        await self._ensure_client()
        assert self._client is not None

        try:
            updates = [
                _build_relationship_update(
                    rel.resource, rel.relation, rel.subject, operation
                )
                for rel in relationships
            ]

            request = WriteRelationshipsRequest(updates=updates)
            await self._client.WriteRelationships(request)

            # Log successful operations
            for rel in relationships:
                if operation == RelationshipOperation.WRITE:
                    self._probe.relationship_written(
                        rel.resource, rel.relation, rel.subject
                    )
                else:
                    self._probe.relationship_deleted(
                        rel.resource, rel.relation, rel.subject
                    )

        except Exception as e:
            if operation == RelationshipOperation.WRITE:
                self._probe.relationship_write_failed(
                    "<bulk>", "<multiple>", "<multiple>", e
                )
            else:
                self._probe.relationship_delete_failed(
                    "<bulk>", "<multiple>", "<multiple>", e
                )
            raise SpiceDBPermissionError(
                f"Failed to {repr(operation)} {len(relationships)} relationships"
            ) from e

    async def write_relationships(
        self,
        relationships: list[RelationshipSpec],
    ) -> None:
        """Write multiple relationships in a single request.

        Args:
            relationships: List of RelationshipSpec objects to write

        Raises:
            SpiceDBPermissionError: If the write fails
        """
        await self._execute_relationship_updates(
            relationships, RelationshipOperation.WRITE
        )

    async def check_permission(
        self,
        resource: str,
        permission: str,
        subject: str,
    ) -> bool:
        """Check if a subject has permission on a resource.

        Args:
            resource: Resource identifier (e.g., "group:abc123")
            permission: Permission to check (e.g., "view", "edit")
            subject: Subject identifier (e.g., "user:alice")

        Returns:
            True if permission is granted, False otherwise

        Raises:
            SpiceDBPermissionError: If the check fails
        """
        await self._ensure_client()
        assert self._client is not None  # For mypy

        # Parse resource and subject
        resource_type, resource_id = _parse_reference(resource, "resource")
        subject_type, subject_id = _parse_reference(subject, "subject")

        try:
            request = CheckPermissionRequest(
                consistency=Consistency(fully_consistent=True),
                resource=ObjectReference(
                    object_type=resource_type,
                    object_id=resource_id,
                ),
                permission=permission,
                subject=SubjectReference(
                    object=ObjectReference(
                        object_type=subject_type,
                        object_id=subject_id,
                    ),
                ),
            )

            response = await self._client.CheckPermission(request)

            has_permission = (
                response.permissionship
                == CheckPermissionResponse.PERMISSIONSHIP_HAS_PERMISSION
            )

            self._probe.permission_checked(
                resource=resource,
                permission=permission,
                subject=subject,
                granted=has_permission,
            )

            return has_permission

        except Exception as e:
            self._probe.permission_check_failed(
                resource=resource,
                permission=permission,
                subject=subject,
                error=e,
            )
            raise SpiceDBPermissionError(
                f"Failed to check permission: {resource} {permission} {subject}"
            ) from e

    async def bulk_check_permission(
        self,
        requests: list[CheckRequest],
    ) -> set[str]:
        """Bulk check permissions for multiple resources.

        For now, this is implemented as sequential checks. Future optimization
        could use SpiceDB's BulkCheckPermission API when available.

        Args:
            requests: List of permission check requests

        Returns:
            Set of resource identifiers that passed permission checks

        Raises:
            SpiceDBPermissionError: If any check fails
        """
        permitted_resources = set()

        for req in requests:
            has_permission = await self.check_permission(
                resource=req.resource,
                permission=req.permission,
                subject=req.subject,
            )

            if has_permission:
                permitted_resources.add(req.resource)

        self._probe.bulk_check_completed(
            total_requests=len(requests),
            permitted_count=len(permitted_resources),
        )

        return permitted_resources

    async def delete_relationship(
        self,
        resource: str,
        relation: str,
        subject: str,
    ) -> None:
        """Delete a relationship from SpiceDB.

        Args:
            resource: Resource identifier (e.g., "group:abc123")
            relation: Relation name (e.g., "member", "owner")
            subject: Subject identifier (e.g., "user:alice")

        Raises:
            SpiceDBPermissionError: If the delete fails
        """
        await self._ensure_client()
        assert self._client is not None  # For mypy

        # Parse resource and subject
        resource_type, resource_id = _parse_reference(resource, "resource")
        subject_type, subject_id = _parse_reference(subject, "subject")

        try:
            relationship = Relationship(
                resource=ObjectReference(
                    object_type=resource_type,
                    object_id=resource_id,
                ),
                relation=relation,
                subject=SubjectReference(
                    object=ObjectReference(
                        object_type=subject_type,
                        object_id=subject_id,
                    ),
                ),
            )

            update = RelationshipUpdate(
                operation=RelationshipUpdate.OPERATION_DELETE,
                relationship=relationship,
            )

            request = WriteRelationshipsRequest(updates=[update])

            await self._client.WriteRelationships(request)

            self._probe.relationship_deleted(
                resource=resource,
                relation=relation,
                subject=subject,
            )

        except Exception as e:
            self._probe.relationship_delete_failed(
                resource=resource,
                relation=relation,
                subject=subject,
                error=e,
            )
            raise SpiceDBPermissionError(
                f"Failed to delete relationship: {resource} {relation} {subject}"
            ) from e

    async def delete_relationships(
        self,
        relationships: list[RelationshipSpec],
    ) -> None:
        """Delete multiple relationships in a single request.

        Args:
            relationships: List of RelationshipSpec objects to delete

        Raises:
            SpiceDBPermissionError: If the delete fails
        """
        await self._execute_relationship_updates(
            relationships, RelationshipOperation.DELETE
        )

    async def lookup_subjects(
        self,
        resource: str,
        relation: str,
        subject_type: str,
    ) -> list[SubjectRelation]:
        """Find all subjects with a relationship to a resource.

        Args:
            resource: Resource identifier (e.g., "group:01ARZ3...")
            relation: Relation name to look up (e.g., "member")
            subject_type: Type of subjects to find (e.g., "user")

        Returns:
            List of SubjectRelation objects with subject IDs and their relations

        Raises:
            SpiceDBPermissionError: If the lookup fails

        Example:
            >>> await client.lookup_subjects("group:abc123", "member", "user")
            [SubjectRelation(subject_id="user123", relation="member"), ...]
        """
        await self._ensure_client()
        assert self._client is not None  # For mypy

        # Parse resource
        resource_type, resource_id = _parse_reference(resource, "resource")

        try:
            request = LookupSubjectsRequest(
                consistency=Consistency(fully_consistent=True),
                resource=ObjectReference(
                    object_type=resource_type,
                    object_id=resource_id,
                ),
                permission=relation,
                subject_object_type=subject_type,
            )

            subjects = []
            async for response in self._client.LookupSubjects(request):
                # Extract subject ID from the response
                # The subject_object_id contains the ID without the type prefix
                subjects.append(
                    SubjectRelation(
                        subject_id=response.subject_object_id,
                        relation=relation,
                    )
                )

            self._probe.subjects_looked_up(
                resource=resource,
                relation=relation,
                subject_type=subject_type,
                count=len(subjects),
            )

            return subjects

        except Exception as e:
            self._probe.subject_lookup_failed(
                resource=resource,
                relation=relation,
                subject_type=subject_type,
                error=e,
            )
            raise SpiceDBPermissionError(
                f"Failed to lookup subjects: {resource} {relation} {subject_type}"
            ) from e

    async def lookup_resources(
        self,
        resource_type: str,
        permission: str,
        subject: str,
    ) -> list[str]:
        """Find all resources of a type that a subject has permission on.

        Args:
            resource_type: Type of resources to find (e.g., "group")
            permission: Permission or relation to check (e.g., "tenant")
            subject: Subject identifier (e.g., "tenant:abc123")

        Returns:
            List of resource IDs (without type prefix)

        Raises:
            SpiceDBPermissionError: If the lookup fails

        Example:
            >>> await client.lookup_resources("group", "tenant", "tenant:abc123")
            ["group-id-1", "group-id-2", ...]
        """
        await self._ensure_client()
        assert self._client is not None  # For mypy

        # Parse subject
        subject_type, subject_id = _parse_reference(subject, "subject")

        try:
            request = LookupResourcesRequest(
                consistency=Consistency(fully_consistent=True),
                resource_object_type=resource_type,
                permission=permission,
                subject=SubjectReference(
                    object=ObjectReference(
                        object_type=subject_type,
                        object_id=subject_id,
                    ),
                ),
            )

            resource_ids = []
            async for response in self._client.LookupResources(request):
                # Extract resource ID from the response
                resource_ids.append(response.resource_object_id)

            self._probe.resources_looked_up(
                resource_type=resource_type,
                permission=permission,
                subject=subject,
                count=len(resource_ids),
            )

            return resource_ids

        except Exception as e:
            self._probe.resource_lookup_failed(
                resource_type=resource_type,
                permission=permission,
                subject=subject,
                error=e,
            )
            raise SpiceDBPermissionError(
                f"Failed to lookup resources: {resource_type} {permission} {subject}"
            ) from e
