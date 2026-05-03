---
id: task-094
title: MCP query tool — add unit tests for internal property filtering
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add unit tests for _filter_internal_properties in query_graph tool"
pr_description: |
  ## What & Why

  The **Requirement: Graph Query Tool — Scenario: Internal property filtering** in
  `specs/query/mcp-server.spec.md` states:

  > GIVEN query results containing internal properties (e.g., `all_content_lower`)
  > WHEN the results are returned to the client
  > THEN internal properties are stripped from the response

  The `_filter_internal_properties` helper in
  `src/api/query/presentation/mcp.py` implements this correctly, but it has
  **zero dedicated unit tests**. This is a spec coverage gap: no test can
  currently catch a regression (e.g., forgetting to add a new internal
  property to `INTERNAL_PROPERTIES`, or breaking recursive filtering).

  The existing test file `tests/unit/query/test_mcp_query_tool.py` covers only
  `_build_error_response`. This task adds a new test class for
  `_filter_internal_properties` in that same file.

  ## Implementation Reference

  ```python
  # src/api/query/presentation/mcp.py
  INTERNAL_PROPERTIES = {"all_content_lower"}

  def _filter_internal_properties(data: Any) -> Any:
      if isinstance(data, dict):
          return {
              k: _filter_internal_properties(v)
              for k, v in data.items()
              if k not in INTERNAL_PROPERTIES
          }
      elif isinstance(data, list):
          return [_filter_internal_properties(item) for item in data]
      else:
          return data
  ```

  The function recursively filters `INTERNAL_PROPERTIES` from dicts, recurses
  into lists, and passes scalars through unchanged.

  ## Spec Scenario

  - GIVEN query results containing internal properties (e.g., `all_content_lower`)
  - WHEN the results are returned to the client
  - THEN internal properties are stripped from the response

  ## TDD Approach

  Follow the project TDD pattern: write all tests FIRST (they will pass immediately
  since the implementation already exists, but this confirms the spec is met), then
  verify no regressions exist.

  Write tests in `src/api/tests/unit/query/test_mcp_query_tool.py` as a new class
  `TestFilterInternalProperties`.

  ## Test Cases Required

  ### Basic filtering
  - `test_strips_all_content_lower_from_flat_dict`
    — `{"all_content_lower": "foo", "name": "bar"}` → `{"name": "bar"}`
  - `test_preserves_non_internal_properties`
    — `{"name": "bar", "label": "baz"}` → unchanged

  ### Node dict filtering (the primary use case)
  - `test_strips_internal_props_from_node_dict`
    — Node dict: `{"node": {"id": "1", "label": "Person", "properties":
      {"name": "Alice", "all_content_lower": "alice engineer"}}}` →
      `all_content_lower` stripped from properties, other fields intact
  - `test_preserves_node_dict_structure`
    — `id`, `label`, and non-internal properties in `properties` are preserved

  ### Edge dict filtering
  - `test_strips_internal_props_from_edge_dict`
    — Edge dict with `all_content_lower` in properties → stripped; `id`,
      `label`, `start_id`, `end_id` preserved

  ### Recursive filtering (map results)
  - `test_filters_recursively_through_nested_dicts`
    — Nested dict: `{"a": {"all_content_lower": "x", "b": 1}}` →
      `{"a": {"b": 1}}`
  - `test_filters_recursively_through_lists`
    — List: `[{"all_content_lower": "x"}, {"name": "foo"}]` →
      `[{}, {"name": "foo"}]`
  - `test_filters_list_inside_dict`
    — `{"items": [{"all_content_lower": "x", "n": 1}]}` →
      `{"items": [{"n": 1}]}`

  ### Scalar pass-through
  - `test_scalars_pass_through_unchanged`
    — `42`, `"hello"`, `True`, `None`, `3.14` all returned as-is
  - `test_none_passes_through`
    — `None` → `None`

  ### Multiple internal properties (future-proofing)
  - `test_strips_all_defined_internal_properties`
    — If `INTERNAL_PROPERTIES` contains more than one property, all are
      stripped. Test with `{"all_content_lower": "x", "name": "Alice"}` and
      assert only `name` remains; if a second internal property is ever added,
      update this test.

  ### Empty dict edge case
  - `test_empty_dict_returns_empty_dict` — `{}` → `{}`
  - `test_dict_with_only_internal_props_returns_empty` — `{"all_content_lower": "x"}` → `{}`

  ## Files Affected

  - `src/api/tests/unit/query/test_mcp_query_tool.py`
    — add `TestFilterInternalProperties` class with the test cases above
  - No implementation changes expected (implementation is correct)

  ## How to Verify

  ```bash
  cd src/api && uv run pytest tests/unit/query/test_mcp_query_tool.py -v
  ```

  All existing tests continue to pass. All new `TestFilterInternalProperties` tests
  pass. No implementation changes needed (the function is already correct).

  ## Caveats

  - `_filter_internal_properties` is a module-level private function in `mcp.py`.
    It can be imported directly for testing:
    `from query.presentation.mcp import _filter_internal_properties`
  - The integration tests do not create nodes with `all_content_lower` properties,
    so they provide no regression protection for this scenario.
  - If future requirements add more internal properties, update `INTERNAL_PROPERTIES`
    in `mcp.py` AND add a test case here.
---
