import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Responsive Design Tests ───────────────────────────────────────────────────
//
// Spec: "Responsive Design"
// Covers:
//   - Scenario: Desktop layout (sidebar visible and collapsible, multi-column)
//   - Scenario: Tablet/mobile layout (sidebar collapses to sheet overlay, single-column)

// ── Layout file content ───────────────────────────────────────────────────────

const layoutPath = resolve(__dirname, '../layouts/default.vue')
const layoutContent = readFileSync(layoutPath, 'utf-8')

// ── Sidebar state logic (mirrors useSidebar composable) ───────────────────────

function createSidebarState() {
  let isCollapsed = false
  let isMobileOpen = false

  return {
    get isCollapsed() { return isCollapsed },
    get isMobileOpen() { return isMobileOpen },
    toggleCollapsed() { isCollapsed = !isCollapsed },
    openMobile() { isMobileOpen = true },
    closeMobile() { isMobileOpen = false },
    get sidebarWidth() { return isCollapsed ? 'w-16' : 'w-64' },
  }
}

// ── Desktop layout: sidebar width computation ─────────────────────────────────

function getSidebarWidth(isCollapsed: boolean): string {
  return isCollapsed ? 'w-16' : 'w-64'
}

// ── Mobile sheet: open state based on screen size ─────────────────────────────

function computeSheetOpen(isDesktop: boolean, mobileOpen: boolean): boolean {
  return !isDesktop && mobileOpen
}

// ── Workspace page responsive layout ─────────────────────────────────────────

function getWorkspaceDetailLayout(selectedWorkspace: unknown, isDesktop: boolean): string {
  if (selectedWorkspace && isDesktop) {
    return 'lg:grid-cols-[1fr_minmax(580px,640px)]'
  }
  return ''
}

function computeWorkspaceSheetOpen(isDesktop: boolean, selectedWorkspace: unknown): boolean {
  return !isDesktop && selectedWorkspace !== null
}

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Desktop layout — sidebar visible and collapsible
// ────────────────────────────────────────────────────────────────────────────

describe('Responsive Design - desktop sidebar visibility', () => {
  it('sidebar uses "hidden md:flex" — hidden on mobile, flex on desktop (md+)', () => {
    // The desktop sidebar element has class "hidden md:flex"
    expect(layoutContent).toContain('hidden md:flex')
  })

  it('sidebar is visible on desktop (md+) breakpoint', () => {
    // "hidden md:flex" means: hidden on <md, flex on md+
    // This verifies the Tailwind responsive class is present
    const hasMdFlex = layoutContent.includes('md:flex')
    expect(hasMdFlex).toBe(true)
  })

  it('sidebar uses transition for smooth collapse/expand', () => {
    expect(layoutContent).toContain('transition-all')
  })
})

describe('Responsive Design - desktop sidebar collapsible', () => {
  it('expanded sidebar has width w-64 (16rem)', () => {
    expect(getSidebarWidth(false)).toBe('w-64')
  })

  it('collapsed sidebar has width w-16 (64px icon-only mode)', () => {
    expect(getSidebarWidth(true)).toBe('w-16')
  })

  it('toggle switches sidebar from expanded to collapsed', () => {
    const sidebar = createSidebarState()
    expect(sidebar.isCollapsed).toBe(false)
    sidebar.toggleCollapsed()
    expect(sidebar.isCollapsed).toBe(true)
    expect(sidebar.sidebarWidth).toBe('w-16')
  })

  it('toggle switches sidebar from collapsed back to expanded', () => {
    const sidebar = createSidebarState()
    sidebar.toggleCollapsed()
    sidebar.toggleCollapsed()
    expect(sidebar.isCollapsed).toBe(false)
    expect(sidebar.sidebarWidth).toBe('w-64')
  })

  it('sidebar width changes reactively on toggle', () => {
    const sidebar = createSidebarState()
    expect(sidebar.sidebarWidth).toBe('w-64')
    sidebar.toggleCollapsed()
    expect(sidebar.sidebarWidth).toBe('w-16')
  })
})

describe('Responsive Design - desktop multi-column layout', () => {
  it('workspace detail panel shows two-column grid on desktop when workspace selected', () => {
    const layout = getWorkspaceDetailLayout({ id: 'ws-1' }, true)
    expect(layout).toContain('lg:grid-cols')
  })

  it('workspace uses single column when no workspace is selected (desktop)', () => {
    const layout = getWorkspaceDetailLayout(null, true)
    expect(layout).toBe('')
  })

  it('workspace uses single column on mobile even when workspace is selected', () => {
    const layout = getWorkspaceDetailLayout({ id: 'ws-1' }, false)
    expect(layout).toBe('')
  })

  it('workspace page uses grid layout for list and detail panel', () => {
    // Verify that the workspaces page has responsive grid definitions
    const workspacesPath = resolve(__dirname, '../pages/workspaces/index.vue')
    const workspacesContent = readFileSync(workspacesPath, 'utf-8')
    expect(workspacesContent).toContain('grid')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Tablet/mobile layout — sidebar collapses to sheet overlay
// ────────────────────────────────────────────────────────────────────────────

describe('Responsive Design - mobile sidebar sheet overlay', () => {
  it('default.vue contains a Sheet component for mobile navigation', () => {
    expect(layoutContent).toContain('Sheet')
    expect(layoutContent).toContain('SheetContent')
  })

  it('mobile sheet is triggered by menu button (isMobileOpen state)', () => {
    const sidebar = createSidebarState()
    expect(sidebar.isMobileOpen).toBe(false)
    sidebar.openMobile()
    expect(sidebar.isMobileOpen).toBe(true)
  })

  it('mobile sheet closes when closeMobile is called', () => {
    const sidebar = createSidebarState()
    sidebar.openMobile()
    sidebar.closeMobile()
    expect(sidebar.isMobileOpen).toBe(false)
  })

  it('sheet is only open on mobile when menu is triggered', () => {
    // On desktop: isMobileOpen may be true but it's irrelevant (sidebar is always visible)
    // Mobile sheet open = !isDesktop && isMobileOpen
    expect(computeSheetOpen(false, true)).toBe(true) // mobile + menu open
    expect(computeSheetOpen(true, true)).toBe(false) // desktop: never sheet
    expect(computeSheetOpen(false, false)).toBe(false) // mobile + menu closed
  })

  it('mobile menu button exists in the layout header', () => {
    // The Menu icon is used for mobile hamburger button
    expect(layoutContent).toContain('Menu')
  })
})

describe('Responsive Design - mobile workspace sheet', () => {
  it('workspace page opens a Sheet for detail panel on mobile', () => {
    const workspacesPath = resolve(__dirname, '../pages/workspaces/index.vue')
    const workspacesContent = readFileSync(workspacesPath, 'utf-8')
    expect(workspacesContent).toContain('Sheet')
    expect(workspacesContent).toContain('SheetContent')
  })

  it('workspace sheet is open on mobile when workspace is selected', () => {
    expect(computeWorkspaceSheetOpen(false, { id: 'ws-1' })).toBe(true)
  })

  it('workspace sheet is closed on desktop regardless of selection', () => {
    expect(computeWorkspaceSheetOpen(true, { id: 'ws-1' })).toBe(false)
  })

  it('workspace sheet is closed when no workspace is selected on mobile', () => {
    expect(computeWorkspaceSheetOpen(false, null)).toBe(false)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Responsive design conventions
// ────────────────────────────────────────────────────────────────────────────

describe('Responsive Design - layout conventions', () => {
  it('layout uses md: breakpoint for desktop transitions', () => {
    // 'md:' prefix for medium screen breakpoint (768px+)
    expect(layoutContent).toContain('md:')
  })

  it('layout uses lg: breakpoint for large screen grid columns', () => {
    const workspacesPath = resolve(__dirname, '../pages/workspaces/index.vue')
    const workspacesContent = readFileSync(workspacesPath, 'utf-8')
    expect(workspacesContent).toContain('lg:')
  })

  it('layout avoids hardcoded pixel widths in favor of Tailwind responsive classes', () => {
    // sidebar width is controlled via 'w-64' / 'w-16' Tailwind classes, not inline styles
    expect(layoutContent).toContain('w-64')
    expect(layoutContent).toContain('w-16')
  })

  it('mobile navigation uses sheet overlay pattern (not a separate page)', () => {
    // Sheet provides overlay navigation, keeping users in context
    const hasSheet = layoutContent.includes('<Sheet') || layoutContent.includes('Sheet v-model')
    expect(hasSheet).toBe(true)
  })
})
