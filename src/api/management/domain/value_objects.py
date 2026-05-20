"""Value objects for Management domain.

Value objects are immutable descriptors that provide type safety and
domain semantics for identifiers and domain concepts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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


class WorkspaceMode(StrEnum):
    """Lifecycle mode of a knowledge-graph workspace."""

    SCHEMA_BOOTSTRAP = "schema_bootstrap"
    EXTRACTION_OPERATIONS = "extraction_operations"


@dataclass(frozen=True)
class WorkspaceReadinessStatus:
    """Readiness flags used to determine bootstrap transition eligibility."""

    has_minimum_entity_types: bool
    has_minimum_relationship_types: bool
    prepopulated_types_ready: bool
    prepopulated_types_without_instances: tuple[str, ...] = field(default_factory=tuple)
    blocking_reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_ready(self) -> bool:
        """Return true when all readiness checks pass."""
        return (
            self.has_minimum_entity_types
            and self.has_minimum_relationship_types
            and self.prepopulated_types_ready
            and not self.prepopulated_types_without_instances
        )


@dataclass(frozen=True)
class WorkspaceSessionPointers:
    """Session pointers projected for workspace status UIs."""

    active_schema_bootstrap_session_id: str | None = None
    active_extraction_operations_session_id: str | None = None
    most_recent_completed_session_id: str | None = None


@dataclass(frozen=True)
class KnowledgeGraphWorkspaceStatus:
    """Workspace status projection for a knowledge graph."""

    knowledge_graph_id: str
    workspace_mode: WorkspaceMode
    readiness: WorkspaceReadinessStatus
    transition_eligible: bool
    session_pointers: WorkspaceSessionPointers


class KnowledgeGraphMaintenanceRunOutcome(StrEnum):
    """Allowed outcomes for a KG-scoped maintenance orchestration attempt."""

    STARTED = "started"
    NO_CHANGES = "no-changes"
    PREFLIGHT_FAILED = "preflight-failed"
    LAUNCH_FAILED = "launch-failed"


@dataclass(frozen=True)
class KnowledgeGraphMaintenanceSchedule:
    """Knowledge-graph level maintenance schedule configuration."""

    enabled: bool
    cron_expression: str
    timezone_name: str
    next_run_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return {
            "enabled": self.enabled,
            "cron_expression": self.cron_expression,
            "timezone_name": self.timezone_name,
            "next_run_at": (
                self.next_run_at.isoformat() if self.next_run_at is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeGraphMaintenanceSchedule":
        """Reconstruct schedule from persisted JSON dictionary."""
        next_run_at_raw = data.get("next_run_at")
        next_run_at = (
            datetime.fromisoformat(str(next_run_at_raw))
            if next_run_at_raw is not None
            else None
        )
        return cls(
            enabled=bool(data.get("enabled", False)),
            cron_expression=str(data.get("cron_expression", "0 2 * * *")),
            timezone_name=str(data.get("timezone_name", "UTC")),
            next_run_at=next_run_at,
        )


@dataclass(frozen=True)
class KnowledgeGraphMaintenanceRunRecord:
    """Immutable audit record for a KG maintenance orchestration attempt."""

    run_id: str
    triggered_at: datetime
    outcome: KnowledgeGraphMaintenanceRunOutcome
    message: str | None = None
    target_data_source_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return {
            "run_id": self.run_id,
            "triggered_at": self.triggered_at.isoformat(),
            "outcome": self.outcome.value,
            "message": self.message,
            "target_data_source_ids": list(self.target_data_source_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeGraphMaintenanceRunRecord":
        """Reconstruct a run record from persisted JSON dictionary."""
        return cls(
            run_id=str(data["run_id"]),
            triggered_at=datetime.fromisoformat(str(data["triggered_at"])),
            outcome=KnowledgeGraphMaintenanceRunOutcome(str(data["outcome"])),
            message=(str(data["message"]) if data.get("message") is not None else None),
            target_data_source_ids=tuple(
                str(ds_id) for ds_id in data.get("target_data_source_ids", [])
            ),
        )


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


# ---------------------------------------------------------------------------
# Typed ontology value objects (used by KnowledgeGraph ontology API)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NodeTypeDefinition:
    """Defines a node type in an ontology.

    A node type describes a category of entities in the knowledge graph.
    The label must be non-empty. Properties are stored as immutable tuples
    to preserve value-object semantics.

    Attributes:
        label: Unique name for this node type (required, non-empty)
        description: Human-readable explanation of this node type
        required_properties: Properties that every node of this type must have
        optional_properties: Properties that nodes of this type may have
    """

    label: str
    description: str = ""
    required_properties: tuple[str, ...] = field(default_factory=tuple)
    optional_properties: tuple[str, ...] = field(default_factory=tuple)
    prepopulated: bool = False
    prepopulated_instance_count: int = 0

    def __post_init__(self) -> None:
        """Validate that label is non-empty."""
        if not self.label or not self.label.strip():
            raise ValueError("NodeTypeDefinition label must not be empty")
        if self.prepopulated_instance_count < 0:
            raise ValueError("prepopulated_instance_count must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict suitable for JSON persistence."""
        return {
            "label": self.label,
            "description": self.description,
            "required_properties": list(self.required_properties),
            "optional_properties": list(self.optional_properties),
            "prepopulated": self.prepopulated,
            "prepopulated_instance_count": self.prepopulated_instance_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeTypeDefinition:
        """Deserialize from a plain dict."""
        return cls(
            label=data["label"],
            description=data.get("description", ""),
            required_properties=tuple(data.get("required_properties", [])),
            optional_properties=tuple(data.get("optional_properties", [])),
            prepopulated=bool(data.get("prepopulated", False)),
            prepopulated_instance_count=int(data.get("prepopulated_instance_count", 0)),
        )


@dataclass(frozen=True)
class EdgeTypeDefinition:
    """Defines a relationship (edge) type in an ontology.

    An edge type describes a kind of relationship between node types.
    The label must be non-empty. All list-like fields are stored as
    immutable tuples to preserve value-object semantics.

    Attributes:
        label: Unique name for this edge type (required, non-empty)
        description: Human-readable explanation of this relationship
        source_labels: Node type labels that may be sources of this edge
        target_labels: Node type labels that may be targets of this edge
        properties: Properties that this edge type may carry
    """

    label: str
    description: str = ""
    source_labels: tuple[str, ...] = field(default_factory=tuple)
    target_labels: tuple[str, ...] = field(default_factory=tuple)
    properties: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate that label is non-empty."""
        if not self.label or not self.label.strip():
            raise ValueError("EdgeTypeDefinition label must not be empty")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict suitable for JSON persistence."""
        return {
            "label": self.label,
            "description": self.description,
            "source_labels": list(self.source_labels),
            "target_labels": list(self.target_labels),
            "properties": list(self.properties),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EdgeTypeDefinition:
        """Deserialize from a plain dict."""
        return cls(
            label=data["label"],
            description=data.get("description", ""),
            source_labels=tuple(data.get("source_labels", [])),
            target_labels=tuple(data.get("target_labels", [])),
            properties=tuple(data.get("properties", [])),
        )


@dataclass(frozen=True)
class OntologyConfig:
    """Configuration for an ontology associated with a KnowledgeGraph.

    Represents the full ontology proposal or approved schema for a KG.
    Immutable value object — use KnowledgeGraph.set_ontology() to attach
    a new config to a knowledge graph.

    Attributes:
        node_types: Tuple of NodeTypeDefinition value objects
        edge_types: Tuple of EdgeTypeDefinition value objects
        approved_at: When the user approved this ontology; None if not yet approved
    """

    node_types: tuple[NodeTypeDefinition, ...] = field(default_factory=tuple)
    edge_types: tuple[EdgeTypeDefinition, ...] = field(default_factory=tuple)
    approved_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict suitable for JSONB persistence."""
        return {
            "node_types": [nt.to_dict() for nt in self.node_types],
            "edge_types": [et.to_dict() for et in self.edge_types],
            "approved_at": (
                self.approved_at.isoformat() if self.approved_at is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OntologyConfig:
        """Deserialize from a plain dict (e.g. loaded from JSONB column)."""
        approved_at: datetime | None = None
        raw_approved_at = data.get("approved_at")
        if raw_approved_at is not None:
            approved_at = datetime.fromisoformat(str(raw_approved_at))

        return cls(
            node_types=tuple(
                NodeTypeDefinition.from_dict(nt) for nt in data.get("node_types", [])
            ),
            edge_types=tuple(
                EdgeTypeDefinition.from_dict(et) for et in data.get("edge_types", [])
            ),
            approved_at=approved_at,
        )
