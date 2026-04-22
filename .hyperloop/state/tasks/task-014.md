---
id: task-014
title: Implement UI — design system, navigation, and IAM management pages
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## What

Bootstrap the Kartograph web UI project and implement the core design system, application shell, navigation, and IAM management pages (workspaces, groups, API keys, MCP connection).

## Spec requirements covered

**Design Language:**
- shadcn/vue (Reka UI) primitives with Tailwind CSS
- Colors as OKLCH CSS custom properties; brand: warm amber/orange
- System font stack; body `text-sm`; section headers `text-[11px]` uppercase `tracking-wider`
- Border radius base `0.625rem`; cards `rounded-xl`, buttons/inputs `rounded-md`, badges `rounded-full`
- Lucide Vue Next icons; CVA for variants
- Dark mode toggle; preference persists across sessions

**Navigation Structure:**
- Sidebar with sections: Explore (Query Console, Schema Browser, Graph Explorer), Data (KGs, Data Sources), Connect (API Keys, MCP Integration), Settings (Workspaces, Groups, Tenants)
- Collapsible sidebar (desktop), sheet overlay (mobile/tablet)
- Tenant selector for multi-tenant users
- Default landing: Query Console for returning users; setup flow prompt for new users

**Tenant & Workspace Context:**
- Tenant selector in sidebar; switching refreshes all data

**Interaction Principles:**
- Toast notifications for write operations
- Inline validation errors on form fields
- Copy-to-clipboard with toast confirmation
- Keyboard shortcuts (Ctrl/Cmd+Enter for execute, `/` for focus search)
- Focus rings: 3px primary-color ring at 50% opacity

**IAM Management Pages:**
- Workspaces: create workspace (name + parent), member management (add/remove/role), list with count
- Groups: create group, member management, list
- API Key Management: create key (name + expiration), list (status, dates), revoke, secret shown once
- MCP Integration: API key creation inline, copy-paste connection snippet, secret shown once

**Responsive Design:** desktop sidebar visible, tablet/mobile collapses to sheet

## Location

New project at `src/ui/` (Vue 3 + Vite + TypeScript). API client generated or hand-written targeting the Kartograph REST API.

## Notes

- No backend dependency — the UI can be built against mock API responses initially.
- Start with the design tokens (colors, typography, radius, elevation) before building components.
- This task creates the shell; tasks 015 and 016 add the data-driven pages.
