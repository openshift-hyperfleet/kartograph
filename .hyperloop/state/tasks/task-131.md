---
id: task-131
title: 'Management — OntologyConfig persistence: KnowledgeGraph aggregate, JSONB column,
  and GET/PUT endpoints'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: verify
deps: []
round: 0
branch: hyperloop/task-131
pr: https://github.com/openshift-hyperfleet/kartograph/pull/591
pr_title: 'feat(management): add OntologyConfig persistence to KnowledgeGraph aggregate
  with GET/PUT API'
pr_description: "## What and Why\n\nThe **Requirement: Ontology Design** in `specs/ui/experience.spec.md`\
  \ requires that\nan approved ontology (node types, edge types, and their properties)\
  \ be persisted\nper-KnowledgeGraph. Three spec scenarios depend on retrievable ontology\
  \ storage:\n\n- **Ontology review and approval**: extraction begins only after the\
  \ user\n  explicitly approves — the approved ontology must be durably stored.\n\
  - **Individual type editing**: label, description, required/optional properties,\n\
  \  and relationship types can be modified — edits must be persisted and re-read.\n\
  - **Ontology change after initial extraction**: the system warns that modifying\
  \ an\n  approved ontology triggers full re-extraction — this requires knowing whether\n\
  \  an approved ontology already exists for the KG.\n\nThis task is pure Management\
  \ bounded-context work. It does NOT touch Extraction\n(AIHCM-174) — storing and\
  \ retrieving the ontology is independent of the AI\nagent that proposes it. Once\
  \ these endpoints exist, task-123 (UI Ontology Design)\ncan use real API calls instead\
  \ of hardcoded proposal data.\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`\
  \ —\n**Requirement: Ontology Design**:\n\n- **Scenario: Ontology review and approval**\
  \ — approved ontology stored via\n  `PUT /management/knowledge-graphs/{id}/ontology`\
  \ and returned by\n  `GET /management/knowledge-graphs/{id}/ontology`.\n- **Scenario:\
  \ Individual type editing** — edited ontology round-trips correctly\n  through GET\
  \ → mutate → PUT → GET.\n- **Scenario: Ontology change after initial extraction**\
  \ — `GET` returns `200`\n  with ontology when one exists (indicating prior approval),\
  \ enabling the UI to\n  show the re-extraction warning; returns `404` when no ontology\
  \ has been saved.\n\n## Design Decisions\n\n- **OntologyConfig as a value object**\
  \ in the Management domain. It contains:\n  - `node_types: list[NodeTypeDefinition]`\
  \ — each with `label`, `description`,\n    `required_properties`, and `optional_properties`.\n\
  \  - `edge_types: list[EdgeTypeDefinition]` — each with `label`, `description`,\n\
  \    `source_labels`, `target_labels`, and `properties`.\n  - `approved_at: datetime\
  \ | None` — set when the user approves; `None` means\n    the proposal has been\
  \ stored but not yet approved.\n\n- **KnowledgeGraph aggregate** gains an `ontology:\
  \ OntologyConfig | None` field.\n  Default is `None` (no ontology configured). The\
  \ aggregate remains unchanged\n  for all existing operations.\n\n- **Persistence**:\
  \ a nullable `JSONB` column `ontology` on the `knowledge_graphs`\n  table. Serialization/deserialization\
  \ is handled in the repository layer — the\n  domain never sees raw JSON.\n\n- **Endpoints**:\n\
  \  - `GET /management/knowledge-graphs/{id}/ontology` — requires `view` permission;\n\
  \    returns `200 OntologyConfigResponse` if ontology exists, `404` otherwise.\n\
  \  - `PUT /management/knowledge-graphs/{id}/ontology` — requires `edit` permission;\n\
  \    accepts `OntologyConfigRequest`; returns `200 OntologyConfigResponse` with\n\
  \    the stored ontology. Performs a full replace (not a merge).\n\n- **No endpoint\
  \ on data sources** — ontology is a KG-level concern, not a\n  data-source concern.\
  \ The current UI's `PATCH /management/data-sources/{id}`\n  with `{ontology: ...}`\
  \ is silently ignored and will be corrected in task-123.\n\n## TDD Sequence (write\
  \ tests before code)\n\n### Unit tests (no infrastructure)\n\n1. `OntologyConfig`\
  \ value object construction and serialization\n   - Valid ontology round-trips through\
  \ `to_dict()` / `from_dict()`\n   - `node_types` and `edge_types` are both optional\
  \ (empty list is valid)\n   - `approved_at` is `None` by default\n\n2. `NodeTypeDefinition`\
  \ and `EdgeTypeDefinition` value object validation\n   - `label` is required and\
  \ non-empty\n   - `required_properties` and `optional_properties` are lists of strings\n\
  \   - `source_labels` and `target_labels` are lists of strings (may be empty)\n\n\
  3. `KnowledgeGraph` aggregate with ontology\n   - `KnowledgeGraph.ontology` is `None`\
  \ by default\n   - `KnowledgeGraph.set_ontology(config)` updates the field and `updated_at`\n\
  \   - `KnowledgeGraph.clear_ontology()` resets to `None` and `updated_at`\n\n4.\
  \ `KnowledgeGraphRepository` — `save_ontology()` and `get_ontology()` unit-tested\n\
  \   via a fake/in-memory repository\n\n### Integration tests (requires DB)\n\n5.\
  \ `GET /management/knowledge-graphs/{id}/ontology` — no ontology → 404\n6. `PUT\
  \ /management/knowledge-graphs/{id}/ontology` → 200, body round-trips\n7. `GET /management/knowledge-graphs/{id}/ontology`\
  \ — after PUT → 200 with data\n8. `PUT` requires `edit` permission → 403 for viewer\n\
  9. `GET` requires `view` permission → 403 for unauthenticated\n10. `PUT` on non-existent\
  \ KG → 404\n11. Full round-trip: PUT node+edge types, GET, assert all fields preserved\n\
  \n## Files / Areas Affected\n\n**Domain layer**\n- `src/api/management/domain/value_objects.py`\
  \ — add `OntologyConfig`,\n  `NodeTypeDefinition`, `EdgeTypeDefinition`\n- `src/api/management/domain/aggregates.py`\
  \ — add `ontology` field to\n  `KnowledgeGraph`; add `set_ontology()` and `clear_ontology()`\
  \ methods\n\n**Repository / Infrastructure layer**\n- `src/api/management/infrastructure/knowledge_graph_repository.py`\
  \ — add\n  `save_ontology(kg_id, config)` and `get_ontology(kg_id)` methods using\
  \ JSONB\n  column\n- Alembic migration: add nullable `JSONB` column `ontology` to\
  \ `knowledge_graphs`\n\n**Application layer**\n- `src/api/management/application/services/knowledge_graph_service.py`\
  \ — add\n  `get_ontology(user_id, kg_id)` and `save_ontology(user_id, kg_id, config)`\n\
  \  with permission checks (view/edit respectively)\n\n**Presentation layer**\n-\
  \ `src/api/management/presentation/knowledge_graphs/models.py` — add\n  `NodeTypeDefinitionModel`,\
  \ `EdgeTypeDefinitionModel`, `OntologyConfigRequest`,\n  `OntologyConfigResponse`\n\
  - `src/api/management/presentation/knowledge_graphs/routes.py` — add two routes:\n\
  \  `GET /knowledge-graphs/{id}/ontology` and `PUT /knowledge-graphs/{id}/ontology`\n\
  \n**Tests**\n- `src/api/tests/unit/management/test_ontology_value_objects.py` (new)\n\
  - `src/api/tests/unit/management/test_knowledge_graph_aggregate_ontology.py` (new)\n\
  - `src/api/tests/integration/management/test_ontology_endpoints.py` (new)\n\n##\
  \ How to Verify\n\n1. `PUT /management/knowledge-graphs/{kg_id}/ontology` with a\
  \ valid body returns\n   `200` and the response contains the stored ontology\n2.\
  \ `GET /management/knowledge-graphs/{kg_id}/ontology` returns `200` with the\n \
  \  same data after the PUT\n3. `GET` on a KG with no ontology returns `404`\n4.\
  \ `PUT` with viewer credentials returns `403`\n5. All unit tests pass without infrastructure:\n\
  \   `cd src/api && uv run pytest tests/unit/management/ -v`\n6. All integration\
  \ tests pass against a dev instance:\n   `cd src/api && uv run pytest tests/integration/management/test_ontology_endpoints.py\
  \ -v -m integration`\n\n## Caveats\n\n- The `ontology` JSONB column is nullable\
  \ to preserve backward compatibility.\n  All existing KG rows have `NULL`; the repository\
  \ returns `None` for these.\n- Do not add a migration that backfills existing rows\
  \ — `None` is valid and\n  the `GET` endpoint intentionally returns `404` for un-configured\
  \ KGs.\n- `approved_at` is stored inside the JSONB blob, not as a separate column.\n\
  \  This avoids schema proliferation for a field used only by the UI state machine.\n\
  - This task does NOT wire up ontology-driven extraction. When AIHCM-174 resolves,\n\
  \  the Extraction context will call `GET /management/knowledge-graphs/{id}/ontology`\n\
  \  to read the approved ontology and use it to guide extraction.\n- The existing\
  \ `KnowledgeGraphResponse` is not changed — this PR only adds new\n  endpoints;\
  \ it does not embed ontology in the existing GET /knowledge-graphs/{id}\n  response\
  \ (avoids bloating the common response model)."
---
