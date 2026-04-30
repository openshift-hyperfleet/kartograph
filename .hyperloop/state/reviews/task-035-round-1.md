---
task_id: task-035
round: 1
role: verifier
verdict: fail
---
## Verification Summary for task-035 (Knowledge Graphs) — Re-Review Pass 2

Branch is now clean: 1 commit ahead of alpha, no foreign commits, all canonical checks pass. The previous review's branch hygiene issues (stale branch, foreign process-improvement commits, missing Task-Ref trailers) are fully resolved. However, one check script in `.hyperloop/checks/` fails for task-035's own bounded context.

---

## Check Results

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Unit tests (2677 tests) | ✅ PASS | All 2677 tests pass |
| 2 | Ruff linting | ✅ PASS | Zero violations |
| 3 | Ruff formatting | ✅ PASS | 538 files already formatted |
| 4 | MyPy type checking | ✅ PASS | Zero errors in 538 source files |
| 5 | Architecture boundary tests (40 tests) | ✅ PASS | All pass |
| 6 | Integration tests | N/A | This commit adds unit-level route tests only |
| 7 | Code review | ✅ PASS | See details below |
| — | `check-run-backend-suite.sh` (canonical) | ✅ PASS | ALL PASS (28 checks) |
| — | `check-branch-rebased-on-alpha.sh` | ✅ PASS | 0 commits behind alpha |
| — | `check-no-foreign-task-commits.sh` | ✅ PASS | No foreign-task commits |
| — | `check-all-commits-have-task-ref.sh` | ✅ PASS | Task-Ref: task-035 present |
| — | `check-no-source-regressions.sh` | ✅ PASS | No unspecified symbol removals |
| — | `check-alpha-local-vs-remote.sh` | ✅ PASS | Local alpha == origin/alpha (cf293495) |
| — | `check-cascade-delete-rollback-test.sh` | ❌ FAIL | `knowledge_graph_service` missing rollback integration test |
| — | `check-process-agent-not-on-task-branch.sh` | N/A | Pre-commit guard for process agent; always exits 1 on task branches by design — not a review check |

---

## Failing Check: `check-cascade-delete-rollback-test.sh`

The check reports three missing rollback integration tests. Two (`workspace_service`, `data_source_service`) are pre-existing technical debt outside task-035's scope and should not block this task. **One is directly in scope:**

```
--- MISSING rollback integration test: src/api/management/application/services/knowledge_graph_service.py ---
  Resource slug : knowledge_graph
  This service has both 'async def delete' and 'session.begin()' —
  a transactional cascade delete that MUST be exercised with a rollback test.
```

The spec explicitly mandates this guarantee:

> AND if any step fails, the entire deletion rolls back with no partial state

The `check-cascade-delete-rollback-test.sh` was added to alpha (`cf293495`) specifically to enforce this pattern. The KG cascade delete implementation is correct, but the rollback integration test was never written.

### Required Fix

Add an integration test to `src/api/tests/integration/management/` (e.g., `test_knowledge_graph_service.py`) that:

1. Creates a knowledge graph with at least one child data source (including credentials).
2. Injects a simulated failure mid-transaction (e.g., raises inside the `async with session.begin()` block after one step).
3. Asserts that **neither** the knowledge graph **nor** any of its child data sources were deleted (full rollback confirmed).

This must be an integration test using a real `async_session` — mock sessions cannot verify SQLAlchemy transaction rollback semantics.

Example skeleton (mirrors existing `test_rollback_removes_both_group_and_outbox_entry` in the IAM context):

```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_knowledge_graph_deletion_rollback_on_failure(
    async_session, knowledge_graph_repository, data_source_repository, ...
):
    # arrange: create KG with child data source
    ...
    # act: simulate failure mid-transaction
    try:
        async with async_session.begin():
            await data_source_repository.delete(data_source)
            raise Exception("simulated failure before KG delete")
    except Exception:
        pass
    # assert: both parent and child still exist
    assert await knowledge_graph_repository.get_by_id(kg.id) is not None
    assert await data_source_repository.get_by_id(ds.id) is not None
```

---

## Code Review (PASS)

The single task-035 commit (`2e0536f6b`) is well-structured:

- **Service layer fix**: `KnowledgeGraphService.update()` now raises `KnowledgeGraphNotFoundError` (typed domain exception) instead of `ValueError` for both not-found cases. This correctly maps to HTTP 404 via the PATCH route handler.
- **Route handler**: `update_knowledge_graph` has explicit `except KnowledgeGraphNotFoundError` → 404, `except UnauthorizedError` → 403, `except DuplicateKnowledgeGraphNameError` → 409, `except ValueError` → 400 (now dead code, harmless). All new routes (GET workspace KGs, PATCH, DELETE) are present and correct.
- **Tests**: `TestListWorkspaceKnowledgeGraphsRoute`, `TestUpdateKnowledgeGraphRoute`, `TestDeleteKnowledgeGraphRoute` cover happy paths and all error responses (200/204/403/404/409/422). Argument delegation is verified with `assert_called_once_with`. No bare MagicMock on domain aggregates. No raw logger usage.
- **Commit trailers**: `Spec-Ref: specs/management/knowledge-graphs.spec.md` and `Task-Ref: task-035` both present.

---

## Action Required

Add the KG cascade-delete rollback integration test and push to `hyperloop/task-035`. No other changes are required. All other aspects of this implementation are clean and correct.