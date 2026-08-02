import { useEffect, useRef } from 'react'
import type { Action, FeedItem } from '../types'

function actionLabel(a: Action): string {
  const i = a.input as Record<string, any>
  switch (a.tool) {
    case 'navigate': return `navigate → ${i.url}`
    case 'click': return `click [${i.element_id}]`
    case 'type_text': return `type "${String(i.text).slice(0, 40)}" into [${i.element_id}]${i.press_enter ? ' ⏎' : ''}`
    case 'select_option': return `select "${i.value}" in [${i.element_id}]`
    case 'scroll': return `scroll ${i.direction ?? 'down'}`
    case 'read_more': return 'read more of this document'
    case 'go_back': return 'go back'
    case 'finish': return `finish (${i.status})`
    default: return a.tool
  }
}

export function describeAction(a: Action): string {
  const i = a.input as Record<string, any>
  switch (a.tool) {
    case 'navigate': return `Opens ${i.url} in the agent's browser.`
    case 'click': return `Clicks element [${i.element_id}] on the current page.`
    case 'type_text': return `Types "${i.text}" into field [${i.element_id}]${i.press_enter ? ', then submits' : ''}.`
    case 'select_option': return `Selects "${i.value}" in dropdown [${i.element_id}].`
    case 'scroll': return `Scrolls the page ${i.direction ?? 'down'}.`
    case 'read_more': return 'Reads the next chunk of this document — no browser action.'
    case 'go_back': return 'Goes back to the previous page.'
    default: return ''
  }
}

export function ActionChip({ action }: { action: Action }) {
  return <code className={`chip chip-${action.tool}`}>{actionLabel(action)}</code>
}

const pad = (n: number) => String(n).padStart(2, '0')

export function Feed({ items, running }: { items: FeedItem[]; running: boolean }) {
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [items])

  const lastStepIdx = items.reduce((acc, f, i) => (f.kind === 'step' ? i : acc), -1)

  return (
    <div className="feed">
      {items.length === 0 && (
        <div className="feed-empty">
          <div className="eyebrow">ACTIVITY</div>
          <p>
            Give the agent a goal and every thought, click and page it touches
            will appear here as it happens.
          </p>
          <ol>
            <li><span className="k">01</span>It narrates in plain English before every action.</li>
            <li><span className="k">02</span>You can pause, stop, or correct it mid-run.</li>
            <li><span className="k">03</span>Failures show up here too — never a silent spinner.</li>
          </ol>
        </div>
      )}
      {items.map((f, i) => {
        if (f.kind === 'status')
          return <div key={i} className="feed-status">{f.detail}</div>
        if (f.kind === 'error')
          return (
            <div key={i} className="titem">
              <div className="rail" />
              <div className={`tcard err ${f.recoverable ? '' : 'fatal'}`}>
                <span className="feed-error-tag">{f.recoverable ? 'RECOVERING' : 'FAILED'}</span>
                <span>{f.message}</span>
              </div>
            </div>
          )
        if (f.kind === 'operator')
          return (
            <div key={i} className="titem">
              <div className="rail"><div className="tnode you">YOU</div></div>
              <div className="tcard op">
                <span className="op-who">You</span>
                {f.opKind === 'steer' && <> said: “{f.text}”</>}
                {f.opKind === 'approve' && <> approved this step.</>}
                {f.opKind === 'reject' && <> rejected this step{f.text ? `: “${f.text}”` : '.'}</>}
              </div>
            </div>
          )
        // step
        const acting = f.ok === undefined && f.action !== null && i === lastStepIdx && running
        const nodeCls = acting ? 'acting' : f.ok === undefined ? '' : f.ok ? 'ok' : 'fail'
        return (
          <div key={i} className="titem">
            <div className="rail"><div className={`tnode ${nodeCls}`}>{pad(f.n)}</div></div>
            <div className="tcard step">
              <div className="step-head">
                {f.action && <ActionChip action={f.action} />}
                {acting && <span className="acting-label">acting…</span>}
                {f.ok !== undefined && (
                  <span className={`step-ok ${f.ok ? 'yes' : 'no'}`}>{f.ok ? '✓' : '✗'}</span>
                )}
              </div>
              {f.reasoning && <p className="step-reasoning">{f.reasoning}</p>}
              {f.detail && f.ok === false && <p className="step-fail-detail">{f.detail}</p>}
            </div>
          </div>
        )
      })}
      <div ref={endRef} />
    </div>
  )
}
