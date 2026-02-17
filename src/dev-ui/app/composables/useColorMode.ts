import { ref, watch, onMounted } from 'vue'

const isDark = ref(false)

export function useColorMode() {
  function applyMode() {
    if (isDark.value) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }

  function toggle() {
    isDark.value = !isDark.value
    localStorage.setItem('kartograph-color-mode', isDark.value ? 'dark' : 'light')
    applyMode()
  }

  onMounted(() => {
    const stored = localStorage.getItem('kartograph-color-mode')
    if (stored === 'dark') {
      isDark.value = true
    } else if (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      isDark.value = true
    }
    applyMode()
  })

  watch(isDark, applyMode)

  return {
    isDark,
    toggle,
  }
}
