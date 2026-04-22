---
id: task-015
title: Implement UI — knowledge graph management, data sources, and sync monitoring
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps: [task-014, task-008, task-009]
round: 0
branch: null
pr: null
---

## What

Implement the Data section of the Kartograph UI: knowledge graph creation/listing, data source connection flow, ontology design wizard, and sync monitoring.

## Spec requirements covered

**Knowledge Graph Creation:**
- Form: name + description, scoped to current workspace
- On create → prompt to add first data source

**Data Source Connection:**
- Adapter type selector (GitHub first)
- Adapter-specific fields (repo URL, access token)
- Infer defaults (data source name from repo name)
- Credentials handled client-side only until submit (never persisted in browser)
- Schedule configuration: MANUAL / CRON (with expression) / INTERVAL (with ISO 8601 duration)

**Ontology Design Flow:**
- After connecting data source: free-text intent description
- Agent-proposed ontology review: approve as-is, or edit individual types
- Type editing: label, description, required/optional properties, relationship types
- Post-extraction ontology change: warn that re-extraction will be triggered, require confirmation

**Sync Monitoring:**
- Per data source: current sync status (ingesting, extracting, applying) with progress indicator
- Sync history: list of runs with status (completed, failed), timestamps, duration
- Sync logs: detailed logs for any run (in-progress or completed)
- Manual sync trigger → new run begins, progress shown

**Interaction Principles (from task-014 design system):**
- Progressive disclosure: summary by default, details on expand/drill-in/sheet
- Inline actions (rename in-place or side panel)
- Mutation feedback: toast on success/failure, inline validation on forms

## Location

`src/ui/src/pages/data/` — knowledge graphs, data sources pages.
`src/ui/src/components/data/` — data source connection wizard, ontology designer, sync monitor.

## Notes

- Depends on task-014 for the design system and application shell.
- Depends on task-008 (Knowledge Graphs API) and task-009 (Data Sources API) for live data.
- The ontology design wizard (agent-proposed ontology) is a multi-step flow; the AI agent integration is aspirational — a placeholder UI is sufficient for this task.
