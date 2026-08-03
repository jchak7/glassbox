"""Resilience tests: the failure modes that matter most for an agent whose
core promise is "no silent failures."

Each of these reproduces a bug that actually occurred during the build.
They exist so those bugs cannot come back quietly.

Run:  python tests/test_resilience.py
"""

import asyncio
import http.server
import socketserver
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.browser import BrowserSession  # noqa: E402
from app.agent import Run  # noqa: E402

PASSED, FAILED = [], []


def check(name: str, ok: bool, detail: str = ""):
    (PASSED if ok else FAILED).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{' — ' + detail if detail else ''}")


# --- A page that animates forever. Used to hang screenshot capture. --------
ANIMATED = ("<html><head><style>@keyframes s{0%{transform:rotate(0)}"
            "100%{transform:rotate(360deg)}}.c{animation:s 1s linear infinite;"
            "width:40px;height:40px;background:#333}</style></head><body>"
            + "".join(f'<div class="c"></div><a href="#{i}">link {i}</a>'
                      for i in range(300)) + "</body></html>")


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(ANIMATED.encode())

    def log_message(self, *a):
        pass


async def test_no_hang_on_animated_page():
    """Regression: looping CSS animations made Playwright wait forever for a
    stability that never arrives. The run froze with no error — a silent
    failure wearing a spinner, the one outcome this agent must never produce."""
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), _Handler)  # OS picks a free port
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    b = BrowserSession()
    try:
        await b.start()
        await b.goto(f"http://127.0.0.1:{port}/")
        t0 = time.time()
        shot = await asyncio.wait_for(b.screenshot_b64(), timeout=15)
        elapsed = time.time() - t0
        check("screenshot of infinitely-animating page completes",
              len(shot) > 1000 and elapsed < 15, f"{elapsed:.2f}s")
        t0 = time.time()
        d = await asyncio.wait_for(b.distill(), timeout=25)
        check("distill of 600-element page completes",
              len(d["elements_desc"]) > 0, f"{time.time() - t0:.2f}s")
    finally:
        await b.close()
        srv.shutdown()


async def test_recovers_from_page_crash():
    """Regression: on a constrained host a very heavy page can OOM the renderer
    and crash the tab. A crashed page object is dead — every later action on it
    fails too — so a naive agent aborts the whole run. The browser now rebuilds
    the context on a crash and the agent re-navigates, turning a fatal crash
    into a recoverable blip."""
    from app.agent import Run
    b = BrowserSession()
    try:
        await b.start()
        # recreate_page must yield a working page
        await b.recreate_page()
        await b.goto("about:blank")
        check("recreate_page yields a live page", not b.page.is_closed())

        # simulate the tab dying, then drive the real executor
        await b.page.close()
        run = Run("x", lambda e: asyncio.sleep(0))
        run.browser = b
        ok1, d1 = await run._execute({"tool": "navigate", "input": {"url": "about:blank"}})
        check("dead page is detected and reset", "reset" in d1.lower() and not ok1)
        ok2, _ = await run._execute({"tool": "navigate", "input": {"url": "about:blank"}})
        check("run continues after recovery", ok2)
    finally:
        await b.close()


async def test_malformed_payload_does_not_crash():
    """Regression: the model returned `notes` as a string instead of a list.
    The frontend called .map() on it and the whole UI went black mid-demo.
    Payloads are now normalized at the source."""
    events = []

    async def emit(e):
        events.append(e)

    run = Run("test", emit)
    await run._finish("success", "summary",
                      table={"columns": ["A", "B"], "rows": [["1", "2"], "not-a-list"]},
                      notes="I am a string, not a list")
    result = events[-1]
    check("string `notes` coerced to list", isinstance(result["notes"], list),
          repr(result["notes"])[:60])
    check("malformed table row survives as strings",
          all(isinstance(r, list) for r in result["table"]["rows"]))

    events.clear()
    run2 = Run("test", emit)
    await run2._finish("failure", "no data", table={"columns": "bad", "rows": None},
                       notes=None)
    r2 = events[-1]
    check("unusable table dropped, not rendered wrong", r2["table"] is None)
    check("dropping the table is disclosed in notes",
          any("malformed" in n.lower() for n in r2["notes"]))


async def main():
    print("\nResilience suite — regressions for bugs found in production\n")
    print("Animated-page hang:")
    await test_no_hang_on_animated_page()
    print("\nRenderer crash recovery:")
    await test_recovers_from_page_crash()
    print("\nMalformed model payload:")
    await test_malformed_payload_does_not_crash()
    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("FAILED:", ", ".join(FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
