---
id: task-131
title: "Management — OntologyConfig persistence: KnowledgeGraph aggregate, JSONB column, and GET/PUT endpoints"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(management): add OntologyConfig persistence to KnowledgeGraph aggregate with GET/PUT API"
pr_description: |
  ## What and Why

  The **Requirement: Ontology Design** in `specs/ui/experience.spec.md` requires that
  an approved ontology (node types, edge types, and their properties) be persisted
  per-KnowledgeGraph. Three spec scenarios depend on retrievable ontology storage:

  - **Ontology review and approval**: extraction begins only after the user
    explicitly approves — the approved ontology must be durably stored.
  - **Individual type editing**: label, description, required/optional properties,
    and relationship types can be modified — edits must be persisted and re-read.
  - **Ontology change after initial extraction**: the system warns that modifying an
    approved ontology triggers full re-extraction — this requires knowing whether
    an approved ontology already exists for the KG.

  This task is pure Management bounded-context work. It does NOT touch Extraction
  (AIHCM-174) — storing and retrieving the ontology is independent of the AI
  agent that proposes it. Once these endpoints exist, task-123 (UI Ontology Design)
  can use real API calls instead of hardcoded proposal data.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da` —
  **Requirement: Ontology Design**:

  - **Scenario: Ontology review and approval** — approved ontology stored via
    `PUT /management/knowledge-graphs/{id}/ontology` and returned by
    `GET /management/knowledge-graphs/{id}/ontology`.
  - **Scenario: Individual type editing** — edited ontology round-trips correctly
    through GET → mutate → PUT → GET.
  - **Scenario: Ontology change after initial extraction** — `GET` returns `200`
    with ontology when one exists (indicating prior approval), enabling the UI to
    show the re-extraction warning; returns `404` when no ontology has been saved.

  ## Design Decisions

  - **OntologyConfig as a value object** in the Management domain. It contains:
    - `node_types: list[NodeTypeDefinition]` — each with `label`, `description`,
      `required_properties`, and `optional_properties`.
    - `edge_types: list[EdgeTypeDefinition]` — each with `label`, `description`,
      `source_labels`, `target_labels`, and `properties`.
    - `approved_at: datetime | None` — set when the user approves; `None` means
      the proposal has been stored but not yet approved.

  - **KnowledgeGraph aggregate** gains an `ontology: OntologyConfig | None` field.
    Default is `None` (no ontology configured). The aggregate remains unchanged
    for all existing operations.

  - **Persistence**: a nullable `JSONB` column `ontology` on the `knowledge_graphs`
    table. Serialization/deserialization is handled in the repository layer — the
    domain never sees raw JSON.

  - **Endpoints**:
    - `GET /management/knowledge-graphs/{id}/ontology` — requires `view` permission;
      returns `200 OntologyConfigResponse` if ontology exists, `404` otherwise.
    - `PUT /management/knowledge-graphs/{id}/ontology` — requires `edit` permission;
      accepts `OntologyConfigRequest`; returns `200 OntologyConfigResponse` with
      the stored ontology. Performs a full replace (not a merge).

  - **No endpoint on data sources** — ontology is a KG-level concern, not a
    data-source concern. The current UI's `PATCH /management/data-sources/{id}`
    with `{ontology: ...}` is silently ignored and will be corrected in task-123.

  ## TDD Sequence (write tests before code)

  ### Unit tests (no infrastructure)

  1. `OntologyConfig` value object construction and serialization
     - Valid ontology round-trips through `to_dict()` / `from_dict()`
     - `node_types` and `edge_types` are both optional (empty list is valid)
     - `approved_at` is `None` by default

  2. `NodeTypeDefinition` and `EdgeTypeDefinition` value object validation
     - `label` is required and non-empty
     - `required_properties` and `optional_properties` are lists of strings
     - `source_labels` and `target_labels` are lists of strings (may be empty)

  3. `KnowledgeGraph` aggregate with ontology
     - `KnowledgeGraph.ontology` is `None` by default
     - `KnowledgeGraph.set_ontology(config)` updates the field and `updated_at`
     - `KnowledgeGraph.clear_ontology()` resets to `None` and `updated_at`

  4. `KnowledgeGraphRepository` — `save_ontology()` and `get_ontology()` unit-tested
     via a fake/in-memory repository

  ### Integration tests (requires DB)

  5. `GET /management/knowledge-graphs/{id}/ontology` — no ontology → 404
  6. `PUT /management/knowledge-graphs/{id}/ontology` → 200, body round-trips
  7. `GET /management/knowledge-graphs/{id}/ontology` — after PUT → 200 with data
  8. `PUT` requires `edit` permission → 403 for viewer
  9. `GET` requires `view` permission → 403 for unauthenticated
  10. `PUT` on non-existent KG → 404
  11. Full round-trip: PUT node+edge types, GET, assert all fields preserved

  ## Files / Areas Affected

  **Domain layer**
  - `src/api/management/domain/value_objects.py` — add `OntologyConfig`,
    `NodeTypeDefinition`, `EdgeTypeDefinition`
  - `src/api/management/domain/aggregates.py` — add `ontology` field to
    `KnowledgeGraph`; add `set_ontology()` and `clear_ontology()` methods

  **Repository / Infrastructure layer**
  - `src/api/management/infrastructure/knowledge_graph_repository.py` — add
    `save_ontology(kg_id, config)` and `get_ontology(kg_id)` methods using JSONB
    column
  - Alembic migration: add nullable `JSONB` column `ontology` to `knowledge_graphs`

  **Application layer**
  - `src/api/management/application/services/knowledge_graph_service.py` — add
    `get_ontology(user_id, kg_id)` and `save_ontology(user_id, kg_id, config)`
    with permission checks (view/edit respectively)

  **Presentation layer**
  - `src/api/management/presentation/knowledge_graphs/models.py` — add
    `NodeTypeDefinitionModel`, `EdgeTypeDefinitionModel`, `OntologyConfigRequest`,
    `OntologyConfigResponse`
  - `src/api/management/presentation/knowledge_graphs/routes.py` — add two routes:
    `GET /knowledge-graphs/{id}/ontology` and `PUT /knowledge-graphs/{id}/ontology`

  **Tests**
  - `src/api/tests/unit/management/test_ontology_value_objects.py` (new)
  - `src/api/tests/unit/management/test_knowledge_graph_aggregate_ontology.py` (new)
  - `src/api/tests/integration/management/test_ontology_endpoints.py` (new)

  ## How to Verify

  1. `PUT /management/knowledge-graphs/{kg_id}/ontology` with a valid body returns
     `200` and the response contains the stored ontology
  2. `GET /management/knowledge-graphs/{kg_id}/ontology` returns `200` with the
     same data after the PUT
  3. `GET` on a KG with no ontology returns `404`
  4. `PUT` with viewer credentials returns `403`
  5. All unit tests pass without infrastructure:
     `cd src/api && uv run pytest tests/unit/management/ -v`
  6. All integration tests pass against a dev instance:
     `cd src/api && uv run pytest tests/integration/management/test_ontology_endpoints.py -v -m integration`

  ## Caveats

  - The `ontology` JSONB column is nullable to preserve backward compatibility.
    All existing KG rows have `NULL`; the repository returns `None` for these.
  - Do not add a migration that backfills existing rows — `None` is valid and
    the `GET` endpoint intentionally returns `404` for un-configured KGs.
  - `approved_at` is stored inside the JSONB blob, not as a separate column.
    This avoids schema proliferation for a field used only by the UI state machine.
  - This task does NOT wire up ontology-driven extraction. When AIHCM-174 resolves,
    the Extraction context will call `GET /management/knowledge-graphs/{id}/ontology`
    to read the approved ontology and use it to guide extraction.
  - The existing `KnowledgeGraphResponse` is not changed — this PR only adds new
    endpoints; it does not embed ontology in the existing GET /knowledge-graphs/{id}
    response (avoids bloating the common response model).
---
