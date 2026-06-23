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

### Requirement: Opinionated Bootstrap Workflow
The system SHALL guide the Graph Management Assistant through a six-phase schema bootstrap workflow.

#### Scenario: Goals before schema
- GIVEN a new schema bootstrap conversation
- WHEN the assistant begins intake
- THEN it asks for questions the graph must answer before proposing entity types

#### Scenario: Phased bootstrap guidance
- GIVEN schema bootstrap skills are resolved for a graph-management turn
- WHEN the agent system prompt is assembled
- THEN it includes the six phases: goals, discovery, schema Q&A, prepopulation planning, confirmed save, bulk implementation

#### Scenario: Confirmed ontology save
- GIVEN the assistant has drafted a schema but the user has not confirmed it
- WHEN the assistant considers persisting types
- THEN guardrails require waiting for explicit user confirmation before `kartograph_save_schema_ontology`

#### Scenario: Property versus entity modeling guidance
- GIVEN schema bootstrap skills are resolved
- WHEN the assistant models attributes
- THEN skills distinguish categorize/distinguish → property from track-which/needs-relationships → entity type

#### Scenario: Workspace discovery before prepopulation
- GIVEN the assistant enters prepopulation planning
- WHEN skills are resolved
- THEN prepopulation guidance requires Glob/Grep discovery on `repository-files/` first

#### Scenario: Execute-first prepopulation after schema save
- GIVEN the ontology is saved and readiness shows prepopulated entity or relationship gaps
- WHEN the Graph Management Assistant continues schema bootstrap
- THEN it executes one prepopulation task per turn via generator script and apply-from-file
- AND does not ask the user for permission to proceed unless strategy is ambiguous or CREATE is rejected

#### Scenario: Entities before relationships during prepopulation
- GIVEN readiness shows both prepopulated entity gaps and prepopulated relationship gaps
- WHEN the assistant implements prepopulation
- THEN it authors and runs entity scanner scripts for every entity gap before any relationship scanner
- AND each scanner discovers instances across all `repository-files/` data sources

### Requirement: Workload Bulk Instance Authoring
The system SHALL support bulk instance authoring for the Graph Management Assistant via workspace files and strict CREATE semantics.

#### Scenario: Dry-run mutation validation
- GIVEN a JSONL batch of mutation lines for one knowledge graph
- WHEN the assistant calls workload mutation validate
- THEN the system returns validation errors without writing to the graph
- AND CREATE lines that target existing instance ids or slugs are rejected

#### Scenario: Apply mutations from workspace file
- GIVEN a JSONL file under the sticky session workspace mount
- WHEN the assistant applies mutations from that file path
- THEN the system reads the full file and applies all valid operations in one request

#### Scenario: Session workspace generator templates
- GIVEN a sticky session work directory is prepared
- WHEN the assistant lists `instance_generators/`
- THEN `_entity_scanner.example.py`, `entities_to_jsonl.py`, and `relationships_to_jsonl.py` are present
- AND the assistant authors `{label}.py` scanners that emit `out/{label}_instances.json`

#### Scenario: Batch entity prepopulation pipeline
- GIVEN a prepopulated entity type with a readiness gap
- WHEN the assistant runs `{label}.py` and `entities_to_jsonl.py`
- THEN it produces `instance_generators/out/{label}_instances.jsonl`
- AND applies all CREATE lines in one validate/apply-from-file batch

### Requirement: Bidirectional Relationship Pairing
The system SHALL default new relationship types to bidirectional pairing. See [Bidirectional Relationships](bidirectional-relationships.spec.md).

#### Scenario: Ontology save creates inverse type
- GIVEN a primary relationship type with `bidirectional=true`
- WHEN the ontology is saved
- THEN the inverse relationship type is stored with swapped endpoints

#### Scenario: Primary edge CREATE expands to twin
- GIVEN a bidirectional relationship type exists in the ontology
- WHEN a primary-direction edge CREATE mutation is applied via workload tools
- THEN an inverse edge CREATE is applied in the same batch

