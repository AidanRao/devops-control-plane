<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElButton, ElIcon } from 'element-plus'
import { ArrowDown, Clock, Plus, Refresh, Star } from '@element-plus/icons-vue'
import AgentHistoryPanel from './AgentHistoryPanel.vue'
import CommonCommandsPanel from './CommonCommandsPanel.vue'
import { useCommonCommands, type CommonCommandPresetInput } from '@/composables/useCommonCommands'
import type { AgentCommandHistoryItem } from '@/api/agents'

const props = defineProps<{
  deviceId: string
  history: AgentCommandHistoryItem[]
  loadingHistory: boolean
}>()

const emit = defineEmits<{
  (e: 'refresh-history'): void
  (e: 'replay-command', item: AgentCommandHistoryItem): void
  (e: 'apply-command', command: string): void
  (e: 'edit-remark'): void
}>()

type ShelfSection = 'history' | 'presets' | null
type CommonCommandsPanelExpose = {
  openCreate: () => void
}

const activeSection = ref<ShelfSection>('history')
const { commonCommands, savePreset, removePreset } = useCommonCommands(() => props.deviceId)
const presetsPanelRef = ref<CommonCommandsPanelExpose | null>(null)

const historySummaryText = computed(() => `${props.history.length} records`)
const presetSummaryText = computed(() => `${commonCommands.value.length} presets`)

function toggleSection(section: Exclude<ShelfSection, null>) {
  activeSection.value = activeSection.value === section ? null : section
}

function applyPreset(command: string) {
  emit('apply-command', command)
}

function openCreatePreset() {
  activeSection.value = 'presets'
  presetsPanelRef.value?.openCreate()
}
</script>

<template>
  <aside class="shelf">
    <div class="shelf-sections">
      <section class="shelf-section" :class="{ 'is-active': activeSection === 'history' }">
        <button class="shelf-trigger" type="button" @click="toggleSection('history')">
          <div class="shelf-trigger-left">
            <span class="trigger-icon trigger-icon--history" aria-hidden="true">
              <el-icon><Clock /></el-icon>
            </span>
            <div class="trigger-copy">
              <div class="trigger-title">历史记录</div>
            </div>
          </div>
          <div class="shelf-trigger-right">
            <span class="trigger-meta">{{ historySummaryText }}</span>
            <el-button
              size="small"
              text
              circle
              class="trigger-action"
              :icon="Refresh"
              :loading="loadingHistory"
              @click.stop="emit('refresh-history')"
            />
            <el-icon class="trigger-chevron" :class="{ 'is-open': activeSection === 'history' }">
              <ArrowDown />
            </el-icon>
          </div>
        </button>

        <div v-if="activeSection === 'history'" class="shelf-panel">
          <AgentHistoryPanel
            :history="history"
            :loading="loadingHistory"
            @replay-command="emit('replay-command', $event)"
          />
        </div>
      </section>

      <section class="shelf-section" :class="{ 'is-active': activeSection === 'presets' }">
        <button class="shelf-trigger" type="button" @click="toggleSection('presets')">
          <div class="shelf-trigger-left">
            <span class="trigger-icon trigger-icon--preset" aria-hidden="true">
              <el-icon><Star /></el-icon>
            </span>
            <div class="trigger-copy">
              <div class="trigger-title">常用指令</div>
            </div>
          </div>
          <div class="shelf-trigger-right">
            <span class="trigger-meta">{{ presetSummaryText }}</span>
            <el-button
              size="small"
              text
              circle
              class="trigger-action"
              :icon="Plus"
              @click.stop="openCreatePreset"
            />
            <el-icon class="trigger-chevron" :class="{ 'is-open': activeSection === 'presets' }">
              <ArrowDown />
            </el-icon>
          </div>
        </button>

        <div v-if="activeSection === 'presets'" class="shelf-panel">
          <CommonCommandsPanel
            ref="presetsPanelRef"
            :commands="commonCommands"
            @save-preset="(payload: CommonCommandPresetInput) => savePreset(payload)"
            @remove-preset="removePreset"
            @apply-preset="applyPreset($event.command)"
          />
        </div>
      </section>
    </div>
  </aside>
</template>

<style scoped>
.shelf {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.98) 100%);
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.04),
    0 10px 24px rgba(15, 23, 42, 0.04);
}

.shelf-sections {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}

.shelf-section {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #ffffff;
  overflow: hidden;
  transition: box-shadow 0.2s, border-color 0.2s;
}

.shelf-section.is-active {
  border-color: #c7d2fe;
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.06);
}

.shelf-trigger {
  width: 100%;
  border: none;
  background: transparent;
  padding: 12px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  text-align: left;
  cursor: pointer;
}

.shelf-trigger-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.trigger-icon {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.trigger-icon--history {
  color: #1d4ed8;
  background: rgba(37, 99, 235, 0.12);
}

.trigger-icon--preset {
  color: #6d28d9;
  background: rgba(124, 58, 237, 0.12);
}

.trigger-copy { min-width: 0; }

.trigger-title {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.shelf-trigger-right {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: 12px;
}

.trigger-meta {
  font-family: 'JetBrains Mono Variable', monospace;
  font-size: 11px;
  color: #64748b;
}

.trigger-action {
  --el-button-text-color: #64748b;
  --el-button-hover-text-color: #2563eb;
  --el-button-hover-bg-color: #eff6ff;
  width: 24px;
  height: 24px;
  margin-right: -2px;
}

.trigger-chevron {
  color: #94a3b8;
  transition: transform 0.18s ease;
}

.trigger-chevron.is-open {
  transform: rotate(180deg);
}

.shelf-panel {
  border-top: 1px solid #eef2f7;
  padding: 0 14px 14px;
}
</style>
