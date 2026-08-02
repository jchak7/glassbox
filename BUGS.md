# Bugs found while building this

Every one of these was found by testing against reality rather than by
reading the code, and every one is now pinned by a test. I'm listing them
because a build with no recorded failures usually means nobody looked hard,
and because how a bug was *closed* says more than whether it existed.

Ordered by how much damage each would have done unnoticed.

---

## 1. The hang — a silent failure wearing a spinner

**Severity:** would have killed the live demo.

**Found:** running the financials task against a real page for the first
time. It pulled Apple's numbers correctly, then froze on Microsoft's page.
Not slow — frozen. Token count stopped moving, no screenshot, no error, no
timeout. The spinner kept spinning.

**Cause:** `stockanalysis.com` renders continuously-animating charts.
Playwright's `page.screenshot()` waits for the page to reach visual
stability before capturing, and on that page stability never arrives. There
was no timeout on the call, so the run parked there forever.

**Why it mattered more than a crash:** this product's entire promise is "no
silent failures." A crash is loud and recoverable. A hang looks like work in
progress, so nobody intervenes — it is the single worst outcome the design
can produce, and it was sitting in the happy path.

**Fix — structural, not a patch.** Patching just the screenshot call would
have left the same class of bug everywhere else. Instead every awaited
operation now carries a hard ceiling: 45s per browser action, 12s per
screenshot capture, 25s per page read. Captures freeze animations
(`animations="disabled"`). A timeout is not swallowed — it is handed to the
agent as a fact it must route around ("this page could not be read in time,
try another route"), and surfaced to the human in the feed.

**Pinned by:** `tests/test_resilience.py` — serves a page with an infinite
CSS animation and 600 elements, asserts capture completes. It used to hang;
it now returns in ~0.05s.

---

## 2. Malformed model output blanked the entire UI

**Severity:** would have looked like a total product failure mid-demo.

**Found:** a production run on Railway. The result panel never appeared —
just a black screen. The run itself had completed fine server-side.

**Cause:** the model returned `notes` as a plain string where the schema
said list of strings. The frontend called `.map()` on it, React threw, and
the whole tree unmounted. One malformed field took down the entire
interface.

**Fix — three layers, because one is a single point of failure.** Payloads
are normalized at the source in `agent.py` (a string becomes a one-item
list; an unusable table is dropped *and the drop is disclosed in the notes*
rather than silently swallowed). The render path in `Result.tsx` guards
independently. A React error boundary wraps the app so any future rendering
bug degrades to a readable message with a reload button instead of a dead
screen.

**Worth noting:** this only appeared with real model output. No scripted
test would have produced it, because I wrote the scripts to match my own
schema. Reality doesn't.

**Pinned by:** `tests/test_resilience.py` — feeds deliberately malformed
payloads through the finish path and asserts the UI contract survives.

---

## 3. Parallel tool calls broke the conversation contract

**Severity:** run-ending, but loud.

**Found:** the very first end-to-end run with real Claude. Two steps in, the
API started returning `400: tool_use ids were found without tool_result
blocks`.

**Cause:** Claude occasionally emitted two `tool_use` blocks in one turn.
The loop executed the first and answered only that one, leaving the second
unanswered — which violates the Messages API contract, so every subsequent
request failed.

**Why the fix isn't "handle both":** one action per turn is a *design
invariant* here, not an implementation detail. The human is watching each
step and can veto it, so steps must be atomic and individually
approvable. Executing two actions per turn would quietly break the approval
model.

**Fix:** enforced at the API level with
`tool_choice: {disable_parallel_tool_use: true}` rather than merely
requested in the prompt, plus defensive handling that answers any extra
calls with an explicit "not executed, one action per turn" result so the
history stays valid even if the constraint is ever lifted.

---

## 4. Concurrent runs would OOM-kill the server

**Severity:** would have taken down a live demo if two people opened the
link at once.

**Found:** deliberately, during adversarial testing. Three simultaneous runs
all completed correctly — so I measured what they cost. Resident memory:
**~377 MB per concurrent Chromium**. The deploy host has 1 GB.

**Cause:** nothing was limiting concurrency. Two runs fit. A third pushes
the container past its memory ceiling, and the OOM killer takes down *every*
session — including the one being demoed.

**Fix:** capacity is refused rather than discovered by crashing. Runs beyond
`GLASSBOX_MAX_CONCURRENT` (default 2) get an explicit message — "the demo
server is at capacity, each run drives a real browser" — instead of a dead
server. `/api/health` reports `active_runs` and `max_concurrent` so the
limit is observable rather than a mystery.

**Verified:** four simultaneous runs against a two-run limit — two
succeeded, two were refused politely, nothing crashed.

---

## 5. SEC EDGAR blocks the host — not a bug, but I chased it like one

**Severity:** cost me a showcase task.

**Found:** the SEC filings task failed in production while working from a
residential IP.

**Diagnosis:** the agent's own report suggested the User-Agent. That was a
reasonable hypothesis — SEC's fair-access policy does require automated
clients to declare themselves — so I set a compliant declared UA
(`Glassbox-Agent/1.0 (contact: ...)`). It still failed.

Rather than guess again, I made the agent read back its own identity from
`httpbin.org/user-agent`. The declared UA was arriving perfectly. SEC was
still refusing. That isolates it: the block is **IP-level**, targeting
datacenter ranges, and no code change can fix it.

**Resolution:** rather than fake the demo, I sourced the same figures from a
reachable provider and cross-checked all six against the actual 10-K
filings — exact match. The declared User-Agent stayed, because it is correct
behaviour regardless.

**Why it's listed here:** the useful part wasn't the fix, it was refusing to
accept a plausible diagnosis without isolating the variable. The agent's
guess was wrong, and it would have been easy to ship a "fix" that changed
nothing.

---

## 6. The agent hunted for its own server's port

**Severity:** cosmetic, but wasteful.

**Found:** watching a production run. The sandbox goal says "the portal at
/sandbox", and the agent's browser starts on a blank page — so a bare path
has no origin to resolve against. It tried `localhost/sandbox`, then
`localhost:3000`, got connection refused, and eventually found port 8080 by
itself.

**Silver lining:** this was unscripted recovery working exactly as designed,
and it's genuinely good to have watched it happen.

**Fix:** the server now tells the agent its own address when a goal
references `/sandbox`. Recovery is a safety net, not a substitute for giving
the agent the information it needs.

---

## 7. A flaw in my own adversarial test

**Found:** the operator-correction scenario failed once — but the product
was fine (it still returned 14/14 rows). The test rejected "the first
*click* after step 5", and on that run the model paginated by URL instead of
clicking, so the rejection never fired.

**Fix:** the test now rejects the first post-login action whatever tool it
uses. A test that depends on which valid path a model chooses is a flaky
test, and a flaky test is worse than no test — it trains you to ignore red.

**Listed because** the same discipline applies to test code as product code,
and because "the test was wrong" is a real finding worth recording rather
than quietly editing away.
