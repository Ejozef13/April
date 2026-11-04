# Validation record — November 3, 2026

## Desktop v0.1 polish — November 4, 2026

Enrique authorized a polished desktop release and a redesign using his actual dog photograph. The current original SVG reflects the tan head, dark folded ears, white muzzle/chest, dark collar and paw tag; the photograph itself is not published. Current screenshots are actual labeled simulation renders of that design. Mouth animation is state-driven, not a claim of phoneme/audio-amplitude synchronization.

The one-command launcher checks local prerequisites without changing services. Fixture tests distinguish unavailable Ollama, missing model names, speech failures, redacted errors, preserved configuration and successful retry. The source code cannot establish the cause of the latest remote desktop failure; the new checks make it diagnosable on that desktop. Physical confirmation of that repair remains pending.

The browser harness passed actual fake-device capture with nonzero input level, mobile overflow checks, full-screen face controls, readiness UI, and timing JSON export with simulation labeling and no transcript/audio. The separate playback harness passed real WAV-tone playback, injected permission retry, pending-play cleanup, media-error preservation, and Stop followed by successful retry. Real model/hardware results remain as separately reported below. Final setup validation passed 24 Python tests; the wheel built successfully and its assets/modules were inspected; no physical performance results have been inferred from these fixtures.

Timing exports are explicit user downloads, include playback outcome and leave loading conditions unknown. Five successful desktop sessions were reported earlier, but the actual five-run numerical samples, real screen/audio walkthrough, and separate physical cancellation observations have not been supplied. Those items remain pending rather than substituted with the new simulated artifacts.


## Desktop follow-up (user-observed results)

### Successful real spoken interaction

After pulling playback fix `c67dcf7`, Enrique reported that the live interaction works. His screenshot shows LIVE mode, the transcript “April, suggest a Python project.”, a generated Pet-Care Scheduler suggestion, Mute off, and the Speaking state. His report confirms audible playback; a screenshot alone cannot prove sound. This establishes one user-observed microphone → Whisper → GPT-OSS → Piper → browser playback interaction. It is not an independently recorded hardware benchmark or a physical Pi test.

Physical Stop/cancel and subsequent retry have not been separately confirmed. Five-run stage measurements, return-to-idle evidence, a real walkthrough recording, and an in-repository live screenshot artifact remain pending. The successful screenshot was shared in chat; it has not been substituted with simulated imagery in the repository. See DESKTOP_ACCEPTANCE.md for capture steps.

### Playback failure follow-up

Enrique's live-browser screenshot shows a generated text reply followed by an interrupted `play()` error. The exact Brave/Piper failure was not reproduced in the cloud; a native WAV tone played successfully. The playback update keeps a mounted media element, invalidates pending playback promises during cleanup, preserves the first media error, and offers an explicit **Play reply** retry when automatic playback is blocked/interrupted. A retry reuses the current audio and remains subject to the server playback deadline; no extra model request is made.

`python scripts/browser_playback_check.py` passed Chromium checks for actual WAV tone playback, injected autoplay denial followed by user retry, completion while `play()` remains pending, injected media error followed by teardown, and Stop followed by successful recovery. The fault injections exercise browser lifecycle handling; the fixture backend is not Piper, Ollama, or physical hardware. JavaScript syntax and diff checks pass. Actual Brave + generated Piper audio was subsequently reported successful as described above; repeated acceptance and physical cancellation measurements remain pending.

Enrique reported successful microphone recording/playback and Piper LJ Speech synthesis on CachyOS. His screenshots show actual Whisper `base.en` transcription of the bundled JFK sample and an actual GPT-OSS 20B answer through Ollama 0.40.13. Ollama reported 100% GPU placement and a 4096-token context. One HTTP request took 5.29 seconds with loading/warmth not established; this is not an end-to-end voice benchmark. The LJ Speech model card lists its dataset as public domain; retain the separate Piper software license obligations.

The desktop integration update adds configurable reasoning effort/context, a bounded 512-token profile for GPT-OSS, exclusion of separate reasoning from final-answer output, and the tested desktop model paths. All 17 automated fixture tests pass after this update; JavaScript syntax and diff checks pass. The complete spoken workflow was subsequently reported successful; cancellation behavior on physical hardware and Pi acceptance remain pending. The cloud-instance results below remain historical cloud results, not claims about desktop hardware.

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

- `docs/evidence/simulation-idle.png`: actual browser idle face with the photo-inspired design.
- `docs/evidence/simulation-face-view.png`, `simulation-mobile.png`: actual full-screen/mobile simulation layouts.
- `docs/evidence/simulation-listening.png`: actual browser with Chromium’s fake microphone.
- `docs/evidence/simulation-reply.png`: actual browser with labeled fixture response.
- `docs/evidence/simulation-walkthrough.webm`: retained copy of the actual automated browser session, originally generated under ignored `artifacts/`. No real voice, model inference or narration.
- `artifacts/browser-check.json`: browser result metadata; fake mic and simulation explicitly identified.

Screenshots are reviewable project assets. The labeled walkthrough is included alongside the screenshots; regenerated artifacts and dependencies remain ignored. There is no invented hardware photo, speech/model performance result, training claim or physical integration claim.

## Saved environment configuration

Draft persistence confirmed: `install_script`, `start_skill`, and the additional custom network destination `huggingface.co`. Existing package-manager presets are preserved. No secret requirement was added. Review and save in environment settings, then publish; saving the draft did not apply networking, publish a snapshot, or validate a new restored task. Artifact redirect hosts may need separate diagnosis after Hugging Face origin access works.

The current-instance simulation and development workflow are verified. The cloud still lacks speech models, Ollama and physical devices; those cloud limitations do not invalidate the later user-observed desktop interaction. Desktop repeatability, model integrity provenance, real benchmark evidence, cancellation acceptance and Pi tests remain outstanding. Optional features are frozen while evidence is collected.


## AM circuit theme and primary portrait update

The newer purple-collar photo supplied by Enrique supersedes the earlier reference for the current cartoon. The head now has a broad forehead and tapered cheeks/muzzle instead of the earlier oval silhouette, with folded ears, dark almond eyes, white muzzle/chest and a purple collar/silver buckle. CSS shows the tongue during listening/thinking, keeps idle closed-mouth, and retains state-driven speaking animation. The original reference photos and AM application files are not published or modified.

The supplied AM screenshot informs a dark grid, lime accents, translucent panels and decorative animated SVG circuit traces. No image-generation service, frontend framework or per-frame JavaScript is required. Reduced motion disables animation; mobile uses fewer decorative traces. Rendering cost on the physical Pi remains unmeasured.

The expanded browser harness passed closed idle mouth, open listening/thinking mouth, non-interactive circuit background, reduced-motion behavior, mobile overflow, face view and existing capture/export checks. Current evidence screenshots and walkthrough remain labeled simulation; the transient thinking state is checked by computed styles rather than presenting a potentially stale screenshot as evidence.


## Plain chest and signal-driven tail

The chest/arm interior strokes were removed, leaving plain white fur. The full-body reference informed a short brown tail with a white tip on the illustration’s right side. It wags rapidly on microphone input above a small level threshold, with a 180 ms hold between syllables, and during acknowledged reply playback. Idle/thinking are stationary; reduced-motion disables wagging. This is decorative signal/state feedback, not voice-activity classification or a physical motor. The original photo is not published.

The browser capture harness passed idle/thinking stationary-tail checks, fake-microphone-driven wagging and reduced-motion checks. The real WAV-tone playback harness passed speaking wagging and stationary idle, plus permission retry, error preservation, cancellation and recovery. Syntax, local documentation links and diff checks passed. Accuracy concerns are recorded in ACCURACY.md as an investigation plan; no Internet search capability or measured accuracy improvement is claimed.


Tail refinement: the tail artwork is scaled to 70%, lowered 16 SVG units with its wag pivot moved to match, and given small fur points on the sides and white tip. The browser capture harness passed idle, signal-driven wagging, reduced-motion, mobile and existing UI checks after this visual-only refinement.


Tail silhouette replacement: the latest supplied illustration supersedes the previous short tuft. The tail is now upright and gently curved, with a broad brown lower section and a long tapered white upper section with fur edges. Existing input/playback wagging and reduced-motion behavior are retained. The simulation browser harness passed and screenshots/video were refreshed.


Final tail-tip refinement: the existing width, brown base and white upper section are preserved; the pointed end is shortened and replaced with a diagonal top edge for the requested cropped-tail cartoon silhouette. Browser capture, wagging, reduced-motion and responsive checks passed; screenshots/video refreshed.
