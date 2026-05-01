---
id: task-051
title: Audit MCP integration page — Get Started Querying scenarios and API alignment
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps:
  - task-050
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Get Started Querying (MCP Connection)** — all 3 scenarios from
`specs/ui/experience.spec.md`:

### Scenario: API key creation inline
> GIVEN a user on the MCP integration page who has no active API keys
> WHEN they view the page
> THEN they are prompted to create an API key inline

### Scenario: Copy-paste connection command
> GIVEN an active API key
> WHEN the user views the MCP integration page
> THEN they see a ready-to-paste configuration snippet for their tool (e.g., Claude Code)
> AND the snippet includes the MCP endpoint URL and API key placeholder
> AND a copy button is provided

### Scenario: Secret shown once
> GIVEN a newly created API key
> WHEN the key is created
> THEN the plaintext secret is shown exactly once
> AND the user can copy it
> AND the secret is not retrievable after leaving the page

**Requirement: Backend API Alignment** (applies to inline key creation on this page):

> GIVEN a user performs any create operation via the UI (inline API key creation on the
> MCP page)
> WHEN the operation is submitted
> THEN the corresponding backend API call succeeds (2xx response)
> AND the UI reflects the updated state without requiring a manual refresh

## Gap

`src/dev-ui/app/pages/integrate/mcp.vue` was implemented by task-014 (complete, against
spec commit `85d49a379a`). Task-050 audits Backend API Alignment for IAM pages
(`workspaces`, `groups`, `api-keys`, `tenants`) and Explore pages but explicitly excludes
the MCP integration page. Task-049 touches `integrate/mcp.vue` only for focus-ring CSS
fixes.

No task has verified the three "Get Started Querying" scenarios against the actual
implementation, nor audited whether the inline API key creation on the MCP page calls
the correct backend endpoint with reactive UI refresh.

## Scope

### 1. Verify `pages/integrate/mcp.vue` against all 3 scenarios

Read the component and confirm:

**API key creation inline** (`FAIL` or `PASS` to determine):
- Does the page call `GET /iam/api-keys` (or the equivalent composable) on mount to
  check whether any active keys exist?
- If no active keys are found, is a visible prompt (button, card, or dialog) rendered
  to guide the user through inline creation?
- If keys already exist, is the inline creation prompt hidden?

**Copy-paste connection command** (`FAIL` or `PASS` to determine):
- Does the page render a configuration snippet that includes the MCP server endpoint URL?
- Does the snippet include an API key field (either the actual key value or a placeholder
  that is replaced once a key is selected)?
- Is a copy button (`navigator.clipboard.writeText` or equivalent) provided adjacent to
  the snippet?

**Secret shown once** (`FAIL` or `PASS` to determine):
- After inline key creation, is the plaintext secret displayed in the UI?
- Is it displayed only until the user navigates away or dismisses the created-key panel
  (not persisted in component state after dismissal)?
- Is the copy button provided alongside the one-time secret display?
- Does the component explicitly clear the secret from reactive state when the panel is
  closed or the page is unmounted?

**Backend API Alignment** for inline creation:
- Does inline creation call `POST /iam/api-keys` (not a different or missing endpoint)?
- After creation succeeds, does the key list and/or snippet refresh reactively without a
  full page reload?

### 2. Audit existing tests

Read `src/dev-ui/app/tests/mcp.test.ts` (or the file that covers the MCP page). For
each scenario above, confirm:
- A test exists that exercises the exact GIVEN/WHEN/THEN conditions.
- The test asserts the **exact API endpoint URL** (not just that a fetch was called).
- The test asserts that the secret is cleared from reactive state after dismissal.

### 3. Write missing tests (TDD before any implementation fix)

For each gap found in step 2, write a test in
`src/dev-ui/app/tests/mcp-integration.test.ts` **before** touching implementation:

```typescript
// Example — no active keys → inline prompt rendered
it('prompts to create an API key when no active keys exist', async () => {
  mockFetch.mockResolvedValueOnce([])  // GET /iam/api-keys returns empty
  const wrapper = await mountMcpPage()
  expect(wrapper.find('[data-testid="create-key-prompt"]').exists()).toBe(true)
})

// Example — inline creation calls correct endpoint
it('creates API key via POST /iam/api-keys', async () => {
  await userEvent.click(wrapper.find('[data-testid="create-key-submit"]').element)
  expect(mockFetch).toHaveBeenCalledWith(
    expect.stringContaining('/iam/api-keys'),
    expect.objectContaining({ method: 'POST' })
  )
})

// Example — secret is shown exactly once and cleared on dismiss
it('shows secret once and clears it when panel is dismissed', async () => {
  // After creation, secret is in the DOM
  expect(wrapper.find('[data-testid="api-key-secret"]').text()).toBe('test-secret-value')
  // Dismiss the panel
  await userEvent.click(wrapper.find('[data-testid="dismiss-secret-panel"]').element)
  // Secret is no longer in the DOM
  expect(wrapper.find('[data-testid="api-key-secret"]').exists()).toBe(false)
})

// Example — snippet includes endpoint URL and copy button
it('renders MCP snippet with endpoint URL and copy button', async () => {
  mockFetch.mockResolvedValueOnce([{ id: 'key-1', name: 'My Key', status: 'active' }])
  const wrapper = await mountMcpPage()
  expect(wrapper.find('[data-testid="mcp-snippet"]').text()).toContain(mcpEndpointUrl)
  expect(wrapper.find('[data-testid="copy-snippet-button"]').exists()).toBe(true)
})
```

### 4. Fix implementation gaps

For any scenario that fails:

- **No inline prompt** — add a conditional block that detects an empty key list and
  renders a "Create API Key" call-to-action. Reuse the API key creation dialog from the
  `useIamApi` composable rather than duplicating logic.
- **Wrong or missing endpoint** — update the `apiFetch` call to `POST /iam/api-keys`.
- **Secret not cleared** — ensure the component clears the secret ref on close:
  ```typescript
  function dismissSecret() {
    newKeySecret.value = null  // or ''
    showSecretPanel.value = false
  }
  ```
- **No snippet or missing copy button** — implement the snippet block with the MCP
  endpoint URL and a `navigator.clipboard.writeText` copy handler showing a toast on
  success.

## Acceptance Criteria

- `GET /iam/api-keys` is called on page mount; an inline creation prompt is shown when
  the result is empty.
- The MCP configuration snippet renders with the correct endpoint URL when an active key
  exists; a copy button is adjacent to the snippet.
- After inline API key creation, the plaintext secret is shown exactly once and the
  component's reactive state is cleared when the user dismisses or navigates away.
- The inline creation calls `POST /iam/api-keys` (verified by test assertion on the URL).
- The key list and snippet update reactively after creation — no `window.location.reload()`.
- All tests in `src/dev-ui/app/tests/mcp-integration.test.ts` pass:
  `cd src/dev-ui && pnpm test`
- No regressions in task-049 focus-ring fixes or task-050 API alignment fixes.

## UI Location

- `src/dev-ui/app/pages/integrate/mcp.vue` — MCP integration page

## Dependencies

- **task-050** must be complete: the IAM API alignment audit establishes the correct
  endpoint patterns for `GET /iam/api-keys` and `POST /iam/api-keys`. The MCP page's
  inline creation should use the same composable functions validated by task-050.

## TDD Cycle

1. Read `pages/integrate/mcp.vue` and existing tests — determine PASS/FAIL per scenario.
2. Write failing tests in `tests/mcp-integration.test.ts` for each gap.
3. Fix implementation in `pages/integrate/mcp.vue` to pass tests.
4. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
5. Commit atomically per conventional commit conventions.
