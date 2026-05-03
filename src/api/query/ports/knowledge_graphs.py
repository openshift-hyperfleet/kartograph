"""Knowledge graph port definitions for the Querying bounded context.

Defines the data contract for accessible knowledge graph summaries
returned by the composition layer to the MCP resource handler.
"""

from __future__ import annotations

from typing import TypedDict


class AccessibleKnowledgeGraph(TypedDict):
    """A summary of a knowledge graph the caller can access.

    This is the minimal representation needed by MCP clients — just
    enough to identify and describe each accessible knowledge graph.

    Attributes:
        id:          Unique identifier of the knowledge graph.
        name:        Human-readable name of the knowledge graph.
        description: Description of the knowledge graph's content.
    """

    id: str
    name: str
    description: str
