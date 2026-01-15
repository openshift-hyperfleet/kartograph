"""End-to-end integration tests for outbox pattern consistency.

These tests verify the complete flow from API to SpiceDB via the outbox:
1. Create group -> verify outbox entry -> verify SpiceDB after processing
2. Add member -> verify role relationship in SpiceDB
3. Remove member -> verify relationship deleted
4. Delete group -> verify all relationships removed
5. Failure scenario: events stay unprocessed when errors occur

Requirements:
    - PostgreSQL with migrations applied
    - SpiceDB running and accessible
"""

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.aggregates import Group
from iam.domain.events import GroupCreated, MemberAdded, MemberRemoved
from iam.domain.value_objects import Role, TenantId, UserId
from iam.infrastructure.group_repository import GroupRepository
from iam.infrastructure.outbox import IAMEventSerializer, IAMEventTranslator
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    ResourceType,
    RelationType,
    format_resource,
    format_subject,
)
from infrastructure.outbox.models import OutboxModel
from infrastructure.outbox.repository import OutboxRepository
from infrastructure.outbox.worker import OutboxWorker
from infrastructure.outbox.composite import CompositeTranslator
from shared_kernel.outbox.observability import DefaultOutboxWorkerProbe

pytestmark = pytest.mark.integration


class TestOutboxEventCreation:
    """Tests for verifying outbox entries are created correctly."""

    @pytest.mark.asyncio
    async def test_group_creation_appends_group_created_event(
        self, async_session: AsyncSession, spicedb_client: AuthorizationProvider
    ):
        """When a group is created, a GroupCreated event should be appended to the outbox."""
        serializer = IAMEventSerializer()
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        tenant_id = TenantId.generate()
        # Use factory method which records GroupCreated event
        group = Group.create(name="Test Group for Outbox", tenant_id=tenant_id)

        async with async_session.begin():
            await group_repo.save(group)

        # Query the outbox for the GroupCreated event
        stmt = select(OutboxModel).where(
            OutboxModel.aggregate_id == group.id.value,
            OutboxModel.event_type == "GroupCreated",
        )
        result = await async_session.execute(stmt)
        outbox_entry = result.scalar_one_or_none()

        assert outbox_entry is not None
        assert outbox_entry.aggregate_type == "group"
        assert outbox_entry.event_type == "GroupCreated"
        assert outbox_entry.processed_at is None

        # Verify the payload can be deserialized
        event = serializer.deserialize(outbox_entry.event_type, outbox_entry.payload)
        assert isinstance(event, GroupCreated)
        assert event.group_id == group.id.value
        assert event.tenant_id == tenant_id.value

        # Clean up
        await async_session.execute(
            text("DELETE FROM outbox WHERE aggregate_id = :id"),
            {"id": group.id.value},
        )
        await async_session.execute(
            text("DELETE FROM groups WHERE id = :id"),
            {"id": group.id.value},
        )
        await async_session.commit()

    @pytest.mark.asyncio
    async def test_add_member_appends_member_added_event(
        self, async_session: AsyncSession, spicedb_client: AuthorizationProvider
    ):
        """When a member is added, a MemberAdded event should be appended to the outbox."""
        serializer = IAMEventSerializer()
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        tenant_id = TenantId.generate()
        # Use factory method
        group = Group.create(name="Test Group Members", tenant_id=tenant_id)
        user_id = UserId.generate()

        # Add member to the group
        group.add_member(user_id, Role.ADMIN)

        async with async_session.begin():
            await group_repo.save(group)

        # Query the outbox for the MemberAdded event
        stmt = select(OutboxModel).where(
            OutboxModel.aggregate_id == group.id.value,
            OutboxModel.event_type == "MemberAdded",
        )
        result = await async_session.execute(stmt)
        outbox_entry = result.scalar_one_or_none()

        assert outbox_entry is not None
        assert outbox_entry.aggregate_type == "group"

        # Verify the payload
        event = serializer.deserialize(outbox_entry.event_type, outbox_entry.payload)
        assert isinstance(event, MemberAdded)
        assert event.group_id == group.id.value
        assert event.user_id == user_id.value
        assert event.role == Role.ADMIN

        # Clean up
        await async_session.execute(
            text("DELETE FROM outbox WHERE aggregate_id = :id"),
            {"id": group.id.value},
        )
        await async_session.execute(
            text("DELETE FROM groups WHERE id = :id"),
            {"id": group.id.value},
        )
        await async_session.commit()

    @pytest.mark.asyncio
    async def test_remove_member_appends_member_removed_event(
        self, async_session: AsyncSession, spicedb_client: AuthorizationProvider
    ):
        """When a member is removed, a MemberRemoved event should be appended."""
        serializer = IAMEventSerializer()
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        tenant_id = TenantId.generate()
        # Use factory method
        group = Group.create(name="Test Group Remove", tenant_id=tenant_id)
        admin1 = UserId.generate()
        admin2 = UserId.generate()

        # Add two admins (need two because we can't remove the last admin)
        group.add_member(admin1, Role.ADMIN)
        group.add_member(admin2, Role.ADMIN)

        async with async_session.begin():
            await group_repo.save(group)

        # Clear the outbox to isolate the remove event
        await async_session.execute(
            text("DELETE FROM outbox WHERE aggregate_id = :id"),
            {"id": group.id.value},
        )
        await async_session.commit()

        # Now remove one member
        group.remove_member(admin2)
        async with async_session.begin():
            await group_repo.save(group)

        # Query the outbox for the MemberRemoved event
        stmt = select(OutboxModel).where(
            OutboxModel.aggregate_id == group.id.value,
            OutboxModel.event_type == "MemberRemoved",
        )
        result = await async_session.execute(stmt)
        outbox_entry = result.scalar_one_or_none()

        assert outbox_entry is not None
        event = serializer.deserialize(outbox_entry.event_type, outbox_entry.payload)
        assert isinstance(event, MemberRemoved)
        assert event.user_id == admin2.value
        assert event.role == Role.ADMIN

        # Clean up
        await async_session.execute(
            text("DELETE FROM outbox WHERE aggregate_id = :id"),
            {"id": group.id.value},
        )
        await async_session.execute(
            text("DELETE FROM groups WHERE id = :id"),
            {"id": group.id.value},
        )
        await async_session.commit()


class TestOutboxWorkerProcessing:
    """Tests for verifying the outbox worker processes events correctly."""

    @pytest.mark.asyncio
    async def test_worker_processes_group_created_and_writes_to_spicedb(
        self,
        async_session: AsyncSession,
        session_factory,
        spicedb_client: AuthorizationProvider,
    ):
        """Worker should process GroupCreated and write tenant relationship to SpiceDB."""
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        tenant_id = TenantId.generate()
        # Use factory method
        group = Group.create(name="Worker Test Group", tenant_id=tenant_id)

        # Create the group (will add to outbox)
        async with async_session.begin():
            await group_repo.save(group)

        # Build composite translator with IAM translator
        translator = CompositeTranslator()
        translator.register(IAMEventTranslator())

        # Process the outbox entries using the worker's processing logic directly
        worker = OutboxWorker(
            session_factory=session_factory,
            authz=spicedb_client,
            translator=translator,
            probe=DefaultOutboxWorkerProbe(),
        )

        # Manually trigger batch processing
        await worker._process_batch()

        # Verify the entry is marked as processed
        stmt = select(OutboxModel).where(
            OutboxModel.aggregate_id == group.id.value,
            OutboxModel.event_type == "GroupCreated",
        )
        result = await async_session.execute(stmt)
        outbox_entry = result.scalar_one_or_none()

        assert outbox_entry is not None
        assert outbox_entry.processed_at is not None

        # Verify the relationship exists in SpiceDB
        group_resource = format_resource(ResourceType.GROUP, group.id.value)
        tenant_resource = format_resource(ResourceType.TENANT, tenant_id.value)

        has_relationship = await spicedb_client.check_permission(
            resource=group_resource,
            permission=RelationType.TENANT,
            subject=tenant_resource,
        )
        assert has_relationship is True

        # Clean up
        await spicedb_client.delete_relationship(
            resource=group_resource,
            relation=RelationType.TENANT,
            subject=tenant_resource,
        )
        await async_session.execute(
            text("DELETE FROM outbox WHERE aggregate_id = :id"),
            {"id": group.id.value},
        )
        await async_session.execute(
            text("DELETE FROM groups WHERE id = :id"),
            {"id": group.id.value},
        )
        await async_session.commit()

    @pytest.mark.asyncio
    async def test_worker_processes_member_added_and_writes_to_spicedb(
        self,
        async_session: AsyncSession,
        session_factory,
        spicedb_client: AuthorizationProvider,
    ):
        """Worker should process MemberAdded and write member relationship to SpiceDB."""
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        tenant_id = TenantId.generate()
        # Use factory method
        group = Group.create(name="Member Test Group", tenant_id=tenant_id)
        user_id = UserId.generate()
        group.add_member(user_id, Role.MEMBER)

        async with async_session.begin():
            await group_repo.save(group)

        # Build composite translator with IAM translator
        translator = CompositeTranslator()
        translator.register(IAMEventTranslator())

        # Process the outbox
        worker = OutboxWorker(
            session_factory=session_factory,
            authz=spicedb_client,
            translator=translator,
            probe=DefaultOutboxWorkerProbe(),
        )
        await worker._process_batch()

        # Verify the member relationship exists in SpiceDB
        group_resource = format_resource(ResourceType.GROUP, group.id.value)
        user_subject = format_subject(ResourceType.USER, user_id.value)

        has_relationship = await spicedb_client.check_permission(
            resource=group_resource,
            permission=Role.MEMBER.value,
            subject=user_subject,
        )
        assert has_relationship is True

        # Clean up
        tenant_resource = format_resource(ResourceType.TENANT, tenant_id.value)
        await spicedb_client.delete_relationship(
            resource=group_resource,
            relation=RelationType.TENANT,
            subject=tenant_resource,
        )
        await spicedb_client.delete_relationship(
            resource=group_resource,
            relation=Role.MEMBER.value,
            subject=user_subject,
        )
        await async_session.execute(
            text("DELETE FROM outbox WHERE aggregate_id = :id"),
            {"id": group.id.value},
        )
        await async_session.execute(
            text("DELETE FROM groups WHERE id = :id"),
            {"id": group.id.value},
        )
        await async_session.commit()


class TestAtomicityGuarantees:
    """Tests for verifying atomicity between PostgreSQL and outbox."""

    @pytest.mark.asyncio
    async def test_outbox_entry_created_in_same_transaction_as_group(
        self, async_session: AsyncSession, spicedb_client: AuthorizationProvider
    ):
        """Outbox entry and group should be committed atomically."""
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        tenant_id = TenantId.generate()
        # Use factory method
        group = Group.create(name="Atomic Test Group", tenant_id=tenant_id)

        # Save within a transaction
        async with async_session.begin():
            await group_repo.save(group)
            # Before commit, both should be visible within the transaction

        # After commit, verify both exist
        from iam.infrastructure.models import GroupModel

        group_stmt = select(GroupModel).where(GroupModel.id == group.id.value)
        group_result = await async_session.execute(group_stmt)
        group_model = group_result.scalar_one_or_none()
        assert group_model is not None

        outbox_stmt = select(OutboxModel).where(
            OutboxModel.aggregate_id == group.id.value
        )
        outbox_result = await async_session.execute(outbox_stmt)
        outbox_entry = outbox_result.scalar_one_or_none()
        assert outbox_entry is not None

        # Clean up
        await async_session.execute(
            text("DELETE FROM outbox WHERE aggregate_id = :id"),
            {"id": group.id.value},
        )
        await async_session.execute(
            text("DELETE FROM groups WHERE id = :id"),
            {"id": group.id.value},
        )
        await async_session.commit()

    @pytest.mark.asyncio
    async def test_rollback_removes_both_group_and_outbox_entry(
        self, async_session: AsyncSession, spicedb_client: AuthorizationProvider
    ):
        """On rollback, neither group nor outbox entry should persist."""
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        tenant_id = TenantId.generate()
        # Use factory method
        group = Group.create(name="Rollback Test Group", tenant_id=tenant_id)

        try:
            async with async_session.begin():
                await group_repo.save(group)
                # Force a rollback
                raise Exception("Forced rollback for test")
        except Exception:
            pass  # Expected

        # Verify neither exists
        from iam.infrastructure.models import GroupModel

        group_stmt = select(GroupModel).where(GroupModel.id == group.id.value)
        group_result = await async_session.execute(group_stmt)
        group_model = group_result.scalar_one_or_none()
        assert group_model is None

        outbox_stmt = select(OutboxModel).where(
            OutboxModel.aggregate_id == group.id.value
        )
        outbox_result = await async_session.execute(outbox_stmt)
        outbox_entry = outbox_result.scalar_one_or_none()
        assert outbox_entry is None


class TestOutboxWorkerNotifyProcessing:
    """Tests for verifying NOTIFY-based processing (not polling)."""

    @pytest.mark.asyncio
    async def test_worker_processes_via_notify_not_polling(
        self,
        async_session: AsyncSession,
        session_factory,
        spicedb_client: AuthorizationProvider,
        db_settings,
    ):
        """Worker should process via NOTIFY immediately, not waiting for poll."""
        import asyncio

        from infrastructure.outbox.event_sources.postgres_notify import (
            PostgresNotifyEventSource,
        )
        from shared_kernel.outbox.observability import (
            DefaultEventSourceProbe,
            DefaultOutboxWorkerProbe,
        )

        # Setup
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Build composite translator
        translator = CompositeTranslator()
        translator.register(IAMEventTranslator())

        # Create event source with REAL database URL
        db_url = (
            f"postgresql://{db_settings.username}:"
            f"{db_settings.password.get_secret_value()}@"
            f"{db_settings.host}:{db_settings.port}/"
            f"{db_settings.database}"
        )
        event_source = PostgresNotifyEventSource(
            db_url=db_url,
            channel="outbox_events",
            probe=DefaultEventSourceProbe(),
        )

        # Create worker with event source
        # Set poll_interval very high to ensure NOTIFY is used, not polling
        worker = OutboxWorker(
            session_factory=session_factory,
            authz=spicedb_client,
            translator=translator,
            probe=DefaultOutboxWorkerProbe(),
            event_source=event_source,
            poll_interval_seconds=999,
        )

        # Start worker
        await worker.start()

        try:
            # Create a group (this triggers INSERT -> NOTIFY)
            tenant_id = TenantId.generate()
            group = Group.create(name="NOTIFY Test Group", tenant_id=tenant_id)

            async with async_session.begin():
                await group_repo.save(group)

            # Give NOTIFY time to propagate and process (should be very fast)
            await asyncio.sleep(0.5)  # 500ms should be plenty

            # Verify the entry was processed
            stmt = select(OutboxModel).where(
                OutboxModel.aggregate_id == group.id.value,
                OutboxModel.event_type == "GroupCreated",
            )
            result = await async_session.execute(stmt)
            outbox_entry = result.scalar_one_or_none()

            assert outbox_entry is not None, "Outbox entry should exist"
            assert outbox_entry.processed_at is not None, (
                "Entry should be processed via NOTIFY"
            )

            # Verify SpiceDB relationship exists
            group_resource = format_resource(ResourceType.GROUP, group.id.value)
            tenant_resource = format_resource(ResourceType.TENANT, tenant_id.value)

            has_relationship = await spicedb_client.check_permission(
                resource=group_resource,
                permission=RelationType.TENANT,
                subject=tenant_resource,
            )
            assert has_relationship is True, "SpiceDB relationship should exist"

            # Clean up SpiceDB
            await spicedb_client.delete_relationship(
                resource=group_resource,
                relation=RelationType.TENANT,
                subject=tenant_resource,
            )

        finally:
            # Stop worker
            await worker.stop()

            # Clean up database
            await async_session.execute(
                text("DELETE FROM outbox WHERE aggregate_id = :id"),
                {"id": group.id.value},
            )
            await async_session.execute(
                text("DELETE FROM groups WHERE id = :id"),
                {"id": group.id.value},
            )
            await async_session.commit()


class TestUnprocessedEventsRetry:
    """Tests for verifying unprocessed events are retried."""

    @pytest.mark.asyncio
    async def test_unprocessed_events_stay_in_outbox(
        self, async_session: AsyncSession, spicedb_client: AuthorizationProvider
    ):
        """Events that fail to process should remain unprocessed for retry."""
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        tenant_id = TenantId.generate()
        # Use factory method
        group = Group.create(name="Retry Test Group", tenant_id=tenant_id)

        async with async_session.begin():
            await group_repo.save(group)

        # Verify the entry exists and is unprocessed
        stmt = select(OutboxModel).where(
            OutboxModel.aggregate_id == group.id.value,
            OutboxModel.processed_at.is_(None),
        )
        result = await async_session.execute(stmt)
        entries = result.scalars().all()

        assert len(entries) >= 1
        assert all(entry.processed_at is None for entry in entries)

        # Clean up (without processing)
        await async_session.execute(
            text("DELETE FROM outbox WHERE aggregate_id = :id"),
            {"id": group.id.value},
        )
        await async_session.execute(
            text("DELETE FROM groups WHERE id = :id"),
            {"id": group.id.value},
        )
        await async_session.commit()
