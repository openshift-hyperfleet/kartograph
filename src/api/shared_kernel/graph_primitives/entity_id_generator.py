"""Entity ID generation for knowledge graph entities.

This module provides deterministic ID generation shared across bounded contexts.
IDs are generated using SHA256 hashing to ensure consistency and idempotency
across the Graph and Extraction contexts.

This is part of the Shared Kernel - changes here affect multiple contexts.
"""

from __future__ import annotations

import hashlib


class EntityIdGenerator:
    """Generates deterministic IDs for knowledge graph entities.

    This class provides a pure, stateless function for generating entity IDs
    that is shared across bounded contexts (particularly Graph and Extraction).
    The generated IDs are deterministic, enabling idempotent operations and
    consistent entity addressing across distributed contexts. More importantly,
    consistent IDs for a given type:slug within a tenant, but across teams + graphs
    enables efficient connected context creation.

    The ID format is: {entity_type}:{hash}
    - entity_type: Normalized to lowercase (e.g., "person", "repository")
    - hash: First 16 characters of SHA256(tenant_id + entity_type + entity_slug)

    Example:
        >>> EntityIdGenerator.generate("Person", "alice-smith")
        "person:abc123def4567890"
        >>> EntityIdGenerator.generate("person", "alice-smith")
        "person:abc123def4567890"  # Same ID - normalized

    Note:
        This is part of the Shared Kernel pattern in DDD. Multiple bounded
        contexts depend on this implementation to produce identical IDs.
        Changes to the ID generation algorithm must be coordinated across
        all dependent contexts.
    """

    @staticmethod
    def _generate_hash(input_string: str) -> str:
        """Generate a 16-character hex hash from input string.

        This is the core hashing function used by both node and edge ID generation.
        Consistency is critical as this is part of the Shared Kernel.

        Args:
            input_string: The string to hash

        Returns:
            First 16 characters of SHA256 hash as hex string
        """
        return hashlib.sha256(input_string.encode()).hexdigest()[:16]

    @staticmethod
    def generate(
        entity_type: str,
        entity_slug: str,
        tenant_id: str = "",
    ) -> str:
        """Generate a deterministic ID for an entity.

        This method produces a stable, reproducible identifier using SHA256
        hashing. The entity_type is normalized to lowercase for the ID prefix,
        ensuring consistent IDs regardless of input casing.

        This supports the secure enclave pattern where IDs and types are
        visible metadata, while all sensitive information resides in properties.

        Args:
            entity_type: The type of entity (e.g., "Person", "Repository").
                Will be normalized to lowercase. Must be non-empty.
            entity_slug: The entity's slug identifier (e.g., "alice-smith").
                Can contain any characters including special chars and unicode.
                Must be non-empty.
            tenant_id: The tenant identifier. Default is "" for single-tenant
                deployments. TODO: Properly incorporate tenant_id when
                multi-tenancy is implemented.

        Returns:
            A deterministic ID string with lowercase type prefix.
            Format: "{normalized_type}:{16_char_hex_hash}"

        Raises:
            ValueError: If entity_type or entity_slug is None, empty, or whitespace-only.

        Example:
            >>> gen = EntityIdGenerator()
            >>> id1 = gen.generate("Person", "alice-smith")
            >>> id2 = gen.generate("person", "alice-smith")
            >>> assert id1 == id2  # Normalized to same ID: "person:..."
            >>> assert id1.startswith("person:")
        """
        # Validate and normalize inputs
        if entity_type is None or not isinstance(entity_type, str):
            raise ValueError("entity_type must be a non-None string")

        if entity_slug is None or not isinstance(entity_slug, str):
            raise ValueError("entity_slug must be a non-None string")

        # Strip whitespace
        entity_type_stripped = entity_type.strip()
        entity_slug_stripped = entity_slug.strip()

        # Ensure non-empty after stripping
        if not entity_type_stripped:
            raise ValueError("entity_type must not be empty or whitespace-only")

        if not entity_slug_stripped:
            raise ValueError("entity_slug must not be empty or whitespace-only")

        # Handle None tenant_id
        tenant_id_str = "" if tenant_id is None else str(tenant_id)

        # Normalize to lowercase for consistent hashing and ID format
        normalized_type = entity_type_stripped.lower()

        # Combine tenant, type, and slug for hash input
        # TODO: Properly incorporate tenant_id when multi-tenancy is implemented
        combined = f"{tenant_id_str}:{normalized_type}:{entity_slug_stripped}"

        # Generate hash using shared hashing function
        hash_value = EntityIdGenerator._generate_hash(combined)

        # Return formatted ID
        return f"{normalized_type}:{hash_value}"

    @staticmethod
    def generate_edge_id(
        edge_label: str,
        start_id: str,
        end_id: str,
        tenant_id: str = "",
    ) -> str:
        """Generate a deterministic ID for an edge.

        Edge IDs are generated from the start node ID, edge label, and end node ID
        to ensure consistency and idempotency across contexts. This enables the
        Extraction context to generate the same edge ID as the Graph context would.

        Args:
            edge_label: The label of the edge (e.g., "knows", "follows").
                Will be normalized to lowercase. Must be non-empty.
            start_id: The ID of the start (source) node (e.g., "person:abc123...").
                Must be non-empty.
            end_id: The ID of the end (target) node (e.g., "person:def456...").
                Must be non-empty.
            tenant_id: The tenant identifier. Default is "" for single-tenant
                deployments. Included for consistency with node ID generation.

        Returns:
            A deterministic ID string with lowercase label prefix.
            Format: "{normalized_label}:{16_char_hex_hash}"

        Raises:
            ValueError: If edge_label, start_id, or end_id is None, empty, or whitespace-only.

        Example:
            >>> gen = EntityIdGenerator()
            >>> id1 = gen.generate_edge_id("knows", "person:aaa", "person:bbb")
            >>> id2 = gen.generate_edge_id("KNOWS", "person:aaa", "person:bbb")
            >>> assert id1 == id2  # Normalized to same ID: "knows:..."
        """
        # Validate and normalize edge_label
        if edge_label is None or not isinstance(edge_label, str):
            raise ValueError("edge_label must be a non-None string")

        if start_id is None or not isinstance(start_id, str):
            raise ValueError("start_id must be a non-None string")

        if end_id is None or not isinstance(end_id, str):
            raise ValueError("end_id must be a non-None string")

        # Strip whitespace
        edge_label_stripped = edge_label.strip()
        start_id_stripped = start_id.strip()
        end_id_stripped = end_id.strip()

        # Ensure non-empty after stripping
        if not edge_label_stripped:
            raise ValueError("edge_label must not be empty or whitespace-only")

        if not start_id_stripped:
            raise ValueError("start_id must not be empty or whitespace-only")

        if not end_id_stripped:
            raise ValueError("end_id must not be empty or whitespace-only")

        # Handle None tenant_id
        tenant_id_str = "" if tenant_id is None else str(tenant_id)

        # Normalize edge label to lowercase
        normalized_label = edge_label_stripped.lower()

        # Combine tenant, start, edge label, and end for hash input
        # Format: tenant:start_id:edge_label:end_id
        combined = (
            f"{tenant_id_str}:{start_id_stripped}:{normalized_label}:{end_id_stripped}"
        )

        # Generate hash using shared hashing function
        hash_value = EntityIdGenerator._generate_hash(combined)

        # Return formatted ID
        return f"{normalized_label}:{hash_value}"
