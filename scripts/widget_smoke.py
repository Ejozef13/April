"""Actual offscreen QtWebEngine + fixture server; no mic/model claim."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import asyncio
import base64
import io
from pathlib import Path
import socket
import sys
import threading
import time
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
import uvicorn
from april.backends import SimulationBackends
from april.config import Config
from april.desktop import Companion
from april.server import create_app


def main():
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    config = Config(mode='simulation', port=port)
    server = uvicorn.Server(uvicorn.Config(create_app(config, SimulationBackends()), log_level='warning'))
    thread = threading.Thread(target=lambda: asyncio.run(server.serve(sockets=[sock])), daemon=True)
    thread.start()
    until = time.monotonic() + 10
    while not server.started and time.monotonic() < until:
        time.sleep(.05)
    if not server.started:
        raise RuntimeError('Fixture server failed to start')
    app = QApplication([])
    window = Companion(config, f'http://127.0.0.1:{port}', microphone=False)
    def wait(expression, predicate, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = []
            window.page.runJavaScript(expression, lambda value: result.append(value))
            while not result and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(.01)
            if result and predicate(result[0]):
                return result[0]
            app.processEvents()
            time.sleep(.05)
        raise AssertionError('Widget check timed out: ' + expression)
    try:
        wait('window.aprilDesktop?.snapshot().connected', bool)
        wait("document.body.classList.contains('desktop-widget')", bool)
        wait("getComputedStyle(document.querySelector('#text-form')).display", lambda v: v == 'none')
        wait("JSON.stringify(window.aprilDesktop.snapshot())", lambda v: isinstance(v, str) and 'connected' in v)
        window.activate()
        wait("document.querySelector('#reply').textContent", lambda v: isinstance(v, str) and '[Simulated reply]' in v)
        wait("document.body.dataset.state", lambda v: v == 'idle')
        window.reveal()
        app.processEvents()
        for _ in range(40):
            app.processEvents()
            time.sleep(.01)
        assert 'SIMULATION' in window.status.text()
        window.grab().save('/tmp/april-widget-simulation.png')
        # Begin + native WAV bridge: a tone/silence fixture, not microphone capture.
        epoch = wait('window.aprilDesktop.begin()', lambda v: isinstance(v, (float, int)) and v >= 0)
        wait("document.body.dataset.state", lambda v: v == 'listening')
        stream = io.BytesIO()
        with wave.open(stream, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
            wav.writeframes(bytes(6400))
        # Stale generations must not submit audio or animate another turn.
        window.deliver_audio(base64.b64encode(stream.getvalue()).decode(), int(epoch) - 1)
        wait("document.body.dataset.state", lambda v: v == 'listening')
        window.js('window.aprilDesktop.level(.1,' + str(int(epoch)) + ')')
        wait("document.body.classList.contains('input-active')", bool)
        window.deliver_audio(base64.b64encode(stream.getvalue()).decode(), int(epoch))
        wait("document.querySelector('#transcript').textContent",
             lambda v: isinstance(v, str) and '[Simulated transcript]' in v)
        wait("document.body.dataset.state", lambda v: v == 'idle')
        window.dismiss()
        app.processEvents()
        window.retry()
        window.reveal()
        app.processEvents()
        assert window.isVisible()
        print('Qt native widget: connected, compact face, simulated reply, native-WAV bridge, dismiss/restore passed.')
        print('Screenshot /tmp/april-widget-simulation.png is SIMULATION; no mic/wake/model test.')
    finally:
        window.dispose()
        app.processEvents()
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == '__main__':
    main()
