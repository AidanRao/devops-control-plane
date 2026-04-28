import http from './http'

export interface AgentInfo {
  device_id: string
  hasDeviceToken: boolean
  lastHeartbeat?: string | null
}

export interface AgentsResponse {
  agents: AgentInfo[]
}

export interface AgentCommandHistoryItem {
  task_uuid: string
  command: string
  status: string
  exitCode?: number | null
  createdAt: string
  stdout?: string | null
  stderr?: string | null
}

export interface AgentCommandHistoryResponse {
  device_id: string
  items: AgentCommandHistoryItem[]
}

export async function fetchAgents(): Promise<AgentInfo[]> {
  const { data } = await http.get<AgentsResponse>('/api/agents')
  return data?.agents ?? []
}

export async function fetchAgentCommands(
  deviceId: string,
): Promise<AgentCommandHistoryItem[]> {
  const { data } = await http.get<AgentCommandHistoryResponse>(
    `/api/agents/${encodeURIComponent(deviceId)}/commands`,
  )
  return data?.items ?? []
}
