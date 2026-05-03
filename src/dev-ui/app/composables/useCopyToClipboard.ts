import { ref } from 'vue'
import { toast } from 'vue-sonner'

/**
 * useCopyToClipboard
 *
 * Centralised clipboard + toast composable.
 *
 * Spec: specs/ui/experience.spec.md — Interaction Principles
 * "GIVEN any identifier, configuration snippet, or secret
 *  THEN a copy button is provided
 *  AND a toast confirms the copy action"
 *
 * Usage:
 *   const { copied, copyToClipboard } = useCopyToClipboard()
 *
 *   await copyToClipboard(secret, 'API key secret')
 *   // ↳ shows: "API key secret copied"
 *
 *   await copyToClipboard(id)
 *   // ↳ shows: "Copied to clipboard"
 */
export function useCopyToClipboard() {
  /** Resets to false 2 s after a successful copy — use for icon feedback. */
  const copied = ref(false)

  /**
   * Copy `text` to the clipboard.
   *
   * @param text  - The string to copy.
   * @param label - Optional label for the success toast, e.g. "API key secret".
   *                If omitted the toast reads "Copied to clipboard".
   * @returns     `true` on success, `false` if the clipboard write fails.
   */
  async function copyToClipboard(text: string, label?: string): Promise<boolean> {
    try {
      await navigator.clipboard.writeText(text)
      toast.success(label ? `${label} copied` : 'Copied to clipboard')
      copied.value = true
      setTimeout(() => {
        copied.value = false
      }, 2000)
      return true
    }
    catch {
      toast.error('Failed to copy to clipboard')
      return false
    }
  }

  return { copied, copyToClipboard }
}
