"""MCP server for the Querying bounded context."""

from typing import Any, Dict

from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from infrastructure.mcp_dependencies import get_schema_service_for_mcp
from infrastructure.settings import get_settings
from query.application.services import MCPQueryService
from query.dependencies import get_mcp_query_service
from query.domain.value_objects import (
    OntologyResponse,
    QueryError,
    SchemaErrorResponse,
    SchemaLabelsResponse,
    TypeDefinitionSchema,
)
from query.ports.schema import ISchemaService, TypeDefinitionLike

settings = get_settings()

mcp = FastMCP(name=settings.app_name)

query_mcp_app = mcp.http_app(path="/mcp")


def _convert_type_definition_to_schema(td: TypeDefinitionLike) -> TypeDefinitionSchema:
    """Convert a TypeDefinition to TypeDefinitionSchema value object.

    Args:
        td: TypeDefinition from Graph context (via ISchemaService port)

    Returns:
        TypeDefinitionSchema domain object
    """
    return TypeDefinitionSchema(
        label=td.label,
        entity_type=td.entity_type.value,
        description=td.description,
        example_file_path=td.example_file_path,
        example_in_file_path=td.example_in_file_path,
        required_properties=sorted(list(td.required_properties)),
        optional_properties=sorted(list(td.optional_properties)),
    )


@mcp.tool
def query_graph(
    cypher: str,
    timeout_seconds: int = 30,
    max_rows: int = 1000,
    service: MCPQueryService = Depends(get_mcp_query_service),
) -> Dict[str, Any]:
    """Execute a Cypher query against the knowledge graph.

    This tool allows you to query the Kartograph knowledge graph using
    Cypher query language. Only read-only queries are permitted.

    IMPORTANT: Apache AGE requires queries to return a single column.
    To return multiple values, wrap them in a map:
      - Single value: RETURN n
      - Multiple values: RETURN {person: p, friend: f}

    Args:
        cypher: The Cypher query to execute. Must be read-only (no CREATE,
            DELETE, SET, REMOVE, or MERGE). Must return a single column
            (use map syntax for multiple values).
        timeout_seconds: Maximum query execution time in seconds.
            Default is 30 seconds. Maximum is 60 seconds.
        max_rows: Maximum number of rows to return. Default is 1000.
            Maximum is 10000.

    Returns:
        A dictionary containing:
        - success: Boolean indicating if the query succeeded
        - rows: List of result rows (on success)
        - row_count: Number of rows returned (on success)
        - truncated: Whether results were truncated (on success)
        - execution_time_ms: Query execution time in milliseconds (on success)
        - error_type: Type of error (on failure)
        - message: Error message (on failure)

    Examples:
        # Get all Person nodes
        query_graph("MATCH (p:Person) RETURN p LIMIT 10")

        # Get specific properties
        query_graph("MATCH (p:Person) RETURN p.name, p.email")

        # Get relationships using map syntax (REQUIRED for multiple items)
        query_graph('''
            MATCH (a:Person)-[r:KNOWS]->(b:Person)
            RETURN {source: a, relationship: r, target: b}
            LIMIT 20
        ''')

        # Aggregations
        query_graph("MATCH (p:Person) RETURN count(p)")
    """

    # Enforce maximum limits
    timeout_seconds = min(timeout_seconds, 60)
    max_rows = min(max_rows, 10000)

    result = service.execute_cypher_query(
        query=cypher,
        timeout_seconds=timeout_seconds,
        max_rows=max_rows,
    )

    if isinstance(result, QueryError):
        return {
            "success": False,
            "error_type": result.error_type,
            "message": result.message,
        }

    # CypherQueryResult
    return {
        "success": True,
        "rows": result.rows,
        "row_count": result.row_count,
        "truncated": result.truncated,
        "execution_time_ms": result.execution_time_ms,
    }


@mcp.resource(
    uri="schema://ontology",
    name="GraphOntology",
    description="Complete graph ontology including all node and edge type definitions with properties and examples",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
def get_ontology(
    service: ISchemaService = Depends(get_schema_service_for_mcp),
) -> OntologyResponse | SchemaErrorResponse:
    """Get complete graph ontology/schema.

    Returns all type definitions for nodes and edges in the knowledge graph.
    This includes labels, descriptions, required/optional properties, and examples.

    Use this resource to understand the structure of the knowledge graph before
    writing Cypher queries.

    Returns:
        OntologyResponse containing all type definitions
    """
    definitions = service.get_ontology()

    # Error handling for empty schema
    if not definitions:
        return SchemaErrorResponse(error="No type definitions found in graph schema")

    # Convert to domain value objects using shared helper
    type_schemas = [_convert_type_definition_to_schema(td) for td in definitions]

    return OntologyResponse(type_definitions=type_schemas, count=len(type_schemas))


@mcp.resource(
    uri="schema://nodes/labels",
    name="NodeTypeLabels",
    description="List of all node type labels available in the graph schema",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
def get_node_labels_resource(
    service: ISchemaService = Depends(get_schema_service_for_mcp),
) -> SchemaLabelsResponse:
    """Get list of all node type labels.

    Returns a list of all node type labels (e.g., person, project, repository)
    available in the knowledge graph schema.

    Returns:
        SchemaLabelsResponse containing node labels and count
    """
    labels = service.get_node_labels()
    return SchemaLabelsResponse(labels=labels, count=len(labels))


@mcp.resource(
    uri="schema://edges/labels",
    name="EdgeTypeLabels",
    description="List of all edge type labels available in the graph schema",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
def get_edge_labels_resource(
    service: ISchemaService = Depends(get_schema_service_for_mcp),
) -> SchemaLabelsResponse:
    """Get list of all edge type labels.

    Returns a list of all edge type labels (e.g., knows, reports_to, depends_on)
    available in the knowledge graph schema.

    Returns:
        SchemaLabelsResponse containing edge labels and count
    """
    labels = service.get_edge_labels()
    return SchemaLabelsResponse(labels=labels, count=len(labels))


@mcp.resource(
    uri="schema://nodes/{label}",
    name="NodeTypeSchema",
    description="Detailed schema for a specific node type including required/optional properties and examples",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
def get_node_schema_resource(
    label: str,
    service: ISchemaService = Depends(get_schema_service_for_mcp),
) -> TypeDefinitionSchema | SchemaErrorResponse:
    """Get detailed schema for a specific node type.

    Provides complete type definition including description, required/optional
    properties, and examples for a specific node type.

    Args:
        label: The node type label (e.g., "person", "project")

    Returns:
        TypeDefinitionSchema if found, SchemaErrorResponse otherwise
    """
    schema = service.get_node_schema(label)

    if schema is None:
        return SchemaErrorResponse(error=f"Node type '{label}' not found")

    return _convert_type_definition_to_schema(schema)


@mcp.resource(
    uri="schema://edges/{label}",
    name="EdgeTypeSchema",
    description="Detailed schema for a specific edge type including required/optional properties and examples",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
def get_edge_schema_resource(
    label: str,
    service: ISchemaService = Depends(get_schema_service_for_mcp),
) -> TypeDefinitionSchema | SchemaErrorResponse:
    """Get detailed schema for a specific edge type.

    Provides complete type definition including description, required/optional
    properties, and examples for a specific edge type.

    Args:
        label: The edge type label (e.g., "knows", "reports_to")

    Returns:
        TypeDefinitionSchema if found, SchemaErrorResponse otherwise
    """
    schema = service.get_edge_schema(label)

    if schema is None:
        return SchemaErrorResponse(error=f"Edge type '{label}' not found")

    return _convert_type_definition_to_schema(schema)
