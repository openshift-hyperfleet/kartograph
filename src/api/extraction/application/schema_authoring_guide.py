"""Schema authoring guide shared by API workload tools and agent runtime skills."""

SCHEMA_AUTHORING_GUIDE = """
# Kartograph schema authoring (Graph Management Assistant)

Use the Kartograph schema tools — never probe undocumented HTTP routes.

## Workspace layout

| Path | Access | Purpose |
|------|--------|---------|
| `repository-files/<data_source>/` | read-only | Source repos for Glob/Grep/Read |
| `instance_generators/` | **writable** | `{label}.py` scanners + `out/*_instances.json(l)` |
| rest of workspace | **writable** | Session metadata, agent-authored files |

Never write to `/tmp` — files there are outside the sticky workspace and cannot be used with
apply-from-file. If `instance_generators/` is not writable, report the error; do not work around it.

Read `instance_generators/PREPOPULATION_WORKFLOW.md` for the numbered six-step entity pipeline,
relationship workflow, slug rules, batch sizes, and verification checklist.

Bundled platform scripts (do not edit): `entities_to_jsonl.py`, `relationships_to_jsonl.py`,
`preview_instances.py`, `scanner_common.py`.
Copy `_entity_scanner.example.py` to `{Label}.py` — **filename must match ontology label exactly**
(case-sensitive: `E2ETest.py`, not `e2etest.py`). Domain references: `instance_generators/examples/`.

## Bootstrap workflow (6 phases)

1. **Understand goals** — 3–5 questions the graph must answer.
2. **Workspace discovery** — Glob/Grep under `repository-files/`.
3. **Draft schema + Q&A** — types, properties, relationships; mark `prepopulated: true` where needed.
4. **Prepopulation planning** — which types get scanners (during design only).
5. **Save ontology** — after user confirms the full schema.
6. **Implement prepopulation** — one prepopulated label per turn (below).

## Prepopulation execution

Start prepopulation immediately **only when all are true**:

1. `kartograph_save_schema_ontology` succeeded.
2. `kartograph_get_workspace_readiness` returns **200** (not 500/503).
3. Readiness shows prepopulated gaps (`next_action` / `prepopulation_tasks` name a label).
4. No systemic server errors on schema tools in this session.

If readiness is unavailable after a successful schema save, **stop and report** — do not advance to
the next prepopulated label.

When readiness shows gaps and the checks above pass, **execute immediately** — do not ask permission.

**First prepopulated entity type only:** smoke-test the pipeline with 1–2 instances before the full
batch (`preview_instances.py --limit 2`, validate, apply, verify with
`kartograph_list_instances_by_type`). Then run the full scanner output.

**Entities** (all entity gaps before any relationship gap):

```bash
python3 instance_generators/E2ETest.py repository-files > instance_generators/out/E2ETest_instances.json
python3 instance_generators/preview_instances.py E2ETest --limit 5
python3 instance_generators/entities_to_jsonl.py E2ETest \\
  --data-source-id schema-bootstrap \\
  instance_generators/out/E2ETest_instances.json > instance_generators/out/E2ETest_instances.jsonl
# validate-from-file → apply-from-file path=instance_generators/out/E2ETest_instances.jsonl
```

**Relationships** (after entity slugs exist; name files `{source}_{rel}_{target}_instances.*`):

```bash
python3 instance_generators/repository_defines_test.py repository-files \\
  > instance_generators/out/repository_defines_test_instances.json
python3 instance_generators/relationships_to_jsonl.py defines repository test \\
  instance_generators/out/repository_defines_test_instances.json \\
  > instance_generators/out/repository_defines_test_instances.jsonl
```

Scanner stdout contract:
- Entities: `[{"slug": "...", "properties": {...}}]`
- Relationships: `[{"source_slug": "...", "target_slug": "...", "properties": {}}]`

## Schema modeling rules

- **Property vs entity:** categorize → property; track instances/relationships → entity + edges.
- **Bidirectional relationships** default on — author **one primary direction only** in `edge_types`.
  Set optional `inverse_label` (default `{label}_inverse`). Never add a separate inverse type;
  the platform auto-generates it and twin edge instances. Design artifacts show
  `primary / inverse` on a single row.
- Set `bidirectional: false` only for asymmetric edges (`depends_on`, `created_by`).

## Workspace discovery patterns

| Target | Glob / Grep hints |
|--------|-------------------|
| Tests | `**/*_test.go`, `**/test_*.go`, `**/*_test.py` |
| API endpoints | route registrations, `@app.`, `HandleFunc`, OpenAPI paths |
| Source files | `Glob **/*.{go,py,ts,java,yaml,md}` per data source |

## Tool workflow

1. `kartograph_get_schema_authoring_guide` · `kartograph_get_workspace_readiness` · `kartograph_get_schema_ontology`
2. `kartograph_save_schema_ontology` when schema is confirmed
3. Prepopulation pipeline above per gap
4. `kartograph_validate_graph_mutations_from_file` → `kartograph_apply_graph_mutations_from_file`
5. Verify with `kartograph_list_instances_by_type` and readiness

## Entity type shape

```json
{
  "label": "test",
  "description": "Automated test file",
  "required_properties": ["name"],
  "optional_properties": ["file_path"],
  "prepopulated": true,
  "prepopulated_instance_count": 0
}
```

Scanner script convention: `instance_generators/{Label}.py` → `out/{Label}_instances.json`
(case-sensitive `{Label}` matching ontology).

## Slug and property rules

- Slugs: lowercase snake_case via `scanner_common.generate_slug()`; dedupe with `dedupe_instances()`.
- Required properties: see `required_properties` on each type in ontology/readiness — include in every instance.
- Optional properties: omit or use empty defaults when source data is incomplete.
- Single deliverable (one entity type): run the full pipeline without stopping.
- Multiple deliverables: one label per turn, then report and continue.

## Relationship type shape

```json
{
  "label": "exercises",
  "source_labels": ["ComponentTest"],
  "target_labels": ["APIEndpoint"],
  "prepopulated": true,
  "bidirectional": true,
  "inverse_label": "exercises_inverse"
}
```

Do **not** also add `exercises_inverse` as its own `edge_types` entry — that inverse is auto-generated on save.

Relationship scanner convention: `out/{source}_{label}_{target}_instances.json` (primary direction only).

## Instance mutations (JSONL)

- CREATE requires `data_source_id` and `slug` on nodes. Put `source_path` in scanner `properties` when needed.
- CREATE is strict — use UPDATE for existing instances.
- Never hand-author bulk CREATE lines in chat; use `entities_to_jsonl.py` / `relationships_to_jsonl.py`.
- Create all entity nodes before relationship edges.

## Readiness checklist

- Every `prepopulated=true` entity type needs ≥1 live instance.
- Every `prepopulated=true` relationship type needs ≥1 live edge.
- Prepopulated relationships may only reference prepopulated entity types.

Call `kartograph_get_workspace_readiness` for gaps, `next_action`, `prepopulation_tasks`, and `blocking_reasons`.

## Failure modes (schema tools)

Classify outcomes before continuing prepopulation:

| Outcome | Meaning | Action |
|---------|---------|--------|
| 422 + validation errors | Ontology or JSONL issue | Fix payload; retry |
| 422 on save | Authoring issue | Fix ontology draft |
| **500 or 503 on readiness/apply after validate passed** | **Platform / graph storage** | **Stop; report; do not continue to next label** |
| 500 on multiple schema endpoints | Systemic infra | Stop; suggest dev repair or env restart |

**Validation vs apply:** If `kartograph_validate_graph_mutations_from_file` passes and
`kartograph_apply_graph_mutations_from_file` returns 500/503, that is a **backend bug** — not bad
JSONL. Report validation success and apply failure together. Do not retry in a loop or skip to the
next entity type.

**`approved_at`:** Optional metadata on save. `null` is valid and does **not** block prepopulation.
Only pass `approved_at` when the user explicitly approved a timestamp.

**Do not** conflate schema design, prepopulation planning, and implementation in one turn when the
user listed multiple deliverables — but **do** stop all implementation when graph tools return
systemic server errors.
""".strip()
