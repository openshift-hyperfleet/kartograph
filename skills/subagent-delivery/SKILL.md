---
name: subagent-delivery
description: >
  Executes a GitHub issue end-to-end with consistent branch, test, PR, and merge behavior.
  Use when implementing units of work with sub-agents, preparing pull requests, resolving merge
  conflicts, or when the user asks to run issue-by-issue delivery into feature/manage-knowledge-graph.
  Supports parallel delivery waves with explicit blocker-question escalation.
---

# Subagent Delivery Protocol

Follow this protocol for every assigned issue.

## Parallel Execution Model

Use this model whenever multiple issues are independent:

1. One subagent per issue branch.
2. Shared target branch: `feature/manage-knowledge-graph`.
3. No shared working branch between agents.
4. Each subagent works to PR-ready state independently.
5. Merge in dependency order (foundational backend before UI polish when coupled).

If two issues touch the same files heavily, either:
- serialize those two issues, or
- split scope so each agent owns non-overlapping symbols.

## Scope and Inputs

Before coding, gather:

1. Issue number and acceptance criteria.
2. Target branch: `feature/manage-knowledge-graph`.
3. Current repository state (`git status`, `git branch -vv`).
4. Context pack (required):
   - relevant specs under `specs/`
   - bounded context ownership (management/ingestion/extraction/graph/querying/ui)
   - existing tests near touched code
   - architectural constraints from `AGENTS.md`

If acceptance criteria are ambiguous, ask one focused question before implementation.

## Blocker Question Protocol (Required)

Subagents must be able to stop and ask questions immediately.

Trigger a blocker question when any of these is true:

1. More than one valid interpretation of acceptance criteria.
2. Missing security/tenancy/authorization decision.
3. Required external behavior is unspecified.
4. You would otherwise make an irreversible guess.

When blocked:

1. Stop implementation at the decision boundary.
2. Ask one concise question in the active agent chat immediately.
3. Include:
   - what is ambiguous
   - 2-3 concrete options
   - recommended option and why
4. If working from a GitHub issue, mirror the same question as an issue comment so the orchestrator can batch unresolved questions across agents.
5. Continue only non-blocked work; do not guess on blocked decisions.

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
7. If new ambiguity appears mid-implementation, invoke the Blocker Question Protocol.

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
5. If any assumptions were made, include an explicit assumptions list in PR body.

## Merge and Conflict Handling

1. Before merge, ensure CI checks are green.
2. If branch is stale, rebase or merge target branch cleanly.
3. Resolve conflicts preserving:
   - Spec-required behavior
   - Existing user changes
   - Authorization and tenancy boundaries
4. Re-run tests after conflict resolution.
5. Merge into `feature/manage-knowledge-graph` only after verification.

## Orchestrator Handoff Contract

Each subagent must hand back:

1. Branch name and PR URL.
2. Test commands run with pass/fail status.
3. Any unresolved questions (if still blocked).
4. Any assumptions that were taken and why they are safe.

## Non-Negotiables

- Do not use destructive git commands.
- Do not skip tests.
- Do not disable hooks.
- Do not commit secrets or credentials.
- Prefer fakes over mocks in unit tests when testing domain/application behavior.

