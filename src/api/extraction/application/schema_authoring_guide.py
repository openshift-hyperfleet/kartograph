"""Schema authoring guide shared by API workload tools and agent runtime skills."""

SCHEMA_AUTHORING_GUIDE = """
# Kartograph schema authoring (Graph Management Assistant)

Use the Kartograph schema tools — never probe undocumented HTTP routes.
Use Read, Grep, and Glob against the session workspace mount to scan prepared repository files.

## Workflow

1. Call `kartograph_get_schema_authoring_guide` (this document).
2. Call `kartograph_get_workspace_readiness` to see prepopulated gaps and live instance counts.
3. Call `kartograph_get_schema_ontology` to read the current entity/relationship types.
4. Edit the ontology JSON (full replace) and call `kartograph_save_schema_ontology`.
5. Scan `repository-files/<data_source_name>/` with Read/Grep/Glob to derive instances.
6. Create entity instances in batches via `kartograph_apply_graph_mutations` (JSONL CREATE lines).
7. Verify with `kartograph_list_instances_by_type`, `kartograph_list_relationship_instances`, and `kartograph_search_graph_by_slug`.

## Entity type (node type) shape

Each entry in `node_types`:

```json
{
  "label": "service",
  "description": "Deployable software service",
  "required_properties": ["name"],
  "optional_properties": ["team"],
  "prepopulated": false,
  "prepopulated_instance_count": 0
}
```

- `label`: lowercase snake_case type name (required).
- `prepopulated`: when true, bootstrap transition requires at least one instance.
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
  "prepopulated_instance_count": 0
}
```

- `source_labels` / `target_labels`: allowed node type labels for edge endpoints.
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
- Apply in batches of 25–50 CREATE lines; create all entity nodes before relationship edges.
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
