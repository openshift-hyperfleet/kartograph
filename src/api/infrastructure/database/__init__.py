"""Database infrastructure - shared connection primitives."""

from infrastructure.database.exceptions import (
    ConnectionError,
    DatabaseError,
    GraphQueryError,
    TransactionError,
)

__all__ = [
    "ConnectionError",
    "DatabaseError",
    "GraphQueryError",
    "TransactionError",
]
