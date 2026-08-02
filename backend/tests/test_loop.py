"""Machinery test: runs the full agent loop against the local sandbox with a
scripted planner instead of Claude. Proves browser actions, event stream,
approval gating, steering, error surfacing and finish — no API key needed.

Run:  python tests/test_loop.py   (server must be up on :8000)
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent import Run  # noqa: E402


class FakeBlock:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def model_dump(self):
        return dict(self.__dict__)


class FakeUsage:
    input_tokens = 100
    output_tokens = 50


class FakeResponse:
    def __init__(self, blocks):
        self.content = blocks
        self.usage = FakeUsage()


SCRIPT = [
    ("I'll open the sandbox portal to see the sign-in page.",
     "navigate", {"url": "http://localhost:8000/sandbox"}),
    ("The sign-in page shows demo credentials. I'll enter the username.",
     "type_text", {"element_id": 1, "text": "demo"}),
    ("Now the password.",
     "type_text", {"element_id": 2, "text": "meridian2026"}),
    ("Submitting the form.",
     "click", {"element_id": 3}),
    ("This click targets an element that no longer exists — to prove errors surface.",
     "click", {"element_id": 999}),
    ("That failed as expected; finishing with a small result table.",
     "finish", {"status": "success", "summary": "Logged in and read page one.",
                "table": {"columns": ["invoice", "vendor"],
                          "rows": [["INV-2041", "Northwind Traders"]]},
                "notes": ["error surfacing verified"]}),
]


class FakePlanner:
    def __init__(self):
        self.i = 0

    async def step(self, messages):
        reasoning, tool, inp = SCRIPT[min(self.i, len(SCRIPT) - 1)]
        self.i += 1
        return FakeResponse([
            FakeBlock(type="text", text=reasoning),
            FakeBlock(type="tool_use", id=f"tu_{self.i}", name=tool, input=inp),
        ])


async def main():
    events = []

    async def emit(e):
        events.append(e)
        kind = e["type"]
        if kind == "screenshot":
            print(f"  [screenshot: {len(e['data'])} b64 chars]")
        elif kind == "step":
            print(f"  step {e['n']}: {e['action']['tool'] if e['action'] else '-'} | {e['reasoning'][:60]}")
        elif kind in ("error", "result", "status", "action_result", "operator"):
            print(f"  {kind}: {str(e)[:110]}")

    run = Run("test goal", emit, mode="auto")
    run.planner = FakePlanner()

    # steer mid-run to prove injection works
    async def steer_later():
        await asyncio.sleep(1.5)
        await run.handle({"type": "steer", "text": "focus on page 1 only"})
    asyncio.get_event_loop().create_task(steer_later())

    await run.run()

    types = [e["type"] for e in events]
    assert "step" in types, "no steps emitted"
    assert "screenshot" in types, "no screenshots emitted"
    assert any(e["type"] == "error" for e in events), "bad click did not surface as error"
    result = [e for e in events if e["type"] == "result"][0]
    assert result["status"] == "success" and result["table"]["rows"], "finish payload lost"
    assert any(e["type"] == "operator" and e.get("kind") == "steer" for e in events), \
        "steer message not echoed"
    urls = [e.get("url", "") for e in events if e["type"] == "action_result"]
    assert any("/sandbox/invoices" in u for u in urls), "login flow did not reach invoices"
    print("\nALL LOOP ASSERTIONS PASSED  "
          f"({len(events)} events, {sum(1 for t in types if t=='screenshot')} screenshots)")


if __name__ == "__main__":
    asyncio.run(main())
