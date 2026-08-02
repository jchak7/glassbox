"""The agent loop: plan with Claude, act with Playwright, narrate everything.

Every state change becomes an event on the wire. There is no code path that
fails without telling the operator — that is the contract this file keeps.
"""

import asyncio
import json
import os
import time

from .browser import BrowserSession
from .llm import Planner, compact_history

MAX_STEPS = int(os.environ.get("GLASSBOX_MAX_STEPS", "40"))
MAX_CONSECUTIVE_ERRORS = 6
LLM_TIMEOUT_S = 120


class Run:
    """One goal, one browser, one operator. Lives for the duration of a task."""

    def __init__(self, goal: str, emit, mode: str = "auto", headless: bool = True):
        self.goal = goal.strip()
        self.emit = emit                      # async fn(dict) -> None
        self.mode = mode                      # "auto" | "approve"
        self.controls = asyncio.Queue()       # inbound operator commands
        self.browser = BrowserSession(headless=headless)
        self.planner = Planner()
        self.stopped = False
        self.paused = False
        self.step_n = 0
        self.usage = {"input": 0, "output": 0}
        self._pending_notes: list[str] = []   # operator steer msgs awaiting delivery
        self._t0 = None

    # ---------------- operator commands ----------------

    async def handle(self, cmd: dict):
        """Called by the websocket layer whenever the operator sends a command."""
        await self.controls.put(cmd)

    async def _drain_controls(self, block: bool = False):
        """Apply queued operator commands. If paused, blocks until resume/stop."""
        while True:
            try:
                cmd = self.controls.get_nowait()
            except asyncio.QueueEmpty:
                if self.paused and not self.stopped and block:
                    cmd = await self.controls.get()
                else:
                    return
            await self._apply(cmd)
            if self.stopped:
                return

    async def _apply(self, cmd: dict):
        t = cmd.get("type")
        if t == "stop":
            self.stopped = True
            await self.emit({"type": "status", "status": "stopping",
                            "detail": "Stop requested by operator."})
        elif t == "pause":
            self.paused = True
            await self.emit({"type": "status", "status": "paused",
                            "detail": "Paused. The browser is holding its state."})
        elif t == "resume":
            self.paused = False
            await self.emit({"type": "status", "status": "running",
                            "detail": "Resumed."})
        elif t == "steer":
            text = (cmd.get("text") or "").strip()
            if text:
                self._pending_notes.append(text)
                await self.emit({"type": "operator", "kind": "steer", "text": text})
        elif t == "set_mode":
            self.mode = cmd.get("mode", self.mode)
            await self.emit({"type": "status", "status": "mode",
                            "detail": f"Mode set to {self.mode}."})

    async def _await_approval(self, action: dict) -> tuple[bool, str]:
        """Block until the operator approves or rejects the proposed action."""
        await self.emit({"type": "approval_request", "n": self.step_n, "action": action})
        while True:
            cmd = await self.controls.get()
            if cmd.get("type") == "approve":
                await self.emit({"type": "operator", "kind": "approve"})
                return True, ""
            if cmd.get("type") == "reject":
                fb = (cmd.get("feedback") or "Operator rejected this step.").strip()
                await self.emit({"type": "operator", "kind": "reject", "text": fb})
                return False, fb
            await self._apply(cmd)
            if self.stopped:
                return False, "stopped"
            if self.mode == "auto":
                # Operator flipped to autopilot mid-approval: release the gate.
                await self.emit({"type": "operator", "kind": "approve"})
                return True, ""

    # ---------------- main loop ----------------

    async def run(self):
        self._t0 = time.time()
        await self.emit({"type": "status", "status": "starting",
                        "detail": "Launching browser..."})
        try:
            await self.browser.start()
        except Exception as e:
            await self._finish("error", f"The browser failed to launch: {e}. "
                              "Nothing was executed.")
            return

        messages = [{"role": "user", "content":
                     f"GOAL: {self.goal}\n\nThe browser is open on a blank page. "
                     "Begin by explaining your plan in a sentence or two, then take "
                     "your first action."}]
        errors_in_a_row = 0
        recent_sigs: list[str] = []

        try:
            while self.step_n < MAX_STEPS and not self.stopped:
                await self._drain_controls(block=True)
                if self.stopped:
                    break

                # --- plan
                try:
                    resp = await asyncio.wait_for(
                        self.planner.step(compact_history(messages)),
                        timeout=LLM_TIMEOUT_S)
                except Exception as e:
                    errors_in_a_row += 1
                    await self.emit({"type": "error", "message":
                                    f"Planner call failed ({e}); retrying.",
                                    "recoverable": True})
                    if errors_in_a_row >= 3:
                        await self._finish("error",
                                           "The planning model is unreachable after "
                                           "repeated attempts. Run aborted cleanly.")
                        return
                    await asyncio.sleep(2 * errors_in_a_row)
                    continue

                self.usage["input"] += resp.usage.input_tokens
                self.usage["output"] += resp.usage.output_tokens
                await self.emit({"type": "usage", **self.usage})

                blocks = [b.model_dump() for b in resp.content]
                reasoning = " ".join(b["text"] for b in blocks if b["type"] == "text").strip()
                tool_uses = [b for b in blocks if b["type"] == "tool_use"]
                tool_use = tool_uses[0] if tool_uses else None
                # Defense in depth: parallel tool use is disabled at the API
                # level, but if extra calls ever arrive, answer them so the
                # conversation history stays valid instead of 400-ing.
                self._extra_results = [{
                    "type": "tool_result", "tool_use_id": x["id"], "is_error": True,
                    "content": "Not executed: one action per turn. Re-issue this "
                               "call on a later turn if still needed.",
                } for x in tool_uses[1:]]

                if tool_use is None:
                    # Model talked without acting — surface it, nudge it to act.
                    if reasoning:
                        await self.emit({"type": "step", "n": self.step_n,
                                        "reasoning": reasoning, "action": None})
                    messages.append({"role": "assistant", "content": blocks})
                    messages.append({"role": "user", "content":
                                     "Continue: call exactly one tool, or finish."})
                    continue

                self.step_n += 1
                action = {"tool": tool_use["name"], "input": tool_use["input"]}
                await self.emit({"type": "step", "n": self.step_n,
                                "reasoning": reasoning, "action": action})
                messages.append({"role": "assistant", "content": blocks})

                # --- stuck detection
                sig = json.dumps(action, sort_keys=True)
                recent_sigs = (recent_sigs + [sig])[-5:]
                if recent_sigs.count(sig) == 3:
                    note = ("You have proposed the exact same action three times. "
                            "It is not working. Explain what is blocking you and "
                            "take a different approach, or finish with an honest "
                            "failure report.")
                    messages.append(self._tool_result(tool_use["id"],
                                                      f"BLOCKED: {note}", error=True))
                    await self.emit({"type": "error", "message":
                                    "Loop detected: same action three times. "
                                    "Redirecting the agent.", "recoverable": True})
                    continue

                # --- human gate
                if self.mode == "approve" and action["tool"] != "finish":
                    ok, fb = await self._await_approval(action)
                    if self.stopped:
                        break
                    if not ok:
                        messages.append(self._tool_result(
                            tool_use["id"],
                            f"Operator rejected this action. Their instruction: {fb}",
                            error=True))
                        continue

                # --- finish
                if action["tool"] == "finish":
                    inp = tool_use["input"]
                    await self._finish(inp.get("status", "failure"),
                                       inp.get("summary", ""),
                                       table=inp.get("table"),
                                       notes=inp.get("notes"))
                    return

                # --- act
                ok, detail = await self._execute(action)
                if ok:
                    errors_in_a_row = 0
                else:
                    errors_in_a_row += 1
                    await self.emit({"type": "error", "n": self.step_n,
                                    "message": detail, "recoverable":
                                    errors_in_a_row < MAX_CONSECUTIVE_ERRORS})
                    if errors_in_a_row >= MAX_CONSECUTIVE_ERRORS:
                        await self._finish("error",
                                           f"Six consecutive actions failed; last error: "
                                           f"{detail}. Stopping rather than thrashing.")
                        return

                await self.emit({"type": "action_result", "n": self.step_n, "ok": ok,
                                "detail": detail[:300], "url": self.browser.page.url})
                try:
                    shot = await self.browser.screenshot_b64()
                    await self.emit({"type": "screenshot", "n": self.step_n,
                                    "data": shot, "url": self.browser.page.url})
                except Exception:
                    pass  # a missing frame is cosmetic; the run continues

                messages.append(self._tool_result(tool_use["id"],
                                                  await self._observation(ok, detail),
                                                  error=not ok))

            if not self.stopped:
                await self._finish("failure",
                                   f"Step limit ({MAX_STEPS}) reached before the goal "
                                   "was met. Partial progress is in the log above.")
            else:
                await self._finish("stopped", "Run stopped by the operator. "
                                   "No further actions were taken.")
        finally:
            await self.browser.close()

    # ---------------- helpers ----------------

    async def _execute(self, action: dict) -> tuple[bool, str]:
        tool, inp = action["tool"], action["input"]
        b = self.browser
        try:
            if tool == "navigate":
                url = inp["url"]
                if url.startswith("/"):
                    from urllib.parse import urljoin
                    url = urljoin(b.page.url, url)
                await b.goto(url)
                return True, f"Navigated to {b.page.url}"
            if tool == "click":
                await b.click(int(inp["element_id"]))
                return True, f"Clicked [{inp['element_id']}]"
            if tool == "type_text":
                await b.type_text(int(inp["element_id"]), inp["text"],
                                  bool(inp.get("press_enter")))
                return True, f"Typed into [{inp['element_id']}]"
            if tool == "select_option":
                await b.select_option(int(inp["element_id"]), inp["value"])
                return True, f"Selected {inp['value']!r}"
            if tool == "scroll":
                await b.scroll(inp.get("direction", "down"))
                return True, "Scrolled"
            if tool == "read_more":
                return True, "Read next chunk of document text"
            if tool == "go_back":
                await b.go_back()
                return True, "Went back"
            return False, f"Unknown tool {tool!r}"
        except Exception as e:
            return False, f"{tool} failed: {str(e)[:200]}"

    async def _observation(self, ok: bool, detail: str) -> str:
        """Build the tool_result content: outcome + fresh page state + operator notes."""
        if detail == "Read next chunk of document text":
            chunk = self.browser.read_more()
            state = (f"[document text, offset {chunk['offset']}]\n{chunk['text']}\n"
                     f"(text_remaining: {chunk['text_remaining']})")
        else:
            d = await self.browser.distill()
            state = (f"URL: {d['url']}\nTITLE: {d.get('title','')}\n"
                     f"SCROLL: {d.get('scroll','')}\n"
                     f"INTERACTIVE ELEMENTS:\n{d.get('elements_desc','')}\n\n"
                     f"PAGE TEXT (excerpt):\n{d.get('text','')}\n"
                     f"(text_remaining: {d.get('text_remaining', 0)})")
        prefix = f"{'OK' if ok else 'FAILED'}: {detail}\n\n"
        notes = ""
        if self._pending_notes:
            notes = "\n\nMESSAGES FROM OPERATOR (address these):\n- " + \
                    "\n- ".join(self._pending_notes)
            self._pending_notes = []
        return prefix + state + notes

    def _tool_result(self, tool_use_id: str, content: str, error: bool = False) -> dict:
        blocks = [{"type": "tool_result", "tool_use_id": tool_use_id,
                   "content": content, "is_error": error}]
        blocks += getattr(self, "_extra_results", [])
        self._extra_results = []
        return {"role": "user", "content": blocks}

    async def _finish(self, status: str, summary: str, table=None, notes=None):
        await self.emit({
            "type": "result", "status": status, "summary": summary,
            "table": table, "notes": notes or [],
            "steps": self.step_n,
            "duration_s": round(time.time() - self._t0, 1) if self._t0 else 0,
            "usage": self.usage,
        })
