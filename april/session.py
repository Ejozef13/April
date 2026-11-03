"""One interaction per server, no queue; events and audio expire with the socket."""
import asyncio
import base64
import tempfile
import time
from pathlib import Path

from .audio import validate_wav
from .state import State, StateMachine
from .tools import current_time


class Session:
    def __init__(self, config, backends, send, gate):
        self.config, self.backends, self.send, self.gate = config, backends, send, gate
        self.machine = StateMachine()
        self.task = None
        self.owns_gate = False
        self.record_timer = None

    async def state(self, value):
        self.machine.move(value)
        await self.send({"type": "state", "state": value})

    def release(self):
        if self.record_timer:
            self.record_timer.cancel()
            self.record_timer = None
        if self.owns_gate:
            self.gate.release()
            self.owns_gate = False

    async def cancel(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        self.release()
        await self.state(State.IDLE)

    async def error(self, message):
        self.release()
        await self.state(State.ERROR)
        await self.send({"type": "error", "message": message})

    async def begin(self, recording=False):
        if self.owns_gate or self.gate.locked():
            await self.send({"type": "error", "message": "April is busy. Stop the current interaction first."})
            return False
        await self.gate.acquire()
        self.owns_gate = True
        if self.machine.state == State.ERROR:
            await self.state(State.IDLE)
        if recording:
            await self.state(State.LISTENING)
            self.record_timer = asyncio.create_task(self.record_deadline())
        return True

    async def record_deadline(self):
        await asyncio.sleep(self.config.max_record_seconds + 3)
        self.record_timer = None
        await self.error("Recording expired. Check microphone permissions and try again.")

    async def handle(self, message):
        action = message.get("type")
        if action == "cancel":
            await self.cancel()
        elif action == "record":
            await self.begin(recording=True)
        elif action == "played" and self.machine.state == State.SPEAKING:
            await self.cancel()
        elif action == "audio":
            if self.machine.state != State.LISTENING:
                await self.send({"type": "error", "message": "Start recording before sending audio."})
                return
            if self.record_timer:
                self.record_timer.cancel()
                self.record_timer = None
            try:
                encoded = message.get("audio", "")
                if not isinstance(encoded, str) or len(encoded) > 1_300_000:
                    raise ValueError("Recording too large")
                data = base64.b64decode(encoded, validate=True)
                validate_wav(data, self.config.max_record_seconds)
            except (ValueError, TypeError) as exc:
                await self.error(str(exc))
                return
            await self.state(State.TRANSCRIBING)
            self.task = asyncio.create_task(self.run(audio=data))
        elif action in {"text", "time"}:
            text = message.get("text", "")
            if action == "text" and (not isinstance(text, str) or not text.strip() or len(text) > 2000):
                await self.send({"type": "error", "message": "Enter 1–2000 characters."})
                return
            if await self.begin():
                self.task = asyncio.create_task(self.run(text=text.strip(), tool=action == "time", arguments=message.get("arguments", {})))
        else:
            await self.send({"type": "error", "message": "Unknown or out-of-order action."})

    async def run(self, text="", audio=None, tool=False, arguments=None):
        timings = {}
        started = time.perf_counter()
        try:
            async with asyncio.timeout(self.config.timeout_seconds):
                with tempfile.TemporaryDirectory(prefix="april-") as directory:
                    root = Path(directory)
                    if audio is not None:
                        recording = root / "input.wav"
                        recording.write_bytes(audio)
                        tick = time.perf_counter()
                        text = await self.backends.transcribe(recording)
                        timings["stt_ms"] = round((time.perf_counter() - tick) * 1000, 1)
                    await self.send({"type": "transcript", "text": "What time is it?" if tool else text})
                    await self.state(State.THINKING)
                    tick = time.perf_counter()
                    reply = current_time(arguments, self.config.timezone) if tool else await self.backends.respond(text)
                    timings["tool_ms" if tool else "llm_ms"] = round((time.perf_counter() - tick) * 1000, 1)
                    await self.send({"type": "reply", "text": reply, "source": "current_time" if tool else self.config.mode})
                    output = root / "reply.wav"
                    tick = time.perf_counter()
                    await self.backends.synthesize(reply, output)
                    timings["tts_ms"] = round((time.perf_counter() - tick) * 1000, 1)
                    timings["server_total_ms"] = round((time.perf_counter() - started) * 1000, 1)
                    await self.send({"type": "timings", "values": timings, "mode": self.config.mode})
                    # Speaking starts only on the client's playback-start acknowledgment.
                    if self.config.mode == "simulation":
                        await self.send({"type": "simulation", "message": "Speech playback simulated; no TTS audio."})
                        self.release()
                        await self.state(State.IDLE)
                    else:
                        await self.send({"type": "audio", "audio": base64.b64encode(output.read_bytes()).decode()})
                        # Wait for client playback events with an independent timeout.
                        self.task = asyncio.create_task(self.playback_deadline())
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Never expose exception bodies, prompts, paths or remote responses.
            hints = {FileNotFoundError: "Speech binary or model missing. Check local configuration.",
                     TimeoutError: "Request timed out. Try a shorter request.",
                     ValueError: "Input or model output was invalid. Check configuration and retry."}
            await self.error(hints.get(type(exc), "Local backend failed. Check Ollama, speech binaries and model paths; then retry."))

    async def playback_deadline(self):
        await asyncio.sleep(self.config.playback_timeout_seconds)
        await self.error("Playback timed out. Check the selected output and retry.")

    async def playback_started(self):
        if self.owns_gate and self.machine.state == State.THINKING:
            await self.state(State.SPEAKING)
