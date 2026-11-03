# Explain APRIL in an interview

“APRIL explores an interactive audio system with an expressive dog interface. Python coordinates replaceable local speech and model backends, while a browser handles devices. Enrique has completed a real spoken interaction on his desktop; automated tests use fixtures. Repeatable physical acceptance, timing evidence and Pi testing remain pending.”

Walk through one turn: browser permission and selected input → bounded recording → resampled mono PCM16 WAV → validated server input → CPU STT → visible transcript → streamed local Ollama response → CPU TTS → browser output selection → actual playback acknowledgment → idle. Explain how text fallback isolates model/synthesis failures from capture/STT failures.

The state machine represents I/O lifecycle, not model thoughts. A single global lock prevents overlapping voice jobs. Cancellation closes our model request, terminates owned child processes, stops browser audio/tracks and releases the lock. An error can be retried in the same running application. Shared AM services remain untouched.

Three tradeoffs to discuss:

1. **CPU speech versus GPU speech:** avoids assuming CUDA/ROCm compatibility and reduces VRAM competition, at potentially higher latency. Measure before optimizing.
2. **Process per speech stage versus a persistent model server:** easier cancellation/resource cleanup, but repeated model loads. CLI boundaries also make replacement understandable.
3. **Browser client versus native device UI:** reuses existing monitor/headphones, supports a lightweight Pi client and accessible controls, but microphone secure contexts, output-selection support and permission flow need explicit handling. Authenticated SSH tunneling preserves localhost semantics.

Demonstrate failure recovery and cancellation rather than adding wake words or hardware movement. Explain why a clock button uses a deterministic function instead of trusting a language model’s current-time answer. Discuss tests with fakes separately from hardware/model integration evidence.

Resume bullet drafts supported by current evidence:

- Implemented and user-tested a local push-to-talk voice pipeline combining CPU Whisper transcription, GPT-OSS 20B through Ollama, and CPU Piper synthesis with a browser dog interface.

- Built a Python/WebSocket companion prototype with an original SVG dog interface, explicit interaction states, bounded recordings and response limits, and replaceable local STT/LLM/TTS adapters.
- Verified cancellation, process cleanup, tool validation and failure recovery with automated fixture-based tests; exercised the browser workflow with a fake microphone and captured a labeled simulation walkthrough.

A real end-to-end local voice interaction can now be described as user-tested on Enrique’s desktop. Ollama reported GPU placement; do not generalize that into driver certification or performance claims. Do not yet claim production deployment, Pi hardware integration, latency improvements, model training, or fine-tuning. Performance samples and physical cancellation/retry evidence remain pending.
