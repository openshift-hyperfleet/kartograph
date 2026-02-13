"""Domain value objects and exceptions for the Querying bounded context."""

from __future__ import annotations

from typing import TypeAlias, TypedDict

from pydantic import BaseModel, ConfigDict, Field


class QueryExecutionError(Exception):
    """Base exception for query execution failures."""

    def __init__(self, message: str, query: str | None = None):
        super().__init__(message)
        self.query = query


class QueryForbiddenError(QueryExecutionError):
    """Raised when a query attempts forbidden operations (mutations)."""

    pass


class QueryTimeoutError(QueryExecutionError):
    """Raised when a query exceeds the timeout limit."""

    pass


class NodeDict(TypedDict):
    """Structure representing a graph node in query results."""

    id: str
    label: str
    properties: dict[str, str | int | float | bool | list | None]


class EdgeDict(TypedDict):
    """Structure representing a graph edge in query results."""

    id: str
    label: str
    start_id: str
    end_id: str
    properties: dict[str, str | int | float | bool | list | None]


# Query result row can be one of:
# - {"node": NodeDict} for single node returns
# - {"edge": EdgeDict} for single edge returns
# - {"value": scalar} for scalar returns
# - {custom_key: NodeDict | EdgeDict | scalar} for map returns
QueryResultRow: TypeAlias = dict[
    str, NodeDict | EdgeDict | str | int | float | bool | list | dict | None
]


class CypherQueryResult(BaseModel):
    """Immutable result of a Cypher query execution.

    Attributes:
        rows: List of result rows as dictionaries
        row_count: Number of rows returned
        truncated: Whether results were truncated by LIMIT
        execution_time_ms: Query execution time in milliseconds
    """

    model_config = ConfigDict(frozen=True)

    rows: list[QueryResultRow] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    execution_time_ms: float | None = None


class QueryError(BaseModel):
    """Structured error response for query failures.

    Attributes:
        error_type: Category of error (syntax, timeout, forbidden, etc.)
        message: Human-readable error message
        query: The query that caused the error (for debugging)
    """

    model_config = ConfigDict(frozen=True)

    error_type: str
    message: str
    query: str | None = None


class TypeDefinitionSchema(BaseModel):
    """Schema information for a node or edge type.

    Domain representation for type definition metadata exposed via MCP.
    """

    model_config = ConfigDict(frozen=True)

    label: str
    entity_type: str
    description: str
    required_properties: list[str]
    optional_properties: list[str]


class OntologyResponse(BaseModel):
    """Response containing full graph ontology."""

    model_config = ConfigDict(frozen=True)

    type_definitions: list[TypeDefinitionSchema]
    count: int


class SchemaLabelsResponse(BaseModel):
    """Response containing list of type labels."""

    model_config = ConfigDict(frozen=True)

    labels: list[str]
    count: int


class SchemaErrorResponse(BaseModel):
    """Error response for schema resource requests."""

    model_config = ConfigDict(frozen=True)

    error: str
