"""Database infrastructure - shared connection primitives."""

from infrastructure.database.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    GraphQueryError,
    TransactionError,
)

__all__ = [
    "DatabaseConnectionError",
    "DatabaseError",
    "GraphQueryError",
    "TransactionError",
]
