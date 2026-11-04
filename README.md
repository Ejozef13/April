# APRIL · Desktop v0.1

A local voice companion inspired by Enrique’s Jack Russell. Built by Enrique, a George Mason University computer science student expecting to graduate in May 2028. APRIL demonstrates interactive systems, audio integration, and reliable software design using pretrained models—not model training or fine-tuning.

**Verified desktop milestone:** Enrique reported five successful real voice sessions on CachyOS: microphone → CPU Whisper → local GPT-OSS 20B → CPU Piper → audible browser playback. A live screenshot and his report confirm the interaction; the five numerical timing samples and physical cancellation observations were not supplied. Automated cloud tests use fixtures. Pi operation and automatic desktop offloading are not implemented yet.

![Photo-inspired April design shown in a labeled simulation browser session](docs/evidence/simulation-idle.png)

The primary reference is April’s newer purple-collar portrait: broad tan forehead, tapered cheeks/muzzle, large folded ears, dark almond eyes, white chest, purple collar and silver buckle. The interface matches the supplied AM reference with a dark grid, lime accents and animated circuit traces. April’s tongue peeks out while listening/thinking; her mouth is closed at idle. Circuit motion is decorative and respects reduced-motion preferences. It is original code-rendered artwork; the personal photo is not bundled. Above is an actual **simulation** UI screenshot, not fabricated live evidence. [Full-screen face](docs/evidence/simulation-face-view.png) · [Labeled simulation walkthrough](docs/evidence/simulation-walkthrough.webm).

The full-body reference informs the plain white chest and short brown tail with a white tip on the illustration's right side. The tail wags quickly during detected microphone signal and actual reply playback, stays still at idle/thinking, and respects reduced motion. Input-level detection is not speech recognition. For inaccurate answers, see [the diagnosis and grounded-answer plan](docs/ACCURACY.md); Internet connectivity alone does not give the local model web access.

## Start on your already-configured desktop

```bash
cd ~/Projects/April
bash april.sh
```

One command checks executable/model/voice files and the configured model in Ollama, then starts **LIVE** mode. It never starts/stops shared services or loads/unloads models during checks. Existing `april.local.toml` is preserved; if absent, the desktop profile is copied into that ignored file. Checks establish prerequisites, not successful inference or model integrity. They can’t predict whether a service will disappear later.

If Ollama is stopped, the launcher tells you to check `systemctl status ollama` and start your existing service with `sudo systemctl start ollama`. Resolve the reported issue and rerun the same APRIL command. This addresses the previously undiagnosed generic backend failure without assuming its cause on your desktop.

```bash
bash april.sh --check               # Read-only checks, no server
bash april.sh --simulation          # Explicit canned replies; no speech/models
```

Open the local address printed in your desktop terminal. Refresh after updates. Cloud onboarding does not provide a localhost web preview. Stop only APRIL with Ctrl+C; leave shared AM/Ollama services intact.

## First installation

Requires Git, a modern browser, and Python 3.12 for the tested dependency set. `uv` can install a separate Python 3.12 without changing CachyOS system Python. Existing virtual environments are preserved. No purchases or API keys are needed.

```bash
git clone https://github.com/Ejozef13/April.git
cd April
bash scripts/setup.sh
bash scripts/setup_speech.sh
```

The speech script needs a C/C++ compiler and Make, and builds CPU-only whisper.cpp with four workers. Prepare the model files using [STACK.md](docs/STACK.md). The launcher’s desktop profile expects:

| Component | Default desktop configuration |
|---|---|
| LLM | Existing `gpt-oss:20b` in loopback Ollama; low reasoning, 4096-token context, 512-token generation budget |
| STT | `.tools/whisper.cpp/build/bin/whisper-cli`, `.tools/whisper.cpp/models/ggml-base.en.bin` |
| TTS | `.venv/bin/piper`, `models/en_US-ljspeech-medium.onnx` and matching `.onnx.json` |
| Audio | Browser-selected microphone/output, 15-second recording maximum |
| Response | Maximum 600 visible/spoken characters; generation budget includes reasoning |
| Timeouts | 90-second processing deadline, 60-second playback deadline |

Change settings in ignored `april.local.toml` or select another config through `APRIL_CONFIG`. Resolve relative paths from the project directory. Inspect `ollama list`, `ollama ps`, available RAM/VRAM and existing AM workloads before changing models. Never assume several models fit simultaneously. Use [april.example.toml](april.example.toml) for other backends; the supported desktop starting profile is [april.desktop.example.toml](april.desktop.example.toml).

## Use April

1. Grant microphone permission with **Enable / refresh devices** and select a real input. The level meter shows captured signal while recording; it does not prove recognition accuracy.
2. Press **Start recording**, speak, then **Finish recording**. Alt+R is the keyboard fallback. Submission is automatic—Send belongs to typed text only.
3. Read the transcript and response. April enters Speaking only after browser playback begins. **Play reply** retries blocked/interrupted playback using the same audio.
4. **Stop / cancel** or Escape releases recording/playback and cancels the owned job. Mute suppresses audio; a completed generated response still appears as text.
5. Use **Face view** for a full-screen presentation with Record, Stop, Mute and clock controls available. Return with Show controls. Reduced-motion settings are respected.
6. **Current time**, “April, what time is it?” and “Tell me the time” call the deterministic clock rather than asking the model. The transcript is preserved. The model does not execute shell commands or select arbitrary tools.

States: idle, listening, transcribing, thinking, speaking, error. Thinking means waiting on a response or preparing its voice; expressions do not reveal model reasoning. Mouth animation follows the speaking state, not phoneme-accurate lip sync. One global job runs at a time, with no application backlog. A new attempt can recover after a failure without restarting APRIL.

## Read-only integration preview

[INTEGRATIONS.md](docs/INTEGRATIONS.md) contains the setup for the requested `~/Documents/aprilfiles` folder, local SearXNG (default), optional Brave Search, and Gmail read-only OAuth. They are opt-in and **not connected to your personal accounts by this code update**. API/folder boundaries are fixture-tested, and Enrique has now reported the approved folder retrieval working. Web/Gmail live authentication and provider quality checks still require desktop setup. Private/external retrieval is disabled in simulation.

Use explicit “search my files for …”, “search my emails for …”, “search the web for …” or the corresponding search buttons. Retrieved sources appear in a review panel and are passed only to the local model. A narrow current-fact router requests a web source instead of silently guessing from old model weights. Missing credentials/service produce actionable errors. Web queries go through your explicitly selected search provider; private excerpts never automatically fall back to web search. No mail sending/deletion, source-file changes, background mailbox crawl or arbitrary system access is provided.

Document RAG uses SQLite keyword retrieval over approved UTF-8 text formats; PDFs/Word/embedding search are not implemented. The index retains private excerpts locally. Gmail tokens/search keys persist outside Git with private permissions; Google browser consent and your own provider key are required. Normal conversation and the clock remain offline-capable.

For subscription-free web search, follow [SEARXNG.md](docs/SEARXNG.md). It provides a pinned, loopback-only service with JSON enabled. Brave remains an optional explicit switch; APRIL never silently falls back to a paid API. Service health does not prove engine access or result quality.

## Diagnostics and evidence

Open **Setup & local services** to repeat read-only checks. Errors distinguish unavailable Ollama, missing models, unusable generation output, Whisper/Piper failures and invalid synthesized WAV. Prompt text, remote error bodies and reasoning are not emitted as diagnostics.

Open **Session timing** after a turn. **Save timing JSON** is an explicit local download containing stage timings, model settings, simulation/live labeling and playback outcome. It excludes transcripts and audio, defaults loading conditions to unknown, and never uploads data. Export after playback completes; cancelled/muted/failed playback must not be labeled successful. Server total excludes capture, transport and playback. See [benchmark boundaries](docs/BENCHMARKS.md).

Follow the [desktop acceptance and real-walkthrough checklist](docs/DESKTOP_ACCEPTANCE.md). Five successful sessions were reported, but numerical measurements, a real recorded walkthrough and separately confirmed physical cancellation/retry remain pending. Do not replace them with fixture results.

```bash
.venv/bin/python -m unittest discover -s tests -v
# Optional: invoking Python needs Playwright; system needs Chromium and FFmpeg.
python scripts/browser_smoke.py          # Requires the simulation server running
python scripts/browser_playback_check.py # Starts its own WAV-tone fixture server
```

[Validation record](docs/VALIDATION.md) · [Desktop release notes](docs/RELEASE_v0.1.md) · [Interview guide](docs/INTERVIEW.md).

## Hardware and roadmap

| Hardware | Observed status |
|---|---|
| CachyOS, Ryzen 7 9700X, RX 9070 XT 16 GB, 32 GB RAM | Specifications supplied by Enrique; speech interaction reported successful. Ollama screenshot reported GPT-OSS 100% GPU placement. Exact driver/runtime and contention measurements pending. |
| Razer Seiren Mini and existing output/headphones | PipeWire enumeration seen; independent recording/playback and APRIL speech reported successful |
| Raspberry Pi 5 16 GB with active cooler | User-owned; Raspberry Pi OS 64-bit selected. Actual installed OS, storage, audio, local model speed and fallback not verified. |
| Dedicated display, USB audio and enclosure | Not required for desktop release; purchases and compatibility remain user decisions |

The goal is **Pi-first standalone assistance plus authenticated desktop acceleration**, not a permanently desktop-dependent face terminal. The [roadmap](docs/ROADMAP.md) separates that future work from Desktop v0.1. Read [PI.md](docs/PI.md) for the existing tunnel/client experiment; that experiment does not implement local Pi inference or automatic fallback.

## Privacy, limits and troubleshooting

No persistent conversation memory, transcript database, automatic audio archive or browser local storage is enabled. Browser memory and private temporary job files support the CLI stages; files are deleted on completion, failure or cancellation. A hard kill/power loss can leave OS temporary files. Use a RAM-backed `TMPDIR` when desired. Timing download, copying a transcript and screen recording are explicit retention actions. Clear your tab to remove its displayed exchange and retrieved excerpts. Explicit document indexing persists a private local SQLite index; Gmail/search credentials persist in private files outside the repository. Review retention and disconnect steps in INTEGRATIONS.md.

Default binding and Ollama endpoints are loopback-only. Host/origin checks, no CORS, restrictive content policy and no external UI assets reduce unintended browser access. This remains a single-user local prototype. The clock validates its empty arguments. Opt-in read-only retrieval is distinct from filesystem/system control; Navidrome, wake words, motors and autonomous actions are not implemented. Model answers can be inaccurate and are not authoritative live facts.

| Symptom | Action |
|---|---|
| Canned transcript or no model speech | Check the badge; `bash april.sh` starts live, `--simulation` intentionally uses fixtures |
| Ollama unavailable | Check existing service; start it if stopped, then retry. No reinstall or APRIL restart normally needed. |
| Model not found | Match `model` to `ollama list`; don’t download duplicates blindly |
| Microphone unavailable | Use localhost/HTTPS, grant permission, select actual input. Adapters alone do not establish ADC/DAC hardware. |
| Output missing/blocked | Unmute, check system routing, try Play reply or system-default output. Browser output selection support varies. |
| Speech failure | Use Check setup; validate matching speech binary/model/voice configuration |
| Timeout or busy | Shorten input, inspect contention, cancel the active turn. APRIL never force-unloads shared models. |
| Browser connection closed | Restart APRIL if necessary and reload; socket loss cancels its job |

## Project map

| Path | Responsibility |
|---|---|
| `april.sh`, `april/launch.py`, `april/readiness.py` | One-command startup and read-only prerequisite checks |
| `april/config.py`, `*.example.toml` | Runtime settings outside application logic |
| `april/state.py`, `april/session.py` | Explicit states, bounded serial jobs, cancellation and timing |
| `april/audio.py`, `april/backends.py`, `april/errors.py` | Audio validation, replaceable local adapters and redacted actionable errors |
| `april/server.py`, `april/tools.py` | Local API lifecycle, origin boundary and spoken/button clock |
| `april/documents.py`, `april/knowledge.py`, `april/gmail.py`, `april/integrations.py` | Opt-in bounded retrieval and secure local account setup |
| `april/evaluate.py`, `april/evaluation_cases.json` | Text-only baseline with human rubrics; no automatic accuracy claim |
| `april/web/` | Photo-inspired SVG, accessible controls, capture worklet and playback |
| `tests/`, `scripts/`, `docs/` | Reliability checks, repeatable setup, architecture and honest evidence |
