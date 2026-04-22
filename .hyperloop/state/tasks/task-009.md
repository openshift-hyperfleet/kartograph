---
id: task-009
title: "UI — Sync monitoring and ontology design"
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps: [task-005, task-007]
round: 0
branch: null
pr: null
---

## Summary

Implements sync monitoring (live status, history, logs) and the agent-assisted ontology design flow. Depends on `task-005` (sync lifecycle state machine backend) and `task-007` (data source management pages that host these features).

## Scope

### Sync Monitoring (within Data Source detail page)

**Active sync indicator**:
- Poll or WebSocket-subscribe to sync run status
- Show current phase badge: `pending` → `ingesting` → `ai_extracting` → `applying` → `completed` / `failed`
- Phase-appropriate progress indicator (spinner, step indicator)

**Sync history table**:
- List of past sync runs for this data source
- Columns: status badge, started_at, duration (completed_at − started_at), error (if failed)
- Calls `GET /management/data-sources/{id}/sync-runs` (if endpoint exists; add to task-002 if missing)

**Sync logs panel** (expand per run):
- Display structured log output for a sync run
- Calls a logs endpoint or renders the error message field for failed runs

**Manual sync trigger**:
- "Sync Now" button (visible to users with `manage` permission)
- Calls `POST /management/data-sources/{id}/sync`
- Disables button while sync is in progress
- Shows toast on trigger success; status badge updates automatically

### Ontology Design Flow

Triggered after connecting a new data source (step following the creation flow in `task-007`).

**Step 1 — Intent description**:
- Free-text textarea: "What problems or questions do you want to solve with this data?"
- Submit button → initiates lightweight scan of data source + AI ontology proposal

**Step 2 — Proposed ontology review**:
- Display AI-proposed node types and edge types as editable cards
- Each card shows: label, description, required properties (chips), optional properties (chips)

**Step 3 — Individual type editing** (slide-out or inline):
- Edit: label, description
- Add/remove required properties (name + type)
- Add/remove optional properties
- Add/remove relationship types

**Step 4 — Approval**:
- "Approve Ontology" → triggers extraction (published as event)
- Warning dialog if user modifies an already-extracted ontology: "This will trigger a full re-extraction. Confirm?"

**API integration**:
- Ontology proposal: POST to an AI orchestration endpoint (stub if backend not yet implemented; show placeholder UI)
- Approve: calls the relevant mutation endpoint or emits via the management API

## TDD Notes

Component tests using Vitest + Vue Test Utils with MSW:
- Sync status badge updates when API returns new status
- "Sync Now" button is disabled when status is `ingesting`; enabled when `completed` or `failed`
- History table renders run rows with correct duration calculation
- Ontology intent form: submit disabled when textarea is empty
- Ontology review: add/remove property chip updates the type card
- Re-extraction warning dialog: cancel does not call approval endpoint
