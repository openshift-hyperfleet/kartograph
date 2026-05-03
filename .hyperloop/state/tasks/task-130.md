---
id: task-130
title: "Management: DataSource ontology storage (domain → API)"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(management): add ontology field to DataSource aggregate and API"
pr_description: |
  ## Summary

  The UI's Ontology Design flow (data-sources page) is fully implemented in the
  frontend but has no backend support. When a user:
  - Approves a proposed ontology after the agent-scan step, or
  - Edits an existing ontology via the ontology editor dialog

  …the backend silently discards the `ontology` payload because `DataSource`
  has no ontology field in the domain, repository, or API layer. The UI even
  comments this explicitly: *"Pre-populate with the GitHub proposal as a
  stand-in for the stored ontology. In a real implementation this would load
  from the server."*

  This PR adds end-to-end ontology storage to the Management bounded context.

  ## What this change does

  ### Domain (Management)
  - Add `OntologyNodeType` and `OntologyEdgeType` value objects (label,
    description, required_properties, optional_properties; edge type adds
    from_type and to_type).
  - Add `Ontology` value object that aggregates a list of node types and edge
    types. An empty `Ontology` (no types defined) is valid.
  - Add `ontology: Ontology | None` field to the `DataSource` aggregate
    (None = no ontology approved yet).
  - Add `update_ontology(ontology: Ontology)` method on `DataSource` that
    replaces the stored ontology and emits `DataSourceUpdated`.

  ### Infrastructure (Management)
  - Update `DataSourceRepository` to persist and load the `ontology` field.
    Store as JSONB in the existing `data_sources` table (new nullable column
    `ontology_json`).
  - Add a database migration for the new column.

  ### Application (Management)
  - Add `update_ontology(user_id, ds_id, ontology)` to `DataSourceService`.
    Authorises via `edit` permission on the data source.

  ### Presentation (Management)
  - Add `OntologyNodeTypeModel`, `OntologyEdgeTypeModel`, and `OntologyModel`
    Pydantic models.
  - Add `ontology: OntologyModel | None` to `CreateDataSourceRequest` (so
    the initial approval step can include the proposed ontology).
  - Add `ontology: OntologyModel | None` to `UpdateDataSourceRequest`.
  - Add `ontology: OntologyModel | None` to `DataSourceResponse`.
  - Wire the `PATCH /data-sources/{ds_id}` handler to call
    `service.update_ontology(...)` when the `ontology` field is present.
  - Wire the `POST /data-sources` handler to attach the ontology to the new
    data source when `ontology` is provided at creation time.

  ## Spec requirements satisfied

  From `specs/ui/experience.spec.md` — **Requirement: Ontology Design**:

  - **Scenario: Ontology review and approval** — `POST /data-sources` now
    accepts the proposed ontology so it is stored when the user approves.
  - **Scenario: Individual type editing** — `PATCH /data-sources/{id}` now
    accepts `{ontology: {...}}` and persists the updated types, making the
    existing UI `saveOntology()` call functional.
  - **Scenario: Ontology change after initial extraction** — `DataSourceResponse`
    now returns the stored ontology, allowing the UI to populate the editor
    from the server rather than from hardcoded fixture data.

  Note: **Scenario: Agent-proposed ontology** and **Scenario: Intent
  description** (the AI-driven scan + proposal backend) remain out of scope;
  they depend on Extraction context work blocked by AIHCM-174.

  ## Key design decisions

  - **JSONB column**: Ontology is schema-flexible (arbitrary property names)
    and read back as a whole; JSONB is the right fit over normalised tables.
  - **Nullable at domain level**: An empty/null ontology is valid — most data
    sources will start without one and gain it after the agent-proposal step.
  - **No new endpoint**: Ontology updates flow through the existing PATCH
    endpoint to keep the API surface minimal; the new field is purely additive.
  - **No extraction trigger here**: Triggering re-extraction when ontology
    changes is Extraction-context responsibility and is deferred to AIHCM-174.

  ## Files / areas affected

  - `management/domain/value_objects.py` — new value objects
  - `management/domain/aggregates/data_source.py` — new field + method
  - `management/infrastructure/repositories/data_source_repository.py`
  - `migrations/versions/<new_migration>.py`
  - `management/application/services/data_source_service.py`
  - `management/presentation/data_sources/models.py`
  - `management/presentation/data_sources/routes.py`
  - `tests/unit/management/**` — new TDD unit tests for each layer
  - `tests/integration/management/**` — integration test covering the full
    create-with-ontology and patch-ontology round-trips

  ## How to verify

  1. `make test-unit` passes with new domain and service tests.
  2. `make test-integration` passes — specifically:
     - `POST /data-sources` with `ontology` stores and returns it.
     - `GET /data-sources/{id}` returns the stored ontology.
     - `PATCH /data-sources/{id}` with `{ontology: {...}}` updates and
       returns the new ontology.
  3. Open the dev UI, add a GitHub data source, complete the ontology-proposal
     step, approve — then view the data source and click "Edit ontology". The
     editor should populate from the server, not from fixture data.

  ## Caveats / follow-up

  - Re-extraction trigger on ontology change deferred to AIHCM-174 (Extraction
    context spike).
  - The simulated agent scan in the frontend (GITHUB_PROPOSAL_NODES/EDGES)
    will be replaced by a real backend scan endpoint in a future task, also
    gated on AIHCM-174.
---
