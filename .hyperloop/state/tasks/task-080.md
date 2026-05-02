---
id: task-080
title: UI component library — add AlertDialog (shadcn/vue)
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: merge
deps: []
round: 1
branch: hyperloop/task-080
pr: https://github.com/openshift-hyperfleet/kartograph/pull/544
pr_title: 'feat(ui): add AlertDialog shadcn/vue component'
pr_description: "## What & Why\n\n`task-079` (Knowledge Graphs UI — add inline edit\
  \ and delete) requires an\n`AlertDialog` component for the KG delete confirmation,\
  \ but this component\ndoes not exist in the UI component library. The component\
  \ library currently\nincludes `alert` (notification banner) but **not** `alert-dialog`\
  \ (modal\nconfirmation dialog with destructive action).\n\nThe shadcn/vue `AlertDialog`\
  \ is the standard primitive for destructive\nconfirmation flows — it is semantically\
  \ distinct from `Dialog` in that it\ncommunicates to users that they are about to\
  \ perform an irreversible action.\nIt is used throughout the spec:\n\n- **task-079**:\
  \ KG delete-with-confirmation dialog\n- Potentially future tasks requiring destructive\
  \ action confirmation gates\n\nThis PR adds the full shadcn/vue `AlertDialog` component\
  \ set, following the\nidentical pattern used by every other component in\n`src/dev-ui/app/components/ui/`:\n\
  \n- `AlertDialog.vue` — root composable wrapper\n- `AlertDialogTrigger.vue`\n- `AlertDialogPortal.vue`\n\
  - `AlertDialogOverlay.vue`\n- `AlertDialogContent.vue` — styled content container\
  \ with ring focus\n- `AlertDialogHeader.vue`\n- `AlertDialogFooter.vue`\n- `AlertDialogTitle.vue`\n\
  - `AlertDialogDescription.vue`\n- `AlertDialogAction.vue` — primary (potentially\
  \ destructive) button\n- `AlertDialogCancel.vue` — cancel button\n- `index.ts` —\
  \ barrel re-export\n\n## Spec Requirements Satisfied\n\n**Requirement: Backend API\
  \ Alignment — Scenario: Resource operations succeed\nend-to-end** from `specs/ui/experience.spec.md`:\n\
  \n> GIVEN a user performs any create, read, update, or **delete** operation via\
  \ the UI\n> THEN the corresponding backend API call succeeds (2xx response)\n\n\
  The `AlertDialog` component is the correct UI primitive for the delete\nconfirmation\
  \ flow added by `task-079`. Without it, `task-079` cannot be\nimplemented as specified.\n\
  \n## Key Design Decisions\n\n- **Reka UI / shadcn/vue primitives**: `AlertDialogContent`\
  \ is built on\n  Reka's `DialogContent` (same as the existing `Dialog` component),\
  \ so it\n  inherits the focus-trap and ARIA attributes automatically.\n- **Design\
  \ language compliance**: Uses `rounded-md` for buttons, `rounded-xl`\n  for the\
  \ content panel, `shadow-sm` elevation, and the `ring-[3px]` focus ring\n  — matching\
  \ the spec's Design Language requirement exactly.\n- **Destructive action styling**:\
  \ `AlertDialogAction` accepts a `class` prop so\n  callers can apply `bg-destructive\
  \ text-destructive-foreground` (as task-079\n  requires) without hard-coding it\
  \ in the component.\n- **Follows established pattern exactly**: All file names,\
  \ export names, and\n  `index.ts` barrel patterns mirror the existing `dialog/`\
  \ component set.\n\n## Files Affected\n\n```\nsrc/dev-ui/app/components/ui/alert-dialog/\n\
  \  AlertDialog.vue\n  AlertDialogTrigger.vue\n  AlertDialogPortal.vue\n  AlertDialogOverlay.vue\n\
  \  AlertDialogContent.vue\n  AlertDialogHeader.vue\n  AlertDialogFooter.vue\n  AlertDialogTitle.vue\n\
  \  AlertDialogDescription.vue\n  AlertDialogAction.vue\n  AlertDialogCancel.vue\n\
  \  index.ts\nsrc/dev-ui/app/tests/alert-dialog.test.ts  (structural tests)\n```\n\
  \n## How to Verify\n\n1. `cd src/dev-ui && npm run test` — all tests pass (including\
  \ the new\n   structural test that verifies `index.ts` exports all named components).\n\
  2. Import and use `AlertDialog` from `@/components/ui/alert-dialog` in any\n   page\
  \ — no runtime errors.\n3. Confirm `task-079` can now import `AlertDialogContent`,\
  \ `AlertDialogAction`,\n   etc. without compilation errors.\n\n## TDD Cycle\n\n\
  1. Write structural tests verifying `index.ts` exports all expected names — RED.\n\
  2. Create all component files following the shadcn/vue pattern — GREEN.\n3. Run\
  \ `cd src/dev-ui && npm run test` — all pass.\n4. Commit atomically, referencing\
  \ this task.\n\n## Caveats / Follow-up\n\n- This task has no runtime behaviour of\
  \ its own — it is pure UI infrastructure.\n- `task-079` lists `task-080` as a dependency;\
  \ it must be merged first."
---
