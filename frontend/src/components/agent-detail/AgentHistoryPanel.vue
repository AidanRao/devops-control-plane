<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  ElButton,
  ElEmpty,
  ElOption,
  ElPagination,
  ElScrollbar,
  ElSelect,
  ElInput,
  ElTooltip,
  ElMessage,
} from 'element-plus'
import { CopyDocument, Refresh } from '@element-plus/icons-vue'
import type { AgentCommandHistoryItem } from '@/api/agents'
import { formatRelative } from '@/utils/time'

type ExitCodeFilter = 'all' | 'success' | 'failed'
type QuickRange = 'all' | '15m' | '1h' | 'today' | '7d'

const props = defineProps<{
  history: AgentCommandHistoryItem[]
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'replay-command', item: AgentCommandHistoryItem): void
}>()

const commandKeyword = ref('')
const exitCodeFilter = ref<ExitCodeFilter>('all')
const quickRange = ref<QuickRange>('all')
const currentPage = ref(1)
const pageSize = 10
const tick = ref(0)
let timer: number | undefined

function parseHistoryTime(input?: string | null): number {
  if (!input) return Number.NaN
  const value = String(input).trim()
  if (!value) return Number.NaN
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value)
  return new Date(hasTimezone ? value : `${value}Z`).getTime()
}

function shortCommand(cmd: string, max = 80) {
  if (cmd.length <= max) return cmd
  return cmd.slice(0, max - 1) + '…'
}

function statusMeta(item: AgentCommandHistoryItem): {
  dotClass: string
  tooltip: string
} {
  const s = item.status
  if (s === 'Finished') {
    const code = item.exitCode ?? 0
    return {
      dotClass: code === 0 ? 'history-status-dot--success' : 'history-status-dot--error',
      tooltip: `exit code: ${code}`,
    }
  }
  if (s === 'Running') return { dotClass: 'history-status-dot--running', tooltip: 'running' }
  if (s === 'Dispatching' || s === 'Pending') {
    return { dotClass: 'history-status-dot--pending', tooltip: s.toLowerCase() }
  }
  if (s === 'Succeeded') return { dotClass: 'history-status-dot--success', tooltip: 'succeeded' }
  if (s === 'Failed') return { dotClass: 'history-status-dot--error', tooltip: 'failed' }
  return { dotClass: 'history-status-dot--pending', tooltip: s.toLowerCase() }
}

const filteredHistory = computed(() => {
  void tick.value
  const keyword = commandKeyword.value.trim().toLowerCase()
  const now = Date.now()
  let startMs: number | null = null
  let endMs: number | null = null

  if (quickRange.value === '15m') {
    startMs = now - 15 * 60 * 1000
    endMs = now
  } else if (quickRange.value === '1h') {
    startMs = now - 60 * 60 * 1000
    endMs = now
  } else if (quickRange.value === 'today') {
    const start = new Date()
    start.setHours(0, 0, 0, 0)
    startMs = start.getTime()
    endMs = now
  } else if (quickRange.value === '7d') {
    startMs = now - 7 * 24 * 60 * 60 * 1000
    endMs = now
  }

  return props.history.filter((item) => {
    if (keyword && !item.command.toLowerCase().includes(keyword)) return false

    const isSuccess =
      (item.status === 'Finished' || item.status === 'Succeeded') &&
      (item.exitCode ?? 0) === 0
    const isFailed =
      item.status === 'Failed' ||
      ((item.status === 'Finished' || item.status === 'Succeeded') &&
        item.exitCode !== undefined &&
        item.exitCode !== null &&
        item.exitCode !== 0)

    if (exitCodeFilter.value === 'success' && !isSuccess) return false
    if (exitCodeFilter.value === 'failed' && !isFailed) return false

    if (startMs !== null || endMs !== null) {
      const createdAtMs = parseHistoryTime(item.createdAt)
      if (Number.isNaN(createdAtMs)) return false
      if (startMs !== null && createdAtMs < startMs) return false
      if (endMs !== null && createdAtMs > endMs) return false
    }

    return true
  })
})

const paginatedHistory = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredHistory.value.slice(start, start + pageSize)
})

const hasActiveFilters = computed(() => {
  return (
    Boolean(commandKeyword.value.trim()) ||
    exitCodeFilter.value !== 'all' ||
    quickRange.value !== 'all'
  )
})

function resetFilters() {
  commandKeyword.value = ''
  exitCodeFilter.value = 'all'
  quickRange.value = 'all'
  currentPage.value = 1
}

function formatTime(iso?: string | null) {
  void tick.value
  return formatRelative(iso)
}

async function copyCommand(item: AgentCommandHistoryItem) {
  try {
    await navigator.clipboard.writeText(item.command)
    ElMessage.success('已复制指令')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

watch([commandKeyword, exitCodeFilter, quickRange], () => {
  currentPage.value = 1
})

watch(filteredHistory, () => {
  const maxPage = Math.max(1, Math.ceil(filteredHistory.value.length / pageSize))
  if (currentPage.value > maxPage) currentPage.value = maxPage
})

onMounted(() => {
  timer = window.setInterval(() => {
    tick.value++
  }, 1000)
})

onUnmounted(() => {
  if (timer !== undefined) window.clearInterval(timer)
})
</script>

<template>
  <div class="history-panel">
    <div class="history-filters">
      <div class="filters-row filters-row--search">
        <el-input
          v-model="commandKeyword"
          size="small"
          clearable
          placeholder="搜索指令"
          class="filter-search"
        />
      </div>
      <div class="filters-row filters-row--selects">
        <el-select v-model="quickRange" size="small" class="filter-compact">
          <el-option label="全部时间" value="all" />
          <el-option label="15 分钟" value="15m" />
          <el-option label="1 小时" value="1h" />
          <el-option label="今天" value="today" />
          <el-option label="7 天" value="7d" />
        </el-select>
        <el-select v-model="exitCodeFilter" size="small" class="filter-compact">
          <el-option label="全部状态" value="all" />
          <el-option label="成功(0)" value="success" />
          <el-option label="失败(非0)" value="failed" />
        </el-select>
        <el-button
          v-if="hasActiveFilters"
          size="small"
          text
          class="filter-reset"
          :icon="Refresh"
          @click="resetFilters"
        >
          重置
        </el-button>
      </div>
    </div>

    <el-scrollbar class="history-scroll">
      <div v-if="history.length === 0 && !loading" class="history-empty">
        <el-empty description="暂无历史命令" :image-size="54" />
      </div>

      <div v-else-if="filteredHistory.length === 0 && !loading" class="history-empty">
        <el-empty description="没有匹配结果" :image-size="54" />
      </div>

      <ul v-else class="history-list">
        <li
          v-for="item in paginatedHistory"
          :key="item.task_uuid"
          class="history-item"
          @click="emit('replay-command', item)"
        >
          <div class="history-item-main">
            <el-tooltip :content="statusMeta(item).tooltip" placement="top">
              <span class="history-status-dot" :class="statusMeta(item).dotClass" />
            </el-tooltip>
            <span class="prompt-mark">$</span>
            <span class="history-cmd" :title="item.command">
              {{ shortCommand(item.command) }}
            </span>
          </div>
          <div class="history-item-right">
            <span class="history-time">{{ formatTime(item.createdAt) }}</span>
            <div class="history-actions">
              <el-button
                size="small"
                text
                circle
                class="history-action-btn"
                :icon="CopyDocument"
                title="复制指令"
                @click.stop="copyCommand(item)"
              />
            </div>
          </div>
        </li>
      </ul>
    </el-scrollbar>

    <div v-if="filteredHistory.length > pageSize" class="history-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="filteredHistory.length"
        small
        background
        layout="prev, pager, next"
      />
    </div>
  </div>
</template>

<style scoped>
.history-panel {
  display: flex;
  flex-direction: column;
}

.history-filters {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 0 12px;
  border-bottom: 1px dashed #e2e8f0;
}

.filters-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-search {
  width: 100%;
}

.filter-compact {
  flex: 1 1 120px;
  min-width: 120px;
}

.filter-reset {
  padding-right: 0;
  margin-left: auto;
}

.history-scroll {
  max-height: 360px;
  padding-top: 10px;
}

.history-empty {
  padding-top: 24px;
  color: #94a3b8;
}

.history-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.history-item {
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  transition: background-color 0.15s, border-color 0.15s;
}

.history-item:hover {
  background: #f8fafc;
  border-color: #dbeafe;
}

.history-item + .history-item {
  margin-top: 6px;
}

.history-item-main {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
  font-family: 'JetBrains Mono Variable', monospace;
  font-size: 12.5px;
}

.history-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: none;
}

.history-status-dot--success {
  background: #22c55e;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.16);
}

.history-status-dot--error {
  background: #ef4444;
  box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.14);
}

.history-status-dot--running {
  background: #f59e0b;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.16);
}

.history-status-dot--pending {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.8);
  box-sizing: border-box;
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

.history-item-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: none;
}

.history-time {
  font-family: 'JetBrains Mono Variable', monospace;
  font-size: 11px;
  color: #94a3b8;
  white-space: nowrap;
}

.history-actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.history-item:hover .history-actions {
  opacity: 1;
}

.history-action-btn {
  --el-button-text-color: #64748b;
  --el-button-hover-text-color: #2563eb;
  --el-button-hover-bg-color: #eff6ff;
  width: 24px;
  height: 24px;
  padding: 0;
}

.history-pagination {
  display: flex;
  justify-content: center;
  padding-top: 12px;
  border-top: 1px dashed #e2e8f0;
  margin-top: 10px;
}
</style>
