# Entity ID Generation

## Purpose
Entity IDs in the knowledge graph are deterministic — the same entity always produces the same ID regardless of when or how many times it is ingested. This enables idempotent mutation replay and deduplication across data sources and sync runs.

## Requirements

### Requirement: Deterministic Node IDs
The system SHALL generate the same ID for a node given the same scoped inputs.

#### Scenario: Consistent ID generation
- GIVEN a node with type "person" and slug "alice-smith" within a specific tenant
- WHEN the entity ID is generated multiple times
- THEN the same ID is produced each time

#### Scenario: ID format
- GIVEN any entity type, slug, and tenant scope
- WHEN the ID is generated
- THEN the result follows the format `{type}:{16_hex_chars}`
- AND the type is normalized to lowercase

#### Scenario: Tenant isolation
- GIVEN the same entity type and slug in two different tenants
- WHEN their IDs are generated
- THEN the IDs are distinct (tenant is part of the hash input)

#### Scenario: Different inputs produce different IDs
- GIVEN two nodes with different slugs within the same tenant
- WHEN their IDs are generated
- THEN the IDs are distinct

### Requirement: Deterministic Edge IDs
The system SHALL generate the same ID for an edge given the same inputs.

#### Scenario: Edge ID from endpoints
- GIVEN an edge type, source node ID, target node ID, and tenant scope
- WHEN the edge ID is generated
- THEN the result is deterministic based on these inputs
- AND the format matches `{type}:{16_hex_chars}`

### Requirement: Canonical Hash Input
The system SHALL include tenant scope as a required component of the hash input.

#### Scenario: Node hash input
- GIVEN a node entity ID generation request
- THEN the canonical input for hashing is `{tenant_id}:{entity_type}:{entity_slug}`

#### Scenario: Edge hash input
- GIVEN an edge entity ID generation request
- THEN the canonical input for hashing is `{tenant_id}:{start_id}:{edge_type}:{end_id}`

### Requirement: SHA256-Based Hashing
The system SHALL use SHA256 to derive the hex portion of entity IDs.

#### Scenario: Hash derivation
- GIVEN the canonical input components for an entity ID
- WHEN the hash is computed
- THEN the first 16 characters of the SHA256 hex digest are used as the ID suffix
