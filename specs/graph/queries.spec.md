# Queries

## Purpose
The graph query interface provides read access to knowledge graph data. It supports slug-based lookups, neighbor traversal, and raw Cypher exploration with safety guardrails.

## Requirements

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

### Requirement: Entity ID Generation
The system SHALL generate deterministic entity IDs from type and slug inputs.

#### Scenario: Generate ID
- GIVEN an entity type and slug
- WHEN an ID is generated
- THEN the result is deterministic (same inputs always produce the same ID)
- AND the entity type is normalized to lowercase
