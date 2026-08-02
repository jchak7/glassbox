"""Glassbox server: one FastAPI app serving the SPA, the sandbox portal,
and the websocket that carries a run's full event stream."""

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .agent import Run
from .sandbox import router as sandbox_router

app = FastAPI(title="Glassbox")
app.include_router(sandbox_router)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@app.get("/api/health")
def health():
    return {"ok": True, "model": os.environ.get("GLASSBOX_MODEL", "claude-sonnet-5"),
            "key_present": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    run: Run | None = None
    run_task: asyncio.Task | None = None
    send_lock = asyncio.Lock()

    async def emit(event: dict):
        async with send_lock:
            try:
                await ws.send_text(json.dumps(event))
            except Exception:
                pass  # client gone; the run task gets cancelled below

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await emit({"type": "error", "message": "Malformed command.",
                            "recoverable": True})
                continue

            if msg.get("type") == "start":
                if run_task and not run_task.done():
                    await emit({"type": "error", "recoverable": True,
                                "message": "A run is already in progress on this "
                                           "connection. Stop it first."})
                    continue
                if not os.environ.get("ANTHROPIC_API_KEY"):
                    await emit({"type": "error", "recoverable": False,
                                "message": "Server is missing ANTHROPIC_API_KEY. "
                                           "Set it and restart."})
                    continue
                goal = (msg.get("goal") or "").strip()
                if not goal:
                    await emit({"type": "error", "message": "Empty goal.",
                                "recoverable": True})
                    continue
                # The agent's browser runs server-side, so a bare "/sandbox" in
                # a goal has no origin to resolve against. Resolve it here from
                # the server's own bind port rather than making the agent guess.
                port = os.environ.get("PORT", "8000")
                run = Run(goal, emit, mode=msg.get("mode", "auto"),
                          self_base_url=f"http://localhost:{port}")
                run_task = asyncio.create_task(run.run())
            elif run is not None:
                await run.handle(msg)
    except WebSocketDisconnect:
        pass
    finally:
        if run is not None:
            await run.handle({"type": "stop"})
        if run_task and not run_task.done():
            try:
                await asyncio.wait_for(run_task, timeout=10)
            except Exception:
                run_task.cancel()


# ---- SPA (built frontend) — mounted last so /api, /ws, /sandbox win ----

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        candidate = STATIC_DIR / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
else:
    @app.get("/")
    def no_frontend():
        return JSONResponse({"error": "frontend not built; run npm build"}, 500)
