---
task_id: task-003
round: 3
role: verifier
verdict: fail
---
## Task-003 — Graph Mutations: Re-verification Verdict

**Verification date:** 2026-04-26

---

## Numbered Check Results

| # | Check | Result | Detail |
|---|-------|--------|--------|
| 1 | Unit Tests (2518) | **PASS** | `uv run pytest tests/unit` — 2518 passed, 0 failed, 51 warnings |
| 2 | Linting (ruff check) | **PASS** | All checks passed |
| 3 | Formatting (ruff format) | **PASS** | 486 files already formatted |
| 4 | Type Checking (mypy) | **PASS** | No issues found in 486 source files |
| 5 | Architecture Boundary Tests | **PASS** | 40 tests passed |
| 6 | Integration Tests | NOT RUN | No running instance (infrastructure not available) |
| 7 | Code Review | **PASS** | See details below |

---

## .hyperloop/checks/ Results

### BLOCKING failures for this task

**1. check-branch-rebased-on-alpha.sh — FAIL**

The branch is **22 commits behind local `alpha`**. The local `alpha` branch has
been advanced by the orchestrator with process and intake commits not yet
pushed to `origin/alpha`. The task branch IS current with `origin/alpha`
(`33e9632d`), but the check uses the local `alpha` tip (`f36fc292`) which is
22 commits ahead.

```
Resolution: git rebase alpha
```

Missing commits include:
- `971d0247 chore(process): enforce DOO mandate with direct-logger check`
- `707a9570 chore(process): enforce domain exception HTTP mapping`
- `6551edb8 chore(process): require proof of rebase execution`
- `f36fc292 chore(process): handle "Agent future missing or failed"`
- (18 more chore/intake commits)

**Fix:** `git rebase alpha` from the task branch.

---

**2. check-no-state-file-commits.sh — FAIL**

21 `.hyperloop/state/` files appear in the diff between the local alpha
merge-base (`48a74d7d`) and `HEAD`. These files arrived via `git merge origin/alpha`
which incorporated IAM feature commits (`3ac824e6`, `f4500909`) that themselves
included orchestrator state files. The task implementation did not author
these files, but they are present in the branch history.

```
Files: .hyperloop/state/intake/2026-04-25-seventh-run.md
       .hyperloop/state/reviews/task-001-round-0.md
       .hyperloop/state/reviews/task-007-round-{0,1}.md
       ... (17 more)
```

**Fix:** After rebasing on local `alpha` (fix #1), verify this check passes.
If state files persist post-rebase, use an interactive rebase to drop the
offending commits or reset the branch from `alpha`.

---

**3. check-property-merge-semantics.sh — FAIL (false positive, task-introduced)**

The check correctly requires `||` merge semantics in SQL `SET properties =`
patterns. The PRODUCTION code in `graph/infrastructure/age_bulk_loading/queries.py`
correctly uses the `||` operator at all three locations. However, two
**test files added by this task** contain the old bad SQL pattern literally
in docstrings:

- `tests/integration/test_bulk_loading.py:240` — docstring reads:
  ```
  SET properties = (s.properties::text)::ag_catalog.agtype
  ```
- `tests/unit/graph/infrastructure/test_age_query_builder_update_merge.py:72` — docstring reads:
  `` `SET properties = (s.properties::text)::agtype` ``

These are intentional documentation of the anti-pattern the tests guard against,
but the check script's 300-character window around `SET properties =` finds no
`||` before the end of the docstring snippet.

**Fix:** Rephrase both docstrings to describe the bug without embedding the
literal SQL pattern. For example:

```python
# BEFORE (triggers false positive):
# The naive implementation `SET properties = (s.properties::text)::agtype`
# would silently drop any property...

# AFTER (avoids check):
# A naive direct-assignment implementation (without jsonb merge) would silently
# drop any property on the existing entity not present in the staging batch.
```

---

### Pre-existing failures (not introduced by this task)

The following checks also fail but on code NOT in the task-003 diff. They are
noted for completeness and are not actionable for this task:

| Check | Failing file | Note |
|-------|-------------|------|
| check-auth-status-codes.sh | `tests/integration/iam/test_group_authorization.py` etc. | IAM tests with 403 assertions; not in task diff |
| check-empty-test-stubs.sh | `tests/integration/test_api_key_auth.py:691` | `test_create_api_key_requires_tenant_membership` empty stub; not in task diff |
| check-failure-path-tests.sh | N/A | Script requires `<spec_file>` argument; fails when invoked without it |
| check-graceful-shutdown-cancel.sh | `infrastructure/outbox/worker.py` | `task.cancel()` in outbox worker; not in task diff |
| check-idempotency-tests.sh | N/A | Same scripting issue as check-failure-path-tests.sh |
| check-no-check-script-deletions.sh | 3 scripts missing `--exclude-dir=.venv` | Pre-existing at base commit `48a74d7d`; not introduced by this task |
| check-pages-have-tests.sh | `src/dev-ui/app/pages/auth/callback.vue` | Missing test for callback page; not in task diff |

---

## Code Review (numbered check #7)

### DOO Compliance — PASS
- `graph/presentation/routes.py` calls `probe.mutation_server_error_occurred()` instead of `logger.error()` directly. ✓
- `graph/application/observability/graph_service_probe.py` defines the new protocol method with appropriate docstring. ✓
- No `logger.*` or `print()` calls in production graph code. ✓

### Mock Usage — PASS (with note)
- `MagicMock(spec=structlog.stdlib.BoundLogger)` used in observability tests to verify probe calls — acceptable for testing the probe itself.
- `MagicMock()` used for `client` and `bulk_loading_strategy` in `test_mutation_applier_sort.py` — these are **infrastructure** dependencies (not domain aggregates); only the sort logic is being tested. Acceptable.
- The `check-route-handler-mock-coverage.sh` reports 2 warnings (bare `Mock()` applier in application tests) — these are pre-existing and do not affect this task's domain validation paths.

### DDD Layer Rules — PASS
- All 40 architecture boundary tests pass.
- Graph bounded context imports do not bleed into IAM/Management/etc.

### Commit Trailers — PASS
All implementation commits carry:
```
Spec-Ref: specs/graph/mutations.spec.md@85d49a379a52479b33f9b39994d76795066899a6
Task-Ref: task-003
```

### Hardcoded Secrets — PASS
No credentials or environment-specific values found in the diff.

---

## Spec Alignment (preserved from prior verification)

All 10 requirements from `specs/graph/mutations.spec.md` are implemented:

| Requirement | Status |
|------------|--------|
| Per-Tenant Graph Isolation | PASS — `get_tenant_graph_name()` → `f"tenant_{tenant_id}"` |
| KnowledgeGraph Scoping | PASS — SpiceDB `edit` check; `_stamp_knowledge_graph_id()` overwrites caller value |
| Mutation Log Format | PASS — JSONL parsing with line-number errors and blank-line skipping |
| DEFINE Operation | PASS — System properties auto-added for node and edge types |
| CREATE Operation | PASS — Idempotent merge via `jsonb ||`; referential checks; schema learning |
| UPDATE Operation | PASS — Set/remove properties with schema learning |
| DELETE Operation | PASS — Cascading detach delete for nodes; edge-only delete for edges |
| Mandatory System Properties | PASS — `validate_operation()` in `value_objects.py` |
| Deterministic Entity IDs | PASS — Pydantic regex `{type}:{16_hex_chars}` |
| Referential Integrity Ordering | PASS — `_sort_operations()`: DEFINE → DELETE(edge/node) → CREATE(node/edge) → UPDATE |

---

## Required Actions Before Merge

1. **Rebase on local `alpha`:** `git rebase alpha`
   - Resolves the staleness check (22 commits behind)
   - May resolve state file contamination
2. **Fix test docstrings** in:
   - `src/api/tests/integration/test_bulk_loading.py` (~line 238–242): rephrase docstring to not contain literal `SET properties =` SQL
   - `src/api/tests/unit/graph/infrastructure/test_age_query_builder_update_merge.py` (~line 70–75): same fix
3. **Re-run checks** after rebase to confirm `check-no-state-file-commits.sh` passes.
4. **Re-run** `check-property-merge-semantics.sh` to confirm false positive is resolved.

The core implementation is complete and correct. All spec requirements are covered,
all unit/type/lint/arch tests pass. Only process/structural issues need resolution.