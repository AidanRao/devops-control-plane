import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  dispatchCommand,
  getCommandStatus,
  type CommandStatusResponse,
  type DispatchCommandPayload,
} from '@/api/commands'

export const useCommandStore = defineStore('commands', () => {
  const currentTaskUuid = ref<string | null>(null)
  const currentStatus = ref<CommandStatusResponse | null>(null)
  const dispatching = ref(false)

  async function submit(payload: DispatchCommandPayload) {
    dispatching.value = true
    try {
      const { task_uuid } = await dispatchCommand(payload)
      currentTaskUuid.value = task_uuid
      currentStatus.value = null
      return task_uuid
    } finally {
      dispatching.value = false
    }
  }

  async function refreshStatus() {
    if (!currentTaskUuid.value) return
    currentStatus.value = await getCommandStatus(currentTaskUuid.value)
  }

  return { currentTaskUuid, currentStatus, dispatching, submit, refreshStatus }
})
