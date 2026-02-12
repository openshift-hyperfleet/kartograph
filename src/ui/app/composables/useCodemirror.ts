import { onMounted, onUnmounted, ref, watch, shallowRef, type Ref } from 'vue'
import { EditorState, Compartment, type Extension } from '@codemirror/state'
import { EditorView, keymap } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { searchKeymap, highlightSelectionMatches } from '@codemirror/search'
import { closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete'
import { bracketMatching } from '@codemirror/language'

export function useCodemirror(
  container: Ref<HTMLElement | null>,
  doc: Ref<string>,
  extensions: Ref<Extension[]>,
) {
  const view = shallowRef<EditorView | null>(null)
  const dynamicCompartment = new Compartment()

  // Prevent feedback loops when we programmatically update the doc
  let ignoreNextUpdate = false

  onMounted(() => {
    if (!container.value) return

    const state = EditorState.create({
      doc: doc.value,
      extensions: [
        // Base extensions that don't change
        keymap.of([
          ...defaultKeymap,
          ...historyKeymap,
          ...searchKeymap,
          ...closeBracketsKeymap,
        ]),
        history(),
        closeBrackets(),
        bracketMatching(),
        highlightSelectionMatches(),
        EditorView.lineWrapping,

        // Dynamic extensions (language, theme, etc.)
        dynamicCompartment.of(extensions.value),

        // Sync doc changes back to the ref
        EditorView.updateListener.of((update) => {
          if (update.docChanged && !ignoreNextUpdate) {
            ignoreNextUpdate = true
            doc.value = update.state.doc.toString()
            ignoreNextUpdate = false
          }
        }),
      ],
    })

    view.value = new EditorView({
      state,
      parent: container.value,
    })
  })

  // Watch for external doc changes (e.g., setting query from history/examples)
  watch(doc, (newDoc) => {
    if (!view.value || ignoreNextUpdate) return
    const currentDoc = view.value.state.doc.toString()
    if (newDoc !== currentDoc) {
      ignoreNextUpdate = true
      view.value.dispatch({
        changes: {
          from: 0,
          to: view.value.state.doc.length,
          insert: newDoc,
        },
      })
      ignoreNextUpdate = false
    }
  })

  // Watch for extension changes
  watch(extensions, (newExts) => {
    if (!view.value) return
    view.value.dispatch({
      effects: dynamicCompartment.reconfigure(newExts),
    })
  })

  // Focus helper
  function focus() {
    view.value?.focus()
  }

  onUnmounted(() => {
    view.value?.destroy()
    view.value = null
  })

  return { view, focus }
}
