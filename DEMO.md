# Demo script — 60 seconds

Audience: Om, walking through the submission on a call. The point to land:
**the interface is the product — a non-technical person can trust and steer
this agent.**

## Setup (before the call)

- Open the public URL. Blank state, presets visible.
- Have the sandbox preset as your primary. EDGAR as the encore if time allows.

## The 60 seconds

**0:00 — Frame it.**
"Everyone's agent can click buttons. The hard part is letting a human trust
one. So I built the transparency layer first and the agent around it."

**0:05 — Launch.** Click *Reconcile messy invoices*, flip on **Approve each
step**, hit Run.
"It's planning with Claude, driving a real Chromium browser server-side.
Left is what the agent sees. Right is what it's thinking — written for a
non-technical reader, before every action, not after."

**0:15 — Approve two steps.** Point at the reasoning → action → result
rhythm. Then flip to **Autopilot** mid-run.
"Control is layered. Gate every step when you don't trust it yet, autopilot
when you do — switchable mid-run."

**0:25 — Steer it.** Type into the steer box: *"also note which vendor has
the highest total"*.
"I can redirect it mid-run without restarting. Watch it acknowledge that."

**0:35 — Show a recovery.** (If an action fails, point at it. If not:)
"When something fails, it fails loudly — errors land in the feed, the agent
says what went wrong and tries another way. It detects its own loops. Six
straight failures and it stops with a report instead of thrashing."

**0:45 — The payoff.** Result panel appears.
"And the output isn't a chat blob — it's a normalized table. It caught the
duplicate invoice number, the credit note, three currencies, four date
formats. Those traps are in the sandbox on purpose — this portal ships
inside the deploy so the demo is deterministic. CSV download for the
accountant."

**0:55 — The kicker.**
"Same loop, zero task-specific code — here it is pulling 10-K financials
off SEC EDGAR." (Start the EDGAR preset, let it run in the background while
you talk.)

**If SEC blocks the datacenter IP that day: let the failure run.** The agent
will try multiple routes, diagnose the block, and file an honest report with
next steps — which is requirement #5 of the brief, live. Say: "This is the
part most agent demos hide. Mine can't lie to you — a failed run ends in a
diagnosis, not made-up numbers. In accounting, that property is the product."

## Likely questions

- **Why not screenshots to the model?** Text is cheaper, faster, and less
  ambiguous to act on. The model reads a numbered element inventory; the
  human gets pixels because trust is visual. Swapping in vision is a
  20-line change in `browser.py`/`llm.py`.
- **Why a self-hosted sandbox?** Determinism for the live demo, and it's the
  only honest way to demo an authenticated workflow publicly. The mess is
  modeled on real client data.
- **What breaks first at scale?** One browser per run is the ceiling —
  next step is a session pool (or Browserbase) behind the same event
  protocol. The protocol wouldn't change.
- **Cost?** Token usage streams live in the header. A sandbox run is
  typically well under a dollar on Sonnet.
