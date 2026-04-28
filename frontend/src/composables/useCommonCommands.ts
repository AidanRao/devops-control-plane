import { ref, watch } from 'vue'

export interface CommonCommandPreset {
  id: string
  title: string
  command: string
  remark?: string
}

export interface CommonCommandPresetInput {
  id?: string | null
  title: string
  command: string
  remark?: string
}

function storageKey(deviceId: string) {
  return `agent-common-commands:${deviceId}`
}

function createPresetId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function normalizePresetList(value: unknown): CommonCommandPreset[] {
  if (!Array.isArray(value)) return []

  const normalized: CommonCommandPreset[] = []
  for (const item of value) {
    if (!item || typeof item !== 'object') continue
    const candidate = item as Record<string, unknown>
    const title = typeof candidate.title === 'string' ? candidate.title.trim() : ''
    const command = typeof candidate.command === 'string' ? candidate.command.trim() : ''
    const remark = typeof candidate.remark === 'string' ? candidate.remark.trim() : ''
    const id = typeof candidate.id === 'string' && candidate.id ? candidate.id : createPresetId()

    if (!title || !command) continue

    normalized.push({
      id,
      title,
      command,
      remark: remark || undefined,
    })
  }

  return normalized
}

export function useCommonCommands(deviceIdGetter: () => string) {
  const commonCommands = ref<CommonCommandPreset[]>([])

  function loadCommonCommands() {
    try {
      const raw = localStorage.getItem(storageKey(deviceIdGetter()))
      commonCommands.value = raw ? normalizePresetList(JSON.parse(raw)) : []
    } catch {
      commonCommands.value = []
    }
  }

  function persistCommonCommands() {
    localStorage.setItem(storageKey(deviceIdGetter()), JSON.stringify(commonCommands.value))
  }

  function savePreset(input: CommonCommandPresetInput) {
    const title = input.title.trim()
    const command = input.command.trim()
    const remark = input.remark?.trim() || undefined

    if (!title || !command) {
      return false
    }

    if (input.id) {
      commonCommands.value = commonCommands.value.map((item) =>
        item.id === input.id
          ? {
              ...item,
              title,
              command,
              remark,
            }
          : item,
      )
    } else {
      commonCommands.value.unshift({
        id: createPresetId(),
        title,
        command,
        remark,
      })
    }

    persistCommonCommands()
    return true
  }

  function removePreset(id: string) {
    commonCommands.value = commonCommands.value.filter((item) => item.id !== id)
    persistCommonCommands()
  }

  watch(
    () => deviceIdGetter(),
    () => {
      loadCommonCommands()
    },
    { immediate: true },
  )

  return {
    commonCommands,
    loadCommonCommands,
    savePreset,
    removePreset,
  }
}
