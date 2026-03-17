"""Management outbox integration.

Provides event serialization and SpiceDB translation for Management
domain events processed through the transactional outbox.
"""

from management.infrastructure.outbox.serializer import ManagementEventSerializer
from management.infrastructure.outbox.translator import ManagementEventTranslator

__all__ = ["ManagementEventSerializer", "ManagementEventTranslator"]
