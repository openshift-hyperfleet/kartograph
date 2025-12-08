"""Database-specific exceptions for the Graph bounded context."""


class DatabaseError(Exception):
    """Base exception for database operations."""

    pass


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""

    pass


class GraphQueryError(DatabaseError):
    """Raised when a Cypher query fails."""

    def __init__(self, message: str, query: str | None = None):
        super().__init__(message)
        self.query = query


class TransactionError(DatabaseError):
    """Raised when transaction operations fail."""

    pass
