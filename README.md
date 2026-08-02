# Glassbox

A browser agent you can see through.

Give it a goal in plain English. It plans with Claude, drives a real Chromium
browser, and streams every thought, click, and page back to you as it works.
You can pause it, stop it, veto individual steps, or talk to it mid-run. It
ends with a clean structured result, or an honest account of why it couldn't.

Built for the Minerva take-home challenge by [Jay Chak](https://jchak7.github.io/portfolio).

## Why it looks the way it does

A browser agent is only as useful as your ability to trust it. Most agent
demos hide the loop and show you a spinner. Glassbox does the opposite: the
interface *is* the product.

- **The agent narrates before it acts.** Every step shows 1–3 sentences of
  reasoning written for a non-technical reader, then the exact action
  (`click [12]`, `navigate → stockanalysis.com/...`) as a separate, legible
  unit.
- **You see what it sees.** A live screenshot of the agent's browser updates
  after every action, next to the URL it's on and the step count.
- **Control is layered, not binary.** Autopilot with Stop/Pause for when you
  trust it; "Approve each step" mode when you don't; a steer box to change
  its instructions mid-run without restarting ("skip Microsoft, just do
  Apple"). Rejecting a step lets you tell it what to do instead, and that
  feedback goes straight into the model's context.
- **No silent failures.** Errors surface in the feed as they happen, marked
  recovering or fatal. The agent detects its own loops (same action three
  times), says so, and changes approach. Six consecutive failures end the
  run with a report instead of a thrash. "Success" is only claimed when the
  goal was actually met — the finish tool forces the model to pick a status
  and defend it.
- **The result is an artifact, not a chat message.** Tabular goals end in a
  real table with a CSV download, plus the agent's own notes on anomalies
  and normalization decisions.

## What to try

Two showcase goals ship as one-click presets, both verified end-to-end in
production:

1. **Reconcile messy invoices.** A deliberately imperfect client billing
   portal ships inside this deploy at `/sandbox` — mixed date formats, three
   currencies, inconsistent status casing, a duplicate invoice number, and a
   credit note. The agent logs in, pages through all 14 records, normalizes
   them into one clean table, and flags the traps. Every extracted row has
   been checked against ground truth: 14/14 exact. The portal is self-hosted
   on purpose — it makes the demo deterministic, and the mess is modeled on
   what real client data looks like.
2. **Compare company financials.** Pulls the latest completed fiscal year
   for Apple and Microsoft — revenue, net income, EPS — then *calculates*
   net profit margin and flags that the two fiscal years don't align
   (Apple ends September, Microsoft ends June), so the periods aren't
   directly comparable. Its figures were cross-checked against the
   companies' actual 10-K filings on SEC EDGAR and match exactly.

Two more presets (a Show HN research brief and a sports-stats form workflow)
show the agent generalizes — the loop has no task-specific code.

## How it's built

```
frontend/   React + TypeScript (Vite). One WebSocket, one reducer over the
            event stream. No state library, no UI framework.
backend/
  app/main.py     FastAPI: serves the SPA, the sandbox portal, and /ws.
  app/agent.py    The loop. Plan (Claude) → gate (human) → act (Playwright)
                  → observe → repeat. All state changes become events.
  app/llm.py      Tool definitions and the system prompt. One tool call per
                  turn; old page states are truncated to keep context lean.
  app/browser.py  Playwright wrapper. Distills each page into a numbered
                  inventory of interactive elements plus a text excerpt.
  app/sandbox.py  The Meridian invoice portal (the zero-flake demo target).
```

Design decisions worth knowing:

- **The model reads text, the human reads pixels.** Claude gets a distilled
  DOM (numbered elements, text excerpt, scroll position) — cheaper, faster,
  and less ambiguous to act on than screenshots. Screenshots go to the
  human, because trust is visual. Elements are tagged with `data-gbid`
  attributes at distill time, so actions target exactly what the model saw.
- **Long documents are paged, not truncated.** Filings and reports run to
  megabytes. A `read_more` tool advances a cursor through the page text so
  the model can dig without re-tokenizing the world, and `text_remaining`
  tells it honestly how much it hasn't read.
- **Nothing is allowed to hang.** Every action, screenshot and page read has
  a hard timeout (45s / 12s / 25s). A hang is a silent failure wearing a
  spinner — the one outcome this agent must never produce — so on timeout
  the agent is told plainly what stalled and re-routes. Heavy pages with
  looping chart animations are captured with animations frozen; if a frame
  still can't be grabbed, the feed says "screenshot skipped" and the run
  continues rather than blocking on cosmetics.
- **Model output is normalized before it reaches the UI.** A malformed
  `notes` or `table` field degrades to something readable instead of
  blanking the screen; a React error boundary is the last backstop.
- **Operator input is part of the model's world.** Steer messages and step
  rejections are delivered as content the model must acknowledge, not as
  out-of-band restarts.
- **Sonnet by default** (`GLASSBOX_MODEL` to override). The loop is
  model-agnostic within the Anthropic tool-use API.

## Run it locally

```bash
# backend
cd backend
pip install -r requirements.txt
playwright install chromium
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn app.main:app --port 8000

# frontend (separate terminal; dev server proxies to :8000)
cd frontend
npm install
npm run dev
```

Or the production shape: `cd frontend && npm run build` (outputs into
`backend/static/`), then uvicorn serves everything on one port.

## Deploy (Railway)

```bash
railway init          # from repo root
railway up            # builds the Dockerfile (Playwright base image)
railway variables --set ANTHROPIC_API_KEY=sk-ant-...
railway variables --set "GLASSBOX_USER_AGENT=Glassbox-Agent/1.0 (contact: you@example.com)"
railway domain        # get the public URL
```

Set a real contact address in `GLASSBOX_USER_AGENT`. Fair-access sites like
SEC EDGAR gate datacenter IPs and require automated clients to declare who
they are; a browser-masquerading UA from a cloud IP gets site-wide blocked.

The Dockerfile is two-stage: Node builds the SPA, the Playwright Python
image runs the server. `/api/health` is the healthcheck and reports whether
the API key is present.

## Honest limitations

- One run per browser tab, one tab per run. No parallel sessions yet.
- No login-walled real-world targets — deliberate scope choice for a public
  demo; the sandbox portal covers the authenticated-workflow case.
- The step limit is 40. Long research tasks hit it; raise
  `GLASSBOX_MAX_STEPS` if you want to watch it work longer.
- Runs are in-memory. Refreshing mid-run loses the feed (the run stops
  safely server-side).
- Fair-access walls are real, and one bit me. SEC EDGAR refuses this
  deploy outright: it blocks datacenter IP ranges, and I proved the block is
  IP-level rather than identity-level by having the agent read back its own
  User-Agent from httpbin — correctly declared, still refused. The same
  route works from a residential IP. So the financials showcase sources
  stockanalysis.com instead, whose figures I cross-checked against the
  actual 10-K filings (they match exactly). The SEC attempt is still worth
  watching if you point the agent there: it tries five distinct routes,
  diagnoses the block precisely, and reports what it would need to proceed
  — which is the transparency layer earning its keep.
