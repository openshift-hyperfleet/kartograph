# Schema

## Purpose
The graph schema tracks type definitions (ontology) for all node and edge types in the knowledge graph. Type definitions describe what properties each entity type requires and optionally supports. The schema evolves automatically as new data is ingested.

## Requirements

### Requirement: Ontology Retrieval
The system SHALL provide the complete set of type definitions as an ontology.

#### Scenario: Get ontology
- GIVEN type definitions exist for multiple node and edge types
- WHEN the ontology is requested
- THEN all type definitions are returned with their labels, entity types, descriptions, required properties, and optional properties

### Requirement: Label Listing
The system SHALL list node and edge type labels with optional filtering.

#### Scenario: List node labels
- GIVEN type definitions for node types "person" and "repository"
- WHEN node labels are listed
- THEN both labels are returned

#### Scenario: Search labels by name
- GIVEN a search term
- WHEN node or edge labels are listed with the search filter
- THEN only labels matching the search (case-insensitive) are returned

#### Scenario: Filter by property
- GIVEN node types where only "person" has a "name" property
- WHEN node labels are listed with `has_property=name`
- THEN only "person" is returned

### Requirement: Type Definition Lookup
The system SHALL return the full schema for a specific type label, scoped by entity type (node or edge).

#### Scenario: Existing type
- GIVEN a type definition for node label "person"
- WHEN the node schema is requested for "person"
- THEN the definition is returned with description, required properties, and optional properties

#### Scenario: Same label, different entity types
- GIVEN a node type "link" and an edge type "link"
- WHEN the node schema is requested for "link"
- THEN only the node definition is returned (labels are scoped by entity type, not globally unique)

#### Scenario: Unknown type
- GIVEN no type definition for label "widget"
- WHEN the schema is requested for "widget"
- THEN a not-found response is returned

### Requirement: Schema Evolution
The system SHALL automatically expand optional properties when new properties are discovered during ingestion.

#### Scenario: New property discovered
- GIVEN a type "person" with required property "name"
- WHEN a CREATE mutation includes a "title" property not in the definition
- THEN "title" is added to the type's optional properties
- AND the required properties remain unchanged
