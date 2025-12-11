"""Graph ports (interfaces) module.

Ports define the contracts between the application layer and infrastructure.
They allow for dependency inversion, enabling the domain to remain
independent of specific implementations.
"""

from graph.ports.repositories import IGraphReadOnlyRepository

__all__ = ["IGraphReadOnlyRepository"]
