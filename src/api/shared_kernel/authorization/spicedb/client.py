"""SpiceDB client implementation for authorization.

Provides async SpiceDB client wrapping the authzed library with proper
error handling and type safety.
"""

from __future__ import annotations

import asyncio
from enum import IntEnum
from pathlib import Path

import grpc
from authzed.api.v1 import (
    CheckPermissionRequest,
    Consistency,
    DeleteRelationshipsRequest,
    LookupResourcesRequest,
    LookupSubjectsRequest,
    ObjectReference,
    ReadRelationshipsRequest,
    Relationship,
    RelationshipFilter,
    RelationshipUpdate,
    SubjectFilter,
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
from shared_kernel.authorization.types import (
    RelationshipSpec,
    RelationshipTuple,
    SubjectRelation,
)


class RelationshipOperation(IntEnum):
    """Enum for relationship operation types."""

    WRITE = RelationshipUpdate.OPERATION_TOUCH
    DELETE = RelationshipUpdate.OPERATION_DELETE


def _create_tls_credentials(
    preshared_key: str, cert_path: str | None = None
) -> grpc.ChannelCredentials:
    """Create TLS channel credentials with optional custom root certificate.

    Args:
        preshared_key: Bearer token for authentication
        cert_path: Path to custom root certificate (e.g., self-signed cert)

    Returns:
        Composite channel credentials with TLS and bearer token

    Raises:
        ValueError: If cert_path is provided but file doesn't exist or can't be read
    """
    # Load custom root certificate if provided
    root_certs = None
    if cert_path:
        cert_file = Path(cert_path)
        if not cert_file.exists():
            raise ValueError(f"TLS certificate file not found: {cert_path}")
        if not cert_file.is_file():
            raise ValueError(f"TLS certificate path is not a file: {cert_path}")
        try:
            root_certs = cert_file.read_bytes()
        except OSError as e:
            raise ValueError(
                f"Failed to read TLS certificate file '{cert_path}': {e}"
            ) from e

    # Create SSL credentials
    ssl_creds = grpc.ssl_channel_credentials(root_certificates=root_certs)

    # Create bearer token call credentials
    call_creds = grpc.access_token_call_credentials(preshared_key)

    # Combine into composite credentials
    return grpc.composite_channel_credentials(ssl_creds, call_creds)


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


def _parse_subject_reference(ref: str) -> tuple[str, str, str | None]:
    """Parse a subject reference string that may include a relation.

    Handles both simple subjects (``user:alice``) and subjects with
    relations (``group:eng-team#member``) as required by SpiceDB schemas
    that define subject types like ``user | group#member``.

    Args:
        ref: Subject reference in format "type:id" or "type:id#relation"

    Returns:
        Tuple of (type, id, optional_relation)

    Raises:
        ValueError: If reference format is invalid
    """
    if ":" not in ref:
        raise ValueError(
            f"Invalid subject format: '{ref}'. Expected 'type:id' or "
            "'type:id#relation' format."
        )
    type_part, id_part = ref.split(":", 1)

    # Check if the id contains a #relation suffix
    if "#" in id_part:
        obj_id, relation = id_part.rsplit("#", 1)
        return (type_part, obj_id, relation)

    return (type_part, id_part, None)


def _build_subject_reference(
    subject_type: str, subject_id: str, subject_relation: str | None = None
) -> SubjectReference:
    """Build a SubjectReference with optional relation.

    Args:
        subject_type: Type of the subject (e.g., "user", "group")
        subject_id: ID of the subject
        subject_relation: Optional relation suffix (e.g., "member" for group#member)

    Returns:
        SubjectReference object for SpiceDB API calls
    """
    obj_ref = ObjectReference(
        object_type=subject_type,
        object_id=subject_id,
    )
    if subject_relation:
        return SubjectReference(
            object=obj_ref,
            optional_relation=subject_relation,
        )
    return SubjectReference(object=obj_ref)


def _build_relationship_update(
    resource: str, relation: str, subject: str, operation: RelationshipOperation
) -> RelationshipUpdate:
    """Build a RelationshipUpdate for write or delete operations.

    Args:
        resource: Resource identifier (e.g., "group:abc123")
        relation: Relation name (e.g., "member")
        subject: Subject identifier (e.g., "user:alice" or "group:eng#member")
        operation: RelationshipOperation.WRITE or DELETE

    Returns:
        RelationshipUpdate object ready for WriteRelationshipsRequest
    """
    resource_type, resource_id = _parse_reference(resource, "resource")
    subject_type, subject_id, subject_relation = _parse_subject_reference(subject)

    subject_ref = _build_subject_reference(subject_type, subject_id, subject_relation)

    relationship = Relationship(
        resource=ObjectReference(
            object_type=resource_type,
            object_id=resource_id,
        ),
        relation=relation,
        subject=subject_ref,
    )

    return RelationshipUpdate(
        operation=int(operation),  # type: ignore[arg-type]  # Protobuf expects ValueType, but accepts int
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
        use_tls: bool = True,
        cert_path: str | None = None,
        probe: AuthorizationProbe | None = None,
    ):
        """Initialize SpiceDB client.

        Args:
            endpoint: SpiceDB gRPC endpoint (e.g., "localhost:50051")
            preshared_key: Pre-shared key for authentication
            use_tls: Use TLS for connection (default: True, False for local dev only)
            cert_path: Path to custom root certificate for TLS (e.g., self-signed cert)
            probe: Optional domain probe for observability
        """
        self._endpoint = endpoint
        self._preshared_key = preshared_key
        self._use_tls = use_tls
        self._cert_path = cert_path
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
                        if self._use_tls:
                            credentials = _create_tls_credentials(
                                self._preshared_key, self._cert_path
                            )
                        else:
                            credentials = insecure_bearer_token_credentials(
                                self._preshared_key
                            )
                            self._probe.insecure_connection_used(self._endpoint)

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
            subject: Subject identifier (e.g., "user:alice" or "group:eng#member")

        Raises:
            SpiceDBPermissionError: If the write fails
        """
        await self._ensure_client()
        assert self._client is not None  # For mypy

        # Parse resource and subject
        resource_type, resource_id = _parse_reference(resource, "resource")
        subject_type, subject_id, subject_relation = _parse_subject_reference(subject)

        try:
            subject_ref = _build_subject_reference(
                subject_type, subject_id, subject_relation
            )

            relationship = Relationship(
                resource=ObjectReference(
                    object_type=resource_type,
                    object_id=resource_id,
                ),
                relation=relation,
                subject=subject_ref,
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

        Here, `permission` can also be a relation.

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
            subject: Subject identifier (e.g., "user:alice" or "group:eng#member")

        Raises:
            SpiceDBPermissionError: If the delete fails
        """
        await self._ensure_client()
        assert self._client is not None  # For mypy

        # Parse resource and subject
        resource_type, resource_id = _parse_reference(resource, "resource")
        subject_type, subject_id, subject_relation = _parse_subject_reference(subject)

        try:
            subject_ref = _build_subject_reference(
                subject_type, subject_id, subject_relation
            )

            relationship = Relationship(
                resource=ObjectReference(
                    object_type=resource_type,
                    object_id=resource_id,
                ),
                relation=relation,
                subject=subject_ref,
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

    async def delete_relationships_by_filter(
        self,
        resource_type: str,
        resource_id: str | None = None,
        relation: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> None:
        """Delete all relationships matching the filter.

        Uses SpiceDB's filter-based deletion to remove multiple relationships
        in a single operation. At least one filter parameter must be specified
        beyond resource_type.

        Args:
            resource_type: Type of resource (required)
            resource_id: Specific resource ID (optional, omit to match all)
            relation: Relation name (optional, omit to match all)
            subject_type: Type of subject (optional, omit to match all)
            subject_id: Specific subject ID (optional, omit to match all)

        Raises:
            SpiceDBPermissionError: If the delete fails
            ValueError: If insufficient filter criteria provided
            ValueError: If subject_id is provided without subject_type

        Example:
            # Delete all root_workspace relations for tenant:123
            await client.delete_relationships_by_filter(
                resource_type="tenant",
                resource_id="123",
                relation="root_workspace",
            )
        """
        if not any([resource_id, relation, subject_type, subject_id]):
            raise ValueError(
                "At least one filter parameter beyond resource_type must be specified"
            )

        # Validate subject_id requires subject_type
        if subject_id and not subject_type:
            raise ValueError(
                "subject_type must be provided when subject_id is specified"
            )

        await self._ensure_client()
        assert self._client is not None  # For mypy

        try:
            # Build the relationship filter
            filter_kwargs: dict[str, object] = {
                "resource_type": resource_type,
            }
            if resource_id:
                filter_kwargs["optional_resource_id"] = resource_id
            if relation:
                filter_kwargs["optional_relation"] = relation

            # Build optional subject filter
            if subject_type or subject_id:
                subject_filter_kwargs: dict[str, str] = {}
                if subject_type:
                    subject_filter_kwargs["subject_type"] = subject_type
                if subject_id:
                    subject_filter_kwargs["optional_subject_id"] = subject_id
                filter_kwargs["optional_subject_filter"] = SubjectFilter(
                    **subject_filter_kwargs
                )

            relationship_filter = RelationshipFilter(**filter_kwargs)
            request = DeleteRelationshipsRequest(
                relationship_filter=relationship_filter,
            )

            await self._client.DeleteRelationships(request)

            self._probe.relationships_deleted_by_filter(
                resource_type=resource_type,
                resource_id=resource_id,
                relation=relation,
                subject_type=subject_type,
                subject_id=subject_id,
            )

        except Exception as e:
            self._probe.relationships_delete_by_filter_failed(
                resource_type=resource_type,
                resource_id=resource_id,
                relation=relation,
                subject_type=subject_type,
                subject_id=subject_id,
                error=e,
            )
            raise SpiceDBPermissionError(
                f"Failed to delete relationships by filter: "
                f"resource_type={resource_type}, resource_id={resource_id}, "
                f"relation={relation}"
            ) from e

    async def lookup_subjects(
        self,
        resource: str,
        relation: str,
        subject_type: str,
        optional_subject_relation: str | None = None,
    ) -> list[SubjectRelation]:
        """Find all subjects with a relationship to a resource.

        Args:
            resource: Resource identifier (e.g., "group:01ARZ3...")
            relation: Relation name to look up (e.g., "member")
            subject_type: Type of subjects to find (e.g., "user")
            optional_subject_relation: Optional subject relation filter (e.g., "member"
                for group#member subjects). Required when subjects were written with
                a subject relation per the SpiceDB schema.

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
            request_kwargs: dict = {
                "consistency": Consistency(fully_consistent=True),
                "resource": ObjectReference(
                    object_type=resource_type,
                    object_id=resource_id,
                ),
                "permission": relation,
                "subject_object_type": subject_type,
            }
            if optional_subject_relation:
                request_kwargs["optional_subject_relation"] = optional_subject_relation
            request = LookupSubjectsRequest(**request_kwargs)

            subjects = []
            async for response in self._client.LookupSubjects(request):
                # Extract subject ID from the response
                # The subject_object_id contains the ID without the type prefix

                # NOTE: relation field has context-dependent semantics:
                # - If optional_subject_relation provided: contains subject's relation (e.g., "member")
                # - If optional_subject_relation omitted: contains resource's permission (e.g., "admin")
                # See SubjectRelation docstring for full explanation.
                subjects.append(
                    SubjectRelation(
                        subject_id=response.subject_object_id,
                        relation=optional_subject_relation or relation,
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

    async def read_relationships(
        self,
        resource_type: str,
        resource_id: str | None = None,
        relation: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> list[RelationshipTuple]:
        """Read explicit relationship tuples from SpiceDB.

        Unlike lookup_subjects which computes permissions by expanding
        groups and other indirections, this returns only the explicit
        tuples stored in SpiceDB.

        Args:
            resource_type: Type of resource (required)
            resource_id: Optional resource ID filter
            relation: Optional relation filter
            subject_type: Optional subject type filter
            subject_id: Optional subject ID filter

        Returns:
            List of RelationshipTuple objects with resource, relation, subject

        Raises:
            SpiceDBPermissionError: If the read fails

        Example:
            >>> await client.read_relationships(
            ...     resource_type="workspace",
            ...     resource_id="abc123",
            ...     relation="admin"
            ... )
            [RelationshipTuple(
                resource="workspace:abc123",
                relation="admin",
                subject="group:xyz#member"
            ), ...]
        """
        # Validate subject_id requires subject_type
        if subject_id and not subject_type:
            raise ValueError(
                "subject_type must be provided when subject_id is specified"
            )

        await self._ensure_client()
        assert self._client is not None  # For mypy

        try:
            # Build the relationship filter
            filter_kwargs: dict[str, object] = {
                "resource_type": resource_type,
            }
            if resource_id:
                filter_kwargs["optional_resource_id"] = resource_id
            if relation:
                filter_kwargs["optional_relation"] = relation

            # Build optional subject filter
            if subject_type:
                subject_filter_kwargs: dict[str, str] = {
                    "subject_type": subject_type,
                }
                if subject_id:
                    subject_filter_kwargs["optional_subject_id"] = subject_id
                filter_kwargs["optional_subject_filter"] = SubjectFilter(
                    **subject_filter_kwargs
                )

            relationship_filter = RelationshipFilter(**filter_kwargs)
            request = ReadRelationshipsRequest(
                consistency=Consistency(fully_consistent=True),
                relationship_filter=relationship_filter,
            )

            tuples: list[RelationshipTuple] = []
            async for response in self._client.ReadRelationships(request):
                rel = response.relationship
                # Format resource as "type:id"
                resource_str = f"{rel.resource.object_type}:{rel.resource.object_id}"

                # Format subject as "type:id" or "type:id#relation"
                subject_str = (
                    f"{rel.subject.object.object_type}:{rel.subject.object.object_id}"
                )
                if rel.subject.optional_relation:
                    subject_str = f"{subject_str}#{rel.subject.optional_relation}"

                tuples.append(
                    RelationshipTuple(
                        resource=resource_str,
                        relation=rel.relation,
                        subject=subject_str,
                    )
                )

            self._probe.relationships_read(
                resource_type=resource_type,
                resource_id=resource_id,
                relation=relation,
                count=len(tuples),
            )

            return tuples

        except Exception as e:
            self._probe.relationships_read_failed(
                resource_type=resource_type,
                resource_id=resource_id,
                relation=relation,
                error=e,
            )
            raise SpiceDBPermissionError(
                f"Failed to read relationships: "
                f"resource_type={resource_type}, resource_id={resource_id}, "
                f"relation={relation}"
            ) from e
