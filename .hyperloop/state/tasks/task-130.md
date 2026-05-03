---
id: task-130
title: 'Management: DataSource ontology storage (domain → API)'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: implement
deps: []
round: 0
branch: hyperloop/task-130
pr: null
pr_title: 'feat(management): add ontology field to DataSource aggregate and API'
pr_description: "## Summary\n\nThe UI's Ontology Design flow (data-sources page) is\
  \ fully implemented in the\nfrontend but has no backend support. When a user:\n\
  - Approves a proposed ontology after the agent-scan step, or\n- Edits an existing\
  \ ontology via the ontology editor dialog\n\n…the backend silently discards the\
  \ `ontology` payload because `DataSource`\nhas no ontology field in the domain,\
  \ repository, or API layer. The UI even\ncomments this explicitly: *\"Pre-populate\
  \ with the GitHub proposal as a\nstand-in for the stored ontology. In a real implementation\
  \ this would load\nfrom the server.\"*\n\nThis PR adds end-to-end ontology storage\
  \ to the Management bounded context.\n\n## What this change does\n\n### Domain (Management)\n\
  - Add `OntologyNodeType` and `OntologyEdgeType` value objects (label,\n  description,\
  \ required_properties, optional_properties; edge type adds\n  from_type and to_type).\n\
  - Add `Ontology` value object that aggregates a list of node types and edge\n  types.\
  \ An empty `Ontology` (no types defined) is valid.\n- Add `ontology: Ontology |\
  \ None` field to the `DataSource` aggregate\n  (None = no ontology approved yet).\n\
  - Add `update_ontology(ontology: Ontology)` method on `DataSource` that\n  replaces\
  \ the stored ontology and emits `DataSourceUpdated`.\n\n### Infrastructure (Management)\n\
  - Update `DataSourceRepository` to persist and load the `ontology` field.\n  Store\
  \ as JSONB in the existing `data_sources` table (new nullable column\n  `ontology_json`).\n\
  - Add a database migration for the new column.\n\n### Application (Management)\n\
  - Add `update_ontology(user_id, ds_id, ontology)` to `DataSourceService`.\n  Authorises\
  \ via `edit` permission on the data source.\n\n### Presentation (Management)\n-\
  \ Add `OntologyNodeTypeModel`, `OntologyEdgeTypeModel`, and `OntologyModel`\n  Pydantic\
  \ models.\n- Add `ontology: OntologyModel | None` to `CreateDataSourceRequest` (so\n\
  \  the initial approval step can include the proposed ontology).\n- Add `ontology:\
  \ OntologyModel | None` to `UpdateDataSourceRequest`.\n- Add `ontology: OntologyModel\
  \ | None` to `DataSourceResponse`.\n- Wire the `PATCH /data-sources/{ds_id}` handler\
  \ to call\n  `service.update_ontology(...)` when the `ontology` field is present.\n\
  - Wire the `POST /data-sources` handler to attach the ontology to the new\n  data\
  \ source when `ontology` is provided at creation time.\n\n## Spec requirements satisfied\n\
  \nFrom `specs/ui/experience.spec.md` — **Requirement: Ontology Design**:\n\n- **Scenario:\
  \ Ontology review and approval** — `POST /data-sources` now\n  accepts the proposed\
  \ ontology so it is stored when the user approves.\n- **Scenario: Individual type\
  \ editing** — `PATCH /data-sources/{id}` now\n  accepts `{ontology: {...}}` and\
  \ persists the updated types, making the\n  existing UI `saveOntology()` call functional.\n\
  - **Scenario: Ontology change after initial extraction** — `DataSourceResponse`\n\
  \  now returns the stored ontology, allowing the UI to populate the editor\n  from\
  \ the server rather than from hardcoded fixture data.\n\nNote: **Scenario: Agent-proposed\
  \ ontology** and **Scenario: Intent\ndescription** (the AI-driven scan + proposal\
  \ backend) remain out of scope;\nthey depend on Extraction context work blocked\
  \ by AIHCM-174.\n\n## Key design decisions\n\n- **JSONB column**: Ontology is schema-flexible\
  \ (arbitrary property names)\n  and read back as a whole; JSONB is the right fit\
  \ over normalised tables.\n- **Nullable at domain level**: An empty/null ontology\
  \ is valid — most data\n  sources will start without one and gain it after the agent-proposal\
  \ step.\n- **No new endpoint**: Ontology updates flow through the existing PATCH\n\
  \  endpoint to keep the API surface minimal; the new field is purely additive.\n\
  - **No extraction trigger here**: Triggering re-extraction when ontology\n  changes\
  \ is Extraction-context responsibility and is deferred to AIHCM-174.\n\n## Files\
  \ / areas affected\n\n- `management/domain/value_objects.py` — new value objects\n\
  - `management/domain/aggregates/data_source.py` — new field + method\n- `management/infrastructure/repositories/data_source_repository.py`\n\
  - `migrations/versions/<new_migration>.py`\n- `management/application/services/data_source_service.py`\n\
  - `management/presentation/data_sources/models.py`\n- `management/presentation/data_sources/routes.py`\n\
  - `tests/unit/management/**` — new TDD unit tests for each layer\n- `tests/integration/management/**`\
  \ — integration test covering the full\n  create-with-ontology and patch-ontology\
  \ round-trips\n\n## How to verify\n\n1. `make test-unit` passes with new domain\
  \ and service tests.\n2. `make test-integration` passes — specifically:\n   - `POST\
  \ /data-sources` with `ontology` stores and returns it.\n   - `GET /data-sources/{id}`\
  \ returns the stored ontology.\n   - `PATCH /data-sources/{id}` with `{ontology:\
  \ {...}}` updates and\n     returns the new ontology.\n3. Open the dev UI, add a\
  \ GitHub data source, complete the ontology-proposal\n   step, approve — then view\
  \ the data source and click \"Edit ontology\". The\n   editor should populate from\
  \ the server, not from fixture data.\n\n## Caveats / follow-up\n\n- Re-extraction\
  \ trigger on ontology change deferred to AIHCM-174 (Extraction\n  context spike).\n\
  - The simulated agent scan in the frontend (GITHUB_PROPOSAL_NODES/EDGES)\n  will\
  \ be replaced by a real backend scan endpoint in a future task, also\n  gated on\
  \ AIHCM-174."
---
