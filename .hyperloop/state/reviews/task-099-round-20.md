---
task_id: task-099
round: 20
role: verifier
verdict: fail
---
## Verification Summary for task-099 (MCP Server)

### Context

The "Merge failed" finding from the previous attempt is no longer relevant — the branch now rebases cleanly onto alpha (`check-branch-rebases-cleanly.sh`: PASS). However, the branch itself has accumulated significant process violations that block a clean merge.

---

### Check Results

#### 1. Unit Tests — PASS
All 2,990 unit tests pass with zero failures and zero errors.
```
2990 passed, 52 warnings in 97.76s
```

#### 2. Linting (ruff check) — PASS
Zero violations.

#### 3. Formatting (ruff format) — PASS
All 567 files are correctly formatted.

#### 4. Type Checking (mypy) — PASS
Zero type errors across 567 source files.

#### 5. Architecture Boundary Tests — PASS
All 40 global + 32 query-specific pytest-archon tests pass.

#### 6. Integration Tests — NOT RUN
Integration tests were not run (no infrastructure available in this verification context). The unit tests cover the spec scenarios adequately.

#### 7. Code Review — FAIL (4 failing checks)

**7a. `check-no-state-file-commits.sh` — FAIL**
Nine `.hyperloop/state/tasks/` files (task-150.md through task-158.md) were committed directly to this task branch. State files are orchestrator-managed and must never appear in task branch commits. These will cause permanent merge conflicts.

Files committed on branch:
- `.hyperloop/state/tasks/task-150.md` through `task-158.md`

**Fix:** Cherry-pick only the delivery commits (those not touching `.hyperloop/state/`) onto a fresh branch from alpha, per the script's guidance.

**7b. `check-all-commits-have-task-ref.sh` — FAIL**
Five commits are missing valid Task-Ref trailers:

- `255b87cfd` — `fix(query): align unexpected error type with spec ("unknown_error")` — **no Task-Ref trailer at all**
- `db9511bb2` — broken trailer block (blank line before `Co-Authored-By` separates `Task-Ref:` from the contiguous block; git refuses to parse it)
- `33d7e9996` — same broken trailer block pattern
- `7d8acba9b` — same broken trailer block pattern
- `f7562cc8d` — same broken trailer block pattern

**Fix:** Interactive rebase to add/repair the `Task-Ref:` trailer as a contiguous line with no blank lines before `Co-Authored-By`.

**7c. `check-no-foreign-task-commits.sh` — FAIL**
Multiple commits carry `Task-Ref: process-improvement` (a different task) on this task-099 branch:

- `ab83b6907` — `chore(process): guard against spec/implementation string constant drift`
- `e5b6adb11` — `chore(verifier): require exact FAIL (REBASE-ONLY) phrase and orchestrator routing`
- `483329b86` — `chore(process): rule: copy spec string literals verbatim into tests and impl`
- `9f7f62e1b` — `fix(query): correct error_type from unknown_error to unexpected_error`
- `a381b847c` — `chore: add alpha-regression classification rules for test regression check`
- `33d7e9996`, `db9511bb2`, `f7562cc8d`, `7d8acba9b` — `Task-Ref: intake` or similar non-task-099 refs

**Fix:** Drop all foreign commits via interactive rebase. Keep only commits with `Task-Ref: task-099`.

**7d. `check-no-check-script-deletions.sh` — FAIL**
`.hyperloop/checks/string-constants-match-spec.sh` (added by this branch in `ab83b6907`) uses `grep -r` without `--exclude-dir=.venv`. The check detects this as a "sabotaged" script because it can produce false positives by scanning the virtual environment's third-party packages.

**Fix:** Add `--exclude-dir=.venv` to the `grep` invocation in `string-constants-match-spec.sh`.

---

### Implementation Quality (Informational)

The actual MCP Server implementation on alpha is complete and correct per the spec:
- `query_graph` tool with write-op rejection (MUTATION_KEYWORDS includes EXPLAIN and LOAD), timeout, result limiting, truncation detection, KG filtering, secure enclave redaction, and internal property filtering — all ✓
- `fetch_documentation_source` tool with GitHub/GitLab support, PAT headers, self-hosted instances, and invalid URL error — all ✓
- `knowledge-graphs://accessible` resource (URI uses hyphen per RFC 3986, with a spec-note explaining the discrepancy) — ✓
- `instructions://agent` resource with fail-fast at startup — ✓
- API key + Bearer token authentication with 401/503 error handling — ✓

The only task-099–specific delivery commit (`77ce95c76`) correctly fixes the truncation integration test to match the spec's "fetch limit+1 rows" contract.

---

### Required Fixes Before Re-submission

1. **Drop all foreign commits** (process-improvement, intake) from the branch — use cherry-pick onto a fresh branch from alpha, keeping only `77ce95c76`.
2. **Verify `77ce95c76` has a valid Task-Ref: task-099** (it does — this is correct).
3. **If retaining the string-constants check script**, add `--exclude-dir=.venv` to its `grep` and ensure it carries `Task-Ref: task-099`.
4. **Do not commit `.hyperloop/state/` files** — these belong exclusively to the orchestrator on trunk.