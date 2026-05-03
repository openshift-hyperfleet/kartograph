---
id: task-094
title: MCP query tool — add unit tests for internal property filtering
spec_ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
status: in_progress
phase: mark-ready
deps: []
round: 0
branch: hyperloop/task-094
pr: https://github.com/openshift-hyperfleet/kartograph/pull/560
pr_title: 'test(query): add unit tests for _filter_internal_properties in query_graph
  tool'
pr_description: "## What & Why\n\nThe **Requirement: Graph Query Tool — Scenario:\
  \ Internal property filtering** in\n`specs/query/mcp-server.spec.md` states:\n\n\
  > GIVEN query results containing internal properties (e.g., `all_content_lower`)\n\
  > WHEN the results are returned to the client\n> THEN internal properties are stripped\
  \ from the response\n\nThe `_filter_internal_properties` helper in\n`src/api/query/presentation/mcp.py`\
  \ implements this correctly, but it has\n**zero dedicated unit tests**. This is\
  \ a spec coverage gap: no test can\ncurrently catch a regression (e.g., forgetting\
  \ to add a new internal\nproperty to `INTERNAL_PROPERTIES`, or breaking recursive\
  \ filtering).\n\nThe existing test file `tests/unit/query/test_mcp_query_tool.py`\
  \ covers only\n`_build_error_response`. This task adds a new test class for\n`_filter_internal_properties`\
  \ in that same file.\n\n## Implementation Reference\n\n```python\n# src/api/query/presentation/mcp.py\n\
  INTERNAL_PROPERTIES = {\"all_content_lower\"}\n\ndef _filter_internal_properties(data:\
  \ Any) -> Any:\n    if isinstance(data, dict):\n        return {\n            k:\
  \ _filter_internal_properties(v)\n            for k, v in data.items()\n       \
  \     if k not in INTERNAL_PROPERTIES\n        }\n    elif isinstance(data, list):\n\
  \        return [_filter_internal_properties(item) for item in data]\n    else:\n\
  \        return data\n```\n\nThe function recursively filters `INTERNAL_PROPERTIES`\
  \ from dicts, recurses\ninto lists, and passes scalars through unchanged.\n\n##\
  \ Spec Scenario\n\n- GIVEN query results containing internal properties (e.g., `all_content_lower`)\n\
  - WHEN the results are returned to the client\n- THEN internal properties are stripped\
  \ from the response\n\n## TDD Approach\n\nFollow the project TDD pattern: write\
  \ all tests FIRST (they will pass immediately\nsince the implementation already\
  \ exists, but this confirms the spec is met), then\nverify no regressions exist.\n\
  \nWrite tests in `src/api/tests/unit/query/test_mcp_query_tool.py` as a new class\n\
  `TestFilterInternalProperties`.\n\n## Test Cases Required\n\n### Basic filtering\n\
  - `test_strips_all_content_lower_from_flat_dict`\n  — `{\"all_content_lower\": \"\
  foo\", \"name\": \"bar\"}` → `{\"name\": \"bar\"}`\n- `test_preserves_non_internal_properties`\n\
  \  — `{\"name\": \"bar\", \"label\": \"baz\"}` → unchanged\n\n### Node dict filtering\
  \ (the primary use case)\n- `test_strips_internal_props_from_node_dict`\n  — Node\
  \ dict: `{\"node\": {\"id\": \"1\", \"label\": \"Person\", \"properties\":\n   \
  \ {\"name\": \"Alice\", \"all_content_lower\": \"alice engineer\"}}}` →\n    `all_content_lower`\
  \ stripped from properties, other fields intact\n- `test_preserves_node_dict_structure`\n\
  \  — `id`, `label`, and non-internal properties in `properties` are preserved\n\n\
  ### Edge dict filtering\n- `test_strips_internal_props_from_edge_dict`\n  — Edge\
  \ dict with `all_content_lower` in properties → stripped; `id`,\n    `label`, `start_id`,\
  \ `end_id` preserved\n\n### Recursive filtering (map results)\n- `test_filters_recursively_through_nested_dicts`\n\
  \  — Nested dict: `{\"a\": {\"all_content_lower\": \"x\", \"b\": 1}}` →\n    `{\"\
  a\": {\"b\": 1}}`\n- `test_filters_recursively_through_lists`\n  — List: `[{\"all_content_lower\"\
  : \"x\"}, {\"name\": \"foo\"}]` →\n    `[{}, {\"name\": \"foo\"}]`\n- `test_filters_list_inside_dict`\n\
  \  — `{\"items\": [{\"all_content_lower\": \"x\", \"n\": 1}]}` →\n    `{\"items\"\
  : [{\"n\": 1}]}`\n\n### Scalar pass-through\n- `test_scalars_pass_through_unchanged`\n\
  \  — `42`, `\"hello\"`, `True`, `None`, `3.14` all returned as-is\n- `test_none_passes_through`\n\
  \  — `None` → `None`\n\n### Multiple internal properties (future-proofing)\n- `test_strips_all_defined_internal_properties`\n\
  \  — If `INTERNAL_PROPERTIES` contains more than one property, all are\n    stripped.\
  \ Test with `{\"all_content_lower\": \"x\", \"name\": \"Alice\"}` and\n    assert\
  \ only `name` remains; if a second internal property is ever added,\n    update\
  \ this test.\n\n### Empty dict edge case\n- `test_empty_dict_returns_empty_dict`\
  \ — `{}` → `{}`\n- `test_dict_with_only_internal_props_returns_empty` — `{\"all_content_lower\"\
  : \"x\"}` → `{}`\n\n## Files Affected\n\n- `src/api/tests/unit/query/test_mcp_query_tool.py`\n\
  \  — add `TestFilterInternalProperties` class with the test cases above\n- No implementation\
  \ changes expected (implementation is correct)\n\n## How to Verify\n\n```bash\n\
  cd src/api && uv run pytest tests/unit/query/test_mcp_query_tool.py -v\n```\n\n\
  All existing tests continue to pass. All new `TestFilterInternalProperties` tests\n\
  pass. No implementation changes needed (the function is already correct).\n\n##\
  \ Caveats\n\n- `_filter_internal_properties` is a module-level private function\
  \ in `mcp.py`.\n  It can be imported directly for testing:\n  `from query.presentation.mcp\
  \ import _filter_internal_properties`\n- The integration tests do not create nodes\
  \ with `all_content_lower` properties,\n  so they provide no regression protection\
  \ for this scenario.\n- If future requirements add more internal properties, update\
  \ `INTERNAL_PROPERTIES`\n  in `mcp.py` AND add a test case here."
---
