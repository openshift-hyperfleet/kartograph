"""Graph primitives module.

Foundational components for graph operations shared across bounded contexts.
This includes entity identification, addressing, and other core graph primitives.
"""

from shared_kernel.graph_primitives.entity_id_generator import EntityIdGenerator

__all__ = ["EntityIdGenerator"]
