# Entity and relationship prepopulation workflow

Use this checklist for every `prepopulated: true` type after the ontology is saved.

## First entity type — smoke test (recommended)

After the ontology is saved, for the **first** prepopulated entity label only:

1. Run the scanner but limit output (e.g. `preview_instances.py {Label} --limit 2` or a tiny hand-trimmed JSON).
2. Convert to JSONL, optionally `kartograph_validate_graph_mutations_from_file`, then `kartograph_apply_graph_mutations_from_file`.
3. Confirm with `kartograph_list_instances_by_type` and `kartograph_get_workspace_readiness` (must return **200**).
4. If validate passes but apply or readiness returns **500/503**, **stop** — report a platform issue; do not run the full batch or advance to the next label.
5. When the smoke test succeeds, run the full pipeline for that label (see **Combined run** below).

## Combined run (recommended)

After the scanner exists, one command runs scan → JSON → JSONL:

```bash
python3 instance_generators/run_scanner.py Resource --entity
python3 instance_generators/run_scanner.py \
  --relationship --source ComponentTest --rel tests --target APIEndpoint
```

The script prints a JSON summary with `jsonl_path` and `next_step`. Apply pre-validates
internally — call `kartograph_apply_graph_mutations_from_file` with the printed path
(optional `kartograph_validate_graph_mutations_from_file` first for dry run).

Use `--validate-only` to stop after JSONL conversion without suggesting apply.

## Entity prepopulation (manual steps)

### Step 1 — Create scanner

Copy `_entity_scanner.example.py` to `instance_generators/{Label}.py`.

- **Filename must match the ontology `label` exactly** (case-sensitive): `E2ETest.py`, not `e2etest.py`.
- Customize `scan()` to discover instances across **all** `repository-files/<data_source>/` folders.
- Import helpers from `scanner_common.py` (`generate_slug`, `dedupe_instances`).

Domain-specific references live in `instance_generators/examples/`.

### Step 2 — Run scanner

```bash
python3 instance_generators/{Label}.py repository-files \
  > instance_generators/out/{Label}_instances.json
```

Stdout contract: `[{"slug": "kebab-or-snake-case", "properties": {...}}, ...]`

### Step 3 — Preview (optional)

Use when spot-checking **50–500** instances, or during the first-entity smoke test.
Skip for very small batches (≤10) and very large ones (>500) where terminal preview is not useful.

```bash
python3 instance_generators/preview_instances.py {Label} --limit 5
```

Fix scanner logic before JSONL conversion if slugs or properties look wrong.

### Step 4 — Convert to JSONL

```bash
python3 instance_generators/entities_to_jsonl.py {Label} \
  --data-source-id schema-bootstrap \
  instance_generators/out/{Label}_instances.json \
  > instance_generators/out/{Label}_instances.jsonl
```

The CLI `{Label}` must match the ontology entity type **exactly** (case-sensitive).
`entities_to_jsonl.py` preserves that casing in CREATE `label` lines.

### Step 5 — Validate (optional dry run)

Apply pre-validates the same checks. Use validate only when you want a dry run without writes.

`kartograph_validate_graph_mutations_from_file` with path `instance_generators/out/{Label}_instances.jsonl`.

CREATE is strict — duplicates fail here, not at apply time.

### Step 6 — Apply and verify

`kartograph_apply_graph_mutations_from_file` with the same path, then:

1. Confirm apply result reports created count and `next_action` / remaining gaps.
2. `kartograph_get_workspace_readiness()` — live count should increase; label leaves entity gaps.
3. `kartograph_list_instances_by_type(entity_type="{label}")` — spot-check slugs.

## Relationship prepopulation (after all entity gaps)

Copy `_relationship_scanner.example.py` to `instance_generators/{Source}_{rel}_{Target}.py`.

```bash
python3 instance_generators/{Source}_{rel}_{Target}.py repository-files \
  > instance_generators/out/{Source}_{rel}_{Target}_instances.json

python3 instance_generators/relationships_to_jsonl.py {rel} {source} {target} \
  instance_generators/out/{Source}_{rel}_{Target}_instances.json \
  > instance_generators/out/{Source}_{rel}_{Target}_instances.jsonl
```

Author **primary direction only** — the platform creates inverse twins for bidirectional types.

## Slug rules

- Lowercase snake_case (use `generate_slug()` from `scanner_common.py`).
- Unique within the entity type.
- Deduplicate before writing JSON (`dedupe_instances()`).

## Required vs optional properties

Check `kartograph_get_schema_ontology` or readiness `prepopulated_entity_types[].required_properties`.

- **Required:** must appear in every instance `properties` object (use sensible defaults if source data lacks them).
- **Optional:** omit or set `null`/empty when unknown.
- **Description:** auto-generate from slug when missing, e.g. `f"E2E test: {slug}"`.

## Entity order

Entities can be prepopulated in any order — relationships run after all entity gaps close.

Suggested dependency order for clarity:

1. Resource
2. APIEndpoint
3. Adapter
4. ComponentTest / E2ETest

## Batch sizes

- Recommended: **100–500** instances per JSONL file.
- Above **1000**: split into `{Label}_instances_001.jsonl`, `{Label}_instances_002.jsonl`, apply each batch separately.

## Never use `/tmp`

Files under `/tmp` are outside the sticky workspace mount and are not valid for apply-from-file.
If you hit permission errors on `instance_generators/`, report them — do not work around with `/tmp`.

## Single vs multi deliverable

- **One entity type requested** (e.g. "prepopulate E2ETest"): run steps 1–6 end-to-end without stopping.
- **Multiple types requested**: complete one label per turn, report, then continue.

## Success criteria

Prepopulation for one label is complete when:

- Apply succeeds with expected instance count.
- `kartograph_get_workspace_readiness()` shows zero live gap for that label.
- Spot-check via `kartograph_list_instances_by_type` looks correct.
