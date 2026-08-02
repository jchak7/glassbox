import { useEffect, useRef, useState } from 'react'
import { useAgentSocket } from './useAgentSocket'
import { Feed, ActionChip, describeAction } from './components/Feed'
import { Result } from './components/Result'
import { PRESETS } from './types'

const MAX_STEPS = 40

function fmtElapsed(s: number): string {
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

export default function App() {
  const { state, start, controls, setIdleMode } = useAgentSocket()
  const [goal, setGoal] = useState('')
  const [steerText, setSteerText] = useState('')
  const [rejecting, setRejecting] = useState(false)
  const [rejectText, setRejectText] = useState('')
  const [elapsed, setElapsed] = useState(0)
  const startedAt = useRef(0)

  const busy = state.phase === 'running' || state.phase === 'paused' || state.phase === 'awaiting_approval'

  useEffect(() => {
    if (!busy) return
    const id = setInterval(
      () => setElapsed(Math.floor((Date.now() - startedAt.current) / 1000)), 1000)
    return () => clearInterval(id)
  }, [busy])

  // keyboard shortcuts for the approval dock
  useEffect(() => {
    if (!state.pendingApproval || rejecting) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Enter') controls.approve()
      if (e.key === 'Escape') setRejecting(true)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [state.pendingApproval, rejecting]) // eslint-disable-line react-hooks/exhaustive-deps

  const launch = () => {
    if (!goal.trim()) return
    startedAt.current = Date.now()
    setElapsed(0)
    start(goal, state.mode)
  }
  const sendSteer = () => {
    if (steerText.trim()) {
      controls.steer(steerText.trim())
      setSteerText('')
    }
  }
  const sendReject = () => {
    controls.reject(rejectText || 'Do something else.')
    setRejecting(false)
    setRejectText('')
  }

  const progressState = (): { text: string; cls: string } => {
    if (state.phase === 'awaiting_approval') return { text: 'paused for review', cls: 'warn' }
    if (state.phase === 'paused') return { text: 'paused', cls: 'warn' }
    if (state.phase === 'finished' && state.result) {
      if (state.result.status === 'success') return { text: 'complete', cls: 'ok' }
      return { text: `stopped at step ${state.result.steps}`, cls: 'bad' }
    }
    return { text: `${fmtElapsed(elapsed)} elapsed`, cls: '' }
  }
  const ps = progressState()

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">▣</span>Glassbox
          <span className="brand-sub">— a browser agent you can see through</span>
        </div>
        <div className="topbar-right">
          <span className="usage" title="Claude tokens used this run">
            {((state.usage.input + state.usage.output) / 1000).toFixed(1)}k tokens
          </span>
          <span className={`phase phase-${state.phase}`}>
            {state.phase === 'idle' && 'ready'}
            {state.phase === 'running' && 'working'}
            {state.phase === 'paused' && 'paused'}
            {state.phase === 'awaiting_approval' && 'waiting for you'}
            {state.phase === 'finished' && 'done'}
          </span>
        </div>
      </header>

      <section className="goalbar">
        <div className="goal-wrap">
          <textarea
            className="goal-input"
            placeholder="Tell the agent what to get done — in plain English."
            value={goal}
            rows={2}
            disabled={busy}
            onChange={(e) => setGoal(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) launch()
            }}
          />
          {!busy && <span className="goal-hint">⌘↵ to run</span>}
        </div>
        <div className="goal-actions">
          <div className="mode-toggle" role="radiogroup" aria-label="control mode">
            <button
              className={state.mode === 'auto' ? 'on' : ''}
              onClick={() => (busy ? controls.setMode('auto') : setIdleMode('auto'))}
            >
              Autopilot
            </button>
            <button
              className={state.mode === 'approve' ? 'on' : ''}
              onClick={() => (busy ? controls.setMode('approve') : setIdleMode('approve'))}
            >
              Approve each step
            </button>
          </div>
          {!busy && (
            <button className="btn btn-primary" onClick={launch} disabled={!goal.trim()}>
              Run agent
            </button>
          )}
          {busy && state.phase !== 'paused' && (
            <button className="btn btn-secondary" onClick={controls.pause}>Pause</button>
          )}
          {state.phase === 'paused' && (
            <button className="btn btn-primary" onClick={controls.resume}>Resume</button>
          )}
          {busy && (
            <button className="btn btn-danger" onClick={controls.stop}>Stop</button>
          )}
          {(busy || state.phase === 'finished') && (
            <div className="progress-strip">
              <span className="progress-label">step {state.stepCount} / {MAX_STEPS} max</span>
              <div className="progress-track">
                <div
                  className={`progress-fill ${ps.cls === 'bad' ? 'bad' : ''}`}
                  style={{ width: `${Math.min(100, (state.stepCount / MAX_STEPS) * 100)}%` }}
                />
              </div>
              <span className={`progress-state ${ps.cls}`}>{ps.text}</span>
            </div>
          )}
        </div>
        {!busy && state.phase !== 'finished' && (
          <div className="presets-row">
            <div className="presets">
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  className={`preset ${p.tag}`}
                  title={p.goal}
                  onClick={() => setGoal(p.goal)}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <span className="presets-help">Pick a preset, or write your own goal.</span>
          </div>
        )}
      </section>

      <main className="workspace">
        <section className="browser-pane">
          <div className="browser-chrome grid-bg">
            <span className={`live-dot ${busy ? 'on' : ''}`} />
            <span className="browser-url">{state.currentUrl || 'about:blank'}</span>
            {state.stepCount > 0 && (
              <span className="step-count">
                step {state.stepCount}{state.phase === 'finished' ? ' · browser closed' : ''}
              </span>
            )}
          </div>
          <div className="browser-view">
            {state.screenshot ? (
              <img src={`data:image/jpeg;base64,${state.screenshot}`} alt="current page" />
            ) : (
              <div className="browser-placeholder">
                <div className="ph-window" />
                {busy ? 'Opening browser…' : 'The agent’s browser will appear here.'}
              </div>
            )}
          </div>
        </section>

        <section className="activity-pane grid-bg">
          <Feed items={state.feed} running={state.phase === 'running'} />

          {state.pendingApproval && (
            <div className="approval">
              <p className="approval-title">The agent wants to:</p>
              <ActionChip action={state.pendingApproval.action} />
              <p className="approval-desc">{describeAction(state.pendingApproval.action)}</p>
              {!rejecting ? (
                <div className="approval-actions">
                  <button className="btn btn-primary" onClick={controls.approve}>Approve</button>
                  <button className="btn btn-secondary" onClick={() => setRejecting(true)}>
                    Reject…
                  </button>
                  <span className="approval-hint">↵ approve · esc reject</span>
                </div>
              ) : (
                <div className="approval-actions">
                  <input
                    autoFocus
                    placeholder="Tell it what to do instead"
                    value={rejectText}
                    onChange={(e) => setRejectText(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && sendReject()}
                  />
                  <button className="btn btn-danger" onClick={sendReject}>Send</button>
                </div>
              )}
            </div>
          )}

          {busy && (
            <div className="steer">
              <input
                placeholder="Steer the agent mid-run…"
                value={steerText}
                onChange={(e) => setSteerText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendSteer()}
              />
              <button className="btn btn-secondary" onClick={sendSteer} disabled={!steerText.trim()}>
                Send
              </button>
            </div>
          )}

          {state.result && <Result result={state.result} onNewRun={() => location.reload()} />}
        </section>
      </main>
    </div>
  )
}
