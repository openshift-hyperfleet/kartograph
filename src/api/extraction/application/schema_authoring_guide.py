"""Schema authoring guide shared by API workload tools and agent runtime skills."""

SCHEMA_AUTHORING_GUIDE = """
# Kartograph schema authoring (Graph Management Assistant)

Use the Kartograph schema tools — never probe undocumented HTTP routes.

## Workflow

1. Call `kartograph_get_schema_authoring_guide` (this document).
2. Call `kartograph_get_schema_ontology` to read the current entity/relationship types.
3. Edit the ontology JSON (full replace) and call `kartograph_save_schema_ontology`.
4. For instances, call `kartograph_apply_graph_mutations` with JSONL lines.

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
  "label": "depends_on",
  "description": "Service dependency",
  "source_labels": ["service"],
  "target_labels": ["service"],
  "properties": []
}
```

- `source_labels` / `target_labels`: allowed node type labels for edge endpoints.

## Instance mutations (JSONL)

Apply after types exist. One JSON object per line.

Define-only line (usually handled by save_schema_ontology instead):

```json
{"op":"DEFINE","type":"node","label":"service","description":"A service","required_properties":["name"]}
```

Create entity instance:

```json
{"op":"CREATE","type":"node","id":"service:0123456789abcdef","label":"service","set_properties":{"name":"api-gateway","slug":"api-gateway","data_source_id":"schema-bootstrap","source_path":"graph-management-assistant"}}
```

Create relationship instance:

```json
{"op":"CREATE","type":"edge","id":"depends_on:0123456789abc001","label":"depends_on","start_id":"service:0123456789abcdef","end_id":"service:fedcba9876543210","set_properties":{"data_source_id":"schema-bootstrap","source_path":"graph-management-assistant"}}
```

Rules:
- `id` format: `{label}:{16 lowercase hex chars}`.
- CREATE requires `data_source_id` and `source_path` in `set_properties`.
- Node CREATE requires `slug` in `set_properties`.
- `knowledge_graph_id` is stamped by the platform — do not set it.

## Readiness checklist

Bootstrap transition needs:
- At least one entity type and one relationship type.
- Every `prepopulated=true` entity type must have instances (use CREATE lines).

## Repository context

Use Read/Grep/Glob on prepared JobPackage files under `repository-files/<data_source_name>/`
(one folder per connected data source for this knowledge graph; folder names are slugified
data source names such as `hyperfleet-api`, not other knowledge graphs) to infer domain
concepts — then model them as ontology types, not as ad-hoc API discoveries.
""".strip()
