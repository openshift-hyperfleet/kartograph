---
task_id: task-053
round: 4
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — Branch: hyperloop/task-053

### Summary of Previous Failures — Re-verification Results

#### FAIL 1 (RESOLVED): Backend API Alignment — Wrong mutations endpoint
- FIXED: `src/dev-ui/app/composables/api/useGraphApi.ts` line 52 now posts to
  `/graph/knowledge-graphs/${knowledgeGraphId}/mutations` with the KG ID in the path.
- FIXED: `src/dev-ui/app/composables/useMutationSubmission.ts` line 42 `submit()` accepts
  `knowledgeGraphId` and passes it to `applyMutations()`.
- Test coverage: `mutations-console.test.ts` lines 532–544 verify both the parameter presence
  and the correct endpoint path.
- STATUS: PASS

#### FAIL 2 (RESOLVED): Mutations Console — No knowledge graph selector
- FIXED: `src/dev-ui/app/pages/graph/mutations.vue` lines 94–125 implement `selectedKgId`,
  `knowledgeGraphs`, and `loadKnowledgeGraphs()`.
- FIXED: Lines 746–770 render a `<Select>` component with placeholder "Select knowledge graph".
- FIXED: Line 294 guards `handleSubmit()` with `!selectedKgId.value` early return.
- FIXED: Line 777 the Apply Mutations button has `:disabled="... || !selectedKgId"`.
- FIXED: Lines 314 and 332 call `submission.submit(selectedKgId.value, ...)`.
- Test coverage: `mutations-console.test.ts` lines 498–588 cover the KG selector UI, gating,
  and submission scoping scenarios.
- STATUS: PASS

#### FAIL 3 (PARTIALLY RESOLVED): Design Language — font-bold violations
- RESOLVED IN PAGES: Grep of `src/dev-ui/app/pages/**/*.vue` for `font-bold` returns zero
  matches. Page files are now clean.
- REGRESSION GUARD: `mutations-console.test.ts` lines 1039–1083 enforce no `font-bold` in
  any page file.
- REMAINING VIOLATION: `src/dev-ui/app/components/query/QueryResultsPanel.vue` contains
  3 occurrences of `font-bold` at lines 279, 286, and 293 — used for keyboard shortcut
  indicator badges (tiny numbered pills shown when Alt is held).
- Spec states: "font weights limited to regular (400), medium (500), and semibold (600) —
  NO font-bold (700)". No exception is stated for keyboard shortcut indicators.
- The `design-language.test.ts` guards only `Button` and `Badge` components, NOT
  `QueryResultsPanel.vue`. No test covers this violation.
- STATUS: FAIL

### Remaining Failure Details

#### FAIL: Design Language Typography — font-bold in QueryResultsPanel.vue
- File: `src/dev-ui/app/components/query/QueryResultsPanel.vue`
- Lines 279, 286, 293: `font-bold text-primary-foreground` on keyboard shortcut indicator spans
- Spec requirement: "font weights limited to regular (400), medium (500), and semibold (600) — NO font-bold (700)"
- Fix needed: Replace `font-bold` with `font-semibold` on those 3 spans
- Test gap: No test checks `QueryResultsPanel.vue` for font-bold violations

### Other Requirements Verified (PASS)

- Navigation Structure: Mutations Console present in Explore section (layout.vue confirmed, tests in mutations-console.test.ts lines 1014–1032).
- Mutations Console — Empty State: Two primary actions + drag-and-drop + quick-start templates all present.
- Mutations Console — JSONL Editing: CodeMirror with linting, autocomplete, line numbers, Ctrl/Cmd+Enter.
- Mutations Console — Live Preview: parseContent, getBreakdown, MutationPreview component wired.
- Mutations Console — File Upload: .jsonl/.json/.ndjson accepted, large-file mode at 5MB.
- Mutations Console — Submission: floating MutationProgress in app.vue at fixed bottom-right.
- Mutations Console — Submission Failure: error display, truncation, operations_applied count shown.
- Mutations Console — Template Insertion: append behavior, activateEditor() called first.
- Mutations Console — Deep-link: ?view=editor and ?template= handled on mount.
- API Key Management: Covered in separate test files (prior passes).
- Design Language — Component Library: shadcn/vue, CVA, Lucide imports confirmed.
- Design Language — Pages: Zero font-bold violations in all page files.