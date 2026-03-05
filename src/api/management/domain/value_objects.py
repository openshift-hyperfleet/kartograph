"""Value objects for Management domain.

Value objects are immutable descriptors that provide type safety and
domain semantics for identifiers and domain concepts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from ulid import ULID

from management.domain.exceptions import InvalidScheduleError

# Generic type variable for ID classes
T = TypeVar("T", bound="BaseId")


@dataclass(frozen=True)
class BaseId:
    """Base class for ULID-based identifier value objects.

    Provides common functionality for ID generation and validation.
    Subclasses only need to define their docstrings for specific semantics.
    """

    value: str

    def __str__(self) -> str:
        """Return string representation."""
        return self.value

    @classmethod
    def generate(cls: type[T]) -> T:
        """Generate a new ID using ULID.

        Returns:
            New ID instance with generated ULID
        """
        return cls(value=str(ULID()))

    @classmethod
    def from_string(cls: type[T], value: str) -> T:
        """Create ID from string value.

        Args:
            value: ULID string

        Returns:
            ID instance

        Raises:
            ValueError: If value is not a valid ULID
        """
        try:
            ULID.from_str(value)
        except ValueError as e:
            raise ValueError(f"Invalid {cls.__name__}: {value}") from e

        return cls(value=value)


@dataclass(frozen=True)
class KnowledgeGraphId(BaseId):
    """Identifier for a KnowledgeGraph aggregate.

    Uses ULID for sortability and distribution-friendly generation.
    """

    pass


@dataclass(frozen=True)
class DataSourceId(BaseId):
    """Identifier for a DataSource aggregate.

    Uses ULID for sortability and distribution-friendly generation.
    """

    pass


class ScheduleType(StrEnum):
    """Schedule type for data source synchronization.

    Defines how a data source sync schedule is configured.
    """

    MANUAL = "manual"
    CRON = "cron"
    INTERVAL = "interval"


@dataclass(frozen=True)
class Schedule:
    """Schedule configuration for data source synchronization.

    Immutable value object that defines when a data source should sync.

    Business rules:
    - MANUAL schedules must NOT have a value (value must be None)
    - CRON schedules MUST have a value (the cron expression)
    - INTERVAL schedules MUST have a value (the interval expression, e.g. "PT1H")

    Attributes:
        schedule_type: The type of schedule (MANUAL, CRON, INTERVAL)
        value: The schedule expression (cron string or interval), None for MANUAL
    """

    schedule_type: ScheduleType
    value: str | None = None

    def __post_init__(self) -> None:
        """Validate schedule configuration."""
        if self.schedule_type in (ScheduleType.CRON, ScheduleType.INTERVAL):
            if not self.value:
                raise InvalidScheduleError(
                    f"{self.schedule_type.value} schedule requires a value"
                )
        if self.schedule_type == ScheduleType.MANUAL and self.value is not None:
            if self.value == "":
                # Normalize empty string to None for MANUAL schedules
                object.__setattr__(self, "value", None)
            else:
                raise InvalidScheduleError("MANUAL schedule must not have a value")
