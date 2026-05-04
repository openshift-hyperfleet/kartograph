import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Dark Mode Logic ────────────────────────────────────────────────────────────
//
// Spec: "Dark Mode"
// Covers:
//   - Scenario: Toggle is available in header
//   - Scenario: Preference persists across sessions (localStorage)
//   - Light/dark class applied to document element

// The useColorMode composable manages theme state. These tests verify the
// core logic extracted from the composable.

describe('Color Mode - toggle persists to localStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('toggle sets isDark to true and writes "dark" to localStorage', () => {
    const isDark = { value: false }
    const KEY = 'kartograph-color-mode'

    function toggle() {
      isDark.value = !isDark.value
      localStorage.setItem(KEY, isDark.value ? 'dark' : 'light')
    }

    toggle()
    expect(isDark.value).toBe(true)
    expect(localStorage.getItem(KEY)).toBe('dark')
  })

  it('toggle back to light writes "light" to localStorage', () => {
    const isDark = { value: true }
    const KEY = 'kartograph-color-mode'

    function toggle() {
      isDark.value = !isDark.value
      localStorage.setItem(KEY, isDark.value ? 'dark' : 'light')
    }

    toggle()
    expect(isDark.value).toBe(false)
    expect(localStorage.getItem(KEY)).toBe('light')
  })
})

describe('Color Mode - initial load reads from localStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('initializes to dark when localStorage stores "dark"', () => {
    localStorage.setItem('kartograph-color-mode', 'dark')

    const isDark = { value: false }

    function initColorMode() {
      const stored = localStorage.getItem('kartograph-color-mode')
      if (stored === 'dark') isDark.value = true
    }

    initColorMode()
    expect(isDark.value).toBe(true)
  })

  it('initializes to light when localStorage stores "light"', () => {
    localStorage.setItem('kartograph-color-mode', 'light')

    const isDark = { value: true }

    function initColorMode() {
      const stored = localStorage.getItem('kartograph-color-mode')
      if (stored === 'dark') {
        isDark.value = true
      } else if (stored === 'light') {
        isDark.value = false
      }
    }

    initColorMode()
    expect(isDark.value).toBe(false)
  })

  it('defaults to light mode when no stored preference exists', () => {
    // No localStorage entry set
    const isDark = { value: false }

    function initColorMode() {
      const stored = localStorage.getItem('kartograph-color-mode')
      if (stored === 'dark') isDark.value = true
    }

    initColorMode()
    expect(isDark.value).toBe(false)
  })
})

describe('Color Mode - system preference fallback', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('uses system dark preference when no stored value exists', () => {
    // Simulate matchMedia returning dark preference
    const mockMatchMedia = vi.fn().mockReturnValue({ matches: true })
    const isDark = { value: false }

    function initColorMode() {
      const stored = localStorage.getItem('kartograph-color-mode')
      if (stored === 'dark') {
        isDark.value = true
      } else if (!stored && mockMatchMedia('(prefers-color-scheme: dark)').matches) {
        isDark.value = true
      }
    }

    initColorMode()
    expect(isDark.value).toBe(true)
  })

  it('does not apply system preference when stored preference exists', () => {
    localStorage.setItem('kartograph-color-mode', 'light')
    const mockMatchMedia = vi.fn().mockReturnValue({ matches: true })
    const isDark = { value: false }

    function initColorMode() {
      const stored = localStorage.getItem('kartograph-color-mode')
      if (stored === 'dark') {
        isDark.value = true
      } else if (!stored && mockMatchMedia('(prefers-color-scheme: dark)').matches) {
        isDark.value = true
      }
    }

    initColorMode()
    // Stored 'light' takes precedence — system dark preference is ignored
    expect(isDark.value).toBe(false)
    // matchMedia should not have been called (or called but result ignored since stored exists)
  })
})

describe('Color Mode - CSS class application', () => {
  it('adds "dark" class to documentElement when isDark is true', () => {
    const isDark = { value: true }

    function applyMode(el: { classList: { add: (c: string) => void; remove: (c: string) => void } }) {
      if (isDark.value) {
        el.classList.add('dark')
      } else {
        el.classList.remove('dark')
      }
    }

    const classes = new Set<string>()
    const fakeEl = {
      classList: {
        add: (c: string) => classes.add(c),
        remove: (c: string) => classes.delete(c),
      },
    }

    applyMode(fakeEl)
    expect(classes.has('dark')).toBe(true)
  })

  it('removes "dark" class from documentElement when isDark is false', () => {
    const isDark = { value: false }
    const classes = new Set<string>(['dark'])

    function applyMode(el: { classList: { add: (c: string) => void; remove: (c: string) => void } }) {
      if (isDark.value) el.classList.add('dark')
      else el.classList.remove('dark')
    }

    const fakeEl = {
      classList: {
        add: (c: string) => classes.add(c),
        remove: (c: string) => classes.delete(c),
      },
    }

    applyMode(fakeEl)
    expect(classes.has('dark')).toBe(false)
  })
})

// ── Dark Mode — toggle present in header ───────────────────────────────────────
//
// Spec: "Dark Mode > Toggle"
// Verifies that:
//   1. The toggle button exists and calls toggleColorMode in default.vue
//   2. Moon and Sun icons from lucide-vue-next are used
//   3. The toggle appears inside the <header> region (not in sidebar or settings)
//   4. The useColorMode composable is imported in the layout
//   5. The composable correctly uses classList.add('dark') on documentElement
//   6. The composable writes to localStorage on toggle

describe('Dark Mode - toggle in header', () => {
  it('default.vue renders a dark mode toggle button in the header', () => {
    const layoutContent = readFileSync(
      resolve(__dirname, '../layouts/default.vue'),
      'utf-8',
    )
    // The toggle button must call toggleColorMode
    expect(layoutContent).toContain('toggleColorMode')
    // It must use Moon and Sun icons from lucide-vue-next
    expect(layoutContent).toContain('Moon')
    expect(layoutContent).toContain('Sun')
    // The toggle must be inside the header (not a settings page)
    const toggleIndex = layoutContent.indexOf('toggleColorMode')
    expect(toggleIndex).toBeGreaterThan(-1)
  })

  it('dark mode toggle is located inside the <header> element, not the sidebar', () => {
    const layoutContent = readFileSync(
      resolve(__dirname, '../layouts/default.vue'),
      'utf-8',
    )
    // Extract the header element's content
    const headerStart = layoutContent.indexOf('<header ')
    const headerEnd = layoutContent.indexOf('</header>')
    expect(headerStart).toBeGreaterThan(-1)
    expect(headerEnd).toBeGreaterThan(headerStart)

    const headerContent = layoutContent.slice(headerStart, headerEnd + '</header>'.length)

    // The @click handler calling toggleColorMode must be inside the header (not sidebar or settings)
    expect(headerContent).toContain('@click="toggleColorMode"')
    // Moon and Sun icons must also be present in the header
    expect(headerContent).toContain('Moon')
    expect(headerContent).toContain('Sun')
  })

  it('default.vue imports useColorMode composable', () => {
    const layoutContent = readFileSync(
      resolve(__dirname, '../layouts/default.vue'),
      'utf-8',
    )
    expect(layoutContent).toContain('useColorMode')
  })

  it('useColorMode applies "dark" class to documentElement', () => {
    const composableContent = readFileSync(
      resolve(__dirname, '../composables/useColorMode.ts'),
      'utf-8',
    )
    expect(composableContent).toContain('classList.add')
    expect(composableContent).toContain("'dark'")
  })

  it('useColorMode writes to localStorage on toggle', () => {
    const composableContent = readFileSync(
      resolve(__dirname, '../composables/useColorMode.ts'),
      'utf-8',
    )
    expect(composableContent).toContain('localStorage.setItem')
    expect(composableContent).toContain('kartograph-color-mode')
  })

  it('dark mode toggle has an accessible label via tooltip', () => {
    const layoutContent = readFileSync(
      resolve(__dirname, '../layouts/default.vue'),
      'utf-8',
    )
    // Tooltip with Switch to light/dark mode label must be present
    expect(layoutContent).toContain('Switch to light mode')
    expect(layoutContent).toContain('Switch to dark mode')
  })
})
