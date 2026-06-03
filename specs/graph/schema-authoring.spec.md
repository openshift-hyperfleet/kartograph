# Schema Authoring

## Purpose
Schema authoring defines how entity and relationship type definitions are created and evolved in the graph through mutation logs. It supports a bootstrap flow for first-time schema establishment and ongoing schema evolution during extraction operations.

## Requirements

### Requirement: Graph-Native Type Definitions
The system SHALL treat graph-stored type definitions as the canonical schema source.

#### Scenario: Canonical storage
- GIVEN schema mutations are applied
- WHEN entity and relationship type definitions are persisted
- THEN canonical schema state is stored in the graph schema layer
- AND no parallel "design artifact" source of truth is required

### Requirement: Bootstrap Authoring Flow
The system SHALL support schema authoring during `schema_bootstrap` mode through mutation logs.

#### Scenario: Bootstrap schema creation
- GIVEN a knowledge graph in `schema_bootstrap`
- WHEN an agent or user creates entity and relationship types
- THEN changes are written via mutation logs
- AND resulting graph schema reflects those mutations

#### Scenario: Capabilities-driven start
- GIVEN a new bootstrap session
- WHEN the schema agent starts
- THEN it asks for user capabilities/goals
- AND it offers two paths: an immediate first-pass schema attempt, or guided question-by-question co-design

### Requirement: Ongoing Schema Evolution
The system SHALL allow schema updates during `extraction_operations` mode.

#### Scenario: Additive schema change in extraction mode
- GIVEN a knowledge graph in `extraction_operations`
- WHEN a user or agent adds a new property or type
- THEN the change is accepted through mutation logs
- AND extraction operations continue using the updated schema

### Requirement: Prepopulated Type Semantics
The system SHALL enforce `prepopulated=true` as a transition-blocking readiness constraint for entity and relationship types.

#### Scenario: Prepopulated entity type with instances
- GIVEN an entity type marked `prepopulated=true`
- WHEN readiness is evaluated
- THEN the type passes only if it has one or more instances

#### Scenario: Prepopulated entity type without instances
- GIVEN an entity type marked `prepopulated=true` with zero instances
- WHEN readiness is evaluated
- THEN validation fails and transition to extraction mode is blocked

#### Scenario: Prepopulated relationship type with prepopulated endpoints
- GIVEN a relationship type marked `prepopulated=true`
- AND every listed source and target entity type is marked `prepopulated=true`
- WHEN the ontology is saved
- THEN the save succeeds

#### Scenario: Prepopulated relationship type without prepopulated endpoints
- GIVEN a relationship type marked `prepopulated=true`
- AND at least one source or target entity type is not marked `prepopulated=true`
- WHEN the ontology is saved
- THEN validation fails with a clear error

#### Scenario: Prepopulated relationship type without instances
- GIVEN a relationship type marked `prepopulated=true` with zero instances
- WHEN readiness is evaluated
- THEN validation fails and transition to extraction mode is blocked

