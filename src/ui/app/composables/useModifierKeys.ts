import { ref, onMounted, onBeforeUnmount } from 'vue'

const ctrlHeld = ref(false)
const altHeld = ref(false)

let listenerCount = 0

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Control' || e.key === 'Meta') ctrlHeld.value = true
  if (e.key === 'Alt') altHeld.value = true
}

function handleKeyUp(e: KeyboardEvent) {
  if (e.key === 'Control' || e.key === 'Meta') ctrlHeld.value = false
  if (e.key === 'Alt') altHeld.value = false
}

function handleBlur() {
  ctrlHeld.value = false
  altHeld.value = false
}

export function useModifierKeys() {
  onMounted(() => {
    if (listenerCount === 0) {
      document.addEventListener('keydown', handleKeyDown)
      document.addEventListener('keyup', handleKeyUp)
      window.addEventListener('blur', handleBlur)
    }
    listenerCount++
  })

  onBeforeUnmount(() => {
    listenerCount--
    if (listenerCount === 0) {
      document.removeEventListener('keydown', handleKeyDown)
      document.removeEventListener('keyup', handleKeyUp)
      window.removeEventListener('blur', handleBlur)
    }
  })

  return { ctrlHeld, altHeld }
}
