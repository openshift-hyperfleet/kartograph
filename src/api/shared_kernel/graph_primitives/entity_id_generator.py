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
                Will be normalized to lowercase.
            entity_slug: The entity's slug identifier (e.g., "alice-smith").
                Can contain any characters including special chars and unicode.
            tenant_id: The tenant identifier. Default is ":" for single-tenant
                deployments. TODO: Properly incorporate tenant_id when
                multi-tenancy is implemented.

        Returns:
            A deterministic ID string with lowercase type prefix.
            Format: "{normalized_type}:{16_char_hex_hash}"

        Example:
            >>> gen = EntityIdGenerator()
            >>> id1 = gen.generate("Person", "alice-smith")
            >>> id2 = gen.generate("person", "alice-smith")
            >>> assert id1 == id2  # Normalized to same ID: "person:..."
            >>> assert id1.startswith("person:")
        """
        # Normalize to lowercase for consistent hashing and ID format
        normalized_type = entity_type.lower()

        # Combine tenant, type, and slug for hash input
        # TODO: Properly incorporate tenant_id when multi-tenancy is implemented
        combined = f"{tenant_id}:{normalized_type}:{entity_slug}"

        # Generate SHA256 hash and take first 16 characters
        hash_value = hashlib.sha256(combined.encode()).hexdigest()[:16]

        # Return formatted ID
        return f"{normalized_type}:{hash_value}"
