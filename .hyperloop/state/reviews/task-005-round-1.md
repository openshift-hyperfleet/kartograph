---
task_id: task-005
round: 1
role: verifier
verdict: fail
---
## Verifier Verdict — task-005 (specs/graph/schema.spec.md)

Date: 2026-04-28

---

## Summary

The task-005 implementation (GET /graph/schema/ontology endpoint + comprehensive schema route
tests) is functionally correct and well-structured. All quality checks pass when run
against the source directly. However, **two automated branch-hygiene checks fail** that
must be resolved before merge.

---

## Check Results

### 1. Unit Tests — PASS
2525 tests passed, 0 failures, 0 errors.

### 2. Linting (ruff check) — PASS
Zero violations across 497 files.

### 3. Formatting (ruff format) — PASS
All 497 files already formatted.

### 4. Type Checking (mypy) — PASS
Zero errors across 497 source files.

### 5. Architecture Boundary Tests — PASS
40/40 passed. No bounded-context import violations.

### 6. Integration Tests — NOT RUN
Task adds a presentation-layer route with no new infrastructure changes.
No integration suite run required.

### 7. Code Review

#### FAIL — check-no-foreign-task-commits.sh
Seven commits tagged `Task-Ref=process-improvement` are present on this branch:

```
41ce47cad  chore(process): add implementer and verifier rules from task-005 findings
a1ba8c951  chore(process): prohibit cherry-pick as a mechanism for picking up upstream commits
f1689a380  chore(process): add process-improvement agent overlay to prevent task-branch contamination
81f0b65e9  chore(process): honor Removes: trailer and tighten pre-commit restore gate
2c978315d  chore(process): recreate check-alpha-local-vs-remote and teach MISSING-check remediation
573750b77  chore(process): guard against overlay content regressions and worker-result deletion commits
47c339956  chore(process): enforce branch hygiene and close test-regression baseline gap
```

All seven commits are already present on `alpha` (with different hashes, i.e. they were
submitted to alpha independently). They must be removed from the task branch.

#### FAIL — check-branch-rebased-on-alpha.sh
The branch is 11 commits behind alpha HEAD (`1829028ef`). The stale state also causes
`check-run-backend-suite.sh` to abort early.

**Fix (both issues resolved by a single rebase):**
```bash
git rebase alpha
# git will incorporate the 7 process-improvement commits from alpha and
# drop the duplicate copies on the task branch, leaving only:
#   1576a42c9  test(graph): add schema route and same-label entity-type-scoping tests
#   aa1f2f0d5  feat(graph): add GET /graph/schema/ontology endpoint
uv run pytest tests/unit -v   # confirm still green
```

#### PASS — check-worker-result-not-committed.sh
No `.hyperloop/worker-result.yaml` appears in any branch commit.
(The previous round's violation — a deletion of the file in commit 1a4951e9f —
has been corrected; that commit is no longer on the branch.)

#### PASS — check-no-test-regressions.sh
Pass 1 (vs merge-base 605405ec) and Pass 2 (vs alpha HEAD 1829028ef): no regressions.

#### PASS — Task-Ref and Spec-Ref trailers
Both implementation commits carry:
  `Task-Ref: task-005`
  `Spec-Ref: specs/graph/schema.spec.md@85d49a379a52479b33f9b39994d76795066899a6`

#### PASS — No direct logger/print usage
All observability flows through domain probes.

#### PASS — No domain aggregate mocks
`mock_schema_service` is a `Mock()` of an application-layer service — consistent
with existing `mock_mutation_service` and `mock_enclave_service` patterns in the
same file. No domain aggregates are mocked.

#### PASS — No empty test stubs, no future-placeholder comments

#### PASS — Spec scenario coverage
All spec scenarios are exercised:
- Ontology Retrieval → `TestGetOntologyRoute` (3 tests)
- Label Listing (nodes, search, has_property) → `TestGetNodeLabelsRoute` / `TestGetEdgeLabelsRoute`
- Type Definition Lookup (200, 404) → `TestGetNodeSchemaRoute` / `TestGetEdgeSchemaRoute`
- Same label, different entity types → `test_schema_service.py::TestGetNodeSchema::test_same_label_different_entity_types_scoped_correctly`
- Route-level wiring for all endpoints → `mock_schema_service` override in `test_client` fixture

Schema Evolution (new property discovered) is a pre-existing service/domain behaviour
not requiring a new route; not a gap introduced by this task.

---

## What Needs Fixing

**One action resolves both failures:**

```bash
git rebase alpha
uv run pytest tests/unit -v
# push when green
```

The rebase incorporates the 7 process-improvement commits from upstream alpha,
automatically dropping the duplicate copies on this branch. No source code changes
are needed — the implementation is correct as-is.