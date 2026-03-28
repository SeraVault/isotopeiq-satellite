<template>
  <div ref="el" class="cm-host"></div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view'
import { EditorState, Compartment } from '@codemirror/state'
import { defaultKeymap, indentWithTab, history, historyKeymap } from '@codemirror/commands'
import { python } from '@codemirror/lang-python'
import { javascript } from '@codemirror/lang-javascript'
import { sql } from '@codemirror/lang-sql'
import { StreamLanguage } from '@codemirror/language'
import { shell } from '@codemirror/legacy-modes/mode/shell'
import { powerShell } from '@codemirror/legacy-modes/mode/powershell'
import { vbScript } from '@codemirror/legacy-modes/mode/vbscript'
import { oneDark } from '@codemirror/theme-one-dark'
import { bracketMatching, indentOnInput, foldGutter } from '@codemirror/language'
import { closeBrackets } from '@codemirror/autocomplete'

const props = defineProps({
  modelValue: { type: String, default: '' },
  language: { type: String, default: 'python' },
})
const emit = defineEmits(['update:modelValue'])

const el = ref(null)
let view = null
const langCompartment = new Compartment()

function langExtension(lang) {
  switch (lang) {
    case 'shell':      return StreamLanguage.define(shell)
    case 'batch':      return StreamLanguage.define(shell)   // closest available
    case 'powershell': return StreamLanguage.define(powerShell)
    case 'vbscript':   return StreamLanguage.define(vbScript)
    case 'javascript': return javascript()
    case 'sql':        return sql()
    default:           return python()
  }
}

onMounted(() => {
  view = new EditorView({
    parent: el.value,
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [
        oneDark,
        langCompartment.of(langExtension(props.language)),
        lineNumbers(),
        highlightActiveLine(),
        highlightActiveLineGutter(),
        foldGutter(),
        bracketMatching(),
        closeBrackets(),
        indentOnInput(),
        history(),
        keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
        EditorView.updateListener.of(update => {
          if (update.docChanged) {
            emit('update:modelValue', update.state.doc.toString())
          }
        }),
        EditorView.theme({
          '&': { height: '100%', fontSize: '0.83rem' },
          '.cm-scroller': { fontFamily: "'JetBrains Mono','Fira Code','Cascadia Code',monospace", overflow: 'auto' },
        }),
      ],
    }),
  })
})

watch(() => props.language, lang => {
  if (!view) return
  view.dispatch({ effects: langCompartment.reconfigure(langExtension(lang)) })
})

watch(() => props.modelValue, val => {
  if (!view) return
  const current = view.state.doc.toString()
  if (val !== current) {
    view.dispatch({ changes: { from: 0, to: current.length, insert: val ?? '' } })
  }
})

onBeforeUnmount(() => { view?.destroy() })
</script>

<style scoped>
.cm-host {
  height: 100%;
  overflow: hidden;
  border-radius: 6px;
  border: 1px solid #313244;
}
.cm-host:focus-within {
  border-color: #4fc3f7;
  box-shadow: 0 0 0 2px rgba(79,195,247,.2);
}
</style>
