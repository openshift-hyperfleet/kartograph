# Instance generators (examples)

These scripts are **starting examples**, not fixed entity types. Copy or author your own
`instance_generators/<your_script>.py` for each prepopulated entity type you define in the ontology.

## Usage

From the session workspace root (`/workspace` in the agent container):

```bash
python3 instance_generators/data_source.py repository-files
python3 instance_generators/folder.py repository-files
python3 instance_generators/source_file.py repository-files
```

Bulk pipeline (generator → JSONL → validate → apply):

```bash
mkdir -p instance_generators/out
python3 instance_generators/source_file.py repository-files \
  > instance_generators/out/source_file.json
python3 instance_generators/json_instances_to_jsonl.py source_file \
  --data-source-id schema-bootstrap \
  --source-path graph-management-assistant \
  instance_generators/out/source_file.json \
  > instance_generators/out/source_file.jsonl
# kartograph_validate_graph_mutations_from_file → kartograph_apply_graph_mutations_from_file
```

## Contract

- **Input:** path to `repository-files/` (one folder per connected data source).
- **Output:** JSON array on stdout: `[{"slug": "...", "properties": {...}}, ...]`
- **Deterministic:** sorted iteration, no timestamps in output.
- **Customize:** copy a template script for your entity type label, adjust property names to match your ontology, then run and convert output to graph CREATE mutations.

## Templates

| Script | Use when |
|--------|----------|
| `data_source.py` | One instance per top-level folder under `repository-files/` |
| `folder.py` | Directory hierarchy anchors per data source |
| `source_file.py` | One instance per source file (common code/doc extensions) |
| `json_instances_to_jsonl.py` | Convert any generator JSON array to CREATE JSONL for one entity label |
| `json_relationships_to_jsonl.py` | Convert relationship JSON (`source_slug`/`target_slug`) to edge CREATE JSONL |

Set `instance_generator` on the entity or relationship type in the ontology (e.g. `"source_file.py"` or
`"my_custom_tests.py"`) to document which script the assistant should run.

After generating slugs, convert to JSONL, dry-run validate, then apply from file.
