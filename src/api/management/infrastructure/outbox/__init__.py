"""Management outbox integration.

Provides event serialization for Management domain events
to be stored in the transactional outbox.
"""

from management.infrastructure.outbox.serializer import ManagementEventSerializer

__all__ = ["ManagementEventSerializer"]
