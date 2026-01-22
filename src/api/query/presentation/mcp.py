"""MCP server for the Querying bounded context."""

from pathlib import Path
from typing import Any, Dict, List

from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from infrastructure.mcp_dependencies import get_schema_service_for_mcp
from infrastructure.settings import get_settings
from query.application.observability import SchemaResourceProbe
from query.application.services import MCPQueryService
from query.dependencies import get_mcp_query_service, get_schema_resource_probe
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

# Load agent instructions from file
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_AGENT_INSTRUCTIONS_PATH = _PROMPTS_DIR / "agent_instructions.md"


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
        required_properties=sorted(list(td.required_properties)),
        optional_properties=sorted(list(td.optional_properties)),
    )


@mcp.tool
def query_graph(
    cypher: str,
    timeout_seconds: int = 30,
    max_rows: int = 1000,
    service: MCPQueryService = Depends(get_mcp_query_service),  # type: ignore[arg-type]
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


@mcp.tool
def get_entity_overview(
    entity_types: List[str],
    service: MCPQueryService = Depends(get_mcp_query_service),  # type: ignore[arg-type]
) -> Dict[str, Any]:
    """Get comprehensive overview of one or more entity types.

    Provides for each entity type:
    - Total instance count
    - Sample instances (first 6 slugs)
    - Outgoing relationships summary (type → target counts)

    Args:
        entity_types: List of entity type labels (e.g., ["DocumentationModule", "KCSArticle"])

    Returns:
        Dictionary with overview for each entity type.

    Examples:
        get_entity_overview(["DocumentationModule"])
        get_entity_overview(["KCSArticle", "CLICommand", "Operator"])
    """
    results = {}

    for label in entity_types:
        overview: Dict[str, Any] = {"label": label}

        # Get instance count
        count_query = f"MATCH (n:{label}) RETURN count(n)"
        count_result = service.execute_cypher_query(count_query, max_rows=1)

        if isinstance(count_result, QueryError):
            overview["error"] = count_result.message
            results[label] = overview
            continue

        if not count_result.rows:
            overview["error"] = f"Entity type '{label}' not found or has no instances."
            results[label] = overview
            continue

        instance_count = count_result.rows[0].get("value", 0)
        overview["instance_count"] = instance_count

        # Get sample slugs (first 6)
        samples_query = f"""
        MATCH (n:{label})
        RETURN COALESCE(n.slug, n.name, n.title, toString(id(n)))
        LIMIT 6
        """
        samples_result = service.execute_cypher_query(samples_query, max_rows=6)

        if not isinstance(samples_result, QueryError) and samples_result.rows:
            overview["sample_slugs"] = [
                row.get("value", "") for row in samples_result.rows
            ]

        # Get outgoing relationship summary
        outgoing_query = f"""
        MATCH (n:{label})-[r]->(target)
        RETURN {{rel_type: type(r), target_type: labels(target)[0], count: count(r)}}
        """
        outgoing_result = service.execute_cypher_query(outgoing_query, max_rows=100)

        if not isinstance(outgoing_result, QueryError) and outgoing_result.rows:
            relationships = []
            for row in outgoing_result.rows:
                rel_type = row.get("rel_type", "")
                target_type = row.get("target_type", "")
                count = row.get("count", 0)
                relationships.append(
                    {"relationship": rel_type, "target": target_type, "count": count}
                )
            # Sort by count descending
            relationships.sort(key=lambda x: x["count"], reverse=True)
            overview["outgoing_relationships"] = relationships[:20]  # Top 20

        results[label] = overview

    return {"entity_overviews": results, "count": len(results)}


@mcp.tool
def find_instances_by_slug(
    search_terms: List[str],
    entity_types: List[str],
    service: MCPQueryService = Depends(get_mcp_query_service),  # type: ignore[arg-type]
) -> Dict[str, Any]:
    """Search for instances of entity types by slug using substring matching.

    Each term in search_terms must appear as a substring in the slug (any order).

    Args:
        search_terms: List of substrings that must all appear in the slug
            (e.g., ["etcd", "backup"] or ["upgrade", "node", "drain"])
        entity_types: List of entity types to search (e.g., ["DocumentationModule", "KCSArticle"])

    Returns:
        Top 15 matching instances with slugs.

    Examples:
        find_instances_by_slug(["etcd", "backup"], ["DocumentationModule"])
        find_instances_by_slug(["upgrade", "node", "drain"], ["Alert", "SOPAlertRunbook"])
        find_instances_by_slug(["pdb", "update"], ["KCSArticle"])

    Important:
        Always call get_entity_overview first to see slug naming patterns
        before constructing search terms.
    """
    # Normalize search terms to lowercase
    normalized_terms = [term.lower() for term in search_terms]
    all_matches: List[Dict[str, Any]] = []
    total_candidates = 0

    for entity_type in entity_types:
        # Get candidate slugs for this entity type
        slug_query = f"""
        MATCH (n:{entity_type})
        RETURN COALESCE(n.slug, n.name, n.title, toString(id(n)))
        """
        slug_result = service.execute_cypher_query(slug_query, max_rows=10000)

        if isinstance(slug_result, QueryError):
            continue  # Skip this entity type on error

        if not slug_result.rows:
            continue

        # Extract slugs - results come back under "value" key
        slugs = [row.get("value", "") for row in slug_result.rows if row.get("value")]
        total_candidates += len(slugs)

        # Each term must be contained in the slug
        for slug in slugs:
            slug_lower = slug.lower()
            if all(term in slug_lower for term in normalized_terms):
                all_matches.append({"entity_type": entity_type, "slug": slug})

    # Sort alphabetically for consistent results
    all_matches.sort(key=lambda x: (x["entity_type"], x["slug"]))

    return {
        "success": True,
        "entity_types": entity_types,
        "search_terms": search_terms,
        "matches": all_matches[:15],
        "total_candidates": total_candidates,
    }


@mcp.tool
def get_neighbors(
    entity_type: str,
    slug: str,
    service: MCPQueryService = Depends(get_mcp_query_service),  # type: ignore[arg-type]
) -> Dict[str, Any]:
    """Get all directly connected nodes (1-hop outgoing relationships).

    Returns all nodes that the specified instance points to, including
    the relationship type and target node info.

    Args:
        entity_type: The entity type (e.g., "DocumentationModule")
        slug: The slug of the instance to explore

    Returns:
        List of outgoing relationships with target node info.

    Examples:
        get_neighbors("KCSArticle", "vm-serial-console-logs")
        get_neighbors("CLITool", "oc")
    """
    # Find the node and its outgoing relationships
    # Use simpler return structure to avoid serialization issues
    query = f"""
    MATCH (n:{entity_type} {{slug: '{slug}'}})-[r]->(target)
    RETURN {{
        relationship_type: type(r),
        target_type: label(target),
        target_slug: COALESCE(target.slug, target.name, target.title, toString(id(target))),
        target_title: target.title
    }}
    """
    result = service.execute_cypher_query(query, max_rows=500)

    if isinstance(result, QueryError):
        return {"success": False, "error": result.message}

    if not result.rows:
        # Check if the node exists
        exists_query = f"MATCH (n:{entity_type} {{slug: '{slug}'}}) RETURN count(n)"
        exists_result = service.execute_cypher_query(exists_query, max_rows=1)

        if isinstance(exists_result, QueryError):
            return {"success": False, "error": exists_result.message}

        count = exists_result.rows[0].get("value", 0) if exists_result.rows else 0
        if count == 0:
            return {
                "success": False,
                "error": f"Instance '{slug}' of type '{entity_type}' not found.",
            }

        return {
            "success": True,
            "entity_type": entity_type,
            "slug": slug,
            "neighbors": [],
            "message": "No outgoing relationships found.",
        }

    neighbors = []
    for row in result.rows:
        neighbor = {
            "relationship": row.get("relationship_type", ""),
            "target_type": row.get("target_type", ""),
            "target_slug": row.get("target_slug", ""),
        }
        # Include title if available
        if row.get("target_title"):
            neighbor["target_title"] = row["target_title"]
        neighbors.append(neighbor)

    # Group by relationship type for easier reading
    by_rel_type: Dict[str, List[Dict[str, Any]]] = {}
    for n in neighbors:
        rel = n["relationship"]
        if rel not in by_rel_type:
            by_rel_type[rel] = []
        by_rel_type[rel].append(n)

    return {
        "success": True,
        "entity_type": entity_type,
        "slug": slug,
        "neighbor_count": len(neighbors),
        "neighbors_by_relationship": by_rel_type,
    }


@mcp.tool
def get_instance_details(
    entity_type: str,
    slug: str,
    service: MCPQueryService = Depends(get_mcp_query_service),  # type: ignore[arg-type]
) -> Dict[str, Any]:
    """Get full details of a specific instance.

    Returns all properties of the node plus a summary of its relationships
    (grouped by type with counts, limited to top 10 relationship types).

    Args:
        entity_type: The entity type (e.g., "KCSArticle")
        slug: The slug of the instance

    Returns:
        Full node properties and relationship summary.

    Examples:
        get_instance_details("KCSArticle", "vm-serial-console-logs")
        get_instance_details("DocumentationModule", "about-rosa")
    """
    # Get the node properties using properties() function to avoid serialization issues
    node_query = f"""
    MATCH (n:{entity_type} {{slug: '{slug}'}})
    RETURN properties(n)
    """
    node_result = service.execute_cypher_query(node_query, max_rows=1)

    if isinstance(node_result, QueryError):
        return {"success": False, "error": node_result.message}

    if not node_result.rows:
        return {
            "success": False,
            "error": f"Instance '{slug}' of type '{entity_type}' not found.",
        }

    # Extract node properties - properties() returns a map directly
    row_data = node_result.rows[0]
    # The result could be under "value" key or directly in the row
    if isinstance(row_data, dict):
        if "value" in row_data and isinstance(row_data["value"], dict):
            properties = row_data["value"]
        else:
            properties = row_data
    else:
        properties = {}

    # Ensure all property values are JSON-serializable
    # Convert any complex types to strings
    clean_properties: Dict[str, Any] = {}
    for key, value in properties.items():
        if isinstance(value, (str, int, float, bool, type(None))):
            clean_properties[key] = value
        elif isinstance(value, list):
            # Keep lists as-is (they should contain primitives)
            clean_properties[key] = value
        elif isinstance(value, dict):
            # Keep dicts as-is
            clean_properties[key] = value
        else:
            # Convert anything else to string
            clean_properties[key] = str(value)

    # Get relationship summary (outgoing)
    rel_query = f"""
    MATCH (n:{entity_type} {{slug: '{slug}'}})-[r]->(target)
    RETURN {{rel_type: type(r), target_type: label(target), count: count(r)}}
    """
    rel_result = service.execute_cypher_query(rel_query, max_rows=100)

    relationship_summary = []
    if not isinstance(rel_result, QueryError) and rel_result.rows:
        for row in rel_result.rows:
            relationship_summary.append(
                {
                    "relationship": row.get("rel_type", ""),
                    "target_type": row.get("target_type", ""),
                    "count": row.get("count", 0),
                }
            )
        # Sort by count descending and limit to top 10
        relationship_summary.sort(key=lambda x: -x["count"])
        relationship_summary = relationship_summary[:10]

    return {
        "success": True,
        "entity_type": entity_type,
        "slug": slug,
        "properties": clean_properties,
        "relationship_summary": relationship_summary,
        "total_relationship_types": len(relationship_summary),
    }


@mcp.tool
def find_instances_by_content(
    search_terms: List[str],
    entity_types: List[str] | None = None,
    service: MCPQueryService = Depends(get_mcp_query_service),  # type: ignore[arg-type]
) -> Dict[str, Any]:
    """Search across all text content of nodes, not just slugs.

    Searches all properties on matching nodes including: title, description,
    content, body, resolution, cause, symptom, misc (list of strings), and
    any other text properties.

    Each term in search_terms must appear in at least one property of the node.

    Args:
        search_terms: List of substrings to search for (e.g., ["webhook", "eviction"])
        entity_types: Optional filter to specific types. If not provided, searches
            common document types: SOPAlertRunbook, KCSArticle, DocumentationModule,
            SOPTroubleshootingGuide, SOPOperationalProcedure

    Returns:
        Top 20 matching nodes with slug, type, title, and matching snippets.

    Examples:
        find_instances_by_content(["webhook", "pod", "eviction"])
        find_instances_by_content(["etcd", "quorum"], ["KCSArticle", "SOPAlertRunbook"])
        find_instances_by_content(["drain", "timeout"], ["DocumentationModule"])

    Use this tool when:
        - find_instances_by_slug returns no results (search terms not in slugs)
        - You need to search actual document content, not just titles/slugs
        - Looking for specific error messages, procedures, or concepts
    """
    # Default to common document entity types
    if not entity_types:
        entity_types = [
            "SOPAlertRunbook",
            "KCSArticle",
            "DocumentationModule",
            "SOPTroubleshootingGuide",
            "SOPOperationalProcedure",
        ]

    # Normalize search terms
    normalized_terms = [term.lower() for term in search_terms]

    all_matches: List[Dict[str, Any]] = []

    for entity_type in entity_types:
        # Get all instances with their properties
        query = f"""
        MATCH (n:{entity_type})
        RETURN {{
            slug: COALESCE(n.slug, n.name, toString(id(n))),
            title: n.title,
            description: n.description,
            content: n.content,
            body: n.body,
            resolution: n.resolution,
            cause: n.cause,
            symptom: n.symptom,
            misc: n.misc
        }}
        """
        result = service.execute_cypher_query(query, max_rows=5000)

        if isinstance(result, QueryError):
            continue  # Skip this entity type on error

        for row in result.rows:
            # Build searchable text from all properties
            searchable_parts: List[str] = []

            for key in [
                "slug",
                "title",
                "description",
                "content",
                "body",
                "resolution",
                "cause",
                "symptom",
            ]:
                value = row.get(key)
                if value and isinstance(value, str):
                    searchable_parts.append(value.lower())

            # Handle misc which is a list of strings
            misc = row.get("misc")
            if misc and isinstance(misc, list):
                for item in misc:
                    if isinstance(item, str):
                        searchable_parts.append(item.lower())

            # Combine all searchable text
            searchable_text = " ".join(searchable_parts)

            # Check if all terms appear in the combined text
            if all(term in searchable_text for term in normalized_terms):
                match_info: Dict[str, Any] = {
                    "entity_type": entity_type,
                    "slug": row.get("slug", ""),
                }
                if row.get("title"):
                    match_info["title"] = row["title"]

                # Find which properties matched (for context)
                matched_in: List[str] = []
                for key in [
                    "title",
                    "description",
                    "content",
                    "resolution",
                    "cause",
                    "symptom",
                ]:
                    value = row.get(key)
                    if value and isinstance(value, str):
                        if any(term in value.lower() for term in normalized_terms):
                            matched_in.append(key)

                if misc and isinstance(misc, list):
                    misc_text = " ".join(
                        item.lower() for item in misc if isinstance(item, str)
                    )
                    if any(term in misc_text for term in normalized_terms):
                        matched_in.append("misc")

                if matched_in:
                    match_info["matched_in"] = matched_in

                all_matches.append(match_info)

    # Sort by entity type priority, then alphabetically
    type_priority = {
        "SOPAlertRunbook": 0,
        "KCSArticle": 1,
        "SOPTroubleshootingGuide": 2,
        "SOPOperationalProcedure": 3,
        "DocumentationModule": 4,
    }
    all_matches.sort(
        key=lambda x: (type_priority.get(x["entity_type"], 99), x["slug"])
    )

    return {
        "success": True,
        "search_terms": search_terms,
        "entity_types_searched": entity_types,
        "matches": all_matches[:20],
        "total_matches": len(all_matches),
    }


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
    probe: SchemaResourceProbe = Depends(get_schema_resource_probe),
) -> TypeDefinitionSchema | SchemaErrorResponse:
    """Get detailed schema for a specific node type.

    Provides complete type definition including description, required/optional
    properties, and examples for a specific node type.

    Args:
        label: The node type label (e.g., "person", "project")

    Returns:
        TypeDefinitionSchema if found, SchemaErrorResponse otherwise
    """
    probe.schema_resource_accessed(resource_uri=f"schema://nodes/{label}", label=label)

    schema = service.get_node_schema(label)

    if schema is None:
        probe.schema_type_not_found(resource_uri=f"schema://nodes/{label}", label=label)
        return SchemaErrorResponse(error=f"Node type '{label}' not found")

    probe.schema_resource_returned(resource_uri=f"schema://nodes/{label}", found=True)

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
    probe: SchemaResourceProbe = Depends(get_schema_resource_probe),
) -> TypeDefinitionSchema | SchemaErrorResponse:
    """Get detailed schema for a specific edge type.

    Provides complete type definition including description, required/optional
    properties, and examples for a specific edge type.

    Args:
        label: The edge type label (e.g., "knows", "reports_to")

    Returns:
        TypeDefinitionSchema if found, SchemaErrorResponse otherwise
    """
    probe.schema_resource_accessed(resource_uri=f"schema://edges/{label}", label=label)

    schema = service.get_edge_schema(label)

    if schema is None:
        probe.schema_type_not_found(resource_uri=f"schema://edges/{label}", label=label)
        return SchemaErrorResponse(error=f"Edge type '{label}' not found")

    probe.schema_resource_returned(resource_uri=f"schema://edges/{label}", found=True)

    return _convert_type_definition_to_schema(schema)


@mcp.resource(
    uri="instructions://agent",
    name="AgentInstructions",
    description="Comprehensive system instructions for AI agents querying the Kartograph knowledge graph",
    mime_type="text/markdown",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
def get_agent_instructions() -> str:
    """Get agent instructions for querying the knowledge graph.

    Returns comprehensive instructions including:
    - Knowledge graph overview and domain
    - Foundational entity types and their purposes
    - Query best practices and common patterns
    - Apache AGE Cypher syntax requirements
    - Error handling and troubleshooting tips

    Returns:
        Markdown-formatted agent instructions
    """
    try:
        with open(_AGENT_INSTRUCTIONS_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return (
            "# Agent Instructions Not Found\n\n"
            "The agent instructions file could not be loaded. "
            "Please ensure the instructions file exists at the expected location."
        )
