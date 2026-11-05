# Honest timing protocol

No collected multi-run stage or end-to-end hardware benchmark is available. One earlier standalone GPT-OSS request took 5.29 seconds on the desktop, with loading conditions unknown; it is not a voice-pipeline benchmark. Simulation delays are artificial fixtures and must never appear in performance claims.

The UI displays per-job server `perf_counter` timings in milliseconds. `stt_ms` covers CLI startup, model loading and transcription until text is read. `llm_ms` covers HTTP connection through collection of the bounded complete response. `tts_ms` covers CLI startup, voice loading and WAV creation. `tool_ms` replaces LLM timing for the deterministic tool. `server_total_ms` begins after the recording has been received/validated (or text accepted) and ends when synthesis is complete. It excludes recording, network transport, base64 transfer, playback startup and playback duration. Text-only runs have no STT measurement; clock runs have no LLM measurement. Never substitute zero for an unrun stage.

For a desktop acceptance run, record the exact OS/kernel, CPU, RAM free/used, GPU/driver, VRAM occupancy, model tags/quantization, whisper/Piper versions and paths, voice license, selected audio hardware, browser and configuration. Record whether AM or any other model workload was active; do not stop shared services to conceal contention.

Use one fixed clearly transcribed 3–5 second sentence and one fixed question. Capture at least one explicitly cold run and five warm runs per configuration. A subprocess loads speech models each turn, even if OS file caches are warm. Document that distinction. Do not unload shared Ollama models just to manufacture a cold run; use an isolated model session with permission or mark cold LLM pending.

Measure user stop-recording → first audible response separately using a local screen/audio recording with consent and a shared time reference. Also measure cancel click → sound stops. Keep every sample, condition and failure count. Report median and range with sample count only after actual measurements; do not report a percentile from an inadequate sample. Retain transcripts/audio only if the user explicitly chooses to keep benchmark evidence.

| Stage | Hardware / conditions | Sample count | Result |
|---|---|---:|---|
| STT | Desktop / cold and warm pending | 0 | Pending |
| LLM | GPT-OSS 20B / repeated samples pending | 0 | Pending |
| TTS | Piper LJ Speech medium / repeated samples pending | 0 | Pending |
| Stop-recording → audible reply | Real microphone + headphones pending | 0 | Pending |
| Pi transport and client playback | Physical Pi pending | 0 | Pending |

## Collection files

Follow [DESKTOP_ACCEPTANCE.md](DESKTOP_ACCEPTANCE.md). The [CSV template](evidence/desktop-timings.template.csv) contains five unmeasured attempts with blank values, not zero-time results. Copy it into ignored `artifacts/` before filling it. Only publish measured data after checking conditions, failures and privacy.


Private-action turns also report `preparation_ms` for bounded calendar/mail/OCR/
execution preparation before the local-model reply. Their server total carries
the original voice turn start and STT timing when present. User review time
between proposing and confirming an action is excluded. No new numerical
hardware benchmark has been published.
