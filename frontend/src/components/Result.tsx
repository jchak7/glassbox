import type { AgentEvent } from '../types'

type ResultEvent = Extract<AgentEvent, { type: 'result' }>

const STATUS_COPY: Record<ResultEvent['status'], { label: string; cls: string; icon: string }> = {
  success: { label: 'Goal completed', cls: 'ok', icon: '✓' },
  failure: { label: 'Finished without completing the goal', cls: 'warn', icon: '✗' },
  stopped: { label: 'Stopped by you', cls: 'muted', icon: '■' },
  error: { label: 'Run aborted', cls: 'bad', icon: '✗' },
}

function toCsv(columns: string[], rows: string[][]): string {
  const esc = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v)
  return [columns, ...rows].map((r) => r.map(esc).join(',')).join('\n')
}

function cellClass(col: string, value: string): string {
  const cls: string[] = []
  if (/^-/.test(value.trim()) && /\d/.test(value)) cls.push('cell-neg')
  if (/status/i.test(col)) {
    const v = value.toLowerCase()
    if (v.includes('paid')) cls.push('cell-status-paid')
    else if (v.includes('pend')) cls.push('cell-status-pending')
    else if (v.includes('overdue')) cls.push('cell-status-overdue')
    else if (v.includes('credit')) cls.push('cell-status-credit')
  }
  return cls.join(' ')
}

export function Result({ result, onNewRun }: { result: ResultEvent; onNewRun: () => void }) {
  const meta = STATUS_COPY[result.status]
  const partial = result.status !== 'success'
  const download = () => {
    if (!result.table) return
    const blob = new Blob([toCsv(result.table.columns, result.table.rows)], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'glassbox-result.csv'
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div className="result">
      <div className={`result-banner ${meta.cls}`}>
        <span className="result-icon">{meta.icon}</span>
        <strong>{meta.label}</strong>
        <span className="result-meta">
          {result.steps} steps · {result.duration_s}s
          {result.usage ? ` · ${((result.usage.input + result.usage.output) / 1000).toFixed(1)}k tokens` : ''}
        </span>
      </div>
      {result.summary && <p className="result-summary">{result.summary}</p>}
      {result.table && result.table.rows.length > 0 && (
        <>
          <div className="result-table-wrap">
            <table>
              <thead>
                <tr>{result.table.columns.map((c, i) => <th key={i}>{c}</th>)}</tr>
              </thead>
              <tbody>
                {result.table.rows.map((r, i) => (
                  <tr key={i}>
                    {r.map((c, j) => (
                      <td key={j} className={cellClass(result.table!.columns[j] ?? '', c)}>{c}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="table-foot">
            <span>glassbox-result.csv</span>
            <span>{result.table.rows.length} rows</span>
          </div>
        </>
      )}
      {result.notes && result.notes.length > 0 && (
        <div className="result-notes">
          <h4>The agent flagged <span className="notes-count">{result.notes.length}</span></h4>
          <ul>{result.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </div>
      )}
      <div className="result-foot">
        {result.table && result.table.rows.length > 0 && (
          <button className="btn btn-primary" onClick={download}>
            {partial ? 'Download partial CSV' : 'Download CSV'}
          </button>
        )}
        <button className="btn btn-secondary" onClick={onNewRun}>New run</button>
        <span className="spacer" />
      </div>
    </div>
  )
}
