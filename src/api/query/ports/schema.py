"""Schema/ontology port for the Query bounded context.

Defines the interface for accessing graph type definitions without
coupling to the Graph context's implementation.
"""

from typing import Any, Protocol


class ISchemaService(Protocol):
    """Interface for schema/ontology access.

    This port defines what the Query context needs for schema discovery,
    allowing the Graph context's GraphSchemaService to be injected at
    runtime without creating static import dependencies.
    """

    def get_ontology(self) -> list[Any]:
        """Get all type definitions (full graph ontology/schema).

        Returns:
            List of all type definitions for nodes and edges
        """
        ...

    def get_node_labels(
        self,
        search: str | None = None,
        has_property: str | None = None,
    ) -> list[str]:
        """Get list of node type labels.

        Args:
            search: Optional search term to filter labels (case-insensitive)
            has_property: Optional property name filter

        Returns:
            List of node type labels matching filters
        """
        ...

    def get_edge_labels(self, search: str | None = None) -> list[str]:
        """Get list of edge type labels.

        Args:
            search: Optional search term to filter labels (case-insensitive)

        Returns:
            List of edge type labels matching filters
        """
        ...

    def get_node_schema(self, label: str) -> Any | None:
        """Get full schema for a specific node type.

        Args:
            label: The node type label

        Returns:
            TypeDefinition if found, None otherwise
        """
        ...

    def get_edge_schema(self, label: str) -> Any | None:
        """Get full schema for a specific edge type.

        Args:
            label: The edge type label

        Returns:
            TypeDefinition if found, None otherwise
        """
        ...
