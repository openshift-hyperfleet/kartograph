"""Infrastructure layer for the outbox pattern.

Contains SQLAlchemy models, repository implementation, and worker
for outbox persistence and processing.
"""

from infrastructure.outbox.composite import CompositeEventHandler
from infrastructure.outbox.models import OutboxModel
from infrastructure.outbox.repository import OutboxRepository
from infrastructure.outbox.spicedb_handler import SpiceDBEventHandler
from infrastructure.outbox.worker import OutboxWorker

__all__ = [
    "CompositeEventHandler",
    "OutboxModel",
    "OutboxRepository",
    "OutboxWorker",
    "SpiceDBEventHandler",
]
