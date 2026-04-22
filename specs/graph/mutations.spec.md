# Mutations

## Purpose
Mutations are the write path for the knowledge graph. They are expressed as JSONL mutation logs, where each line describes a single operation (define a type, create/update/delete a node or edge). Mutations are designed for idempotent replay by AI agents and deterministic processors.

## Requirements

### Requirement: Per-Tenant Graph Isolation
The system SHALL execute mutations against a tenant-specific graph for data isolation.

#### Scenario: Tenant graph routing
- GIVEN an authenticated user in tenant "t1"
- WHEN mutations are submitted
- THEN they execute against the AGE graph named `tenant_{tenant_id}` (e.g., `tenant_t1`)
- AND no data is written to any other tenant's graph

### Requirement: KnowledgeGraph Scoping
The system SHALL require a target KnowledgeGraph for all mutations and enforce authorization.

#### Scenario: Mutation authorization
- GIVEN a mutation request targeting a specific KnowledgeGraph
- WHEN the request is processed
- THEN the user MUST have `edit` permission on the KnowledgeGraph (via SpiceDB)
- AND the request is rejected with a forbidden error if permission is denied

#### Scenario: KnowledgeGraph ID stamping
- GIVEN a mutation targeting KnowledgeGraph "kg-123"
- WHEN CREATE or UPDATE operations are applied
- THEN `knowledge_graph_id` is stamped on all created/updated nodes and edges from the authorized target KnowledgeGraph
- AND any `knowledge_graph_id` value provided by the caller is rejected or ignored
- AND this applies to mutation validation logic so callers cannot spoof the graph ID

### Requirement: Mutation Log Format
The system SHALL accept mutations as JSONL (one JSON object per line).

#### Scenario: Valid JSONL
- GIVEN a string with one valid JSON operation per line
- WHEN the mutations are submitted
- THEN each line is parsed and applied in order

#### Scenario: Parse error on a line
- GIVEN a JSONL string with an invalid JSON line
- WHEN the mutations are submitted
- THEN the error is reported with the line number and a content preview

#### Scenario: Empty lines
- GIVEN a JSONL string with blank lines between operations
- WHEN the mutations are submitted
- THEN blank lines are skipped without error

### Requirement: DEFINE Operation
The system SHALL support declaring node and edge types with property schemas.

#### Scenario: Define a node type
- GIVEN a DEFINE operation with label "person", description, and required properties
- WHEN the mutation is applied
- THEN a type definition is stored with the label, description, required properties, and empty optional properties
- AND system properties (`data_source_id`, `source_path`, `slug`) are automatically added to required properties

#### Scenario: Define an edge type
- GIVEN a DEFINE operation with entity type "edge"
- WHEN the mutation is applied
- THEN system properties for edges (`data_source_id`, `source_path`) are automatically added

### Requirement: CREATE Operation
The system SHALL support idempotent entity creation with property accumulation.

#### Scenario: Create a new node
- GIVEN a CREATE operation with a deterministic ID, label, and `set_properties`
- WHEN the entity does not yet exist in the graph
- THEN the node is created with the specified properties

#### Scenario: Create an existing node (idempotent merge)
- GIVEN a CREATE operation for a node that already exists
- WHEN the mutation is applied
- THEN existing properties are preserved
- AND new properties from `set_properties` are added

#### Scenario: Create an edge
- GIVEN a CREATE operation for an edge with `start_id` and `end_id`
- WHEN both referenced nodes exist
- THEN the edge is created between them

#### Scenario: Missing type definition
- GIVEN a CREATE operation for a label with no prior DEFINE (in this batch or stored)
- WHEN the mutation is applied
- THEN the operation is rejected with an error

#### Scenario: Missing required properties
- GIVEN a CREATE operation that omits a required property from the type definition
- WHEN the mutation is applied
- THEN the operation is rejected with a validation error

#### Scenario: Schema learning
- GIVEN a CREATE operation with `set_properties` containing fields beyond the required set
- WHEN the mutation succeeds
- THEN the extra properties are added to the type definition's optional properties

### Requirement: UPDATE Operation
The system SHALL support modifying or removing specific properties on existing entities.

#### Scenario: Set properties
- GIVEN an UPDATE operation with `set_properties`
- WHEN the entity exists
- THEN the specified properties are set (added or overwritten)
- AND unlisted properties are preserved

#### Scenario: Remove properties
- GIVEN an UPDATE operation with `remove_properties`
- WHEN the entity exists
- THEN the specified properties are removed

#### Scenario: Schema learning on update
- GIVEN an UPDATE that sets a property not in the type definition
- WHEN the mutation succeeds
- THEN the property is added to the type definition's optional properties

### Requirement: DELETE Operation
The system SHALL support deleting nodes and edges.

#### Scenario: Delete a node
- GIVEN a DELETE operation for a node
- WHEN the mutation is applied
- THEN the node and all its connected edges are removed (cascading detach delete)

#### Scenario: Delete an edge
- GIVEN a DELETE operation for an edge
- WHEN the mutation is applied
- THEN only the edge is removed

### Requirement: Mandatory System Properties
The system SHALL require specific system-managed properties on all CREATE operations.

#### Scenario: Node system properties
- GIVEN a CREATE operation for a node
- THEN `data_source_id`, `source_path`, `slug`, and `knowledge_graph_id` MUST be present in `set_properties`

#### Scenario: Edge system properties
- GIVEN a CREATE operation for an edge
- THEN `data_source_id`, `source_path`, and `knowledge_graph_id` MUST be present in `set_properties`

### Requirement: Deterministic Entity IDs
The system SHALL use deterministic IDs for idempotent mutation replay.

#### Scenario: ID format
- GIVEN a CREATE operation
- THEN the `id` field follows the pattern `{type}:{16_hex_chars}`
- AND the same entity always produces the same ID

### Requirement: Referential Integrity Ordering
The system SHALL enforce correct ordering of operations to maintain referential integrity.

#### Scenario: Operation ordering
- GIVEN a batch with mixed operation types
- WHEN the mutations are applied
- THEN DEFINE operations run first
- AND DELETE operations run next (edges before nodes)
- AND CREATE operations follow (nodes before edges)
- AND UPDATE operations run last
