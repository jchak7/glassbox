export type Action = { tool: string; input: Record<string, unknown> }

export type ResultTable = { columns: string[]; rows: string[][] }

export type AgentEvent =
  | { type: 'status'; status: string; detail?: string }
  | { type: 'step'; n: number; reasoning: string; action: Action | null }
  | { type: 'action_result'; n: number; ok: boolean; detail: string; url: string }
  | { type: 'screenshot'; n: number; data: string; url: string }
  | { type: 'approval_request'; n: number; action: Action }
  | { type: 'operator'; kind: 'steer' | 'approve' | 'reject'; text?: string }
  | { type: 'error'; n?: number; message: string; recoverable: boolean }
  | { type: 'usage'; input: number; output: number }
  | {
      type: 'result'
      status: 'success' | 'failure' | 'stopped' | 'error'
      summary: string
      table?: ResultTable | null
      notes?: string[]
      steps: number
      duration_s: number
      usage?: { input: number; output: number }
    }

export type FeedItem =
  | { kind: 'step'; n: number; reasoning: string; action: Action | null; ok?: boolean; detail?: string }
  | { kind: 'error'; message: string; recoverable: boolean }
  | { kind: 'operator'; opKind: 'steer' | 'approve' | 'reject'; text?: string }
  | { kind: 'status'; detail: string }

export type RunPhase = 'idle' | 'running' | 'paused' | 'awaiting_approval' | 'finished'

export interface RunState {
  phase: RunPhase
  mode: 'auto' | 'approve'
  feed: FeedItem[]
  screenshot: string | null
  currentUrl: string
  pendingApproval: { n: number; action: Action } | null
  result: Extract<AgentEvent, { type: 'result' }> | null
  usage: { input: number; output: number }
  stepCount: number
}

export const PRESETS: { label: string; goal: string; tag: string }[] = [
  {
    label: 'Reconcile messy invoices (sandbox)',
    tag: 'showcase',
    goal:
      'Log in to the billing portal at /sandbox (credentials are shown on the sign-in page). ' +
      'Collect every invoice across all pages. Normalize into one table with columns: ' +
      'invoice number, vendor, date (ISO 8601), amount, currency, status (Paid/Pending/Overdue/Credit). ' +
      'Flag anything unusual — duplicates, credit notes, inconsistent formats — in your notes.',
  },
  {
    label: 'Compare company financials',
    tag: 'showcase',
    goal:
      'Compare the latest full-fiscal-year financials for Apple and Microsoft. ' +
      'Open https://stockanalysis.com/stocks/aapl/financials/ and read the most recent ' +
      'completed fiscal year column (not TTM): revenue, net income, and earnings per share. ' +
      'Then do the same at https://stockanalysis.com/stocks/msft/financials/. ' +
      'Build one comparison table: company, fiscal year end, revenue (USD millions), ' +
      'net income (USD millions), EPS, and net profit margin which you calculate as ' +
      'net income divided by revenue. Note in your findings that the two companies have ' +
      'different fiscal year ends, so the periods are not directly comparable.',
  },
  {
    label: 'Research brief: Show HN',
    tag: 'extra',
    goal:
      'Visit https://news.ycombinator.com/show and compile a short structured brief of the top 5 Show HN projects right now: ' +
      'name, one-line description, points, and link. Add two sentences on any visible trend.',
  },
  {
    label: 'Tedious workflow: web form',
    tag: 'extra',
    goal:
      'Go to https://www.scrapethissite.com/pages/forms/ and find all NHL teams whose name contains “Rangers”. ' +
      'Report each team’s wins and losses for every year listed, as a table.',
  },
]
