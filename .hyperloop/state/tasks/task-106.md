---
id: task-106
title: 'Interaction principle completeness: copy-to-clipboard toast, focus rings,
  shortcut discovery'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: verify
deps: []
round: 0
branch: hyperloop/task-106
pr: https://github.com/openshift-hyperfleet/kartograph/pull/571
pr_title: 'feat(ui): implement copy-to-clipboard toast, focus ring design, and shortcut
  tooltips'
pr_description: "## What & Why\n\nThree **Interaction Principles** in `specs/ui/experience.spec.md`\
  \ have not been\nconsistently applied across the UI:\n\n**Copy-to-clipboard toast:**\n\
  > \"GIVEN any identifier, configuration snippet, or secret THEN a copy button is\n\
  > provided AND a toast confirms the copy action\"\n\n**Focus indicators:**\n> \"\
  GIVEN an interactive element receiving focus THEN a 3px ring in the primary\n> color\
  \ at 50% opacity is shown AND native outlines are suppressed in favor of\n> the\
  \ ring\"\n\n**Keyboard shortcuts (discoverable):**\n> \"GIVEN a power-user action\
  \ (execute query, focus search) THEN a keyboard\n> shortcut is available (Ctrl/Cmd+Enter,\
  \ /) AND the shortcut is discoverable\n> via tooltip or documentation\"\n\nThese\
  \ are cross-cutting design system concerns that affect every page. Applying\nthem\
  \ consistently eliminates the need for per-page review of copy/focus behavior.\n\
  \n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md`:\n- **Requirement:\
  \ Interaction Principles** — Scenario: *Copy-to-clipboard*\n- **Requirement: Interaction\
  \ Principles** — Scenario: *Focus indicators*\n- **Requirement: Interaction Principles**\
  \ — Scenario: *Keyboard shortcuts*\n\n## What This Change Does\n\n### 1. Copy-to-Clipboard\
  \ Toast — `useCopyToClipboard` composable\n\nCreate (or update) a `useCopyToClipboard.ts`\
  \ composable that:\n- Copies a string to the clipboard via `navigator.clipboard.writeText`\n\
  - On success: shows a toast: \"Copied to clipboard\" (short duration, ~2s)\n- On\
  \ failure (e.g., non-HTTPS, permission denied): shows an error toast\n- Returns\
  \ a reactive `copied` boolean that resets after 2s (for button icon feedback)\n\n\
  Apply this composable to every place in the UI where identifiers, secrets, or\n\
  configuration snippets can be copied. Audit at minimum:\n- API key secret display\
  \ (`/api-keys/index.vue`, `/integrate/mcp.vue`)\n- Knowledge graph ID (wherever\
  \ shown)\n- MCP configuration snippet (`/integrate/mcp.vue`)\n- Any `<code>` blocks\
  \ showing endpoint URLs or tokens\n\n### 2. Focus Ring Design Token\n\nAdd a global\
  \ CSS rule to suppress native browser outlines and apply the spec-\ncompliant focus\
  \ ring:\n\n```css\n/* In global stylesheet or Tailwind base layer */\n*:focus-visible\
  \ {\n  outline: none;\n  box-shadow: 0 0 0 3px oklch(0.5768 0.2469 29.23 / 50%);\n\
  }\n```\n\nThis uses the spec's primary brand color at 50% opacity. Verify the rule\
  \ is\napplied to:\n- Buttons (all variants)\n- Inputs, textareas, selects\n- Links\n\
  - Checkboxes and radio buttons\n- Any custom interactive component (e.g., comboboxes,\
  \ dropdowns)\n\nIf `shadcn/vue` components suppress outlines internally, override\
  \ within the\ncomponent's CSS or via Tailwind `focus-visible:ring-*` utilities.\n\
  \n### 3. Keyboard Shortcut Tooltips\n\nFor every interactive element with a keyboard\
  \ shortcut, add the shortcut hint\nto the element's tooltip. Use the existing `Tooltip`\
  \ component (shadcn/vue).\n\nElements requiring shortcut tooltips (audit and apply):\n\
  - Query Console \"Run\" button → `Ctrl/Cmd+Enter`\n- Mutations Console \"Apply Mutations\"\
  \ button → `Ctrl/Cmd+Enter`\n- Sidebar search or global search (if implemented)\
  \ → `/`\n- Any other action with a documented shortcut\n\nTooltip text format: `\"\
  Run query (⌘↵)\"` on macOS, `\"Run query (Ctrl+Enter)\"` on\nother platforms. Use\
  \ `navigator.platform` or a `useIsMac` composable to\nconditionally show the correct\
  \ modifier symbol.\n\n## Files / Areas Affected\n\n- `src/dev-ui/app/composables/useCopyToClipboard.ts`\
  \ (new or update)\n- `src/dev-ui/app/assets/css/` or `src/dev-ui/app/app.vue` —\
  \ global focus ring CSS\n- `src/dev-ui/app/pages/integrate/mcp.vue` — apply copy\
  \ composable to MCP snippet\n- `src/dev-ui/app/pages/api-keys/index.vue` — apply\
  \ copy composable to key secret display\n- `src/dev-ui/app/pages/query/index.vue`\
  \ — add tooltip with shortcut hint to Run button\n- `src/dev-ui/app/pages/graph/mutations.vue`\
  \ — add tooltip to Apply Mutations button\n- Other pages with copy buttons: audit\
  \ and update as needed\n\n## Tests\n\nVitest / Vue Test Utils tests in `src/dev-ui/app/tests/`:\n\
  - `test_copy_composable_shows_success_toast`: mock clipboard API, invoke\n  `useCopyToClipboard`,\
  \ assert toast is shown with \"Copied to clipboard\"\n- `test_copy_composable_shows_error_toast`:\
  \ mock clipboard failure, assert error\n  toast is shown\n- `test_copy_button_on_mcp_page_triggers_copy`:\
  \ mount MCP integration page,\n  click copy button for snippet, assert `navigator.clipboard.writeText`\
  \ was called\n- `test_run_button_tooltip_shows_shortcut`: mount query console, assert\
  \ the Run\n  button's tooltip text includes the keyboard shortcut\n\n## How to Verify\n\
  \n1. Navigate to `/api-keys` — create a key, copy the secret, confirm toast appears\n\
  2. Navigate to `/integrate/mcp` — copy the MCP snippet, confirm toast appears\n\
  3. Tab through interactive elements on any page — confirm all receive a visible\n\
  \   amber ring on focus (3px, 50% opacity)\n4. Hover the query console \"Run\" button\
  \ — confirm tooltip shows `⌘↵` or `Ctrl+Enter`\n5. Hover the mutations \"Apply Mutations\"\
  \ button — confirm same shortcut tooltip\n\n## Caveats\n\n- `navigator.clipboard.writeText`\
  \ requires a secure context (HTTPS or localhost).\n  In the dev environment (localhost),\
  \ it works; in production it requires TLS.\n  The error toast fallback handles non-secure\
  \ contexts gracefully.\n- The focus ring rule uses `:focus-visible` (not `:focus`)\
  \ to avoid showing rings\n  when clicking with a mouse. Verify that keyboard navigation\
  \ still works correctly.\n- The spec's exact color value `oklch(0.5768 0.2469 29.23\
  \ / 50%)` may appear\n  lighter on dark mode backgrounds. Verify contrast in both\
  \ light and dark modes.\n- Do not remove existing focus handling from shadcn/vue\
  \ components — layer on top\n  of or replace with `:focus-visible` only."
---
