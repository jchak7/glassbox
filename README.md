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
  (`click [12]`, `navigate → sec.gov/...`) as a separate, legible unit.
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

Two showcase goals ship as one-click presets:

1. **SEC filings → comparison table.** Pulls fiscal year, revenue and net
   income for Apple and Microsoft from their latest 10-Ks on SEC EDGAR and
   normalizes them into one table, citing the exact filings used.
2. **Reconcile messy invoices.** A deliberately imperfect client billing
   portal ships inside this deploy at `/sandbox` — mixed date formats, three
   currencies, inconsistent statuses, a duplicate invoice number, and a
   credit note. The agent logs in, pages through all invoices, normalizes
   them into one clean table, and flags the traps. The portal is
   self-hosted on purpose: it makes the demo deterministic, and the mess is
   modeled on what real client data looks like.

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
- **Long documents are paged, not truncated.** SEC filings run to megabytes.
  A `read_more` tool advances a cursor through the page text so the model
  can dig without re-tokenizing the world, and `text_remaining` tells it
  honestly how much it hasn't read.
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
railway domain        # get the public URL
```

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
