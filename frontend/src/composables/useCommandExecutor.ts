import { ref } from 'vue'
import { dispatchCommand, getCommandStatus, type CommandResultSummary } from '@/api/commands'
import type { PendingCd } from './useTerminalCwd'

export type BlockKind = 'cmd' | 'stdout' | 'stderr' | 'meta' | 'hint'

export interface LogLine {
  kind: BlockKind
  text: string
  exitCode?: number | null
}

type SubmitPayload = {
  displayCommand: string
  commandToSend: string
  workDir?: string
  timeoutSeconds?: number
  pendingCd?: PendingCd | null
}

type UseCommandExecutorOptions = {
  deviceId: () => string
  scrollToBottom: () => void
  focusInput: () => void
  onCommandFinished?: (payload: { taskUuid: string }) => void
  onCdApplied?: (pending: PendingCd | null, exitCode: number) => void
}

export function useCommandExecutor(options: UseCommandExecutorOptions) {
  const lines = ref<LogLine[]>([])
  const running = ref(false)
  const dispatching = ref(false)
  const currentTaskUuid = ref<string | null>(null)

  let pollTimer: number | undefined
  let lastStdoutLen = 0
  let lastStderrLen = 0
  let currentCommandLineIndex: number | null = null
  let pendingCd: PendingCd | null = null

  function splitLines(text: string): string[] {
    if (!text) return []
    const arr = text.split(/\r?\n/)
    if (arr.length && arr[arr.length - 1] === '') arr.pop()
    return arr
  }

  function clearTerminalViewport() {
    lines.value = []
    currentCommandLineIndex = null
  }

  function normalizeTerminalChunk(chunk: string): string {
    if (!chunk) return ''

    let text = chunk
    if (/\x1b\[(?:3J|2J|H)/.test(text)) {
      clearTerminalViewport()
      text = text.replace(/\x1b\[(?:3J|2J|H)/g, '')
    }

    text = text.replace(/\x1B\[[0-?]*[ -/]*[@-~]/g, '')
    return text
  }

  function appendChunk(kind: 'stdout' | 'stderr', chunk: string) {
    const normalized = normalizeTerminalChunk(chunk)
    for (const l of splitLines(normalized)) {
      lines.value.push({ kind, text: l })
    }
    if (dispatching.value) dispatching.value = false
    options.scrollToBottom()
  }

  function stopPolling() {
    if (pollTimer !== undefined) {
      window.clearInterval(pollTimer)
      pollTimer = undefined
    }
  }

  function finishTracking(message: string, withEmit = true) {
    stopPolling()
    lines.value.push({ kind: 'meta', text: message })
    if (withEmit && currentTaskUuid.value) {
      options.onCommandFinished?.({ taskUuid: currentTaskUuid.value })
    }
    running.value = false
    dispatching.value = false
    currentTaskUuid.value = null
    currentCommandLineIndex = null
    pendingCd = null
    options.scrollToBottom()
    options.focusInput()
  }

  function completeTracking(exitCode: number, withEmit = true) {
    stopPolling()
    if (currentCommandLineIndex !== null && lines.value[currentCommandLineIndex]) {
      lines.value[currentCommandLineIndex].exitCode = exitCode
    }
    if (withEmit && currentTaskUuid.value) {
      options.onCommandFinished?.({ taskUuid: currentTaskUuid.value })
    }

    options.onCdApplied?.(pendingCd, exitCode)
    pendingCd = null

    running.value = false
    dispatching.value = false
    currentTaskUuid.value = null
    currentCommandLineIndex = null
    options.scrollToBottom()
    options.focusInput()
  }

  async function pollOnce() {
    const uuid = currentTaskUuid.value
    if (!uuid) return
    try {
      const resp = await getCommandStatus(uuid)
      const r: CommandResultSummary | undefined = resp.results.find(
        (x) => x.agent_id === options.deviceId(),
      )
      if (r) {
        const fullStdout = r.stdout || ''
        const fullStderr = r.stderr || ''
        if (fullStdout.length > lastStdoutLen) {
          appendChunk('stdout', fullStdout.slice(lastStdoutLen))
          lastStdoutLen = fullStdout.length
        }
        if (fullStderr.length > lastStderrLen) {
          appendChunk('stderr', fullStderr.slice(lastStderrLen))
          lastStderrLen = fullStderr.length
        }
        if (r.status === 'Finished') {
          const code = r.exitCode ?? 0
          completeTracking(code)
          return
        }
      }
      if (resp.status === 'Succeeded' || resp.status === 'Failed') {
        const r2 = resp.results.find((x) => x.agent_id === options.deviceId())
        const code = r2?.exitCode ?? (resp.status === 'Succeeded' ? 0 : 1)
        completeTracking(code)
      }
    } catch (err) {
      finishTracking(`[tracking error] ${(err as Error).message || 'unknown'}`, false)
    }
  }

  async function submit(payload: SubmitPayload) {
    if (running.value) return

    lines.value.push({ kind: 'cmd', text: payload.displayCommand })
    currentCommandLineIndex = lines.value.length - 1
    options.scrollToBottom()

    running.value = true
    dispatching.value = true
    lastStdoutLen = 0
    lastStderrLen = 0
    pendingCd = payload.pendingCd ?? null

    try {
      const { task_uuid } = await dispatchCommand({
        command: payload.commandToSend,
        workDir: payload.workDir,
        targets: [options.deviceId()],
        timeoutSeconds: payload.timeoutSeconds ?? 60,
      })
      currentTaskUuid.value = task_uuid
      options.scrollToBottom()

      pollTimer = window.setInterval(pollOnce, 500)
      pollOnce()
    } catch (err) {
      finishTracking(`[dispatch error] ${(err as Error).message || 'unknown'}`, false)
    }
  }

  function cancelTracking() {
    if (!running.value) return
    lines.value.push({
      kind: 'hint',
      text: '^C  — tracking stopped. command may still be running on the agent.',
    })
    finishTracking('[tracking cancelled]', false)
  }

  function pushBanner(banner: string | undefined, deviceId: string) {
    if (banner) {
      lines.value.push({ kind: 'meta', text: banner })
    }
    lines.value.push({
      kind: 'hint',
      text: `connected · device=${deviceId} · type a command and press ↵  (Ctrl+C / Esc to stop tailing)`,
    })
  }

  function reset(banner: string | undefined, deviceId: string) {
    stopPolling()
    running.value = false
    dispatching.value = false
    currentTaskUuid.value = null
    currentCommandLineIndex = null
    pendingCd = null
    lines.value = []
    pushBanner(banner, deviceId)
  }

  function cleanup() {
    stopPolling()
  }

  return {
    lines,
    running,
    dispatching,
    submit,
    pollOnce,
    cancelTracking,
    pushBanner,
    reset,
    cleanup,
  }
}

