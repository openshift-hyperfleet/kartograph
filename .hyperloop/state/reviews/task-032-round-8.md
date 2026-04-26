---
task_id: task-032
round: 8
role: verifier
verdict: fail
---
## Task-032 — Groups Feature — Round 11

Branch: `hyperloop/task-032`
Spec: `specs/iam/groups.spec.md`
Date: 2026-04-26

---

### Summary

The groups feature implementation is **correct and complete** — all 175
group-specific unit tests pass, all 2401 unit tests pass, linting/formatting/
type-checking pass, and architecture boundary tests pass. All spec requirements
remain fully covered.

However, `check-run-backend-suite.sh` **fails** with 4 failing checks.  All 4
failures trace to pre-existing technical debt on alpha that was present at the
merge-base (`af817054`) — none were introduced by this task. Despite their
pre-existing origin, the verification protocol requires `FAIL` until the full
suite passes.

**Verdict: FAIL**

---

### Code-Quality Checks (PASS)

| Check | Result |
|---|---|
| Unit tests (2401 total, 175 groups-specific) | **PASS** |
| Ruff linting | **PASS** |
| Ruff formatting | **PASS** |
| Mypy type checking | **PASS** (zero errors) |
| Architecture boundary tests (40/40) | **PASS** |

---

### Process Check Suite (`check-run-backend-suite.sh`)

Run from worktree root.  Alpha at `3c8349ea`.

| Check | Result |
|---|---|
| check-no-check-script-deletions | **FAIL** (see below) |
| check-process-overlays-intact | PASS |
| check-branch-has-commits | PASS |
| check-branch-rebased-on-alpha | PASS (1 commit behind — within range) |
| check-no-state-file-commits | PASS |
| check-no-source-regressions | PASS |
| check-no-test-regressions | PASS |
| check-empty-test-stubs | **FAIL** (see below) |
| check-domain-aggregate-mocks | **FAIL** (see below) |
| check-no-direct-logger-usage | **FAIL** (see below) |
| check-no-coming-soon-stubs | PASS |
| check-weak-test-assertions | PASS |
| check-di-wiring-updated | PASS |

---

### Failing Checks — Required Remediation

All 4 failures are pre-existing on alpha at `af817054` (the merge-base) and
were present before task-032 started. Nevertheless, the suite must fully pass
before the verdict can be recorded as PASS.

---

#### 1. FAIL — `check-no-check-script-deletions.sh`

The check flags scripts using `grep --include=` without `--exclude-dir=.venv`.

**Investigation note:** Two of the five flagged scripts are false positives —
they use the **quoted** form `--exclude-dir=".venv"` while the detection regex
looks for the unquoted form `--exclude-dir=.venv`.  The check script itself has
a detection bug.

Real violations (genuinely missing `.venv` exclusion):
- `.hyperloop/checks/check-auth-status-codes.sh` — uses `--include=` without
  any `.venv` exclusion.

False positives (have `.venv` exclusion but with quotes):
- `.hyperloop/checks/check-domain-exception-http-mapping.sh` — has
  `--exclude-dir=".venv"` on line 40.
- `.hyperloop/checks/check-no-direct-logger-usage.sh` — has
  `--exclude-dir=".venv"` on lines 22 and 36.

Frontend scripts (do not scan Python, `.venv` exclusion not applicable):
- `.hyperloop/checks/check-fake-success-notifications.sh`
- `.hyperloop/checks/check-pages-have-tests.sh`

**Fix:** Add `--exclude-dir=.venv` (unquoted) to
`check-auth-status-codes.sh`.  Additionally, update
`check-no-check-script-deletions.sh` to accept both quoted and unquoted forms
(e.g. change the detection grep to `--exclude-dir=.*.venv`), or change the two
quoted-form scripts to unquoted form so all scripts are consistent.

---

#### 2. FAIL — `check-empty-test-stubs.sh`

```
src/api/tests/integration/test_api_key_auth.py:691:
    test_create_api_key_requires_tenant_membership
```

This test function contains only a docstring explaining why it was skipped —
no assertions, no real test body.

**Fix:** Implement the test body.  The docstring says it requires a third user
who is not a tenant member.  The fake OIDC provider (`tests/fakes/oidc_provider.py`)
can be extended to issue a token for a third user (e.g. `carol`) who is
**not** added to the test tenant.  Use that token to call POST `/api-keys` and
assert `401` or `403`.  Alternatively, if the scenario genuinely cannot be
tested with the current infrastructure, document the gap as a `pytest.skip()`
call with a reason string — the check only blocks entirely empty bodies.

---

#### 3. FAIL — `check-domain-aggregate-mocks.sh`

```
src/api/tests/unit/management/application/test_knowledge_graph_service.py
    592:  ds1 = MagicMock()
    593:  ds2 = MagicMock()
```

**Fix (management context):** Locate or create a `_make_ds()` factory helper
in the management test suite (e.g. in
`tests/unit/management/application/conftest.py` or alongside the failing test
class) that constructs a real `DataSource` domain object.  Replace both
`MagicMock()` calls with `_make_ds(...)`.  If only the interface is needed
(no validation), `MagicMock(spec=DataSource)` is also acceptable.

---

#### 4. FAIL — `check-no-direct-logger-usage.sh`

```
src/api/query/presentation/mcp.py:197:
    print(source["content"])  # Full AsciiDoc content starting from title
```

**Fix:** Remove the bare `print()` call.  Per the DOO mandate, all
observability must go through domain probes.  If the content genuinely needs
to be logged, add a probe method (e.g.
`probe.source_content_traced(content: str)`) to the `QueryProbe` protocol and
its default implementation, inject the probe via FastAPI `Depends`, and call
`probe.source_content_traced(source["content"])`.  If this was debug code,
simply delete the line.

---

### Secondary Concern — `check-deps-satisfied.sh` Modified

`check-deps-satisfied.sh` was modified on this branch (the only source-code
diff beyond process/verdict files).  The secondary git-ancestry stale-state
detection block was removed.  This makes the check more strict (it no longer
accepts a dep whose branch is merged into alpha but whose state file still
shows "in-progress"), which is a process regression for the broader pipeline.

**Not a blocker for this verdict** (the change doesn't cause any check to
fail), but the orchestrator should review whether to restore the stale-state
detection on alpha.

---

### Spec Coverage (all COVERED — implementation is on alpha)

| Requirement | Status |
|---|---|
| Group Creation — ULID generated, creator gets `admin` role | COVERED |
| Group Creation — duplicate name in tenant returns 409 | COVERED |
| Group Name Validation — 1–255 chars (trimmed) accepted | COVERED |
| Group Name Validation — empty/whitespace returns 422 | COVERED |
| Group Retrieval — authorized user returns 200 with details | COVERED |
| Group Retrieval — unauthorized/non-existent returns 404 | COVERED |
| Group Listing — only groups with `view` permission returned | COVERED |
| Group Rename — `manage` permission, unique name succeeds | COVERED |
| Group Rename — duplicate name returns 409 | COVERED |
| Group Deletion — `manage` permission, member snapshot captured | COVERED |
| Member Add — `manage` permission, `member` role granted | COVERED |
| Member Role Change — old role revoked, new granted | COVERED |
| Member Remove — role revoked | COVERED |
| Last-admin guard — demote or remove last admin rejected | COVERED |
| Member Listing — `view` permission returns all members with roles | COVERED |
| Workspace Access Inheritance — group→workspace role propagation | COVERED |
| Member added after group assigned to workspace gets workspace perms | COVERED |
| Member removed from group loses inherited workspace permissions | COVERED |
| Group Roles — admin has `manage`+`view`, included in workspace inheritance | COVERED |
| Group Roles — member has `view`, included in workspace inheritance | COVERED |

---

### Required Fix Order

1. Fix `check-auth-status-codes.sh` — add `--exclude-dir=.venv` (and/or fix
   the detection logic in `check-no-check-script-deletions.sh`).
2. Implement `test_create_api_key_requires_tenant_membership` test body in
   `tests/integration/test_api_key_auth.py`.
3. Replace `MagicMock()` with real `DataSource` objects in
   `tests/unit/management/application/test_knowledge_graph_service.py:592-593`.
4. Remove `print(source["content"])` from `query/presentation/mcp.py:197` and
   replace with a probe call.
5. Re-run: `bash .hyperloop/checks/check-run-backend-suite.sh` from worktree
   root — must exit 0.
6. Re-run: `cd src/api && uv run pytest tests/unit -q` — must pass.
7. Commit fixes with conventional commit messages and Spec-Ref / Task-Ref
   trailers on relevant commits.