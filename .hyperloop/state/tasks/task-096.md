---
id: task-096
title: MCP server — Apache AGE Single-Column Return requirement spec alignment
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add missing _row_to_dict tests for map-with-edge and scalar variants"
pr_description: |
  ## What & Why

  The **Requirement: Apache AGE Single-Column Return** in
  `specs/query/mcp-server.spec.md` specifies how query result rows must be
  formatted for MCP clients. Apache AGE (A Graph Extension for PostgreSQL)
  requires all Cypher `RETURN` clauses to emit a single column; this requirement
  documents how the Querying context normalises that single column into structured
  Python dicts that MCP agents can consume.

  The requirement has four scenarios. All four are implemented in
  `QueryGraphRepository._row_to_dict()`, but **two sub-types are not exercised
  by any existing test**:

  1. **Map return with a nested edge** — `test_converts_map_with_vertices` exists
     but no equivalent test covers a map that contains an `AgeEdge` value.
  2. **Non-integer scalar variants** — `test_converts_scalar_value` uses an integer
     (`42`). No test covers a string scalar, a float, or `None`.

  These gaps could hide regressions if `_row_to_dict()` is refactored.

  ## Background — Apache AGE single-column constraint

  AGE returns results as PostgreSQL rows. A Cypher query that logically returns
  multiple values must wrap them in a map:

  ```cypher
  -- AGE requires this (single column):
  MATCH (p:Person)-[r:KNOWS]->(q) RETURN {person: p, rel: r}
  -- NOT this (multi-column, AGE rejects it):
  MATCH (p:Person)-[r:KNOWS]->(q) RETURN p, r
  ```

  `_row_to_dict()` converts the single AGE column into a Python dict for JSON
  serialisation by the MCP tool.

  ## Spec Scenarios (line-by-line verification)

  ### Scenario: Node return
  > GIVEN a query returning a single node
  > WHEN the result is formatted
  > THEN it is wrapped as `{"node": {...properties...}}`

  Implementation: `isinstance(item, AgeVertex)` → delegates to `_vertex_to_dict()`,
  returned under the `"node"` key.

  Tests (existing — PASS):
  - `TestRowToDict.test_converts_single_vertex`
  - `TestVertexToDict.test_converts_vertex_properties`
  - `TestVertexToDict.test_handles_empty_properties`

  **Status: ✅ fully covered.**

  ### Scenario: Edge return
  > GIVEN a query returning a single edge
  > WHEN the result is formatted
  > THEN it is wrapped as `{"edge": {...properties...}}`

  Implementation: `isinstance(item, AgeEdge)` → delegates to `_edge_to_dict()`,
  returned under the `"edge"` key.

  Tests (existing — PASS):
  - `TestRowToDict.test_converts_single_edge`
  - `TestEdgeToDict.test_converts_edge_properties`
  - `TestEdgeToDict.test_handles_empty_properties`

  **Status: ✅ fully covered.**

  ### Scenario: Map return (multiple values)
  > GIVEN a query returning a map (e.g., `RETURN {name: n.name, label: label(n)}`)
  > WHEN the result is formatted
  > THEN map keys are preserved with nested nodes/edges converted to dictionaries

  Implementation: `isinstance(item, dict)` → iterate key-value pairs, convert
  `AgeVertex`/`AgeEdge` values, pass scalars through as-is.

  Tests (existing):
  - `TestRowToDict.test_converts_map_with_vertices` ✅ — two vertex values

  **Missing tests — add these:**

  ```python
  def test_converts_map_with_edges(self, repository):
      """Map result containing edge values — edges converted to EdgeDicts."""
      edge = AgeEdge(id=10, label="KNOWS", properties={"since": 2020})
      edge.start_id = 1
      edge.end_id = 2
      row = ({"relationship": edge},)
      result = repository._row_to_dict(row)
      assert "relationship" in result
      assert result["relationship"]["id"] == "10"
      assert result["relationship"]["label"] == "KNOWS"
      assert result["relationship"]["start_id"] == "1"
      assert result["relationship"]["end_id"] == "2"

  def test_converts_map_with_mixed_vertex_and_scalar(self, repository):
      """Map with a vertex and a scalar — vertex converted, scalar preserved."""
      vertex = AgeVertex(id=1, label="Person", properties={"name": "Alice"})
      row = ({"person": vertex, "count": 42},)
      result = repository._row_to_dict(row)
      assert result["person"]["label"] == "Person"
      assert result["count"] == 42

  def test_converts_map_with_only_scalars(self, repository):
      """Map with only scalar values — preserved as-is."""
      row = ({"name": "Alice", "age": 30},)
      result = repository._row_to_dict(row)
      assert result == {"name": "Alice", "age": 30}
  ```

  **Status: ⚠️ partially covered — add the three tests above.**

  ### Scenario: Scalar return
  > GIVEN a query returning a scalar value (e.g., count)
  > WHEN the result is formatted
  > THEN it is wrapped as `{"value": scalar}`

  Implementation: fall-through `else` branch → `{"value": item}`.

  Tests (existing):
  - `TestRowToDict.test_converts_scalar_value` — integer `42` ✅

  **Missing tests — add these:**

  ```python
  def test_converts_string_scalar(self, repository):
      """String scalars are wrapped as {"value": <str>}."""
      row = ("hello",)
      result = repository._row_to_dict(row)
      assert result == {"value": "hello"}

  def test_converts_none_scalar(self, repository):
      """None returned from the database is wrapped as {"value": None}."""
      row = (None,)
      result = repository._row_to_dict(row)
      assert result == {"value": None}

  def test_converts_float_scalar(self, repository):
      """Float scalars (e.g., similarity scores) are wrapped as {"value": float}."""
      row = (0.95,)
      result = repository._row_to_dict(row)
      assert result == {"value": 0.95}
  ```

  **Status: ⚠️ partially covered — add the three tests above.**

  ## Files Affected

  - `src/api/tests/unit/query/test_query_repository.py`
    — add tests to `TestRowToDict`:
      - `test_converts_map_with_edges`
      - `test_converts_map_with_mixed_vertex_and_scalar`
      - `test_converts_map_with_only_scalars`
      - `test_converts_string_scalar`
      - `test_converts_none_scalar`
      - `test_converts_float_scalar`

  No implementation changes expected (the implementation already handles all
  these cases correctly; the tests verify it).

  ## How to Verify

  ```bash
  cd src/api && uv run pytest tests/unit/query/test_query_repository.py::TestRowToDict -v
  ```

  All new tests pass without modifying `query_repository.py`. If any test fails,
  fix the implementation (TDD: test is authoritative).

  ## TDD Cycle

  1. Add all six new tests to `TestRowToDict` — RED (before verifying they pass)
  2. Run: `cd src/api && uv run pytest tests/unit/query/test_query_repository.py -v`
  3. If GREEN immediately → implementation already correct, commit.
  4. If RED → fix `_row_to_dict()` to handle the failing case, then GREEN.
  5. Commit atomically.

  ## Design Context

  - `NodeDict` and `EdgeDict` are TypedDicts (in `query/domain/value_objects.py`).
    The `node`/`edge` dict wrapping is what downstream components (secure enclave,
    internal property filter) use to identify entity dicts vs scalars.
  - `_row_to_dict` only handles single-column rows (length-1 tuples). The
    catch-all `{f"col_{i}": val}` for multi-column rows is a safety net that
    should never be reached in practice (AGE enforces single-column returns).
  - Tests in `TestRowToDict` are already using `AgeVertex` and `AgeEdge` directly
    from the `age.models` module — follow the same import pattern.

  ## Gap Analysis

  The `mcp-server.spec.md` Apache AGE Single-Column Return requirement has no prior
  hyperloop traceability task. The implementation predates the intake process. This
  task provides traceability AND closes two concrete test gaps: map-with-edge and
  non-integer scalar variants.
---
