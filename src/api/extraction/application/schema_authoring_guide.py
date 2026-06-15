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
`preview_instances.py`, `run_scanner.py`, `scanner_common.py`.
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

**Entities** (all entity gaps before any relationship gap). Prefer `run_scanner.py`:

```bash
python3 instance_generators/run_scanner.py E2ETest --entity
# kartograph_apply_graph_mutations_from_file path=<printed jsonl_path>
```

Manual pipeline:

```bash
python3 instance_generators/E2ETest.py repository-files > instance_generators/out/E2ETest_instances.json
python3 instance_generators/preview_instances.py E2ETest --limit 5
python3 instance_generators/entities_to_jsonl.py E2ETest \\
  --data-source-id schema-bootstrap \\
  instance_generators/out/E2ETest_instances.json > instance_generators/out/E2ETest_instances.jsonl
# apply-from-file path=instance_generators/out/E2ETest_instances.jsonl
```

Apply pre-validates internally; validate-from-file is an optional dry run. Apply responses include
`next_action` and remaining prepopulation gaps — use those instead of polling readiness after
every batch when chaining scanners.

**Relationships** (after entity slugs exist; files use `{source}_{rel}_{target}_instances.*`):

```bash
python3 instance_generators/run_scanner.py \\
  --relationship --source ComponentTest --rel tests --target APIEndpoint
```

Scanner stdout contract:
- Entities: `[{"slug": "...", "properties": {...}}]`
- Relationships: `[{"source_slug": "...", "target_slug": "...", "properties": {}}]`

## Schema modeling rules

- **Property vs entity:** categorize → property; track instances/relationships → entity + edges.
- Set `bidirectional: false` only for asymmetric edges (`depends_on`, `created_by`).

## Relationship types (authoring vs UI)

### Unique edge labels (required)

Every `edge_types[].label` must be **unique** within the ontology. The platform stores edge types by
label; duplicate labels are rejected or silently collapse to one definition — **never** author six
entries all named `tests` or two named `covered_by`.

**When the operator wants N rows in the Relationship ontology UI** (one row per source → target
pair), create **N primary `edge_types` entries with N distinct labels** — one concrete
`source_labels` + `target_labels` pair each (single element in each array). Assign a unique label
per row (e.g. `tests_ct_api`, `tests_e2e_adapter`, `covered_by_us_ct`). Set a distinct
`inverse_label` per entry when bidirectional (e.g. `appears_in_ct_api`, `covers_us_ct`).

Example — eight UI rows for eight endpoint pairs (labels illustrative; adjust naming to taste):

| UI row | `label` | `source_labels` | `target_labels` | `inverse_label` |
|--------|---------|-----------------|-----------------|-----------------|
| 1 | `tests_ct_api` | `["ComponentTest"]` | `["APIEndpoint"]` | `appears_in_ct_api` |
| 2 | `tests_ct_adapter` | `["ComponentTest"]` | `["Adapter"]` | `appears_in_ct_adapter` |
| … | … | … | … | … |
| 8 | `covered_by_us_e2e` | `["UserStory"]` | `["E2ETest"]` | `covers_us_e2e` |

After save, call `kartograph_get_schema_ontology` and confirm **eight primary** edge types exist
(`auto_generated` / `inverse_of` entries are inverses — the UI hides them). **Never** claim “8 types
saved” until read-back shows eight distinct primary labels.

**Relationship scanners:** `--rel` must match the saved `label` for that row (e.g.
`--rel tests_ct_api`, not `--rel tests` when the ontology label is `tests_ct_api`).

### How the UI counts rows

Design artifacts show **one row per primary relationship label**. Inverse types are **not**
separate rows; each row shows `primary / inverse` badges (e.g. `tests_ct_api / appears_in_ct_api`).

**Bidirectional (default):** author **one primary direction only** per label. Do **not** add the
inverse as its own authored `edge_types` entry — the platform auto-generates it on save.

### Semantic grouping vs UI rows

**Count relationship types by stored label**, not by endpoint pair alone. Two patterns:

1. **Few semantic types, few UI rows:** one label (e.g. `tests`) with one representative pair; other
   endpoint combinations get relationship **instances** via extraction jobs later.
2. **Many UI rows:** many labels (unique per pair) as in the table above — report the count from
   read-back primary entries, not “8 combinations” while only two labels exist.

**Multi-label arrays (advanced):** one entry may list multiple entity types in `source_labels` /
`target_labels`, but the UI shows **one row** using `source_labels[0]` → `target_labels[0]` only.
Do not promise N×M separate UI rows without N×M distinct primary labels.

**After every schema save or relationship edit:** call `kartograph_get_schema_ontology` and report
what is stored — for each **primary** edge type: `label`, `source_labels`, `target_labels`,
`inverse_label`, `bidirectional`, `prepopulated`. Do not claim combinations or counts not in that
payload.

**User-facing summaries must match stored ontology:**

- ✅ “8 relationship types in the UI: `tests_ct_api`, `tests_ct_adapter`, … (each bidirectional).”
- ✅ “2 relationship types: `tests`, `covered_by` — one representative pair each; other pairs via extraction jobs.”
- ❌ “Saved 8 types: ComponentTest|tests|APIEndpoint, …” when read-back shows only two labels.
- ❌ Listing auto-generated inverses as types you authored.

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
4. `kartograph_apply_graph_mutations_from_file` (apply pre-validates; validate is optional dry run)
5. Verify with `kartograph_list_instances_by_type` and readiness when apply does not return next_action

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

One primary entry per UI row (single source/target pair; **unique `label`**):

```json
{
  "label": "tests_ct_api",
  "description": "ComponentTest validates APIEndpoint behavior",
  "source_labels": ["ComponentTest"],
  "target_labels": ["APIEndpoint"],
  "prepopulated": false,
  "bidirectional": true,
  "inverse_label": "appears_in_ct_api"
}
```

Do **not** also add `appears_in_ct_api` as its own `edge_types` entry — that inverse is auto-generated on save.

**Prepopulation / scanners:** one concrete triple per run; `--rel` equals the saved `label`:
`run_scanner.py --relationship --source ComponentTest --rel tests_ct_api --target APIEndpoint`.
Output: `out/{source}_{label}_{target}_instances.json` (primary direction only; platform adds twin inverse edges on apply).

## Instance mutations (JSONL)

- Supported ops: **CREATE**, **UPDATE**, and **DELETE** for nodes and edges.
- CREATE requires `data_source_id` and `slug` on nodes. Put `source_path` in scanner `properties` when needed.
- CREATE is strict — duplicate ids/slugs fail validation; use UPDATE or DELETE for existing instances.
- DELETE removes a node or edge by `id` (edges before nodes when batching deletes manually).
- Never hand-author bulk CREATE lines in chat; use `entities_to_jsonl.py` / `relationships_to_jsonl.py`.
- Create all entity nodes before relationship edges unless you are correcting data with UPDATE/DELETE.

## One-off mutations (Graph Management Assistant)

Use this workflow when the UI mode is **one-off-mutations** — the operator asks for specific schema or instance edits and you apply them directly.

### Decision tree

| Request | Tool path |
|---------|-----------|
| Add/change entity or relationship **types** | Read ontology → propose delta → `kartograph_save_schema_ontology` |
| Create/update/delete **instances** | Search/list targets → JSONL → validate → apply |
| Mixed | Schema save first, then instance JSONL |

### JSONL examples

Bundled at `helpers/mutation-examples.jsonl` in the workspace. Canonical shapes:

```json
{"op":"UPDATE","type":"node","id":"adapter:abc123def4567890","set_properties":{"transport":"maestro"}}
{"op":"CREATE","type":"edge","id":"edge:...","label":"tests_ct_api","start_id":"...","end_id":"...","set_properties":{"data_source_id":"manual-edit"}}
{"op":"DELETE","type":"node","id":"adapter:deadbeefdeadbeef"}
```

Rules: both `op` and `type` on every line; `set_properties` not `properties`; UPDATE/DELETE need top-level `id`.

### Workflow (small edits, ≤5 lines)

1. `kartograph_get_schema_ontology` — always before edits
2. Resolve targets: one `kartograph_list_instances_by_type` or `kartograph_search_graph_by_slug`
3. `kartograph_validate_graph_mutations` → `kartograph_apply_graph_mutations`
4. Verify with list/search; report write op counts

### Bulk instance operations (5+ deletes/creates/updates)

Use when the operator asks to replace, prune, reconcile, or keep-only a set of instances.

**Mental model:** classify delete vs create → query once per type → generate JSONL in batch → validate once → apply once → done.

1. **List, don't loop search** — `kartograph_list_instances_by_type` returns `id`, `slug`, and `properties` (mutation-ready). Paginate with `offset` until you cover `total`. Filter by `data_source_id`, slug, or path in Bash/python. Do **not** call `search_by_slug` per instance.
2. **Generate JSONL programmatically** — save list output to `helpers/current_<Label>.json`, desired slugs to `helpers/desired_<Label>.json`, then run `python3 helpers/sync_instances.py --entity-type <Label> --current ... --desired ... --out helpers/bulk_<task>.jsonl` (optional `--filter-data-source-id`, `--create-missing`). Or Write `helpers/bulk_<task>.jsonl` directly. Example DELETE shape: `{"op":"DELETE","type":"node","id":"<id from list>"}`. Never hand-type dozens of lines in chat.
3. **Validate once, apply once** — `kartograph_validate_graph_mutations_from_file` then `kartograph_apply_graph_mutations_from_file`.
4. **Verify** — one list call; report counts.

Target **2–4 tool rounds** for bulk cleanup. Explicit delete/replace requests do not need a second confirmation after validate passes.

Confirm before schema type removals. Do not use prepopulation scanners unless the operator explicitly requests bulk import via scanner workflow.

## Readiness checklist

- Every `prepopulated=true` entity type needs ≥1 live instance.
- Every `prepopulated=true` relationship type needs ≥1 live edge.
- Prepopulated relationships may only reference prepopulated entity types.

Call `kartograph_get_workspace_readiness` for gaps, `next_action`, `prepopulation_tasks`
(with `order`, `blocking_types`, and `run_command`), and `blocking_reasons`.

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

## Batch extraction jobs (workload API, no MCP)

Extraction job sandboxes use `helpers/workload-graph-read.sh` and `helpers/workload-mutations.sh`
instead of `kartograph_*` MCP tools. Credentials live in `job-context.json`.

**Read before UPDATE:** `job-context.json` `target_instances` includes `graph_id` and
`properties_missing` (empty fields only). For populated fields you are refining — especially long
text like `description` — fetch live values first:

```bash
bash helpers/workload-graph-read.sh search-by-slug <slug> --entity-type <Type> --out mutations/current_<slug>.json
```

**Partial UPDATE:** `set_properties` merges into the live node; omitted properties are preserved.
Put only changed keys in each UPDATE line. Example:

```json
{"op":"UPDATE","type":"node","id":"componenttest:abc123def4567890","set_properties":{"description":"<edited full text>"}}
```

For surgical text edits: load the saved JSON, edit one property with Bash/python, emit JSONL
programmatically — do not paste full prior text into chat or resubmit unrelated properties.

**Apply:** validate then apply via `helpers/workload-mutations.sh` (writes `mutations/result.json`).
""".strip()
