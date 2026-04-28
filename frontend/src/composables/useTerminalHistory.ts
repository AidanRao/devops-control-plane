import { ref } from 'vue'

export function useTerminalHistory() {
  const history = ref<string[]>([])
  const historyIdx = ref<number>(-1)
  const draft = ref<string>('')

  function record(cmd: string) {
    history.value.push(cmd)
    historyIdx.value = -1
    draft.value = ''
  }

  function moveCaretToEnd(inputEl: HTMLInputElement | null) {
    if (!inputEl) return
    inputEl.setSelectionRange(inputEl.value.length, inputEl.value.length)
  }

  function handleArrowKeydown(
    e: KeyboardEvent,
    opts: {
      input: { value: string }
      inputEl: { value: HTMLInputElement | null }
      updateCaretOffset: () => void
    },
  ): boolean {
    if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return false
    if (history.value.length === 0) return false

    if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (historyIdx.value === -1) {
        draft.value = opts.input.value
        historyIdx.value = history.value.length - 1
      } else if (historyIdx.value > 0) {
        historyIdx.value--
      }
      opts.input.value = history.value[historyIdx.value] ?? ''
      queueMicrotask(() => {
        moveCaretToEnd(opts.inputEl.value)
        opts.updateCaretOffset()
      })
      return true
    }

    // ArrowDown
    if (historyIdx.value === -1) return false
    e.preventDefault()
    if (historyIdx.value < history.value.length - 1) {
      historyIdx.value++
      opts.input.value = history.value[historyIdx.value] ?? ''
    } else {
      historyIdx.value = -1
      opts.input.value = draft.value
    }
    queueMicrotask(() => {
      moveCaretToEnd(opts.inputEl.value)
      opts.updateCaretOffset()
    })
    return true
  }

  return {
    history,
    historyIdx,
    draft,
    record,
    handleArrowKeydown,
  }
}

