import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchAgents, type AgentInfo } from '@/api/agents'

export const useAgentStore = defineStore('agents', () => {
  const agents = ref<AgentInfo[]>([])
  const selected = ref<Set<string>>(new Set())
  const loading = ref(false)

  const selectedCount = computed(() => selected.value.size)
  const allSelected = computed(
    () => agents.value.length > 0 && selected.value.size === agents.value.length,
  )
  const indeterminate = computed(
    () => selected.value.size > 0 && selected.value.size < agents.value.length,
  )

  async function refresh() {
    loading.value = true
    try {
      agents.value = await fetchAgents()
      // 清理已经下线的选中项
      const alive = new Set(agents.value.map((a) => a.device_id))
      const next = new Set<string>()
      for (const id of selected.value) {
        if (alive.has(id)) next.add(id)
      }
      selected.value = next
    } finally {
      loading.value = false
    }
  }

  function toggle(id: string, checked: boolean) {
    const next = new Set(selected.value)
    if (checked) next.add(id)
    else next.delete(id)
    selected.value = next
  }

  function toggleAll(checked: boolean) {
    selected.value = checked ? new Set(agents.value.map((a) => a.device_id)) : new Set()
  }

  function clearSelection() {
    selected.value = new Set()
  }

  return {
    agents,
    selected,
    loading,
    selectedCount,
    allSelected,
    indeterminate,
    refresh,
    toggle,
    toggleAll,
    clearSelection,
  }
})
