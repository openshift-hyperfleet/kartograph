"""Ports (interfaces) for IAM bounded context.

Ports define the contracts for repositories and domain services without
specifying implementation details. This allows for dependency inversion
and makes the domain layer independent of infrastructure.
"""

from iam.ports.exceptions import DuplicateGroupNameError
from iam.ports.repositories import IGroupRepository, IUserRepository

__all__ = [
    "IGroupRepository",
    "IUserRepository",
    "DuplicateGroupNameError",
]
