import http from './http'

export interface CommandResultSummary {
  agent_id: string
  status: string
  exitCode?: number | null
  stdout?: string | null
  stderr?: string | null
}

export interface CommandStatusResponse {
  task_uuid: string
  status: string
  results: CommandResultSummary[]
}

export interface DispatchCommandPayload {
  command: string
  timeoutSeconds?: number
  targets?: string[]
  idempotencyKey?: string
}

export async function dispatchCommand(
  payload: DispatchCommandPayload,
): Promise<{ task_uuid: string }> {
  const { data } = await http.post('/api/commands', payload)
  return data
}

export async function getCommandStatus(taskUuid: string): Promise<CommandStatusResponse> {
  const { data } = await http.get(`/api/commands/${taskUuid}`)
  return data
}
