/**
 * Persists mutation editor state across page navigations using Nuxt's
 * useState. This ensures the editor content, mode, and file name survive
 * when the user navigates away and returns.
 */
export function useMutationEditorState() {
  const editorContent = useState<string>('mutation-editor:content', () => '')
  const largeFileMode = useState<boolean>('mutation-editor:largeFileMode', () => false)
  const uploadFileName = useState<string>('mutation-editor:uploadFileName', () => '')

  function clearState() {
    editorContent.value = ''
    largeFileMode.value = false
    uploadFileName.value = ''
  }

  return {
    editorContent,
    largeFileMode,
    uploadFileName,
    clearState,
  }
}
