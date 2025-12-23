"""SpiceDB client implementation for authorization.

Provides async SpiceDB client wrapping the authzed library with proper
error handling and type safety.
"""

from __future__ import annotations

from authzed.api.v1 import (
    CheckPermissionRequest,
    Consistency,
    ObjectReference,
    Relationship,
    RelationshipUpdate,
    SubjectReference,
    WriteRelationshipsRequest,
)
from authzed.api.v1.permission_service_pb2 import CheckPermissionResponse
from grpcutil import bearer_token_credentials

from shared_kernel.authorization.observability import (
    AuthorizationProbe,
    DefaultAuthorizationProbe,
)
from shared_kernel.authorization.protocols import CheckRequest
from shared_kernel.authorization.spicedb.exceptions import (
    SpiceDBConnectionError,
    SpiceDBPermissionError,
)


class SpiceDBClient:
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

    async def _ensure_client(self):
        """Lazily initialize the gRPC client."""
        if self._client is None:
            try:
                from authzed.api.v1 import Client

                # Create credentials with preshared key
                credentials = bearer_token_credentials(self._preshared_key)

                # Initialize client
                self._client = Client(
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
        resource_type, resource_id = resource.split(":", 1)
        subject_type, subject_id = subject.split(":", 1)

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
        resource_type, resource_id = resource.split(":", 1)
        subject_type, subject_id = subject.split(":", 1)

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
        resource_type, resource_id = resource.split(":", 1)
        subject_type, subject_id = subject.split(":", 1)

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
