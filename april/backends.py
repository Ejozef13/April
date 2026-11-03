"""Adapters run serially. Canceling a job terminates its speech subprocess.

Ollama is shared: closing our HTTP stream cancels our request; never stop its
service or unload a model another application may be using.
"""
import asyncio
import json
import os
import signal
from pathlib import Path

import httpx

from .config import Config


async def run_process(*args: str, input_data: bytes | None = None):
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL, start_new_session=True,
        stdin=asyncio.subprocess.PIPE if input_data is not None else asyncio.subprocess.DEVNULL,
    )
    try:
        await process.communicate(input_data)
        code = process.returncode
        if code:
            raise RuntimeError("Speech process failed; check binary/model compatibility")
    finally:
        if process.returncode is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), 2)
            except TimeoutError:
                os.killpg(process.pid, signal.SIGKILL)
                await process.wait()


class LocalBackends:
    def __init__(self, config: Config):
        self.config = config

    async def transcribe(self, audio: Path) -> str:
        output = audio.parent / "transcript"
        await run_process(self.config.whisper_cli, "-m", self.config.stt_model,
                          "-f", str(audio), "-otxt", "-of", str(output), "-nt", "-t", "4")
        text = output.with_suffix(".txt").read_text().strip()
        if not text:
            raise ValueError("No speech recognized. Check the microphone and try again")
        return text[:2000]

    async def respond(self, text: str) -> str:
        payload = {
            "model": self.config.model, "stream": True,
            "messages": [
                {"role": "system", "content": "You are April, a playful, curious, affectionate Jack Russell companion. Give useful answers in 1–3 short sentences. Do not claim to access tools, devices, live facts or memory. No barking in every answer."},
                {"role": "user", "content": text},
            ],
            "options": {"num_predict": self.config.max_response_tokens, "num_ctx": self.config.context_tokens},
        }
        # GPT-OSS supports effort levels. Omit this field for other models unless
        # explicitly configured; their supported thinking settings can differ.
        if self.config.reasoning_effort != "default":
            payload["think"] = self.config.reasoning_effort
        result = ""
        # Local requests must not traverse the cloud's external HTTP proxy.
        async with httpx.AsyncClient(trust_env=False, timeout=self.config.timeout_seconds) as client:
            async with client.stream("POST", self.config.ollama_url + "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if len(line) > 65536:
                        raise ValueError("Oversized model response")
                    if line:
                        item = json.loads(line)
                        if "error" in item:
                            raise RuntimeError("Ollama could not generate a response")
                        # Only the final answer is displayed or spoken. Never
                        # collect or persist the separate `thinking` field.
                        result += item.get("message", {}).get("content", "")
                        if len(result) >= self.config.max_response_chars:
                            break
        if not result.strip():
            raise ValueError("The model returned an empty response")
        return result.strip()[:self.config.max_response_chars]

    async def synthesize(self, text: str, output: Path):
        await run_process(self.config.piper_cli, "--model", self.config.voice,
                          "--output_file", str(output), input_data=text.encode())
        if not output.exists() or output.stat().st_size > 8_000_000:
            raise ValueError("Missing or oversized synthesized audio")


class SimulationBackends:
    """Explicit fixtures for UI development. These are not model or audio tests."""
    async def transcribe(self, audio: Path) -> str:
        await asyncio.sleep(.15)
        return "[Simulated transcript] Hello April"

    async def respond(self, text: str) -> str:
        await asyncio.sleep(.3)
        return "[Simulated reply] Hello! I’m April. Ready to tackle one small task together?"

    async def synthesize(self, text: str, output: Path):
        # No fake audible speech: the UI explicitly labels this stage simulated.
        await asyncio.sleep(.15)
