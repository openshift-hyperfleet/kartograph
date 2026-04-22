---
id: task-006
title: "UI — Design system, layout and navigation shell"
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Summary

This task establishes the foundational UI layer: the design system, application shell, and navigation structure. All other UI tasks build on this foundation.

## Scope

### Tech Stack

- Vue 3 + TypeScript (Composition API)
- shadcn/vue (Reka UI) as the component library
- Tailwind CSS v4 for styling
- Class Variance Authority (CVA) for component variants
- Lucide Vue Next for icons
- Vite as the bundler

### Design Language

Implement the Kartograph design system:

**Colors** (OKLCH CSS custom properties):
- Primary/brand: warm amber/orange — `oklch(0.5768 0.2469 29.23)` (light), `oklch(0.6857 0.1560 17.57)` (dark)
- Neutral gray palette for backgrounds, cards, borders
- Destructive: coral/red accent
- Data visualization: 5-color palette (amber, blue, purple, yellow, green)

**Typography**:
- System font stack (no custom fonts)
- Body: `text-sm` (0.875rem)
- Section headers: uppercase `text-[11px]` with `tracking-wider`
- Font weights: 400, 500, 600 only

**Border radius**:
- Base: `0.625rem` (10px)
- Cards: `rounded-xl`; buttons/inputs: `rounded-md`; badges: `rounded-full`

**Elevation**: `shadow-sm` (cards), `shadow-xs` (buttons); predominantly flat

**Focus indicators**: 3px ring in primary color at 50% opacity

### Application Shell

Implement the main layout with:
- **Collapsible sidebar** (visible on desktop, sheet overlay on mobile/tablet)
- **Sidebar navigation groups**:
  - **Explore**: Query Console, Schema Browser, Graph Explorer
  - **Data**: Knowledge Graphs, Data Sources
  - **Connect**: API Keys, MCP Integration
  - **Settings**: Workspaces, Groups, Tenants
- **Tenant selector** in the sidebar (for multi-tenant users)
- **Dark mode toggle** in the header (preference persisted in localStorage)
- Responsive: sidebar collapses to sheet on narrow screens

### Interaction Principles

Implement as reusable composables/components:
- Toast notification system (success/failure feedback for mutations)
- Copy-to-clipboard with toast confirmation
- Progressive disclosure pattern (expand/drill-in/sheet)
- Keyboard shortcuts infrastructure (Ctrl/Cmd+Enter for query execution, `/` for search focus)

### Auth & Routing

- Vue Router setup with route guards
- Auth state management (Pinia store): current user, current tenant
- Landing page logic: redirect returning users to Explore, new users to setup flow

### New User Setup Prompt

When a user has no knowledge graphs, display a prompt in the main content area: "Create your first knowledge graph to get started" with a call-to-action button.

## TDD Notes

This is a frontend task. Write component tests using Vitest + Vue Test Utils:
- Sidebar renders all navigation groups
- Tenant selector switches active tenant
- Dark mode toggle persists preference
- Toast system: show/dismiss notifications
- Copy button: triggers clipboard write and shows toast
