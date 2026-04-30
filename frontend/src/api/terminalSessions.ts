import http from './http'

export interface TerminalSession {
  sessionId: string
  deviceId: string
  status: 'opening' | 'open' | 'closing' | 'closed' | 'error'
  title: string
  shell: string
  cwd?: string | null
  envSummary?: Record<string, string> | null
  cols: number
  rows: number
  createdAt: string
  updatedAt: string
  lastActiveAt: string
  exitCode?: number | null
  closeReason?: string | null
}

export interface CreateTerminalSessionPayload {
  shell?: string
  cwd?: string
  env?: Record<string, string>
  cols: number
  rows: number
  title?: string
}

export interface TerminalSessionSnapshot {
  session: TerminalSession
  capabilities: Record<string, boolean>
  seq: number
  connectedClients: number
}

export async function createTerminalSession(
  deviceId: string,
  payload: CreateTerminalSessionPayload,
): Promise<{ session: TerminalSession }> {
  const { data } = await http.post(`/api/agents/${deviceId}/terminal-sessions`, payload)
  return data
}

export async function listTerminalSessions(
  deviceId: string,
): Promise<{ items: TerminalSession[] }> {
  const { data } = await http.get(`/api/agents/${deviceId}/terminal-sessions`)
  return data
}

export async function getTerminalSession(
  deviceId: string,
  sessionId: string,
): Promise<TerminalSessionSnapshot> {
  const { data } = await http.get(`/api/agents/${deviceId}/terminal-sessions/${sessionId}`)
  return data
}

export async function updateTerminalSession(
  deviceId: string,
  sessionId: string,
  payload: { title: string },
): Promise<{ session: TerminalSession }> {
  const { data } = await http.patch(`/api/agents/${deviceId}/terminal-sessions/${sessionId}`, payload)
  return data
}

export async function deleteTerminalSession(
  deviceId: string,
  sessionId: string,
): Promise<{ ok: boolean }> {
  const { data } = await http.delete(`/api/agents/${deviceId}/terminal-sessions/${sessionId}`)
  return data
}
