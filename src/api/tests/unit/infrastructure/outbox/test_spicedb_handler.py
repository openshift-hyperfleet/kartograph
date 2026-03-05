"""Unit tests for SpiceDBEventHandler.

These tests verify that SpiceDBEventHandler correctly adapts the
EventTranslator + AuthorizationProvider pair into the EventHandler protocol,
extracting the _apply_operation pattern match from OutboxWorker.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from infrastructure.outbox.spicedb_handler import SpiceDBEventHandler
from shared_kernel.authorization.types import RelationType, ResourceType
from shared_kernel.outbox.operations import (
    DeleteRelationship,
    DeleteRelationshipsByFilter,
    WriteRelationship,
)
from shared_kernel.outbox.ports import EventHandler


class TestSpiceDBEventHandler:
    """Tests for SpiceDBEventHandler."""

    def test_implements_event_handler_protocol(self) -> None:
        """SpiceDBEventHandler must satisfy the EventHandler protocol."""
        translator = MagicMock()
        authz = AsyncMock()
        handler = SpiceDBEventHandler(translator=translator, authz=authz)

        assert isinstance(handler, EventHandler)

    def test_supported_event_types_delegates_to_translator(self) -> None:
        """supported_event_types should delegate to the translator."""
        expected = frozenset({"GroupCreated", "MemberAdded"})
        translator = MagicMock()
        translator.supported_event_types.return_value = expected
        authz = AsyncMock()

        handler = SpiceDBEventHandler(translator=translator, authz=authz)

        result = handler.supported_event_types()

        assert result == expected
        translator.supported_event_types.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_translates_and_applies_write_relationship(self) -> None:
        """handle should translate event and apply WriteRelationship via authz."""
        write_op = WriteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="group-123",
            relation=RelationType.MEMBER,
            subject_type=ResourceType.USER,
            subject_id="user-456",
        )
        translator = MagicMock()
        translator.translate.return_value = [write_op]
        authz = AsyncMock()

        handler = SpiceDBEventHandler(translator=translator, authz=authz)
        await handler.handle("GroupCreated", {"id": "group-123"})

        translator.translate.assert_called_once_with(
            "GroupCreated", {"id": "group-123"}
        )
        authz.write_relationship.assert_awaited_once_with(
            resource="group:group-123",
            relation="member",
            subject="user:user-456",
        )

    @pytest.mark.asyncio
    async def test_handle_translates_and_applies_delete_relationship(self) -> None:
        """handle should translate event and apply DeleteRelationship via authz."""
        delete_op = DeleteRelationship(
            resource_type=ResourceType.WORKSPACE,
            resource_id="ws-789",
            relation=RelationType.ADMIN,
            subject_type=ResourceType.USER,
            subject_id="user-111",
        )
        translator = MagicMock()
        translator.translate.return_value = [delete_op]
        authz = AsyncMock()

        handler = SpiceDBEventHandler(translator=translator, authz=authz)
        await handler.handle("MemberRemoved", {"workspace_id": "ws-789"})

        authz.delete_relationship.assert_awaited_once_with(
            resource="workspace:ws-789",
            relation="admin",
            subject="user:user-111",
        )

    @pytest.mark.asyncio
    async def test_handle_translates_and_applies_delete_by_filter(self) -> None:
        """handle should translate event and apply DeleteRelationshipsByFilter via authz."""
        filter_op = DeleteRelationshipsByFilter(
            resource_type=ResourceType.GROUP,
            resource_id="group-999",
            relation=RelationType.MEMBER,
            subject_type=ResourceType.USER,
            subject_id=None,
        )
        translator = MagicMock()
        translator.translate.return_value = [filter_op]
        authz = AsyncMock()

        handler = SpiceDBEventHandler(translator=translator, authz=authz)
        await handler.handle("GroupDeleted", {"id": "group-999"})

        authz.delete_relationships_by_filter.assert_awaited_once_with(
            resource_type="group",
            resource_id="group-999",
            relation="member",
            subject_type="user",
            subject_id=None,
        )

    @pytest.mark.asyncio
    async def test_handle_applies_multiple_operations_in_order(self) -> None:
        """handle should apply all operations in order from the translator."""
        write_op = WriteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="group-1",
            relation=RelationType.TENANT,
            subject_type=ResourceType.TENANT,
            subject_id="tenant-1",
        )
        delete_op = DeleteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="group-1",
            relation=RelationType.MEMBER,
            subject_type=ResourceType.USER,
            subject_id="user-old",
        )
        translator = MagicMock()
        translator.translate.return_value = [write_op, delete_op]
        authz = AsyncMock()

        handler = SpiceDBEventHandler(translator=translator, authz=authz)
        await handler.handle("GroupUpdated", {"id": "group-1"})

        # Verify both operations applied
        authz.write_relationship.assert_awaited_once_with(
            resource="group:group-1",
            relation="tenant",
            subject="tenant:tenant-1",
        )
        authz.delete_relationship.assert_awaited_once_with(
            resource="group:group-1",
            relation="member",
            subject="user:user-old",
        )

        # Verify order: write before delete
        assert authz.method_calls == [
            call.write_relationship(
                resource="group:group-1",
                relation="tenant",
                subject="tenant:tenant-1",
            ),
            call.delete_relationship(
                resource="group:group-1",
                relation="member",
                subject="user:user-old",
            ),
        ]

    @pytest.mark.asyncio
    async def test_handle_delete_by_filter_with_none_optional_fields(self) -> None:
        """handle should correctly pass None for optional filter fields."""
        filter_op = DeleteRelationshipsByFilter(
            resource_type=ResourceType.TENANT,
            resource_id="tenant-1",
            relation=None,
            subject_type=None,
            subject_id=None,
        )
        translator = MagicMock()
        translator.translate.return_value = [filter_op]
        authz = AsyncMock()

        handler = SpiceDBEventHandler(translator=translator, authz=authz)
        await handler.handle("TenantDeleted", {"tenant_id": "tenant-1"})

        authz.delete_relationships_by_filter.assert_awaited_once_with(
            resource_type="tenant",
            resource_id="tenant-1",
            relation=None,
            subject_type=None,
            subject_id=None,
        )

    @pytest.mark.asyncio
    async def test_handle_propagates_translator_errors(self) -> None:
        """handle should propagate errors raised by the translator."""
        translator = MagicMock()
        translator.translate.side_effect = ValueError("Unsupported event type")
        authz = AsyncMock()

        handler = SpiceDBEventHandler(translator=translator, authz=authz)

        with pytest.raises(ValueError, match="Unsupported event type"):
            await handler.handle("UnknownEvent", {})

    @pytest.mark.asyncio
    async def test_handle_propagates_authz_errors(self) -> None:
        """handle should propagate errors raised by the authorization provider."""
        write_op = WriteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="group-1",
            relation=RelationType.MEMBER,
            subject_type=ResourceType.USER,
            subject_id="user-1",
        )
        translator = MagicMock()
        translator.translate.return_value = [write_op]
        authz = AsyncMock()
        authz.write_relationship.side_effect = Exception("SpiceDB unavailable")

        handler = SpiceDBEventHandler(translator=translator, authz=authz)

        with pytest.raises(Exception, match="SpiceDB unavailable"):
            await handler.handle("GroupCreated", {"id": "group-1"})

    @pytest.mark.asyncio
    async def test_handle_raises_for_unsupported_operation_type(self) -> None:
        """handle should raise TypeError for unknown operation types."""
        # Create a fake operation object that isn't one of the 3 known types
        fake_op = object()  # not Write/Delete/DeleteByFilter
        translator = MagicMock()
        translator.translate.return_value = [fake_op]
        authz = AsyncMock()

        handler = SpiceDBEventHandler(translator=translator, authz=authz)

        with pytest.raises(TypeError, match="Unsupported"):
            await handler.handle("SomeEvent", {})

        # Verify no authz methods were called
        authz.write_relationship.assert_not_awaited()
        authz.delete_relationship.assert_not_awaited()
        authz.delete_relationships_by_filter.assert_not_awaited()
