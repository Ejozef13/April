# Honest timing protocol

No real STT, LLM, TTS or end-to-end hardware latency figures have been measured. Simulation delays are artificial fixtures and must never appear in performance claims.

The UI displays per-job server `perf_counter` timings in milliseconds. `stt_ms` covers CLI startup, model loading and transcription until text is read. `llm_ms` covers HTTP connection through collection of the bounded complete response. `tts_ms` covers CLI startup, voice loading and WAV creation. `tool_ms` replaces LLM timing for the deterministic tool. `server_total_ms` begins after the recording has been received/validated (or text accepted) and ends when synthesis is complete. It excludes recording, network transport, base64 transfer, playback startup and playback duration. Text-only runs have no STT measurement; clock runs have no LLM measurement. Never substitute zero for an unrun stage.

For a desktop acceptance run, record the exact OS/kernel, CPU, RAM free/used, GPU/driver, VRAM occupancy, model tags/quantization, whisper/Piper versions and paths, voice license, selected audio hardware, browser and configuration. Record whether AM or any other model workload was active; do not stop shared services to conceal contention.

Use one fixed clearly transcribed 3–5 second sentence and one fixed question. Capture at least one explicitly cold run and five warm runs per configuration. A subprocess loads speech models each turn, even if OS file caches are warm. Document that distinction. Do not unload shared Ollama models just to manufacture a cold run; use an isolated model session with permission or mark cold LLM pending.

Measure user stop-recording → first audible response separately using a local screen/audio recording with consent and a shared time reference. Also measure cancel click → sound stops. Keep every sample, condition and failure count. Report median and range with sample count only after actual measurements; do not report a percentile from an inadequate sample. Retain transcripts/audio only if the user explicitly chooses to keep benchmark evidence.

| Stage | Hardware / conditions | Sample count | Result |
|---|---|---:|---|
| STT | Desktop / cold and warm pending | 0 | Pending |
| LLM | Existing desktop Ollama model pending | 0 | Pending |
| TTS | Desktop / licensed voice pending | 0 | Pending |
| Stop-recording → audible reply | Real microphone + headphones pending | 0 | Pending |
| Pi transport and client playback | Physical Pi pending | 0 | Pending |
