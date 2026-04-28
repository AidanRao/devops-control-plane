<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElBadge,
  ElButton,
  ElEmpty,
  ElIcon,
  ElScrollbar,
  ElTag,
  ElTooltip,
} from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import TerminalConsole from '@/components/TerminalConsole.vue'
import { fetchAgents, fetchAgentCommands, type AgentCommandHistoryItem, type AgentInfo } from '@/api/agents'
import { formatRelative, heartbeatLevel } from '@/utils/time'

const props = defineProps<{ deviceId: string }>()

const router = useRouter()
const agent = ref<AgentInfo | null>(null)
const history = ref<AgentCommandHistoryItem[]>([])
const loadingHistory = ref(false)
const terminalRef = ref<InstanceType<typeof TerminalConsole> | null>(null)
const tick = ref(0)
let heartbeatTimer: number | undefined
let historyTimer: number | undefined

async function loadAgent() {
  const list = await fetchAgents()
  agent.value = list.find((a) => a.device_id === props.deviceId) ?? {
    device_id: props.deviceId,
    hasDeviceToken: false,
    lastHeartbeat: null,
  }
}

async function loadHistory() {
  loadingHistory.value = true
  try {
    history.value = await fetchAgentCommands(props.deviceId)
  } finally {
    loadingHistory.value = false
  }
}

function heartbeatDotClass(iso?: string | null) {
  return `dot-${heartbeatLevel(iso)}`
}

function statusTag(item: AgentCommandHistoryItem): {
  type: 'success' | 'warning' | 'danger' | 'info'
  label: string
} {
  const s = item.status
  if (s === 'Finished') {
    const code = item.exitCode ?? 0
    return code === 0
      ? { type: 'success', label: `exit ${code}` }
      : { type: 'danger', label: `exit ${code}` }
  }
  if (s === 'Running') return { type: 'warning', label: 'running' }
  if (s === 'Dispatching' || s === 'Pending')
    return { type: 'info', label: s.toLowerCase() }
  if (s === 'Succeeded') return { type: 'success', label: 'succeeded' }
  if (s === 'Failed') return { type: 'danger', label: 'failed' }
  return { type: 'info', label: s.toLowerCase() }
}

function shortCommand(cmd: string, max = 80) {
  if (cmd.length <= max) return cmd
  return cmd.slice(0, max - 1) + '…'
}

function replayCommand(item: AgentCommandHistoryItem) {
  terminalRef.value?.fillInput(item.command)
}

function goBack() {
  router.push({ name: 'dashboard' })
}

const statsText = computed(() => {
  const total = history.value.length
  const ok = history.value.filter(
    (x) => x.status === 'Finished' && (x.exitCode ?? 0) === 0,
  ).length
  const fail = total - ok
  return { total, ok, fail }
})

onMounted(() => {
  loadAgent()
  loadHistory()
  // 心跳相对时间每秒重算
  heartbeatTimer = window.setInterval(() => {
    tick.value++
  }, 1000)
  // 历史列表每 3s 自动刷新（设备执行时同步）
  historyTimer = window.setInterval(loadHistory, 3000)
})

onUnmounted(() => {
  if (heartbeatTimer !== undefined) window.clearInterval(heartbeatTimer)
  if (historyTimer !== undefined) window.clearInterval(historyTimer)
})

watch(
  () => props.deviceId,
  () => {
    loadAgent()
    loadHistory()
  },
)

// 命令执行完成后立即刷新一次历史
function onCommandFinished() {
  loadHistory()
}

function formatHeartbeat(iso?: string | null) {
  void tick.value
  return formatRelative(iso)
}
</script>

<template>
  <div class="detail">
    <!-- 顶栏 -->
    <header class="detail-header">
      <button class="back-btn" @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        <span>返回</span>
      </button>

      <div class="title-block">
        <div class="eyebrow">AGENT · CONSOLE</div>
        <h1 class="title">
          <span class="title-glyph">⌘</span>
          <span class="title-id">{{ deviceId }}</span>
        </h1>
      </div>

      <div class="meta-chips">
        <el-tooltip :content="agent?.hasDeviceToken ? 'DeviceToken 已配置' : 'DeviceToken 未配置'">
          <span class="chip">
            <span class="chip-dot" :class="agent?.hasDeviceToken ? 'dot-ok' : 'dot-missing'" />
            token
          </span>
        </el-tooltip>
        <span class="chip">
          <span class="chip-dot" :class="heartbeatDotClass(agent?.lastHeartbeat)" />
          {{ formatHeartbeat(agent?.lastHeartbeat) }}
        </span>
      </div>
    </header>

    <!-- 主区域：左历史 + 右终端 -->
    <main class="detail-main">
      <!-- 历史栏 -->
      <aside class="history">
        <div class="history-head">
          <div class="history-title">
            <span class="history-bullet">▘</span>
            <span>History</span>
            <el-badge :value="statsText.total" :max="999" class="history-count" />
          </div>
          <el-button
            :icon="Refresh"
            size="small"
            text
            :loading="loadingHistory"
            @click="loadHistory"
          />
        </div>

        <div class="history-stats">
          <span><i class="stat-dot stat-ok" />{{ statsText.ok }} ok</span>
          <span><i class="stat-dot stat-fail" />{{ statsText.fail }} other</span>
        </div>

        <el-scrollbar class="history-scroll">
          <div v-if="history.length === 0 && !loadingHistory" class="history-empty">
            <el-empty description="暂无历史命令" :image-size="54" />
          </div>

          <ul v-else class="history-list">
            <li
              v-for="item in history"
              :key="item.task_uuid"
              class="history-item"
              @click="replayCommand(item)"
            >
              <div class="history-item-head">
                <span class="prompt-mark">$</span>
                <span class="history-cmd" :title="item.command">
                  {{ shortCommand(item.command) }}
                </span>
              </div>
              <div class="history-item-foot">
                <el-tag :type="statusTag(item).type" size="small" effect="dark">
                  {{ statusTag(item).label }}
                </el-tag>
                <span class="history-time">{{ formatHeartbeat(item.createdAt) }}</span>
              </div>
            </li>
          </ul>
        </el-scrollbar>
      </aside>

      <!-- 终端 -->
      <section class="console">
        <TerminalConsole
          ref="terminalRef"
          :device-id="deviceId"
          banner="DevOps Control Plane · interactive shell · type any command and press ↵"
          @command-finished="onCommandFinished"
        />
      </section>
    </main>
  </div>
</template>

<style scoped>
.detail {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  padding: 20px 24px 24px;
  box-sizing: border-box;
  gap: 16px;
}

/* ========= 顶栏 ========= */
.detail-header {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 18px;
}
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px 6px 8px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  color: #334155;
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}
.back-btn:hover {
  border-color: #2563eb;
  color: #2563eb;
}

.title-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.eyebrow {
  font-family: 'JetBrains Mono Variable', monospace;
  font-size: 11px;
  letter-spacing: 2.2px;
  color: #94a3b8;
}
.title {
  margin: 0;
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-family: 'IBM Plex Sans', sans-serif;
  font-weight: 600;
  font-size: 22px;
  color: #0f172a;
  line-height: 1.2;
}
.title-glyph {
  color: #2563eb;
  font-family: 'JetBrains Mono Variable', monospace;
}
.title-id {
  font-family: 'JetBrains Mono Variable', monospace;
  letter-spacing: -0.5px;
  font-weight: 500;
  font-size: 20px;
  color: #1e293b;
  padding-bottom: 1px;
  border-bottom: 2px solid #bfdbfe;
}

.meta-chips {
  display: flex;
  gap: 8px;
  align-items: center;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: #ffffff;
  font-family: 'JetBrains Mono Variable', monospace;
  font-size: 11px;
  color: #475569;
  letter-spacing: 0.3px;
}
.chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #9ca3af;
}
.dot-ok { background: #22c55e; box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.18); }
.dot-missing { background: #9ca3af; }
.dot-green { background: #22c55e; box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.18); }
.dot-yellow { background: #f59e0b; box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.2); }
.dot-red { background: #ef4444; box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.18); }

/* ========= 主区域 ========= */
.detail-main {
  flex: 1;
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
  min-height: 0; /* 让 grid 子项能压缩 */
}

/* 历史栏 */
.history {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px 6px 10px 14px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-right: 8px;
  margin-bottom: 6px;
}
.history-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'IBM Plex Sans', sans-serif;
  font-weight: 600;
  font-size: 13px;
  color: #0f172a;
  letter-spacing: 0.5px;
}
.history-bullet {
  color: #2563eb;
  font-family: 'JetBrains Mono Variable', monospace;
}
.history-count :deep(.el-badge__content) {
  background: #e0e7ff;
  color: #3730a3;
  border: none;
}
.history-stats {
  display: flex;
  gap: 16px;
  font-family: 'JetBrains Mono Variable', monospace;
  font-size: 11px;
  color: #64748b;
  padding: 2px 2px 10px 2px;
  border-bottom: 1px dashed #e2e8f0;
  margin-right: 8px;
  margin-bottom: 8px;
}
.stat-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 5px;
  transform: translateY(-1px);
}
.stat-ok { background: #22c55e; }
.stat-fail { background: #ef4444; }

.history-scroll {
  flex: 1;
  min-height: 0;
}
.history-empty {
  padding-top: 30px;
  color: #94a3b8;
}
.history-list {
  list-style: none;
  margin: 0;
  padding: 0 8px 6px 0;
}
.history-item {
  padding: 8px 10px;
  border-radius: 6px;
  border-left: 2px solid transparent;
  cursor: pointer;
  transition: background-color 0.15s, border-color 0.15s;
}
.history-item:hover {
  background: #f1f5f9;
  border-left-color: #2563eb;
}
.history-item-head {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-family: 'JetBrains Mono Variable', monospace;
  font-size: 12.5px;
}
.prompt-mark {
  color: #2563eb;
  font-weight: 600;
}
.history-cmd {
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.history-item-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
  padding-left: 14px;
}
.history-time {
  font-family: 'JetBrains Mono Variable', monospace;
  font-size: 11px;
  color: #94a3b8;
}

/* 终端容器 */
.console {
  min-height: 0;
  display: flex;
  flex-direction: column;
}
</style>
