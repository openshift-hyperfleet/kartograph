# Instance generators

Prepopulation for `prepopulated: true` types uses **three kinds of files**:

| File | Who writes it | Purpose |
|------|---------------|---------|
| `{label}.py` | Agent | Scans `repository-files/` → JSON array on stdout |
| `entities_to_jsonl.py` | Platform | `{label}_instances.json` → `{label}_instances.jsonl` |
| `relationships_to_jsonl.py` | Platform | `{key}_instances.json` → `{key}_instances.jsonl` |

Copy `_entity_scanner.example.py` to `{entity_label}.py` and replace the `scan()` body.

## Entity prepopulation (one type per turn)

```bash
python3 instance_generators/test.py repository-files \
  > instance_generators/out/test_instances.json

python3 instance_generators/entities_to_jsonl.py test \
  --data-source-id schema-bootstrap \
  instance_generators/out/test_instances.json \
  > instance_generators/out/test_instances.jsonl
```

Then `kartograph_validate_graph_mutations_from_file` and
`kartograph_apply_graph_mutations_from_file` with path
`instance_generators/out/test_instances.jsonl` (one batch for all instances).

## Relationship prepopulation (after all entity gaps)

Naming: `out/{source}_{relationship}_{target}_instances.json` (e.g. `repository_defines_test_instances.json`).

```bash
python3 instance_generators/repository_defines_test.py repository-files \
  > instance_generators/out/repository_defines_test_instances.json

python3 instance_generators/relationships_to_jsonl.py defines repository test \
  instance_generators/out/repository_defines_test_instances.json \
  > instance_generators/out/repository_defines_test_instances.jsonl
```

## Scanner JSON contract

**Entities:** `[{"slug": "kebab-case", "properties": {...}}]`

**Relationships:** `[{"source_slug": "...", "target_slug": "...", "properties": {}}]`

Include `source_path` in `properties` only when you need provenance on that instance.

Never write output to `/tmp` — only `instance_generators/out/` is valid for apply-from-file.
