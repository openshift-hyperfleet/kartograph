---
id: task-069
title: Data source credential handling — test plaintext not persisted in browser
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: implement
deps: []
round: 0
branch: hyperloop/task-069
pr: null
pr_title: 'test(ui): verify credential plaintext is never persisted in the browser'
pr_description: "## What & Why\n\nThe `experience.spec.md` spec contains a **Requirement:\
  \ Data Source Connection —\nScenario: Credential handling** that includes a browser-side\
  \ guarantee:\n\n> **Scenario: Credential handling**\n> GIVEN credentials provided\
  \ during data source setup\n> WHEN the data source is saved\n> THEN credentials\
  \ are encrypted and stored server-side\n> AND the plaintext is never persisted in\
  \ the browser\n\nThe implementation in `data-sources/index.vue` is correct:\n- `connToken`\
  \ is a Vue `ref('')` (in-memory only — no localStorage write)\n- `resetForm()` clears\
  \ `connToken.value = ''` after the wizard closes\n- The UI shows an amber warning\
  \ panel with the text:\n  _\"Credentials are encrypted server-side using Vault and\
  \ are never stored in\n  plain text. The token will not be retrievable after saving.\"\
  _\n\nHowever, **no test currently asserts any of these browser-side behaviors**.\
  \  The\nexisting test at line 938 of `data-sources.test.ts` only verifies that\n\
  `credentials` is passed to the `createDataSource` call — it does not assert\nnon-persistence.\n\
  \nThis PR closes that gap by adding a dedicated test block that:\n1. Confirms the\
  \ UI warning text is present in the component template.\n2. Confirms `connToken`\
  \ is reset to empty after the wizard form is reset.\n3. Confirms `connToken` is\
  \ never written to `localStorage` or `sessionStorage`.\n\n## Spec Requirements Satisfied\n\
  \n**Requirement: Data Source Connection — Scenario: Credential handling** from\n\
  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\n> THEN\
  \ credentials are encrypted and stored server-side\n> AND the plaintext is never\
  \ persisted in the browser\n\nThe backend encryption guarantee is a server-side\
  \ contract; the UI cannot\nmeaningfully test it in isolation. The browser-side guarantee\
  \ — that plaintext\nis never placed in `localStorage`, `sessionStorage`, or any\
  \ persistent store —\nis exactly what this PR tests.\n\n## Key Design Decisions\n\
  \n- **Template string matching** (static analysis): The simplest way to assert the\n\
  \  warning text is present is to read `data-sources/index.vue` as a string and\n\
  \  assert it contains the exact text. This mirrors the established codebase pattern\n\
  \  (used throughout `mutations-console.test.ts`, `design-language.test.ts`, etc.)\n\
  \  for testing template content.\n- **Behavioral ref clearing test**: Extract `resetForm()`\
  \ logic as a pure\n  function in the test (same `connToken` ref pattern used in\
  \ the existing approval\n  test at line 916), call it, and assert `connToken.value`\
  \ is `''`.\n- **No-localStorage assertion**: Spy on `localStorage.setItem` and\n\
  \  `sessionStorage.setItem` during `approveOntology()`, assert they are never\n\
  \  called with a value that contains the raw token string.\n\n## Files Affected\n\
  \n- `src/dev-ui/app/tests/data-sources.test.ts` — add a new `describe` block\n \
  \ \"Data Source Connection — Credential Handling: plaintext never persisted in browser\"\
  \n\n## How to Verify\n\n1. Run `cd src/dev-ui && pnpm test -- data-sources` — new\
  \ describe block passes.\n2. Run `cd src/dev-ui && pnpm test` — no regressions.\n\
  3. Confirm tests reference the spec scenario in their comments.\n\n## Caveats\n\n\
  - No production code changes. The implementation is already correct.\n- The server-side\
  \ encryption guarantee is not testable from the UI test suite;\n  only the browser-side\
  \ non-persistence is asserted here."
---
