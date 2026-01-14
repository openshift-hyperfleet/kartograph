"""Outbox pattern implementation for ensuring consistency.

This module provides the transactional outbox pattern to ensure consistency
between PostgreSQL (application data) and SpiceDB (authorization data).
"""

from shared_kernel.outbox.ports import IOutboxRepository
from shared_kernel.outbox.value_objects import OutboxEntry

__all__ = ["IOutboxRepository", "OutboxEntry"]
