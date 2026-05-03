"""Value objects for Management domain.

Value objects are immutable descriptors that provide type safety and
domain semantics for identifiers and domain concepts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TypeVar

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


@dataclass(frozen=True)
class OntologyNodeType:
    """A node type definition within an ontology.

    Immutable value object representing a single entity class in the graph
    ontology. Describes what kinds of nodes exist, their labels, and which
    properties are expected.

    Attributes:
        label: The type label (e.g. "Repository", "PullRequest")
        description: Optional human-readable description
        required_properties: Property names that must be present on nodes of this type
        optional_properties: Property names that may be present on nodes of this type
    """

    label: str
    description: str | None = None
    required_properties: list[str] = field(default_factory=list)
    optional_properties: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OntologyEdgeType:
    """An edge type definition within an ontology.

    Immutable value object representing a single relationship class in the
    graph ontology. Describes what kinds of edges exist, their labels, and
    which node types they connect.

    Attributes:
        label: The edge label (e.g. "HAS_PR", "CREATED_BY")
        from_type: The source node type label
        to_type: The target node type label
        description: Optional human-readable description
        required_properties: Property names that must be present on edges of this type
        optional_properties: Property names that may be present on edges of this type
    """

    label: str
    from_type: str
    to_type: str
    description: str | None = None
    required_properties: list[str] = field(default_factory=list)
    optional_properties: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Ontology:
    """An approved ontology for a data source.

    Immutable value object aggregating node type and edge type definitions.
    An empty Ontology (no types) is valid — it represents a data source
    that has no approved ontology yet or where all types have been removed.

    Attributes:
        node_types: List of node type definitions
        edge_types: List of edge type definitions
    """

    node_types: list[OntologyNodeType]
    edge_types: list[OntologyEdgeType]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-serializable dictionary for persistence.

        Returns:
            Dictionary with node_types and edge_types lists
        """
        return {
            "node_types": [
                {
                    "label": nt.label,
                    "description": nt.description,
                    "required_properties": list(nt.required_properties),
                    "optional_properties": list(nt.optional_properties),
                }
                for nt in self.node_types
            ],
            "edge_types": [
                {
                    "label": et.label,
                    "from_type": et.from_type,
                    "to_type": et.to_type,
                    "description": et.description,
                    "required_properties": list(et.required_properties),
                    "optional_properties": list(et.optional_properties),
                }
                for et in self.edge_types
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Ontology:
        """Deserialize an Ontology from a dictionary.

        Args:
            data: Dictionary with node_types and edge_types lists

        Returns:
            Reconstructed Ontology value object
        """
        node_types = [
            OntologyNodeType(
                label=nt["label"],
                description=nt.get("description"),
                required_properties=list(nt.get("required_properties", [])),
                optional_properties=list(nt.get("optional_properties", [])),
            )
            for nt in data.get("node_types", [])
        ]
        edge_types = [
            OntologyEdgeType(
                label=et["label"],
                from_type=et["from_type"],
                to_type=et["to_type"],
                description=et.get("description"),
                required_properties=list(et.get("required_properties", [])),
                optional_properties=list(et.get("optional_properties", [])),
            )
            for et in data.get("edge_types", [])
        ]
        return cls(node_types=node_types, edge_types=edge_types)
