"""Domain-Oriented Observability for IAM domain layer.

Probes for domain aggregate operations following Domain-Oriented Observability patterns.
"""

from iam.domain.observability.workspace_probe import (
    DefaultWorkspaceProbe,
    WorkspaceProbe,
)

__all__ = [
    "DefaultWorkspaceProbe",
    "WorkspaceProbe",
]
