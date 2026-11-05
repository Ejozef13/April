"""Loopback-only HTTP/WebSocket server; rejects cross-origin browser commands."""
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .backends import LocalBackends, SimulationBackends
from .config import load_config
from .session import Session


def create_app(config=None, backends=None):
    config = config or load_config()
    backends = backends or (SimulationBackends() if config.mode == "simulation" else LocalBackends(config))
    gate = asyncio.Lock()
    clients = set()

    @asynccontextmanager
    async def lifespan(app):
        yield
        for session in list(clients):
            try:
                await session.cancel()
            except (RuntimeError, WebSocketDisconnect):
                pass

    app = FastAPI(lifespan=lifespan)
    web = Path(__file__).parent / "web"

    @app.middleware("http")
    async def local_only(request, call_next):
        if request.url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            return JSONResponse({"error": "Use a local address or SSH tunnel"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; connect-src 'self'; media-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'"
        return response

    @app.get("/")
    async def index():
        return FileResponse(web / "index.html")

    @app.get("/api/config")
    async def settings():
        values={k: getattr(config, k) for k in ("mode", "model", "web_provider", "automatic_web_search", "context_tokens", "reasoning_effort", "max_response_tokens", "max_record_seconds", "display_width", "display_height", "input_device_id", "output_device_id")}
        values['integrations']={'web':True,
            'documents':bool(config.document_roots),'gmail':Path(config.gmail_token_path).expanduser().is_file()}
        return values

    @app.get("/health")
    async def health():
        return {"status": "ok", "mode": config.mode, "backend_verified": False}

    @app.get('/api/readiness')
    async def readiness():
        from .readiness import check_readiness
        return await check_readiness(config)

    @app.websocket("/ws")
    async def socket(ws: WebSocket):
        host = ws.headers.get("host", "")
        origin = ws.headers.get("origin")
        if ws.url.hostname not in {"localhost", "127.0.0.1", "::1"} or origin != "http://" + host:
            await ws.close(code=1008)
            return
        await ws.accept()
        session = Session(config, backends, ws.send_json, gate)
        clients.add(session)
        try:
            await ws.send_json({"type": "state", "state": "idle"})
            while True:
                raw = await ws.receive_text()
                if len(raw) > 1_400_000:
                    await ws.close(code=1009)
                    break
                try:
                    message = json.loads(raw)
                    if not isinstance(message, dict):
                        raise ValueError()
                    if message.get("type") == "playback_started":
                        await session.playback_started()
                    else:
                        await session.handle(message)
                except (ValueError, TypeError):
                    await ws.send_json({"type": "error", "message": "Invalid command."})
        except WebSocketDisconnect:
            pass
        finally:
            clients.discard(session)
            try:
                await session.cancel()
            except (RuntimeError, WebSocketDisconnect):
                pass

    app.mount("/static", StaticFiles(directory=web), name="static")
    return app


def main():
    import uvicorn
    config = load_config()
    uvicorn.run(create_app(config), host=config.host, port=config.port,
                ws_max_size=1_400_000, ws_max_queue=2, access_log=False)


if __name__ == "__main__":
    main()
