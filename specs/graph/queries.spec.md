# Queries

## Purpose
The graph query interface provides read access to knowledge graph data. It supports slug-based lookups, neighbor traversal, and raw Cypher exploration with safety guardrails. All queries execute against the requesting user's tenant graph and enforce per-entity authorization via the secure enclave pattern.

## Requirements

### Requirement: Per-Tenant Graph Routing
The system SHALL route all queries to the tenant-specific AGE graph.

#### Scenario: Tenant graph routing
- GIVEN an authenticated user in tenant "t1"
- WHEN any graph query is executed
- THEN it runs against the AGE graph named `tenant_{tenant_id}`
- AND no data from other tenants' graphs is accessible

### Requirement: KnowledgeGraph Filtering
The system SHALL support optional filtering by KnowledgeGraph across all query types.

#### Scenario: Filtered query
- GIVEN a query with a `knowledge_graph_id` parameter
- WHEN the query is executed
- THEN only nodes and edges with a matching `knowledge_graph_id` property are returned

#### Scenario: Unfiltered query
- GIVEN a query without a `knowledge_graph_id` parameter
- WHEN the query is executed
- THEN nodes and edges across all KnowledgeGraphs in the tenant graph are returned

### Requirement: Secure Enclave — Per-Entity Authorization
The system SHALL check authorization on every individual node and edge in query results, redacting content the user is not authorized to view.

#### Scenario: Authorized entity
- GIVEN a node the user has `view` permission on
- WHEN the node appears in query results
- THEN its full properties are returned

#### Scenario: Unauthorized node (redacted)
- GIVEN a node the user does NOT have `view` permission on
- WHEN the node appears in query results
- THEN only the entity ID is returned (e.g., `{"id": "documentation_module:abf3ad8"}`)
- AND all other properties are stripped

#### Scenario: Unauthorized edge (redacted)
- GIVEN an edge the user does NOT have `view` permission on
- WHEN the edge appears in query results
- THEN only the edge ID, `start_id`, and `end_id` are returned
- AND all other properties are stripped

#### Scenario: Graph topology preserved
- GIVEN a query that traverses relationships between authorized and unauthorized entities
- WHEN the results are returned
- THEN unauthorized edges appear as stubs containing only their ID, `start_id`, and `end_id`
- AND the overall graph structure remains traversable
- AND the user can see that a relationship exists between nodes without seeing the edge's properties

### Requirement: Slug-Based Node Lookup
The system SHALL support finding nodes by their slug property.

#### Scenario: Search by slug
- GIVEN nodes with slug properties in the graph
- WHEN a slug search is performed
- THEN all nodes matching the slug are returned with their properties

#### Scenario: Filter by node type
- GIVEN a slug search with an optional `node_type` filter
- WHEN the search is performed
- THEN only nodes of the specified type are returned

### Requirement: Neighbor Traversal
The system SHALL support retrieving a node and all its directly connected nodes and edges.

#### Scenario: Get neighbors
- GIVEN a node with connected neighbors
- WHEN a neighbor query is performed with the node's ID
- THEN the central node, all adjacent nodes, and connecting edges are returned

### Requirement: Exploration Queries
The system SHALL support raw Cypher queries for advanced graph exploration with safety constraints.

#### Scenario: Valid read-only query
- GIVEN a valid Cypher query that only reads data
- WHEN the query is executed
- THEN results are returned as dictionaries with column mappings

#### Scenario: Write operation rejected
- GIVEN a Cypher query containing CREATE, DELETE, SET, REMOVE, or MERGE
- WHEN the query is submitted
- THEN it is rejected (write operations are not permitted via the query interface)

#### Scenario: Automatic result limiting
- GIVEN a Cypher query without a LIMIT clause
- WHEN the query is executed
- THEN a LIMIT of 100 is automatically applied

#### Scenario: Query timeout
- GIVEN a Cypher query that would take longer than 5 seconds
- WHEN the query is executed
- THEN it is terminated at the timeout boundary

### Requirement: Cypher Injection Prevention
The system SHALL prevent SQL injection via Cypher dollar-quoting by using randomly generated nonce-based delimiters.

#### Scenario: Nonce-based dollar-quoting
- GIVEN a Cypher query to be executed against Apache AGE
- WHEN the query is wrapped in the AGE `cypher()` SQL function
- THEN a unique 64-character random nonce is generated per query
- AND the Cypher text is delimited with `$<nonce>$` tags instead of the default `$$`
- AND the graph name is escaped via parameterized SQL

#### Scenario: Nonce collision with query content
- GIVEN a Cypher query whose text contains the generated nonce
- WHEN the query is about to be executed
- THEN execution is rejected with an insecure query error
- AND the query is not sent to the database

### Requirement: Entity ID Generation
The system SHALL generate deterministic entity IDs from type and slug inputs.

#### Scenario: Generate ID
- GIVEN an entity type and slug
- WHEN an ID is generated
- THEN the result is deterministic (same inputs always produce the same ID)
- AND the entity type is normalized to lowercase
