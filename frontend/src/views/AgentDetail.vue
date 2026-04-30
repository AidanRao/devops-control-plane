<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElButton, ElDialog, ElIcon, ElInput, ElMessage, ElTooltip } from 'element-plus'
import { ArrowLeft, CopyDocument, EditPen } from '@element-plus/icons-vue'
import TerminalSessions from '@/components/TerminalSessions.vue'
import AgentDetailShelf from '@/components/agent-detail/AgentDetailShelf.vue'
import {
  fetchAgentCommands,
  fetchAgents,
  updateAgentRemark,
  type AgentCommandHistoryItem,
  type AgentInfo,
} from '@/api/agents'

const props = defineProps<{ deviceId: string }>()

const router = useRouter()
const agent = ref<AgentInfo | null>(null)
const history = ref<AgentCommandHistoryItem[]>([])
const loadingHistory = ref(false)
const terminalRef = ref<InstanceType<typeof TerminalSessions> | null>(null)
let historyTimer: number | undefined
let agentTimer: number | undefined
const POLL_INTERVAL_MS = 15_000

const remarkDialogVisible = ref(false)
const remarkDraft = ref('')
const savingRemark = ref(false)

async function loadAgent() {
  const list = await fetchAgents()
  agent.value = list.find((a) => a.device_id === props.deviceId) ?? null
}

async function loadHistory() {
  loadingHistory.value = true
  try {
    history.value = await fetchAgentCommands(props.deviceId)
  } finally {
    loadingHistory.value = false
  }
}

function normalizedRemark(value?: string | null) {
  return (value ?? '').trim()
}

const displayName = computed(() => {
  const remark = normalizedRemark(agent.value?.remark)
  return remark || '未命名服务器'
})

const deviceIdShort = computed(() => {
  const id = props.deviceId
  if (id.length <= 18) return id
  return `${id.slice(0, 8)}…${id.slice(-6)}`
})

function openRemarkDialog() {
  remarkDraft.value = normalizedRemark(agent.value?.remark)
  remarkDialogVisible.value = true
}

async function saveRemark() {
  if (savingRemark.value) return
  savingRemark.value = true
  try {
    const next = remarkDraft.value.trim()
    await updateAgentRemark(props.deviceId, next)
    if (!agent.value) {
      agent.value = {
        device_id: props.deviceId,
        online: false,
        hasDeviceToken: false,
        lastHeartbeat: null,
        remark: next,
      }
    } else {
      agent.value.remark = next
    }
    ElMessage.success('备注已更新')
    remarkDialogVisible.value = false
  } catch (e) {
    ElMessage.error((e as Error).message || '更新备注失败')
  } finally {
    savingRemark.value = false
  }
}

async function copyDeviceId() {
  try {
    await navigator.clipboard.writeText(props.deviceId)
    ElMessage.success('已复制设备 ID')
  } catch {
    // 简易兜底：不阻塞交互
    ElMessage.warning('复制失败，请手动复制')
  }
}

function goBack() {
  router.push({ name: 'dashboard' })
}

function replayCommand(item: AgentCommandHistoryItem) {
  terminalRef.value?.fillInput(item.command)
}

function applyCommand(command: string) {
  terminalRef.value?.fillInput(command)
}

onMounted(() => {
  loadAgent()
  loadHistory()
  historyTimer = window.setInterval(loadHistory, POLL_INTERVAL_MS)
  // 定期刷新 agent 列表以拿到最新心跳/metrics（当前后端在 /api/agents 聚合）.
  agentTimer = window.setInterval(loadAgent, POLL_INTERVAL_MS)
})

onUnmounted(() => {
  if (historyTimer !== undefined) window.clearInterval(historyTimer)
  if (agentTimer !== undefined) window.clearInterval(agentTimer)
})

watch(
  () => props.deviceId,
  () => {
    loadAgent()
    loadHistory()
  },
)
</script>

<template>
  <div class="detail">
    <header class="detail-header">
      <button class="back-btn" @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        <span>返回</span>
      </button>

      <div class="title-block">
        <div class="name-row">
          <h1 class="name-title">{{ displayName }}</h1>
          <el-button
            size="small"
            text
            :icon="EditPen"
            class="icon-btn"
            @click="openRemarkDialog"
          >
            编辑
          </el-button>
        </div>

        <div class="id-row">
          <span class="id-label">device</span>
          <el-tooltip :content="props.deviceId" placement="top">
            <span class="id-value">{{ deviceIdShort }}</span>
          </el-tooltip>
          <el-button size="small" text :icon="CopyDocument" class="icon-btn" @click="copyDeviceId">
            复制
          </el-button>
        </div>
      </div>
    </header>

    <main class="detail-main">
      <AgentDetailShelf
        :device-id="deviceId"
        :history="history"
        :loading-history="loadingHistory"
        @refresh-history="loadHistory"
        @replay-command="replayCommand"
        @apply-command="applyCommand"
        @edit-remark="openRemarkDialog"
      />

      <section class="console">
        <TerminalSessions
          ref="terminalRef"
          :device-id="deviceId"
          :cpu-percent="agent?.cpuPercent ?? null"
          :mem-percent="agent?.memPercent ?? null"
          :mem-used="agent?.memUsed ?? null"
          :mem-total="agent?.memTotal ?? null"
          banner="DevOps Control Plane · interactive shell · type any command and press ↵"
        />
      </section>
    </main>

    <el-dialog v-model="remarkDialogVisible" title="编辑服务器名称/备注" width="520px" destroy-on-close>
      <div class="remark-dialog-body">
        <el-input
          v-model="remarkDraft"
          maxlength="80"
          show-word-limit
          clearable
          placeholder="例如：DB-Master / Web-Node-1"
        />
        <div class="remark-hint">
          留空会显示为“未命名服务器”。设备 ID 会作为副标题保留。
        </div>
      </div>
      <template #footer>
        <div class="dialog-actions">
          <el-button @click="remarkDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="savingRemark" @click="saveRemark">保存</el-button>
        </div>
      </template>
    </el-dialog>
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

.detail-header {
  display: grid;
  grid-template-columns: auto 1fr;
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
  min-width: 0;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.name-title {
  margin: 0;
  font-family: 'IBM Plex Sans', sans-serif;
  font-weight: 650;
  font-size: 24px;
  color: #0f172a;
  line-height: 1.2;
  letter-spacing: -0.2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.icon-btn {
  --el-button-text-color: #64748b;
  --el-button-hover-text-color: #2563eb;
}
.id-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 2px;
  min-width: 0;
}
.id-label {
  font-family: 'JetBrains Mono Variable', monospace;
  font-size: 10px;
  letter-spacing: 1.6px;
  text-transform: uppercase;
  color: #94a3b8;
}
.id-value {
  font-family: 'JetBrains Mono Variable', monospace;
  font-size: 12px;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.remark-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.remark-hint {
  font-size: 12px;
  color: #94a3b8;
}
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.detail-main {
  flex: 1;
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 16px;
  min-height: 0;
}

.console {
  min-height: 0;
  display: flex;
  flex-direction: column;
}
</style>
