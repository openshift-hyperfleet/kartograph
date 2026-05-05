---
task_id: task-158
round: 0
role: verifier
verdict: fail
---
## Summary

The implementation is **functionally correct** — the production code now emits
`error_type="unknown_error"` as required by the spec, all 2990 unit tests pass,
and linting/type checks are clean. However, the branch fails **five** process
checks. The implementation cannot be merged until all five are resolved.

---

## Check Results

| # | Check | Result |
|---|-------|--------|
| 1 | Unit tests (`uv run pytest tests/unit -v`) | PASS — 2990 passed, 0 failures |
| 2 | Ruff linting | PASS — zero violations |
| 3 | Ruff formatting | PASS — all files formatted |
| 4 | mypy type checking | PASS — zero errors |
| 5 | Architecture boundary tests | PASS — 40 passed |
| 6 | No direct logger/print usage | PASS |
| 7 | `string-constants-match-spec.sh` integrity | FAIL — see Finding 1 |
| 8 | No state-file commits on branch | FAIL — see Finding 2 |
| 9 | All commits have Task-Ref trailer | FAIL — see Finding 3 |
| 10 | Branch owns task-158 commits | FAIL — see Finding 4 |
| 11 | No foreign-task commits | FAIL — see Finding 5 |

---

## Findings

### Finding 1 — New check script missing `--exclude-dir=.venv` (FAIL)

**File:** `.hyperloop/checks/string-constants-match-spec.sh` (introduced on this branch)

The script's `grep` call does not pass `--exclude-dir=.venv`, so it scans the
virtual-environment packages directory. This causes `check-no-check-script-deletions.sh`
to report the script as "damaged" (false positives from venv scanning are
forbidden by check-script policy).

**Fix:** Add `--exclude-dir=.venv` to both `grep -r` calls in the script:

```bash
if ! grep -r --include="*.py" --exclude-dir=.venv -q "\"${constant}\"" "${SRC_DIR}"; then
```

---

### Finding 2 — State files committed on task branch (FAIL)

`check-no-state-file-commits.sh` reports nine `.hyperloop/state/` files were
added by commits on this branch:

```
.hyperloop/state/tasks/task-150.md through task-158.md
```

These are orchestrator-managed metadata and must NOT appear in task-branch
history. They were introduced by the `chore(intake)` and `chore(tasks)` commits,
which are foreign-task (intake) commits piggybacking on this branch.

**Fix:** Strip these commits from the branch history (see Finding 5 — the
foreign commits carrying state files must be dropped entirely).

---

### Finding 3 — Implementation commit missing Task-Ref and Spec-Ref trailers (FAIL)

Commit `5ac4ee831` ("fix(query): align unexpected error type with spec") carries
no `Task-Ref` or `Spec-Ref` trailer. It has a `Co-Authored-By` line but the
trailer block is otherwise empty.

Required trailers:
```
Spec-Ref: specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2
Task-Ref: task-158
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

**Fix:** Amend or rebase to add these trailers to the implementation commit.
Ensure no blank line appears between the trailers and `Co-Authored-By`.

---

### Finding 4 — No commits on the branch carry `Task-Ref: task-158` (FAIL)

`check-task-owns-branch-commits.sh` reports that none of the 11 commits above
`alpha` are tagged for task-158. This is a consequence of Finding 3 (the
implementation commit is untagged).

**Fix:** Resolved by fixing Finding 3.

---

### Finding 5 — Foreign-task commits present on the branch (FAIL)

The branch contains commits belonging to other tasks:

| Commit | Task-Ref | Subject |
|--------|----------|---------|
| `2d6c44e3d` | `intake` | pm intake pass 5 |
| `4eb1ad7fa` | `process-improvement` | guard against spec/implementation string constant drift |
| `42a379115` | `process-improvement` | add alpha-regression classification rules |
| `36d85c4e5` | `process-improvement` | require exact FAIL phrase |
| `329b4a522` | `process-improvement` | rule: copy spec string literals verbatim |
| `457680c9e` | `process-improvement` | fix(query): correct error_type from unknown_error to unexpected_error |

These commits introduce `.hyperloop/state/` files, a new check script
(`string-constants-match-spec.sh`), and process overlay changes — none of which
belong to task-158.

**Fix (recommended):** Cherry-pick only the task-158 implementation commit onto
a fresh branch from `origin/alpha`:

```bash
git checkout -b hyperloop/task-158-clean origin/alpha
git cherry-pick 5ac4ee831   # the implementation commit
# then amend to add Task-Ref: task-158 and Spec-Ref trailers
```

Then verify:
```bash
bash .hyperloop/checks/check-no-state-file-commits.sh
bash .hyperloop/checks/check-no-foreign-task-commits.sh
bash .hyperloop/checks/check-all-commits-have-task-ref.sh
bash .hyperloop/checks/check-task-owns-branch-commits.sh
```

---

## What Is Correct

The one-line production change in `query/application/services.py` is exactly
right: `error_type="unknown_error"` matches the spec. Test assertion values
were updated correctly throughout the three affected test files. No logger or
print usage was introduced. DDD layer boundaries are intact.