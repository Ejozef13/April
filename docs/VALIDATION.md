# Validation record — November 3, 2026

## Desktop follow-up (user-observed results)

### Playback failure follow-up

Enrique's live-browser screenshot shows a generated text reply followed by an interrupted `play()` error. The exact Brave/Piper failure was not reproduced in the cloud; a native WAV tone played successfully. The playback update keeps a mounted media element, invalidates pending playback promises during cleanup, preserves the first media error, and offers an explicit **Play reply** retry when automatic playback is blocked/interrupted. A retry reuses the current audio and remains subject to the server playback deadline; no extra model request is made.

`python scripts/browser_playback_check.py` passed Chromium checks for actual WAV tone playback, injected autoplay denial followed by user retry, completion while `play()` remains pending, injected media error followed by teardown, and Stop followed by successful recovery. The fault injections exercise browser lifecycle handling; the fixture backend is not Piper, Ollama, or physical hardware. JavaScript syntax and diff checks pass. Actual Brave + generated Piper audio acceptance remains pending.

Enrique reported successful microphone recording/playback and Piper LJ Speech synthesis on CachyOS. His screenshots show actual Whisper `base.en` transcription of the bundled JFK sample and an actual GPT-OSS 20B answer through Ollama 0.40.13. Ollama reported 100% GPU placement and a 4096-token context. One HTTP request took 5.29 seconds with loading/warmth not established; this is not an end-to-end voice benchmark. The LJ Speech model card lists its dataset as public domain; retain the separate Piper software license obligations.

The desktop integration update adds configurable reasoning effort/context, a bounded 512-token profile for GPT-OSS, exclusion of separate reasoning from final-answer output, and the tested desktop model paths. All 17 automated fixture tests pass after this update; JavaScript syntax and diff checks pass. The complete browser microphone → Whisper → GPT-OSS → Piper → selected output workflow, its cancellation behavior on physical hardware, and Pi acceptance remain pending. The cloud-instance results below remain historical cloud results, not claims about desktop hardware.

The initial checkout contained no files or commits (symbolic unborn `work` branch). No existing application or user changes were overwritten. Implementation was explicitly requested after onboarding began. No commit or push was performed during initial validation; the user subsequently authorized publishing this prototype to GitHub.

| Check | Outcome | What it establishes |
|---|---|---|
| `bash scripts/setup.sh` | Passed | Isolated venv, locked dependencies, editable package installation and 16 tests |
| `APRIL_TOOLS_DIR=/workspace/april-tools bash scripts/setup_speech.sh` | Passed, repeated | Pinned CPU whisper.cpp builds; actual whisper and Piper CLI help run |
| `python -m unittest discover -s tests -v` in `.venv` | 16 passed, 0 failed, 0 skipped | State transitions, bounds, invalid input, origin checks, cancellation, real owned-process termination, lock release, failure recovery, timeout, clock validation, actual local HTTP protocol fixture, speech CLI fixtures, playback acknowledgment |
| `python scripts/browser_smoke.py` | Passed, no page errors | Actual Chromium UI, fake mic capture/WAV upload, simulated STT/reply, real clock tool, cancel/retry lifecycle, screenshots/video |
| `node --check` for UI and capture worklet | Passed | JS syntax only |
| `.venv/bin/python -m pip check` | Passed | Installed Python dependency consistency |
| Wheel build and ZIP contents inspection | Passed | Installable package includes all four browser assets |
| Server SIGINT shutdown and restart | Passed | Clean application shutdown and saved startup command; browser checks passed again after restart |
| Git HTTPS read via existing platform proxy | Completed without credential request | No remote HEAD was returned; repository remains unborn locally |
| Model download origin request | Blocked: proxy 403 for `huggingface.co` | Required environment network setting, not a missing GitHub token |
| Physical audio, actual speech inference, actual Ollama answer | Not run | No sound/GPU device, speech model files or Ollama in this cloud instance |
| Physical Raspberry Pi and authenticated tunnel | Not run | Device and SSH access unavailable here |
| Real performance benchmarks | Not run | Sample count zero; see BENCHMARKS.md |

The 16 tests use fixtures. A local HTTP fixture validates our Ollama streaming contract, not Ollama inference. Fake speech executables validate argument/file/stdin boundaries, not whisper/Piper model quality. The Chromium fake microphone validates browser capture integration, not Enrique’s microphone or adapter compatibility.

Initial issues fixed: the sandbox blocked socket creation (approved execution path used, without proxy bypass); a browser test string predicate conflicted with the app’s strict content policy (test predicate corrected); generated artifact directories broke setuptools auto-discovery (explicit package discovery added). A Starlette test-client deprecation warning remains; the tested HTTPX path still passes. No assertions were disabled.

## Evidence

- `docs/evidence/simulation-idle.png`: actual browser idle face.
- `docs/evidence/simulation-listening.png`: actual browser with Chromium’s fake microphone.
- `docs/evidence/simulation-reply.png`: actual browser with labeled fixture response.
- `docs/evidence/simulation-walkthrough.webm`: retained copy of the actual automated browser session, originally generated under ignored `artifacts/`. No real voice, model inference or narration.
- `artifacts/browser-check.json`: browser result metadata; fake mic and simulation explicitly identified.

Screenshots are reviewable project assets. The labeled walkthrough is included alongside the screenshots; regenerated artifacts and dependencies remain ignored. There is no invented hardware photo, speech/model performance result, training claim or physical integration claim.

## Saved environment configuration

Draft persistence confirmed: `install_script`, `start_skill`, and the additional custom network destination `huggingface.co`. Existing package-manager presets are preserved. No secret requirement was added. Review and save in environment settings, then publish; saving the draft did not apply networking, publish a snapshot, or validate a new restored task. Artifact redirect hosts may need separate diagnosis after Hugging Face origin access works.

The current-instance simulation and development workflow are verified. Live voice readiness is blocked on model access/license/integrity checks, an available local Ollama model, and actual device acceptance. Optional features are frozen while those prerequisites remain outstanding.
