# Knowledge Graph Manage Experience

## Purpose
Define the canonical UX for the Knowledge Graph `Manage` flow in Kartograph, modeled after the proven interaction patterns in k-extract project workspace and design pages.

This spec is the detailed source of truth for KG management UI behavior.

## Scope
In scope:
- `Knowledge Graphs -> Manage` entry flow.
- KG workspace layout, step cards, and progress semantics.
- Graph Management conversation-first interaction model.
- Mode switch behavior and lower-panel content contracts.
- Error/loading/empty/forbidden states and keyboard interactions.

Out of scope:
- Backend domain rules already specified in management/extraction/graph specs.
- Container runtime implementation details.

## Page Contracts
### Page: KG Manage Workspace Overview
Route: `/knowledge-graphs/{kgId}/manage`

Primary intent:
- Provide a project-workspace-style control center for the selected graph.
- Help the user decide the next action with minimal navigation overhead.

Top-level regions:
- Header (graph name/identity, back action)
- `Project workspace` section
- `Suggested next step` callout with one primary CTA
- Step-card grid (`Data Sources`, `Graph Management`, `MutationLogs`, `Maintain`)

### Page: KG Graph Management
Route: `/knowledge-graphs/{kgId}/manage` (same page surface, `Graph Management` active state)

Primary intent:
- Keep conversation as the main control surface.
- Support three operation modes without session fragmentation.

Top-level regions:
- Graph Management mode switcher
- Shared persistent chat box
- Hybrid lower panel:
  - left rail: status/artifacts
  - right detail panel: mode-specific workspace

## Requirements

### Requirement: Manage Entry Navigation
The system SHALL route users from knowledge graph list rows into a graph-scoped manage workspace.

#### Scenario: Manage route entry
- GIVEN the user is on the Knowledge Graphs list
- WHEN the user clicks `Manage` for a knowledge graph
- THEN navigation lands on `/knowledge-graphs/{kgId}/manage`
- AND the page header includes graph identity and a back action
- AND the selected graph context is available to all step cards without re-selection

### Requirement: Workspace Shell and Step Cards
The system SHALL provide a project-workspace-style shell with actionable step cards.

#### Scenario: Step card set
- GIVEN the user opens KG manage workspace
- THEN the step card grid contains exactly:
  - `Data Sources`
  - `Graph Management`
  - `MutationLogs`
  - `Maintain`

#### Scenario: Suggested next step
- GIVEN workspace status and run metadata are available
- WHEN the manage page renders
- THEN a `Suggested next step` callout is shown above the card grid
- AND the callout CTA routes to the corresponding step destination
- AND the CTA label uses action wording (`Open`, `Revisit`, or `Run`)

#### Scenario: Card status semantics
- GIVEN each step has completion/readiness metadata
- WHEN cards render
- THEN each card displays status tint and label (`ready`, `in_progress`, `needs_attention`, or `blocked`)
- AND each card includes one primary action (`Open` or `Revisit`)
- AND each card includes one line of status detail text suitable for quick scanning

### Requirement: Data Sources Step Behavior
The system SHALL preserve the established data-source operations experience while keeping graph context.

#### Scenario: Graph-scoped data source step
- GIVEN the user opens `Data Sources` from KG manage workspace
- THEN the destination is pre-scoped to the selected knowledge graph
- AND existing commit cues, maintenance readiness, and diff summary behaviors remain available
- AND returning to manage workspace preserves the current graph context

### Requirement: Graph Management Conversation-First Layout
The system SHALL use a single persistent chat panel as the primary control surface.

#### Scenario: Persistent shared chat
- GIVEN the user is in Graph Management
- WHEN the user changes modes
- THEN chat history remains in the same session scope
- AND the active mode changes assistant skill framing/instructions rather than opening a new chat
- AND the input placeholder/help text updates to reflect the selected mode

#### Scenario: Top-section controls
- GIVEN the Graph Management page
- THEN the top section includes:
  - mode switcher
  - clear chat action
  - session status indicator
  - validation affordance when relevant to mode
- AND these controls are visible without scrolling on desktop layout

### Requirement: Graph Management Modes
The system SHALL support three operator modes on one page.

#### Scenario: Supported modes
- GIVEN the mode selector in Graph Management
- THEN available modes are:
  - `Initial Schema Design`
  - `Extraction Jobs`
  - `One-off Mutations`

#### Scenario: Mode-specific AI behavior
- GIVEN the user selects a mode
- WHEN the assistant responds or suggests next actions
- THEN the assistant uses mode-appropriate skills and guidance
- AND does not lose shared conversational context
- AND assistant suggestions are constrained to the current knowledge graph scope

### Requirement: Hybrid Lower Panel
The system SHALL provide a hybrid lower panel with shared status/artifact rail and mode-specific detail panel.

#### Scenario: Shared rail
- GIVEN the Graph Management lower panel
- THEN a persistent rail shows graph-management status/artifact items relevant across modes
- AND each item includes status plus last-updated metadata
- AND rail items support keyboard focus and selection

#### Scenario: Mode-specific detail panel
- GIVEN a selected mode and selected rail item
- THEN the right-side detail panel renders mode-specific content:
  - `Initial Schema Design`: schema artifacts, readiness blockers, validation controls
  - `Extraction Jobs`: job setup, execution controls, and job run context
  - `One-off Mutations`: mutation authoring controls and submit/preview context
- AND switching modes preserves rail selection when the selected item is valid in the new mode

#### Scenario: Schema design parity behavior
- GIVEN `Initial Schema Design` mode is active
- THEN the lower panel exposes schema-focused artifact/status content analogous to k-extract design-artifact workflow
- AND the user can inspect and revise schema-related content without leaving Graph Management

### Requirement: MutationLogs Step Experience
The system SHALL provide graph-scoped mutation run visibility.

#### Scenario: Graph-scoped mutation run list
- GIVEN the user opens the `MutationLogs` step
- THEN only runs for the selected knowledge graph are listed
- AND list items show status, timestamp, source, and run identifier
- AND the list defaults to newest run first

#### Scenario: Run detail richness
- GIVEN a selected run
- THEN the detail panel shows run summary, session reference, token/cost metrics, and operation-class counts
- AND supports per-entry operation preview when available
- AND gracefully displays a no-preview state when detailed entries are unavailable

### Requirement: Maintain Step Experience
The system SHALL provide incremental maintenance entry points from the manage workspace.

#### Scenario: Maintenance readiness actioning
- GIVEN tracked source changes are detected
- WHEN the user opens `Maintain`
- THEN the UI highlights change readiness and provides the maintenance execution path
- AND relevant diff summary context is available before execution
- AND the user can navigate back to workspace overview without losing step status context

### Requirement: Session and Reset Behavior
The system SHALL support explicit conversational reset without losing auditability.

#### Scenario: Clear chat reset
- GIVEN an active graph-management chat
- WHEN the user clicks `Clear chat`
- THEN the current chat thread resets
- AND a new clean session starts for the same user/knowledge-graph scope
- AND historical session records remain available for audit/history views
- AND mode selection remains unchanged after reset

### Requirement: State and Accessibility Contracts
The system SHALL provide predictable state handling and keyboard affordances.

#### Scenario: Loading and empty states
- GIVEN initial page load or step data fetch
- THEN each major section shows explicit loading placeholders
- AND empty states provide direct next actions
- AND loading/error state messaging is step-specific (not generic across all steps)

#### Scenario: Forbidden state
- GIVEN the user lacks required permission for a step action
- WHEN the action is attempted
- THEN the UI shows a clear forbidden state/message
- AND avoids partial, misleading updates
- AND disabled actions explain why access is restricted

#### Scenario: Keyboard behavior
- GIVEN the chat input is focused
- THEN `Enter` sends and `Shift+Enter` inserts newline
- AND mode switch/step navigation remains keyboard reachable
- AND primary step-card actions can be triggered by keyboard focus + Enter/Space

## Traceability to UI Surfaces

Primary surfaces expected to implement this UX:
- `src/dev-ui/app/pages/knowledge-graphs/index.vue`
- `src/dev-ui/app/pages/knowledge-graphs/[kgId]/manage.vue`
- `src/dev-ui/app/components/extraction/SharedConversationPanel.vue`

Requirement-to-surface mapping:
- Manage Entry Navigation -> `knowledge-graphs/index.vue`
- Workspace Shell and Step Cards -> `knowledge-graphs/[kgId]/manage.vue`
- Graph Management Conversation-First Layout -> `knowledge-graphs/[kgId]/manage.vue`, `SharedConversationPanel.vue`
- Graph Management Modes -> `knowledge-graphs/[kgId]/manage.vue`
- Hybrid Lower Panel -> `knowledge-graphs/[kgId]/manage.vue`
- MutationLogs Step Experience -> `knowledge-graphs/[kgId]/manage.vue`
- Maintain Step Experience -> `knowledge-graphs/[kgId]/manage.vue` (+ data-source operations surface)
- Session and Reset Behavior -> `knowledge-graphs/[kgId]/manage.vue`, `SharedConversationPanel.vue`
- State and Accessibility Contracts -> `knowledge-graphs/[kgId]/manage.vue`, `SharedConversationPanel.vue`

## Issue Mapping
Detailed implementation tracking for this spec has been externalized to GitHub issues:
- `#722` workspace overview parity
- `#723` graph-management parity (shared chat + mode switch + hybrid panel)
- `#724` mutationlogs step hardening
- `#725` accessibility and state contracts

## Notes for Issue Alignment
- In-place unified operations parity is tracked by GitHub issue `#720`.
- Per-run operation preview depth is tracked by GitHub issue `#721`.
