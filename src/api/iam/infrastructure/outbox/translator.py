"""IAM-specific event translator for SpiceDB operations.

This module provides the translation layer between IAM domain events and
SpiceDB relationship operations. It uses type-safe enums for all resource
types and relations to avoid magic strings.

The translator uses a dictionary-based dispatch approach with automatic
validation to ensure all domain events have corresponding handlers.
"""

from __future__ import annotations

from typing import Any, Callable, get_args

from iam.domain.events import (
    APIKeyCreated,
    APIKeyDeleted,
    APIKeyRevoked,
    DomainEvent,
    GroupCreated,
    GroupDeleted,
    MemberAdded,
    MemberRemoved,
    MemberRoleChanged,
    TenantCreated,
    TenantDeleted,
    TenantMemberAdded,
    TenantMemberRemoved,
    WorkspaceCreated,
    WorkspaceDeleted,
    WorkspaceMemberAdded,
    WorkspaceMemberRemoved,
    WorkspaceMemberRoleChanged,
)
from iam.domain.value_objects import GroupRole, MemberType, TenantRole, WorkspaceRole
from shared_kernel.authorization.types import RelationType, ResourceType
from shared_kernel.outbox.operations import (
    DeleteRelationship,
    DeleteRelationshipsByFilter,
    SpiceDBOperation,
    WriteRelationship,
)

# Build registry mapping event type names to classes
_EVENT_REGISTRY: dict[str, type] = {cls.__name__: cls for cls in get_args(DomainEvent)}


def validate_required_keys(payload: dict[str, Any], required_keys: list[str]) -> None:
    """Validate that all required keys are present and are strings.

    Args:
        payload: The event payload to validate
        required_keys: List of keys that must be present with string values

    Raises:
        ValueError: If any required keys are missing or have non-string values
    """
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise ValueError(f"Payload missing required keys: {sorted(missing)}")

    for key in required_keys:
        if not isinstance(payload[key], str):
            raise ValueError(
                f"Payload key '{key}' must be a string, "
                f"got {type(payload[key]).__name__}"
            )


class IAMEventTranslator:
    """Translates IAM domain events to SpiceDB operations.

    This translator handles all IAM-specific events defined in the
    DomainEvent type alias. Handler methods are mapped via a dictionary
    and validated at initialization to ensure completeness.
    """

    def __init__(self) -> None:
        """Initialize translator and validate all events have handlers."""
        # Map event classes to handler methods
        self._handlers: dict[
            type, Callable[[dict[str, Any]], list[SpiceDBOperation]]
        ] = {
            GroupCreated: self._translate_group_created,
            GroupDeleted: self._translate_group_deleted,
            MemberAdded: self._translate_member_added,
            MemberRemoved: self._translate_member_removed,
            MemberRoleChanged: self._translate_member_role_changed,
            TenantCreated: self._translate_tenant_created,
            TenantDeleted: self._translate_tenant_deleted,
            TenantMemberAdded: self._translate_tenant_member_added,
            TenantMemberRemoved: self._translate_tenant_member_removed,
            WorkspaceCreated: self._translate_workspace_created,
            WorkspaceDeleted: self._translate_workspace_deleted,
            WorkspaceMemberAdded: self._translate_workspace_member_added,
            WorkspaceMemberRemoved: self._translate_workspace_member_removed,
            WorkspaceMemberRoleChanged: self._translate_workspace_member_role_changed,
            APIKeyCreated: self._translate_api_key_created,
            APIKeyRevoked: self._translate_api_key_revoked,
            APIKeyDeleted: self._translate_api_key_deleted,
        }

        # Validate all domain events have handlers
        self._validate_handlers()

    def _validate_handlers(self) -> None:
        """Ensure all domain events have handler methods.

        This is primarily a developer convenience - Kartograph
        will fail to start if a DomainEvent doesn't have a registered handler.

        Raises:
            ValueError: If any domain events are missing handlers
        """
        event_types = set(get_args(DomainEvent))
        handler_types = set(self._handlers.keys())

        missing = event_types - handler_types
        if missing:
            missing_names = [e.__name__ for e in missing]
            raise ValueError(
                f"Missing translation handlers for events: {missing_names}"
            )

    def supported_event_types(self) -> frozenset[str]:
        """Return the event type names this translator handles."""
        return frozenset(cls.__name__ for cls in self._handlers.keys())

    def translate(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Convert an event payload to SpiceDB operations.

        Args:
            event_type: The name of the event type
            payload: The serialized event data

        Returns:
            List of SpiceDB operations to execute

        Raises:
            ValueError: If the event type is not supported
        """
        # Get event class from registry
        event_class = _EVENT_REGISTRY.get(event_type)
        if not event_class:
            raise ValueError(f"Unknown event type: {event_type}")

        # Look up handler method
        handler = self._handlers.get(event_class)
        if not handler:
            raise ValueError(f"No handler for event: {event_type}")

        return handler(payload)

    def _translate_group_created(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate GroupCreated to tenant relationship write."""
        return [
            WriteRelationship(
                resource_type=ResourceType.GROUP,
                resource_id=payload["group_id"],
                relation=RelationType.TENANT,
                subject_type=ResourceType.TENANT,
                subject_id=payload["tenant_id"],
            )
        ]

    def _translate_group_deleted(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate GroupDeleted to delete operations for all relationships."""
        operations: list[SpiceDBOperation] = []

        # Delete tenant relationship
        operations.append(
            DeleteRelationship(
                resource_type=ResourceType.GROUP,
                resource_id=payload["group_id"],
                relation=RelationType.TENANT,
                subject_type=ResourceType.TENANT,
                subject_id=payload["tenant_id"],
            )
        )

        # Delete all member relationships from the snapshot
        for member in payload["members"]:
            role = GroupRole(member["role"])
            operations.append(
                DeleteRelationship(
                    resource_type=ResourceType.GROUP,
                    resource_id=payload["group_id"],
                    relation=role,
                    subject_type=ResourceType.USER,
                    subject_id=member["user_id"],
                )
            )

        return operations

    def _translate_member_added(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate MemberAdded to role relationship write."""
        role = GroupRole(payload["role"])
        return [
            WriteRelationship(
                resource_type=ResourceType.GROUP,
                resource_id=payload["group_id"],
                relation=role,
                subject_type=ResourceType.USER,
                subject_id=payload["user_id"],
            )
        ]

    def _translate_member_removed(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate MemberRemoved to role relationship delete."""
        role = GroupRole(payload["role"])
        return [
            DeleteRelationship(
                resource_type=ResourceType.GROUP,
                resource_id=payload["group_id"],
                relation=role,
                subject_type=ResourceType.USER,
                subject_id=payload["user_id"],
            )
        ]

    def _translate_member_role_changed(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate MemberRoleChanged to delete old + write new role."""
        old_role = GroupRole(payload["old_role"])
        new_role = GroupRole(payload["new_role"])

        return [
            # First delete the old role relationship
            DeleteRelationship(
                resource_type=ResourceType.GROUP,
                resource_id=payload["group_id"],
                relation=old_role,
                subject_type=ResourceType.USER,
                subject_id=payload["user_id"],
            ),
            # Then write the new role relationship
            WriteRelationship(
                resource_type=ResourceType.GROUP,
                resource_id=payload["group_id"],
                relation=new_role,
                subject_type=ResourceType.USER,
                subject_id=payload["user_id"],
            ),
        ]

    def _translate_tenant_created(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate TenantCreated.

        TenantCreated only captures the tenant entity creation.
        Tenant admin relationships are created via TenantMemberAdded events
        which are emitted separately when members are added.
        """
        return []

    def _translate_tenant_deleted(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate TenantDeleted to delete all member relationships and root workspace pointer.

        Deletes all tenant membership relationships from the member snapshot.
        Each member may have one or more role relationships (member, admin).

        Also deletes the tenant#root_workspace relationship using filter-based
        deletion (no need to know the specific workspace ID).

        TODO: Ensure the tenant deletion service emits WorkspaceDeleted events
        for all tenant workspaces before emitting TenantDeleted. This ensures:
        - Workspace data is cleaned up from the database (via repository)
        - Child workspace relationships are cleaned up in SpiceDB
        - Domain events provide audit trail for workspace deletions
        The filter-based deletion here only cleans up the tenant's pointer to
        its root workspace; the workspace's own relationships are cleaned up
        by WorkspaceDeleted events.
        """
        operations: list[SpiceDBOperation] = []

        # Delete the tenant's root_workspace pointer (filter-based)
        operations.append(
            DeleteRelationshipsByFilter(
                resource_type=ResourceType.TENANT,
                resource_id=payload["tenant_id"],
                relation=RelationType.ROOT_WORKSPACE,
                # No subject filters - delete any root_workspace relationship
            )
        )

        # Delete all member relationships from the snapshot
        for member in payload["members"]:
            role = TenantRole(member["role"])
            operations.append(
                DeleteRelationship(
                    resource_type=ResourceType.TENANT,
                    resource_id=payload["tenant_id"],
                    relation=role,
                    subject_type=ResourceType.USER,
                    subject_id=member["user_id"],
                )
            )

        return operations

    def _translate_tenant_member_added(
        self, payload: dict[str, Any]
    ) -> list[SpiceDBOperation]:
        role = TenantRole(payload["role"])
        return [
            WriteRelationship(
                subject_type=ResourceType.USER,
                subject_id=payload["user_id"],
                relation=role,
                resource_type=ResourceType.TENANT,
                resource_id=payload["tenant_id"],
            )
        ]

    def _translate_tenant_member_removed(
        self, payload: dict[str, Any]
    ) -> list[SpiceDBOperation]:
        """Translate TenantMemberRemoved to DeleteRelationship operations.

        Unlike _translate_member_removed which receives a specific role in the
        payload, TenantMemberRemoved events do not include a role. Therefore,
        this method deletes all TenantRole relations (member, admin) for the
        given user from the tenant, ensuring complete removal regardless of
        which roles the user held.

        Args:
            payload: Event payload containing tenant_id and user_id

        Returns:
            List of DeleteRelationship operations for each TenantRole

        Raises:
            ValueError: If required keys tenant_id or user_id are missing
        """
        required_keys = {"tenant_id", "user_id"}
        missing_keys = required_keys - payload.keys()
        if missing_keys:
            raise ValueError(
                f"_translate_tenant_member_removed missing required keys: {missing_keys}"
            )

        return [
            DeleteRelationship(
                subject_type=ResourceType.USER,
                subject_id=payload["user_id"],
                relation=role,
                resource_type=ResourceType.TENANT,
                resource_id=payload["tenant_id"],
            )
            for role in TenantRole
        ]

    def _translate_workspace_created(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate WorkspaceCreated event to SpiceDB relationships.

        Creates the following relationships:
        - workspace#tenant@tenant (always)
        - tenant#root_workspace@workspace (if is_root=True)
        - workspace#parent@workspace (if parent_workspace_id exists)

        Args:
            payload: Event payload containing workspace_id, tenant_id,
                     parent_workspace_id, and is_root

        Returns:
            List of WriteRelationship operations for SpiceDB
        """
        workspace_id = payload["workspace_id"]
        tenant_id = payload["tenant_id"]
        parent_workspace_id = payload.get("parent_workspace_id")
        is_root = payload["is_root"]

        relationships: list[SpiceDBOperation] = []

        # 1. ALWAYS: Workspace belongs to tenant
        relationships.append(
            WriteRelationship(
                resource_type=ResourceType.WORKSPACE,
                resource_id=workspace_id,
                relation=RelationType.TENANT,
                subject_type=ResourceType.TENANT,
                subject_id=tenant_id,
            )
        )

        # 2. If root: Tenant points to root workspace
        if is_root:
            relationships.append(
                WriteRelationship(
                    resource_type=ResourceType.TENANT,
                    resource_id=tenant_id,
                    relation=RelationType.ROOT_WORKSPACE,
                    subject_type=ResourceType.WORKSPACE,
                    subject_id=workspace_id,
                )
            )

        # 3. If non-root: Workspace has a parent workspace
        if parent_workspace_id:
            relationships.append(
                WriteRelationship(
                    resource_type=ResourceType.WORKSPACE,
                    resource_id=workspace_id,
                    relation=RelationType.PARENT,
                    subject_type=ResourceType.WORKSPACE,
                    subject_id=parent_workspace_id,
                )
            )

        return relationships

    def _translate_workspace_deleted(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate WorkspaceDeleted event to SpiceDB relationship deletions.

        Deletes the relationships that were created during workspace creation
        and membership management, using the snapshot data captured in the event.

        Args:
            payload: Event payload containing workspace_id, tenant_id,
                     parent_workspace_id, is_root, and members (snapshot)

        Returns:
            List of DeleteRelationship operations for SpiceDB
        """
        workspace_id = payload["workspace_id"]
        tenant_id = payload["tenant_id"]
        parent_workspace_id = payload.get("parent_workspace_id")
        is_root = payload["is_root"]

        relationships: list[SpiceDBOperation] = []

        # 1. ALWAYS: Remove workspace->tenant relation
        relationships.append(
            DeleteRelationship(
                resource_type=ResourceType.WORKSPACE,
                resource_id=workspace_id,
                relation=RelationType.TENANT,
                subject_type=ResourceType.TENANT,
                subject_id=tenant_id,
            )
        )

        # 2. If root: Remove tenant->root_workspace pointer
        if is_root:
            relationships.append(
                DeleteRelationship(
                    resource_type=ResourceType.TENANT,
                    resource_id=tenant_id,
                    relation=RelationType.ROOT_WORKSPACE,
                    subject_type=ResourceType.WORKSPACE,
                    subject_id=workspace_id,
                )
            )

        # 3. If non-root: Remove workspace->parent relation
        if parent_workspace_id:
            relationships.append(
                DeleteRelationship(
                    resource_type=ResourceType.WORKSPACE,
                    resource_id=workspace_id,
                    relation=RelationType.PARENT,
                    subject_type=ResourceType.WORKSPACE,
                    subject_id=parent_workspace_id,
                )
            )

        # 4. Delete all member relationships from the snapshot
        for member in payload.get("members", []):
            role = WorkspaceRole(member["role"])
            subject_type = self._resolve_subject_type(member["member_type"])

            relationships.append(
                DeleteRelationship(
                    resource_type=ResourceType.WORKSPACE,
                    resource_id=workspace_id,
                    relation=role,
                    subject_type=subject_type,
                    subject_id=member["member_id"],
                )
            )

        return relationships

    def _resolve_subject_type(self, member_type: str) -> ResourceType:
        """Resolve the SpiceDB subject type from the member_type field.

        Args:
            member_type: The member type string ("user" or "group")

        Returns:
            ResourceType.USER for user grants, ResourceType.GROUP for group grants
        """
        resolved = MemberType(member_type)
        if resolved == MemberType.USER:
            return ResourceType.USER
        return ResourceType.GROUP

    def _translate_workspace_member_added(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate WorkspaceMemberAdded to role relationship write.

        Creates a relationship: workspace#<role>@<member_type>:<member_id>
        """
        validate_required_keys(
            payload, ["workspace_id", "member_id", "member_type", "role"]
        )
        role = WorkspaceRole(payload["role"])
        subject_type = self._resolve_subject_type(payload["member_type"])

        return [
            WriteRelationship(
                resource_type=ResourceType.WORKSPACE,
                resource_id=payload["workspace_id"],
                relation=role,
                subject_type=subject_type,
                subject_id=payload["member_id"],
            )
        ]

    def _translate_workspace_member_removed(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate WorkspaceMemberRemoved to role relationship delete.

        Deletes: workspace#<role>@<member_type>:<member_id>
        """
        validate_required_keys(
            payload, ["workspace_id", "member_id", "member_type", "role"]
        )
        role = WorkspaceRole(payload["role"])
        subject_type = self._resolve_subject_type(payload["member_type"])

        return [
            DeleteRelationship(
                resource_type=ResourceType.WORKSPACE,
                resource_id=payload["workspace_id"],
                relation=role,
                subject_type=subject_type,
                subject_id=payload["member_id"],
            )
        ]

    def _translate_workspace_member_role_changed(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate WorkspaceMemberRoleChanged to delete old + write new role.

        Deletes: workspace#<old_role>@<member_type>:<member_id>
        Writes:  workspace#<new_role>@<member_type>:<member_id>
        """
        validate_required_keys(
            payload,
            ["workspace_id", "member_id", "member_type", "old_role", "new_role"],
        )
        old_role = WorkspaceRole(payload["old_role"])
        new_role = WorkspaceRole(payload["new_role"])
        subject_type = self._resolve_subject_type(payload["member_type"])

        return [
            DeleteRelationship(
                resource_type=ResourceType.WORKSPACE,
                resource_id=payload["workspace_id"],
                relation=old_role,
                subject_type=subject_type,
                subject_id=payload["member_id"],
            ),
            WriteRelationship(
                resource_type=ResourceType.WORKSPACE,
                resource_id=payload["workspace_id"],
                relation=new_role,
                subject_type=subject_type,
                subject_id=payload["member_id"],
            ),
        ]

    def _translate_api_key_created(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate APIKeyCreated to owner and tenant relationship writes.

        Creates two relationships:
        - api_key:<id>#owner@user:<user_id> - ownership
        - api_key:<id>#tenant@tenant:<tenant_id> - tenant scoping
        """
        return [
            WriteRelationship(
                resource_type=ResourceType.API_KEY,
                resource_id=payload["api_key_id"],
                relation=RelationType.OWNER,
                subject_type=ResourceType.USER,
                subject_id=payload["user_id"],
            ),
            WriteRelationship(
                resource_type=ResourceType.API_KEY,
                resource_id=payload["api_key_id"],
                relation=RelationType.TENANT,
                subject_type=ResourceType.TENANT,
                subject_id=payload["tenant_id"],
            ),
        ]

    def _translate_api_key_revoked(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate APIKeyRevoked - no SpiceDB changes needed.

        We keep all relationships (owner, tenant) when a key is revoked because:
        - Owners need to see their revoked keys in the list (audit trail)
        - Tenant admins need to see all revoked keys
        - The is_revoked flag in PostgreSQL controls authentication
        - Revoked keys should remain visible with status "revoked"

        If we deleted the owner relationship, users would lose visibility
        of their own revoked keys, breaking the audit trail.
        """
        return []

    def _translate_api_key_deleted(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate APIKeyDeleted to delete all relationships.

        Used for cascade deletion when a tenant is deleted. Removes all
        SpiceDB relationships to prevent orphaned data.

        Deletes:
        - api_key:<id>#owner@user:<user_id>
        - api_key:<id>#tenant@tenant:<tenant_id>
        """
        return [
            DeleteRelationship(
                resource_type=ResourceType.API_KEY,
                resource_id=payload["api_key_id"],
                relation=RelationType.OWNER,
                subject_type=ResourceType.USER,
                subject_id=payload["user_id"],
            ),
            DeleteRelationship(
                resource_type=ResourceType.API_KEY,
                resource_id=payload["api_key_id"],
                relation=RelationType.TENANT,
                subject_type=ResourceType.TENANT,
                subject_id=payload["tenant_id"],
            ),
        ]
