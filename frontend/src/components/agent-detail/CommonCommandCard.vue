<script setup lang="ts">
import { ElButton, ElIcon } from 'element-plus'
import { Delete, DocumentCopy, EditPen } from '@element-plus/icons-vue'
import type { CommonCommandPreset } from '@/composables/useCommonCommands'

defineProps<{
  item: CommonCommandPreset
}>()

const emit = defineEmits<{
  (e: 'apply', item: CommonCommandPreset): void
  (e: 'edit', item: CommonCommandPreset): void
  (e: 'remove', id: string): void
}>()
</script>

<template>
  <article class="preset-card">
    <div class="preset-card-head">
      <div class="preset-card-copy">
        <div class="preset-title-row">
          <span class="preset-accent" />
          <h3 class="preset-title">{{ item.title }}</h3>
        </div>
        <p v-if="item.remark" class="preset-remark" :title="item.remark">{{ item.remark }}</p>
      </div>

      <!-- 低频操作：仅 hover 展示，避免占用垂直空间 -->
      <div class="preset-actions">
        <el-button
          size="small"
          text
          circle
          class="action-btn"
          :icon="EditPen"
          title="编辑"
          @click.stop="emit('edit', item)"
        />
        <el-button
          size="small"
          text
          circle
          class="action-btn action-btn--danger"
          :icon="Delete"
          title="删除"
          @click.stop="emit('remove', item.id)"
        />
      </div>
    </div>

    <!-- 主交互：点击代码块填入终端 -->
    <button class="preset-command-shell" type="button" @click="emit('apply', item)">
      <span class="preset-prompt">$</span>
      <code class="preset-command">{{ item.command }}</code>
      <span class="preset-fill-hint" aria-hidden="true">
        <el-icon><DocumentCopy /></el-icon>
      </span>
    </button>
  </article>
</template>

<style scoped>
.preset-card {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 10px 10px 10px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.96) 100%);
  transition: box-shadow 0.16s ease, border-color 0.16s ease;
}

.preset-card:hover {
  border-color: #c7d2fe;
  box-shadow: 0 10px 18px rgba(37, 99, 235, 0.06);
}

.preset-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.preset-card-copy {
  min-width: 0;
}

.preset-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preset-accent {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
  flex: none;
}

.preset-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.preset-remark {
  margin: 4px 0 0 14px;
  font-size: 11px;
  line-height: 1.5;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.preset-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.15s ease;
  flex: none;
}

.preset-card:hover .preset-actions {
  opacity: 1;
}

.action-btn {
  --el-button-text-color: #64748b;
  --el-button-hover-text-color: #2563eb;
  --el-button-hover-bg-color: #eff6ff;
  width: 26px;
  height: 26px;
  padding: 0;
}

.action-btn--danger {
  --el-button-hover-text-color: #ef4444;
  --el-button-hover-bg-color: rgba(239, 68, 68, 0.08);
}

.preset-command-shell {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 8px 10px;
  border-radius: 12px;
  background:
    linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
  border: 1px solid #e2e8f0;
  width: 100%;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.preset-command-shell:hover {
  border-color: #bfdbfe;
  background: linear-gradient(180deg, #f0f9ff 0%, #eef2ff 100%);
}

.preset-prompt {
  font-family: 'JetBrains Mono Variable', monospace;
  color: #2563eb;
  font-weight: 700;
  line-height: 1.5;
}

.preset-command {
  font-family: 'JetBrains Mono Variable', monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #1f2937;
  white-space: pre-wrap;
  word-break: break-word;
  flex: 1;
}

.preset-fill-hint {
  color: #94a3b8;
  flex: none;
  opacity: 0.55;
  transform: translateY(1px);
  transition: opacity 0.15s ease;
}

.preset-command-shell:hover .preset-fill-hint {
  opacity: 0.95;
}
</style>
