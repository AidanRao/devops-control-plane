<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import {
  createTerminalSession,
  deleteTerminalSession,
  listTerminalSessions,
} from '@/api/terminalSessions'
import TerminalConsole from './TerminalConsole.vue'

const props = defineProps<{
  deviceId: string
  banner?: string
  cpuPercent?: number | null
  memPercent?: number | null
  memUsed?: number | null
  memTotal?: number | null
}>()

type SessionMeta = {
  id: string
  title: string
  status: string
}

const sessions = ref<SessionMeta[]>([])
const activeSessionId = ref<string>('default')
const consoleRefs = ref<Record<string, InstanceType<typeof TerminalConsole> | null>>({})
const showRail = computed(() => sessions.value.length > 1)
const loadingSessions = ref(false)
const creatingSession = ref(false)

const MAX_SESSIONS = 8

function activeSessionKey() {
  return `terminal-active-session:${props.deviceId}`
}

function defaultTitle(idx: number) {
  return idx === 1 ? 'zsh' : `zsh-${idx}`
}

function persistActiveSession() {
  try {
    localStorage.setItem(activeSessionKey(), activeSessionId.value)
  } catch {
    // ignore
  }
}

function hydrateSessionMetas(items: Array<{ sessionId: string; title: string; status: string }>) {
  sessions.value = items.map((item) => ({
    id: item.sessionId,
    title: item.title,
    status: item.status,
  }))
}

async function loadSessions() {
  loadingSessions.value = true
  try {
    const { items } = await listTerminalSessions(props.deviceId)
    if (!items.length) {
      await createSession()
      return
    }
    hydrateSessionMetas(items)
    const stored = localStorage.getItem(activeSessionKey())
    activeSessionId.value = stored && sessions.value.some((s) => s.id === stored)
      ? stored
      : sessions.value[0].id
    persistActiveSession()
  } finally {
    loadingSessions.value = false
  }
}

function setConsoleRef(id: string, el: InstanceType<typeof TerminalConsole> | null) {
  consoleRefs.value[id] = el
}

function focusActive() {
  nextTick(() => {
    consoleRefs.value[activeSessionId.value]?.focus()
  })
}

function setActive(id: string) {
  if (activeSessionId.value === id) return
  activeSessionId.value = id
  persistActiveSession()
  focusActive()
}

async function createSession() {
  if (sessions.value.length >= MAX_SESSIONS || creatingSession.value) return
  creatingSession.value = true
  try {
    const title = defaultTitle(sessions.value.length + 1)
    const { session } = await createTerminalSession(props.deviceId, {
      shell: '/bin/zsh',
      cwd: '',
      cols: 120,
      rows: 32,
      title,
    })
    sessions.value = [
      ...sessions.value,
      {
        id: session.sessionId,
        title: session.title,
        status: session.status,
      },
    ]
    activeSessionId.value = session.sessionId
    persistActiveSession()
    focusActive()
  } finally {
    creatingSession.value = false
  }
}

async function removeSession(id: string) {
  if (sessions.value.length <= 1) return
  const idx = sessions.value.findIndex((s) => s.id === id)
  if (idx === -1) return
  await deleteTerminalSession(props.deviceId, id)
  const nextSessions = sessions.value.filter((s) => s.id !== id)
  delete consoleRefs.value[id]
  sessions.value = nextSessions

  if (activeSessionId.value === id) {
    const fallback = nextSessions[Math.min(idx, nextSessions.length - 1)] ?? nextSessions[idx - 1]
    activeSessionId.value = fallback?.id ?? nextSessions[0]?.id ?? ''
  }

  persistActiveSession()
  focusActive()
}

function fillInput(text: string) {
  consoleRefs.value[activeSessionId.value]?.fillInput(text)
}

function onSessionState(payload: { sessionId: string; title: string; status: string }) {
  const session = sessions.value.find((item) => item.id === payload.sessionId)
  if (!session) return
  session.title = payload.title || session.title
  session.status = payload.status || session.status
}

defineExpose({
  focus: focusActive,
  fillInput,
})

onMounted(() => {
  void loadSessions()
})

watch(
  () => props.deviceId,
  () => {
    sessions.value = []
    activeSessionId.value = ''
    consoleRefs.value = {}
    void loadSessions()
  },
)
</script>

<template>
  <div class="terminal-sessions">
    <TerminalConsole
      v-for="s in sessions"
      :key="s.id"
      :ref="(el) => setConsoleRef(s.id, el as any)"
      v-show="s.id === activeSessionId"
      :device-id="deviceId"
      :session-id="s.id"
      :show-rail="showRail"
      :can-create-session="sessions.length < MAX_SESSIONS && !loadingSessions && !creatingSession"
      :cpu-percent="cpuPercent"
      :mem-percent="memPercent"
      :mem-used="memUsed"
      :mem-total="memTotal"
      :banner="banner"
      @create-session="createSession"
      @session-state="onSessionState"
    >
      <template #rail>
        <div v-if="showRail" class="rail-list">
          <div
            v-for="ss in sessions"
            :key="ss.id"
            class="rail-item"
            :class="{ 'is-active': ss.id === activeSessionId }"
          >
            <button
              type="button"
              class="rail-tab"
              :title="ss.title"
              @click="setActive(ss.id)"
            >
              {{ ss.title }}
            </button>
            <button
              type="button"
              class="rail-remove"
              title="Close session"
              :disabled="sessions.length <= 1"
              @click.stop="removeSession(ss.id)"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M9 3.75h6a1.5 1.5 0 0 1 1.5 1.5V6h3a.75.75 0 0 1 0 1.5h-1.06l-.72 10.08A2.25 2.25 0 0 1 15.47 19.5H8.53a2.25 2.25 0 0 1-2.25-1.92L5.56 7.5H4.5a.75.75 0 0 1 0-1.5h3v-.75A1.5 1.5 0 0 1 9 3.75Zm6 2.25v-.75h-6V6h6Zm-7.94 1.5.71 9.97a.75.75 0 0 0 .75.64h6.94a.75.75 0 0 0 .75-.64l.71-9.97H7.06Zm2.69 2.25a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5a.75.75 0 0 1 .75-.75Zm4.5 0a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5a.75.75 0 0 1 .75-.75Z"
                  fill="currentColor"
                />
              </svg>
            </button>
          </div>
        </div>
      </template>
    </TerminalConsole>
  </div>
</template>

<style scoped>
.terminal-sessions {
  height: 100%;
}

.rail-list {
  display: flex;
  flex-direction: column;
  flex: 1;
  gap: 6px;
  overflow-y: auto;
  min-height: 0;
  padding-right: 2px;
}

.rail-list::after {
  content: '';
  flex: 1 1 auto;
  min-height: 12px;
  margin-top: 8px;
  border-top: 1px solid rgba(148, 163, 184, 0.08);
}

.rail-list::-webkit-scrollbar { width: 8px; }
.rail-list::-webkit-scrollbar-thumb {
  background: #1f2937;
  border-radius: 4px;
}
.rail-list::-webkit-scrollbar-track { background: transparent; }

.rail-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: transparent;
}

.rail-tab {
  flex: 1;
  min-width: 0;
  text-align: left;
  padding: 7px 6px 7px 8px;
  border: none;
  background: transparent;
  color: rgba(203, 213, 225, 0.92);
  cursor: pointer;
  font-family: 'JetBrains Mono Variable', 'SFMono-Regular', Menlo, Consolas, monospace;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rail-item:hover {
  background: rgba(30, 41, 59, 0.55);
  border-color: rgba(96, 165, 250, 0.22);
}

.rail-item.is-active {
  background: rgba(59, 130, 246, 0.18);
  border-color: rgba(96, 165, 250, 0.38);
  color: rgba(226, 232, 240, 0.98);
}

.rail-item.is-active .rail-tab {
  color: rgba(226, 232, 240, 0.98);
}

.rail-remove {
  width: 24px;
  height: 24px;
  flex: none;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: rgba(148, 163, 184, 0.82);
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
  transition:
    opacity 120ms ease,
    background-color 120ms ease,
    color 120ms ease;
}

.rail-remove svg {
  width: 14px;
  height: 14px;
  display: block;
  margin: 0 auto;
}

.rail-item:hover .rail-remove,
.rail-item.is-active .rail-remove {
  opacity: 1;
  pointer-events: auto;
}

.rail-remove:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.14);
  color: rgba(254, 202, 202, 0.98);
}

.rail-remove:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
</style>
