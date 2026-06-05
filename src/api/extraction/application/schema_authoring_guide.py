"""Schema authoring guide shared by API workload tools and agent runtime skills."""

SCHEMA_AUTHORING_GUIDE = """
# Kartograph schema authoring (Graph Management Assistant)

Use the Kartograph schema tools — never probe undocumented HTTP routes.

## Workspace layout

| Path | Access | Purpose |
|------|--------|---------|
| `repository-files/<data_source>/` | read-only | Source repos for Glob/Grep/Read |
| `ingestion-context/` | read-only | Sync metadata |
| `instance_generators/` | **writable** | `{label}.py` scanners + `out/*_instances.json(l)` |

Never write to `/tmp`. Apply-from-file paths must be under `instance_generators/out/`
(e.g. `instance_generators/out/test_instances.jsonl`).

Bundled platform scripts (do not edit): `entities_to_jsonl.py`, `relationships_to_jsonl.py`.
Copy `_entity_scanner.example.py` to `{label}.py` for each prepopulated type.

## Bootstrap workflow (6 phases)

1. **Understand goals** — 3–5 questions the graph must answer.
2. **Workspace discovery** — Glob/Grep under `repository-files/`.
3. **Draft schema + Q&A** — types, properties, relationships; mark `prepopulated: true` where needed.
4. **Prepopulation planning** — which types get scanners (during design only).
5. **Save ontology** — after user confirms the full schema.
6. **Implement prepopulation** — one prepopulated label per turn (below).

## Prepopulation execution

When `kartograph_get_workspace_readiness` shows gaps after ontology save, **execute immediately**.

**Entities** (all entity gaps before any relationship gap):

```bash
python3 instance_generators/test.py repository-files > instance_generators/out/test_instances.json
python3 instance_generators/entities_to_jsonl.py test \\
  --data-source-id schema-bootstrap --source-path graph-management-assistant \\
  instance_generators/out/test_instances.json > instance_generators/out/test_instances.jsonl
# validate-from-file → apply-from-file path=instance_generators/out/test_instances.jsonl
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
- **Bidirectional relationships** default on — author primary direction only; platform creates inverse + twins.
- Set `bidirectional: false` for asymmetric edges (`depends_on`, `created_by`).

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

Scanner script convention: `instance_generators/{label}.py` → `out/{label}_instances.json`.

## Relationship type shape

```json
{
  "label": "defines",
  "source_labels": ["repository"],
  "target_labels": ["api_endpoint"],
  "prepopulated": true,
  "bidirectional": true
}
```

Relationship scanner convention: `out/{source}_{label}_{target}_instances.json`.

## Instance mutations (JSONL)

- CREATE requires `data_source_id` and `slug` on nodes. Add `source_path` only when provenance matters.
- CREATE is strict — use UPDATE for existing instances.
- Never hand-author bulk CREATE lines in chat; use `entities_to_jsonl.py` / `relationships_to_jsonl.py`.
- Create all entity nodes before relationship edges.

## Readiness checklist

- Every `prepopulated=true` entity type needs ≥1 live instance.
- Every `prepopulated=true` relationship type needs ≥1 live edge.
- Prepopulated relationships may only reference prepopulated entity types.

Call `kartograph_get_workspace_readiness` for gaps and `blocking_reasons`.
""".strip()
