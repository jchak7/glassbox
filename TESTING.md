# How this was tested

I'm a QA engineer by trade, so I'll be specific about what "it works" means
here. Three questions get asked separately, because they fail separately:

1. **Does the machinery run?** — the loop, the event stream, the controls.
2. **Is the output actually correct?** — not plausible-looking. Correct.
3. **Does it fail the way it promises to?** — loudly, never silently.

Everything below is reproducible from this repo.

## 1. Machinery — `backend/tests/test_loop.py`

Runs the full agent loop against the sandbox portal with a *scripted*
planner substituted for Claude, so it needs no API key and is deterministic.
It drives a real Chromium browser through a real login and asserts on the
event stream: steps are emitted, screenshots arrive, a deliberately invalid
click surfaces as an error, a mid-run steer message is echoed back, and the
finish payload survives intact.

```
$ python tests/test_loop.py
ALL LOOP ASSERTIONS PASSED  (26 events, 5 screenshots)
```

## 2. Correctness — `backend/tests/verify_extraction.py`

This is the one that matters. A browser agent can produce a table that looks
right and is wrong, and no amount of "the run completed" tells you which you
got. So the expected result is derived **independently** from the sandbox's
source data — dates re-parsed from four formats, European decimal commas and
Indian lakh grouping re-computed, status casing re-normalized — and then
compared to the agent's output field by field.

```
$ python tests/verify_extraction.py
PASS — 14 rows x 6 fields = 84 values, all match ground truth derived
independently from source data.
Includes the deliberate traps: duplicate invoice number INV-2050, credit
note CN-0107 (negative), 4 date formats, 3 currencies, inconsistent status
casing.
```

The sandbox portal is seeded with traps on purpose. The agent has to survive
all of them to pass:

| Trap | Why it's there |
| --- | --- |
| `INV-2050` used twice, different vendors | tests whether it flags or silently merges |
| `CN-0107` credit note, negative amount | tests whether it drops what doesn't fit |
| `2.450,00 EUR` vs `$1,240.50` vs `₹1,98,000` | three numbering conventions |
| `03/15/2026`, `2026-03-18`, `21.03.2026`, `Mar 24, 2026` | four date formats |
| `Paid` / `PAID` / `pending` / `overdue` | casing inconsistency |
| Records split across 3 paginated pages | tests completeness, not just page 1 |

Passing means it flagged the duplicate rather than deduping it, kept the
credit note as a negative rather than discarding it, and parsed all three
currency conventions correctly.

### External data cross-check

The "Compare company financials" task was verified against primary sources.
I read Apple's and Microsoft's actual 10-K filings on SEC EDGAR by hand and
recorded the figures in `backend/tests/ground_truth.md`, then compared the
agent's output:

| | Agent | SEC 10-K | Match |
| --- | --- | --- | --- |
| Apple FY2025 revenue | 416,161 | 416,161 | exact |
| Apple net income | 112,010 | 112,010 | exact |
| Apple diluted EPS | 7.46 | 7.46 | exact |
| Microsoft FY2026 revenue | 331,839 | 331,839 | exact |
| Microsoft net income | 133,749 | 133,749 | exact |
| Microsoft diluted EPS | 17.95 | 17.95 | exact |

The agent also computes net margin itself; both values re-derive correctly
(Apple 26.92%, Microsoft 40.31% — the agent displays 40.30%, truncating
rather than rounding the final digit).

## 3. Resilience — `backend/tests/test_resilience.py`

Every test here reproduces a bug that actually happened during this build.
They exist so those bugs cannot come back quietly.

```
$ python tests/test_resilience.py
Animated-page hang:
  PASS  screenshot of infinitely-animating page completes — 0.05s
  PASS  distill of 600-element page completes — 0.07s
Malformed model payload:
  PASS  string `notes` coerced to list
  PASS  malformed table row survives as strings
  PASS  unusable table dropped, not rendered wrong
  PASS  dropping the table is disclosed in notes
6 passed, 0 failed
```

**The hang.** A financial page with looping chart animations made
Playwright's screenshot call wait forever for a stability that never
arrived. The run froze: no error, no timeout, spinner spinning. That is a
silent failure wearing a spinner — precisely what this product promises
never to produce, and worse than a crash because nobody knows to intervene.
Fixed structurally rather than patched: every action, capture and page read
now carries a hard ceiling (45s / 12s / 25s), captures freeze animations,
and a timeout is handed to the agent as a fact it must route around.

**The malformed payload.** The model returned `notes` as a string where the
schema said list. The frontend called `.map()` on it and the entire UI went
black mid-run. Fixed in three layers: normalized at the source in
`agent.py`, guarded at the render in `Result.tsx`, and a React error
boundary as the final backstop so a display bug can never again present as
a dead app.

**The parallel tool call.** Claude occasionally emitted two tool calls in
one turn, which broke the conversation history contract and 400'd the next
request. One action per turn is a design invariant here — the human is
watching and can veto each step, so steps must be atomic — so it is now
enforced at the API level (`disable_parallel_tool_use`) rather than merely
requested in the prompt, with defensive handling if extra calls ever arrive.

## 4. Live production verification

Machinery tests pass with a scripted planner. That is not the same as the
real thing working, so every showcase task was also run against the deployed
instance with real Claude driving a real browser, and the output checked
against the tables above:

| Task | Result | Steps | Time |
| --- | --- | --- | --- |
| Reconcile messy invoices | 14/14 rows exact | 9 | 68s |
| Compare company financials | 6/6 figures exact vs 10-K | 3 | 37s |
| Research brief: Show HN | structured brief, live site | 2 | 22s |

## Running everything

```bash
cd backend
pip install -r requirements.txt && playwright install chromium
uvicorn app.main:app --port 8000 &     # tests 1 and 3 need the sandbox served

python tests/test_loop.py          # machinery
python tests/verify_extraction.py  # correctness vs ground truth
python tests/test_resilience.py    # regression suite

cd ../frontend && npx tsc -b       # frontend typecheck
```

## What isn't covered

Being straight about the gaps, since a test suite that claims everything is
worth less than one that names its edges:

- No unit tests on the distillation JavaScript itself; it's exercised
  end-to-end through the browser rather than in isolation.
- The scripted-planner tests pin the *machinery*, not Claude's judgment.
  Model behaviour is verified by the live runs in section 4, which are
  manual by nature.
- No load or concurrency testing. One browser per run is the current
  architecture, so contention isn't yet a meaningful question.
- The frontend has typechecking but no component tests. For a single-screen
  app under active demo use, live verification caught more than unit tests
  would have — including both production bugs above.
