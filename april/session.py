"""One interaction per server, no queue; events and audio expire with the socket."""
import asyncio
import base64
import tempfile
import time
from pathlib import Path

from .audio import validate_wav
from .state import State, StateMachine
from .tools import current_time, is_time_request
from .errors import BackendError
from .knowledge import route_knowledge, retrieve


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

    async def error(self, message, code='interaction_failed'):
        self.release()
        await self.state(State.ERROR)
        await self.send({"type": "error", "message": message, "code": code})

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
        elif action in {"text", "time", "web", "documents", "gmail"}:
            text = message.get("text", "")
            if action != "time" and (not isinstance(text, str) or not text.strip() or len(text) > 2000):
                await self.send({"type": "error", "message": "Enter 1–2000 characters."})
                return
            if await self.begin():
                self.task = asyncio.create_task(self.run(text=text.strip(), tool=action == "time", arguments=message.get("arguments", {}),search_action=action if action in {'web','documents','gmail'} else None))
        else:
            await self.send({"type": "error", "message": "Unknown or out-of-order action."})

    async def run(self, text="", audio=None, tool=False, arguments=None,search_action=None):
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
                    # Spoken/typed clock queries must use the actual clock,
                    # not the model's training data. Preserve the real transcript.
                    if not tool and not search_action and is_time_request(text):
                        tool, arguments = True, {}
                    await self.state(State.THINKING)
                    tick = time.perf_counter()
                    sources=[]
                    model_called=False
                    if not tool:
                        detected,query=route_knowledge(text)
                        action=search_action or detected
                        if action:
                            if self.config.mode=='simulation':
                                raise BackendError('simulation_search_disabled','Private/external retrieval is disabled in simulation. Use live mode after local setup.')
                            query=text if search_action else query
                            sources=await retrieve(self.config,action,query)
                            timings['retrieval_ms']=round((time.perf_counter()-tick)*1000,1)
                            await self.send({'type':'sources','sources':sources})
                            tick=time.perf_counter()
                            if sources:
                                reply=await self.backends.respond(text,sources=sources)
                                model_called=True
                            else:reply='No matching sources were returned. I cannot verify an answer from this search.'
                        else:
                            reply=await self.backends.respond(text)
                            model_called=True
                    else:reply=current_time(arguments,self.config.timezone)
                    if tool or model_called:
                        timings["tool_ms" if tool else "llm_ms"] = round((time.perf_counter() - tick) * 1000, 1)
                    await self.send({"type": "reply", "text": reply, "source": "current_time" if tool else ('retrieval' if action else self.config.mode)})
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
        except BackendError as exc:
            await self.error(str(exc), exc.code)
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
