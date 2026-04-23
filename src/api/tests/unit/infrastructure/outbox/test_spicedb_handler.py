"""Unit tests for SpiceDBEventHandler.

These tests verify that SpiceDBEventHandler correctly adapts the
EventTranslator + AuthorizationProvider pair into the EventHandler protocol,
extracting the _apply_operation pattern match from OutboxWorker.
"""

from __future__ import annotations

from typing import Any
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


class TestSpiceDBEventHandlerIdempotency:
    """Tests for idempotent write semantics of the SpiceDB handler.

    Covers spec: Requirement: Idempotent Event Handlers — duplicate delivery scenario.

    SpiceDB relationships form a set: writing the same tuple twice is a no-op.
    The handler must tolerate being invoked twice for the same payload (e.g.,
    when a process crashes after writing to SpiceDB but before marking the
    outbox entry as processed, and the worker later retries the entry).
    """

    @pytest.mark.asyncio
    async def test_duplicate_invocation_produces_identical_final_state(self) -> None:
        """Spec: Duplicate delivery — two handler invocations produce the same outcome.

        GIVEN an outbox entry that was partially processed (handler ran but
              mark_processed was not called due to a transient failure)
        WHEN the worker retries the same entry
        THEN reprocessing produces the same final state as a single successful run
        AND no duplicate side effects are created (e.g., duplicate SpiceDB relationships)

        Uses a FakeAuthorizationProvider whose write_relationship stores tuples in a
        Python set, mirroring SpiceDB's upsert / set-membership semantics.
        """

        class FakeAuthorizationProvider:
            """Fake authz provider with set-based relationship storage (upsert semantics).

            Implements the full AuthorizationProvider protocol so that mypy's
            structural subtype check accepts it.  Only write_relationship and
            delete_relationship carry meaningful logic for this test; all other
            methods are stubs that satisfy the protocol signature.
            """

            def __init__(self) -> None:
                self.relationships: set[tuple[str, str, str]] = set()

            async def write_relationship(
                self,
                resource: str,
                relation: str,
                subject: str,
            ) -> None:
                # set.add is idempotent — adding the same tuple twice leaves it once
                self.relationships.add((resource, relation, subject))

            async def write_relationships(
                self,
                relationships: list[Any],
            ) -> None:
                for rel in relationships:
                    self.relationships.add((rel.resource, rel.relation, rel.subject))

            async def check_permission(
                self,
                resource: str,
                permission: str,
                subject: str,
            ) -> bool:
                return (resource, permission, subject) in self.relationships

            async def bulk_check_permission(
                self,
                requests: list[Any],
            ) -> set[str]:
                return set()

            async def delete_relationship(
                self,
                resource: str,
                relation: str,
                subject: str,
            ) -> None:
                self.relationships.discard((resource, relation, subject))

            async def delete_relationships(
                self,
                relationships: list[Any],
            ) -> None:
                for rel in relationships:
                    self.relationships.discard(
                        (rel.resource, rel.relation, rel.subject)
                    )

            async def delete_relationships_by_filter(
                self,
                resource_type: str,
                resource_id: str | None = None,
                relation: str | None = None,
                subject_type: str | None = None,
                subject_id: str | None = None,
            ) -> None:
                pass

            async def lookup_subjects(
                self,
                resource: str,
                relation: str,
                subject_type: str,
                optional_subject_relation: str | None = None,
            ) -> list[Any]:
                return []

            async def lookup_resources(
                self,
                resource_type: str,
                permission: str,
                subject: str,
            ) -> list[str]:
                return []

            async def read_relationships(
                self,
                resource_type: str,
                resource_id: str | None = None,
                relation: str | None = None,
                subject_type: str | None = None,
                subject_id: str | None = None,
            ) -> list[Any]:
                return []

        write_op = WriteRelationship(
            resource_type=ResourceType.GROUP,
            resource_id="group-idempotent",
            relation=RelationType.TENANT,
            subject_type=ResourceType.TENANT,
            subject_id="tenant-abc",
        )
        translator = MagicMock()
        translator.translate.return_value = [write_op]

        fake_authz = FakeAuthorizationProvider()
        handler = SpiceDBEventHandler(translator=translator, authz=fake_authz)

        payload: dict[str, Any] = {
            "group_id": "group-idempotent",
            "tenant_id": "tenant-abc",
        }

        # --- First invocation: handler writes the relationship to SpiceDB ---
        await handler.handle("GroupCreated", payload)
        state_after_first = frozenset(fake_authz.relationships)

        # --- Second invocation: retry after partial failure (mark_processed skipped) ---
        await handler.handle("GroupCreated", payload)
        state_after_second = frozenset(fake_authz.relationships)

        # Final state is identical to post-first-invocation state
        assert state_after_second == state_after_first, (
            "Duplicate handler invocation must not alter the final relationship state "
            "(idempotent: no duplicate or missing relationships)"
        )
        # And the expected relationship is present
        assert (
            "group:group-idempotent",
            "tenant",
            "tenant:tenant-abc",
        ) in state_after_second
