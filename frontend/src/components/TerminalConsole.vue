<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { FitAddon } from '@xterm/addon-fit'
import { Terminal } from '@xterm/xterm'
import '@xterm/xterm/css/xterm.css'
import { useTerminalSession } from '@/composables/useTerminalSession'

/**
 * xterm 终端组件：
 * - 每个组件绑定一个真实 terminal session；
 * - xterm 负责渲染 ANSI/PTY 原始输出；
 * - 输入通过 terminal.stdin.write 写入 PTY；
 * - Ctrl+C 通过 signal 发送给前台进程组。
 */

const props = defineProps<{
  deviceId: string
  sessionId?: string
  showRail?: boolean
  canCreateSession?: boolean
  banner?: string
  cpuPercent?: number | null
  memPercent?: number | null
  memUsed?: number | null
  memTotal?: number | null
}>()

const emit = defineEmits<{
  (e: 'create-session'): void
  (e: 'session-state', payload: { sessionId: string; title: string; status: string }): void
}>()

const terminalHostEl = ref<HTMLDivElement | null>(null)
const currentSessionId = computed(() => props.sessionId ?? 'default')

const {
  connected,
  sessionStatus,
  connect,
  sendInput,
  sendSignal,
  resize,
  cleanup,
  reset,
} = useTerminalSession({
  sessionId: () => currentSessionId.value,
  onSessionState: (payload) => {
    emit('session-state', {
      sessionId: payload.sessionId,
      title: payload.title,
      status: payload.status,
    })
  },
  onChunk: (payload) => writeChunk(payload.data),
  onClosed: (payload) => writeSystemLine(`[session closed] ${payload.reason}`),
  onError: (payload) => writeSystemLine(`[session error] ${payload.code}: ${payload.message}`),
  onDisconnect: () => writeSystemLine('[terminal disconnected]'),
})

const isOpen = computed(() => connected.value && sessionStatus.value === 'open')
const statusLabel = computed(() => (connected.value ? sessionStatus.value : 'disconnected'))

let terminal: Terminal | null = null
let fitAddon: FitAddon | null = null
let dataListener: { dispose: () => void } | null = null
let resizeTimer: number | undefined
const pendingWrites: string[] = []

function formatPercent(value?: number | null) {
  if (value === undefined || value === null || Number.isNaN(value)) return '—'
  return `${value.toFixed(1)}%`
}

function formatBytes(value?: number | null) {
  if (value === undefined || value === null || Number.isNaN(value)) return '—'
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
  let n = value
  let idx = 0
  while (n >= 1024 && idx < units.length - 1) {
    n /= 1024
    idx++
  }
  const digits = idx <= 1 ? 0 : idx === 2 ? 1 : 2
  return `${n.toFixed(digits)} ${units[idx]}`
}

function queueWrite(data: string) {
  if (terminal) {
    terminal.write(data)
    return
  }
  pendingWrites.push(data)
}

function writeChunk(data: string) {
  queueWrite(data)
}

function writeSystemLine(text: string) {
  queueWrite(`${text}\r\n`)
}

function flushPendingWrites() {
  if (!terminal || !pendingWrites.length) return
  while (pendingWrites.length) {
    terminal.write(pendingWrites.shift()!)
  }
}

function writeBanner() {
  if (!props.banner) return
  for (const line of props.banner.split(/\r?\n/)) {
    if (line.trim()) writeSystemLine(line)
  }
}

function disposeTerminal() {
  window.clearTimeout(resizeTimer)
  resizeTimer = undefined
  dataListener?.dispose()
  dataListener = null
  fitAddon = null
  terminal?.dispose()
  terminal = null
}

function createTerminal() {
  disposeTerminal()
  if (!terminalHostEl.value) return

  const term = new Terminal({
    fontFamily: "'JetBrains Mono Variable', 'SFMono-Regular', Menlo, Consolas, monospace",
    fontSize: 13,
    lineHeight: 1.35,
    cursorBlink: true,
    scrollback: 5000,
    allowTransparency: false,
    theme: {
      background: '#0b0f17',
      foreground: '#e2e8f0',
      cursor: '#93c5fd',
      cursorAccent: '#0b0f17',
      selectionBackground: 'rgba(96, 165, 250, 0.28)',
      black: '#0b0f17',
      red: '#f87171',
      green: '#4ade80',
      yellow: '#fbbf24',
      blue: '#60a5fa',
      magenta: '#c084fc',
      cyan: '#22d3ee',
      white: '#e2e8f0',
      brightBlack: '#64748b',
      brightRed: '#fca5a5',
      brightGreen: '#86efac',
      brightYellow: '#fde68a',
      brightBlue: '#93c5fd',
      brightMagenta: '#d8b4fe',
      brightCyan: '#67e8f9',
      brightWhite: '#f8fafc',
    },
  })
  const fit = new FitAddon()
  term.loadAddon(fit)
  term.open(terminalHostEl.value)

  terminal = term
  fitAddon = fit
  dataListener = term.onData((data: string) => {
    void sendInput(data).catch((err) => {
      writeSystemLine(`[send error] ${(err as Error).message || 'unknown'}`)
    })
  })

  writeBanner()
  writeSystemLine(`terminal session=${currentSessionId.value} · waiting for attach`)
  flushPendingWrites()
  requestAnimationFrame(() => {
    void syncResize(true)
    term.focus()
  })
}

function resetTerminalViewport() {
  pendingWrites.length = 0
  if (!terminal) return
  terminal.reset()
  writeBanner()
  writeSystemLine(`terminal session=${currentSessionId.value} · waiting for attach`)
}

async function syncResize(immediate = false, retryCount = 0) {
  if (!terminal || !fitAddon || !terminalHostEl.value) return
  
  if (!connected.value) {
    if (retryCount < 10) {
      setTimeout(() => {
        void syncResize(immediate, retryCount + 1)
      }, 50 * (retryCount + 1))
    }
    return
  }
  
  const currentWidth = terminalHostEl.value.offsetWidth
  const currentHeight = terminalHostEl.value.offsetHeight
  
  if (currentWidth <= 0 || currentHeight <= 0) {
    if (retryCount < 10) {
      setTimeout(() => {
        void syncResize(immediate, retryCount + 1)
      }, 50 * (retryCount + 1))
    }
    return
  }
  
  const currentFitAddon = fitAddon

  const perform = async () => {
    currentFitAddon.fit()
    
    if (terminal && terminal.cols > 0 && terminal.rows > 0) {
      try {
        await resize(terminal.cols, terminal.rows)
      } catch {
      }
    }
  }

  if (immediate) {
    await perform()
    return
  }

  window.clearTimeout(resizeTimer)
  resizeTimer = window.setTimeout(() => {
    void perform()
  }, 50)
}

function focusTerminal() {
  nextTick(() => {
    requestAnimationFrame(() => {
      terminal?.focus()
      void syncResize(true)
    })
  })
}

function onWindowResize() {
  void syncResize()
}

function onGlobalKeydown(e: KeyboardEvent) {
  const isCtrlC = (e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'C')
  if (!isCtrlC) return
  if (!terminalHostEl.value?.contains(document.activeElement)) return
  if (terminal?.hasSelection()) return
  e.preventDefault()
  void sendSignal('SIGINT').catch(() => {})
}

watch(
  () => [props.deviceId, currentSessionId.value],
  () => {
    reset()
    resetTerminalViewport()
    connect()
    focusTerminal()
    void syncResize(true)
  },
)

watch(
  () => props.showRail,
  () => {
    nextTick(() => {
      void syncResize(true)
    })
  },
)

watch(
  connected,
  (isConnected) => {
    if (isConnected) {
      nextTick(() => {
        requestAnimationFrame(() => {
          void syncResize(true)
        })
      })
    }
  }
)

onMounted(() => {
  createTerminal()
  window.addEventListener('keydown', onGlobalKeydown)
  window.addEventListener('resize', onWindowResize)
  connect()
  focusTerminal()
  void syncResize(true)
})

onBeforeUnmount(() => {
  cleanup()
  disposeTerminal()
  window.removeEventListener('keydown', onGlobalKeydown)
  window.removeEventListener('resize', onWindowResize)
})

defineExpose({
  focus: focusTerminal,
  fillInput: (text: string) => {
    focusTerminal()
    void sendInput(text).catch((err) => {
      writeSystemLine(`[send error] ${(err as Error).message || 'unknown'}`)
    })
  },
})
</script>

<template>
  <div class="terminal" @click="focusTerminal">
    <div class="terminal-chrome" @click.stop>
      <span class="dot dot--red" />
      <span class="dot dot--yellow" />
      <span class="dot dot--green" />
      <span class="chrome-title">
        <span class="chrome-host">agent@{{ deviceId }}</span>
        <span class="chrome-tag" :class="isOpen ? 'chrome-tag--live' : 'chrome-tag--idle'">
          {{ statusLabel }}
        </span>
      </span>
      <div class="chrome-right">
        <span class="metric-pill" title="CPU usage">
          <span class="metric-key">CPU</span>
          <span class="metric-val">{{ formatPercent(cpuPercent) }}</span>
        </span>
        <span
          class="metric-pill"
          :title="memUsed != null && memTotal != null ? `${formatBytes(memUsed)} / ${formatBytes(memTotal)}` : 'Memory usage'"
        >
          <span class="metric-key">MEM</span>
          <span class="metric-val">{{ formatPercent(memPercent) }}</span>
          <span class="metric-sub">{{ formatBytes(memUsed) }}/{{ formatBytes(memTotal) }}</span>
        </span>
        <button
          type="button"
          class="chrome-action"
          title="新建终端"
          aria-label="新建终端"
          :disabled="!props.canCreateSession"
          @click.stop="emit('create-session')"
        >
          +
        </button>
      </div>
    </div>

    <div class="terminal-content">
      <div class="terminal-body">
        <div ref="terminalHostEl" class="terminal-host" />
      </div>

      <aside v-if="props.showRail && $slots.rail" class="terminal-rail" aria-label="Terminal sessions">
        <slot name="rail" />
      </aside>
    </div>
  </div>
</template>

<style scoped>
.terminal {
  --bg: #0b0f17;
  --fg: #e2e8f0;
  --muted: #64748b;
  --green: #4ade80;
  --border: #1e293b;

  position: relative;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  font-family: 'JetBrains Mono Variable', 'SFMono-Regular', Menlo, Consolas, monospace;
  color: var(--fg);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.04) inset,
    0 10px 30px rgba(2, 6, 23, 0.35),
    0 0 0 1px rgba(74, 222, 128, 0.03);
  height: 100%;
  display: flex;
  flex-direction: column;
}

.terminal-content {
  flex: 1;
  min-height: 0;
  display: flex;
}

.terminal-chrome {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: linear-gradient(180deg, #111827 0%, #0d1320 100%);
  border-bottom: 1px solid var(--border);
}

.dot {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.3);
}

.dot--red { background: #ff5f57; }
.dot--yellow { background: #febc2e; }
.dot--green { background: #28c840; }

.chrome-title {
  margin-left: 12px;
  font-size: 12px;
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 8px;
  letter-spacing: 0.3px;
}

.chrome-host {
  color: #cbd5e1;
}

.chrome-tag {
  margin-left: 6px;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 10px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.chrome-tag--live {
  color: #052e16;
  background: var(--green);
  animation: pulse 1.4s ease-in-out infinite;
}

.chrome-tag--idle {
  color: rgba(226, 232, 240, 0.82);
  background: rgba(51, 65, 85, 0.8);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}

.chrome-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}

.chrome-action {
  width: 28px;
  height: 28px;
  padding: 0;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.35);
  color: rgba(226, 232, 240, 0.95);
  cursor: pointer;
  font-family: inherit;
  font-size: 18px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    background-color 120ms ease,
    border-color 120ms ease,
    color 120ms ease,
    opacity 120ms ease;
}

.chrome-action:hover:not(:disabled) {
  background: rgba(30, 41, 59, 0.72);
  border-color: rgba(96, 165, 250, 0.32);
}

.chrome-action:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.metric-pill {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.35);
  color: rgba(226, 232, 240, 0.9);
  font-size: 11px;
  line-height: 1.2;
  letter-spacing: 0.2px;
  white-space: nowrap;
}

.metric-key {
  color: rgba(148, 163, 184, 0.9);
  letter-spacing: 1px;
}

.metric-val {
  color: #e2e8f0;
}

.metric-sub {
  color: rgba(148, 163, 184, 0.85);
  font-size: 10px;
}

.terminal-body {
  flex: 1;
  min-width: 0;
  min-height: 0;
  position: relative;
  display: flex;
  padding: 8px 10px 10px;
  background: var(--bg);
  overflow: hidden;
}

.terminal-host {
  flex: 1;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

:deep(.xterm) {
  flex: 1;
  height: 100%;
  width: 100%;
}

:deep(.xterm-viewport) {
  overflow-y: auto !important;
}

.terminal-rail {
  width: 118px;
  min-width: 118px;
  border-left: 1px solid rgba(30, 41, 59, 0.92);
  background:
    linear-gradient(180deg, rgba(7, 15, 28, 0.96) 0%, rgba(6, 12, 24, 0.98) 100%),
    linear-gradient(90deg, rgba(96, 165, 250, 0.05), rgba(15, 23, 42, 0));
  box-shadow:
    inset 1px 0 0 rgba(148, 163, 184, 0.04),
    inset 24px 0 40px rgba(15, 23, 42, 0.16);
  display: flex;
  flex-direction: column;
}
</style>
