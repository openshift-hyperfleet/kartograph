"""Domain aggregates for IAM context.

Aggregates are the core business objects containing state and business logic.
They enforce invariants and business rules without depending on infrastructure.
"""

from iam.domain.aggregates.api_key import APIKey
from iam.domain.aggregates.group import Group
from iam.domain.aggregates.tenant import Tenant
from iam.domain.aggregates.user import User
from iam.domain.aggregates.workspace import Workspace

__all__ = [
    "APIKey",
    "Group",
    "Tenant",
    "User",
    "Workspace",
]
