# Entity ID Generation

## Purpose
Entity IDs in the knowledge graph are deterministic — the same entity always produces the same ID regardless of when or how many times it is ingested. This enables idempotent mutation replay and deduplication across data sources and sync runs.

## Requirements

### Requirement: Deterministic Node IDs
The system SHALL generate the same ID for a node given the same inputs.

#### Scenario: Consistent ID generation
- GIVEN a node with type "person" and slug "alice-smith" within a tenant
- WHEN the entity ID is generated multiple times
- THEN the same ID is produced each time

#### Scenario: ID format
- GIVEN any entity type and slug
- WHEN the ID is generated
- THEN the result follows the format `{type}:{16_hex_chars}`
- AND the type is normalized to lowercase

#### Scenario: Different inputs produce different IDs
- GIVEN two nodes with different slugs
- WHEN their IDs are generated
- THEN the IDs are distinct

### Requirement: Deterministic Edge IDs
The system SHALL generate the same ID for an edge given the same inputs.

#### Scenario: Edge ID from endpoints
- GIVEN an edge type, source node ID, and target node ID
- WHEN the edge ID is generated
- THEN the result is deterministic based on these three inputs
- AND the format matches `{type}:{16_hex_chars}`

### Requirement: SHA256-Based Hashing
The system SHALL use SHA256 to derive the hex portion of entity IDs.

#### Scenario: Hash derivation
- GIVEN the input components for an entity ID
- WHEN the hash is computed
- THEN the first 16 characters of the SHA256 hex digest are used as the ID suffix
