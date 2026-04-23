---
task_id: task-003
round: 1
role: spec-reviewer
verdict: fail
---
## Verification Results (Round 3 — Independent Re-Review)

All 2009 unit tests pass. All linting/formatting/type-checking pass. The implementation
is generally sound. However, three spec scenarios have missing or insufficient test
coverage that prevents a PASS verdict under strict alignment rules.

---

### Requirement Coverage

#### Requirement: Per-Tenant Graph Isolation — COVERED
- **Code:** `get_tenant_graph_name()` → `tenant_{tenant_id}`, wired into `get_age_graph_client`
  (`graph/dependencies.py`).
- **Tests:** `TestTenantGraphRouting::test_graph_client_uses_tenant_specific_graph_name`
  (asserts `"tenant_t1"`) and `test_graph_name_uses_full_tenant_id` (asserts
  `"tenant_my-org-tenant-123"`).

#### Requirement: KnowledgeGraph Scoping — COVERED
- **Mutation authorization:** `apply_kg_mutations` checks `edit` on
  `knowledge_graph:{id}` via SpiceDB before calling the service. Tests:
  `test_kg_mutations_route_forbidden_without_edit_permission` (403, service not called),
  `test_kg_mutations_route_checks_correct_resource` (asserts correct resource string),
  `test_kg_mutations_route_accessible_with_edit_permission` (200 path).
- **KG ID stamping + anti-spoofing:** `_stamp_knowledge_graph_id` overwrites any
  caller-supplied value. Tests: `test_stamps_knowledge_graph_id_on_create_operation`,
  `test_overwrites_caller_provided_knowledge_graph_id`,
  `test_stamps_knowledge_graph_id_on_update_operation`,
  `test_stamps_knowledge_graph_id_in_jsonl_parse`, `test_does_not_stamp_on_delete_operation`.
- **kg_id validation in `validate_operation()`:** `test_create_node_requires_knowledge_graph_id`
  and `test_create_edge_requires_knowledge_graph_id` confirm rejection when missing.

#### Requirement: Mutation Log Format — PARTIAL
- **Valid JSONL:** COVERED — `test_parses_jsonl_and_applies_mutations`.
- **Empty lines:** COVERED — `test_handles_whitespace_only_lines`.
- **Parse error on a line:** PARTIAL.
  - Spec: "the error is reported with **the line number** and **a content preview**".
  - Implementation: `graph_mutation_service.py` lines 269-278 produce:
    `f"JSON parse error on line {line_num}: {str(e)}"` and `f"Line content: {line_preview}"`.
    Both the line number and the content preview are present.
  - Test `test_returns_error_on_invalid_json` only asserts:
    `assert "JSON" in result.errors[0] or "parse" in result.errors[0].lower()`
    It does **not** assert that a line number appears in the error, and it does **not** assert
    that a content preview (`Line content: ...`) is present. If the implementation changed to
    drop the line number or preview, this test would still pass.
  - **Fix needed:** Add assertions: `assert "line 1" in result.errors[0].lower()` (or similar)
    and `assert len(result.errors) >= 2` with `"line content" in result.errors[1].lower()`.

#### Requirement: DEFINE Operation — PARTIAL
- **Define an edge type:** COVERED (indirectly by `test_edge_does_not_require_slug`).
- **Define a node type:** PARTIAL.
  - Spec: "system properties (`data_source_id`, `source_path`, `slug`) are **automatically
    added** to required properties".
  - Implementation: `graph_mutation_service.py` lines 197-209 augment `required_properties`
    with `get_system_properties_for_entity(op.type)` before saving the `TypeDefinition`.
  - Test `test_apply_mutations_stores_define_operations` only asserts `label`, `entity_type`,
    and `description` on the saved `TypeDefinition`. It does **not** assert that
    `data_source_id`, `source_path`, and `slug` appear in `required_properties`.
  - Indirect coverage exists via `test_rejects_create_missing_system_properties` (which
    verifies that CREATE fails when system properties are missing), but this does not
    directly assert the DEFINE scenario's THEN condition.
  - **Fix needed:** Add assertion to `test_apply_mutations_stores_define_operations` (or a
    new dedicated test) checking `"data_source_id" in saved_type_def.required_properties`,
    `"source_path" in saved_type_def.required_properties`, and
    `"slug" in saved_type_def.required_properties`.

#### Requirement: CREATE Operation — COVERED
- **Create a new node:** `test_create_node_valid` + service acceptance tests.
- **Create an existing node (idempotent merge):** Integration test
  `test_repeated_batch_is_idempotent` (requires live infra).
- **Create an edge:** `test_create_edge_valid`, `test_edge_does_not_require_slug`.
- **Missing type definition:** `test_rejects_create_without_define_in_batch`.
- **Missing required properties:** `test_rejects_create_missing_required_properties`.
- **Schema learning:** `TestSchemaLearning::test_extra_properties_added_to_optional`.

#### Requirement: UPDATE Operation — COVERED
- **Set properties:** `test_update_with_set_properties` + integration test.
- **Remove properties:** `test_update_with_remove_properties`.
- **Schema learning on update:** `test_update_discovers_optional_properties`.

#### Requirement: DELETE Operation — COVERED
- **Delete a node (cascading):** `test_delete_valid` + `test_calls_delete_node_once_per_id`
  verifies `delete_node_with_detach` is called (detach = cascade). Integration test
  `test_delete_node_detaches_edges` confirms the cascade in a live graph.
- **Delete an edge:** `test_calls_delete_edge_once_per_id`.

#### Requirement: Mandatory System Properties — COVERED
- Node: `test_create_requires_data_source_id`, `test_create_requires_source_path`,
  `test_create_node_requires_slug`, `test_create_node_requires_knowledge_graph_id`.
- Edge: `test_create_requires_data_source_id`, `test_create_requires_source_path`,
  `test_create_edge_requires_knowledge_graph_id`.

#### Requirement: Deterministic Entity IDs — COVERED
- `TestEntityIdGenerator` fully covers determinism, `{type}:{16_hex_chars}` format,
  normalization, edge IDs, and validation.

#### Requirement: Referential Integrity Ordering — PARTIAL
- Spec: "THEN DEFINE operations run first AND DELETE operations run next (edges before
  nodes) AND CREATE operations follow (nodes before edges) AND UPDATE operations run last".
- Implementation:
  - `MutationApplier._sort_operations()` (`mutation_applier.py` lines 50-81) implements
    the sort key: DEFINE=0, DELETE=1, CREATE=2, UPDATE=3; within DELETE: edges=0, nodes=1;
    within CREATE/UPDATE: nodes=0, edges=1.
  - `AgeBulkLoadingStrategy.apply_batch()` (`strategy.py` lines 70-141) also partitions
    independently: delete_edges → delete_nodes → create_nodes → create_edges → update_ops.
- **No test exists for `_sort_operations()`**. The method is not exercised by any unit test.
  A mixed-operation-type batch is never assembled to verify that the method produces the
  correct ordering. If the sort key priorities were swapped (e.g., CREATE before DELETE),
  no test would catch it.
- The integration tests for delete (`test_delete_node`), create, and update operate on
  homogeneous batches — they do not test cross-type ordering.
- **Fix needed:** Add a unit test that creates a list of mixed operations
  (`[UPDATE, CREATE_edge, DELETE_node, DEFINE, DELETE_edge, CREATE_node]`) and asserts
  that `applier._sort_operations(ops)` returns them in the spec-mandated order.

---

### Summary of Findings

| Requirement                          | Status  | Gap                                                |
|--------------------------------------|---------|----------------------------------------------------|
| Per-Tenant Graph Isolation           | COVERED |                                                    |
| KnowledgeGraph Scoping               | COVERED |                                                    |
| Mutation Log Format (Valid JSONL)    | COVERED |                                                    |
| Mutation Log Format (Empty lines)    | COVERED |                                                    |
| Mutation Log Format (Parse error)    | PARTIAL | Test doesn't assert line number or content preview |
| DEFINE (node type, system props)     | PARTIAL | Test doesn't assert system props in required_properties |
| DEFINE (edge type)                   | COVERED |                                                    |
| CREATE (all scenarios)               | COVERED |                                                    |
| UPDATE (all scenarios)               | COVERED |                                                    |
| DELETE (all scenarios)               | COVERED |                                                    |
| Mandatory System Properties          | COVERED |                                                    |
| Deterministic Entity IDs             | COVERED |                                                    |
| Referential Integrity Ordering       | PARTIAL | `_sort_operations()` has no unit test              |

Three PARTIAL items. Per the review protocol, **FAIL if any SHALL/MUST requirement
lacks … test coverage**. The Referential Integrity Ordering scenario (a SHALL) has a
complete implementation in `_sort_operations()` but **zero test coverage** of the
ordering contract.