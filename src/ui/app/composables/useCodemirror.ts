import { onMounted, onUnmounted, watch, shallowRef, nextTick, type Ref } from 'vue'
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

  function createView(el: HTMLElement) {
    if (view.value) return // already created

    const state = EditorState.create({
      doc: doc.value,
      extensions: [
        // Ensure CM always has height even with an empty document.
        // The outer min-h CSS class only sizes .cm-editor; CM's internal
        // scroller/content still measures 0 when the doc is empty.  Setting
        // min-height via EditorView.theme targets the internal elements so
        // CM's viewport calculation always has non-zero dimensions.
        EditorView.theme({
          '&': { minHeight: '300px' },
          '.cm-scroller': { minHeight: '300px' },
        }),

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
      parent: el,
    })

    // Force a re-measure after the browser has had a chance to layout.
    // This prevents zero-height editors when the container appears via v-if
    // or is rendered during the first paint (onMounted).
    nextTick(() => {
      requestAnimationFrame(() => {
        view.value?.requestMeasure()
      })
    })
  }

  onMounted(() => {
    if (container.value) createView(container.value)
  })

  // Handle late mounting: when the container ref appears via v-if after
  // onMounted has already fired, create the EditorView at that point.
  // Uses flush: 'post' to ensure the DOM element is fully mounted and has
  // correct dimensions before we create the EditorView (prevents zero-height).
  watch(container, (el) => {
    if (el && !view.value) createView(el)
  }, { flush: 'post' })

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
