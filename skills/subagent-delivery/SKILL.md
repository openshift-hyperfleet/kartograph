---
name: subagent-delivery
description: >
  Executes a GitHub issue end-to-end with consistent branch, test, PR, and merge behavior.
  Use when implementing units of work with sub-agents, preparing pull requests, resolving merge
  conflicts, or when the user asks to run issue-by-issue delivery into feature/manage-knowledge-graph.
---

# Subagent Delivery Protocol

Follow this protocol for every assigned issue.

## Scope and Inputs

Before coding, gather:

1. Issue number and acceptance criteria.
2. Target branch: `feature/manage-knowledge-graph`.
3. Current repository state (`git status`, `git branch -vv`).

If acceptance criteria are ambiguous, ask one focused question before implementation.

## Git Workflow

1. Ensure local target branch is up to date:
   - `git checkout feature/manage-knowledge-graph`
   - `git pull --ff-only`
2. Create a dedicated branch per issue:
   - `feat/issue-<id>-<short-scope>` for features
   - `fix/issue-<id>-<short-scope>` for fixes
3. Never mix multiple issues in one branch.
4. Keep commits atomic and conventional (`feat:`, `fix:`, `refactor:`, `test:`).

## Implementation Workflow (TDD Required)

1. Read relevant spec(s) and affected bounded context code first.
2. Write/adjust tests for expected behavior before implementation.
3. Implement minimal code to satisfy tests.
4. Run focused tests first, then broader suite for touched context.
5. Run lints/type checks for changed files when applicable.
6. If behavior depends on configuration, use settings/DI instead of hardcoding.

## PR Workflow

1. Push branch to origin with upstream tracking.
2. Open PR against `feature/manage-knowledge-graph`.
3. Use this body structure:

```markdown
## Summary
- <what changed and why>
- <important architectural/security note>

## Testing
- [x] <unit tests run>
- [x] <integration tests run if applicable>
- [ ] <manual verification if pending>

## Risks
- <none> or <known risk + mitigation>
```

4. Link the issue in PR body using `Closes #<id>` when appropriate.

## Merge and Conflict Handling

1. Before merge, ensure CI checks are green.
2. If branch is stale, rebase or merge target branch cleanly.
3. Resolve conflicts preserving:
   - Spec-required behavior
   - Existing user changes
   - Authorization and tenancy boundaries
4. Re-run tests after conflict resolution.
5. Merge into `feature/manage-knowledge-graph` only after verification.

## Non-Negotiables

- Do not use destructive git commands.
- Do not skip tests.
- Do not disable hooks.
- Do not commit secrets or credentials.
- Prefer fakes over mocks in unit tests when testing domain/application behavior.

