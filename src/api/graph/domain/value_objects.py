"""Domain value objects for the Graph bounded context.

These are immutable data structures that represent domain concepts
within the Graph context. They have no identity - equality is based
on their attribute values.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class MutationOperation(str, Enum):
    """Types of graph mutation operations."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class MutationLine(BaseModel):
    """A single mutation operation for the graph.

    Represents one line in a MutationLog JSONL file.
    Used by the Extraction context to communicate graph changes
    to the Graph context.

    Attributes:
        operation: The type of mutation (CREATE, UPDATE, DELETE)
        id: The deterministic ID of the entity being mutated
        data: The data payload (required for CREATE/UPDATE, optional for DELETE)
    """

    model_config = ConfigDict(frozen=True)

    operation: MutationOperation
    id: str
    data: dict[str, Any] | None = Field(default=None)

    def to_jsonl(self) -> str:
        """Serialize to JSONL format for MutationLog files."""
        payload: dict[str, Any] = {
            "op": self.operation.value,
            "id": self.id,
        }
        if self.data:
            payload["data"] = self.data
        return json.dumps(payload)

    @classmethod
    def from_jsonl(cls, line: str) -> MutationLine:
        """Deserialize from JSONL format."""
        payload = json.loads(line)
        return cls(
            operation=MutationOperation(payload["op"]),
            id=payload["id"],
            data=payload.get("data"),
        )
