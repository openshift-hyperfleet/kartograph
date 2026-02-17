import { ref, watch } from 'vue'

const STORAGE_KEY = 'kartograph:sidebar-collapsed'

function loadCollapsed(): boolean {
  if (typeof window === 'undefined') return false
  return localStorage.getItem(STORAGE_KEY) === 'true'
}

const isCollapsed = ref(loadCollapsed())
const isMobileOpen = ref(false)

export function useSidebar() {
  function toggleCollapsed() {
    isCollapsed.value = !isCollapsed.value
    localStorage.setItem(STORAGE_KEY, String(isCollapsed.value))
  }

  function toggleMobile() {
    isMobileOpen.value = !isMobileOpen.value
  }

  function closeMobile() {
    isMobileOpen.value = false
  }

  return {
    isCollapsed,
    isMobileOpen,
    toggleCollapsed,
    toggleMobile,
    closeMobile,
  }
}
