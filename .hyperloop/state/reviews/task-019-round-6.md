---
task_id: task-019
round: 6
role: verifier
verdict: fail
---
## Verification Summary — specs/management/credentials.spec.md (round 4)

The branch has been contaminated by orchestrator intake commits that ran on
this task branch after the previous PASS verdict was recorded. The backend
check suite now fails on 3 mandatory checks.

---

## Backend Suite Results

| Check | Result |
|-------|--------|
| check-no-check-script-deletions.sh | PASS |
| check-process-overlays-intact.sh | PASS |
| check-branch-has-commits.sh | PASS |
| check-branch-rebased-on-alpha.sh | PASS (2 commits behind — acceptable) |
| check-no-state-file-commits.sh | **FAIL** |
| check-no-source-regressions.sh | **FAIL** |
| check-no-test-regressions.sh | **FAIL** |
| check-empty-test-stubs.sh | PASS |
| check-domain-aggregate-mocks.sh | PASS |
| check-no-direct-logger-usage.sh | PASS |
| check-no-coming-soon-stubs.sh | PASS |
| check-weak-test-assertions.sh | PASS |
| check-di-wiring-updated.sh | PASS |
| check-pytest-env-skip-if-set.sh | PASS |
| check-cascade-delete-empty-collection-mocks.sh | PASS |
| Unit tests (uv run pytest tests/unit) | PASS (2405 passed) |

---

## Root Cause: Orchestrator Contamination

All three failures trace to a single commit on this branch:

```
13ba0b7a chore(intake): record Run 6 review of index and NFR specs — no tasks created
```

This intake commit (an orchestrator operation that ran directly on this task
branch) accidentally deleted the following files that exist on alpha:

**Deleted source files:**
- `src/api/management/dependencies/encryption_keys.py`
- `src/api/management/presentation/auth_bridge.py`

**Deleted test files:**
- `src/api/tests/unit/iam/domain/test_workspace_role_hierarchy.py`
- `src/api/tests/unit/iam/presentation/test_tenant_routes.py`
- `src/api/tests/unit/management/presentation/test_knowledge_graph_routes.py`

Additionally, this and other intake commits added 38 `.hyperloop/state/` files
to the branch's git history, contaminating it with orchestrator-managed metadata.

---

## Implementation Quality (Unchanged — Previously Verified PASS)

The task-019 implementation commits are correct and complete:

| Commit | Description | Trailers |
|--------|-------------|---------|
| `07dd3715` | test: add tenant isolation unit tests for FernetSecretStore | Spec-Ref ✓, Task-Ref ✓ |
| `3ed67df2` | feat(management): cascade credential deletion on KG delete | Spec-Ref ✓, Task-Ref ✓ |
| `5e5e4b35` | fix(test): replace bare MagicMock() with real DataSource instances | Spec-Ref ✓, Task-Ref ✓ |
| `bd7456b5` | test(iam): add non-empty group cascade test in TestDeleteTenant | Spec-Ref ✓, Task-Ref ✓ |

Spec coverage:
- Credential Encryption (FernetSecretStore store/retrieve) — PASS
- Tenant Isolation (composite PK path + tenant_id) — PASS
- Key Rotation (MultiFernet with fallback keys) — PASS
- Credential Lifecycle / data source deletion — PASS
- Credential Lifecycle / knowledge graph cascade — PASS

---

## Required Fix: Cherry-Pick to Clean Branch

The branch history cannot be cleaned without a rewrite. The ONLY viable fix is:

**Step 1 — Create a clean branch from current alpha:**
```bash
git checkout alpha
git checkout -b hyperloop/task-019-clean
```

**Step 2 — Cherry-pick the 4 delivery commits (in order):**
```bash
git cherry-pick 07dd3715  # test: tenant isolation unit tests
git cherry-pick 3ed67df2  # feat: cascade credential deletion on KG delete
git cherry-pick 5e5e4b35  # fix: replace MagicMock with real DataSource instances
git cherry-pick bd7456b5  # test: non-empty group cascade test in TestDeleteTenant
```

**Step 3 — Run the full backend suite:**
```bash
bash .hyperloop/checks/check-run-backend-suite.sh
```
Expected: all 15 checks PASS.

**Step 4 — Write PASS verdict and force-push to task-019:**
```bash
git checkout -b hyperloop/task-019  # or force-push clean branch to remote
```

Do NOT cherry-pick any intake, process, or chore commits — only the 4 commits
listed above contain the task-019 implementation.