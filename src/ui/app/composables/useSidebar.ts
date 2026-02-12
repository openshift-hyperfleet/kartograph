import { ref } from 'vue'

const isCollapsed = ref(false)
const isMobileOpen = ref(false)

export function useSidebar() {
  function toggleCollapsed() {
    isCollapsed.value = !isCollapsed.value
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
