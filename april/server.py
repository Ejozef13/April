"""Loopback-only HTTP/WebSocket server; rejects cross-origin browser commands."""
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .backends import LocalBackends, SimulationBackends
from .config import load_config
from .session import Session


def create_app(config=None, backends=None):
    config = config or load_config()
    backends = backends or (SimulationBackends() if config.mode == "simulation" else LocalBackends(config))
    from .memory import MemoryStore
    memory = MemoryStore(config)
    gate = asyncio.Lock()
    clients = set()
    peers = {}

    async def notify():
        while True:
            await asyncio.sleep(30)
            if not clients or gate.locked():continue
            peer=next((ws for ws in peers.values() if ws.query_params.get('client')=='widget'),next(iter(peers.values()),None))
            if not peer:continue
            try:
                for note in memory.notifications():
                    await asyncio.wait_for(peer.send_json({'type':'memory_notification',**note}),1)
                    memory.delivered(note['id'])
            except (OSError,ValueError,RuntimeError,TimeoutError,WebSocketDisconnect):
                pass

    @asynccontextmanager
    async def lifespan(app):
        notifier=asyncio.create_task(notify())
        try:yield
        finally:
            notifier.cancel()
            await asyncio.gather(notifier,return_exceptions=True)
        await memory.close()
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
        values={k: getattr(config, k) for k in ("avatar_3d", "avatar_model_url", "mode", "model", "web_provider", "automatic_web_search", "context_tokens", "reasoning_effort", "max_response_tokens", "max_record_seconds", "display_width", "display_height", "input_device_id", "output_device_id")}
        values['memory_enabled']=memory.enabled
        values['integrations']={'web':True,
            'documents':bool(config.document_roots),'gmail':Path(config.gmail_token_path).expanduser().is_file(),
            'calendar':Path(config.caldav_credentials).expanduser().is_file()}
        return values

    @app.post("/api/debug/check")
    async def debug_check(request: Request):
        origin=request.headers.get('origin')
        if origin and origin!=str(request.base_url).rstrip('/'):
            return JSONResponse({'error':'Local origin required'},status_code=403)
        try:
            raw=bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw)>4096:raise ValueError('Request too large')
            data=json.loads(raw)
            if not isinstance(data,dict) or set(data)!={'file'}:raise ValueError('Invalid request')
            from .debugging import review_file
            source,_=await asyncio.to_thread(review_file,config,data['file'])
            return {'diagnostics':[source['diagnostic']] if source['diagnostic'] else []}
        except (ValueError,OSError,TypeError):
            return JSONResponse({'error':'Use a saved Python file inside the approved root'},status_code=400)

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
        async def send(message):
            is_state=message.get('type')=='state'
            try:
                await ws.send_json({**message,'busy':gate.locked()} if is_state else message)
            finally:
                if is_state:
                    # Availability only: never broadcast transcripts/private sources.
                    await asyncio.gather(*(asyncio.wait_for(peer.send_json(
                        {'type':'availability','busy':gate.locked()}),.5)
                        for peer in list(peers.values()) if peer is not ws),return_exceptions=True)
        session = Session(config, backends, send, gate, memory=memory)
        clients.add(session)
        peers[session]=ws
        try:
            await ws.send_json({"type": "state", "state": "idle","busy":gate.locked()})
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
            peers.pop(session,None)
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
                ws_max_size=1_400_000, ws_max_queue=2, access_log=False, timeout_graceful_shutdown=5)


if __name__ == "__main__":
    main()
