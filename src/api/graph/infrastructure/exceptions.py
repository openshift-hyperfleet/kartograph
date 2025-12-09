"""Exceptions for Graph Infrastructure."""

from infrastructure.database.exceptions import (
    GraphQueryError,
)


class InsecureCypherQueryError(GraphQueryError):
    """Raised when a Cypher query is identified as potentially malicious."""

    def __init__(self, message: str, query: str | None = None):
        super().__init__(message)
        self.query = query
