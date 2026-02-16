import { onMounted, onUnmounted, watch, shallowRef, type Ref } from 'vue'
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

  // Prevent feedback loops between the EditorView update listener and the
  // Vue doc watcher.  A simple boolean flag doesn't work because the listener
  // sets it synchronously, but Vue schedules watchers asynchronously — by the
  // time the watcher runs the flag has already been reset.  Instead we use a
  // generation counter: the listener bumps it, and the watcher only dispatches
  // when the generation hasn't changed since its last observation.
  let updateGeneration = 0
  let watcherGeneration = 0

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

        // Sync doc changes back to the ref.
        // For very large documents (>5 MB), skip syncing to avoid freezing
        // the main thread with a full doc.toString() on every keystroke.
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            updateGeneration++
            if (update.state.doc.length > 5_000_000) return
            doc.value = update.state.doc.toString()
          }
        }),
      ],
    })

    view.value = new EditorView({
      state,
      parent: container.value,
    })
  })

  // Watch for external doc changes (e.g., setting query from history/examples).
  // Skip dispatching to CM for very large docs to avoid freezing.
  watch(doc, (newDoc) => {
    if (!view.value) return
    // If this change originated from the editor itself, skip the dispatch
    if (watcherGeneration !== updateGeneration) {
      watcherGeneration = updateGeneration
      return
    }
    // Don't sync very large content back into CM — it will be handled
    // via large-file mode in the mutations page.
    if (newDoc.length > 5_000_000) return
    const currentDoc = view.value.state.doc.toString()
    if (newDoc !== currentDoc) {
      updateGeneration++ // prevent the listener from echoing back
      view.value.dispatch({
        changes: {
          from: 0,
          to: view.value.state.doc.length,
          insert: newDoc,
        },
      })
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
