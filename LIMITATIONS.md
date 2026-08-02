# Limitations

I'd rather tell you where the edges are than have you find them. A submission
that names its own limits is easier to trust than one that implies it has
none — and every item here has either a workaround already in place or a
clear path to production.

Ordered by how likely you are to actually hit it.

---

## 1. SEC EDGAR is worked around, not solved

**What.** The "Compare company financials" task sources its numbers from
`stockanalysis.com`, not directly from SEC EDGAR. If you point the agent
straight at sec.gov from the deployed instance, it will fail.

**Why.** SEC's fair-access system blocks requests from datacenter IP ranges —
which is where any hosted backend (Railway, Render, Fly, AWS) lives. This is
**IP-level, not a bug in the agent**, and I proved that rather than assuming
it: I had the agent read its own User-Agent back from `httpbin.org` and
confirmed it was arriving correctly declared, and SEC still refused. The same
route works fine from a residential IP. (Full write-up: item 5 in
[BUGS.md](BUGS.md).)

**What it does instead of hiding it.** Point it at SEC anyway and watch —
it tries five distinct routes, diagnoses the block precisely, and reports
what it would need to proceed, rather than inventing numbers. That failure is
one of the better demonstrations of the transparency layer in the whole
build.

**Why the workaround is honest.** The figures from stockanalysis.com were
cross-checked field by field against the companies' actual 10-K filings —
all six exact ([TESTING.md](TESTING.md) §2). The data is identical; only the
source differs.

**Path to production.** A hosted-browser provider with residential egress
(Browserbase, Steel) restores the direct-EDGAR route without touching a line
of agent code — the fair-access wall is about *where the request comes from*,
not *what the agent does*.

---

## 2. Two of the four tasks depend on live sites I don't control

**What.** The sandbox invoice task is bulletproof — the target portal is
served by this same app, so it is deterministic and cannot flake. But the
financials task (stockanalysis.com) and the Show HN brief
(news.ycombinator.com) depend on those third-party sites being up and
structurally unchanged.

**Why.** They're real websites. If one restructures its page or has an outage
on a given day, the agent may have to work harder or, worst case, report that
it couldn't complete — honestly, but it's still a task that didn't finish for
reasons outside the code.

**How likely.** Low on any given day, but not zero, and genuinely outside my
control.

**Mitigation.** Lead any demo with the sandbox task, which cannot fail for
external reasons. Treat the live-site tasks as showing generality — the loop
has no task-specific code — rather than as the reliability centerpiece.

---

## 3. This is a demo-grade deployment, not production infrastructure

**What.** Real constraints, all deliberate for a take-home:

- **Two concurrent runs maximum** (`GLASSBOX_MAX_CONCURRENT`). Each run drives
  a real Chromium at ~380 MB resident, and the host has 1 GB. A third run
  would OOM-kill the container, so it's refused with a clear message instead.
  (This was found during load testing — item 4 in [BUGS.md](BUGS.md).)
- **Runs are in-memory.** Refreshing the page mid-run loses the feed; the run
  stops safely server-side. There's no database and no run history.
- **One browser per run**, no session pooling.
- **Railway trial credit.** The hosting is on a trial tier and should be
  checked before any scheduled review.

**Why.** The task was to demonstrate design, transparency and judgment on a
public link — not to stand up production infrastructure. Every one of these
is a known trade-off, not an oversight.

**Path to production.** Concurrency is a function of host memory, not code —
raise the cap on a bigger instance, or move to a hosted-browser pool to lift
it entirely behind the same event protocol. Run persistence is a database and
a resume endpoint; the event stream is already structured for it.

---

## 4. The agent can misread a page invented on the spot

**What.** On the tested tasks it's reliable. If you hand it something novel
and awkward live — an unusual layout, an ambiguous form, a page type it
hasn't seen — the model (Claude Sonnet) may misjudge a step.

**Why.** It's an LLM reasoning about a distilled page, not a hardcoded
scraper. That generality is the point — it's why there's no task-specific
code — but generality and perfect reliability on arbitrary input are in
tension. This is inherent to LLM agents, not specific to this one.

**What contains it.** This is exactly why the transparency and control layer
is the centerpiece rather than an afterthought. A misread step is *visible*
before or as it happens, and you can stop, reject with a correction, or steer
— which the adversarial tests confirm works ([TESTING.md](TESTING.md) §5).
The honest claim is "reliable on real tasks, and legible enough that you catch
it when it isn't," not "flawless."

**Path to improvement.** Swapping in vision (screenshots to the model
alongside the text distillation) is a ~20-line change and would help on
visually-structured pages; a stronger model tier trades cost for judgment.
Neither changes the architecture.

---

## 5. Deliberate scope choices

Not failures — decisions, listed so they're not mistaken for gaps:

- **No login-walled real-world targets.** The self-hosted sandbox covers the
  authenticated-workflow case deterministically, and it's the only honest way
  to demo login on a public link without someone's real credentials.
- **The model reads text, not screenshots.** A distilled DOM is cheaper,
  faster and less ambiguous to act on; the human gets the pixels because trust
  is visual. This is a design choice with a known trade-off (see item 4), not
  a missing feature.
- **Step limit of 40** (`GLASSBOX_MAX_STEPS`). Long research tasks can hit it;
  it's a guard against runaway loops, raisable per-deploy.
