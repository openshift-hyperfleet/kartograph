---
id: task-106
title: "Interaction principle completeness: copy-to-clipboard toast, focus rings, shortcut discovery"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(ui): implement copy-to-clipboard toast, focus ring design, and shortcut tooltips"
pr_description: |
  ## What & Why

  Three **Interaction Principles** in `specs/ui/experience.spec.md` have not been
  consistently applied across the UI:

  **Copy-to-clipboard toast:**
  > "GIVEN any identifier, configuration snippet, or secret THEN a copy button is
  > provided AND a toast confirms the copy action"

  **Focus indicators:**
  > "GIVEN an interactive element receiving focus THEN a 3px ring in the primary
  > color at 50% opacity is shown AND native outlines are suppressed in favor of
  > the ring"

  **Keyboard shortcuts (discoverable):**
  > "GIVEN a power-user action (execute query, focus search) THEN a keyboard
  > shortcut is available (Ctrl/Cmd+Enter, /) AND the shortcut is discoverable
  > via tooltip or documentation"

  These are cross-cutting design system concerns that affect every page. Applying
  them consistently eliminates the need for per-page review of copy/focus behavior.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md`:
  - **Requirement: Interaction Principles** — Scenario: *Copy-to-clipboard*
  - **Requirement: Interaction Principles** — Scenario: *Focus indicators*
  - **Requirement: Interaction Principles** — Scenario: *Keyboard shortcuts*

  ## What This Change Does

  ### 1. Copy-to-Clipboard Toast — `useCopyToClipboard` composable

  Create (or update) a `useCopyToClipboard.ts` composable that:
  - Copies a string to the clipboard via `navigator.clipboard.writeText`
  - On success: shows a toast: "Copied to clipboard" (short duration, ~2s)
  - On failure (e.g., non-HTTPS, permission denied): shows an error toast
  - Returns a reactive `copied` boolean that resets after 2s (for button icon feedback)

  Apply this composable to every place in the UI where identifiers, secrets, or
  configuration snippets can be copied. Audit at minimum:
  - API key secret display (`/api-keys/index.vue`, `/integrate/mcp.vue`)
  - Knowledge graph ID (wherever shown)
  - MCP configuration snippet (`/integrate/mcp.vue`)
  - Any `<code>` blocks showing endpoint URLs or tokens

  ### 2. Focus Ring Design Token

  Add a global CSS rule to suppress native browser outlines and apply the spec-
  compliant focus ring:

  ```css
  /* In global stylesheet or Tailwind base layer */
  *:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px oklch(0.5768 0.2469 29.23 / 50%);
  }
  ```

  This uses the spec's primary brand color at 50% opacity. Verify the rule is
  applied to:
  - Buttons (all variants)
  - Inputs, textareas, selects
  - Links
  - Checkboxes and radio buttons
  - Any custom interactive component (e.g., comboboxes, dropdowns)

  If `shadcn/vue` components suppress outlines internally, override within the
  component's CSS or via Tailwind `focus-visible:ring-*` utilities.

  ### 3. Keyboard Shortcut Tooltips

  For every interactive element with a keyboard shortcut, add the shortcut hint
  to the element's tooltip. Use the existing `Tooltip` component (shadcn/vue).

  Elements requiring shortcut tooltips (audit and apply):
  - Query Console "Run" button → `Ctrl/Cmd+Enter`
  - Mutations Console "Apply Mutations" button → `Ctrl/Cmd+Enter`
  - Sidebar search or global search (if implemented) → `/`
  - Any other action with a documented shortcut

  Tooltip text format: `"Run query (⌘↵)"` on macOS, `"Run query (Ctrl+Enter)"` on
  other platforms. Use `navigator.platform` or a `useIsMac` composable to
  conditionally show the correct modifier symbol.

  ## Files / Areas Affected

  - `src/dev-ui/app/composables/useCopyToClipboard.ts` (new or update)
  - `src/dev-ui/app/assets/css/` or `src/dev-ui/app/app.vue` — global focus ring CSS
  - `src/dev-ui/app/pages/integrate/mcp.vue` — apply copy composable to MCP snippet
  - `src/dev-ui/app/pages/api-keys/index.vue` — apply copy composable to key secret display
  - `src/dev-ui/app/pages/query/index.vue` — add tooltip with shortcut hint to Run button
  - `src/dev-ui/app/pages/graph/mutations.vue` — add tooltip to Apply Mutations button
  - Other pages with copy buttons: audit and update as needed

  ## Tests

  Vitest / Vue Test Utils tests in `src/dev-ui/app/tests/`:
  - `test_copy_composable_shows_success_toast`: mock clipboard API, invoke
    `useCopyToClipboard`, assert toast is shown with "Copied to clipboard"
  - `test_copy_composable_shows_error_toast`: mock clipboard failure, assert error
    toast is shown
  - `test_copy_button_on_mcp_page_triggers_copy`: mount MCP integration page,
    click copy button for snippet, assert `navigator.clipboard.writeText` was called
  - `test_run_button_tooltip_shows_shortcut`: mount query console, assert the Run
    button's tooltip text includes the keyboard shortcut

  ## How to Verify

  1. Navigate to `/api-keys` — create a key, copy the secret, confirm toast appears
  2. Navigate to `/integrate/mcp` — copy the MCP snippet, confirm toast appears
  3. Tab through interactive elements on any page — confirm all receive a visible
     amber ring on focus (3px, 50% opacity)
  4. Hover the query console "Run" button — confirm tooltip shows `⌘↵` or `Ctrl+Enter`
  5. Hover the mutations "Apply Mutations" button — confirm same shortcut tooltip

  ## Caveats

  - `navigator.clipboard.writeText` requires a secure context (HTTPS or localhost).
    In the dev environment (localhost), it works; in production it requires TLS.
    The error toast fallback handles non-secure contexts gracefully.
  - The focus ring rule uses `:focus-visible` (not `:focus`) to avoid showing rings
    when clicking with a mouse. Verify that keyboard navigation still works correctly.
  - The spec's exact color value `oklch(0.5768 0.2469 29.23 / 50%)` may appear
    lighter on dark mode backgrounds. Verify contrast in both light and dark modes.
  - Do not remove existing focus handling from shadcn/vue components — layer on top
    of or replace with `:focus-visible` only.
---
