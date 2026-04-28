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
  ElInput,
  ElMessage,
  type CheckboxValueType,
} from 'element-plus'
import { Check, Close, EditPen, Refresh } from '@element-plus/icons-vue'
import { useAgentStore } from '@/stores/agents'
import { formatRelative, heartbeatLevel } from '@/utils/time'
import type { AgentInfo } from '@/api/agents'

const store = useAgentStore()
const { agents, selected, loading, selectedCount, allSelected, indeterminate } = storeToRefs(store)

// 触发相对时间每秒刷新（不发请求，仅让模板重渲染）
const tick = ref(0)
let timer: number | undefined

const editingId = ref<string | null>(null)
const remarkDraft = ref('')
const savingId = ref<string | null>(null)

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

function normalizedRemark(value?: string | null) {
  return (value ?? '').trim()
}

function displayRemark(value?: string | null, max = 18) {
  const text = normalizedRemark(value)
  if (!text) return '-'
  if (text.length <= max) return text
  return text.slice(0, max - 1) + '…'
}

function startEditRemark(row: AgentInfo) {
  if (savingId.value) return
  editingId.value = row.device_id
  remarkDraft.value = normalizedRemark(row.remark)
}

function cancelEditRemark() {
  if (savingId.value) return
  editingId.value = null
  remarkDraft.value = ''
}

async function saveRemark(row: AgentInfo) {
  if (savingId.value) return
  const value = normalizedRemark(remarkDraft.value)
  if (value.length > 100) {
    ElMessage.warning('备注最多 100 字')
    return
  }

  savingId.value = row.device_id
  try {
    await store.updateRemark(row.device_id, value)
    editingId.value = null
    remarkDraft.value = ''
    ElMessage.success('备注已保存')
  } catch (e) {
    // Keep editor open so user can retry.
    ElMessage.error('保存失败，请重试')
  } finally {
    savingId.value = null
  }
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
      <template #empty>
        <el-empty v-if="!loading" description="暂无在线 Agent" :image-size="64" />
      </template>
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

      <el-table-column label="备注" min-width="220">
        <template #default="{ row }: { row: AgentInfo }">
          <div class="remark-cell">
            <template v-if="editingId === row.device_id">
              <el-input
                v-model="remarkDraft"
                size="small"
                maxlength="100"
                clearable
                placeholder="添加备注（最多 100 字）"
                class="remark-input"
                :disabled="savingId === row.device_id"
                @keyup.enter="saveRemark(row)"
                @keyup.esc="cancelEditRemark"
              />
              <el-button
                size="small"
                type="primary"
                :icon="Check"
                :loading="savingId === row.device_id"
                @click="saveRemark(row)"
              />
              <el-button size="small" :icon="Close" :disabled="savingId === row.device_id" @click="cancelEditRemark" />
            </template>

            <template v-else>
              <el-tooltip
                v-if="normalizedRemark(row.remark)"
                :content="normalizedRemark(row.remark)"
                placement="top"
                :disabled="normalizedRemark(row.remark).length <= 18"
              >
                <span class="remark-text" :class="normalizedRemark(row.remark) ? '' : 'remark-text--empty'">
                  {{ displayRemark(row.remark) }}
                </span>
              </el-tooltip>
              <span
                v-else
                class="remark-text remark-text--empty"
              >
                -
              </span>
              <el-button size="small" text :icon="EditPen" @click="startEditRemark(row)">编辑</el-button>
            </template>
          </div>
        </template>
      </el-table-column>
    </el-table>
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

.remark-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.remark-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: #334155;
}
.remark-text--empty {
  color: #94a3b8;
}
.remark-input {
  flex: 1;
  min-width: 0;
}
</style>
