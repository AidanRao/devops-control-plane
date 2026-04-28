<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useCommandExecutor } from '@/composables/useCommandExecutor'
import { useTerminalCwd } from '@/composables/useTerminalCwd'
import { useTerminalHistory } from '@/composables/useTerminalHistory'

/**
 * 交互式终端组件：
 * - 输入命令 → Enter 下发 → 自动轮询结果 → 输出到当前 block；
 * - Ctrl+C / Esc 停止对当前任务的结果追踪（不中断 agent 上的实际执行）；
 * - ↑ / ↓ 浏览本地输入历史。
 */

const props = defineProps<{
  deviceId: string
  /** 可选：初始提示横幅 */
  banner?: string
  /** 可选：agent 侧上报的实时指标（来自心跳聚合） */
  cpuPercent?: number | null
  memPercent?: number | null
  memUsed?: number | null
  memTotal?: number | null
}>()

const emit = defineEmits<{
  (e: 'command-finished', payload: { taskUuid: string }): void
}>()

const input = ref('')
const bodyEl = ref<HTMLDivElement | null>(null)
const inputEl = ref<HTMLInputElement | null>(null)
// 光标在 input 中的位置（字符下标），用于把自定义方块光标放到正确位置
const caretIndex = ref(0)
const measureEl = ref<HTMLSpanElement | null>(null)
const caretOffset = ref(0)

const deviceIdRef = computed(() => props.deviceId)
const {
  cwd,
  isTempCwd,
  loadCwd,
  persistCwd,
  clearCwd,
  parseCdCommand,
  applyCdResult,
  resetForDevice,
} = useTerminalCwd(deviceIdRef)
const { record, handleArrowKeydown } = useTerminalHistory()

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

function scrollToBottom() {
  nextTick(() => {
    if (bodyEl.value) bodyEl.value.scrollTop = bodyEl.value.scrollHeight
  })
}

function focusInput() {
  nextTick(() => inputEl.value?.focus())
}

const {
  lines,
  running,
  dispatching,
  submit: executeCommand,
  cancelTracking,
  pushBanner,
  reset,
  cleanup,
} = useCommandExecutor({
  deviceId: () => props.deviceId,
  scrollToBottom,
  focusInput,
  onCommandFinished: (payload) => emit('command-finished', payload),
  onCdApplied: (pending, exitCode) => applyCdResult(pending, exitCode),
})

pushBanner(props.banner, props.deviceId)

/**
 * 根据 input 当前选区位置，测量出自定义光标应该放置的像素偏移。
 * 通过一个隐藏的 span 镜像渲染「光标前的文本」，取其宽度即可。
 */
function updateCaretOffset() {
  const el = inputEl.value
  const meas = measureEl.value
  if (!el || !meas) return
  const pos = el.selectionStart ?? el.value.length
  caretIndex.value = pos
  // 用 NBSP 替换空格，避免末尾空格被 HTML 折叠
  const before = el.value.slice(0, pos).replace(/ /g, '\u00a0')
  meas.textContent = before
  caretOffset.value = meas.offsetWidth
}

function onInputEvent() {
  // v-model 会在 input 事件后触发，selectionStart 已经更新，nextTick 让 measure span 的内容先更新
  nextTick(updateCaretOffset)
}

function onInputSelectionChange() {
  updateCaretOffset()
}

async function submit() {
  const cmd = input.value.trim()
  if (!cmd) return
  const cd = parseCdCommand(cmd)
  const commandToSend = cd ? cd.commandToSend : cmd

  // 输入历史
  record(cmd)
  input.value = ''
  nextTick(updateCaretOffset)
  await executeCommand({
    displayCommand: cmd,
    commandToSend,
    workDir: cwd.value ? cwd.value : undefined,
    pendingCd: cd?.pending ?? null,
    timeoutSeconds: 60,
  })
}

function onKeydown(e: KeyboardEvent) {
  // Ctrl+C / Cmd+C / Esc 停止追踪（input 未禁用，这里仍可进入）
  const isCtrlC = (e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'C')
  const isEsc = e.key === 'Escape'
  if ((isCtrlC || isEsc) && running.value) {
    // Ctrl+C 若 input 里有选区（用户想复制），则不拦截
    const inputNode = inputEl.value
    if (isCtrlC && inputNode) {
      const hasSelection =
        typeof inputNode.selectionStart === 'number' &&
        typeof inputNode.selectionEnd === 'number' &&
        inputNode.selectionStart !== inputNode.selectionEnd
      if (hasSelection) return
    }
    e.preventDefault()
    cancelTracking()
    return
  }

  if (handleArrowKeydown(e, { input, inputEl, updateCaretOffset })) {
    return
  }
  if (e.key === 'Enter') {
    if (running.value) {
      // 执行中禁止回车再下发新命令
      e.preventDefault()
      return
    }
    e.preventDefault()
    submit()
  }
}

// 兜底：全局 keydown 监听 Ctrl+C / ⌘+C / Esc，保证焦点不在 input 时也生效
function onGlobalKeydown(e: KeyboardEvent) {
  if (!running.value) return
  const isCtrlC = (e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'C')
  const isEsc = e.key === 'Escape'
  if (!isCtrlC && !isEsc) return
  // 若事件来源于我们自己的 input，交给 onKeydown 处理以便走选区判断
  if (e.target === inputEl.value) return
  e.preventDefault()
  cancelTracking()
}

// 当 deviceId 切换时重置终端
watch(
  () => props.deviceId,
  () => {
    reset(props.banner, props.deviceId)
    resetForDevice()
    focusInput()
  },
)

onMounted(() => {
  window.addEventListener('keydown', onGlobalKeydown)
  loadCwd()
  focusInput()
})

onBeforeUnmount(() => {
  cleanup()
  window.removeEventListener('keydown', onGlobalKeydown)
})

// 暴露给父组件：把历史命令回填到输入框（便于点击历史时快速复用）
defineExpose({
  focus: focusInput,
  fillInput: (text: string) => {
    input.value = text
    focusInput()
    nextTick(() => {
      const el = inputEl.value
      if (el) el.setSelectionRange(el.value.length, el.value.length)
      updateCaretOffset()
    })
  },
})
</script>

<template>
  <div class="terminal" @click="focusInput">
    <!-- 顶部 chrome 区域允许交互（cwd 等），避免点击时把焦点抢到命令输入 -->
    <div class="terminal-chrome" @click.stop>
      <span class="dot dot--red" />
      <span class="dot dot--yellow" />
      <span class="dot dot--green" />
      <span class="chrome-title">
        <span class="chrome-host">agent@{{ deviceId }}</span>
        <span v-if="running" class="chrome-tag chrome-tag--live">● live</span>
      </span>
      <div class="chrome-right">
        <span
          class="cwd-pill"
          :class="{
            'cwd-pill--set': Boolean(cwd),
            'cwd-pill--temp': isTempCwd,
          }"
          title="工作目录（会话级）"
        >
          <span class="cwd-key">cwd</span>
          <input
            v-model="cwd"
            class="cwd-input"
            type="text"
            spellcheck="false"
            placeholder="(default)"
            @mousedown.stop
            @click.stop
            @blur="persistCwd"
            @keydown.enter.prevent="persistCwd"
            @keydown.esc.prevent="clearCwd"
          />
        </span>
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
      </div>
    </div>

    <div ref="bodyEl" class="terminal-body">
      <template v-for="(line, i) in lines" :key="i">
        <div v-if="line.kind === 'cmd'" class="line line--cmd">
          <el-tooltip
            v-if="line.exitCode !== undefined && line.exitCode !== null"
            :content="`exit code: ${line.exitCode}`"
            placement="top"
          >
            <span
              class="cmd-status-dot"
              :class="line.exitCode === 0 ? 'cmd-status-dot--success' : 'cmd-status-dot--error'"
            />
          </el-tooltip>
          <span v-else class="cmd-status-dot cmd-status-dot--pending" />
          <span class="prompt">$</span>
          <span class="cmd-text">{{ line.text }}</span>
        </div>
        <div v-else-if="line.kind === 'stdout'" class="line line--stdout">{{ line.text }}</div>
        <div v-else-if="line.kind === 'stderr'" class="line line--stderr">{{ line.text }}</div>
        <div v-else-if="line.kind === 'hint'" class="line line--hint">{{ line.text }}</div>
        <div v-else class="line line--meta">{{ line.text }}</div>
      </template>

      <!-- 下发中但尚未收到输出的临时指示行；收到第一条输出或终态即消失 -->
      <div v-if="dispatching" class="line line--dispatching" aria-live="polite">
        <span class="dispatch-spinner" aria-hidden="true">
          <span class="spinner-dot" />
          <span class="spinner-dot" />
          <span class="spinner-dot" />
        </span>
        <span class="dispatch-text">dispatching</span>
      </div>

      <!-- 当前输入行（始终在最底部） -->
      <div class="line line--input">
        <span class="cmd-status-dot cmd-status-dot--pending" />
        <span class="prompt" :class="{ 'prompt--busy': running }">$</span>
        <div class="input-wrap">
          <input
            ref="inputEl"
            v-model="input"
            type="text"
            class="input"
            spellcheck="false"
            autocomplete="off"
            autocapitalize="off"
            :placeholder="running ? 'tailing output …  (Ctrl+C / Esc to stop)' : ''"
            @keydown="onKeydown"
            @input="onInputEvent"
            @keyup="onInputSelectionChange"
            @click="onInputSelectionChange"
            @select="onInputSelectionChange"
            @focus="onInputSelectionChange"
          />
          <!-- 隐藏测量 span：与 input 完全同字体/字号，用于计算光标像素偏移 -->
          <span ref="measureEl" class="input-measure" aria-hidden="true" />
          <!-- 自定义方块光标，绝对定位，跟随输入位置移动 -->
          <span
            class="caret"
            :class="{ 'caret--hidden': running }"
            :style="{ transform: `translateX(${caretOffset}px)` }"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.terminal {
  --bg: #0b0f17;
  --bg-accent: #0f1422;
  --fg: #e2e8f0;
  --muted: #64748b;
  --green: #4ade80;
  --red: #f87171;
  --yellow: #fbbf24;
  --blue: #60a5fa;
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

/* 顶部"窗口栏" */
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

.cwd-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.35);
  color: rgba(226, 232, 240, 0.9);
  font-size: 11px;
  line-height: 1.2;
  min-width: 160px;
}

.cwd-pill--set {
  border-color: rgba(96, 165, 250, 0.28);
}

.cwd-pill--temp {
  border-color: rgba(251, 191, 36, 0.38);
}

.cwd-key {
  color: rgba(148, 163, 184, 0.9);
  letter-spacing: 1px;
  flex: none;
}

.cwd-input {
  width: 100%;
  min-width: 0;
  background: transparent;
  border: none;
  outline: none;
  color: #e2e8f0;
  font-family: inherit;
  font-size: 11px;
  padding: 0;
}

.cwd-input::placeholder {
  color: rgba(148, 163, 184, 0.55);
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

/* 终端正文 */
.terminal-body {
  flex: 1;
  padding: 14px 16px 18px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.55;
  background-image:
    radial-gradient(ellipse at top, rgba(74, 222, 128, 0.04) 0%, transparent 55%),
    repeating-linear-gradient(
      0deg,
      rgba(255, 255, 255, 0.012) 0px,
      rgba(255, 255, 255, 0.012) 1px,
      transparent 1px,
      transparent 3px
    );
  scroll-behavior: smooth;
}
.terminal-body::-webkit-scrollbar { width: 8px; }
.terminal-body::-webkit-scrollbar-thumb {
  background: #1f2937;
  border-radius: 4px;
}
.terminal-body::-webkit-scrollbar-track { background: transparent; }

.line {
  white-space: pre-wrap;
  word-break: break-all;
}
.line--cmd {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #e2e8f0;
  margin-top: 2px;
}
.cmd-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: none;
  cursor: help;
}
.cmd-status-dot--pending {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.7);
  box-sizing: border-box;
  cursor: default;
}
.cmd-status-dot--success {
  background: #22c55e;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.18);
}
.cmd-status-dot--error {
  background: #ef4444;
  box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.18);
}
.line--stdout { color: #cbd5e1; }
.line--stderr { color: var(--red); }
.line--hint {
  color: var(--muted);
  font-style: italic;
}
.line--meta {
  color: var(--blue);
  opacity: 0.85;
}

.prompt {
  display: inline-block;
  color: var(--green);
  margin-right: 10px;
  font-weight: 600;
  text-shadow: 0 0 10px rgba(74, 222, 128, 0.45);
}
.prompt--busy {
  color: var(--yellow);
  text-shadow: 0 0 10px rgba(251, 191, 36, 0.5);
  animation: pulse 1.2s ease-in-out infinite;
}
.cmd-text { color: #f1f5f9; }

/* 下发中指示 */
.line--dispatching {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #94a3b8;
  font-style: italic;
  padding: 2px 0;
}
.dispatch-spinner {
  display: inline-flex;
  gap: 4px;
  align-items: center;
}
.spinner-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #fbbf24;
  box-shadow: 0 0 6px rgba(251, 191, 36, 0.55);
  animation: dot-bounce 1s ease-in-out infinite;
}
.spinner-dot:nth-child(2) { animation-delay: 0.15s; }
.spinner-dot:nth-child(3) { animation-delay: 0.3s; }
@keyframes dot-bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.45; }
  40% { transform: translateY(-3px); opacity: 1; }
}
.dispatch-text {
  font-size: 12.5px;
  letter-spacing: 0.5px;
}

/* 当前输入行 */
.line--input {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 4px;
}
.input-wrap {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  min-height: 1.55em;
}
.input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #f1f5f9;
  font-family: inherit;
  font-size: inherit;
  caret-color: transparent; /* 用自定义 caret */
  padding: 0;
  /* 让自定义 caret 浮在 input 上方不影响点击：input 保持在下层 */
  position: relative;
  z-index: 1;
}
.input::placeholder { color: #475569; }
.input:disabled { opacity: 0.85; }

/* 隐藏的测量元素：与 input 完全同字体/字号/字距，不占布局空间 */
.input-measure {
  position: absolute;
  left: 0;
  top: 0;
  visibility: hidden;
  pointer-events: none;
  white-space: pre;
  font-family: inherit;
  font-size: inherit;
  letter-spacing: inherit;
  padding: 0;
}

.caret {
  position: absolute;
  left: 0;
  top: 50%;
  margin-top: -8px;
  width: 2px;
  height: 16px;
  background: var(--green);
  border-radius: 1px;
  box-shadow: 0 0 8px rgba(74, 222, 128, 0.7);
  animation: blink 1.05s steps(2, start) infinite;
  pointer-events: none;
  z-index: 2;
  transition: transform 60ms linear;
}
.caret--hidden { visibility: hidden; }
@keyframes blink {
  to { opacity: 0; }
}
</style>
