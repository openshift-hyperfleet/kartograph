"""Domain value objects for the Graph bounded context.

These are immutable data structures that represent domain concepts
within the Graph context. They have no identity - equality is based
on their attribute values.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

# Type alias for exploration query results.
# These are dynamic dictionaries returned from arbitrary Cypher queries.
# Keys are column names from the query, values can be nodes, edges,
# scalars, or other AGE data types.
QueryResultRow: TypeAlias = dict[str, Any]

ID_REGEX = r"^[0-9a-z_]+:[0-9a-f]{16}$"


class EntityType(str, Enum):
    """Enum for graph entity types."""

    NODE = "node"
    EDGE = "edge"


class MutationOperationType(str, Enum):
    """Enum for mutation operation types."""

    DEFINE = "DEFINE"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


# System-managed properties
# These are automatically added by the system and should not be tracked as optional properties

# Properties required for ALL entities (nodes and edges)
COMMON_SYSTEM_PROPERTIES: frozenset[str] = frozenset({"data_source_id", "source_path"})

# Node-specific system properties (in addition to common)
NODE_SYSTEM_PROPERTIES: frozenset[str] = frozenset({"slug"})

# Edge-specific system properties (in addition to common)
# Currently empty, but defined for future extensibility
EDGE_SYSTEM_PROPERTIES: frozenset[str] = frozenset()


def get_system_properties_for_entity(entity_type: EntityType) -> frozenset[str]:
    """Get all system properties for a specific entity type.

    System properties are automatically managed by the platform and should not
    be exposed as optional properties in type definitions.

    Args:
        entity_type: EntityType.NODE or EntityType.EDGE

    Returns:
        Frozenset of system property names for the given entity type

    Raises:
        ValueError: If entity_type is not a valid EntityType
    """
    if entity_type == EntityType.NODE:
        return COMMON_SYSTEM_PROPERTIES | NODE_SYSTEM_PROPERTIES
    elif entity_type == EntityType.EDGE:
        return COMMON_SYSTEM_PROPERTIES | EDGE_SYSTEM_PROPERTIES
    else:
        raise ValueError(f"Invalid entity_type: {repr(entity_type)}")


class SchemaLabelsResponse(BaseModel):
    """Response model for schema label list endpoints."""

    labels: list[str] = Field(description="List of type labels")
    count: int = Field(description="Total number of labels")


class NodeRecord(BaseModel):
    """Immutable representation of a graph node.

    This is a domain-level abstraction over the infrastructure's
    Vertex objects, providing a clean interface for domain logic.

    Attributes:
        id: Unique identifier for the node (e.g., "person:alice123")
        label: The node's label/type (e.g., "Person", "Repository")
        properties: Dictionary of node properties
    """

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)


class EdgeRecord(BaseModel):
    """Immutable representation of a graph edge/relationship.

    Attributes:
        id: Unique identifier for the edge
        label: The relationship type (e.g., "KNOWS", "OWNS")
        start_id: ID of the source node
        end_id: ID of the target node
        properties: Dictionary of edge properties
    """

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    start_id: str
    end_id: str
    properties: dict[str, Any] = Field(default_factory=dict)


class TypeDefinition(BaseModel):
    """Domain model for a node or edge type definition.

    Stores metadata about graph entity types (from DEFINE operations).
    This allows validation of CREATE operations against defined schemas.

    Attributes:
        label: The type label (e.g., "Person", "KNOWS")
        entity_type: Whether this is a node or edge type
        description: Plain-text description of this type
        required_properties: Properties that must be present on all instances
        optional_properties: Properties that may be present on instances
    """

    model_config = ConfigDict(frozen=True)

    label: str = Field(description="Type label (must be lowercase)")
    entity_type: EntityType
    description: str
    required_properties: set[str]
    optional_properties: set[str] = Field(default_factory=set)


class MutationOperation(BaseModel):
    """JSONL mutation operation for the Graph bounded context.

    Represents one line in a MutationLog JSONL file from the Extraction context.

    Operation semantics:
    - DEFINE: Declares a node/edge type schema with required/optional properties
    - CREATE: Entity Discovery (idempotent assertion)
        * Semantic: "I discovered this entity with these properties"
        * Behavior: MERGE + accumulate properties (preserves existing unlisted properties)
        * Use case: AI agent discovering entities across multiple files
        * Triggers schema learning for new optional properties
    - UPDATE: Entity Modification (explicit change)
        * Semantic: "Change this specific property value" or "Remove this property"
        * Behavior: MATCH + SET/REMOVE specific fields
        * Use case: Deterministic processor handling renames, corrections, deletions
        * Triggers schema learning for new optional properties in set_properties
        * Can remove properties via remove_properties
    - DELETE: Cascades edges automatically (DETACH DELETE for nodes, DELETE for edges)

    Key distinction: Both CREATE and UPDATE preserve unlisted properties. The difference
    is semantic intent and the ability to REMOVE properties (UPDATE only).

    Attributes:
        op: The operation type
        type: The entity type being mutated (node or edge)
        id: Deterministic ID from Extraction context (format: {type}:{16_hex_chars})
        label: The graph label (required for CREATE and DEFINE)
        start_id: Start node ID (required for CREATE edge)
        end_id: End node ID (required for CREATE edge)
        set_properties: Properties to set/update
        remove_properties: Properties to remove (UPDATE only)
        description: Type description (DEFINE only)
        required_properties: Required property names (DEFINE only)
        optional_properties: Optional property names (DEFINE only)
    """

    model_config = ConfigDict(frozen=True)

    op: MutationOperationType
    type: EntityType
    id: str | None = Field(default=None, pattern=ID_REGEX)

    # CREATE/DEFINE fields
    label: str | None = Field(default=None, description="Type label")

    # CREATE edge fields
    start_id: str | None = Field(default=None, pattern=ID_REGEX)
    end_id: str | None = Field(default=None, pattern=ID_REGEX)

    # CREATE/UPDATE fields
    set_properties: dict[str, Any] | None = None
    remove_properties: list[str] | None = None

    # DEFINE fields
    description: str | None = None
    required_properties: set[str] | None = None
    optional_properties: set[str] | None = None

    def validate_operation(self) -> None:
        """Validate operation-specific requirements.

        Raises:
            ValueError: If operation is invalid or missing required fields
        """
        if self.op == "DEFINE":
            # DEFINE does not require id
            if not all(
                [
                    self.label,
                    self.description,
                    self.required_properties is not None,
                ]
            ):
                raise ValueError(
                    "DEFINE requires 'label', 'description', and 'required_properties'"
                )
            if any(
                [
                    self.set_properties,
                    self.remove_properties,
                    self.start_id,
                    self.end_id,
                ]
            ):
                raise ValueError(
                    "DEFINE cannot include set_properties, remove_properties, "
                    "start_id, or end_id"
                )

        elif self.op == "CREATE":
            if not self.id:
                raise ValueError("CREATE requires 'id'")
            if not self.label:
                raise ValueError("CREATE requires 'label'")
            if not self.set_properties:
                raise ValueError("CREATE requires 'set_properties'")
            if "data_source_id" not in self.set_properties:
                raise ValueError("CREATE requires 'data_source_id' in set_properties")
            if "source_path" not in self.set_properties:
                raise ValueError("CREATE requires 'source_path' in set_properties")

            if self.type == "node":
                if "slug" not in self.set_properties:
                    raise ValueError("CREATE node requires 'slug' in set_properties")

            if self.type == "edge":
                if not self.start_id or not self.end_id:
                    raise ValueError("CREATE edge requires 'start_id' and 'end_id'")

        elif self.op == "UPDATE":
            if not self.id:
                raise ValueError("UPDATE requires 'id'")
            if not self.set_properties and not self.remove_properties:
                raise ValueError(
                    "UPDATE requires at least one of 'set_properties' or 'remove_properties'"
                )

        elif self.op == "DELETE":
            if not self.id:
                raise ValueError("DELETE requires 'id'")
            if any(
                [
                    self.set_properties,
                    self.remove_properties,
                    self.label,
                    self.start_id,
                    self.end_id,
                ]
            ):
                raise ValueError("DELETE only requires 'op', 'type', and 'id'")

    def to_type_definition(self) -> TypeDefinition:
        """Convert a DEFINE operation to a TypeDefinition.

        Returns:
            TypeDefinition instance

        Raises:
            ValueError: If operation is not DEFINE
        """
        if self.op != "DEFINE":
            raise ValueError(
                "Only DEFINE operations can be converted to TypeDefinition"
            )

        # Convert string type to EntityType enum
        entity_type = EntityType.NODE if self.type == "node" else EntityType.EDGE

        return TypeDefinition(
            label=self.label or "",
            entity_type=entity_type,
            description=self.description or "",
            required_properties=self.required_properties or set(),
            optional_properties=self.optional_properties or set(),
        )


class MutationResult(BaseModel):
    """Result of applying a batch of mutations.

    Attributes:
        success: Whether all operations succeeded
        operations_applied: Number of operations successfully applied
        errors: List of error messages (empty if success=True)
    """

    model_config = ConfigDict(frozen=True)

    success: bool
    operations_applied: int
    errors: list[str] = Field(default_factory=list)
