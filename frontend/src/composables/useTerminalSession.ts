import { ref } from 'vue'

export type SessionStatePayload = {
  sessionId: string
  status: string
  title: string
  cwd?: string
  cols: number
  rows: number
  seq: number
  updatedAt: string
}

export type SessionChunkPayload = {
  sessionId: string
  seq: number
  stream: string
  data: string
  cwd?: string
  title?: string
  isBinary?: boolean
}

export type SessionClosedPayload = {
  sessionId: string
  exitCode?: number | null
  reason: string
  seq?: number
}

export type SessionErrorPayload = {
  sessionId: string
  code: string
  message: string
}

type UseTerminalSessionOptions = {
  sessionId: () => string
  onSessionState?: (payload: SessionStatePayload) => void
  onChunk?: (payload: SessionChunkPayload) => void
  onClosed?: (payload: SessionClosedPayload) => void
  onError?: (payload: SessionErrorPayload) => void
  onDisconnect?: () => void
}

type AttachResponsePayload = {
  sessionId: string
  status: string
  seq: number
  replayFrom?: number
}

function wsUrl(path: string) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${path}`
}

export function useTerminalSession(options: UseTerminalSessionOptions) {
  const connected = ref(false)
  const sessionStatus = ref('opening')
  const cwd = ref('')
  const seq = ref(0)

  let socket: WebSocket | null = null
  let requestCounter = 0
  let intentionalClose = false
  const pending = new Map<string, { resolve: (value: any) => void; reject: (reason?: any) => void }>()

  function sendRequest(method: string, params: any) {
    return new Promise<any>((resolve, reject) => {
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        reject(new Error('terminal websocket is not connected'))
        return
      }
      const id = `req_${++requestCounter}`
      pending.set(id, { resolve, reject })
      socket.send(JSON.stringify({ type: 'req', id, method, params }))
    })
  }

  async function attach() {
    const payload = (await sendRequest('terminal.session.attach', {
      sessionId: options.sessionId(),
      afterSeq: seq.value,
    })) as AttachResponsePayload

    sessionStatus.value = payload.status || sessionStatus.value
    seq.value = Math.max(seq.value, payload.seq ?? 0)
  }

  function handleState(payload: SessionStatePayload) {
    sessionStatus.value = payload.status
    cwd.value = payload.cwd ?? cwd.value
    seq.value = Math.max(seq.value, payload.seq)
    options.onSessionState?.(payload)
  }

  function handleEvent(event: string, payload: any) {
    if (event === 'terminal.session.state') {
      handleState(payload as SessionStatePayload)
      return
    }
    if (event === 'terminal.stdout.chunk') {
      const chunk = payload as SessionChunkPayload
      seq.value = Math.max(seq.value, chunk.seq)
      if (chunk.cwd) cwd.value = chunk.cwd
      options.onChunk?.(chunk)
      return
    }
    if (event === 'terminal.session.closed') {
      const closed = payload as SessionClosedPayload
      sessionStatus.value = 'closed'
      options.onClosed?.(closed)
      return
    }
    if (event === 'terminal.session.error') {
      const err = payload as SessionErrorPayload
      sessionStatus.value = 'error'
      options.onError?.(err)
    }
  }

  function connect() {
    cleanup()
    intentionalClose = false
    socket = new WebSocket(wsUrl('/ws/terminal'))
    socket.addEventListener('open', async () => {
      connected.value = true
      try {
        await attach()
      } catch (err) {
        options.onError?.({
          sessionId: options.sessionId(),
          code: 'ATTACH_FAILED',
          message: (err as Error).message || 'attach failed',
        })
      }
    })
    socket.addEventListener('message', (event) => {
      const message = JSON.parse(event.data) as any
      if (message.type === 'res') {
        const waiter = pending.get(message.id)
        if (!waiter) return
        pending.delete(message.id)
        if (message.ok) waiter.resolve(message.payload)
        else waiter.reject(new Error(message.error?.message || 'terminal request failed'))
        return
      }
      if (message.type === 'event') {
        handleEvent(message.event, message.payload)
      }
    })
    socket.addEventListener('close', () => {
      connected.value = false
      for (const [, waiter] of pending) {
        waiter.reject(new Error('terminal websocket closed'))
      }
      pending.clear()
      if (!intentionalClose) {
        options.onDisconnect?.()
      }
    })
  }

  async function sendInput(data: string) {
    await sendRequest('terminal.stdin.write', {
      sessionId: options.sessionId(),
      data,
    })
  }

  async function sendSignal(signal: string) {
    await sendRequest('terminal.session.signal', {
      sessionId: options.sessionId(),
      signal,
    })
  }

  async function resize(cols: number, rows: number) {
    await sendRequest('terminal.session.resize', {
      sessionId: options.sessionId(),
      cols,
      rows,
    })
  }

  function reset() {
    seq.value = 0
    cwd.value = ''
    sessionStatus.value = 'opening'
  }

  function cleanup() {
    intentionalClose = true
    if (socket) {
      socket.close()
      socket = null
    }
    connected.value = false
    pending.clear()
  }

  return {
    connected,
    sessionStatus,
    cwd,
    seq,
    connect,
    sendInput,
    sendSignal,
    resize,
    reset,
    cleanup,
  }
}
