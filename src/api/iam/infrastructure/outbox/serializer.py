"""IAM-specific event serializer for outbox persistence.

This module provides serialization and deserialization of IAM domain events
for storage in the outbox table. Events are converted to JSON-compatible
dictionaries and reconstructed when processed by the worker.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, get_args

from iam.domain.events import (
    DomainEvent,
    MemberSnapshot,
    WorkspaceMemberSnapshot,
)
from iam.domain.value_objects import MemberType, TenantRole, WorkspaceRole

# Derive supported events from the DomainEvent type alias
_SUPPORTED_EVENTS: frozenset[str] = frozenset(
    cls.__name__ for cls in get_args(DomainEvent)
)

# Build registry mapping event type names to classes
_EVENT_REGISTRY: dict[str, type] = {cls.__name__: cls for cls in get_args(DomainEvent)}


class IAMEventSerializer:
    """Serializes and deserializes IAM domain events.

    This serializer handles all IAM-specific events defined in the
    DomainEvent type alias. It converts domain events to JSON-compatible
    dictionaries for storage and reconstructs them when needed.
    """

    def supported_event_types(self) -> frozenset[str]:
        """Return the event type names this serializer handles."""
        return _SUPPORTED_EVENTS

    def serialize(self, event: DomainEvent) -> dict[str, Any]:
        """Convert a domain event to a JSON-serializable dictionary.

        Args:
            event: The domain event to serialize

        Returns:
            Dictionary with all event fields

        Raises:
            ValueError: If the event type is not supported
        """
        event_type = type(event).__name__
        if event_type not in _SUPPORTED_EVENTS:
            raise ValueError(f"Unsupported event type: {event_type}")

        # Convert dataclass to dict
        data = asdict(event)

        # Convert non-JSON-serializable types
        self._convert_for_json(data)

        return data

    def deserialize(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> Any:
        """Reconstruct a domain event from a payload.

        Args:
            event_type: The name of the event type
            payload: The serialized event data

        Returns:
            The reconstructed domain event

        Raises:
            ValueError: If the event type is not supported
        """
        event_class = _EVENT_REGISTRY.get(event_type)
        if event_class is None:
            raise ValueError(f"Unsupported event type: {event_type}")

        # Convert serialized types back to their original types
        data = payload.copy()
        self._convert_from_json(data, event_type)

        return event_class(**data)

    def _convert_for_json(self, data: dict[str, Any]) -> None:
        """Convert non-JSON-serializable types in-place.

        Args:
            data: The dictionary to convert
        """
        for key, value in list(data.items()):
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, tuple):
                # Handle MemberSnapshot tuples in GroupDeleted/TenantDeleted
                # and WorkspaceMemberSnapshot tuples in WorkspaceDeleted
                data[key] = [
                    self._convert_member_snapshot(item)
                    if isinstance(item, MemberSnapshot)
                    else self._convert_workspace_member_snapshot(item)
                    if isinstance(item, WorkspaceMemberSnapshot)
                    else item
                    for item in value
                ]
            elif isinstance(value, dict):
                self._convert_for_json(value)

    def _convert_member_snapshot(self, snapshot: MemberSnapshot) -> dict[str, Any]:
        """Convert a MemberSnapshot to a JSON-serializable dict."""
        return {
            "user_id": snapshot.user_id,
            "role": snapshot.role,
        }

    def _convert_workspace_member_snapshot(
        self, snapshot: WorkspaceMemberSnapshot
    ) -> dict[str, Any]:
        """Convert a WorkspaceMemberSnapshot to a JSON-serializable dict."""
        return {
            "member_id": snapshot.member_id,
            "member_type": snapshot.member_type,
            "role": snapshot.role,
        }

    def _convert_from_json(self, data: dict[str, Any], event_type: str) -> None:
        """Convert serialized types back to original types in-place.

        Args:
            data: The dictionary to convert
            event_type: The event type for context-specific conversion
        """
        # Convert occurred_at back to datetime
        if "occurred_at" in data:
            data["occurred_at"] = datetime.fromisoformat(data["occurred_at"])

        # Convert members list back to tuple of MemberSnapshot
        if "members" in data and event_type in ("GroupDeleted", "TenantDeleted"):
            data["members"] = tuple(
                MemberSnapshot(
                    user_id=m["user_id"],
                    role=m["role"],
                )
                for m in data["members"]
            )

        # Convert members list back to tuple of WorkspaceMemberSnapshot
        if "members" in data and event_type == "WorkspaceDeleted":
            data["members"] = tuple(
                WorkspaceMemberSnapshot(
                    member_id=m["member_id"],
                    member_type=m["member_type"],
                    role=m["role"],
                )
                for m in data["members"]
            )

        # Convert workspace member event strings to domain enums
        _WORKSPACE_MEMBER_EVENTS = (
            "WorkspaceMemberAdded",
            "WorkspaceMemberRemoved",
            "WorkspaceMemberRoleChanged",
        )
        if event_type in _WORKSPACE_MEMBER_EVENTS:
            if "member_type" in data:
                data["member_type"] = MemberType(data["member_type"])
            if "role" in data:
                data["role"] = WorkspaceRole(data["role"])
            if "old_role" in data:
                data["old_role"] = WorkspaceRole(data["old_role"])
            if "new_role" in data:
                data["new_role"] = WorkspaceRole(data["new_role"])

        # Convert tenant member event strings to domain enums
        if event_type == "TenantMemberAdded" and "role" in data:
            data["role"] = TenantRole(data["role"])
