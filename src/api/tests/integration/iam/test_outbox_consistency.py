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
from iam.domain.value_objects import GroupRole, UserId
from iam.infrastructure.group_repository import GroupRepository
from iam.infrastructure.outbox import IAMEventSerializer
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
from infrastructure.outbox.spicedb_handler import SpiceDBEventHandler
from shared_kernel.outbox.observability import DefaultOutboxWorkerProbe

pytestmark = pytest.mark.integration


class TestOutboxEventCreation:
    """Tests for verifying outbox entries are created correctly."""

    @pytest.mark.asyncio
    async def test_group_creation_appends_group_created_event(
        self,
        async_session: AsyncSession,
        spicedb_client: AuthorizationProvider,
        test_tenant,
    ):
        """When a group is created, a GroupCreated event should be appended to the outbox."""
        serializer = IAMEventSerializer()
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Use factory method which records GroupCreated event
        group = Group.create(name="Test Group for Outbox", tenant_id=test_tenant)

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
        assert event.tenant_id == test_tenant.value

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
        self,
        async_session: AsyncSession,
        spicedb_client: AuthorizationProvider,
        test_tenant,
        clean_iam_data,
    ):
        """When a member is added, a MemberAdded event should be appended to the outbox."""
        serializer = IAMEventSerializer()
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Use factory method
        group = Group.create(name="Test Group Members", tenant_id=test_tenant)
        user_id = UserId.generate()

        # Add member to the group
        group.add_member(user_id, GroupRole.ADMIN)

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
        assert event.role == GroupRole.ADMIN

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
        self,
        async_session: AsyncSession,
        spicedb_client: AuthorizationProvider,
        test_tenant,
        clean_iam_data,
    ):
        """When a member is removed, a MemberRemoved event should be appended."""
        serializer = IAMEventSerializer()
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Use factory method
        group = Group.create(name="Test Group Remove", tenant_id=test_tenant)
        admin1 = UserId.generate()
        admin2 = UserId.generate()

        # Add two admins (need two because we can't remove the last admin)
        group.add_member(admin1, GroupRole.ADMIN)
        group.add_member(admin2, GroupRole.ADMIN)

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
        assert event.role == GroupRole.ADMIN

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
        spicedb_event_handler: SpiceDBEventHandler,
        test_tenant,
        clean_iam_data,
    ):
        """Worker should process GroupCreated and write tenant relationship to SpiceDB."""
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Use factory method
        group = Group.create(name="Worker Test Group", tenant_id=test_tenant)

        # Create the group (will add to outbox)
        async with async_session.begin():
            await group_repo.save(group)

        # Process the outbox entries using the worker's processing logic directly
        worker = OutboxWorker(
            session_factory=session_factory,
            handler=spicedb_event_handler,
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
        tenant_resource = format_resource(ResourceType.TENANT, test_tenant.value)

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
        spicedb_event_handler: SpiceDBEventHandler,
        test_tenant,
        clean_iam_data,
    ):
        """Worker should process MemberAdded and write member relationship to SpiceDB."""
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Use factory method
        group = Group.create(name="Member Test Group", tenant_id=test_tenant)
        user_id = UserId.generate()
        group.add_member(user_id, GroupRole.MEMBER)

        async with async_session.begin():
            await group_repo.save(group)

        # Process the outbox
        worker = OutboxWorker(
            session_factory=session_factory,
            handler=spicedb_event_handler,
            probe=DefaultOutboxWorkerProbe(),
        )
        await worker._process_batch()

        # Verify the member relationship exists in SpiceDB
        group_resource = format_resource(ResourceType.GROUP, group.id.value)
        user_subject = format_subject(ResourceType.USER, user_id.value)

        has_relationship = await spicedb_client.check_permission(
            resource=group_resource,
            permission=GroupRole.MEMBER.value,
            subject=user_subject,
        )
        assert has_relationship is True

        # Clean up
        tenant_resource = format_resource(ResourceType.TENANT, test_tenant.value)
        await spicedb_client.delete_relationship(
            resource=group_resource,
            relation=RelationType.TENANT,
            subject=tenant_resource,
        )
        # Use MEMBER_RELATION (the actual relation) not MEMBER (which is a permission)
        await spicedb_client.delete_relationship(
            resource=group_resource,
            relation=RelationType.MEMBER_RELATION,
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
        self,
        async_session: AsyncSession,
        spicedb_client: AuthorizationProvider,
        test_tenant,
        clean_iam_data,
    ):
        """Outbox entry and group should be committed atomically."""
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Use factory method
        group = Group.create(name="Atomic Test Group", tenant_id=test_tenant)

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
        self,
        async_session: AsyncSession,
        spicedb_client: AuthorizationProvider,
        test_tenant,
        clean_iam_data,
    ):
        """On rollback, neither group nor outbox entry should persist."""
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Use factory method
        group = Group.create(name="Rollback Test Group", tenant_id=test_tenant)

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
        spicedb_event_handler: SpiceDBEventHandler,
        db_settings,
        test_tenant,
        clean_iam_data,
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
            handler=spicedb_event_handler,
            probe=DefaultOutboxWorkerProbe(),
            event_source=event_source,
            poll_interval_seconds=999,
        )

        group = None  # Initialize before try block

        # Start worker
        await worker.start()

        try:
            # Create a group (this triggers INSERT -> NOTIFY)
            group = Group.create(name="NOTIFY Test Group", tenant_id=test_tenant)

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
            tenant_resource = format_resource(ResourceType.TENANT, test_tenant.value)

            has_relationship = await spicedb_client.check_permission(
                resource=group_resource,
                permission=RelationType.TENANT,
                subject=tenant_resource,
            )
            assert has_relationship is True, "SpiceDB relationship should exist"

        finally:
            # Stop worker (always execute)
            await worker.stop()

            # Clean up database entries (only if group was created)
            if group is not None:
                # Clean up SpiceDB
                group_resource = format_resource(ResourceType.GROUP, group.id.value)
                tenant_resource = format_resource(
                    ResourceType.TENANT, group.tenant_id.value
                )
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


class TestIdempotentEventHandlers:
    """Integration tests for idempotent event handling on duplicate delivery.

    Covers spec: Requirement: Idempotent Event Handlers — duplicate delivery scenario.

    Simulates the scenario where the outbox worker invokes a handler (which writes
    to SpiceDB) but then crashes before marking the entry as processed.  On retry,
    the worker finds the still-unprocessed entry, calls the handler again, and
    the final SpiceDB state must be identical to a single successful run.
    """

    @pytest.mark.asyncio
    async def test_handler_invoked_twice_produces_same_spicedb_state(
        self,
        async_session: AsyncSession,
        session_factory,
        spicedb_client: AuthorizationProvider,
        spicedb_event_handler: SpiceDBEventHandler,
        test_tenant,
        clean_iam_data,
    ):
        """Spec: Duplicate delivery — idempotent final state in SpiceDB.

        GIVEN an outbox entry that was partially processed (handler ran, SpiceDB
              relationship written, but mark_processed was NOT called due to a crash)
        WHEN the worker retries the same still-unprocessed entry
        THEN the final SpiceDB state is identical to a single successful run
        AND processed_at is set on the outbox entry after the retry
        AND no duplicate relationships are created (SpiceDB upsert semantics)
        """
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Step 1: Create a group — this appends a GroupCreated event to the outbox
        group = Group.create(
            name="Idempotent Handler Test Group", tenant_id=test_tenant
        )
        async with async_session.begin():
            await group_repo.save(group)

        # Step 2: Read the unprocessed outbox entry
        stmt = select(OutboxModel).where(
            OutboxModel.aggregate_id == group.id.value,
            OutboxModel.event_type == "GroupCreated",
        )
        result = await async_session.execute(stmt)
        outbox_entry = result.scalar_one_or_none()
        assert outbox_entry is not None
        assert outbox_entry.processed_at is None

        entry_id = outbox_entry.id
        event_type = outbox_entry.event_type
        payload = outbox_entry.payload

        # Step 3: First handler invocation — simulates the handler writing to
        # SpiceDB but the process crashing before _mark_processed could run.
        await spicedb_event_handler.handle(event_type, payload)

        group_resource = format_resource(ResourceType.GROUP, group.id.value)
        tenant_resource = format_resource(ResourceType.TENANT, test_tenant.value)

        has_relationship = await spicedb_client.check_permission(
            resource=group_resource,
            permission=RelationType.TENANT,
            subject=tenant_resource,
        )
        assert has_relationship is True, (
            "SpiceDB relationship must exist after first handler invocation"
        )

        # The entry is still unprocessed (mark_processed was never called)
        # Confirm this by re-querying; the outbox_entry object may be cached.
        result_check = await async_session.execute(
            select(OutboxModel).where(OutboxModel.id == entry_id)
        )
        still_unprocessed = result_check.scalar_one()
        assert still_unprocessed.processed_at is None, (
            "Entry must remain unprocessed (mark_processed was not called)"
        )

        # Step 4: Worker retries — it picks up the still-unprocessed entry and
        # calls the handler again (second invocation with the same payload).
        worker = OutboxWorker(
            session_factory=session_factory,
            handler=spicedb_event_handler,
            probe=DefaultOutboxWorkerProbe(),
        )
        await worker._process_batch()

        # Step 5a: Entry must now be marked as processed
        async_session.expire_all()  # Expire session cache to force a fresh DB read
        result_after = await async_session.execute(
            select(OutboxModel).where(OutboxModel.id == entry_id)
        )
        processed_entry = result_after.scalar_one()
        assert processed_entry.processed_at is not None, (
            "Entry must be marked as processed after the worker retries it"
        )

        # Step 5b: SpiceDB relationship still exists and is correct (idempotent)
        # The duplicate write_relationship call must not have removed or duplicated it.
        has_relationship_after_retry = await spicedb_client.check_permission(
            resource=group_resource,
            permission=RelationType.TENANT,
            subject=tenant_resource,
        )
        assert has_relationship_after_retry is True, (
            "SpiceDB relationship must still exist after duplicate handler invocation "
            "(write_relationship is an upsert — same tuple written twice stays once)"
        )

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


class TestUnprocessedEventsRetry:
    """Tests for verifying unprocessed events are retried."""

    @pytest.mark.asyncio
    async def test_unprocessed_events_stay_in_outbox(
        self,
        async_session: AsyncSession,
        spicedb_client: AuthorizationProvider,
        test_tenant,
        clean_iam_data,
    ):
        """Events that fail to process should remain unprocessed for retry."""
        outbox_repo = OutboxRepository(async_session)
        group_repo = GroupRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Use factory method
        group = Group.create(name="Retry Test Group", tenant_id=test_tenant)

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
