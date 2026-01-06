"""Domain-Oriented Observability for IAM infrastructure.

Probes for repository operations following Domain-Oriented Observability patterns.
"""

from iam.infrastructure.observability.repository_probe import (
    DefaultGroupRepositoryProbe,
    DefaultUserRepositoryProbe,
    GroupRepositoryProbe,
    UserRepositoryProbe,
)

__all__ = [
    "GroupRepositoryProbe",
    "DefaultGroupRepositoryProbe",
    "UserRepositoryProbe",
    "DefaultUserRepositoryProbe",
]
