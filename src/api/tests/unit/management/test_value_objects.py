"""Unit tests for Management domain value objects."""

from __future__ import annotations

import pytest
from ulid import ULID

from management.domain.exceptions import InvalidScheduleError
from management.domain.value_objects import (
    BaseId,
    DataSourceId,
    KnowledgeGraphId,
    Schedule,
    ScheduleType,
)


class TestKnowledgeGraphId:
    """Tests for KnowledgeGraphId value object."""

    def test_generate_creates_valid_ulid(self):
        """generate() should produce a valid ULID string."""
        kg_id = KnowledgeGraphId.generate()
        assert isinstance(kg_id.value, str)
        # Should not raise
        ULID.from_str(kg_id.value)

    def test_generate_creates_unique_ids(self):
        """Each call to generate() should produce a unique ID."""
        ids = {KnowledgeGraphId.generate().value for _ in range(100)}
        assert len(ids) == 100

    def test_from_string_roundtrips(self):
        """from_string(id.value) should reconstruct the same ID."""
        original = KnowledgeGraphId.generate()
        restored = KnowledgeGraphId.from_string(original.value)
        assert restored == original
        assert restored.value == original.value

    def test_from_string_rejects_invalid_ulid(self):
        """from_string() should raise ValueError for non-ULID strings."""
        with pytest.raises(ValueError, match="Invalid KnowledgeGraphId"):
            KnowledgeGraphId.from_string("not-a-ulid")

    def test_str_returns_value(self):
        """str() should return the raw ULID string."""
        kg_id = KnowledgeGraphId.generate()
        assert str(kg_id) == kg_id.value

    def test_is_frozen(self):
        """KnowledgeGraphId should be immutable."""
        kg_id = KnowledgeGraphId.generate()
        with pytest.raises(AttributeError):
            kg_id.value = "something"

    def test_equality_by_value(self):
        """Two IDs with the same value should be equal."""
        value = str(ULID())
        id1 = KnowledgeGraphId(value=value)
        id2 = KnowledgeGraphId(value=value)
        assert id1 == id2

    def test_inequality_different_values(self):
        """Two IDs with different values should not be equal."""
        id1 = KnowledgeGraphId.generate()
        id2 = KnowledgeGraphId.generate()
        assert id1 != id2

    def test_is_subclass_of_base_id(self):
        """KnowledgeGraphId should extend BaseId."""
        assert issubclass(KnowledgeGraphId, BaseId)


class TestDataSourceId:
    """Tests for DataSourceId value object."""

    def test_generate_creates_valid_ulid(self):
        """generate() should produce a valid ULID string."""
        ds_id = DataSourceId.generate()
        assert isinstance(ds_id.value, str)
        ULID.from_str(ds_id.value)

    def test_generate_creates_unique_ids(self):
        """Each call to generate() should produce a unique ID."""
        ids = {DataSourceId.generate().value for _ in range(100)}
        assert len(ids) == 100

    def test_from_string_roundtrips(self):
        """from_string(id.value) should reconstruct the same ID."""
        original = DataSourceId.generate()
        restored = DataSourceId.from_string(original.value)
        assert restored == original

    def test_from_string_rejects_invalid_ulid(self):
        """from_string() should raise ValueError for non-ULID strings."""
        with pytest.raises(ValueError, match="Invalid DataSourceId"):
            DataSourceId.from_string("not-a-ulid")

    def test_str_returns_value(self):
        """str() should return the raw ULID string."""
        ds_id = DataSourceId.generate()
        assert str(ds_id) == ds_id.value

    def test_is_frozen(self):
        """DataSourceId should be immutable."""
        ds_id = DataSourceId.generate()
        with pytest.raises(AttributeError):
            ds_id.value = "something"

    def test_is_subclass_of_base_id(self):
        """DataSourceId should extend BaseId."""
        assert issubclass(DataSourceId, BaseId)


class TestScheduleType:
    """Tests for ScheduleType enum."""

    def test_manual_value(self):
        assert ScheduleType.MANUAL == "manual"
        assert ScheduleType.MANUAL.value == "manual"

    def test_cron_value(self):
        assert ScheduleType.CRON == "cron"
        assert ScheduleType.CRON.value == "cron"

    def test_interval_value(self):
        assert ScheduleType.INTERVAL == "interval"
        assert ScheduleType.INTERVAL.value == "interval"

    def test_is_str_enum(self):
        """ScheduleType members should be usable as strings."""
        assert isinstance(ScheduleType.MANUAL, str)


class TestSchedule:
    """Tests for Schedule value object."""

    def test_manual_schedule_without_value(self):
        """MANUAL schedule with no value should be valid."""
        schedule = Schedule(schedule_type=ScheduleType.MANUAL)
        assert schedule.schedule_type == ScheduleType.MANUAL
        assert schedule.value is None

    def test_cron_schedule_with_value(self):
        """CRON schedule with a cron expression should be valid."""
        schedule = Schedule(schedule_type=ScheduleType.CRON, value="0 * * * *")
        assert schedule.schedule_type == ScheduleType.CRON
        assert schedule.value == "0 * * * *"

    def test_interval_schedule_with_value(self):
        """INTERVAL schedule with an interval expression should be valid."""
        schedule = Schedule(schedule_type=ScheduleType.INTERVAL, value="PT1H")
        assert schedule.schedule_type == ScheduleType.INTERVAL
        assert schedule.value == "PT1H"

    def test_cron_schedule_without_value_raises(self):
        """CRON schedule without a value should raise InvalidScheduleError."""
        with pytest.raises(
            InvalidScheduleError, match="cron schedule requires a value"
        ):
            Schedule(schedule_type=ScheduleType.CRON)

    def test_cron_schedule_with_empty_string_raises(self):
        """CRON schedule with empty string should raise InvalidScheduleError."""
        with pytest.raises(
            InvalidScheduleError, match="cron schedule requires a value"
        ):
            Schedule(schedule_type=ScheduleType.CRON, value="")

    def test_interval_schedule_without_value_raises(self):
        """INTERVAL schedule without a value should raise InvalidScheduleError."""
        with pytest.raises(
            InvalidScheduleError, match="interval schedule requires a value"
        ):
            Schedule(schedule_type=ScheduleType.INTERVAL)

    def test_interval_schedule_with_empty_string_raises(self):
        """INTERVAL schedule with empty string should raise InvalidScheduleError."""
        with pytest.raises(
            InvalidScheduleError, match="interval schedule requires a value"
        ):
            Schedule(schedule_type=ScheduleType.INTERVAL, value="")

    def test_manual_schedule_with_value_raises(self):
        """MANUAL schedule with a value should raise InvalidScheduleError."""
        with pytest.raises(
            InvalidScheduleError, match="MANUAL schedule must not have a value"
        ):
            Schedule(schedule_type=ScheduleType.MANUAL, value="0 * * * *")

    def test_manual_schedule_with_empty_string_normalizes_to_none(self):
        """MANUAL schedule with empty string should normalize value to None."""
        schedule = Schedule(schedule_type=ScheduleType.MANUAL, value="")
        assert schedule.value is None

    def test_is_frozen(self):
        """Schedule should be immutable."""
        schedule = Schedule(schedule_type=ScheduleType.MANUAL)
        with pytest.raises(AttributeError):
            schedule.schedule_type = ScheduleType.CRON

    def test_equality(self):
        """Two schedules with same type and value should be equal."""
        s1 = Schedule(schedule_type=ScheduleType.CRON, value="0 * * * *")
        s2 = Schedule(schedule_type=ScheduleType.CRON, value="0 * * * *")
        assert s1 == s2

    def test_inequality_different_type(self):
        """Schedules with different types should not be equal."""
        s1 = Schedule(schedule_type=ScheduleType.MANUAL)
        s2 = Schedule(schedule_type=ScheduleType.CRON, value="0 * * * *")
        assert s1 != s2
