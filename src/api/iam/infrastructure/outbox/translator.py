"""IAM-specific event translator for SpiceDB operations.

This module provides the translation layer between IAM domain events and
SpiceDB relationship operations. It uses type-safe enums for all resource
types and relations to avoid magic strings.
"""

from __future__ import annotations

from typing import Any, get_args

from iam.domain.events import DomainEvent
from iam.domain.value_objects import GroupRole
from shared_kernel.authorization.types import RelationType, ResourceType
from shared_kernel.outbox.operations import (
    DeleteRelationship,
    SpiceDBOperation,
    WriteRelationship,
)

# Derive supported events from the DomainEvent type alias
_SUPPORTED_EVENTS: frozenset[str] = frozenset(
    cls.__name__ for cls in get_args(DomainEvent)
)


class IAMEventTranslator:
    """Translates IAM domain events to SpiceDB operations.

    This translator handles all IAM-specific events defined in the
    DomainEvent type alias. The supported events are derived automatically
    from the type definition to avoid duplication.
    """

    def supported_event_types(self) -> frozenset[str]:
        """Return the event type names this translator handles."""
        return _SUPPORTED_EVENTS

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
        match event_type:
            case "GroupCreated":
                return self._translate_group_created(payload)
            case "GroupDeleted":
                return self._translate_group_deleted(payload)
            case "MemberAdded":
                return self._translate_member_added(payload)
            case "MemberRemoved":
                return self._translate_member_removed(payload)
            case "MemberRoleChanged":
                return self._translate_member_role_changed(payload)
            case "TenantCreated":
                return self._translate_tenant_created(payload)
            case "TenantDeleted":
                return self._translate_tenant_deleted(payload)
            case "APIKeyCreated":
                return self._translate_api_key_created(payload)
            case "APIKeyRevoked":
                return self._translate_api_key_revoked(payload)
            case _:
                raise ValueError(f"Unsupported event type: {event_type}")

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

        For the walking skeleton, tenants don't automatically get SpiceDB
        relationships on creation. The SpiceDB tenant definition exists,
        but relationships (like admin assignments) will be set separately.
        """
        return []

    def _translate_tenant_deleted(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate TenantDeleted.

        For the walking skeleton, tenant deletion doesn't require SpiceDB
        cleanup. Any cascade rules or related resource cleanup should be
        handled by database constraints or separate processes.
        """
        return []

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
