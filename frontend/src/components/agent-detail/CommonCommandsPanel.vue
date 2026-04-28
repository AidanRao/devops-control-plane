<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  ElButton,
  ElDialog,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElScrollbar,
} from 'element-plus'
import CommonCommandCard from './CommonCommandCard.vue'
import type { CommonCommandPreset, CommonCommandPresetInput } from '@/composables/useCommonCommands'

const props = defineProps<{
  commands: CommonCommandPreset[]
}>()

const emit = defineEmits<{
  (e: 'save-preset', payload: CommonCommandPresetInput): void
  (e: 'remove-preset', id: string): void
  (e: 'apply-preset', item: CommonCommandPreset): void
}>()

const dialogVisible = ref(false)
const editingPresetId = ref<string | null>(null)
const form = ref({
  title: '',
  command: '',
  remark: '',
})

const dialogTitle = computed(() =>
  editingPresetId.value ? '编辑常用指令' : '新增常用指令',
)

function openCreateDialog() {
  editingPresetId.value = null
  form.value = {
    title: '',
    command: '',
    remark: '',
  }
  dialogVisible.value = true
}

function openEditDialog(item: CommonCommandPreset) {
  editingPresetId.value = item.id
  form.value = {
    title: item.title,
    command: item.command,
    remark: item.remark ?? '',
  }
  dialogVisible.value = true
}

function savePreset() {
  const title = form.value.title.trim()
  const command = form.value.command.trim()

  if (!title) {
    ElMessage.warning('请输入指令标题')
    return
  }

  if (!command) {
    ElMessage.warning('请输入指令内容')
    return
  }

  emit('save-preset', {
    id: editingPresetId.value,
    title,
    command,
    remark: form.value.remark,
  })

  dialogVisible.value = false
}

defineExpose({
  openCreate: openCreateDialog,
})
</script>

<template>
  <div class="preset-panel">
    <div v-if="commands.length === 0" class="preset-empty">
      <el-empty description="还没有常用指令" :image-size="54" />
    </div>

    <el-scrollbar v-else class="preset-scroll">
      <div class="preset-list">
        <CommonCommandCard
          v-for="item in commands"
          :key="item.id"
          :item="item"
          @apply="emit('apply-preset', $event)"
          @edit="openEditDialog"
          @remove="emit('remove-preset', $event)"
        />
      </div>
    </el-scrollbar>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="560px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="标题">
          <el-input v-model="form.title" maxlength="40" show-word-limit placeholder="例如：查看磁盘使用情况" />
        </el-form-item>
        <el-form-item label="指令">
          <el-input v-model="form.command" type="textarea" :rows="4" placeholder="例如：df -h" />
        </el-form-item>
        <el-form-item label="备注（可选）">
          <el-input
            v-model="form.remark"
            type="textarea"
            :rows="2"
            placeholder="补充说明这条常用指令的作用"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-actions">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="savePreset">保存</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.preset-panel {
  display: flex;
  flex-direction: column;
}

.preset-empty {
  padding-top: 18px;
}

.preset-scroll {
  max-height: 430px;
  padding-top: 10px;
}

.preset-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 4px;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
