"""Schema authoring guide shared by API workload tools and agent runtime skills."""

SCHEMA_AUTHORING_GUIDE = """
# Kartograph schema authoring (Graph Management Assistant)

Use the Kartograph schema tools — never probe undocumented HTTP routes.
Use Read, Grep, Glob, and Bash against the session workspace mount. Prebuilt generator scripts
live under `instance_generators/` (see README there). Write scripts and JSON/JSONL outputs
only under `instance_generators/` — `repository-files/` and `ingestion-context/` are read-only.

## Bootstrap workflow (6 phases)

Complete these in order. Do not mix schema design, prepopulation planning, and bulk
implementation in the same turn when the user gave multiple deliverables.

1. **Understand goals** — Ask what questions the graph must answer; collect 3–5 stakeholder use cases.
2. **Workspace discovery** — Glob/Grep under `repository-files/`; report file counts, extensions, and code patterns.
3. **Draft schema + validation Q&A** — Propose entity types, properties, and relationships; cite workspace examples.
4. **Prepopulation planning** — Decide prepopulated vs manual per type; required properties; generator strategy.
5. **Save ontology** — `kartograph_save_schema_ontology` only after the user confirms the full schema.
6. **Implement prepopulation** — Bash generators → `json_*_to_jsonl.py` → validate-from-file → apply-from-file; entities before edges; verify readiness.

## Schema modeling rules

- **Property vs entity:** distinguish/categorize (e.g. tier0/tier1) → property on an existing type;
  track which/what or needs relationships → entity type + edges.
- **Bidirectional relationships** default on — author primary direction only; platform creates inverse type
  and twin edge instances. Set `bidirectional: false` for asymmetric edges (`depends_on`, `created_by`).
- For asymmetric edges, confirm direction explicitly (X → rel → Y).

## Workspace discovery patterns

| Target | Glob / Grep hints |
|--------|-------------------|
| Tests | `**/*_test.go`, `**/test_*.go`, `**/*_test.py`, `**/tests/**` |
| API endpoints / handlers | `Grep` for route registrations, `@app.`, `HandleFunc`, OpenAPI paths |
| Source files | `Glob **/*.{go,py,ts,java,yaml,md}` per data source folder |

Cite the session workspace appendix for per-repo file counts and extension summaries before prepopulation Q&A.

## Tool workflow

1. Call `kartograph_get_schema_authoring_guide` (this document).
2. Call `kartograph_get_workspace_readiness` to see prepopulated gaps and live instance counts.
3. Call `kartograph_get_schema_ontology` to read the current entity/relationship types.
4. Edit the ontology JSON (full replace) and call `kartograph_save_schema_ontology`.
5. For prepopulated types at scale: run a script under `instance_generators/` (examples:
   `data_source.py`, `folder.py`, `source_file.py`, or your own), then
   `python3 instance_generators/json_instances_to_jsonl.py <entity_label> out/instances.json`.
6. After entity nodes exist, convert relationship JSON with
   `json_relationships_to_jsonl.py <edge_label> <source_entity> <target_entity> out/relationships.json`.
7. Optional: `kartograph_check_graph_slugs` to batch-check which slugs already exist before CREATE.
8. Dry-run with `kartograph_validate_graph_mutations_from_file`, then apply with
   `kartograph_apply_graph_mutations_from_file` (or inline tools for small fixes).
9. Verify with `kartograph_list_instances_by_type` and `kartograph_get_workspace_readiness`.

## Entity type (node type) shape

Each entry in `node_types`:

```json
{
  "label": "service",
  "description": "Deployable software service",
  "required_properties": ["name"],
  "optional_properties": ["team"],
  "prepopulated": false,
  "prepopulated_instance_count": 0,
  "instance_generator": "source_file.py"
}
```

- `label`: lowercase snake_case type name (required).
- `prepopulated`: when true, bootstrap transition requires at least one instance.
- `instance_generator`: optional script name under `instance_generators/` (example templates or your own).
- Saving replaces the entire ontology — read first, merge your edits, then save.

## Relationship type (edge type) shape

Each entry in `edge_types`:

```json
{
  "label": "contains",
  "description": "Test exercises an API endpoint",
  "source_labels": ["test"],
  "target_labels": ["api_endpoint"],
  "properties": [],
  "prepopulated": true,
  "prepopulated_instance_count": 0,
  "instance_generator": "my_edges.py",
  "bidirectional": true,
  "inverse_label": "contained_in"
}
```

- `bidirectional`: default `true` for new relationship types — platform auto-creates inverse type and twin edge instances.
- `inverse_label`: optional override; otherwise derived (`contains` → `contained_in`, else `{label}_inverse`).
- Set `bidirectional: false` for asymmetric edges (`depends_on`, `created_by`).
- Author **primary direction only** in generators; inverse instances are created automatically on apply.
- `source_labels` / `target_labels`: allowed node type labels for edge endpoints.
- `instance_generator`: optional script under `instance_generators/` for relationship prepopulation.
- `prepopulated`: when true, bootstrap transition requires at least one instance of this
  relationship type. Every listed source and target entity type must also have
  `prepopulated: true`.

## Instance mutations (JSONL)

Apply after types exist. One JSON object per line.

Create entity instance:

```json
{"op":"CREATE","type":"node","id":"service:0123456789abcdef","label":"service","set_properties":{"name":"api-gateway","slug":"api-gateway","data_source_id":"schema-bootstrap","source_path":"graph-management-assistant"}}
```

Create relationship instance (requires entity node IDs from prior CREATE or list tool):

```json
{"op":"CREATE","type":"edge","id":"depends_on:0123456789abc001","label":"depends_on","start_id":"service:0123456789abcdef","end_id":"service:fedcba9876543210","set_properties":{"data_source_id":"schema-bootstrap","source_path":"graph-management-assistant"}}
```

Rules:
- `id` format: `{label}:{16 lowercase hex chars}` — generate with `secrets.token_hex(8)`.
- CREATE requires `data_source_id` and `source_path` in `set_properties`.
- Node CREATE requires `slug` in `set_properties` (kebab-case, unique per type).
- `knowledge_graph_id` is stamped by the platform — do not set it.
- For large sets: Bash + custom script under `instance_generators/` → `json_*_to_jsonl.py` → apply-from-file.
  Never hand-author bulk CREATE ids in chat — use converter scripts for deterministic ids.
- CREATE is strict: existing types/instances must be changed with UPDATE, not CREATE again.
- Dry-run before apply: `kartograph_validate_graph_mutations` or `kartograph_validate_graph_mutations_from_file`.
- Create all entity nodes before relationship edges.
- Sort instances deterministically (by slug or path) before emitting CREATE lines.

## Instance generation cookbook

Scan prepared files under `repository-files/<data_source_slug>/` (see session workspace appendix).

| Pattern | When to use | Scan strategy | Slug rule | Key properties |
|---------|-------------|---------------|-----------|----------------|
| **data_source** | One instance per connected repo | Top-level folders under `repository-files/` | folder name | `name`, `source_type`, `file_count` |
| **folder** | Directory hierarchy anchors | `Glob **/*` dirs per data source | `folder-{path-kebab}` | `folder_path`, `data_source`, child counts |
| **source_file** | File-level extraction jobs | `Glob **/*.{go,py,yaml,md,json,...}` | path → kebab (`pkg-api-foo-go`) | `file_path`, `source_path`, `name` |

Workflow for bulk prepopulation:
1. Mark the entity type `prepopulated: true` and save ontology.
2. Use Glob to list candidate paths (exclude dot-directories).
3. Derive slugs deterministically from relative paths.
4. Call `kartograph_search_graph_by_slug` for a sample slug to avoid duplicates.
5. Emit JSONL CREATE batches via `kartograph_apply_graph_mutations`.
6. Confirm coverage with `kartograph_list_instances_by_type`.
7. For prepopulated relationships: use `kartograph_list_relationship_instances` or entity lists to resolve `start_id`/`end_id`, then CREATE edges.

## Readiness checklist

Bootstrap transition needs:
- At least one entity type and one relationship type.
- Every `prepopulated=true` entity type must have at least one live instance.
- Every `prepopulated=true` relationship type must have at least one live edge instance.
- A prepopulated relationship type may only reference entity types that are also prepopulated.

Call `kartograph_get_workspace_readiness` for:
- `prepopulated_entity_types_without_instances_live` — entity types still needing CREATE lines.
- `prepopulated_relationship_types_without_instances_live` — relationship keys still needing edge CREATE lines.
- `prepopulated_entity_types` / `prepopulated_relationship_types` — metadata vs live counts.
- `blocking_reasons` — transition blockers.

After applying instance mutations, ontology `prepopulated_instance_count` metadata is refreshed automatically from live graph totals.

## Repository context

Prepared JobPackage files live under `repository-files/<data_source_name>/` relative to the
workspace mount (one folder per connected data source; names are slugified data source names
such as `hyperfleet-api`). Use Read, Grep, and Glob on those paths — not HTTP discovery.
The session workspace appendix lists data sources, file counts, sample paths, and extension
hints when available.
""".strip()
