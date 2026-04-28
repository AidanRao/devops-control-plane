<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import {
  ElTable,
  ElTableColumn,
  ElCheckbox,
  ElButton,
  ElTag,
  ElEmpty,
  ElTooltip,
  type CheckboxValueType,
} from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useAgentStore } from '@/stores/agents'
import { formatRelative, heartbeatLevel } from '@/utils/time'
import type { AgentInfo } from '@/api/agents'

const store = useAgentStore()
const { agents, selected, loading, selectedCount, allSelected, indeterminate } = storeToRefs(store)

// 触发相对时间每秒刷新（不发请求，仅让模板重渲染）
const tick = ref(0)
let timer: number | undefined

async function refresh() {
  await store.refresh()
}

onMounted(() => {
  refresh()
  timer = window.setInterval(() => {
    tick.value++
  }, 1000)
})

onUnmounted(() => {
  if (timer !== undefined) window.clearInterval(timer)
})

function isRowSelected(row: AgentInfo) {
  return selected.value.has(row.device_id)
}

function rowClassName({ row }: { row: AgentInfo }) {
  return isRowSelected(row) ? 'agent-row-selected' : ''
}

function onRowToggle(row: AgentInfo, checked: CheckboxValueType) {
  store.toggle(row.device_id, Boolean(checked))
}

function onToggleAll(checked: CheckboxValueType) {
  store.toggleAll(Boolean(checked))
}

function tokenTooltip(row: AgentInfo) {
  return row.hasDeviceToken ? 'DeviceToken 已配置' : 'DeviceToken 未配置'
}

function heartbeatTagType(iso?: string | null): 'success' | 'warning' | 'danger' {
  const level = heartbeatLevel(iso)
  if (level === 'green') return 'success'
  if (level === 'yellow') return 'warning'
  return 'danger'
}

// 依赖 tick 触发重渲染，显式消费一下避免被 TS 警告
function formatHeartbeat(iso?: string | null) {
  void tick.value
  return formatRelative(iso)
}
</script>

<template>
  <div class="agent-table">
    <div class="agent-toolbar">
      <div class="agent-toolbar-left">
        <el-checkbox
          :model-value="allSelected"
          :indeterminate="indeterminate"
          :disabled="agents.length === 0"
          @change="onToggleAll"
        >
          全选
        </el-checkbox>
        <span class="selected-count">已选择 {{ selectedCount }} / {{ agents.length }} 台</span>
      </div>
      <div class="agent-toolbar-right">
        <el-button size="small" :icon="Refresh" :loading="loading" @click="refresh">
          刷新
        </el-button>
      </div>
    </div>

    <el-table
      :data="agents"
      size="small"
      stripe
      border
      :row-class-name="rowClassName"
      empty-text=" "
    >
      <el-table-column width="56" align="center">
        <template #header>
          <el-checkbox
            :model-value="allSelected"
            :indeterminate="indeterminate"
            :disabled="agents.length === 0"
            @change="onToggleAll"
          />
        </template>
        <template #default="{ row }: { row: AgentInfo }">
          <el-checkbox
            :model-value="isRowSelected(row)"
            @change="(v: CheckboxValueType) => onRowToggle(row, v)"
          />
        </template>
      </el-table-column>

      <el-table-column label="设备 ID" min-width="240">
        <template #default="{ row }: { row: AgentInfo }">
          <div class="device-cell">
            <el-tooltip :content="tokenTooltip(row)" placement="top">
              <span
                class="token-dot"
                :class="row.hasDeviceToken ? 'token-dot--ok' : 'token-dot--missing'"
              />
            </el-tooltip>
            <router-link
              :to="{ name: 'agent-detail', params: { deviceId: row.device_id } }"
              class="device-id-link"
            >
              {{ row.device_id }}
            </router-link>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="最近心跳" width="160">
        <template #default="{ row }: { row: AgentInfo }">
          <el-tag :type="heartbeatTagType(row.lastHeartbeat)" size="small" effect="dark">
            {{ formatHeartbeat(row.lastHeartbeat) }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && agents.length === 0" description="暂无在线 Agent" :image-size="64" />
  </div>
</template>

<style scoped>
.agent-table {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px 16px 16px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.agent-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.agent-toolbar-left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.selected-count {
  font-size: 12px;
  color: #64748b;
}
.device-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.token-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: none;
}
.token-dot--ok {
  background: #22c55e;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.18);
}
.token-dot--missing {
  background: #9ca3af;
  box-shadow: 0 0 0 2px rgba(156, 163, 175, 0.2);
}
.device-id {
  font-family: 'JetBrains Mono', 'SFMono-Regular', Menlo, Consolas, monospace;
  font-size: 13px;
  color: #1f2937;
}
.device-id-link {
  font-family: 'JetBrains Mono', 'SFMono-Regular', Menlo, Consolas, monospace;
  font-size: 13px;
  color: #1f2937;
  text-decoration: none;
  border-bottom: 1px dashed transparent;
  transition: color 0.15s, border-color 0.15s;
}
.device-id-link:hover {
  color: #2563eb;
  border-bottom-color: #2563eb;
}

/* 选中行：浅蓝色高亮 */
.agent-table :deep(.agent-row-selected td.el-table__cell) {
  background: #eff6ff !important;
}
</style>
