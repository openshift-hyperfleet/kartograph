---
task_id: task-151
round: 2
role: verifier
verdict: fail
---
## Summary

The task branch `hyperloop/task-151` contains a focused, technically correct fix
(restoring the `__all__` sentinel in the Query Console KG selector) but fails
four process/hygiene checks that must be resolved before it can be merged.

---

## Check Results

| Check | Result |
|-------|--------|
| check-branch-rebased-on-alpha | ✅ PASS |
| check-branch-has-commits | ✅ PASS (8 commits ahead) |
| check-implementation-commits-exist | ✅ PASS |
| check-branch-rebases-cleanly | ✅ PASS |
| check-no-ruff-violations | ✅ PASS |
| check-no-mypy-violations | ✅ PASS |
| check-no-direct-logger-usage | ✅ PASS |
| check-frontend-tests-pass (vitest) | ✅ PASS (2493/2493) |
| check-pages-have-tests | ✅ PASS |
| check-frontend-lockfile-frozen | ✅ PASS |
| check-tautological-frontend-tests | ✅ PASS |
| check-no-api-simulation | ✅ PASS |
| check-all-commits-have-task-ref | ❌ FAIL |
| check-no-foreign-task-commits | ❌ FAIL |
| check-task-owns-branch-commits | ❌ FAIL |
| check-no-test-regressions | ❌ FAIL |

---

## Failures — Actionable Details

### 1. ❌ Broken trailer blocks in two commits

Commits `36bb73721` and `a171b9ba0` have a **blank line** between
`Task-Ref: task-151` and `Co-Authored-By: Claude…`, which prevents git
from parsing them as contiguous trailers. The check `check-all-commits-have-task-ref`
reports these as "BROKEN TRAILER BLOCK".

**Fix:** Interactive rebase to squash the blank line out of each commit:

```bash
git rebase -i $(git merge-base HEAD origin/alpha)
# Mark both offending commits as 'reword' and remove the blank line
# inside the trailer block — trailers must be a single contiguous block.
```

Correct trailer block (no blank lines between lines):

```
Spec-Ref: specs/ui/experience.spec.md@<hash>
Task-Ref: task-151
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

---

### 2. ❌ Foreign task commit on the branch

Commit `cac7a7d6f` carries `Task-Ref: task-146` and is the work from
PR #617. It should not appear on the `hyperloop/task-151` branch. Its
presence caused `check-no-foreign-task-commits` to fail.

**Fix:** Drop it during the interactive rebase above:

```bash
git rebase -i $(git merge-base HEAD origin/alpha)
# Mark cac7a7d6f as 'drop'
```

Note: the task-151 fix (`a171b9ba0`) explicitly reverts what `cac7a7d6f`
introduced, so dropping the foreign commit is safe and correct.

---

### 3. ❌ `check-task-owns-branch-commits` fails as a consequence

This check fails because none of the commits above `origin/alpha` currently
carry a parseable `Task-Ref: task-151` trailer (broken blocks + foreign
commit account for all flagged commits). Fixing items 1 and 2 above will
resolve this check automatically.

---

### 4. ❌ Test regression: `test_mcp_query_tool.py` is 5 net lines shorter than alpha HEAD

`check-no-test-regressions` (pass 2) reports:

```
src/api/tests/unit/query/test_mcp_query_tool.py  (net -5 lines vs alpha HEAD)
```

The diff shows that this branch renamed `TestBuildErrorResponseUnexpectedErrors`
→ `TestBuildErrorResponseUnknownErrors` (and matching method names), which
is a net-neutral rename (same line count). The -5 line gap means `origin/alpha`
added further tests to this file after this branch was cut, and those additions
are absent here.

**Fix:** Rebase onto `origin/alpha` (`329b4a522`) to incorporate those additions,
then verify `uv run pytest tests/unit/query/test_mcp_query_tool.py -v` still passes.

```bash
git fetch origin
git rebase origin/alpha
```

---

## Implementation Quality (informational)

The core code change is correct and well-motivated:

- Replaced `ref('')` sentinel with `ref('__all__')` for the "unscoped" KG
  selector state. Reka UI reserves `value=""` for a cleared selection, making
  the empty-string approach semantically broken.
- All five touch-points updated consistently: ref init, SelectItem value,
  `kgScopeLabel` guard, `executeQuery` ternary, and `Badge` condition.
- 2493/2493 frontend tests pass on the task branch; the fix correctly unblocks
  the 16 tests that were failing with the empty-string sentinel.
- No logger/print usage, no foreign MagicMocks, no stub placeholders.

The work is functionally ready but cannot be landed until the four process
checks above are resolved.