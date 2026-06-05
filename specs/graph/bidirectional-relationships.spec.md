# Bidirectional Relationships

## Purpose
Relationship types in Kartograph are directed edges. Many bootstrap and query use cases need traversal from either endpoint without debating arrow direction at authoring time. This spec defines **paired relationship types** (primary + inverse) and **twin edge instances** so that every bidirectional relationship is materialized as two explicit graph edges with distinct labels, validated for parity, and visible in schema design artifacts.

This complements schema authoring: the Graph Management Assistant authors the primary direction; the platform materializes the inverse type and twin instances by default.

## Design principles

- **Explicit over implicit:** Twin edges are separate mutation log lines and separate AGE edges — auditable and idempotent.
- **Opt-out, not opt-in:** New relationship types default to bidirectional pairing. Causal or asymmetric relationships (e.g. `depends_on`, `created_by`) set `bidirectional: false`.
- **Distinct inverse labels:** Primary and inverse use different edge labels (e.g. `contains` / `contained_in`), not the same label reversed. Semantics and UI already assume this (`reverse_relationship_type` in design artifacts).
- **No hyperedge shortcut:** Pairing is always between two node types with one primary direction declared in ontology.

## Requirements

### Requirement: Bidirectional pairing metadata on relationship types
The system SHALL store bidirectional pairing metadata on canonical relationship type definitions.

#### Scenario: Default bidirectional on new relationship type
- GIVEN a new relationship type `Repository → contains → Test` is added to the ontology
- AND `bidirectional` is omitted
- WHEN the ontology is saved
- THEN the relationship type is stored with `bidirectional=true`
- AND an inverse relationship type is created or linked: `Test → contained_in → Repository` (inverse label derived or explicit)
- AND design artifacts expose `reverse_relationship_type` and `reverse_relationship_description` for the primary row

#### Scenario: Opt out of bidirectional pairing
- GIVEN a relationship type `Service → depends_on → Service` with `bidirectional=false`
- WHEN the ontology is saved
- THEN no inverse relationship type is auto-generated
- AND instance twin validation does not apply to that label

#### Scenario: Explicit inverse label
- GIVEN a primary relationship type with `bidirectional=true` and `inverse_label="housed_in"`
- WHEN the ontology is saved
- THEN the inverse type uses label `housed_in` with swapped `source_labels` and `target_labels`
- AND metadata links `inverse_of` on the inverse type back to the primary label

### Requirement: Inverse type materialization on ontology save
The system SHALL ensure every bidirectional primary relationship type has a corresponding inverse type definition before instances are created.

#### Scenario: Auto-generate missing inverse type
- GIVEN ontology save includes `repository|contains|test` as a bidirectional primary
- AND no inverse type exists yet
- WHEN save completes
- THEN canonical schema includes `test|contained_in|repository` (or explicit `inverse_label`)
- AND both types share pairing metadata (`bidirectional_pair_key`)

#### Scenario: Reject invalid inverse pairing
- GIVEN a relationship type references `inverse_label` that already exists with incompatible endpoints
- WHEN ontology save is attempted
- THEN validation fails with a clear error

### Requirement: Twin edge instances on CREATE
The system SHALL create paired edge instances for bidirectional relationship types when a primary edge instance is created.

#### Scenario: Primary CREATE expands to twin CREATE
- GIVEN bidirectional relationship `contains` from Repository node R to Test node T
- WHEN a CREATE edge mutation is applied for `R -[contains]-> T`
- THEN the mutation batch also CREATEs `T -[contained_in]-> R` in the same atomic apply
- AND both edges receive distinct deterministic ids
- AND inverse edge properties copy non-directional fields from the primary; directional fields may be omitted on the inverse

#### Scenario: Bulk JSONL primary-only input
- GIVEN a JSONL file with only primary-direction edge CREATE lines for bidirectional types
- WHEN mutations are validated or applied via workload tools
- THEN the preflight/expansion layer adds inverse CREATE lines before apply
- AND validate reports the expanded operation count

#### Scenario: Idempotent re-apply
- GIVEN twin edges for pair (R, T) already exist
- WHEN the same primary CREATE is submitted again under strict CREATE semantics
- THEN validation rejects the duplicate primary CREATE
- AND no orphan inverse edge is created

### Requirement: Twin instance validation
The system SHALL validate that bidirectional relationship instances exist in pairs.

#### Scenario: Readiness reports missing inverse instance
- GIVEN a bidirectional primary edge instance exists without its inverse twin
- WHEN workspace readiness or design artifacts are evaluated
- THEN a blocking or warning reason identifies the orphan primary edge (source slug, target slug, label)
- AND transition eligibility may be blocked when strict pairing mode is enabled for bootstrap

#### Scenario: Balanced pairing passes validation
- GIVEN every primary `contains` edge has a matching `contained_in` edge between the same node ids (reversed)
- WHEN twin validation runs
- THEN no pairing defects are reported

### Requirement: Authoring guidance
The system SHALL instruct the Graph Management Assistant to author primary direction only for bidirectional types.

#### Scenario: GMA authors one direction
- GIVEN schema bootstrap with bidirectional relationship types
- WHEN the assistant plans prepopulation
- THEN it emits generator output for the primary label only
- AND relies on platform twin expansion for inverse instances
- AND does not ask the user to confirm arrow direction when `bidirectional=true` unless `bidirectional=false` is set

## Data model (canonical type metadata)

Primary relationship type (`edge`, entity_type=edge):

| Field | Default | Meaning |
|-------|---------|---------|
| `bidirectional` | `true` | Whether twin inverse type + instances are required |
| `inverse_label` | derived | Label of inverse edge type; default `{primary}_inverse` or linguistic map |
| `bidirectional_pair_key` | derived | Stable key `source\|primary\|target` linking primary and inverse rows |

Inverse relationship type (auto-generated):

| Field | Meaning |
|-------|---------|
| `inverse_of` | Primary label this type mirrors |
| `bidirectional` | `true` |
| `auto_generated` | `true` — hide from GMA authoring prompts or show as read-only twin |

## Inverse label derivation (default)

When `inverse_label` is not provided and `bidirectional=true`:

1. Use a small built-in map for common verbs (`contains` → `contained_in`, `defines` → `defined_by`, `implements` → `implemented_by`).
2. Otherwise default to `{primary_label}_inverse` (snake_case).

Authors MAY override `inverse_label` in ontology JSON.

## Write path summary

```
Ontology save (Management → canonical schema)
  → pairing expander adds/updates inverse type definitions

Edge CREATE (Graph / Extraction workload)
  → twin expander adds inverse CREATE to batch
  → mutation applier executes both in one transaction

Readiness (Management / Extraction)
  → twin validator checks primary/inverse instance parity
```

## Read path summary

- **Design artifacts:** populate `reverse_relationship_type` from pairing metadata (UI already renders it).
- **Relationship listing:** workload list tools may group primary + inverse counts or report twin balance.
- **Queries:** agents traverse using the label appropriate to start node type; both directions always exist when bidirectional.

## Out of scope (initial tracer)

- Automatic linguistic inference beyond the small verb map.
- Symmetric edges with the **same** label in both directions (conflicts with distinct-semantics principle).
- Retroactive twin backfill job for graphs authored before this feature (separate migration spec).
- Graph query MCP auto-expanding undirected traversals (clients use explicit labels).

## Migration notes

- Existing ontologies without pairing metadata: treat as `bidirectional=false` until re-saved or migrated.
- Existing orphan edge instances: report in readiness; optional backfill command in a follow-up.
