---
id: task-096
title: MCP server — Apache AGE Single-Column Return requirement spec alignment
spec_ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
status: not_started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: 'test(query): add missing _row_to_dict tests for map-with-edge and scalar
  variants'
pr_description: "## What & Why\n\nThe **Requirement: Apache AGE Single-Column Return**\
  \ in\n`specs/query/mcp-server.spec.md` specifies how query result rows must be\n\
  formatted for MCP clients. Apache AGE (A Graph Extension for PostgreSQL)\nrequires\
  \ all Cypher `RETURN` clauses to emit a single column; this requirement\ndocuments\
  \ how the Querying context normalises that single column into structured\nPython\
  \ dicts that MCP agents can consume.\n\nThe requirement has four scenarios. All\
  \ four are implemented in\n`QueryGraphRepository._row_to_dict()`, but **two sub-types\
  \ are not exercised\nby any existing test**:\n\n1. **Map return with a nested edge**\
  \ — `test_converts_map_with_vertices` exists\n   but no equivalent test covers a\
  \ map that contains an `AgeEdge` value.\n2. **Non-integer scalar variants** — `test_converts_scalar_value`\
  \ uses an integer\n   (`42`). No test covers a string scalar, a float, or `None`.\n\
  \nThese gaps could hide regressions if `_row_to_dict()` is refactored.\n\n## Background\
  \ — Apache AGE single-column constraint\n\nAGE returns results as PostgreSQL rows.\
  \ A Cypher query that logically returns\nmultiple values must wrap them in a map:\n\
  \n```cypher\n-- AGE requires this (single column):\nMATCH (p:Person)-[r:KNOWS]->(q)\
  \ RETURN {person: p, rel: r}\n-- NOT this (multi-column, AGE rejects it):\nMATCH\
  \ (p:Person)-[r:KNOWS]->(q) RETURN p, r\n```\n\n`_row_to_dict()` converts the single\
  \ AGE column into a Python dict for JSON\nserialisation by the MCP tool.\n\n## Spec\
  \ Scenarios (line-by-line verification)\n\n### Scenario: Node return\n> GIVEN a\
  \ query returning a single node\n> WHEN the result is formatted\n> THEN it is wrapped\
  \ as `{\"node\": {...properties...}}`\n\nImplementation: `isinstance(item, AgeVertex)`\
  \ → delegates to `_vertex_to_dict()`,\nreturned under the `\"node\"` key.\n\nTests\
  \ (existing — PASS):\n- `TestRowToDict.test_converts_single_vertex`\n- `TestVertexToDict.test_converts_vertex_properties`\n\
  - `TestVertexToDict.test_handles_empty_properties`\n\n**Status: ✅ fully covered.**\n\
  \n### Scenario: Edge return\n> GIVEN a query returning a single edge\n> WHEN the\
  \ result is formatted\n> THEN it is wrapped as `{\"edge\": {...properties...}}`\n\
  \nImplementation: `isinstance(item, AgeEdge)` → delegates to `_edge_to_dict()`,\n\
  returned under the `\"edge\"` key.\n\nTests (existing — PASS):\n- `TestRowToDict.test_converts_single_edge`\n\
  - `TestEdgeToDict.test_converts_edge_properties`\n- `TestEdgeToDict.test_handles_empty_properties`\n\
  \n**Status: ✅ fully covered.**\n\n### Scenario: Map return (multiple values)\n>\
  \ GIVEN a query returning a map (e.g., `RETURN {name: n.name, label: label(n)}`)\n\
  > WHEN the result is formatted\n> THEN map keys are preserved with nested nodes/edges\
  \ converted to dictionaries\n\nImplementation: `isinstance(item, dict)` → iterate\
  \ key-value pairs, convert\n`AgeVertex`/`AgeEdge` values, pass scalars through as-is.\n\
  \nTests (existing):\n- `TestRowToDict.test_converts_map_with_vertices` ✅ — two vertex\
  \ values\n\n**Missing tests — add these:**\n\n```python\ndef test_converts_map_with_edges(self,\
  \ repository):\n    \"\"\"Map result containing edge values — edges converted to\
  \ EdgeDicts.\"\"\"\n    edge = AgeEdge(id=10, label=\"KNOWS\", properties={\"since\"\
  : 2020})\n    edge.start_id = 1\n    edge.end_id = 2\n    row = ({\"relationship\"\
  : edge},)\n    result = repository._row_to_dict(row)\n    assert \"relationship\"\
  \ in result\n    assert result[\"relationship\"][\"id\"] == \"10\"\n    assert result[\"\
  relationship\"][\"label\"] == \"KNOWS\"\n    assert result[\"relationship\"][\"\
  start_id\"] == \"1\"\n    assert result[\"relationship\"][\"end_id\"] == \"2\"\n\
  \ndef test_converts_map_with_mixed_vertex_and_scalar(self, repository):\n    \"\"\
  \"Map with a vertex and a scalar — vertex converted, scalar preserved.\"\"\"\n \
  \   vertex = AgeVertex(id=1, label=\"Person\", properties={\"name\": \"Alice\"})\n\
  \    row = ({\"person\": vertex, \"count\": 42},)\n    result = repository._row_to_dict(row)\n\
  \    assert result[\"person\"][\"label\"] == \"Person\"\n    assert result[\"count\"\
  ] == 42\n\ndef test_converts_map_with_only_scalars(self, repository):\n    \"\"\"\
  Map with only scalar values — preserved as-is.\"\"\"\n    row = ({\"name\": \"Alice\"\
  , \"age\": 30},)\n    result = repository._row_to_dict(row)\n    assert result ==\
  \ {\"name\": \"Alice\", \"age\": 30}\n```\n\n**Status: ⚠️ partially covered — add\
  \ the three tests above.**\n\n### Scenario: Scalar return\n> GIVEN a query returning\
  \ a scalar value (e.g., count)\n> WHEN the result is formatted\n> THEN it is wrapped\
  \ as `{\"value\": scalar}`\n\nImplementation: fall-through `else` branch → `{\"\
  value\": item}`.\n\nTests (existing):\n- `TestRowToDict.test_converts_scalar_value`\
  \ — integer `42` ✅\n\n**Missing tests — add these:**\n\n```python\ndef test_converts_string_scalar(self,\
  \ repository):\n    \"\"\"String scalars are wrapped as {\"value\": <str>}.\"\"\"\
  \n    row = (\"hello\",)\n    result = repository._row_to_dict(row)\n    assert\
  \ result == {\"value\": \"hello\"}\n\ndef test_converts_none_scalar(self, repository):\n\
  \    \"\"\"None returned from the database is wrapped as {\"value\": None}.\"\"\"\
  \n    row = (None,)\n    result = repository._row_to_dict(row)\n    assert result\
  \ == {\"value\": None}\n\ndef test_converts_float_scalar(self, repository):\n  \
  \  \"\"\"Float scalars (e.g., similarity scores) are wrapped as {\"value\": float}.\"\
  \"\"\n    row = (0.95,)\n    result = repository._row_to_dict(row)\n    assert result\
  \ == {\"value\": 0.95}\n```\n\n**Status: ⚠️ partially covered — add the three tests\
  \ above.**\n\n## Files Affected\n\n- `src/api/tests/unit/query/test_query_repository.py`\n\
  \  — add tests to `TestRowToDict`:\n    - `test_converts_map_with_edges`\n    -\
  \ `test_converts_map_with_mixed_vertex_and_scalar`\n    - `test_converts_map_with_only_scalars`\n\
  \    - `test_converts_string_scalar`\n    - `test_converts_none_scalar`\n    - `test_converts_float_scalar`\n\
  \nNo implementation changes expected (the implementation already handles all\nthese\
  \ cases correctly; the tests verify it).\n\n## How to Verify\n\n```bash\ncd src/api\
  \ && uv run pytest tests/unit/query/test_query_repository.py::TestRowToDict -v\n\
  ```\n\nAll new tests pass without modifying `query_repository.py`. If any test fails,\n\
  fix the implementation (TDD: test is authoritative).\n\n## TDD Cycle\n\n1. Add all\
  \ six new tests to `TestRowToDict` — RED (before verifying they pass)\n2. Run: `cd\
  \ src/api && uv run pytest tests/unit/query/test_query_repository.py -v`\n3. If\
  \ GREEN immediately → implementation already correct, commit.\n4. If RED → fix `_row_to_dict()`\
  \ to handle the failing case, then GREEN.\n5. Commit atomically.\n\n## Design Context\n\
  \n- `NodeDict` and `EdgeDict` are TypedDicts (in `query/domain/value_objects.py`).\n\
  \  The `node`/`edge` dict wrapping is what downstream components (secure enclave,\n\
  \  internal property filter) use to identify entity dicts vs scalars.\n- `_row_to_dict`\
  \ only handles single-column rows (length-1 tuples). The\n  catch-all `{f\"col_{i}\"\
  : val}` for multi-column rows is a safety net that\n  should never be reached in\
  \ practice (AGE enforces single-column returns).\n- Tests in `TestRowToDict` are\
  \ already using `AgeVertex` and `AgeEdge` directly\n  from the `age.models` module\
  \ — follow the same import pattern.\n\n## Gap Analysis\n\nThe `mcp-server.spec.md`\
  \ Apache AGE Single-Column Return requirement has no prior\nhyperloop traceability\
  \ task. The implementation predates the intake process. This\ntask provides traceability\
  \ AND closes two concrete test gaps: map-with-edge and\nnon-integer scalar variants."
---
