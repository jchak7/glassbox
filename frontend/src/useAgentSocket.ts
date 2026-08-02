import { useCallback, useEffect, useReducer, useRef } from 'react'
import type { AgentEvent, RunState } from './types'

const initial: RunState = {
  phase: 'idle',
  mode: 'auto',
  feed: [],
  screenshot: null,
  currentUrl: '',
  pendingApproval: null,
  result: null,
  usage: { input: 0, output: 0 },
  stepCount: 0,
}

type Msg =
  | { t: 'event'; e: AgentEvent }
  | { t: 'reset'; mode: 'auto' | 'approve' }
  | { t: 'local_mode'; mode: 'auto' | 'approve' }
  | { t: 'local_pause'; paused: boolean }

function reducer(s: RunState, m: Msg): RunState {
  if (m.t === 'reset') return { ...initial, mode: m.mode, phase: 'running' }
  if (m.t === 'local_mode') return { ...s, mode: m.mode }
  if (m.t === 'local_pause')
    return { ...s, phase: m.paused ? 'paused' : 'running' }

  const e = m.e
  switch (e.type) {
    case 'status':
      if (e.status === 'paused') return { ...s, phase: 'paused' }
      if (e.status === 'running') return { ...s, phase: 'running' }
      return {
        ...s,
        feed: e.detail ? [...s.feed, { kind: 'status' as const, detail: e.detail }] : s.feed,
      }
    case 'step':
      return {
        ...s,
        stepCount: e.n,
        feed: [...s.feed, { kind: 'step', n: e.n, reasoning: e.reasoning, action: e.action }],
      }
    case 'action_result': {
      const feed = s.feed.map((f) =>
        f.kind === 'step' && f.n === e.n ? { ...f, ok: e.ok, detail: e.detail } : f,
      )
      return { ...s, feed, currentUrl: e.url }
    }
    case 'screenshot':
      return { ...s, screenshot: e.data, currentUrl: e.url }
    case 'approval_request':
      return { ...s, phase: 'awaiting_approval', pendingApproval: { n: e.n, action: e.action } }
    case 'operator':
      return {
        ...s,
        phase: e.kind === 'approve' || e.kind === 'reject' ? 'running' : s.phase,
        pendingApproval: e.kind === 'approve' || e.kind === 'reject' ? null : s.pendingApproval,
        feed: [...s.feed, { kind: 'operator', opKind: e.kind, text: e.text }],
      }
    case 'error':
      return { ...s, feed: [...s.feed, { kind: 'error', message: e.message, recoverable: e.recoverable }] }
    case 'usage':
      return { ...s, usage: { input: e.input, output: e.output } }
    case 'result':
      return { ...s, phase: 'finished', result: e, pendingApproval: null }
    default:
      return s
  }
}

export function useAgentSocket() {
  const [state, dispatch] = useReducer(reducer, initial)
  const wsRef = useRef<WebSocket | null>(null)

  const connect = useCallback((): Promise<WebSocket> => {
    return new Promise((resolve, reject) => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/ws`)
      ws.onopen = () => resolve(ws)
      ws.onerror = () => reject(new Error('websocket failed'))
      ws.onmessage = (ev) => {
        try {
          dispatch({ t: 'event', e: JSON.parse(ev.data) as AgentEvent })
        } catch {
          /* ignore malformed frames */
        }
      }
      ws.onclose = () => {
        wsRef.current = null
      }
      wsRef.current = ws
    })
  }, [])

  const send = useCallback((msg: Record<string, unknown>) => {
    wsRef.current?.send(JSON.stringify(msg))
  }, [])

  const start = useCallback(
    async (goal: string, mode: 'auto' | 'approve') => {
      dispatch({ t: 'reset', mode })
      try {
        const ws = wsRef.current && wsRef.current.readyState === WebSocket.OPEN
          ? wsRef.current
          : await connect()
        ws.send(JSON.stringify({ type: 'start', goal, mode }))
      } catch {
        dispatch({
          t: 'event',
          e: { type: 'error', message: 'Could not reach the server. Is the backend running?', recoverable: false },
        })
        dispatch({
          t: 'event',
          e: { type: 'result', status: 'error', summary: 'Connection failed before the run started.', steps: 0, duration_s: 0 },
        })
      }
    },
    [connect],
  )

  const controls = {
    stop: () => send({ type: 'stop' }),
    pause: () => {
      send({ type: 'pause' })
      dispatch({ t: 'local_pause', paused: true })
    },
    resume: () => {
      send({ type: 'resume' })
      dispatch({ t: 'local_pause', paused: false })
    },
    approve: () => send({ type: 'approve' }),
    reject: (feedback: string) => send({ type: 'reject', feedback }),
    steer: (text: string) => send({ type: 'steer', text }),
    setMode: (mode: 'auto' | 'approve') => {
      send({ type: 'set_mode', mode })
      dispatch({ t: 'local_mode', mode })
    },
  }

  useEffect(() => () => wsRef.current?.close(), [])

  return { state, start, controls, setIdleMode: (mode: 'auto' | 'approve') => dispatch({ t: 'local_mode', mode }) }
}
