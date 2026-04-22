---
id: task-007
title: "UI — Knowledge graph and data source management pages"
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps: [task-001, task-002, task-006]
round: 0
branch: null
pr: null
---

## Summary

Implements the UI pages for managing knowledge graphs and data sources, including the guided creation flow. Depends on `task-001` and `task-002` (management REST APIs) and `task-006` (navigation shell).

## Scope

### Knowledge Graph Management

**List page** (`/data/knowledge-graphs`):
- List KGs within the current workspace (calls `GET /management/workspaces/{id}/knowledge-graphs`)
- Show name, description, data source count
- Create button → inline sheet/modal

**Create flow** (sheet or modal):
- Fields: name, description, workspace selector (defaults to current)
- On success: created KG appears in list; user is prompted to add their first data source

**Detail page** (`/data/knowledge-graphs/{id}`):
- Shows KG metadata (name, description)
- Lists associated data sources with sync status badges
- Inline edit for name/description (no separate edit page — inline action)
- Delete with confirmation dialog

### Data Source Management

**Create flow** (triggered from KG detail or "Add Data Source" prompt):
1. **Adapter type selection**: card grid with available adapters (GitHub first)
2. **Connection configuration**: adapter-specific form fields
   - GitHub: repository URL, access token (PAT)
   - Name field (pre-filled from repo name if detectable)
   - Schedule type selector: Manual / CRON / Interval
3. **On submit**: POST to `/management/knowledge-graphs/{id}/data-sources`; credentials go in request body, never stored in browser state after submission

**Data Source list** (within KG detail):
- Name, adapter type, schedule, last sync status badge
- Quick-trigger sync button (if user has `manage` permission)

**Data Source detail** (`/data/data-sources/{id}`):
- Configuration details (no raw credentials displayed)
- Edit form (inline): name, connection config, credential re-entry
- Delete with confirmation

### Credential Handling

Credentials are typed into form fields, submitted in the API request body, and immediately discarded from client state — never stored in browser storage.

### API Key Integration

The management pages consume the IAM API for workspace context but do not re-implement IAM management (that is in `task-010`).

### API Client Layer

Create a typed API client (using `fetch` or `axios`) for:
- `GET/POST /management/workspaces/{id}/knowledge-graphs`
- `GET/PATCH/DELETE /management/knowledge-graphs/{id}`
- `GET/POST /management/knowledge-graphs/{id}/data-sources`
- `GET/PATCH/DELETE /management/data-sources/{id}`
- `POST /management/data-sources/{id}/sync`

Use Pinia for caching fetched resources; invalidate on mutations.

## TDD Notes

Component tests using Vitest + Vue Test Utils with MSW (Mock Service Worker) for API mocking:
- KG list renders items from API response
- Create form validates name length constraints (1–100 chars)
- Adapter type selection step renders correct form for GitHub
- Credential fields are cleared from component state after form submission
- Delete confirmation dialog: cancel keeps resource; confirm calls DELETE endpoint
