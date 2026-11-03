# Stack decisions and primary sources

Documentation inspected on November 3, 2026. Builds and local CLI help were checked separately from inference. No reference dog photo was provided or inspected; the SVG is original and replaceable through `april/web/index.html` and CSS.

| Choice | Why | License / download / compatibility |
|---|---|---|
| Python + FastAPI + WebSocket + plain browser JS | Small modules; one long-lived cancellable interaction; no frontend build system | Python 3.11+, pinned package versions in `requirements.lock`; cloud validated on 3.12 / x86_64 |
| whisper.cpp v1.9.5, commit `d1be6fde11ac6e0407606b4e42fe72d34add8037` | CPU-only baseline, local CLI, supports x86 and ARM; no CUDA requirement | MIT engine; converted Whisper `ggml` model downloaded separately. `base.en` is a proposed English starting point, not installed or benchmarked here. |
| OHF Piper `piper-tts==1.8.0` | Local CPU ONNX synthesis, process isolation, no voice cloning | Engine GPL-3.0-or-later. Each voice has its own model card and terms. `.onnx` + matching `.onnx.json` required. Check voice licensing before use/distribution. Candidate Lessac voice license remains unverified because its host is blocked here. |
| Existing Ollama | Reuse Enrique’s local service/model where practical | Ollama MIT; model licenses vary by exact tag. Suggested Qwen tag is configurable and unverified. No new shared service, GPU driver, or model installed here. |

Piper’s current repository explicitly says it is looking for maintainers. This is an upstream maintenance risk, not a reason to silently use the archived original. Keep it behind an adapter and pin the tested release. Its CLI documentation warns that loading a voice each invocation is slower than a persistent server. APRIL accepts that cost initially to simplify cancellation and release CPU memory. Do not assert a latency benefit without measuring it.

whisper.cpp documents CPU-only inference and separate AMD ROCm support. We explicitly disable CUDA/HIP/Vulkan for the initial speech build. This establishes a CPU route compatible with the desktop architecture, not verified RX 9070 XT acceleration. Pi browser packaging does not require Pi inference. Browser device IDs depend on origin and permissions and may change; refresh the device list.

Primary sources:

- [whisper.cpp README and CPU/AMD support](https://github.com/ggml-org/whisper.cpp), [MIT license](https://github.com/ggml-org/whisper.cpp/blob/master/LICENSE), [model formats/downloads](https://github.com/ggml-org/whisper.cpp/tree/master/models).
- [OpenAI Whisper model/code license](https://github.com/openai/whisper/blob/main/LICENSE).
- [Current Piper repository](https://github.com/OHF-Voice/piper1-gpl), [CLI](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md), [GPL text](https://github.com/OHF-Voice/piper1-gpl/blob/main/COPYING).
- [Piper voice cards and files](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/medium) — access blocked here; voice-specific review pending.
- [Ollama API](https://docs.ollama.com/api/chat), [AMD support](https://docs.ollama.com/gpu), [license](https://github.com/ollama/ollama/blob/main/LICENSE) — API contract implemented; actual desktop service and GPU compatibility pending.
- [Browser microphone security requirements](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia#privacy_and_security), [output selection](https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/setSinkId).

## Model preparation on the desktop (not executed here)

After reviewing licenses and available disk/RAM:

```bash
# From the pinned whisper.cpp source directory created by setup_speech.sh:
bash models/download-ggml-model.sh base.en
# From the APRIL project directory:
.venv/bin/python -m piper.download_voices --data-dir models en_US-lessac-medium
```

Use the actual resulting absolute paths in `april.local.toml`. Model download destinations include `huggingface.co` and whatever artifact redirect host that service returns. The cloud request to Hugging Face returned a policy 403; only the identified origin domain is requested in the draft. Additional redirect destinations must be diagnosed after origin access works. Do not disable checksums/signatures/TLS or replace expected hashes to force a download.

The CPU binaries and installed Python distributions are prepared. A successful `--help` does not validate a model file or successful transcription/synthesis. Model integrity verification and voice-license review remain required before declaring the live speech workflow ready.
