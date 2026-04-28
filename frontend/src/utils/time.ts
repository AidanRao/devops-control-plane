/**
 * 把 ISO 时间字符串格式化为相对时间（例如「5s 前」、「2m 前」）。
 * 兼容后端返回的 UTC ISO 字符串与空值。
 */
export function formatRelative(iso?: string | null): string {
  if (!iso) return '—'
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return '—'
  const diffMs = Date.now() - t
  if (diffMs < 0) return '刚刚'
  const s = Math.floor(diffMs / 1000)
  if (s < 5) return '刚刚'
  if (s < 60) return `${s}s 前`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m 前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h 前`
  const d = Math.floor(h / 24)
  return `${d}d 前`
}

/** 返回心跳时间对应的在线颜色级别：green=近期活跃，yellow=稍有延迟，red=长时间未见 */
export function heartbeatLevel(iso?: string | null): 'green' | 'yellow' | 'red' {
  if (!iso) return 'red'
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return 'red'
  const diffMs = Date.now() - t
  if (diffMs < 30_000) return 'green'
  if (diffMs < 120_000) return 'yellow'
  return 'red'
}
