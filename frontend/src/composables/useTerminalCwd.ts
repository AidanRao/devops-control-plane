import { computed, ref, type Ref } from 'vue'

export type PendingCd = {
  from: string
  to: string
}

export type ParsedCd = {
  commandToSend: string
  pending: PendingCd
}

export function useTerminalCwd(deviceId: Ref<string>, sessionId?: Ref<string>) {
  const cwd = ref<string>('')
  const persistedCwd = ref<string>('')
  const prevCwd = ref<string>('')
  const sid = sessionId ?? computed(() => 'default')

  function storageKey() {
    return `terminal-cwd:${deviceId.value}:${sid.value}`
  }

  function normalizeCwd(value: string) {
    // keep it simple: trim + collapse whitespace
    return value.trim().replace(/\s+/g, ' ')
  }

  function loadCwd() {
    try {
      const raw = localStorage.getItem(storageKey())
      const v = raw ? normalizeCwd(raw) : ''
      persistedCwd.value = v
      cwd.value = v
    } catch {
      persistedCwd.value = ''
      cwd.value = ''
    }
  }

  function persistCwd() {
    try {
      const v = normalizeCwd(cwd.value)
      cwd.value = v
      persistedCwd.value = v
      if (!v) localStorage.removeItem(storageKey())
      else localStorage.setItem(storageKey(), v)
    } catch {
      // ignore
    }
  }

  function clearCwd() {
    cwd.value = ''
    persistCwd()
  }

  function normalizePosixPath(inputPath: string) {
    const trimmed = inputPath.trim()
    if (!trimmed) return ''
    if (trimmed === '/') return '/'
    const isAbs = trimmed.startsWith('/')
    const isHome = trimmed.startsWith('~')

    const segments = trimmed.split('/').filter((s) => s.length > 0)
    const out: string[] = []
    for (const seg of segments) {
      if (seg === '.' || seg === '') continue
      if (seg === '..') {
        // Don't pop beyond "/" or "~"
        if (out.length > 0 && out[out.length - 1] !== '~') out.pop()
        continue
      }
      out.push(seg)
    }

    if (isHome) {
      if (out.length === 0 || out[0] !== '~') out.unshift('~')
      return out.length === 1 ? '~' : `${out[0]}/${out.slice(1).join('/')}`
    }

    if (isAbs) return `/${out.join('/')}`
    return out.join('/')
  }

  function joinPosixPath(base: string, rel: string) {
    const b = base.trim()
    const r = rel.trim()
    if (!r) return normalizePosixPath(b)
    if (r.startsWith('/') || r.startsWith('~')) return normalizePosixPath(r)
    if (!b) return normalizePosixPath(r)
    const sep = b.endsWith('/') ? '' : '/'
    return normalizePosixPath(`${b}${sep}${r}`)
  }

  function parseCdCommand(cmd: string): ParsedCd | null {
    const raw = cmd.trim()
    // Only handle simple `cd ...` forms; ignore chained commands to avoid surprises.
    if (!/^cd(?:\s+.*)?$/.test(raw)) return null
    if (/[;&|]/.test(raw)) return null

    const from = cwd.value
    const arg = raw.replace(/^cd\b/, '').trim()

    // cd - : only if we can predict the next cwd
    if (arg === '-') {
      const target = prevCwd.value
      if (!target) return null
      return {
        commandToSend: `cd ${target}`,
        pending: { from, to: target },
      }
    }

    if (!arg || arg === '~') {
      return {
        commandToSend: arg ? 'cd ~' : 'cd',
        pending: { from, to: '~' },
      }
    }

    return {
      commandToSend: `cd ${arg}`,
      pending: { from, to: joinPosixPath(from, arg) },
    }
  }

  function applyCdResult(pending: PendingCd | null, exitCode: number) {
    if (!pending) return
    if (exitCode !== 0) return
    prevCwd.value = pending.from
    cwd.value = pending.to
  }

  function promptDirNameFromPath(path?: string | null) {
    const value = (path ?? '').trim()
    if (!value) return '~'
    if (value === '/' || value === '~') return value

    const normalized = value.endsWith('/') && value.length > 1 ? value.slice(0, -1) : value
    const lastSlash = normalized.lastIndexOf('/')
    if (lastSlash === -1) return normalized
    const base = normalized.slice(lastSlash + 1)
    return base || (normalized.startsWith('/') ? '/' : '~')
  }

  const currentPromptDir = computed(() => promptDirNameFromPath(cwd.value))
  const isTempCwd = computed(() => Boolean(cwd.value) && cwd.value !== persistedCwd.value)

  function resetForDevice() {
    prevCwd.value = ''
    loadCwd()
  }

  return {
    cwd,
    persistedCwd,
    prevCwd,
    currentPromptDir,
    isTempCwd,
    loadCwd,
    persistCwd,
    clearCwd,
    parseCdCommand,
    applyCdResult,
    promptDirNameFromPath,
    resetForDevice,
  }
}
