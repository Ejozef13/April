# Desktop evidence collection

Status: Enrique reported one successful real spoken interaction on November 3, 2026. The live screenshot supplied in chat shows transcription, generated text and Speaking. The following steps collect repeatable evidence; they have not been completed merely by adding this document.

## Prepare without changing shared services

Keep the desktop server running in live mode, Mute off, Razer microphone selected, and the known working output selected. Use the existing GPT-OSS 20B model; do not restart Ollama, stop AM, unload shared models, or pull another model for these measurements.

In a second terminal, collect non-secret system facts:

```bash
cd ~/Projects/April
git rev-parse HEAD
uname -srmo
.venv/bin/python --version
.venv/bin/python -m pip show piper-tts
ollama --version
ollama ps
free -h
```

Record CPU/GPU specifications, input/output hardware, browser version, whether AM or another inference workload was active, and any observed GPU memory usage from your existing monitor. Missing driver/memory details stay unknown. Avoid environment dumps, credential files or logs containing personal prompts.

## Five spoken attempts

1. Say the same question each time: **“April, suggest a Python project.”** Press Finish recording; do not press Send.
2. After playback ends, verify the transcript, visible reply, audible speech and return to Idle.
3. Expand Session timing and copy its complete JSON before starting another turn. Keep all five attempts, including failures. If a failed attempt has no timings, record the failure with blank timings rather than dropping it or substituting zero.
4. Record loading conditions as **unknown** unless observed. If `ollama ps` immediately before a run shows the model loaded, label that run **LLM resident**. Speech subprocesses still reload their models each turn; OS-cache warmth is not measured.
5. Do not describe these five attempts as five cold runs, or as a completed cold/warm benchmark. Do not infer end-to-end audible latency from server processing time.

Optional local record, deliberately ignored by Git:

```bash
mkdir -p artifacts
cp -n docs/evidence/desktop-timings.template.csv artifacts/desktop-timings.csv
```

Fill the copied CSV from the actual UI values. The template's numbered rows are planned attempts, not measurements. Preserve full JSON locally if desired. A reply can vary between attempts, so note response length or obvious differences. Share the five results and all failure notes for review before calculating a median/range. No percentile or speedup claim is warranted yet.

## Cancellation and recovery

- During an active request, press Stop / cancel. Confirm no later answer starts playing and the interface returns to Idle.
- During actual speech, press Stop. Confirm sound stops and Idle returns.
- After each cancellation, record another short question and verify a complete reply without restarting the application.
- Check Mute separately: it suppresses audio; a completed generation should still show its text. Record any difference from this behavior.

Write down which operation was active when you pressed Stop and whether recovery passed. These observations are separate from automated fixture tests. Click-to-silence latency remains unmeasured unless captured with a time reference.

## Record a real 30–60 second walkthrough

Use a screen recorder already available on your desktop. If none is available, report that before installing one. On KDE, check whether Spectacle offers screen recording. Verify whether the chosen recorder captures application/system audio; screen recording alone does not establish audible TTS. Headphones may keep April's voice out of a microphone-only recording.

Record only the APRIL window, with private tabs/notifications hidden:

1. Show the LIVE badge and briefly explain that inference is local and uses pretrained models.
2. Record the fixed question, showing Listening and the resulting transcript.
3. Let April finish an audible reply and return to Idle. Keep the app output audio in the recording if supported.
4. Show Stop during speech and a successful next request if time permits; otherwise capture cancellation separately.
5. Open timing details. Explain that those values exclude capture, transport and playback.

Save the initial recording under ignored `artifacts/`, for example `artifacts/desktop-live-walkthrough.webm`. Review it before publishing. Explicitly note any missing system audio, cuts, or unrecorded stages. Do not rename the existing simulation video as real evidence.

Save a clean live screenshot locally too. The screenshot already supplied in chat is evidence of UI state but is not yet a versioned repository image. After review, selected real assets can be copied under `docs/evidence/` and committed; raw conversations, model files, credentials and unrelated desktop footage remain excluded. Keep large recordings outside Git and link a reviewed hosted video when appropriate.

## Current acceptance record

| Capability | Evidence | Status |
|---|---|---|
| Mic → Whisper → GPT-OSS → Piper → audible browser reply | Enrique's report plus live screenshot in chat | One successful interaction reported |
| Speaking state | Live screenshot | Observed |
| Return to Idle after audible reply | Separate explicit observation | Pending |
| Stop during generation / speech and successful retry | Physical desktop observation | Pending |
| Five spoken timing attempts and failure count | UI JSON plus run conditions | Pending |
| Real walkthrough with application audio | Reviewed desktop recording | Pending |
| Live screenshot stored in Git | Reviewed original image file | Pending |
| Physical Pi | Hardware, OS, audio, tunnel and browser checks | Pending |

Once these desktop checks are documented, freeze optional features and proceed to the Pi plan in PI.md. A working desktop demo does not verify the Pi or require new purchases.
