"""Authorization primitives for fine-grained access control.

This module provides shared authorization types and abstractions used across
bounded contexts for SpiceDB integration.
"""

from shared_kernel.authorization.types import (
    Permission,
    RelationType,
    ResourceType,
    format_resource,
    format_subject,
)

__all__ = [
    "ResourceType",
    "RelationType",
    "Permission",
    "format_resource",
    "format_subject",
]
