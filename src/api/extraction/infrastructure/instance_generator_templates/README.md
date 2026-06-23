# Instance generators

Prepopulation for `prepopulated: true` types uses **three kinds of files**:

| File | Who writes it | Purpose |
|------|---------------|---------|
| `{Label}.py` | Agent | Scans `repository-files/` → JSON array on stdout |
| `run_scanner.py` | Platform | One command: scan → JSON → JSONL |
| `entities_to_jsonl.py` | Platform | `{label}_instances.json` → `{label}_instances.jsonl` |
| `relationships_to_jsonl.py` | Platform | `{key}_instances.json` → `{key}_instances.jsonl` |

**Read `PREPOPULATION_WORKFLOW.md` first** — it documents the full six-step entity pipeline,
relationship workflow, slug rules, batch sizes, and verification.

## Naming (case-sensitive)

| Item | Convention |
|------|------------|
| Entity scanner | `instance_generators/{Label}.py` — must match ontology `label` exactly (`E2ETest.py`, not `e2etest.py`) |
| Entity output | `instance_generators/out/{Label}_instances.json` |
| Relationship scanner | `instance_generators/{Source}_{rel}_{Target}.py` |
| Relationship output | `instance_generators/out/{Source}_{rel}_{Target}_instances.json` |

Copy `_entity_scanner.example.py` to `{Label}.py` or start from `examples/` for domain patterns.

## Entity prepopulation (one type per turn)

Preferred — combined run:

```bash
python3 instance_generators/run_scanner.py E2ETest --entity
# apply the printed jsonl_path with kartograph_apply_graph_mutations_from_file
```

Manual steps:

```bash
python3 instance_generators/E2ETest.py repository-files \
  > instance_generators/out/E2ETest_instances.json

python3 instance_generators/preview_instances.py E2ETest --limit 5

python3 instance_generators/entities_to_jsonl.py E2ETest \
  --data-source-id schema-bootstrap \
  instance_generators/out/E2ETest_instances.json \
  > instance_generators/out/E2ETest_instances.jsonl
```

Then `kartograph_apply_graph_mutations_from_file` with path
`instance_generators/out/E2ETest_instances.jsonl` (apply pre-validates; validate first is optional).

## Relationship prepopulation (after all entity gaps)

```bash
python3 instance_generators/ComponentTest_exercises_APIEndpoint.py repository-files \
  > instance_generators/out/ComponentTest_exercises_APIEndpoint_instances.json

python3 instance_generators/relationships_to_jsonl.py exercises component_test api_endpoint \
  instance_generators/out/ComponentTest_exercises_APIEndpoint_instances.json \
  > instance_generators/out/ComponentTest_exercises_APIEndpoint_instances.jsonl
```

## Scanner JSON contract

**Entities:** `[{"slug": "snake_case", "properties": {...}}]`

**Relationships:** `[{"source_slug": "...", "target_slug": "...", "properties": {}}]`

Use `scanner_common.generate_slug()` and `dedupe_instances()` / `dedupe_relationships()`.

Never write output to `/tmp` — only `instance_generators/out/` is valid for apply-from-file.
